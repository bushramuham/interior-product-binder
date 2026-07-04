"""Extract text and likely product images from a webpage."""

import io
import os
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image

import config
from src.models import ExtractedContent

_KEYWORDS = (
    "product", "chair", "table", "fixture", "finish", "material",
    "sofa", "lamp", "light", "cabinet", "sink", "vanity", "tile",
    "faucet", "hero", "main", "detail",
)
_SKIP_PATTERNS = ("logo", "icon", "sprite", "favicon", "pixel", "tracking",
                  "badge", "avatar", "button", "arrow", "spinner")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60] or "web"


def _score_image(src: str, alt: str, width: int, height: int) -> int:
    """Heuristic score: bigger + product-keyword-matching images win."""
    combined = f"{src} {alt}".lower()
    if any(p in combined for p in _SKIP_PATTERNS):
        return -1
    score = 0
    if width and height:
        if width < config.MIN_IMAGE_DIMENSION_PX or height < config.MIN_IMAGE_DIMENSION_PX:
            return -1
        score += min(width * height // 10000, 100)
    score += sum(10 for kw in _KEYWORDS if kw in combined)
    return score


def extract_url(url: str) -> ExtractedContent:
    """Download a page, extract its visible text and a few likely product images."""
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    try:
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        return ExtractedContent(error=f"Could not fetch URL '{url}': {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)[: config.MAX_TEXT_CHARS_TO_AI]

    # Rank <img> candidates.
    candidates = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        try:
            width = int(str(img.get("width", "0")).rstrip("px") or 0)
            height = int(str(img.get("height", "0")).rstrip("px") or 0)
        except ValueError:
            width = height = 0
        score = _score_image(src, img.get("alt") or "", width, height)
        if score >= 0:
            candidates.append((score, urljoin(url, src)))
    candidates.sort(key=lambda c: c[0], reverse=True)

    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
    base = _slug(urlsplit(url).path or urlsplit(url).netloc)
    image_paths = []
    for _, img_url in candidates:
        if len(image_paths) >= config.MAX_IMAGES_PER_PRODUCT:
            break
        try:
            img_resp = session.get(img_url, timeout=config.REQUEST_TIMEOUT_SECONDS)
            img_resp.raise_for_status()
            pil = Image.open(io.BytesIO(img_resp.content))
            if min(pil.size) < config.MIN_IMAGE_DIMENSION_PX:
                continue
            out_path = os.path.join(
                config.TEMP_IMAGE_DIR, f"{base}_{len(image_paths)}.png"
            )
            pil.convert("RGB").save(out_path, "PNG")
            image_paths.append(out_path)
        except Exception as e:
            print(f"  WARNING: skipping web image {img_url}: {e}")

    return ExtractedContent(text=text, image_paths=image_paths)
