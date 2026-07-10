"""Central configuration constants for the interior product binder generator."""

ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 1500

MAX_IMAGES_PER_PRODUCT = 3
MAX_TEXT_CHARS_TO_AI = 15000
MIN_IMAGE_DIMENSION_PX = 80
MAX_AI_IMAGE_DIMENSION_PX = 1024
REQUEST_TIMEOUT_SECONDS = 10

TEMP_IMAGE_DIR = "temp/extracted_images"
OUTPUT_DIR = "output"

# ─── Firm identity (DFH template) ────────────────────────────────────────────
# Shown on the cover "PREPARED BY" block and in the page footer.
FIRM_NAME = "DFH ARCHITECTS"
FIRM_PRINCIPAL = "Kara Block AIA"
FIRM_ROLE = "Principal"
FIRM_EMAIL = "email: block@dfhaia.com"
FIRM_LLP = "DFH ARCHITECTS LLP"
FIRM_ADDRESS = "Los Angeles, CA"          # TODO: replace with the firm's real address
FIRM_LOGO_PATH = "assets/dfh_logo.png"    # optional real logo; a text logo is drawn if absent
BINDER_TAG = "INTERIOR FFE [DRAFT]"       # footer tag between project name and date

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "InteriorProductBinder/0.1 (proof-of-concept)"
)
