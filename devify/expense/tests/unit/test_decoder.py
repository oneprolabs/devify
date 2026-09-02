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
    decode_xml,
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


def build_ofd_with_cdata(path, parts):
    """Build an OFD the way real issuers do: labels plain, values in CDATA."""
    body = []
    for plain, cdata in parts:
        inner = plain if plain is not None else f"<![CDATA[{cdata}]]>"
        body.append(f"<ofd:TextCode X='0' Y='0'>{inner}</ofd:TextCode>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("OFD.xml", "<ofd:OFD xmlns:ofd='urn:ofd'/>")
        archive.writestr(
            "Doc_0/Pages/Page_0/Content.xml",
            "<ofd:Page xmlns:ofd='urn:ofd'>" + "".join(body) + "</ofd:Page>",
        )


def build_ofd_with_index(path, fields, extra_text=""):
    """
    Build a 全电 OFD the way issuers do.

    CustomTag.xml names the drawn object holding each field; Content.xml
    draws them, with the values in CDATA.
    """
    tags = "".join(
        f"<ofd:{element}><ofd:ObjectRef PageRef='1'>{oid}</ofd:ObjectRef>"
        f"</ofd:{element}>"
        for element, (oid, _) in fields.items()
    )
    objects = "".join(
        f"<ofd:TextObject ID=\"{oid}\" Size='3.0'>"
        f"<ofd:TextCode X='0' Y='3'><![CDATA[{value}]]></ofd:TextCode>"
        f"</ofd:TextObject>"
        for _, (oid, value) in fields.items()
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("OFD.xml", "<ofd:OFD xmlns:ofd='urn:ofd'/>")
        archive.writestr(
            "Doc_0/Tags/CustomTag.xml",
            f"<ofd:root xmlns:ofd='urn:ofd'>{tags}</ofd:root>",
        )
        archive.writestr(
            "Doc_0/Pages/Page_0/Content.xml",
            f"<ofd:Page xmlns:ofd='urn:ofd'>{objects}"
            f"<ofd:TextObject ID='999'><ofd:TextCode X='0' Y='0'>"
            f"{extra_text}</ofd:TextCode></ofd:TextObject></ofd:Page>",
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


class TestOfdFieldIndex:
    """
    A 全电 OFD names which drawn object carries which field.

    Reading the invoice out of that index settles the fields it would be
    worst to misread - the number and the amounts - without asking a model
    to recognize them off the page.
    """

    SAMPLE = {
        "InvoiceNo": ("55", "26312000005014116361"),
        "IssueDate": ("57", "2026年08月06日"),
        "BuyerName": ("71", "北京万云博华科技中心（有限合伙）"),
        "BuyerTaxID": ("76", "91110105MA01UYHY0T"),
        "SellerName": ("88", "上海申茂旅游发展有限公司"),
        "TaxInclusiveTotalAmount": ("102", "¥71.62"),
        "TaxTotalAmount": ("96", "¥2.09"),
    }

    def test_the_declared_fields_are_read(self, tmp_path):
        target = tmp_path / "index.ofd"
        build_ofd_with_index(target, self.SAMPLE)

        decoded = decode_ofd(str(target))

        assert decoded.fields["invoice_no"] == "26312000005014116361"
        assert decoded.fields["seller_name"] == "上海申茂旅游发展有限公司"

    def test_amounts_lose_their_currency_mark(self, tmp_path):
        target = tmp_path / "index.ofd"
        build_ofd_with_index(target, self.SAMPLE)

        decoded = decode_ofd(str(target))

        assert decoded.fields["total_amount"] == "71.62"
        assert decoded.fields["tax_amount"] == "2.09"

    def test_the_chinese_date_becomes_a_date(self, tmp_path):
        target = tmp_path / "index.ofd"
        build_ofd_with_index(target, self.SAMPLE)

        decoded = decode_ofd(str(target))

        assert decoded.fields["issue_date"] == "2026-08-06"

    def test_the_text_is_still_produced_for_the_model(self, tmp_path):
        # The index carries no invoice type, category or line items, so
        # the page still has to be read as usual.
        target = tmp_path / "index.ofd"
        build_ofd_with_index(target, self.SAMPLE, extra_text="旅客运输服务")

        decoded = decode_ofd(str(target))

        assert "旅客运输服务" in decoded.text

    def test_an_ofd_without_an_index_declares_nothing(self, tmp_path):
        # Three of nine real files came from generators that ship no index.
        target = tmp_path / "plain.ofd"
        build_ofd(target, "电子发票 号码 25117000000012345678")

        decoded = decode_ofd(str(target))

        assert decoded.fields == {}

    def test_a_field_the_page_never_drew_is_left_out(self, tmp_path):
        target = tmp_path / "index.ofd"
        build_ofd_with_index(
            target,
            {
                "InvoiceNo": ("55", "26312000005014116361"),
                "SellerTaxID": ("93", ""),
            },
        )

        decoded = decode_ofd(str(target))

        assert "seller_tax_id" not in decoded.fields

    def test_a_broken_index_does_not_break_the_read(self, tmp_path):
        target = tmp_path / "broken.ofd"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("OFD.xml", "<ofd:OFD xmlns:ofd='urn:ofd'/>")
            archive.writestr("Doc_0/Tags/CustomTag.xml", "<not xml at all")
            archive.writestr(
                "Doc_0/Pages/Page_0/Content.xml",
                "<ofd:Page xmlns:ofd='urn:ofd'><ofd:TextCode X='0' Y='0'>"
                "电子发票 128.50</ofd:TextCode></ofd:Page>",
            )

        decoded = decode_ofd(str(target))

        assert "128.50" in decoded.text


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

    def test_values_wrapped_in_cdata_are_read(self, tmp_path):
        # Real issuers put the form labels in as plain text and the values
        # in CDATA. A CDATA section looks exactly like one long tag to a
        # tag stripper, so getting this wrong reads an invoice as a blank
        # form: the labels survive and every number disappears.
        target = tmp_path / "cdata.ofd"
        build_ofd_with_cdata(
            target,
            [("发票号码：", None), (None, "26312000005014116361"),
             ("价税合计", None), (None, "¥71.62")],
        )

        decoded = decode_ofd(str(target))

        assert "26312000005014116361" in decoded.text
        assert "71.62" in decoded.text

    def test_labels_still_come_through(self, tmp_path):
        target = tmp_path / "cdata.ofd"
        build_ofd_with_cdata(
            target, [("发票号码：", None), (None, "26312000005014116361")]
        )

        decoded = decode_ofd(str(target))

        assert "发票号码" in decoded.text

    def test_an_ofd_of_nothing_but_labels_is_still_decoded(self, tmp_path):
        # It decodes, but it says nothing an invoice needs. Recognition is
        # what refuses to file that as a ¥0.00 invoice, not the decoder.
        target = tmp_path / "labels.ofd"
        build_ofd(target, "发票号码： 开票日期： 价税合计")

        decoded = decode_ofd(str(target))

        assert "发票号码" in decoded.text
        assert decoded.mode == DecodeMode.TEXT


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


INVOICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EInvoice xmlns="urn:einvoice">
  <Header>
    <InvoiceNumber>25117000000012345678</InvoiceNumber>
    <IssueDate>2026-08-12</IssueDate>
  </Header>
  <Seller name="滴滴出行">
    <TaxNo>91110108MA002XY31Z</TaxNo>
  </Seller>
  <Total>128.50</Total>
</EInvoice>
"""


class TestDecodeXml:
    def test_fields_are_read_without_any_recognition(self, tmp_path):
        # The XML is the authoritative copy, so nothing has to be read off
        # pixels and no OCR error can reach an amount.
        target = tmp_path / "invoice.xml"
        target.write_text(INVOICE_XML, encoding="utf-8")

        decoded = decode_xml(str(target))

        assert decoded.mode == DecodeMode.TEXT
        assert decoded.decoder == "xml"
        assert "InvoiceNumber: 25117000000012345678" in decoded.text
        assert "Total: 128.50" in decoded.text

    def test_labels_survive_so_values_keep_their_meaning(self, tmp_path):
        target = tmp_path / "invoice.xml"
        target.write_text(INVOICE_XML, encoding="utf-8")

        text = decode_xml(str(target)).text

        assert "TaxNo: 91110108MA002XY31Z" in text
        assert "Seller.name: 滴滴出行" in text

    def test_malformed_xml_is_rejected(self, tmp_path):
        target = tmp_path / "broken.xml"
        target.write_text("<EInvoice><unclosed>", encoding="utf-8")

        with pytest.raises(DecodeError):
            decode_xml(str(target))

    def test_an_empty_document_is_rejected(self, tmp_path):
        target = tmp_path / "empty.xml"
        target.write_text("<EInvoice/>", encoding="utf-8")

        with pytest.raises(DecodeError):
            decode_xml(str(target))

    def test_the_dispatcher_routes_xml(self, tmp_path):
        target = tmp_path / "invoice.xml"
        target.write_text(INVOICE_XML, encoding="utf-8")

        decoded = decode_source(
            str(target), content_type="text/xml", filename="invoice.xml"
        )

        assert decoded.decoder == "xml"



class TestZipArchives:
    """
    Rail operators deliver a ticket as a zip.

    The archive holds one journey as both PDF and OFD, so reading every
    member would file the same expense twice. One member is chosen, and
    the archive is treated as what it is: untrusted input from a stranger.
    """

    def _archive(self, tmp_path, members):
        import zipfile

        path = tmp_path / "invoice.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        return str(path)

    def test_the_pdf_is_preferred_over_the_ofd(self, tmp_path):
        # Both are the same ticket; the PDF has a text layer and, failing
        # that, can still be rendered for the vision model.
        path = self._archive(
            tmp_path,
            {
                "ticket.ofd": b"PK\x03\x04ofd",
                "ticket.pdf": build_pdf("Ticket 2611911001"),
            },
        )

        decoded = decode_source(path, filename="invoice.zip")

        assert decoded.decoder.startswith("zip:")
        assert "pdf" in decoded.decoder

    def test_the_decoder_is_named_through_the_archive(self, tmp_path):
        path = self._archive(tmp_path, {"ticket.pdf": build_pdf("Ticket 2611911001")})

        decoded = decode_source(path, filename="invoice.zip")

        # Knowing it arrived in a zip is worth keeping for diagnosis; which
        # PDF route ran inside is the pdf decoder's business, not this one's.
        assert decoded.decoder.startswith("zip:pdf")

    def test_an_archive_of_nothing_readable_is_refused(self, tmp_path):
        path = self._archive(tmp_path, {"readme.txt": b"hello"})

        with pytest.raises(DecodeError, match="no readable invoice"):
            decode_source(path, filename="invoice.zip")

    def test_a_corrupt_archive_is_refused(self, tmp_path):
        path = tmp_path / "broken.zip"
        path.write_bytes(b"not a zip at all")

        with pytest.raises(DecodeError, match="could not be opened"):
            decode_source(str(path), filename="broken.zip")

    def test_an_oversized_member_is_refused(self, tmp_path, monkeypatch):
        # A zip bomb declares little and expands to a lot, so the guard
        # has to survive the archive's own headers being untrue.
        from expense.services import decoder as decoder_module

        monkeypatch.setattr(decoder_module, "MAX_ZIP_MEMBER_BYTES", 10)
        path = self._archive(tmp_path, {"ticket.pdf": build_pdf("Ticket 2611911001")})

        with pytest.raises(DecodeError, match="too large"):
            decode_source(path, filename="invoice.zip")

    def test_the_content_type_routes_it_too(self, tmp_path):
        path = self._archive(tmp_path, {"ticket.pdf": build_pdf("Ticket 2611911001")})

        decoded = decode_source(
            path, content_type="application/zip", filename="anything"
        )

        assert decoded.decoder.startswith("zip:")


class TestOfdDrawnAsGraphics:
    """
    Some issuers print the invoice rather than write it.

    The characters arrive as filled vector outlines with no text object
    anywhere in the file, so no amount of parsing will read them. The page
    is drawn instead and sent down the path a scanned PDF takes.
    """

    def _ofd(self, tmp_path, content, res=None):
        import zipfile

        path = tmp_path / "invoice.ofd"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("OFD.xml", "<ofd:OFD/>")
            archive.writestr("Doc_0/Pages/Page_0/Content.xml", content)
            if res is not None:
                archive.writestr("Doc_0/DocumentRes.xml", res)
        return str(path)

    def _page(self, paths):
        return (
            '<ofd:Page xmlns:ofd="http://www.ofdspec.org/2016">'
            "<ofd:Area><ofd:PhysicalBox>0 0 100 50</ofd:PhysicalBox>"
            "</ofd:Area>" + paths + "</ofd:Page>"
        )

    def _path(self, data, draw_param=None):
        reference = f' DrawParam="{draw_param}"' if draw_param else ""
        return (
            f'<ofd:PathObject Boundary="0 0 100 50" Fill="true"{reference}>'
            f"<ofd:AbbreviatedData>{data}</ofd:AbbreviatedData>"
            "</ofd:PathObject>"
        )

    def test_a_drawn_page_is_rendered_instead_of_refused(self, tmp_path):
        path = self._ofd(
            tmp_path,
            self._page(self._path("M 10 10 L 90 10 L 90 40 L 10 40 C")),
        )

        decoded = decode_source(path, filename="invoice.ofd")

        assert decoded.mode == DecodeMode.IMAGE
        assert decoded.decoder == "ofd_render"
        assert len(decoded.images) == 1

    def test_the_page_background_does_not_black_out_the_invoice(
        self, tmp_path
    ):
        # The first path in a real invoice is a full-page rectangle filled
        # white. Painting every path the same colour hid the document
        # behind it, which is exactly what a vision model cannot read.
        res = (
            '<ofd:Res xmlns:ofd="http://www.ofdspec.org/2016"><ofd:DrawParams>'
            '<ofd:DrawParam ID="4"><ofd:FillColor Value="255 255 255"/>'
            "</ofd:DrawParam>"
            '<ofd:DrawParam ID="8"><ofd:FillColor Value="0 0 0"/>'
            "</ofd:DrawParam></ofd:DrawParams></ofd:Res>"
        )
        paths = self._path(
            "M 0 0 L 100 0 L 100 50 L 0 50 C", draw_param="4"
        ) + self._path("M 10 10 L 30 10 L 30 20 L 10 20 C", draw_param="8")
        path = self._ofd(tmp_path, self._page(paths), res=res)

        decoded = decode_source(path, filename="invoice.ofd")

        from io import BytesIO

        from PIL import Image

        page = Image.open(BytesIO(decoded.images[0][1])).convert("L")
        pixels = list(page.get_flattened_data())
        light = sum(1 for value in pixels if value > 200)
        # Most of the page stays white; only the marked rectangle is dark.
        assert light > len(pixels) * 0.7

    def test_readable_text_is_still_preferred(self, tmp_path):
        import zipfile

        path = tmp_path / "text.ofd"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "Doc_0/Pages/Page_0/Content.xml",
                '<ofd:Page xmlns:ofd="http://www.ofdspec.org/2016">'
                "<ofd:TextCode>发票号码 123</ofd:TextCode></ofd:Page>",
            )

        decoded = decode_source(str(path), filename="text.ofd")

        # Reading the markup is cheaper and exact; drawing is the fallback.
        assert decoded.mode == DecodeMode.TEXT
        assert decoded.decoder == "ofd_xml"

    def test_an_ofd_with_neither_text_nor_paths_is_refused(self, tmp_path):
        path = self._ofd(tmp_path, self._page(""))

        with pytest.raises(DecodeError, match="neither text nor a page"):
            decode_source(path, filename="invoice.ofd")

    def test_a_curve_is_flattened_rather_than_dropped(self):
        from expense.services.decoder import _ofd_subpaths

        # A glyph stroke is mostly curves; dropping them would leave the
        # character as a few disconnected corners.
        straight = _ofd_subpaths("M 0 0 L 10 0 L 10 10 C")
        curved = _ofd_subpaths("M 0 0 Q 5 0 10 10 L 0 10 C")

        assert len(straight[0]) == 3
        assert len(curved[0]) > 3

    def test_an_unknown_command_stops_the_path(self):
        from expense.services.decoder import _ofd_subpaths

        # Its operands cannot be placed, so everything after it would be
        # drawn at the wrong coordinates.
        subpaths = _ofd_subpaths(
            "M 0 0 L 10 0 L 10 10 C M 0 0 Z 5 5 L 9 9 C"
        )

        assert len(subpaths) == 1
