"""Build the final binder PDF: cover page, table of contents, product sections."""

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
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.models import ProductResult

TOC_ROWS_PER_PAGE = 32  # keeps each TOC chunk safely on one page at 8pt rows
MAX_IMAGE_WIDTH = 3.6 * inch
MAX_IMAGE_HEIGHT = 3.0 * inch
NAVY = colors.HexColor("#2b3990")

_styles = getSampleStyleSheet()
STYLE_COVER_LABEL = ParagraphStyle(
    "CoverLabel", parent=_styles["Normal"], fontSize=12, spaceAfter=6,
    fontName="Helvetica-Bold",
)
STYLE_COVER_VALUE = ParagraphStyle(
    "CoverValue", parent=_styles["Normal"], fontSize=14, spaceAfter=24,
)
STYLE_HEADING = ParagraphStyle(
    "ProductHeading", parent=_styles["Heading1"], fontSize=16, spaceAfter=4,
)
STYLE_SUBHEADING = ParagraphStyle(
    "ProductSubheading", parent=_styles["Normal"], fontSize=10,
    textColor=colors.grey, spaceAfter=12,
)
STYLE_LABEL = ParagraphStyle(
    "FieldLabel", parent=_styles["Normal"], fontSize=11,
    fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2,
)
STYLE_BODY = ParagraphStyle(
    "FieldBody", parent=_styles["Normal"], fontSize=10, spaceAfter=4, leading=13,
)
STYLE_BULLET = ParagraphStyle(
    "FieldBullet", parent=STYLE_BODY, leftIndent=14, bulletIndent=4,
)
STYLE_ERROR = ParagraphStyle(
    "ErrorBody", parent=STYLE_BODY, textColor=colors.HexColor("#8a1f11"),
)
STYLE_TOC_TITLE = ParagraphStyle(
    "TocTitle", parent=_styles["Heading1"], fontSize=14, spaceAfter=12,
)
STYLE_KEY_BADGE = ParagraphStyle(
    "KeyBadge", parent=_styles["Normal"], fontSize=12, fontName="Helvetica-Bold",
    textColor=NAVY, alignment=1,  # centered
)


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
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _field(label: str, value: str) -> list:
    if not value or not value.strip():
        return []
    return [
        Paragraph(label, STYLE_LABEL),
        Paragraph(_escape(value), STYLE_BODY),
    ]


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


def _key_badges(product) -> Table:
    """Vertical stack of boxed keys, right-aligned, matching the reference binder."""
    rows = [[Paragraph(_escape(k), STYLE_KEY_BADGE)] for k in product.keys]
    badges = Table(rows, colWidths=[0.95 * inch], hAlign="RIGHT")
    badges.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, NAVY),
        ("INNERGRID", (0, 0), (-1, -1), 1, NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return badges


def _cover_story(project_name: str, prepared_by: str) -> list:
    today = datetime.date.today().strftime("%B %d, %Y")
    return [
        Spacer(1, 1.5 * inch),
        Paragraph("PRODUCT SELECTIONS FOR:", STYLE_COVER_LABEL),
        Paragraph(_escape(project_name), STYLE_COVER_VALUE),
        Spacer(1, 0.5 * inch),
        Paragraph("PREPARED BY:", STYLE_COVER_LABEL),
        Paragraph(_escape(prepared_by), STYLE_COVER_VALUE),
        Spacer(1, 2.5 * inch),
        Paragraph(today, STYLE_BODY),
        PageBreak(),
    ]


def _product_story(result: ProductResult) -> list:
    product = result.product
    info = result.info

    # Title on the left, boxed KEY badges on the top right (same row).
    title_text = (info.product_name if info and info.product_name
                  else " · ".join(product.keys))
    title = Paragraph(_escape(title_text), STYLE_HEADING)
    header = Table(
        [[title, _key_badges(product)]],
        colWidths=[4.55 * inch, 1.25 * inch],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    header._product_group_id = product.group_id  # picked up by afterFlowable
    story: list = [header]
    if product.combined_description:
        story.append(Paragraph(_escape(product.combined_description), STYLE_SUBHEADING))

    # Image first, so it always shares the page with the start of the text.
    if result.representative_image:
        img = _image_flowable(result.representative_image)
        if img:
            story.extend([Spacer(1, 6), img, Spacer(1, 12)])

    if result.error:
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
        story.extend([Spacer(1, 12), box])
    else:
        story += _field("Manufacturer", info.manufacturer)
        story += _field("Description", info.description)
        story += _field("Dimensions", info.dimensions)
        story += _field("Materials", info.materials)
        story += _field("Finishes", info.finishes)
        story += _field("Certifications", info.certifications)
        if info.important_specs:
            story.append(Paragraph("Important Specifications", STYLE_LABEL))
            for spec in info.important_specs:
                story.append(
                    Paragraph(_escape(spec), STYLE_BULLET, bulletText="•")
                )
        story += _field("Installation Notes", info.installation_notes)
        story += _field("Care Notes", info.care_notes)

    story.append(PageBreak())
    return story


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
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b3990")),
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


def _build_doc(target, story) -> "_BinderDoc":
    doc = _BinderDoc(
        target,
        pagesize=letter,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title="Interior Product Binder",
    )
    doc.build(story)
    return doc


def build_binder(
    results: list[ProductResult],
    output_path: str,
    project_name: str,
    prepared_by: str,
) -> str:
    """Two-pass build: pass 1 discovers page numbers, pass 2 renders the real TOC.

    Returns the path actually written. If ``output_path`` is locked (e.g. the
    binder is open in a PDF viewer), a timestamped fallback file is written
    instead so a full run is never lost to a file lock.
    """
    toc_pages = _toc_pages_needed(results)
    product_stories = [_product_story(r) for r in results]

    def assemble(toc_story: list) -> list:
        story = _cover_story(project_name, prepared_by) + list(toc_story)
        for ps in product_stories:
            story.extend(ps)
        # drop the trailing PageBreak so we don't emit a blank last page
        if story and isinstance(story[-1], PageBreak):
            story.pop()
        return story

    # Pass 1: placeholder TOC pages, harvest real page numbers.
    pass1 = _build_doc(io.BytesIO(), assemble(_toc_placeholder(toc_pages)))

    # Pass 2: real TOC with harvested page numbers, same page count. Flowables
    # can't be reused across builds, so rebuild the product stories each time.
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    def write_pass2(target: str) -> None:
        product_stories[:] = [_product_story(r) for r in results]
        _build_doc(
            target, assemble(_toc_story(results, pass1.page_numbers, toc_pages))
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
