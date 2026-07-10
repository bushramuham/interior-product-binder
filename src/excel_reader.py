"""Read an exported schedule .xlsx and group rows into Products by shared PATH."""

import os
from urllib.parse import urlsplit

from openpyxl import Workbook, load_workbook

from src.models import Product, ProductEntry

# Canonical schedule columns (order used when writing a new schedule).
SCHEDULE_HEADERS = ["KEY", "DESCRIPTION", "PG", "PATH", "DESCRIPTION2", "DESCRIPTION3"]

# Recognized header names (lowercased) -> canonical field
_HEADER_ALIASES = {
    "key": "key",
    "description": "description",
    "description2": "description2",
    "description3": "description3",
    "pg": "page_hint",
    "page": "page_hint",
    "path": "raw_path",
    "source": "raw_path",
}


def _normalize_source(path: str) -> tuple[str, str]:
    """Return (group_id, source_type) for a PATH cell value."""
    path = path.strip()
    lower = path.lower()
    if lower.startswith(("http://", "https://")):
        parts = urlsplit(path)
        group_id = f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path}"
        if parts.query:
            group_id += f"?{parts.query}"
        return group_id, "url"
    return os.path.normcase(os.path.normpath(path)), "pdf"


def save_schedule(rows: list[dict], path: str) -> None:
    """Write rows (dicts keyed by SCHEDULE_HEADERS) to an .xlsx schedule."""
    wb = Workbook()
    ws = wb.active
    ws.title = "MC Schedule by Keynote"
    ws.append(SCHEDULE_HEADERS)
    for row in rows:
        ws.append([str(row.get(h, "") or "") for h in SCHEDULE_HEADERS])
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)


def _map_headers(header_row) -> dict[int, str]:
    """Map column index -> canonical field name, case-insensitively."""
    mapping = {}
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        name = str(cell).strip().lower()
        if name in _HEADER_ALIASES:
            mapping[idx] = _HEADER_ALIASES[name]
    return mapping


def load_products(xlsx_path: str) -> list[Product]:
    """Load the schedule and return Products grouped by normalized PATH, in row order."""
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    rows = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration:
        wb.close()
        raise ValueError(f"Spreadsheet is empty: {xlsx_path}")

    columns = _map_headers(header_row)
    if "key" not in columns.values():
        wb.close()
        raise ValueError(
            f"Could not find the required KEY column in {xlsx_path}. "
            f"Found headers: {[str(c) for c in header_row if c is not None]}"
        )

    groups: dict[str, Product] = {}
    for row_num, row in enumerate(rows, start=2):
        values = {}
        for idx, fieldname in columns.items():
            cell = row[idx] if idx < len(row) else None
            values[fieldname] = str(cell).strip() if cell is not None else ""

        entry = ProductEntry(
            key=values.get("key", ""),
            description=values.get("description", ""),
            description2=values.get("description2", ""),
            description3=values.get("description3", ""),
            raw_path=values.get("raw_path", ""),
            page_hint=values.get("page_hint", ""),
        )

        if not entry.key:
            if any([entry.description, entry.raw_path]):
                print(f"  WARNING: skipping row {row_num} (missing KEY)")
            continue

        if entry.raw_path:
            group_id, source_type = _normalize_source(entry.raw_path)
        else:
            # A scheduled key with no source yet -> its own "owner input needed"
            # page; never grouped with other sourceless rows.
            group_id, source_type = f"__nosource__{row_num}", "none"

        if group_id not in groups:
            groups[group_id] = Product(
                group_id=group_id,
                source_path=entry.raw_path.strip(),
                source_type=source_type,
            )
        groups[group_id].entries.append(entry)

    wb.close()
    return list(groups.values())
