"""Phase 17 — Drawing renderer: produces a deterministic normalized PNG for multimodal AI input.

Renders vector drawings (SVG, PDF) and raster images (PNG, JPEG) to high-resolution
normalized PNGs for AI multimodal understanding.
Fails explicitly if rendering fails or produces a blank image, rather than silently
submitting empty placeholder images.
"""
from __future__ import annotations

import hashlib
import io
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from src.drawing.schemas import DrawingSource, MultimodalRequestManifest

# Minimum long-edge pixel dimension for normalized PNG (for AI model quality)
MIN_LONG_EDGE_PX = 1200


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _png_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    except struct.error:
        return None


def is_blank_image(png_path: Path) -> Tuple[bool, str]:
    """Inspects a PNG file to verify it is not blank/monochrome/corrupt.

    Returns (is_blank, reason).
    """
    if not png_path.exists() or png_path.stat().st_size < 100:
        return True, "Rendered file does not exist or is too small (<100 bytes)"

    try:
        from PIL import Image
        with Image.open(png_path) as im:
            w, h = im.size
            if w <= 1 or h <= 1:
                return True, f"Image dimensions too small ({w}x{h})"

            gray = im.convert("L")
            extrema = gray.getextrema()
            if extrema is None:
                return True, "Unable to compute image pixel extrema"

            min_val, max_val = extrema
            if min_val == max_val:
                return True, f"Image is completely solid monochrome (pixel value: {min_val})"

            # For engineering drawings with white/light background, verify there are non-background pixels
            # Count pixels that deviate significantly from the background
            # Sample pixels efficiently
            thumb = gray.resize((min(w, 200), min(h, 200)), Image.NEAREST)
            thumb_extrema = thumb.getextrema()
            if thumb_extrema and thumb_extrema[0] == thumb_extrema[1]:
                return True, f"Downsampled image is completely monochrome (pixel value: {thumb_extrema[0]})"

            return False, "Valid non-blank image"
    except Exception as exc:
        return True, f"Error inspecting image content: {exc}"


class RenderResult:
    """Result of a drawing rendering operation."""

    def __init__(
        self,
        png_path: Path,
        width_px: int,
        height_px: int,
        sha256: str,
        render_quality: str,  # "full" | "limited" | "copy"
        render_notes: str,
    ):
        self.png_path = png_path
        self.width_px = width_px
        self.height_px = height_px
        self.sha256 = sha256
        self.render_quality = render_quality
        self.render_notes = render_notes


def _prepare_svg_for_rendering(svg_bytes: bytes) -> bytes:
    """Preprocesses SVG to ensure CSS classes and styles are inlined for renderers

    that do not evaluate embedded <style> rules (e.g. MuPDF).
    Guarantees white background and proper fills/strokes are rendered.
    """
    import re
    try:
        svg_str = svg_bytes.decode("utf-8", errors="replace")

        # 1. Parse CSS rules from <style> blocks
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', svg_str, flags=re.DOTALL)
        css_rules: dict[str, dict[str, str]] = {}
        for block in style_blocks:
            for match in re.finditer(r'\.([a-zA-Z0-9_-]+)\s*\{([^}]+)\}', block):
                class_name = match.group(1).strip()
                declarations = match.group(2).strip()
                attrs: dict[str, str] = {}
                for decl in declarations.split(';'):
                    decl = decl.strip()
                    if ':' in decl:
                        prop, val = decl.split(':', 1)
                        attrs[prop.strip()] = val.strip().strip("'\"")
                if attrs:
                    css_rules[class_name] = attrs

        if not css_rules:
            return svg_bytes

        # 2. Parse XML with ElementTree and inline attributes
        tree = ET.fromstring(svg_str.encode("utf-8"))

        for elem in tree.iter():
            cls_attr = elem.get("class")
            if cls_attr:
                for c in cls_attr.split():
                    if c in css_rules:
                        for k, v in css_rules[c].items():
                            if k not in elem.attrib:
                                elem.set(k, v)

        return ET.tostring(tree, encoding="utf-8")
    except Exception:
        return svg_bytes


class DrawingRenderer:
    """Produces a normalized PNG from a drawing source file.

    Fails explicitly if rendering fails or produces a blank image.
    """

    def render(self, source: DrawingSource, output_dir: Path) -> RenderResult:
        """Render the drawing to a normalized PNG.

        Parameters
        ----------
        source : DrawingSource
            Ingested source metadata (source_path must exist).
        output_dir : Path
            Directory to write the normalized PNG.

        Returns
        -------
        RenderResult
            PNG path, pixel dimensions, SHA-256, quality level, and notes.

        Raises
        ------
        RuntimeError
            If rendering fails or produces a blank image.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(source.filename).stem
        out_png = output_dir / f"{stem}_normalized.png"
        mime = source.mime_type

        if mime == "application/pdf":
            result = self._render_pdf(Path(source.source_path), out_png)
        elif mime == "image/svg+xml":
            result = self._render_svg(Path(source.source_path), out_png)
        elif mime in ("image/png", "image/jpeg"):
            result = self._render_raster(Path(source.source_path), out_png, mime)
        else:
            raise ValueError(f"Cannot render unsupported MIME type: {mime}")

        # Strict post-render verification: ensure output PNG is not blank
        blank, reason = is_blank_image(result.png_path)
        if blank:
            raise RuntimeError(
                f"Normalized drawing rendering failed: produced a blank/invalid image ({reason}). "
                f"Source: '{source.filename}' ({mime})."
            )

        return result

    # ------------------------------------------------------------------
    # SVG rendering
    # ------------------------------------------------------------------

    def _render_svg(self, src: Path, out_png: Path) -> RenderResult:
        """Converts SVG to high-resolution PNG using available vector rendering engines.

        Priority order:
        1. PyMuPDF (fitz) with CSS inlining - native vector rasterizer at 200 DPI
        2. CairoSVG
        3. svglib + ReportLab PDF bridge
        4. Inkscape CLI
        """
        errors = []
        raw_svg_bytes = src.read_bytes()
        prepared_svg_bytes = _prepare_svg_for_rendering(raw_svg_bytes)

        # Attempt 1: PyMuPDF (fitz) - fast, high-quality vector rasterizer
        try:
            import fitz  # type: ignore
            doc = fitz.open(stream=prepared_svg_bytes, filetype="svg")
            if len(doc) > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=200, alpha=False)
                pix.save(str(out_png))
                doc.close()

                blank, reason = is_blank_image(out_png)
                if not blank:
                    dims = _png_dimensions(out_png.read_bytes())
                    w, h = dims if dims else (pix.width, pix.height)
                    sha = _sha256_path(out_png)
                    return RenderResult(
                        out_png, w, h, sha, "full",
                        f"Rendered via PyMuPDF (fitz) vector engine at 200 DPI ({w}x{h})."
                    )
                else:
                    errors.append(f"PyMuPDF output was blank: {reason}")
            else:
                errors.append("PyMuPDF: document contains 0 pages")
        except ImportError:
            errors.append("PyMuPDF (fitz) not installed in current environment")
        except Exception as exc:
            errors.append(f"PyMuPDF error: {exc}")

        # Attempt 2: CairoSVG
        try:
            import cairosvg  # type: ignore
            data = src.read_bytes()
            cairosvg.svg2png(
                bytestring=data,
                write_to=str(out_png),
                dpi=200,
                scale=2.0,
            )
            blank, reason = is_blank_image(out_png)
            if not blank:
                raw = out_png.read_bytes()
                dims = _png_dimensions(raw)
                w, h = dims if dims else (0, 0)
                sha = _sha256_path(out_png)
                return RenderResult(
                    out_png, w, h, sha, "full",
                    f"Rendered via CairoSVG at 200 DPI ({w}x{h})."
                )
            else:
                errors.append(f"CairoSVG output was blank: {reason}")
        except ImportError:
            errors.append("CairoSVG not installed")
        except Exception as exc:
            errors.append(f"CairoSVG error: {exc}")

        # Attempt 3: svglib + ReportLab PDF bridge -> PyMuPDF
        try:
            from svglib.svglib import svg2rlg  # type: ignore
            from reportlab.graphics import renderPDF  # type: ignore
            drawing = svg2rlg(str(src))
            if drawing:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                    tmp_pdf_path = Path(tmp_pdf.name)
                try:
                    renderPDF.drawToFile(drawing, str(tmp_pdf_path))
                    import fitz  # type: ignore
                    doc = fitz.open(str(tmp_pdf_path))
                    if len(doc) > 0:
                        page = doc.load_page(0)
                        pix = page.get_pixmap(dpi=200)
                        pix.save(str(out_png))
                        doc.close()
                        blank, reason = is_blank_image(out_png)
                        if not blank:
                            dims = _png_dimensions(out_png.read_bytes())
                            w, h = dims if dims else (pix.width, pix.height)
                            sha = _sha256_path(out_png)
                            return RenderResult(
                                out_png, w, h, sha, "full",
                                f"Rendered via svglib + ReportLab PDF bridge at 200 DPI ({w}x{h})."
                            )
                finally:
                    tmp_pdf_path.unlink(missing_ok=True)
            errors.append("svglib: failed to parse drawing")
        except ImportError:
            errors.append("svglib/reportlab not installed")
        except Exception as exc:
            errors.append(f"svglib bridge error: {exc}")

        # Attempt 4: Inkscape CLI
        try:
            res = subprocess.run(
                [
                    "inkscape", "--export-type=png", f"--export-filename={out_png}",
                    "--export-dpi=200", str(src)
                ],
                capture_output=True, timeout=60,
            )
            if res.returncode == 0 and out_png.exists():
                blank, reason = is_blank_image(out_png)
                if not blank:
                    raw = out_png.read_bytes()
                    dims = _png_dimensions(raw)
                    w, h = dims if dims else (0, 0)
                    sha = _sha256_path(out_png)
                    return RenderResult(
                        out_png, w, h, sha, "full",
                        f"Rendered via Inkscape CLI at 200 DPI ({w}x{h})."
                    )
                else:
                    errors.append(f"Inkscape output was blank: {reason}")
            else:
                errors.append(f"Inkscape CLI returned code {res.returncode}")
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            errors.append(f"Inkscape CLI unavailable: {exc}")

        # All rendering attempts failed — FAIL EXPLICITLY, never send a blank image
        err_msg = (
            f"SVG rendering failed. No working SVG renderer is available.\n"
            f"Diagnostics:\n" + "\n".join(f"  - {e}" for e in errors) + "\n"
            f"Please install 'pymupdf' (`pip install pymupdf`) or 'cairosvg' (`pip install cairosvg`)."
        )
        raise RuntimeError(err_msg)

    # ------------------------------------------------------------------
    # PDF rendering
    # ------------------------------------------------------------------

    def _render_pdf(self, src: Path, out_png: Path) -> RenderResult:
        """Renders PDF to normalized PNG. Fails explicitly if dependencies missing."""
        data = src.read_bytes()
        errors = []

        # Attempt 1: pymupdf (fitz)
        try:
            import fitz  # type: ignore
            doc = fitz.open(stream=data, filetype="pdf")
            if len(doc) > 0:
                page = doc.load_page(0)
                mat = fitz.Matrix(3.0, 3.0)  # ~216 DPI
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pix.save(str(out_png))
                doc.close()
                blank, reason = is_blank_image(out_png)
                if not blank:
                    w, h = pix.width, pix.height
                    sha = _sha256_path(out_png)
                    return RenderResult(out_png, w, h, sha, "full", f"Rendered via PyMuPDF at 216 DPI ({w}x{h}).")
                else:
                    errors.append(f"PyMuPDF output was blank: {reason}")
        except ImportError:
            errors.append("PyMuPDF (fitz) not installed")
        except Exception as exc:
            errors.append(f"PyMuPDF error: {exc}")

        # Attempt 2: pdf2image
        try:
            from pdf2image import convert_from_bytes  # type: ignore
            images = convert_from_bytes(data, dpi=200, first_page=1, last_page=1)
            if images:
                img = images[0]
                img.save(str(out_png), "PNG")
                blank, reason = is_blank_image(out_png)
                if not blank:
                    w, h = img.size
                    sha = _sha256_path(out_png)
                    return RenderResult(out_png, w, h, sha, "full", f"Rendered via pdf2image at 200 DPI ({w}x{h}).")
                else:
                    errors.append(f"pdf2image output was blank: {reason}")
        except ImportError:
            errors.append("pdf2image not installed")
        except Exception as exc:
            errors.append(f"pdf2image error: {exc}")

        # Attempt 3: ghostscript via subprocess
        try:
            result = subprocess.run(
                [
                    "gs", "-dNOPAUSE", "-dBATCH", "-dSAFER",
                    "-sDEVICE=png16m", "-r200",
                    f"-sOutputFile={out_png}", str(src),
                ],
                capture_output=True, timeout=60,
            )
            if result.returncode == 0 and out_png.exists():
                blank, reason = is_blank_image(out_png)
                if not blank:
                    raw = out_png.read_bytes()
                    dims = _png_dimensions(raw)
                    w, h = dims if dims else (0, 0)
                    sha = _sha256_path(out_png)
                    return RenderResult(out_png, w, h, sha, "full", f"Rendered via Ghostscript at 200 DPI ({w}x{h}).")
                else:
                    errors.append(f"Ghostscript output was blank: {reason}")
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            errors.append(f"Ghostscript unavailable: {exc}")

        err_msg = (
            f"PDF rendering failed. No working PDF renderer is available.\n"
            f"Diagnostics:\n" + "\n".join(f"  - {e}" for e in errors) + "\n"
            f"Please install 'pymupdf' (`pip install pymupdf`) or 'pdf2image'."
        )
        raise RuntimeError(err_msg)

    # ------------------------------------------------------------------
    # Raster (PNG/JPEG) rendering
    # ------------------------------------------------------------------

    def _render_raster(self, src: Path, out_png: Path, mime: str) -> RenderResult:
        """Copy or normalize source raster, upscaling to MIN_LONG_EDGE_PX if needed."""
        data = src.read_bytes()

        try:
            from PIL import Image  # type: ignore
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            long_edge = max(w, h)
            if long_edge < MIN_LONG_EDGE_PX and long_edge > 0:
                scale = MIN_LONG_EDGE_PX / long_edge
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                note = f"Upscaled from {w}x{h} to {new_w}x{new_h} for AI model quality."
                w, h = new_w, new_h
            else:
                note = f"Used original {w}x{h} resolution."
            img.save(str(out_png), "PNG")
            sha = _sha256_path(out_png)
            return RenderResult(out_png, w, h, sha, "copy", note)
        except ImportError:
            if mime == "image/png":
                shutil.copy2(src, out_png)
                dims = _png_dimensions(data)
                w, h = dims if dims else (0, 0)
                sha = _sha256_path(out_png)
                return RenderResult(out_png, w, h, sha, "copy", "Copied PNG source directly.")
            else:
                raise RuntimeError("Pillow is required to convert JPEG images to PNG.")
        except Exception as exc:
            raise RuntimeError(f"Failed to process raster image: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svg_dimensions_from_bytes(data: bytes) -> Tuple[Optional[int], Optional[int]]:
    try:
        xml_str = data.decode("utf-8", errors="replace")
        xml_str = xml_str.replace(' xmlns="http://www.w3.org/2000/svg"', "")
        root = ET.fromstring(xml_str)

        def _parse(v: str) -> Optional[int]:
            v = v.strip()
            for suffix in ("px", "mm", "in", "pt", "cm"):
                v = v.rstrip(suffix).strip()
            try:
                return int(float(v))
            except ValueError:
                return None

        return _parse(root.get("width", "")), _parse(root.get("height", ""))
    except ET.ParseError:
        return None, None


def build_manifest(
    provider: str,
    model: str,
    png_path: Path,
    width_px: int,
    height_px: int,
    prompt: str,
) -> MultimodalRequestManifest:
    """Build and validate a multimodal request manifest for an actual image payload."""
    data = png_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    return MultimodalRequestManifest(
        provider=provider,
        model=model,
        image_path=str(png_path),
        mime_type="image/png",
        image_width_px=width_px,
        image_height_px=height_px,
        image_byte_size=len(data),
        image_sha256=sha,
        image_attached=True,          # validator enforces this is always True
        prompt_length_chars=len(prompt),
        request_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def crop_detected_views(
    png_path: Path,
    views: List[Any],
    output_dir: Path,
    padding_pct: float = 0.05,
) -> Dict[str, Path]:
    """Crop individual orthographic views from the full drawing PNG at high resolution.

    Parameters
    ----------
    png_path : Path
        Path to the high-resolution normalized drawing PNG.
    views : List[DetectedView]
        List of detected views with bounding boxes.
    output_dir : Path
        Destination directory for cropped view images.
    padding_pct : float
        Proportional margin around each view bbox to include nearby dimension callouts.

    Returns
    -------
    Dict[str, Path]
        Mapping from view_id to cropped PNG image path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_map: Dict[str, Path] = {}

    try:
        from PIL import Image
        with Image.open(png_path) as im:
            img_w, img_h = im.size

            for v in views:
                vid = getattr(v, "view_id", "view")
                vtype = str(getattr(v, "view_type", "view")).lower()
                bbox = getattr(v, "bbox", None)
                if not bbox:
                    continue

                x1 = float(getattr(bbox, "x1", 0.0))
                y1 = float(getattr(bbox, "y1", 0.0))
                x2 = float(getattr(bbox, "x2", 0.0))
                y2 = float(getattr(bbox, "y2", 0.0))

                if x2 <= x1 or y2 <= y1:
                    continue

                # Add padding
                w_box = x2 - x1
                h_box = y2 - y1
                pad_x = w_box * padding_pct
                pad_y = h_box * padding_pct

                crop_x1 = max(0, int(x1 - pad_x))
                crop_y1 = max(0, int(y1 - pad_y))
                crop_x2 = min(img_w, int(x2 + pad_x))
                crop_y2 = min(img_h, int(y2 + pad_y))

                if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                    continue

                cropped = im.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                out_name = f"view_{vid}_{vtype}.png"
                out_path = output_dir / out_name
                cropped.save(str(out_path), "PNG")
                crop_map[vid] = out_path

    except Exception:
        pass

    return crop_map


def _write_placeholder_png(path: Path, width: int = 100, height: int = 100) -> None:
    """Generate a minimal valid PNG for test stubbing."""
    import zlib
    raw_data = b"\x00" + b"\x80" * (width * 3)
    compressed = zlib.compress(raw_data * height)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed))
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
        + struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
        + struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    )
    path.write_bytes(png_bytes)

