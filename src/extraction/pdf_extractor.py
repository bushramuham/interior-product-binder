"""Extract text and images from a local PDF using PyMuPDF."""

import io
import os
import re

import fitz  # PyMuPDF
from PIL import Image

import config
from src.models import ExtractedContent


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "pdf"


def extract_pdf(path: str) -> ExtractedContent:
    """Extract readable text and up to MAX_IMAGES_PER_PRODUCT useful images."""
    try:
        doc = fitz.open(path)
    except Exception as e:
        return ExtractedContent(error=f"Could not open PDF '{path}': {e}")

    try:
        text_parts = []
        total_chars = 0
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
                total_chars += len(page_text)
            if total_chars >= config.MAX_TEXT_CHARS_TO_AI:
                break
        text = "\n".join(text_parts)[: config.MAX_TEXT_CHARS_TO_AI]

        image_paths = []
        os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
        base = _slug(os.path.splitext(os.path.basename(path))[0])
        seen_xrefs = set()
        for page in doc:
            if len(image_paths) >= config.MAX_IMAGES_PER_PRODUCT:
                break
            for img in page.get_images(full=True):
                if len(image_paths) >= config.MAX_IMAGES_PER_PRODUCT:
                    break
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    extracted = doc.extract_image(xref)
                    pil = Image.open(io.BytesIO(extracted["image"]))
                    if min(pil.size) < config.MIN_IMAGE_DIMENSION_PX:
                        continue  # likely an icon/logo
                    out_path = os.path.join(
                        config.TEMP_IMAGE_DIR, f"{base}_{len(image_paths)}.png"
                    )
                    pil.convert("RGB").save(out_path, "PNG")
                    image_paths.append(out_path)
                except Exception as e:
                    print(f"  WARNING: skipping image xref {xref} in '{path}': {e}")

        return ExtractedContent(text=text, image_paths=image_paths)
    finally:
        doc.close()
