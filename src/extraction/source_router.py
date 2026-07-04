"""Dispatch a Product's source to the right extractor."""

import os

from src.extraction import pdf_extractor, web_extractor
from src.models import ExtractedContent, Product


def extract_source(product: Product, xlsx_dir: str = "") -> ExtractedContent:
    """Extract text/images from the product's source.

    Local paths are tried as-is (relative to CWD) first; relative paths are
    also tried relative to the input spreadsheet's directory.
    """
    source = product.source_path
    if product.source_type == "url":
        return web_extractor.extract_url(source)

    resolved = source
    if not os.path.exists(resolved) and xlsx_dir and not os.path.isabs(source):
        candidate = os.path.join(xlsx_dir, source)
        if os.path.exists(candidate):
            resolved = candidate

    if not os.path.exists(resolved):
        return ExtractedContent(error=f"File not found: {source}")
    return pdf_extractor.extract_pdf(resolved)
