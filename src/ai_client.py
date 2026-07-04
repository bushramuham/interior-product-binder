"""Anthropic API wrapper: forced tool-use extraction with prompt caching."""

import base64
import io

import anthropic
from PIL import Image

import config
from src.models import ExtractedContent, Product, ProductInfo

SYSTEM_PROMPT = """You are an architectural interior product binder assistant working for an \
interior architecture firm. You receive raw product information extracted from manufacturer \
spec sheets (PDF cut sheets) or product webpages, and you extract the information an interior \
designer or architect needs when assembling a product selections binder for a construction \
project.

You will be given:
- One or more product KEYS from the project's finish/fixture schedule (e.g. "U-36", "CH-01"). \
Several keys may share one spec sheet when a single manufacturer document covers multiple \
scheduled items (for example a vanity cabinet, its countertop, and its sink sold as one unit).
- Short schedule descriptions written by the design team (e.g. "BATHROOM VANITY CABINET - 60-IN").
- The raw text extracted from the source document or webpage. This text can be noisy: it may \
contain navigation menus, legal boilerplate, unrelated products, page headers/footers, or \
OCR-like artifacts. Focus only on the product(s) matching the keys and descriptions.
- Optionally, one or more images extracted from the source, which may show the product, its \
dimensioned drawings, or finish options.

Extract the following, always via the extract_product_info tool:
- product_name: the manufacturer's marketed name of the product. Prefer the official model/series \
name over the schedule description.
- manufacturer: the brand or manufacturer name.
- description: 2-4 professional sentences summarizing what the product is, suitable for a client- \
facing binder. Neutral tone, no marketing superlatives.
- dimensions: overall dimensions with units as stated in the source (width x depth x height where \
available). Include multiple size options only if the schedule description implies a specific one \
is unclear.
- materials: primary materials of construction.
- finishes: available or specified finishes/colors.
- certifications: any listed certifications, ratings, or compliance standards (UL, ADA, \
GREENGUARD, WaterSense, etc.).
- installation_notes: concise notes relevant to installation (mounting type, clearances, rough-in \
requirements, required hardware).
- care_notes: cleaning/maintenance guidance if stated.
- important_specs: a short list of additional specification bullet points useful to a designer \
(weight capacity, electrical ratings, water consumption, lead times, model numbers, etc.), each \
as one concise string.

Rules:
- Do not invent information. Only report what is present in the provided text or clearly visible \
in the provided images.
- If a field's information is missing from the source, return an empty string for it (or an empty \
list for important_specs). Never guess.
- Keep every field concise and professional; this is a technical reference binder, not marketing \
copy.
- If the source text covers multiple products, extract only the product(s) matching the given \
keys and schedule descriptions.
- Normalize whitespace; do not include raw artifacts like navigation text, cookie notices, or \
page numbers.
"""

EXTRACT_PRODUCT_INFO_TOOL = {
    "name": "extract_product_info",
    "description": (
        "Record the structured interior product information extracted from the "
        "provided source text and images."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "product_name": {"type": "string"},
            "manufacturer": {"type": "string"},
            "description": {"type": "string"},
            "dimensions": {"type": "string"},
            "materials": {"type": "string"},
            "finishes": {"type": "string"},
            "certifications": {"type": "string"},
            "installation_notes": {"type": "string"},
            "care_notes": {"type": "string"},
            "important_specs": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "product_name", "manufacturer", "description", "dimensions",
            "materials", "finishes", "certifications", "installation_notes",
            "care_notes", "important_specs",
        ],
    },
}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


def _image_block(path: str) -> dict | None:
    """Downscale + JPEG-encode an image file into an API content block."""
    try:
        pil = Image.open(path).convert("RGB")
        pil.thumbnail(
            (config.MAX_AI_IMAGE_DIMENSION_PX, config.MAX_AI_IMAGE_DIMENSION_PX)
        )
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=85)
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(buf.getvalue()).decode("ascii"),
            },
        }
    except Exception as e:
        print(f"  WARNING: could not prepare image '{path}' for AI: {e}")
        return None


def extract_product_info(
    product: Product, extracted: ExtractedContent
) -> tuple[ProductInfo | None, str | None]:
    """Call Claude to structure the extracted content. Returns (info, error)."""
    user_text = (
        f"Product keys: {', '.join(product.keys)}\n"
        f"Schedule descriptions: {product.combined_description}\n\n"
        f"Extracted source text:\n{extracted.text or '(no text could be extracted)'}"
    )
    content: list[dict] = [{"type": "text", "text": user_text}]
    for img_path in extracted.image_paths[: config.MAX_IMAGES_PER_PRODUCT]:
        block = _image_block(img_path)
        if block:
            content.append(block)

    try:
        response = _get_client().messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.MAX_OUTPUT_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[EXTRACT_PRODUCT_INFO_TOOL],
            tool_choice={"type": "tool", "name": "extract_product_info"},
            messages=[{"role": "user", "content": content}],
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        info = ProductInfo(**tool_use.input)
        return info, None
    except StopIteration:
        return None, "AI response contained no tool call"
    except (TypeError, KeyError) as e:
        return None, f"AI returned unexpected fields: {e}"
    except anthropic.APIError as e:
        return None, f"AI API error: {e}"
    except Exception as e:
        return None, f"AI extraction failed: {e}"
