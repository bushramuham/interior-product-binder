"""Reusable end-to-end pipeline shared by the CLI (main.py) and the notebook."""

import datetime
import os
import re
import shutil

import config
from src import ai_client, excel_reader, pdf_builder
from src.extraction import source_router
from src.models import Product, ProductResult


def _slug(text: str, fallback: str) -> str:
    """Filesystem-safe fragment from a project/company name."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (text or "").strip()).strip("_")
    return cleaned[:60] or fallback


def unique_output_base(project_name: str, prepared_by: str, output_dir: str = "output") -> str:
    """Return a collision-free base path: output/<project>__<company>__<timestamp>.

    Callers append '.pdf' / '.xlsx'. The timestamp makes every run unique.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{_slug(project_name, 'project')}__{_slug(prepared_by, 'firm')}__{stamp}"
    return os.path.join(output_dir, name)


def reset_temp_images() -> None:
    """Clear the temp image dir so stale images never leak into a new binder."""
    shutil.rmtree(config.TEMP_IMAGE_DIR, ignore_errors=True)
    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)


def process_products(
    products: list[Product], xlsx_dir: str = "", log=print
) -> list[ProductResult]:
    """Extract each source and run AI extraction; never abort on a single failure."""
    results: list[ProductResult] = []
    for i, product in enumerate(products, start=1):
        keys = ", ".join(product.keys)
        if product.source_type == "none":
            log(f"[{i}/{len(products)}] {keys}: no source -> OWNER INPUT NEEDED")
            results.append(ProductResult(product=product, needs_owner_input=True))
            continue
        log(f"[{i}/{len(products)}] Processing {keys} ({product.source_path})")
        try:
            extracted = source_router.extract_source(product, xlsx_dir)
            representative = extracted.image_paths[0] if extracted.image_paths else None
            if extracted.error:
                log(f"  extraction failed: {extracted.error}")
                results.append(ProductResult(product=product, error=extracted.error))
                continue
            info, ai_error = ai_client.extract_product_info(product, extracted)
            if ai_error:
                log(f"  AI extraction failed: {ai_error}")
                results.append(
                    ProductResult(
                        product=product,
                        representative_image=representative,
                        error=ai_error,
                    )
                )
                continue
            results.append(
                ProductResult(
                    product=product, info=info, representative_image=representative
                )
            )
            log(f"  ok: {info.product_name or '(no name found)'}")
        except Exception as e:  # top-level safety net
            log(f"  unexpected error: {e}")
            results.append(ProductResult(product=product, error=str(e)))
    return results


def generate_from_xlsx(
    xlsx_path: str,
    output_path: str,
    project_name: str,
    prepared_by: str,
    log=print,
) -> list[ProductResult]:
    """Load a schedule, process every product, and write the binder PDF."""
    reset_temp_images()
    log(f"Reading schedule: {xlsx_path}")
    products = excel_reader.load_products(xlsx_path)
    log(f"Found {len(products)} product group(s)")

    xlsx_dir = os.path.dirname(os.path.abspath(xlsx_path))
    results = process_products(products, xlsx_dir, log)

    log(f"Building binder: {output_path}")
    actual = pdf_builder.build_binder(results, output_path, project_name, prepared_by)
    log(f"Binder written to: {actual}")
    return results
