"""Secure upload validation + sanitisation (rules/70, P2-3). Runs BEFORE anything is stored or parsed further.

Accept only PDF/JPEG/PNG by magic bytes (the client's content type is ignored), enforce size/page limits, reject
encrypted PDFs and decompression bombs, strip metadata/active content by rebuilding the file, and run the DEMO AV hook.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.core.errors import FileTooLarge, UnsupportedMedia, ValidationFailed

PDF_MAGIC = b"%PDF-"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
MAX_PIXELS = 40_000_000  # decompression-bomb guard (~40 MP)
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass(frozen=True)
class SanitizedFile:
    data: bytes
    mime: str
    ext: str
    pages: int
    sha256: str
    original_sha256: str


def sniff(data: bytes) -> str:
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    raise UnsupportedMedia("Only PDF, JPG and PNG files are accepted.")


def demo_av_scan(data: bytes) -> str:
    """DEMO anti-virus hook: flags the EICAR test signature. Replace with a real scanner in prod."""
    return "infected" if EICAR in data else "clean"


def _sanitize_pdf(data: bytes, max_pages: int) -> tuple[bytes, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnsupportedMedia("Encrypted PDFs are not accepted.")
        pages = len(reader.pages)
    except PdfReadError as exc:
        raise UnsupportedMedia("The PDF could not be read.") from exc
    if pages == 0:
        raise UnsupportedMedia("The PDF has no pages.")
    if pages > max_pages:
        raise FileTooLarge(f"PDFs may have at most {max_pages} pages.")
    writer = PdfWriter()
    # Copy page content only: drops document metadata, JavaScript, open actions, and attachments.
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/Producer": "AutoServe AI sanitizer"})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), pages


def _sanitize_image(data: bytes, mime: str) -> bytes:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
                raise FileTooLarge("Image dimensions are too large.")
            clean = img.convert("RGB")  # drops EXIF/ICC/text chunks and any trailing payload
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise UnsupportedMedia("The image could not be read.") from exc
    out = io.BytesIO()
    clean.save(out, format="PNG" if mime == "image/png" else "JPEG", quality=90)
    return out.getvalue()


def validate_and_sanitize(data: bytes, *, max_bytes: int, max_pages: int) -> SanitizedFile:
    if len(data) > max_bytes:
        raise FileTooLarge(f"Files may be at most {max_bytes // (1024 * 1024)} MB.")
    if not data:
        raise UnsupportedMedia("The file is empty.")
    mime = sniff(data)
    if demo_av_scan(data) != "clean":
        raise ValidationFailed("The file was rejected by the malware scan (DEMO scanner).")
    if mime == "application/pdf":
        clean, pages = _sanitize_pdf(data, max_pages)
        ext = "pdf"
    else:
        clean, pages = _sanitize_image(data, mime), 1
        ext = "png" if mime == "image/png" else "jpg"
    return SanitizedFile(
        data=clean,
        mime=mime,
        ext=ext,
        pages=pages,
        sha256=hashlib.sha256(clean).hexdigest(),
        original_sha256=hashlib.sha256(data).hexdigest(),
    )
