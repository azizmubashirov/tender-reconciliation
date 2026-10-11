"""Bring uploaded files to what the model reads: a PDF (text or scan) or plain text (sheets)."""

import csv
import io
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import fitz
import openpyxl
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

ARCHIVES = {".zip", ".rar", ".7z"}
OFFICE = {".doc", ".docx", ".rtf", ".odt", ".xls", ".ods"}
IMAGES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".heif"}
SHEETS = {".xlsx", ".xlsm", ".csv"}
TEXTS = {".txt"}
SUPPORTED = ARCHIVES | OFFICE | IMAGES | SHEETS | TEXTS | {".pdf"}

MAX_ARCHIVE_DEPTH = 3
MAX_UNPACKED_BYTES = 2 * 1024**3  # zip-bomb guard
MAX_IMAGE_SIDE = 2200  # enough for small print, keeps phone photos well under request limits


class UnsupportedFormatError(ValueError):
    pass


@dataclass
class Normalized:
    pdf: bytes | None = None
    text: str | None = None
    page_texts: list[str] = field(default_factory=list)
    page_count: int = 0


def expand(filename: str, data: bytes, depth: int = 0) -> list[tuple[str, bytes]]:
    """Unpack archives recursively, keeping the folder path in the name."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ARCHIVES:
        return [(filename, data)]
    if depth >= MAX_ARCHIVE_DEPTH:
        raise UnsupportedFormatError(f"{filename}: слишком глубокая вложенность архивов")
    members = _zip_members(data) if suffix == ".zip" else _libarchive_members(suffix, data)
    files: list[tuple[str, bytes]] = []
    for name, content in sorted(members):
        parts = PurePosixPath(name).parts
        if (
            name.startswith("/")
            or ".." in parts
            or any(p.startswith((".", "__MACOSX")) for p in parts)
        ):
            continue
        files.extend(expand(f"{filename}/{name}", content, depth + 1))
    return files


def _zip_members(data: bytes) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
            raise UnsupportedFormatError("архив слишком большой после распаковки")
        members = []
        for info in infos:
            name = info.filename
            if not info.flag_bits & 0x800:
                # Not flagged as UTF-8: archives made on Russian/Uzbek Windows use cp866.
                name = name.encode("cp437").decode("cp866", errors="replace")
            members.append((name, zf.read(info)))
        return members


def _libarchive_members(suffix: str, data: bytes) -> list[tuple[str, bytes]]:
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"archive{suffix}"
        archive.write_bytes(data)
        out = Path(tmp) / "out"
        out.mkdir()
        # bsdtar (libarchive) reads rar/7z and refuses absolute paths and "..".
        subprocess.run(
            ["bsdtar", "-xf", str(archive), "-C", str(out)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        paths = [p for p in out.rglob("*") if p.is_file()]
        if sum(p.stat().st_size for p in paths) > MAX_UNPACKED_BYTES:
            raise UnsupportedFormatError("архив слишком большой после распаковки")
        return [(p.relative_to(out).as_posix(), p.read_bytes()) for p in paths]


def normalize(filename: str, data: bytes) -> Normalized:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(data)
    if suffix in OFFICE:
        return _from_pdf(_office_to_pdf(filename, data))
    if suffix in IMAGES:
        return _from_pdf(_images_to_pdf(data))
    if suffix in SHEETS:
        text = _sheet_to_text(suffix, data)
        return Normalized(text=text, page_texts=[text], page_count=1)
    if suffix in TEXTS:
        text = data.decode("utf-8", errors="replace")
        return Normalized(text=text, page_texts=[text], page_count=1)
    raise UnsupportedFormatError(f"{filename}: формат не поддерживается")


def _from_pdf(pdf: bytes) -> Normalized:
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        texts = [page.get_text() for page in doc]
    return Normalized(pdf=pdf, page_texts=texts, page_count=len(texts))


def _office_to_pdf(filename: str, data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{Path(filename).suffix.lower()}"
        src.write_bytes(data)
        # A private profile per call lets several conversions run in parallel.
        profile = f"file://{tmp}/lo-profile-{uuid.uuid4().hex}"
        subprocess.run(
            [
                "soffice",
                f"-env:UserInstallation={profile}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(src),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        out = src.with_suffix(".pdf")
        if not out.exists():
            raise UnsupportedFormatError(f"{filename}: не удалось конвертировать в PDF")
        return out.read_bytes()


def _images_to_pdf(data: bytes) -> bytes:
    frames: list[Image.Image] = []
    with Image.open(io.BytesIO(data)) as img:
        for index in range(getattr(img, "n_frames", 1)):  # multi-page TIFF
            img.seek(index)
            frame = ImageOps.exif_transpose(img.copy()).convert("RGB")
            frame.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            frames.append(frame)
    buf = io.BytesIO()
    frames[0].save(buf, format="PDF", save_all=True, append_images=frames[1:], quality=85)
    return buf.getvalue()


def _sheet_to_text(suffix: str, data: bytes) -> str:
    if suffix == ".csv":
        rows = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
        return "\n".join(" | ".join(row) for row in rows)
    book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for sheet in book.worksheets:
        lines = [f"## Лист: {sheet.title}"]
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                lines.append(" | ".join("" if c is None else str(c) for c in row))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def pdf_parts(pdf: bytes, pages_per_part: int = 80) -> list[tuple[int, bytes]]:
    """Split long PDFs so each request stays well inside model limits. Returns (first_page, pdf)."""
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        if doc.page_count <= pages_per_part:
            return [(1, pdf)]
        parts = []
        for start in range(0, doc.page_count, pages_per_part):
            part = fitz.open()
            part.insert_pdf(doc, from_page=start, to_page=start + pages_per_part - 1)
            parts.append((start + 1, part.tobytes()))
            part.close()
        return parts
