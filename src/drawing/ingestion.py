"""Phase 17 — Drawing ingestion: records source metadata and saves immutable copy."""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.drawing.schemas import DrawingSource

# Supported MIME types for UC2 drawings
SUPPORTED_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/svg+xml",
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".svg"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_mime(filename: str, content: bytes) -> str:
    """Detect MIME type from file extension, with magic-byte fallback."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".svg":
        return "image/svg+xml"

    # Magic byte fallback
    if content[:4] == b"%PDF":
        return "application/pdf"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:2] in (b"\xff\xd8",):
        return "image/jpeg"
    if b"<svg" in content[:512] or b"<?xml" in content[:64]:
        return "image/svg+xml"

    guess, _ = mimetypes.guess_type(filename)
    return guess or "application/octet-stream"


def _png_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    """Extract width, height from PNG IHDR without Pillow."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    except struct.error:
        return None


def _jpeg_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    """Extract width, height from JPEG SOF markers."""
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        length = struct.unpack(">H", data[i + 2: i + 4])[0]
        # SOF0–SOF3, SOF5–SOF7, SOF9–SOF11, SOF13–SOF15
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h = struct.unpack(">H", data[i + 5: i + 7])[0]
            w = struct.unpack(">H", data[i + 7: i + 9])[0]
            return w, h
        i += 2 + length
    return None


def _svg_dimensions(data: bytes) -> Optional[tuple[Optional[int], Optional[int]]]:
    """Extract width and height from SVG root element attributes."""
    try:
        # Strip xmlns for simpler parsing
        xml_str = data.decode("utf-8", errors="replace")
        # Remove default namespace to simplify tag matching
        xml_str = xml_str.replace(' xmlns="http://www.w3.org/2000/svg"', "")
        root = ET.fromstring(xml_str)
        w_str = root.get("width", "")
        h_str = root.get("height", "")

        def _parse_px(val: str) -> Optional[int]:
            val = val.strip().rstrip("px").rstrip("mm").rstrip("in").strip()
            try:
                return int(float(val))
            except ValueError:
                return None

        return _parse_px(w_str), _parse_px(h_str)
    except ET.ParseError:
        return None


def _pdf_page_count(data: bytes) -> Optional[int]:
    """Count PDF pages by scanning for /Type /Page markers (lightweight, no pypdf dep)."""
    try:
        text = data.decode("latin-1", errors="ignore")
        # Count occurrences of /Type /Page (individual page objects)
        count = text.count("/Type /Page") + text.count("/Type/Page")
        return count if count > 0 else 1
    except Exception:
        return None


class DrawingIngestion:
    """Ingests a 2D engineering drawing file, records metadata, and saves an immutable copy."""

    def ingest(
        self,
        filename: str,
        content: bytes,
        output_dir: Path,
    ) -> DrawingSource:
        """
        Validates, records, and stores the source drawing.

        Parameters
        ----------
        filename : str
            Original uploaded filename.
        content : bytes
            Raw file bytes.
        output_dir : Path
            Workspace directory where the immutable source copy will be stored.

        Returns
        -------
        DrawingSource
            Complete metadata record for the source drawing.

        Raises
        ------
        ValueError
            If the file format is unsupported or the content is empty.
        """
        if not content:
            raise ValueError("Drawing content is empty.")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                f"Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        mime = _detect_mime(filename, content)
        if mime not in SUPPORTED_MIMES:
            raise ValueError(
                f"Detected MIME type '{mime}' is not supported for drawing ingestion."
            )

        sha = _sha256_bytes(content)
        now = datetime.now(timezone.utc).isoformat()

        output_dir.mkdir(parents=True, exist_ok=True)

        # Save immutable source copy — never modified after this point
        source_filename = f"{Path(filename).stem}_source{ext}"
        source_path = output_dir / source_filename
        source_path.write_bytes(content)

        # Determine pixel/page dimensions
        width_px: Optional[int] = None
        height_px: Optional[int] = None
        page_count: Optional[int] = None
        detected_units: Optional[str] = None

        if mime == "image/png":
            dims = _png_dimensions(content)
            if dims:
                width_px, height_px = dims

        elif mime == "image/jpeg":
            dims = _jpeg_dimensions(content)
            if dims:
                width_px, height_px = dims

        elif mime == "image/svg+xml":
            dims = _svg_dimensions(content)
            if dims:
                width_px, height_px = dims[0], dims[1]
            # Try to detect units from SVG
            try:
                xml_str = content.decode("utf-8", errors="replace")
                if 'mm"' in xml_str or "mm'" in xml_str:
                    detected_units = "mm"
                elif 'in"' in xml_str or "in'" in xml_str:
                    detected_units = "inch"
            except Exception:
                pass

        elif mime == "application/pdf":
            page_count = _pdf_page_count(content)

        return DrawingSource(
            filename=filename,
            mime_type=mime,
            sha256=sha,
            file_size_bytes=len(content),
            image_width_px=width_px,
            image_height_px=height_px,
            page_count=page_count,
            detected_units=detected_units,
            ingestion_timestamp=now,
            source_path=str(source_path),
        )
