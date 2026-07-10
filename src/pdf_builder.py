"""Build the binder PDF in the DFH Architects template.

Cover (firm block + logo + DRAFT watermark), a table of contents, and one page
per product with navy KEY badges + descriptions, a serif brand heading, the
extracted image, and structured fields. Scheduled keys with no source render an
"OWNER INPUT NEEDED" page. Every page carries the DFH draft footer.
"""

import datetime
import io
import math
import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import config
from src.models import ProductResult

TOC_ROWS_PER_PAGE = 32
MAX_IMAGE_WIDTH = 3.6 * inch
MAX_IMAGE_HEIGHT = 3.0 * inch

# ─── DFH template palette (sampled from the reference binder) ─────────────────
NAVY = colors.HexColor("#2b3a8c")        # KEY codes + descriptions
DRAFT_RED = colors.HexColor("#d42a28")   # footer "DRAFT ... NOT FOR CONSTRUCTION"
LOGO_GREEN = colors.HexColor("#8a9a3a")  # "architects" in the logo
CHARCOAL = colors.HexColor("#404040")    # "dfh" in the logo, cover labels
WATERMARK = colors.HexColor("#8a8a8a")   # diagonal DRAFT watermark
FOOTER_GREY = colors.HexColor("#333333")

_styles = getSampleStyleSheet()
STYLE_COVER_LABEL = ParagraphStyle(
    "CoverLabel", parent=_styles["Normal"], fontSize=12, fontName="Helvetica-Bold",
    textColor=CHARCOAL,
)
STYLE_COVER_VALUE = ParagraphStyle(
    "CoverValue", parent=_styles["Normal"], fontSize=13, textColor=CHARCOAL, alignment=2,
)
STYLE_FIRM = ParagraphStyle(
    "Firm", parent=_styles["Normal"], fontSize=9.5, leading=12, textColor=CHARCOAL, alignment=2,
)
STYLE_LOGO_MAIN = ParagraphStyle(
    "LogoMain", parent=_styles["Normal"], fontSize=34, leading=32,
    fontName="Helvetica-Bold", textColor=CHARCOAL, alignment=2,
)
STYLE_LOGO_SUB = ParagraphStyle(
    "LogoSub", parent=_styles["Normal"], fontSize=12, leading=13,
    fontName="Helvetica", textColor=LOGO_GREEN, alignment=2,
)
STYLE_KEY_DESC = ParagraphStyle(
    "KeyDesc", parent=_styles["Normal"], fontSize=9.5, leading=11,
    textColor=NAVY, alignment=2,  # right, sits left of the code box
)
STYLE_CODE = ParagraphStyle(
    "Code", parent=_styles["Normal"], fontSize=15, leading=17,
    fontName="Helvetica-Bold", textColor=NAVY, alignment=1,
)
STYLE_BRAND = ParagraphStyle(
    "Brand", parent=_styles["Normal"], fontSize=17, leading=20,
    fontName="Times-Bold", textColor=colors.black, alignment=1,
)
STYLE_BRAND_SUB = ParagraphStyle(
    "BrandSub", parent=_styles["Normal"], fontSize=9, leading=11,
    textColor=colors.HexColor("#555555"), alignment=1,
)
STYLE_LABEL = ParagraphStyle(
    "FieldLabel", parent=_styles["Normal"], fontSize=11, fontName="Helvetica-Bold",
    textColor=CHARCOAL, spaceBefore=8, spaceAfter=2,
)
STYLE_BODY = ParagraphStyle(
    "FieldBody", parent=_styles["Normal"], fontSize=10, spaceAfter=4, leading=13,
)
STYLE_BULLET = ParagraphStyle("FieldBullet", parent=STYLE_BODY, leftIndent=14, bulletIndent=4)
STYLE_ERROR = ParagraphStyle(
    "ErrorBody", parent=STYLE_BODY, textColor=colors.HexColor("#8a1f11"),
)
STYLE_OWNER = ParagraphStyle(
    "Owner", parent=_styles["Normal"], fontSize=22, leading=26, fontName="Helvetica-Bold",
    textColor=NAVY, alignment=1, spaceBefore=40, spaceAfter=8,
)
STYLE_OWNER_SUB = ParagraphStyle(
    "OwnerSub", parent=_styles["Normal"], fontSize=10, textColor=colors.HexColor("#555555"),
    alignment=1,
)
STYLE_TOC_TITLE = ParagraphStyle(
    "TocTitle", parent=_styles["Heading1"], fontSize=14, spaceAfter=12, textColor=CHARCOAL,
)


def _date_long() -> str:
    d = datetime.date.today()
    return f"{d.month}/{d.day}/{d.year}"


def _date_short() -> str:
    d = datetime.date.today()
    return f"{d.month}/{d.day}/{str(d.year)[-2:]}"


class _BinderDoc(SimpleDocTemplate):
    """SimpleDocTemplate that records the page each tagged product heading lands on."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_numbers: dict[str, int] = {}

    def afterFlowable(self, flowable):
        group_id = getattr(flowable, "_product_group_id", None)
        if group_id is not None and group_id not in self.page_numbers:
            self.page_numbers[group_id] = self.page


def _escape(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─── Page furniture (footer on every page, watermark on the cover) ────────────
def _draw_footer(canvas, project_name: str) -> None:
    width = letter[0]
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(DRAFT_RED)
    canvas.drawCentredString(
        width / 2, 40, f"DRAFT {_date_short()} - NOT FOR CONSTRUCTION"
    )
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(FOOTER_GREY)
    canvas.drawString(0.6 * inch, 28, f"{config.FIRM_LLP}, {config.FIRM_ADDRESS}")
    canvas.drawCentredString(
        width / 2, 28,
        f"{project_name} - {config.BINDER_TAG} - {_date_long()}",
    )
    canvas.drawRightString(width - 0.6 * inch, 28, str(canvas.getPageNumber()))
    canvas.restoreState()


def _draw_watermark(canvas) -> None:
    canvas.saveState()
    canvas.translate(letter[0] / 2, letter[1] / 2)
    canvas.rotate(40)
    canvas.setFont("Helvetica-Bold", 96)
    try:
        canvas.setFillAlpha(0.16)
    except Exception:
        pass
    canvas.setFillColor(WATERMARK)
    canvas.drawCentredString(0, -25, "DRAFT")
    canvas.restoreState()


def _image_flowable(path: str) -> Image | None:
    try:
        with PILImage.open(path) as pil:
            w, h = pil.size
        scale = min(MAX_IMAGE_WIDTH / w, MAX_IMAGE_HEIGHT / h, 1.0)
        img = Image(path, width=w * scale, height=h * scale)
        img.hAlign = "CENTER"
        return img
    except Exception as e:
        print(f"  WARNING: could not embed image '{path}': {e}")
        return None


# ─── Cover ────────────────────────────────────────────────────────────────────
def _logo_flowables() -> list:
    """Real logo image if configured, else a drawn 'dfh architects' wordmark."""
    if config.FIRM_LOGO_PATH and os.path.exists(config.FIRM_LOGO_PATH):
        img = _image_flowable(config.FIRM_LOGO_PATH)
        if img:
            img.hAlign = "RIGHT"
            return [img]
    return [Paragraph("dfh", STYLE_LOGO_MAIN), Paragraph("architects", STYLE_LOGO_SUB)]


def _firm_block() -> list:
    return _logo_flowables() + [
        Spacer(1, 8),
        Paragraph(f"<b>{_escape(config.FIRM_NAME)}</b>", STYLE_FIRM),
        Paragraph(_escape(config.FIRM_PRINCIPAL), STYLE_FIRM),
        Paragraph(_escape(config.FIRM_ROLE), STYLE_FIRM),
        Paragraph(_escape(config.FIRM_EMAIL), STYLE_FIRM),
    ]


def _cover_story(project_name: str) -> list:
    tbl = Table(
        [
            [Paragraph("PRODUCT SELECTIONS FOR:", STYLE_COVER_LABEL),
             Paragraph(_escape(project_name), STYLE_COVER_VALUE)],
            [Paragraph("PREPARED BY:", STYLE_COVER_LABEL), _firm_block()],
        ],
        colWidths=[2.3 * inch, 4.35 * inch],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 1), (-1, 1), 64),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 1.3 * inch), tbl, PageBreak()]


# ─── Product page pieces ──────────────────────────────────────────────────────
def _key_desc_block(product) -> Table:
    """Description (left, navy) + boxed navy KEY code (right), one row per entry."""
    rows = [
        [Paragraph(_escape(e.description), STYLE_KEY_DESC),
         Paragraph(_escape(e.key), STYLE_CODE)]
        for e in product.entries
    ]
    block = Table(rows, colWidths=[3.2 * inch, 0.9 * inch], hAlign="RIGHT")
    block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("RIGHTPADDING", (0, 0), (0, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("BOX", (1, 0), (1, -1), 1.1, NAVY),
        ("INNERGRID", (1, 0), (1, -1), 1.1, NAVY),
        ("TOPPADDING", (1, 0), (1, -1), 5),
        ("BOTTOMPADDING", (1, 0), (1, -1), 5),
    ]))
    return block


def _brand_heading(info) -> list:
    brand = (info.manufacturer or info.product_name) if info else ""
    if not brand:
        return []
    out = [Spacer(1, 14), HRFlowable(width="100%", thickness=1, color=colors.black),
           Spacer(1, 4), Paragraph(_escape(brand), STYLE_BRAND)]
    if info.manufacturer and info.product_name and info.product_name != brand:
        out.append(Paragraph(_escape(info.product_name), STYLE_BRAND_SUB))
    out += [Spacer(1, 4), HRFlowable(width="100%", thickness=1, color=colors.black),
            Spacer(1, 10)]
    return out


def _field(label: str, value: str) -> list:
    if not value or not value.strip():
        return []
    return [Paragraph(label, STYLE_LABEL), Paragraph(_escape(value), STYLE_BODY)]


def _product_story(result: ProductResult) -> list:
    product = result.product

    header = _key_desc_block(product)
    header._product_group_id = product.group_id  # picked up by afterFlowable
    story: list = [header]

    # 1) Scheduled key with no source yet.
    if result.needs_owner_input:
        story.append(Paragraph("OWNER INPUT NEEDED", STYLE_OWNER))
        story.append(Paragraph(
            "No specification source has been provided for this item.",
            STYLE_OWNER_SUB,
        ))
        story.append(PageBreak())
        return story

    # 2) Extraction / AI failure.
    if result.error:
        story += _brand_heading(result.info)
        error_body = [
            Paragraph("Could not generate full product information", STYLE_LABEL),
            Paragraph(f"Source: {_escape(product.source_path)}", STYLE_ERROR),
            Paragraph(f"Reason: {_escape(result.error)}", STYLE_ERROR),
        ]
        box = Table([[error_body]], colWidths=[6.5 * inch])
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#8a1f11")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdeceb")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.extend([Spacer(1, 12), box, PageBreak()])
        return story

    # 3) Normal product page.
    info = result.info
    story += _brand_heading(info)
    if result.representative_image:
        img = _image_flowable(result.representative_image)
        if img:
            story.extend([img, Spacer(1, 12)])
    story += _field("Description", info.description)
    story += _field("Dimensions", info.dimensions)
    story += _field("Materials", info.materials)
    story += _field("Finishes", info.finishes)
    story += _field("Certifications", info.certifications)
    if info.important_specs:
        story.append(Paragraph("Important Specifications", STYLE_LABEL))
        for spec in info.important_specs:
            story.append(Paragraph(_escape(spec), STYLE_BULLET, bulletText="•"))
    story += _field("Installation Notes", info.installation_notes)
    story += _field("Care Notes", info.care_notes)
    story.append(PageBreak())
    return story


# ─── Table of contents ────────────────────────────────────────────────────────
def _toc_pages_needed(results: list[ProductResult]) -> int:
    total_rows = sum(len(r.product.entries) for r in results)
    return max(1, math.ceil(total_rows / TOC_ROWS_PER_PAGE))


def _toc_story(
    results: list[ProductResult], page_numbers: dict[str, int], toc_pages: int
) -> list:
    rows = [["KEY", "DESCRIPTION", "PG"]]
    for result in results:
        pg = page_numbers.get(result.product.group_id, "?")
        for entry in result.product.entries:
            rows.append([entry.key, entry.description, str(pg)])

    story: list = [Paragraph("TABLE OF CONTENTS", STYLE_TOC_TITLE)]
    for page_idx in range(toc_pages):
        chunk = rows[1:][page_idx * TOC_ROWS_PER_PAGE:(page_idx + 1) * TOC_ROWS_PER_PAGE]
        table = Table(
            [rows[0]] + chunk,
            colWidths=[0.9 * inch, 4.6 * inch, 0.7 * inch],
            repeatRows=1,
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(PageBreak())
    return story


def _toc_placeholder(toc_pages: int) -> list:
    story: list = []
    for _ in range(toc_pages):
        story.extend([Spacer(1, 1), PageBreak()])
    return story


# ─── Document assembly ────────────────────────────────────────────────────────
def _build_doc(target, story, project_name: str) -> "_BinderDoc":
    doc = _BinderDoc(
        target,
        pagesize=letter,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.95 * inch,  # leaves room for the two-line draft footer
        title="Interior Product Binder",
    )

    def on_first(canvas, _doc):
        _draw_watermark(canvas)   # DRAFT watermark on the cover only
        _draw_footer(canvas, project_name)

    def on_later(canvas, _doc):
        _draw_footer(canvas, project_name)

    doc.build(story, onFirstPage=on_first, onLaterPages=on_later)
    return doc


def build_binder(
    results: list[ProductResult],
    output_path: str,
    project_name: str,
    prepared_by: str = "",
) -> str:
    """Two-pass build: pass 1 discovers page numbers, pass 2 renders the real TOC.

    Returns the path actually written. If ``output_path`` is locked (e.g. the
    binder is open in a PDF viewer), a timestamped fallback file is written
    instead so a full run is never lost to a file lock.
    """
    toc_pages = _toc_pages_needed(results)
    product_stories = [_product_story(r) for r in results]

    def assemble(toc_story: list) -> list:
        story = _cover_story(project_name) + list(toc_story)
        for ps in product_stories:
            story.extend(ps)
        if story and isinstance(story[-1], PageBreak):
            story.pop()
        return story

    # Pass 1: placeholder TOC pages, harvest real page numbers.
    pass1 = _build_doc(io.BytesIO(), assemble(_toc_placeholder(toc_pages)), project_name)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    def write_pass2(target: str) -> None:
        product_stories[:] = [_product_story(r) for r in results]
        _build_doc(
            target, assemble(_toc_story(results, pass1.page_numbers, toc_pages)),
            project_name,
        )

    try:
        write_pass2(output_path)
        return output_path
    except PermissionError:
        base, ext = os.path.splitext(output_path)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = f"{base}_{stamp}{ext}"
        print(
            f"  WARNING: '{output_path}' is locked (open in another program?). "
            f"Writing to '{fallback}' instead."
        )
        write_pass2(fallback)
        return fallback
