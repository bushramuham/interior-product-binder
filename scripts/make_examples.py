"""Generate the committed example data: sample spec-sheet PDFs and schedule .xlsx files.

Run from the repo root:
    python scripts/make_examples.py
"""

import io
import os
import sys

from openpyxl import Workbook
from PIL import Image as PILImage, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples")
PDFS_DIR = os.path.join(EXAMPLES_DIR, "pdfs")

HEADERS = ["KEY", "DESCRIPTION", "PG", "PATH", "DESCRIPTION2", "DESCRIPTION3"]

SAMPLE_PRODUCTS = {
    "sample_chair_spec.pdf": {
        "title": "AXEL Lounge Chair — Model AX-200",
        "manufacturer": "Nordform Studio",
        "color": (176, 122, 78),
        "body": [
            "The AXEL lounge chair pairs a solid white-oak frame with a molded "
            "plywood shell and full-grain leather upholstery. Designed for "
            "residential and light-commercial interiors.",
            "Overall dimensions: 30 in W x 32 in D x 28 in H. Seat height: 16 in. "
            "Weight capacity: 300 lb.",
            "Materials: solid white oak frame, molded plywood shell, top-grain "
            "aniline leather seat and back.",
            "Finishes: natural oak, smoked oak, or ebonized oak. Leather in "
            "cognac, charcoal, and ivory.",
            "Certifications: ANSI/BIFMA X5.4 tested. GREENGUARD Gold certified.",
            "Installation: ships fully assembled. Attach felt glides (included) "
            "before placing on hardwood floors.",
            "Care: vacuum leather weekly with soft brush attachment. Condition "
            "leather twice yearly. Wipe oak with a dry cloth; avoid silicone polish.",
        ],
    },
    "sample_vanity_spec.pdf": {
        "title": "MARLOW 60-in Double Vanity Suite — Model MV-6022",
        "manufacturer": "Calderhouse Bath",
        "color": (98, 128, 148),
        "body": [
            "The MARLOW vanity suite combines a 60-inch solid-birch cabinet, a "
            "honed Carrara marble countertop, and two undermount ceramic basins "
            "sold as a coordinated set.",
            "Cabinet: 60 in W x 22 in D x 34 in H, two soft-close doors and six "
            "dovetailed drawers. Countertop: 61 in W x 22.5 in D x 1.25 in thick, "
            "pre-drilled for 8-in widespread faucets.",
            "Materials: solid birch cabinet with plywood box, natural Carrara "
            "marble top, vitreous china basins.",
            "Finishes: cabinet in dove white, storm grey, or natural birch; "
            "polished nickel or matte black hardware.",
            "Certifications: cUPC listed basins. CARB Phase 2 compliant casework.",
            "Installation: secure cabinet to wall studs with included cleats. "
            "Marble top requires two installers; seal before first use. Rough-in "
            "drain at 21 in AFF recommended.",
            "Care: reseal marble every 12 months. Clean with pH-neutral stone "
            "cleaner only. Wipe cabinet with damp cloth.",
        ],
    },
    "sample_light_fixture_spec.pdf": {
        "title": "ORBIT 18 Pendant — Model OR-18-BR",
        "manufacturer": "Lumen & Field",
        "color": (196, 168, 90),
        "body": [
            "The ORBIT 18 pendant features a spun-brass shade with a white "
            "powder-coated interior for warm, glare-free downlight over kitchen "
            "islands and dining tables.",
            "Dimensions: 18 in diameter x 9 in H shade. Overall drop adjustable "
            "12 in to 60 in via field-cuttable cord.",
            "Materials: spun brass shade, steel canopy, cloth-wrapped cord.",
            "Finishes: natural brushed brass, blackened brass, or polished nickel.",
            "Certifications: UL and cUL listed for dry locations. Title 24 "
            "compliant with included LED lamp.",
            "Electrical: E26 medium base, 100 W max incandescent or 17 W LED "
            "(included, 1600 lumens, 2700 K, 90+ CRI, dimmable).",
            "Installation: mounts to standard 4-in octagonal junction box. "
            "Canopy hardware included. Ceiling support must hold 15 lb.",
            "Care: dust with dry microfiber cloth. Uncoated brass will patina "
            "naturally; polish with brass cleaner if a bright finish is preferred.",
        ],
    },
}


def _product_image(color: tuple[int, int, int], label: str) -> str:
    """Draw a simple raster 'product photo' PNG and return its temp path."""
    img = PILImage.new("RGB", (640, 480), (245, 243, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 100, 560, 420], fill=color, outline=(60, 55, 50), width=4)
    draw.rectangle([120, 140, 520, 260], fill=tuple(min(c + 40, 255) for c in color))
    draw.text((90, 40), label, fill=(60, 55, 50))
    path = os.path.join(PDFS_DIR, "_tmp_img.png")
    img.save(path, "PNG")
    return path


def make_pdfs() -> None:
    styles = getSampleStyleSheet()
    for filename, spec in SAMPLE_PRODUCTS.items():
        img_path = _product_image(spec["color"], spec["title"])
        story = [
            Paragraph(spec["title"], styles["Title"]),
            Paragraph(spec["manufacturer"], styles["Heading2"]),
            Spacer(1, 12),
            Image(img_path, width=4.5 * inch, height=3.375 * inch),
            Spacer(1, 16),
        ]
        for para in spec["body"]:
            story.append(Paragraph(para, styles["Normal"]))
            story.append(Spacer(1, 8))
        out = os.path.join(PDFS_DIR, filename)
        SimpleDocTemplate(out, pagesize=letter).build(story)
        os.remove(img_path)
        print(f"wrote {out}")


def _write_xlsx(name: str, rows: list[list[str]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "MC Schedule by Keynote"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    out = os.path.join(EXAMPLES_DIR, name)
    wb.save(out)
    print(f"wrote {out}")


def make_xlsx_files() -> None:
    chair = "examples/pdfs/sample_chair_spec.pdf"
    vanity = "examples/pdfs/sample_vanity_spec.pdf"
    light = "examples/pdfs/sample_light_fixture_spec.pdf"

    _write_xlsx("example_basic.xlsx", [
        ["CH-01", "LOUNGE CHAIR - LIVING ROOM", "1", chair, "", ""],
        ["LT-01", "PENDANT @ KITCHEN ISLAND", "2", light, "", ""],
    ])

    _write_xlsx("example_grouping.xlsx", [
        ["U-36", "VANITY CABINET - 60-IN", "1", vanity, "", ""],
        ["U-37", "VANITY COUNTERTOP - 60-IN", "1", vanity, "MARBLE TOP", ""],
        ["U-03", "BATHROOM SINK", "1", vanity, "UNDERMOUNT", "CERAMIC BASIN"],
        ["CH-01", "LOUNGE CHAIR - LIVING ROOM", "2", chair, "", ""],
        ["LT-01", "PENDANT @ KITCHEN ISLAND", "3", light, "", ""],
    ])

    _write_xlsx("example_mixed_sources.xlsx", [
        ["CH-01", "LOUNGE CHAIR - LIVING ROOM", "1", chair, "", ""],
        ["CH-02", "ICONIC LOUNGE CHAIR - STUDY",
         "2", "https://en.wikipedia.org/wiki/Eames_Lounge_Chair", "", ""],
        ["CH-03", "ACCENT CHAIR - ENTRY",
         "3", "https://en.wikipedia.org/wiki/Barcelona_chair", "", ""],
        ["LT-01", "PENDANT @ KITCHEN ISLAND", "4", light, "", ""],
    ])

    _write_xlsx("example_errors.xlsx", [
        ["CH-01", "LOUNGE CHAIR - LIVING ROOM", "1", chair, "", ""],
        ["XX-01", "MISSING SPEC SHEET", "2",
         "products/does_not_exist.pdf", "", ""],
        ["XX-02", "UNREACHABLE PRODUCT PAGE", "3",
         "https://this-domain-does-not-exist-xyz123.example.invalid/product", "", ""],
        ["U-36", "VANITY CABINET - 60-IN", "4", vanity, "", ""],
        ["U-37", "VANITY COUNTERTOP - 60-IN", "4", vanity, "", ""],
    ])


def main() -> int:
    os.makedirs(PDFS_DIR, exist_ok=True)
    make_pdfs()
    make_xlsx_files()
    return 0


if __name__ == "__main__":
    sys.exit(main())
