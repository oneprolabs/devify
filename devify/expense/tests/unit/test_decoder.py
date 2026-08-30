"""Unit tests for turning invoice files into model input."""

import zipfile

import pytest

from expense.services.decoder import (
    DecodeError,
    DecodeMode,
    decode_image,
    decode_ofd,
    decode_pdf,
    decode_source,
)


pytestmark = pytest.mark.unit


def build_pdf(text: str | None) -> bytes:
    """A minimal one-page PDF, with a text layer only when text is given."""
    content = (
        f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode() if text else b""
    )
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        (
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]"
            b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>"
        ),
        b"<</Length "
        + str(len(content)).encode()
        + b">>stream\n"
        + content
        + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(index).encode() + b" 0 obj" + body + b"endobj\n"

    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += ("%010d 00000 n \n" % offset).encode()
    out += (
        b"trailer<</Size "
        + str(len(objects) + 1).encode()
        + b"/Root 1 0 R>>\nstartxref\n"
        + str(xref_at).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)


def build_ofd(path, text: str):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("OFD.xml", "<ofd:OFD xmlns:ofd='urn:ofd'/>")
        archive.writestr(
            "Doc_0/Pages/Page_0/Content.xml",
            "<ofd:Page xmlns:ofd='urn:ofd'>"
            + "".join(
                f"<ofd:TextCode X='0' Y='0'>{part}</ofd:TextCode>"
                for part in text.split()
            )
            + "</ofd:Page>",
        )


def build_png(path):
    from PIL import Image

    Image.new("RGB", (40, 40), (255, 255, 255)).save(path)


class TestDecodePdf:
    def test_text_layer_is_preferred(self, tmp_path):
        target = tmp_path / "invoice.pdf"
        target.write_bytes(
            build_pdf("INVOICE NO 25117000000012345678 TOTAL 128.50 CNY")
        )

        decoded = decode_pdf(str(target))

        assert decoded.mode == DecodeMode.TEXT
        assert decoded.decoder == "pdf_text_layer"
        assert "25117000000012345678" in decoded.text
        assert decoded.images == []

    def test_page_without_text_is_rendered(self, tmp_path):
        target = tmp_path / "scan.pdf"
        target.write_bytes(build_pdf(None))

        decoded = decode_pdf(str(target))

        assert decoded.mode == DecodeMode.IMAGE
        assert decoded.decoder == "pdf_render"
        assert len(decoded.images) == 1
        assert decoded.images[0][0] == "image/png"

    def test_trivial_text_layer_falls_back_to_rendering(self, tmp_path):
        # A page number is not an invoice; it must not block the vision path.
        target = tmp_path / "short.pdf"
        target.write_bytes(build_pdf("1"))

        assert decode_pdf(str(target)).mode == DecodeMode.IMAGE

    def test_page_cap_is_honored(self, tmp_path):
        target = tmp_path / "scan.pdf"
        target.write_bytes(build_pdf(None))

        decoded = decode_pdf(str(target), max_pages=1)

        assert len(decoded.images) <= 1

    def test_data_urls_are_produced_for_the_vision_path(self, tmp_path):
        target = tmp_path / "scan.pdf"
        target.write_bytes(build_pdf(None))

        urls = decode_pdf(str(target)).image_data_urls()

        assert urls[0].startswith("data:image/png;base64,")


class TestDecodeOfd:
    def test_text_is_read_straight_out_of_the_markup(self, tmp_path):
        target = tmp_path / "invoice.ofd"
        build_ofd(target, "电子发票 号码 25117000000012345678 金额 128.50")

        decoded = decode_ofd(str(target))

        assert decoded.mode == DecodeMode.TEXT
        assert decoded.decoder == "ofd_xml"
        assert "25117000000012345678" in decoded.text

    def test_a_non_zip_is_rejected_clearly(self, tmp_path):
        target = tmp_path / "broken.ofd"
        target.write_bytes(b"not a zip at all")

        with pytest.raises(DecodeError):
            decode_ofd(str(target))

    def test_an_ofd_without_text_is_rejected(self, tmp_path):
        target = tmp_path / "empty.ofd"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("OFD.xml", "<ofd:OFD xmlns:ofd='urn:ofd'/>")

        with pytest.raises(DecodeError):
            decode_ofd(str(target))


class TestDecodeImage:
    def test_image_bytes_are_returned(self, tmp_path):
        target = tmp_path / "photo.png"
        build_png(target)

        decoded = decode_image(str(target))

        assert decoded.mode == DecodeMode.IMAGE
        assert decoded.images[0][0] == "image/png"

    def test_missing_file_is_reported(self, tmp_path):
        with pytest.raises(DecodeError):
            decode_image(str(tmp_path / "nope.png"))


class TestDecodeSource:
    def test_content_type_selects_the_decoder(self, tmp_path):
        target = tmp_path / "a.bin"
        target.write_bytes(build_pdf(
                "INVOICE NO 25117000000012345678 TOTAL 100.00 CNY SELLER"
            ))

        decoded = decode_source(
            str(target), content_type="application/pdf", filename="a.bin"
        )

        assert decoded.decoder == "pdf_text_layer"

    def test_extension_is_used_when_the_type_is_generic(self, tmp_path):
        target = tmp_path / "invoice.pdf"
        target.write_bytes(build_pdf(
                "INVOICE NO 25117000000012345678 TOTAL 100.00 CNY SELLER"
            ))

        decoded = decode_source(
            str(target),
            content_type="application/octet-stream",
            filename="invoice.pdf",
        )

        assert decoded.mode == DecodeMode.TEXT

    def test_unsupported_type_is_rejected(self, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("hello")

        with pytest.raises(DecodeError):
            decode_source(
                str(target), content_type="text/plain", filename="notes.txt"
            )

    def test_missing_file_is_reported(self, tmp_path):
        with pytest.raises(DecodeError):
            decode_source(str(tmp_path / "gone.pdf"), filename="gone.pdf")
