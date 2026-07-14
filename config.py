"""Central configuration constants for the interior product binder generator."""

import os
import sys

IS_FROZEN = bool(getattr(sys, "frozen", False))  # running as a PyInstaller exe

# Directory the app runs from: next to the .exe when frozen, repo root otherwise.
APP_DIR = (
    os.path.dirname(sys.executable) if IS_FROZEN
    else os.path.dirname(os.path.abspath(__file__))
)


def resource_path(rel: str) -> str:
    """Path to a bundled read-only resource (PyInstaller unpacks to _MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, rel)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(APP_DIR, rel)


ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 1500

MAX_IMAGES_PER_PRODUCT = 3
MAX_TEXT_CHARS_TO_AI = 15000
MIN_IMAGE_DIMENSION_PX = 80
MAX_AI_IMAGE_DIMENSION_PX = 1024
REQUEST_TIMEOUT_SECONDS = 10

# Writable dirs live next to the exe when frozen, in the repo otherwise.
TEMP_IMAGE_DIR = (
    os.path.join(APP_DIR, "temp", "extracted_images") if IS_FROZEN
    else "temp/extracted_images"
)
OUTPUT_DIR = os.path.join(APP_DIR, "output") if IS_FROZEN else "output"

# ─── Firm identity (DFH template) ────────────────────────────────────────────
# Shown on the cover "PREPARED BY" block and in the page footer.
FIRM_NAME = "DFH ARCHITECTS"
FIRM_PRINCIPAL = "Kara Block AIA"
FIRM_ROLE = "Principal"
FIRM_EMAIL = "email: block@dfhaia.com"
FIRM_LLP = "DFH ARCHITECTS LLP"
FIRM_LOGO_PATH = resource_path(os.path.join("assets", "dfh_logo.jpeg"))  # text logo drawn if absent
BINDER_TAG = "INTERIOR FFE"               # footer tag; " [DRAFT]" appended in draft mode

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "InteriorProductBinder/0.1 (proof-of-concept)"
)
