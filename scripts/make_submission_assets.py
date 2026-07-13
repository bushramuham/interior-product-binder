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
from src import ai_client, excel_reader, pdf_builder, pipeline  # noqa: E402
from src.extraction import pdf_extractor, source_router, web_extractor  # noqa: E402
from src.models import Product, ProductEntry, ProductInfo, ProductResult  # noqa: E402

ASSETS = os.path.join("submission", "Bushra_Muhammadi_Assignment07", "assets")
os.makedirs(ASSETS, exist_ok=True)

PROJECT = "721 CHAUTAUQUA AVE - PALISADES REBUILD"


def _first_image(pdf_path: str) -> str | None:
    ec = pdf_extractor.extract_pdf(pdf_path)
    return ec.image_paths[0] if ec.image_paths else None


def build_demo_binder(out_pdf: str) -> None:
    """Deterministic showcase binder (fixture-fed) so the layout figures are
    always populated and carry the draft banner. Product data mirrors the real
    extraction of the project's own sample spec sheets; the genuine AI round-trip
    is captured separately in ai_interaction.json."""
    pipeline.reset_temp_images()
    vanity = Product("g1", "examples/pdfs/sample_vanity_spec.pdf", "pdf", [
        ProductEntry("U-36", "VANITY CABINET - 36-IN"),
        ProductEntry("U-37", "VANITY COUNTERTOP - 36-IN"),
        ProductEntry("U-03", "BATHROOM SINK")])
    vanity_info = ProductInfo(
        product_name="MARLOW Double Vanity Suite - Cabinet (MV-6022)",
        manufacturer="Calderhouse Bath",
        description="The Marlow 60-in double vanity cabinet is solid birch with a "
        "plywood box, two soft-close doors, and six dovetailed drawers, sold as a "
        "coordinated suite with a honed Carrara marble top and undermount basins.",
        dimensions="60 in W x 22 in D x 34 in H",
        materials="Solid birch face frame and doors; plywood box construction",
        finishes="Dove White, Storm Grey, or Natural Birch; Polished Nickel or Matte Black hardware",
        certifications="CARB Phase 2 compliant casework",
        installation_notes="Secure cabinet to wall studs using included mounting cleats.",
        care_notes="Wipe cabinet surfaces with a damp cloth.",
        important_specs=["Model: MV-6022", "Two soft-close doors",
                         "Sold as a set with countertop and basins (U-37, U-03)"])
    chair = Product("g2", "examples/pdfs/sample_chair_spec.pdf", "pdf",
                    [ProductEntry("CH-01", "LOUNGE CHAIR - LIVING ROOM")])
    chair_info = ProductInfo(
        product_name="AXEL Lounge Chair - Model AX-200",
        manufacturer="Nordform Studio",
        description="A residential lounge chair with a solid white-oak frame and a "
        "molded plywood shell upholstered in top-grain aniline leather.",
        dimensions="30 in W x 32 in D x 28 in H; Seat height 16 in",
        materials="Solid white oak frame; molded plywood shell; aniline leather",
        finishes="Natural, smoked, or ebonized oak; cognac, charcoal, or ivory leather",
        certifications="ANSI/BIFMA X5.4 tested; GREENGUARD Gold certified",
        installation_notes="Ships fully assembled.",
        important_specs=["Model: AX-200", "Weight capacity: 300 lb"])
    eames = Product("g_web", "https://en.wikipedia.org/wiki/Eames_Lounge_Chair", "url",
                    [ProductEntry("CH-02", "LOUNGE CHAIR - STUDY")])
    eames_info = ProductInfo(
        product_name="Eames Lounge Chair and Ottoman (Model 670 / 671)",
        manufacturer="Herman Miller (MillerKnoll)",
        description="A mid-century lounge chair and ottoman with a molded plywood "
        "shell and leather upholstery, in continuous production since 1956.",
        dimensions="Overall dimensions vary by configuration",
        materials="Molded plywood shell; leather cushions; aluminum base",
        finishes="Multiple veneer and leather options",
        important_specs=["Model numbers: 670 (chair) / 671 (ottoman)",
                         "In production since 1956"])
    web_img = None
    ec = web_extractor.extract_url(eames.source_path)
    if ec.image_paths:
        web_img = ec.image_paths[0]

    towel = Product("g3", "", "none", [ProductEntry("U-38", "TOWEL RING")])
    results = [
        # PDF sources -> overlay mode (source pages embedded verbatim + stamped).
        ProductResult(vanity, source_pdf_path="examples/pdfs/sample_vanity_spec.pdf"),
        ProductResult(chair, source_pdf_path="examples/pdfs/sample_chair_spec.pdf"),
        # URL source -> rebuilt page (no PDF to overlay).
        ProductResult(eames, info=eames_info, representative_image=web_img),
        ProductResult(towel, needs_owner_input=True),
    ]
    pdf_builder.build_binder(results, out_pdf, PROJECT)
    print("built demo binder (fixtures):", out_pdf)


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


def find_page(doc, *needles, exclude: str | None = None) -> int | None:
    def norm(s: str) -> str:
        return "".join(s.split()).lower()  # strip all whitespace (codes can wrap)

    for i, pg in enumerate(doc):
        text = norm(pg.get_text())
        if exclude and norm(exclude) in text:
            continue
        if all(norm(n) in text for n in needles):
            return i
    return None


def render(pdf: str, out_name: str, *needles, exclude: str | None = None, dpi: int = 105) -> None:
    doc = fitz.open(os.path.join(ASSETS, pdf))
    idx = find_page(doc, *needles, exclude=exclude)
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
    build_demo_binder(os.path.join(ASSETS, "binder_demo.pdf"))
    run("examples/example_errors.xlsx",
        os.path.join(ASSETS, "binder_errors.pdf"), "Error Handling Demo", "errors")

    render("binder_demo.pdf", "page_cover.png", "prepared by")
    render("binder_demo.pdf", "page_toc.png", "table of contents")
    render("binder_demo.pdf", "page_vanity_grouped.png", "u-36", "materials")
    render("binder_demo.pdf", "page_chair.png", "ch-01", exclude="table of contents")
    render("binder_demo.pdf", "page_web_eames.png", "eames", exclude="table of contents")
    render("binder_demo.pdf", "page_owner.png", "owner input needed")
    render("binder_errors.pdf", "page_error_block.png", "could not generate")

    capture_ai_interaction()
    print("\nAll submission assets generated in", ASSETS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
