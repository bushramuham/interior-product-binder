"""Generate the evidence assets for the Assignment07 submission report.

Runs the binder tool (DFH template) against demo schedules, renders the key PDF
pages to PNG, and captures a real API interaction (with prompt-cache stats) into
the submission assets folder. Page selection is content-based so it survives
layout/page-count changes.

Run from the repo root:  python scripts/make_submission_assets.py
"""

import io
import json
import os
import sys
from contextlib import redirect_stdout

import fitz
from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

load_dotenv()

import anthropic  # noqa: E402

import config  # noqa: E402
from src import ai_client, excel_reader, pipeline  # noqa: E402
from src.extraction import source_router  # noqa: E402

ASSETS = os.path.join("submission", "Bushra_Muhammadi_Assignment07", "assets")
os.makedirs(ASSETS, exist_ok=True)

PROJECT = "721 CHAUTAUQUA AVE - PALISADES REBUILD"

# Demo schedule: a grouped vanity (U-36/U-37/U-03), a chair, and a sourceless
# key (U-38) that must render OWNER INPUT NEEDED.
DEMO_ROWS = [
    {"KEY": "U-36", "DESCRIPTION": "VANITY CABINET - 36-IN",
     "PATH": "examples/pdfs/sample_vanity_spec.pdf", "DESCRIPTION2": "MARBLE TOP"},
    {"KEY": "U-37", "DESCRIPTION": "VANITY COUNTERTOP - 36-IN",
     "PATH": "examples/pdfs/sample_vanity_spec.pdf"},
    {"KEY": "U-03", "DESCRIPTION": "BATHROOM SINK",
     "PATH": "examples/pdfs/sample_vanity_spec.pdf", "DESCRIPTION2": "UNDERMOUNT"},
    {"KEY": "CH-01", "DESCRIPTION": "LOUNGE CHAIR - LIVING ROOM",
     "PATH": "examples/pdfs/sample_chair_spec.pdf"},
    {"KEY": "U-38", "DESCRIPTION": "TOWEL RING", "PATH": ""},
]


def run(xlsx: str, out_pdf: str, project: str, name: str) -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        results = pipeline.generate_from_xlsx(xlsx, out_pdf, project, "DFH Architects")
        failed = [r for r in results if r.error]
        print(f"\nDone. {len(results)} group(s): "
              f"{len(results) - len(failed)} ok, {len(failed)} failed.")
    with open(os.path.join(ASSETS, f"log_{name}.txt"), "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"ran {name}: binder + log saved")


def find_page(doc, *needles) -> int | None:
    for i, pg in enumerate(doc):
        text = pg.get_text().lower()
        if all(n.lower() in text for n in needles):
            return i
    return None


def render(pdf: str, out_name: str, *needles, dpi: int = 105) -> None:
    doc = fitz.open(os.path.join(ASSETS, pdf))
    idx = find_page(doc, *needles)
    if idx is not None:
        doc[idx].get_pixmap(dpi=dpi).save(os.path.join(ASSETS, out_name))
        print(f"rendered {out_name} (page {idx + 1})")
    else:
        print(f"WARNING: no page matched {needles} in {pdf}")
    doc.close()


def capture_ai_interaction() -> None:
    pipeline.reset_temp_images()
    products = excel_reader.load_products("examples/example_grouping.xlsx")
    vanity = products[0]
    extracted = source_router.extract_source(vanity, "examples")
    client = anthropic.Anthropic()
    user_text = (
        f"Product keys: {', '.join(vanity.keys)}\n"
        f"Schedule descriptions: {vanity.combined_description}\n\n"
        f"Extracted source text:\n{extracted.text}"
    )

    def call():
        return client.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=config.MAX_OUTPUT_TOKENS,
            system=[{"type": "text", "text": ai_client.SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            tools=[ai_client.EXTRACT_PRODUCT_INFO_TOOL],
            tool_choice={"type": "tool", "name": "extract_product_info"},
            messages=[{"role": "user", "content": [{"type": "text", "text": user_text}]}],
        )

    r1, r2 = call(), call()
    tool_use = next(b for b in r1.content if b.type == "tool_use")
    capture = {
        "model": config.ANTHROPIC_MODEL,
        "input_excerpt": user_text[:1200],
        "structured_output": tool_use.input,
        "usage_call_1": dict(input_tokens=r1.usage.input_tokens,
                             cache_creation_input_tokens=r1.usage.cache_creation_input_tokens,
                             cache_read_input_tokens=r1.usage.cache_read_input_tokens,
                             output_tokens=r1.usage.output_tokens),
        "usage_call_2": dict(input_tokens=r2.usage.input_tokens,
                             cache_creation_input_tokens=r2.usage.cache_creation_input_tokens,
                             cache_read_input_tokens=r2.usage.cache_read_input_tokens,
                             output_tokens=r2.usage.output_tokens),
    }
    with open(os.path.join(ASSETS, "ai_interaction.json"), "w", encoding="utf-8") as f:
        json.dump(capture, f, indent=2)
    print(f"captured ai_interaction.json "
          f"(cache read on call 2: {r2.usage.cache_read_input_tokens} tokens)")


def main() -> int:
    demo_xlsx = os.path.join(ASSETS, "demo_schedule.xlsx")
    excel_reader.save_schedule(DEMO_ROWS, demo_xlsx)
    demo_pdf = os.path.join(ASSETS, "binder_demo.pdf")
    run(demo_xlsx, demo_pdf, PROJECT, "demo")
    run("examples/example_mixed_sources.xlsx",
        os.path.join(ASSETS, "binder_mixed.pdf"), "Mixed Sources Demo", "mixed")
    run("examples/example_errors.xlsx",
        os.path.join(ASSETS, "binder_errors.pdf"), "Error Handling Demo", "errors")

    render("binder_demo.pdf", "page_cover.png", "prepared by")
    render("binder_demo.pdf", "page_toc.png", "table of contents")
    render("binder_demo.pdf", "page_vanity_grouped.png", "u-36", "materials")
    render("binder_demo.pdf", "page_chair.png", "ch-01", "dimensions")  # product page, not TOC
    render("binder_demo.pdf", "page_owner.png", "owner input needed")
    render("binder_mixed.pdf", "page_web_eames.png", "eames", "materials")
    render("binder_errors.pdf", "page_error_block.png", "could not generate")

    capture_ai_interaction()
    print("\nAll submission assets generated in", ASSETS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
