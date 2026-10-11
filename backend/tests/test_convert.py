import io
import shutil
import zipfile

import openpyxl
import pytest
from PIL import Image

from app.pipeline.convert import expand, normalize

DOCX_XML = {
    "[Content_Types].xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    ),
    "_rels/.rels": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    ),
    "word/document.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Гарантийный срок не менее 36 месяцев. Kafolat muddati 36 oy.</w:t>"
        "</w:r></w:p></w:body></w:document>"
    ),
}


def _zip(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_photo_becomes_one_page_pdf() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(buf, format="JPEG")

    result = normalize("scan.jpg", buf.getvalue())

    assert result.pdf is not None and result.pdf.startswith(b"%PDF")
    assert result.page_count == 1


def test_multipage_tiff_keeps_all_pages() -> None:
    buf = io.BytesIO()
    pages = [Image.new("RGB", (800, 1100), color) for color in ("white", "gray")]
    pages[0].save(buf, format="TIFF", save_all=True, append_images=pages[1:])

    assert normalize("scan.tiff", buf.getvalue()).page_count == 2


def test_spreadsheet_becomes_text() -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Параметр", "Значение"])
    sheet.append(["ОЗУ", "16 ГБ"])
    buf = io.BytesIO()
    book.save(buf)

    result = normalize("spec.xlsx", buf.getvalue())

    assert result.pdf is None
    assert result.text is not None and "ОЗУ | 16 ГБ" in result.text


def test_nested_archive_is_expanded() -> None:
    inner = _zip({"cert.txt": "ISO 9001"})
    outer = _zip({"bid/proposal.txt": "Proposal", "bid/certs.zip": inner, "__MACOSX/x": "junk"})

    names = [name for name, _ in expand("package.zip", outer)]

    assert names == ["package.zip/bid/certs.zip/cert.txt", "package.zip/bid/proposal.txt"]


class _LegacyWindowsName(zipfile.ZipInfo):
    """Writes the name as raw cp866 bytes without the UTF-8 flag, like old Windows archivers."""

    def _encodeFilenameFlags(self) -> tuple[bytes, int]:  # noqa: N802 (overrides zipfile)
        return self.filename.encode("cp437"), self.flag_bits


def test_cyrillic_names_from_windows_zip() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(_LegacyWindowsName("Паспорт.txt".encode("cp866").decode("cp437")), "passport")

    assert expand("bid.zip", buf.getvalue())[0][0] == "bid.zip/Паспорт.txt"


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="не поддерживается"):
        normalize("drawing.dwg", b"AC1027")


@pytest.mark.skipif(
    shutil.which("soffice") is None, reason="LibreOffice is only in the Docker image"
)
def test_docx_becomes_pdf_with_text() -> None:
    result = normalize("tz.docx", _zip(dict(DOCX_XML)))

    assert result.pdf is not None
    assert "не менее 36 месяцев" in result.page_texts[0]
    assert "Kafolat muddati" in result.page_texts[0]
