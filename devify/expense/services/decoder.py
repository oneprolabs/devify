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


def decode_ofd(path: str) -> DecodedSource:
    """
    Read an OFD by opening it as what it is: a zip of XML.

    The invoice fields live in the markup as text, so pulling them out
    directly is both cheaper and more accurate than rendering the document
    and asking a vision model to read it back.
    """
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise DecodeError(f"OFD is not a readable zip: {exc}") from exc

    fragments: list[str] = []
    with archive:
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
        raise DecodeError("OFD contains no readable text")

    return DecodedSource(
        mode=DecodeMode.TEXT, text=text, decoder="ofd_xml"
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
        return decode_ofd(path)

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

    raise DecodeError(f"Unsupported file type: {content_type or extension}")
