"""
Turn an invoice file into something a model can read.

The guiding rule is text first. Chinese electronic invoices almost always
carry a real text layer, and reading it costs a fraction of a vision call
while getting amounts and tax numbers exactly right instead of hoping OCR
saw them correctly. Vision is the fallback for scans and photos, not the
default path.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Below this, a PDF "text layer" is page furniture rather than an invoice.
MIN_TEXT_LAYER_CHARS = 40

# Pages are rendered at 2x so small print survives the trip to the model.
RENDER_SCALE = 2

# OFD stores visible glyphs in TextCode elements inside Content.xml.
OFD_TEXT_PATTERN = re.compile(
    r"<[^>]*TextCode[^>]*>(.*?)</[^>]*TextCode>", re.IGNORECASE | re.DOTALL
)
OFD_XML_TAG_PATTERN = re.compile(r"<[^>]+>")
OFD_CDATA_PATTERN = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)


class DecodeMode:
    TEXT = "text"
    IMAGE = "image"


class DecodeError(Exception):
    """The file could not be turned into text or images."""


@dataclass
class DecodedSource:
    """What recognition will actually look at."""

    mode: str
    text: str = ""
    images: list[tuple[str, bytes]] = field(default_factory=list)
    page_count: int = 0
    decoder: str = ""
    # Fields the document states about itself, in the shape extraction
    # returns. A 全电 OFD names which drawn object holds which field, so
    # those values are known exactly rather than read back off the page.
    fields: dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.images

    def image_data_urls(self) -> list[str]:
        return [
            f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"
            for mime, blob in self.images
        ]


def _read_pdf_text(document, max_pages: int) -> str:
    parts = []
    for index in range(min(len(document), max_pages)):
        page = document[index]
        textpage = page.get_textpage()
        try:
            parts.append(textpage.get_text_range())
        finally:
            textpage.close()
    return "\n".join(part for part in parts if part)


def _render_pdf_images(document, max_pages: int) -> list[tuple[str, bytes]]:
    import io

    images = []
    for index in range(min(len(document), max_pages)):
        page = document[index]
        bitmap = page.render(scale=RENDER_SCALE)
        pil_image = bitmap.to_pil()
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        images.append(("image/png", buffer.getvalue()))
    return images


def decode_pdf(path: str, max_pages: int = 3) -> DecodedSource:
    """Read the text layer if there is one, otherwise render the pages."""
    import pypdfium2

    document = pypdfium2.PdfDocument(path)
    try:
        page_count = len(document)
        text = _read_pdf_text(document, max_pages)

        if len(text.strip()) >= MIN_TEXT_LAYER_CHARS:
            return DecodedSource(
                mode=DecodeMode.TEXT,
                text=text,
                page_count=page_count,
                decoder="pdf_text_layer",
            )

        images = _render_pdf_images(document, max_pages)
        return DecodedSource(
            mode=DecodeMode.IMAGE,
            images=images,
            page_count=page_count,
            decoder="pdf_render",
        )
    finally:
        document.close()


def _strip_ofd_markup(fragment: str) -> str:
    """
    Take the text out of a TextCode element.

    CDATA has to be unwrapped before tags are stripped, because a CDATA
    section looks exactly like one long tag to the stripper and would be
    deleted whole. Issuers put the labels in as plain text and the values
    in CDATA, so getting this wrong reads an invoice as a blank form:
    "发票号码：" and "价税合计" survive while the number and the amount do
    not.
    """
    fragment = OFD_CDATA_PATTERN.sub(lambda m: m.group(1), fragment)
    return OFD_XML_TAG_PATTERN.sub("", fragment).strip()


# Doc_0/Tags/CustomTag.xml names the drawn object that carries each
# invoice field, so the values can be read from the document's own index
# instead of being recognized off the page.
OFD_TAG_FIELDS = {
    "InvoiceNo": "invoice_no",
    "IssueDate": "issue_date",
    "BuyerName": "buyer_name",
    "BuyerTaxID": "buyer_tax_id",
    "SellerName": "seller_name",
    "SellerTaxID": "seller_tax_id",
    "TaxInclusiveTotalAmount": "total_amount",
    "TaxExclusiveTotalAmount": "amount_excl_tax",
    "TaxTotalAmount": "tax_amount",
}

OFD_TAG_REF_PATTERN = re.compile(
    r"<(?:[\w.-]+:)?(\w+)>\s*"
    r"<[^>]*ObjectRef[^>]*>(\d+)</[^>]*ObjectRef>",
    re.IGNORECASE,
)
OFD_TEXT_OBJECT_PATTERN = re.compile(
    r"<[^>]*TextObject[^>]*\bID=\"(\d+)\"[^>]*>(.*?)</[^>]*TextObject>",
    re.IGNORECASE | re.DOTALL,
)
OFD_AMOUNT_CHARS = "¥￥, \t\r\n"
OFD_DATE_PATTERN = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")


def _ofd_object_text(content: str) -> dict:
    """Map each drawn object's id to the text it renders."""
    texts = {}
    for object_id, body in OFD_TEXT_OBJECT_PATTERN.findall(content):
        parts = [
            _strip_ofd_markup(match)
            for match in OFD_TEXT_PATTERN.findall(body)
        ]
        value = "".join(part for part in parts if part)
        if value:
            texts[object_id] = value
    return texts


def _ofd_clean_amount(value: str) -> str:
    return value.strip(OFD_AMOUNT_CHARS).replace(",", "")


def _ofd_clean_date(value: str) -> str:
    match = OFD_DATE_PATTERN.search(value)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _ofd_declared_fields(archive) -> dict:
    """
    Read the invoice out of the document's own field index.

    Only the fields the index names are returned: it carries no invoice
    type, category or line items, so this states what the document is
    certain about and leaves the rest to be read as usual.
    """
    names = {name.lower(): name for name in archive.namelist()}
    tag_name = next(
        (
            original
            for lowered, original in names.items()
            if lowered.endswith("customtag.xml")
        ),
        None,
    )
    content_name = next(
        (
            original
            for lowered, original in names.items()
            if lowered.endswith("content.xml")
        ),
        None,
    )
    if not tag_name or not content_name:
        return {}

    tags = archive.read(tag_name).decode("utf-8", errors="ignore")
    refs = {
        OFD_TAG_FIELDS[element]: object_id
        for element, object_id in OFD_TAG_REF_PATTERN.findall(tags)
        if element in OFD_TAG_FIELDS
    }
    if not refs:
        return {}

    content = archive.read(content_name).decode("utf-8", errors="ignore")
    texts = _ofd_object_text(content)

    fields = {}
    for name, object_id in refs.items():
        value = texts.get(object_id, "").strip()
        if not value:
            continue
        if name in ("total_amount", "amount_excl_tax", "tax_amount"):
            value = _ofd_clean_amount(value)
        elif name == "issue_date":
            value = _ofd_clean_date(value)
        if value:
            fields[name] = value

    return fields


# An OFD page states its size in millimetres; this many pixels per
# millimetre gives a page a vision model can read without producing an
# image too large to send.
OFD_PIXELS_PER_MM = 4
OFD_MAX_PAGE_PIXELS = 4000
# A quadratic segment is drawn as this many straight ones. Glyph curves
# are small, and more segments buy nothing a model would notice.
OFD_CURVE_STEPS = 8

OFD_PAGE_PATTERN = re.compile(
    r"<(?:\w+:)?PhysicalBox>([^<]+)</(?:\w+:)?PhysicalBox>"
)
OFD_PATH_OBJECT_PATTERN = re.compile(
    r"<(?:\w+:)?PathObject\b([^>]*)>(.*?)</(?:\w+:)?PathObject>", re.S
)
OFD_PATH_PATTERN = re.compile(
    r"<(?:\w+:)?AbbreviatedData>([^<]*)</(?:\w+:)?AbbreviatedData>"
)
OFD_DRAW_PARAM_PATTERN = re.compile(
    r"<(?:\w+:)?DrawParam\b([^>]*)>(.*?)</(?:\w+:)?DrawParam>", re.S
)
OFD_FILL_COLOR_PATTERN = re.compile(
    r"<(?:\w+:)?FillColor\b[^>]*Value=\"([^\"]+)\""
)
OFD_ID_PATTERN = re.compile(r'ID="([^"]+)"')
OFD_DRAW_PARAM_REF_PATTERN = re.compile(r'DrawParam="([^"]+)"')
OFD_TOKEN_PATTERN = re.compile(r"[A-Za-z]|-?\d+(?:\.\d+)?")

BLACK = (0, 0, 0)


def _ofd_fill_colors(archive) -> dict:
    """
    Map each draw parameter to the colour it fills with.

    Without this every path is drawn the same, and the first one is the
    page background: a full-page rectangle filled white, which painted
    black hides the whole invoice behind it.
    """
    colors: dict = {}
    for name in archive.namelist():
        if not name.lower().endswith(".xml"):
            continue
        if "res" not in name.lower():
            continue
        try:
            raw = archive.read(name).decode("utf-8", errors="ignore")
        except KeyError:
            continue
        for attrs, body in OFD_DRAW_PARAM_PATTERN.findall(raw):
            found = OFD_ID_PATTERN.search(attrs)
            fill = OFD_FILL_COLOR_PATTERN.search(body)
            if not found or not fill:
                continue
            parts = fill.group(1).split()
            if len(parts) < 3:
                continue
            try:
                colors[found.group(1)] = tuple(
                    max(0, min(255, int(float(part)))) for part in parts[:3]
                )
            except ValueError:
                continue
    return colors


def _ofd_subpaths(data: str) -> list[list[tuple[float, float]]]:
    """
    Turn one path's abbreviated data into closed polylines.

    Only the commands a printed invoice uses are handled: move, line,
    quadratic curve, cubic curve and close. Curves are flattened rather
    than drawn, because the result is filled and a few straight segments
    per glyph stroke are indistinguishable at reading size.
    """
    tokens = OFD_TOKEN_PATTERN.findall(data or "")
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    index = 0

    def take(count: int) -> list[float]:
        nonlocal index
        values = [float(token) for token in tokens[index:index + count]]
        index += count
        return values

    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in ("M", "S"):
            if len(current) > 2:
                subpaths.append(current)
            point = take(2)
            current = [(point[0], point[1])] if len(point) == 2 else []
        elif command == "L":
            point = take(2)
            if len(point) == 2 and current:
                current.append((point[0], point[1]))
        elif command == "Q":
            values = take(4)
            if len(values) == 4 and current:
                x0, y0 = current[-1]
                cx, cy, x1, y1 = values
                for step in range(1, OFD_CURVE_STEPS + 1):
                    t = step / OFD_CURVE_STEPS
                    inv = 1 - t
                    current.append(
                        (
                            inv * inv * x0 + 2 * inv * t * cx + t * t * x1,
                            inv * inv * y0 + 2 * inv * t * cy + t * t * y1,
                        )
                    )
        elif command == "B":
            values = take(6)
            if len(values) == 6 and current:
                x0, y0 = current[-1]
                c1x, c1y, c2x, c2y, x1, y1 = values
                for step in range(1, OFD_CURVE_STEPS + 1):
                    t = step / OFD_CURVE_STEPS
                    inv = 1 - t
                    current.append(
                        (
                            inv ** 3 * x0 + 3 * inv * inv * t * c1x
                            + 3 * inv * t * t * c2x + t ** 3 * x1,
                            inv ** 3 * y0 + 3 * inv * inv * t * c1y
                            + 3 * inv * t * t * c2y + t ** 3 * y1,
                        )
                    )
        elif command == "C":
            if len(current) > 2:
                subpaths.append(current)
            current = []
        else:
            # An unknown command carries operands this reader cannot place,
            # so the rest of the path is no longer trustworthy.
            break

    if len(current) > 2:
        subpaths.append(current)
    return subpaths


def _render_ofd_page(content: str, colors: dict):
    """
    Draw one page's filled paths, in the colours the document names.

    Subpaths within a path are combined by even-odd, which is what puts
    the hole in a 口 and the counter in an 8; filling them one after
    another would black those in.
    """
    from PIL import Image, ImageChops, ImageDraw

    box = OFD_PAGE_PATTERN.search(content)
    if not box:
        return None
    numbers = [float(value) for value in box.group(1).split()]
    if len(numbers) != 4:
        return None
    _, _, width_mm, height_mm = numbers
    if width_mm <= 0 or height_mm <= 0:
        return None

    # One scale for both axes. Capping them separately squashes a page
    # that is long in one direction - 2000x100mm came out 10:1 instead of
    # 20:1 - and characters a model has to read are the last thing to
    # distort.
    scale = min(
        OFD_PIXELS_PER_MM,
        OFD_MAX_PAGE_PIXELS / width_mm,
        OFD_MAX_PAGE_PIXELS / height_mm,
    )
    width = int(width_mm * scale)
    height = int(height_mm * scale)
    if width < 2 or height < 2:
        return None

    scale_x = width / width_mm
    scale_y = height / height_mm
    page = Image.new("RGB", (width, height), (255, 255, 255))
    drawn = 0

    for attrs, body in OFD_PATH_OBJECT_PATTERN.findall(content):
        data = OFD_PATH_PATTERN.search(body)
        if not data:
            continue
        subpaths = _ofd_subpaths(data.group(1))
        if not subpaths:
            continue

        inline = OFD_FILL_COLOR_PATTERN.search(body)
        if inline:
            parts = inline.group(1).split()[:3]
            try:
                color = tuple(int(float(part)) for part in parts)
            except ValueError:
                color = BLACK
        else:
            reference = OFD_DRAW_PARAM_REF_PATTERN.search(attrs)
            color = colors.get(
                reference.group(1) if reference else "", BLACK
            )
        if len(color) != 3:
            color = BLACK

        mask = Image.new("1", (width, height), 0)
        for points in subpaths:
            scaled = [(x * scale_x, y * scale_y) for x, y in points]
            piece = Image.new("1", (width, height), 0)
            ImageDraw.Draw(piece).polygon(scaled, fill=1)
            mask = ImageChops.logical_xor(mask, piece)
        page.paste(color, (0, 0), mask)
        drawn += 1

    # A page with a size but no marks renders as a blank sheet, and asking
    # a model to read one costs a call to be told there is nothing there.
    return page if drawn else None


def _render_ofd(archive, max_pages: int) -> list[tuple[str, bytes]]:
    """Draw the pages of an OFD whose text is not text."""
    import io

    colors = _ofd_fill_colors(archive)
    names = sorted(
        name
        for name in archive.namelist()
        if name.lower().endswith("content.xml")
    )
    images: list[tuple[str, bytes]] = []
    for name in names[:max_pages]:
        try:
            content = archive.read(name).decode("utf-8", errors="ignore")
        except KeyError:
            continue
        page = _render_ofd_page(content, colors)
        if page is None:
            continue
        buffer = io.BytesIO()
        page.save(buffer, format="PNG")
        images.append(("image/png", buffer.getvalue()))
    return images


def decode_ofd(path: str, max_pages: int = 3) -> DecodedSource:
    """
    Read an OFD by opening it as what it is: a zip of XML.

    The invoice fields usually live in the markup as text, so pulling them
    out directly is both cheaper and more accurate than rendering the
    document and asking a vision model to read it back.

    Some issuers print the invoice instead: the characters arrive as filled
    vector outlines with no text object anywhere in the file. Nothing can
    read those as text, so the page is drawn and sent down the same path a
    scanned PDF takes.
    """
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise DecodeError(f"OFD is not a readable zip: {exc}") from exc

    fragments: list[str] = []
    declared: dict = {}
    with archive:
        try:
            declared = _ofd_declared_fields(archive)
        except Exception:  # pragma: no cover - a broken index is not fatal
            logger.warning("OFD field index unreadable in %s", path)

        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".xml")
        ]
        # Content.xml holds the rendered glyphs; attachments often carry the
        # structured original invoice record.
        names.sort(key=lambda name: ("content.xml" not in name.lower(), name))

        for name in names:
            try:
                raw = archive.read(name).decode("utf-8", errors="ignore")
            except KeyError:
                continue

            matches = OFD_TEXT_PATTERN.findall(raw)
            if matches:
                fragments.extend(
                    _strip_ofd_markup(match) for match in matches
                )

    text = "\n".join(fragment for fragment in fragments if fragment)
    if not text.strip():
        with zipfile.ZipFile(path) as archive:
            images = _render_ofd(archive, max_pages)
        if images:
            return DecodedSource(
                mode=DecodeMode.IMAGE,
                images=images,
                decoder="ofd_render",
                fields=declared,
            )
        raise DecodeError("OFD holds neither text nor a page to draw")

    return DecodedSource(
        mode=DecodeMode.TEXT,
        text=text,
        decoder="ofd_xml",
        fields=declared,
    )



def _xml_lines(element, prefix: str = "") -> list[str]:
    """Flatten an element tree into `label: value` lines."""
    lines = []
    tag = element.tag.rsplit("}", 1)[-1]
    label = f"{prefix}{tag}" if prefix else tag

    for name, value in (element.attrib or {}).items():
        name = name.rsplit("}", 1)[-1]
        text = str(value).strip()
        if text:
            lines.append(f"{label}.{name}: {text}")

    text = (element.text or "").strip()
    if text:
        lines.append(f"{label}: {text}")

    for child in element:
        lines.extend(_xml_lines(child))

    return lines


def decode_xml(path: str) -> DecodedSource:
    """
    Read the XML that a fully digital invoice ships alongside its PDF.

    This is the authoritative record: the fields are already structured and
    exact, so nothing has to be recognized from pixels and no OCR error can
    creep into an amount or a tax number. Element names differ between
    issuers, so the tree is flattened into labelled lines and the labels
    carry the meaning through.
    """
    from xml.etree import ElementTree

    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError as exc:
        raise DecodeError(f"XML is not readable: {exc}") from exc

    lines = _xml_lines(tree.getroot())
    text = "\n".join(lines)
    if not text.strip():
        raise DecodeError("XML contains no readable fields")

    return DecodedSource(mode=DecodeMode.TEXT, text=text, decoder="xml")


def decode_image(path: str) -> DecodedSource:
    """Hand the image straight to a vision model."""
    file_path = Path(path)
    if not file_path.exists():
        raise DecodeError(f"Image file not found: {path}")

    mime_type, _ = mimetypes.guess_type(file_path.name)
    return DecodedSource(
        mode=DecodeMode.IMAGE,
        images=[(mime_type or "image/png", file_path.read_bytes())],
        decoder="image",
    )


# A zip arriving from a stranger is untrusted input, so the reader is
# bounded rather than trusting the archive's own headers.
MAX_ZIP_ENTRIES = 40
MAX_ZIP_MEMBER_BYTES = 30 * 1024 * 1024

# Which format to read when an archive carries the same invoice several
# times, best first. Railway invoices ship PDF and OFD of one ticket, and
# reading both would file the journey twice. PDF leads because its text
# layer is the most reliable and, failing that, it can still be rendered
# for the vision model - an OFD that will not parse has nowhere to go.
ZIP_FORMAT_PRIORITY = ("pdf", "ofd", "xml", "png", "jpg", "jpeg")


def decode_zip(path: str, max_pages: int = 3) -> DecodedSource:
    """
    Read the one invoice inside an archive.

    Rail operators deliver a ticket as a zip holding the same document as
    both PDF and OFD. Only one of them is the expense, so this picks a
    single member rather than handing back everything it finds.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            members = [
                info
                for info in archive.infolist()[:MAX_ZIP_ENTRIES]
                if not info.is_dir()
            ]

            best = None
            best_rank = len(ZIP_FORMAT_PRIORITY)
            for info in members:
                suffix = info.filename.lower().rsplit(".", 1)[-1]
                if suffix not in ZIP_FORMAT_PRIORITY:
                    continue
                rank = ZIP_FORMAT_PRIORITY.index(suffix)
                if rank < best_rank:
                    best, best_rank = info, rank

            if best is None:
                raise DecodeError("Archive holds no readable invoice")

            if best.file_size > MAX_ZIP_MEMBER_BYTES:
                raise DecodeError("Archive member is too large to read")

            suffix = best.filename.lower().rsplit(".", 1)[-1]
            # Read the member by name rather than extracting, so a crafted
            # path in the archive cannot write outside the temp file.
            with archive.open(best) as source:
                payload = source.read(MAX_ZIP_MEMBER_BYTES + 1)
            if len(payload) > MAX_ZIP_MEMBER_BYTES:
                raise DecodeError("Archive member is too large to read")
    except DecodeError:
        raise
    except zipfile.BadZipFile as exc:
        raise DecodeError(f"Archive could not be opened: {exc}") from exc

    with tempfile.NamedTemporaryFile(suffix=f".{suffix}") as handle:
        handle.write(payload)
        handle.flush()
        decoded = decode_source(
            handle.name, filename=best.filename, max_pages=max_pages
        )

    decoded.decoder = f"zip:{decoded.decoder}"
    return decoded


def decode_source(
    path: str,
    content_type: str = "",
    filename: str = "",
    max_pages: int = 3,
) -> DecodedSource:
    """Pick a decoder from the content type, falling back to the extension."""
    if not Path(path).exists():
        raise DecodeError(f"File not found: {path}")

    normalized = (content_type or "").lower().split(";")[0].strip()
    extension = (filename or path).lower().rsplit(".", 1)[-1]

    is_pdf = normalized in ("application/pdf", "application/x-pdf")
    if is_pdf or extension == "pdf":
        return decode_pdf(path, max_pages=max_pages)

    is_ofd = normalized in ("application/ofd", "application/x-ofd")
    if is_ofd or extension == "ofd":
        return decode_ofd(path, max_pages=max_pages)

    is_xml = normalized in ("application/xml", "text/xml")
    if is_xml or extension == "xml":
        return decode_xml(path)

    if normalized.startswith("image/") or extension in (
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "heic",
    ):
        return decode_image(path)

    is_zip = normalized in ("application/zip", "application/x-zip-compressed")
    if is_zip or extension == "zip":
        return decode_zip(path, max_pages=max_pages)

    raise DecodeError(f"Unsupported file type: {content_type or extension}")
