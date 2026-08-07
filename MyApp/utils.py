# Utility: Automatic file conversion and compression using pdflayer API.

"""
Converts uploaded documents (PPTX, DOCX, images, etc.) into compressed PDF files using the pdflayer API.
If pdflayer is unavailable or the API key is missing, falls back to local conversion/compression for images and PDFs.
"""

import io
import os
import uuid
import logging
import requests
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# Supported extensions
CONVERTIBLE_EXTENSIONS = {
    ".pptx",
    ".ppt",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".webp",
    ".html",
    ".htm",
    ".txt",
    ".rtf",
    ".odt",
    ".odp",
    ".ods",
}

PDF_EXTENSION = ".pdf"

SKIP_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".bz2",
    ".xz",
    ".tar",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".mp3",
    ".aac",
    ".ogg",
    ".flac",
    ".wma",
    ".exe",
    ".msi",
    ".apk",
}

# pdflayer endpoint
PDFLAYER_API_URL = "https://api.pdflayer.com/api/convert"


def _compress_pdf_local(pdf_bytes: bytes) -> bytes | None:
    """Compress a PDF file locally using PyPDF2."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        logger.error(f"Local PDF compression error: {e}")
        return None


def _convert_image_to_pdf_local(image_bytes: bytes) -> bytes | None:
    """Convert an image to PDF locally using Pillow."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            bg.paste(image, mask=image.split()[3] if image.mode == "RGBA" else None)
            image = bg
        elif image.mode != "RGB":
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, format="PDF", quality=50)
        return out.getvalue()
    except Exception as e:
        logger.error(f"Image to PDF conversion error: {e}")
        return None


def _convert_to_pdf_pdflayer(file_data: bytes, filename: str, api_key: str) -> bytes | None:
    """Convert a file to PDF using the pdflayer API."""
    files = {"file": (filename, file_data)}
    data = {"apikey": api_key}
    try:
        response = requests.post(PDFLAYER_API_URL, files=files, data=data, timeout=120)
        if response.status_code == 200:
            logger.info(f"Converted '{filename}' to PDF via pdflayer (size {len(response.content):,})")
            return response.content
        else:
            logger.error(f"pdflayer conversion error {response.status_code}: {response.text[:500]}")
            return None
    except Exception as e:
        logger.error(f"pdflayer conversion exception: {e}")
        return None


def compress_uploaded_file(uploaded_file) -> SimpleUploadedFile | None:
    """Convert and compress an uploaded file into an optimized PDF.
    Steps:
      1. Use pdflayer API for conversion/compression when API key is present.
      2. Fallback to local conversion for images and local compression for PDFs.
      3. For unsupported formats, return original file with a warning.
    """
    if uploaded_file is None:
        return None

    original_name = uploaded_file.name
    _, ext = os.path.splitext(original_name.lower())

    if ext in SKIP_EXTENSIONS:
        logger.info(f"Skipping compression for {ext} (already-compressed format).")
        uploaded_file.compression_info = "File is already in a compressed format. No further compression needed."
        return uploaded_file

    # Read raw data
    uploaded_file.seek(0)
    raw_data = uploaded_file.read()

    api_key = getattr(settings, "PDFLAYER_API_KEY", None)
    has_api_key = bool(api_key and api_key not in ("YOUR_API_KEY_HERE", ""))

    compressed_data = None
    warning_msg = None
    info_msg = None

    if ext == PDF_EXTENSION:
        # Already PDF
        if has_api_key:
            # pdflayer does not provide a dedicated compression endpoint; use local compression
            compressed_data = _compress_pdf_local(raw_data)
            info_msg = "✅ PDF compressed locally (pdflayer key present)."
        else:
            compressed_data = _compress_pdf_local(raw_data)
            info_msg = "✅ PDF compressed locally (offline)."
    elif ext in CONVERTIBLE_EXTENSIONS:
        if has_api_key:
            pdf_bytes = _convert_to_pdf_pdflayer(raw_data, original_name, api_key)
            if pdf_bytes:
                # Attempt local compression on the resulting PDF
                compressed_pdf = _compress_pdf_local(pdf_bytes)
                compressed_data = compressed_pdf if compressed_pdf else pdf_bytes
                info_msg = f"✅ {ext.upper()} converted to PDF via pdflayer."
            else:
                warning_msg = f"⚠️ pdflayer conversion failed for {ext.upper()}."
        else:
            # No API key: handle images locally, others get warning
            if ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}:
                pdf_bytes = _convert_image_to_pdf_local(raw_data)
                if pdf_bytes:
                    compressed_data = _compress_pdf_local(pdf_bytes) or pdf_bytes
                    info_msg = "✅ Image converted and compressed locally."
                else:
                    warning_msg = "⚠️ Image conversion failed locally."
            else:
                warning_msg = f"⚠️ No pdflayer API key configured. {ext.upper()} uploaded as-is."
    else:
        # Unknown format
        warning_msg = f"⚠️ Format {ext} not supported; uploaded unchanged."

    if compressed_data is None:
        uploaded_file.seek(0)
        ret_file = uploaded_file
    else:
        pdf_name = os.path.splitext(original_name)[0] + ".pdf"
        ret_file = SimpleUploadedFile(name=pdf_name, content=compressed_data, content_type="application/pdf")

    if warning_msg:
        ret_file.compression_warning = warning_msg
    if info_msg:
        ret_file.compression_info = info_msg

    return ret_file
