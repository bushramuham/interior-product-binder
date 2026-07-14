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

import fitz
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

import config
from src.models import ProductResult

TOC_ROWS_PER_PAGE = 32
MAX_IMAGE_WIDTH = 3.6 * inch
MAX_IMAGE_HEIGHT = 3.0 * inch

# ─── DFH template palette (sampled from the firm's own binder PDF) ────────────
NAVY = colors.HexColor("#25408f")        # KEY codes + descriptions
LOGO_GREEN = colors.HexColor("#8a9a3a")  # "architects" in the fallback text logo
CHARCOAL = colors.HexColor("#404040")    # fallback text logo, cover labels
WATERMARK = colors.HexColor("#cdcdcd")   # diagonal DRAFT watermark
DRAFT_RED = colors.HexColor("#ec1c24")   # "DRAFT ... NOT FOR CONSTRUCTION" banner
DRAFT_RED_ALPHA = 0.5                    # half-tone (screened) red
MARGIN = 0.5 * inch                      # matches the firm's page margins

# RGB (0-1) equivalents for PyMuPDF stamping onto embedded source pages.
NAVY_RGB = (0x25 / 255, 0x40 / 255, 0x8f / 255)
RED_HALF_RGB = (0.925, 0.545, 0.55)      # solid look of the half-tone draft red
BLACK_RGB = (0, 0, 0)

# Key/description block geometry (shared so the owner note lines up under it).
KEY_DESC_COL = 3.2 * inch                # description column width
CODE_COL = 1.05 * inch                   # boxed KEY code column width
DESC_RPAD = 10                           # description right padding before the box

_styles = getSampleStyleSheet()
STYLE_COVER_LABEL = ParagraphStyle(
    "CoverLabel", parent=_styles["Normal"], fontSize=14, fontName="Helvetica-Bold",
    textColor=colors.black,
)
STYLE_COVER_VALUE = ParagraphStyle(
    "CoverValue", parent=_styles["Normal"], fontSize=14, leading=17, textColor=colors.black,
    alignment=0,
)
STYLE_FIRM_NAME = ParagraphStyle(
    "FirmName", parent=_styles["Normal"], fontSize=14, leading=17, textColor=colors.black, alignment=2,
)
STYLE_FIRM = ParagraphStyle(
    "Firm", parent=_styles["Normal"], fontSize=12, leading=15, textColor=colors.black, alignment=2,
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
    "KeyDesc", parent=_styles["Normal"], fontSize=12, leading=14,
    textColor=NAVY, alignment=2,  # right, sits left of the code box
)
STYLE_CODE = ParagraphStyle(
    "Code", parent=_styles["Normal"], fontSize=26, leading=30,
    fontName="Helvetica", textColor=NAVY, alignment=1,
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
# Same font and size as the schedule description, just bold red; sits directly
# under the description in the key block.
STYLE_OWNER = ParagraphStyle(
    "Owner", parent=STYLE_KEY_DESC, fontName="Helvetica-Bold",
    textColor=colors.HexColor("#c00000"), spaceBefore=3,
    rightIndent=CODE_COL + DESC_RPAD,  # right edge aligns under the description
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


def _escape(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─── PyMuPDF stamping (footer on every page, KEY badges on source pages) ──────
def _fitz_right(page, x_right, y, text, size, color, bold=False):
    font = "hebo" if bold else "helv"
    tw = fitz.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text((x_right - tw, y), text, fontname=font, fontsize=size, color=color)


def _fitz_center(page, x_center, y, text, size, color, bold=False):
    font = "hebo" if bold else "helv"
    tw = fitz.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text((x_center - tw / 2, y), text, fontname=font, fontsize=size, color=color)


def _stamp_footer(page, project_name: str, page_no: int | None, draft: bool = True) -> None:
    """Firm/project/page footer; in draft mode also the half-tone red draft banner."""
    w, h = page.rect.width, page.rect.height
    short = project_name.split(" - ")[0].strip() or project_name
    if draft:
        _fitz_center(page, w / 2, h - 44, f"DRAFT {_date_short()} - NOT FOR CONSTRUCTION",
                     14, RED_HALF_RGB, bold=True)
    page.insert_text((MARGIN, h - 24), config.FIRM_LLP, fontname="helv", fontsize=10,
                     color=BLACK_RGB)
    tag = config.BINDER_TAG + (" [DRAFT]" if draft else "")
    right = w - MARGIN
    if page_no is not None:
        _fitz_right(page, right, h - 23, str(page_no), 12, BLACK_RGB)
        right -= 0.45 * inch
    _fitz_right(page, right, h - 24, f"{short} - {tag} - {_date_long()}",
                10, BLACK_RGB)


def _stamp_badges(page, product) -> None:
    """Stamp the navy KEY code boxes + descriptions on a source page's top-right."""
    w = page.rect.width
    right = w - MARGIN
    bw, bh, top = CODE_COL, 41, MARGIN
    for i, entry in enumerate(product.entries):
        y0 = top + i * bh
        box = fitz.Rect(right - bw, y0, right, y0 + bh)
        page.draw_rect(box, color=NAVY_RGB, width=1.1)
        _fitz_center(page, box.x0 + bw / 2, y0 + bh / 2 + 9, entry.key, 26, NAVY_RGB)
        if entry.description:
            _fitz_right(page, right - bw - DESC_RPAD, y0 + bh / 2 + 4,
                        entry.description, 12, NAVY_RGB)


WATERMARK_RGB = (0xcd / 255, 0xcd / 255, 0xcd / 255)


def _stamp_watermark(page) -> None:
    """Diagonal DRAFT across the page, stamped AFTER the content so it sits on
    the top layer (in front of the logo)."""
    w, h = page.rect.width, page.rect.height
    size = 144
    tw = fitz.get_text_length("DRAFT", fontname="helv", fontsize=size)
    center = fitz.Point(w / 2, h / 2)
    # Baseline start so the text is centered on the page before rotation.
    origin = fitz.Point(w / 2 - tw / 2, h / 2 + 0.35 * size)
    page.insert_text(origin, "DRAFT", fontname="helv", fontsize=size,
                     color=WATERMARK_RGB, fill_opacity=0.35,
                     morph=(center, fitz.Matrix(1, 1).prerotate(45)))


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
    """The firm's logo image if present, else a drawn 'dfh architects' wordmark."""
    path = config.FIRM_LOGO_PATH
    if path and os.path.exists(path):
        try:
            with PILImage.open(path) as pil:
                w, h = pil.size
            width = 2.2 * inch
            img = Image(path, width=width, height=width * h / w)
            img.hAlign = "RIGHT"
            return [img]
        except Exception as e:
            print(f"  WARNING: could not load logo '{path}': {e}")
    return [Paragraph("dfh", STYLE_LOGO_MAIN), Paragraph("architects", STYLE_LOGO_SUB)]


def _firm_block() -> list:
    return _logo_flowables() + [
        Spacer(1, 10),
        Paragraph(_escape(config.FIRM_NAME), STYLE_FIRM_NAME),
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
        colWidths=[3.0 * inch, 4.5 * inch],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 1), (-1, 1), 80),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [tbl, PageBreak()]


# ─── Product page pieces ──────────────────────────────────────────────────────
def _key_desc_block(product) -> Table:
    """Description (left, navy) + boxed navy KEY code (right), one row per entry."""
    rows = [
        [Paragraph(_escape(e.description), STYLE_KEY_DESC),
         Paragraph(_escape(e.key), STYLE_CODE)]
        for e in product.entries
    ]
    block = Table(rows, colWidths=[KEY_DESC_COL, CODE_COL], hAlign="RIGHT")
    block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("RIGHTPADDING", (0, 0), (0, -1), DESC_RPAD),
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
    out = [Spacer(1, 14), Paragraph(_escape(brand), STYLE_BRAND)]
    if info.manufacturer and info.product_name and info.product_name != brand:
        out.append(Paragraph(_escape(info.product_name), STYLE_BRAND_SUB))
    out += [Spacer(1, 10)]
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
        story.append(Paragraph("OWNER INPUT NEEDED.", STYLE_OWNER))
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
    rows = [["KEY", "DESCRIPTION", "P#"]]
    for result in results:
        pg = page_numbers.get(result.product.group_id)
        pg_str = str(pg) if isinstance(pg, int) else "?"
        for entry in result.product.entries:
            rows.append([entry.key, entry.description, pg_str])

    story: list = [Paragraph("TABLE OF CONTENTS", STYLE_TOC_TITLE)]
    for page_idx in range(toc_pages):
        chunk = rows[1:][page_idx * TOC_ROWS_PER_PAGE:(page_idx + 1) * TOC_ROWS_PER_PAGE]
        table = Table(
            [rows[0]] + chunk,
            colWidths=[0.9 * inch, 5.9 * inch, 0.7 * inch],
            repeatRows=1,
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(PageBreak())
    return story


def _add_toc_links(binder, toc_pages: int, key_to_index: dict[str, int]) -> None:
    """Turn each TOC row into a clickable GOTO link to its product page."""
    key_col_max_x = MARGIN + 0.9 * inch + 10   # KEY column width in the TOC table
    for pi in range(1, min(toc_pages + 1, binder.page_count)):
        page = binder[pi]
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            target = key_to_index.get(word)
            if target is None or x0 > key_col_max_x:
                continue
            page.insert_link({
                "kind": fitz.LINK_GOTO,
                "from": fitz.Rect(MARGIN, y0 - 2, page.rect.width - MARGIN, y1 + 2),
                "page": target,
                "to": fitz.Point(0, 0),
            })


# ─── Document assembly ────────────────────────────────────────────────────────
def _render_story_pdf(story: list) -> bytes:
    """Render a flowable story to PDF bytes with no footer (stamped later by fitz)."""
    if story and isinstance(story[-1], PageBreak):
        story = story[:-1]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=0.85 * inch,  # clears the stamped footer/banner
        title="Interior Product Binder",
    )
    doc.build(story)
    return buf.getvalue()


def _open_product_doc(result: ProductResult):
    """Return (fitz_doc, kind) for a product: 'pdf' embeds the source verbatim,
    'rebuilt' is a ReportLab page for URL / owner / error products."""
    src = result.source_pdf_path
    if src and not result.error and not result.needs_owner_input:
        try:
            doc = fitz.open(src)
            if doc.is_pdf and doc.page_count > 0:
                return doc, "pdf"
            doc.close()
        except Exception as e:
            print(f"  WARNING: could not open source PDF '{src}': {e}")
            result.error = f"Could not open source PDF: {os.path.basename(src)}"
    return fitz.open("pdf", _render_story_pdf(_product_story(result))), "rebuilt"


FOOTER_ZONE = 0.85 * inch   # bottom band reserved for the banner + footer line
BADGE_ROW_H = 41            # height of one KEY badge row (matches _stamp_badges)
HEADER_GAP = 12             # gap between the badge block and the embedded page


def _embed_source_page(binder, src, pno: int, product, first: bool) -> None:
    """Add one binder page holding a source page scaled (aspect preserved) into
    the zone between the KEY badge header and the footer band — no overlap."""
    page = binder.new_page(width=letter[0], height=letter[1])
    w, h = page.rect.width, page.rect.height
    header_h = (MARGIN + BADGE_ROW_H * len(product.entries) + HEADER_GAP
                if first else MARGIN)
    zone = fitz.Rect(MARGIN, header_h, w - MARGIN, h - FOOTER_ZONE)

    sr = src[pno].rect
    scale = min(zone.width / sr.width, zone.height / sr.height)
    dw, dh = sr.width * scale, sr.height * scale
    x0 = zone.x0 + (zone.width - dw) / 2   # centered horizontally
    y0 = zone.y0                            # top-aligned under the header
    page.show_pdf_page(fitz.Rect(x0, y0, x0 + dw, y0 + dh), src, pno)
    if first:
        _stamp_badges(page, product)


def build_binder(
    results: list[ProductResult],
    output_path: str,
    project_name: str,
    prepared_by: str = "",
    draft: bool = True,
) -> str:
    """Assemble the binder with PyMuPDF: cover + TOC + one entry per product.

    PDF-sourced products are embedded verbatim, uniformly scaled to fit
    between the KEY badge header and the footer band (never overlapping
    either); URL / owner / error products are rebuilt pages. With ``draft``
    (default) the cover carries the diagonal DRAFT watermark and every page
    gets the red "DRAFT ... NOT FOR CONSTRUCTION" line and a "[DRAFT]" footer
    tag; ``draft=False`` removes all draft marks. Returns the path actually
    written (a timestamped fallback if the target is locked).
    """
    toc_pages = _toc_pages_needed(results)
    cover = fitz.open("pdf", _render_story_pdf(_cover_story(project_name)))

    # Prepare each product's pages and its printed start page number.
    entries = [dict(zip(("doc", "kind"), _open_product_doc(r)), result=r) for r in results]
    printed = 1 + toc_pages  # cover = page 0 (unnumbered); TOC = 1..toc_pages
    for e in entries:
        e["start"] = printed
        printed += e["doc"].page_count
    page_numbers = {e["result"].product.group_id: e["start"] for e in entries}

    toc = fitz.open("pdf", _render_story_pdf(_toc_story(results, page_numbers, toc_pages)))

    binder = fitz.open()
    binder.insert_pdf(cover)
    binder.insert_pdf(toc)
    while binder.page_count - 1 < toc_pages:      # keep TOC exactly toc_pages long
        binder.new_page(width=letter[0], height=letter[1])
    while binder.page_count - 1 > toc_pages:
        binder.delete_page(binder.page_count - 1)

    for e in entries:
        if e["kind"] == "pdf":
            src = e["doc"]
            for pno in range(src.page_count):
                _embed_source_page(binder, src, pno, e["result"].product,
                                   first=(pno == 0))
        else:
            binder.insert_pdf(e["doc"])

    for i in range(binder.page_count):
        _stamp_footer(binder[i], project_name, page_no=(None if i == 0 else i),
                      draft=draft)
    if draft:
        _stamp_watermark(binder[0])   # after content -> top layer, over the logo

    # Make each TOC row a clickable link to its product's first page.
    # Printed page numbers equal binder page indexes (cover is unnumbered 0).
    key_to_index = {
        entry.key: e["start"]
        for e in entries for entry in e["result"].product.entries
    }
    _add_toc_links(binder, toc_pages, key_to_index)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    try:
        binder.save(output_path, deflate=True, garbage=3)
        return output_path
    except Exception:
        base, ext = os.path.splitext(output_path)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = f"{base}_{stamp}{ext}"
        print(f"  WARNING: '{output_path}' is locked (open in another program?). "
              f"Writing to '{fallback}' instead.")
        binder.save(fallback, deflate=True, garbage=3)
        return fallback
