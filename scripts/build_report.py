"""Inline all images into the report so the submission is a single HTML file.

Reads the editable report (which references assets/*.png) and writes a
standalone copy with every image embedded as a base64 data URI.

    submission/Bushra_Muhammadi_Assignment07/Bushra_Muhammadi_Assignment07.html  (source)
        -> submission/Bushra_Muhammadi_Assignment07.html                          (standalone)

Run from the repo root:  python scripts/build_report.py
"""

import base64
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(REPO_ROOT, "submission", "Bushra_Muhammadi_Assignment07")
SOURCE = os.path.join(FOLDER, "Bushra_Muhammadi_Assignment07.html")
STANDALONE = os.path.join(REPO_ROOT, "submission", "Bushra_Muhammadi_Assignment07.html")


def _data_uri(rel_path: str) -> str:
    abs_path = os.path.join(FOLDER, rel_path)
    ext = os.path.splitext(rel_path)[1].lstrip(".").lower()
    media = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(abs_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{media};base64,{b64}"


def main() -> int:
    with open(SOURCE, "r", encoding="utf-8") as f:
        html = f.read()

    embedded = {"n": 0}

    def repl(match: re.Match) -> str:
        rel = match.group(2)
        if rel.startswith(("data:", "http://", "https://")):
            return match.group(0)
        embedded["n"] += 1
        return f'{match.group(1)}="{_data_uri(rel)}"'

    # Inline any src="..." / href="..." that points at a local image file.
    html = re.sub(
        r'(src|href)="([^"]+\.(?:png|jpg|jpeg|gif|svg))"', repl, html
    )

    with open(STANDALONE, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = os.path.getsize(STANDALONE) / (1024 * 1024)
    print(f"embedded {embedded['n']} image(s)")
    print(f"wrote {STANDALONE}  ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
