#!/usr/bin/env python3
"""
Daily Clue Cards - Instagram Automation Pipeline

Generates a daily word guessing game as a 2-image carousel:
- Slide 1: 3 clue words with "Guess the Word!" header
- Slide 2: The answer reveal

Uses Gemini AI to generate words and clues, Pillow for image creation,
and Instagram Graph API for carousel publishing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Environment & Configuration
# ---------------------------------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
BRAND_NAME = os.getenv("BRAND_NAME", "dailycluecards")
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", f"@{BRAND_NAME}")

# Gemini model configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MODELS_TO_TRY = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]
RETRY_ON_503_MAX = 3
RETRY_ON_503_DELAY = 45

# Duplicate prevention
WORD_HISTORY_SIZE = 60
WORD_HISTORY_PATH = Path("word_history.json")
DUPLICATE_CONTENT_RETRIES = 5

# Image dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350  # 4:5 aspect ratio for feed

# Output paths
OUTPUT_CLUE_IMAGE = Path("final_clue.jpg")
OUTPUT_ANSWER_IMAGE = Path("final_answer.jpg")

# Design colors (RGB)
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (230, 57, 70)       # #E63946
COLOR_YELLOW = (255, 209, 102)  # #FFD166
COLOR_TEXT = (43, 45, 66)       # #2B2D42
COLOR_LIGHT_GRAY = (200, 200, 200)

# Typography sizes
HEADER_FONT_SIZE = 72
CLUE_FONT_SIZE = 48
ANSWER_FONT_SIZE = 80
INSTRUCTION_FONT_SIZE = 32
WATERMARK_FONT_SIZE = 28

# Instagram API
GRAPH_API_BASE = "https://graph.facebook.com/v26.0"
INSTAGRAM_LOGIN_API_BASE = "https://graph.instagram.com/v23.0"
CONTAINER_POLL_INTERVAL = 5
CONTAINER_POLL_TIMEOUT = 120

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema for Gemini AI
# ---------------------------------------------------------------------------

CONTENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "word": {
            "type": "string",
            "description": (
                "A simple, common everyday object in English. Single word, lowercase. "
                "Examples: chair, pen, comb, umbrella, clock, pillow, mirror, lamp, book, phone."
            ),
        },
        "clues": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
            "description": (
                "Exactly 3 one-word clues that hint at the answer. Each clue should be "
                "a single word association. Not too obvious, not too obscure. "
                "Example for 'chair': sit, legs, furniture"
            ),
        },
        "caption": {
            "type": "string",
            "description": (
                "Engaging Instagram caption for the post. 2-3 short paragraphs. "
                "Include a hook, encourage engagement (comments with guesses), "
                "and a call to action. Use some emojis sparingly."
            ),
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 15,
            "maxItems": 15,
            "description": (
                "Exactly 15 relevant hashtags, lowercase, without # prefix. "
                "Mix of popular and niche tags related to word games, puzzles, brain teasers."
            ),
        },
    },
    "required": ["word", "clues", "caption", "hashtags"],
}

# ---------------------------------------------------------------------------
# System Prompt for Gemini
# ---------------------------------------------------------------------------

GEMINI_SYSTEM_PROMPT = f"""You are the creative director for @{BRAND_NAME} — an Instagram account
that posts daily word guessing games where followers try to guess a word from 3 clues.

Generate ONE unique daily clue card that includes:
- A simple, common everyday object as the answer word
- 3 single-word clues that hint at the answer

Rules for the WORD:
- Must be a tangible, everyday object (NOT abstract concepts)
- Single English word, lowercase
- Common items everyone knows: household items, office supplies, kitchen items, personal items
- Good examples: chair, pen, comb, umbrella, clock, pillow, mirror, lamp, book, phone, keys, wallet, brush, cup, plate, fork, spoon, towel, soap, bottle, bag, hat, shoe, belt, watch, ring, glasses, door, window, table, bed, couch, desk, shelf, carpet, blanket, candle, vase, plant

Rules for the CLUES:
- Exactly 3 clues, each a single word
- Should be word associations that hint at the answer
- Balance difficulty: not too easy, not too hard
- Avoid direct synonyms or parts of the word itself
- Make people think for a moment before getting it

Rules for the CAPTION:
- Start with an engaging hook
- Encourage followers to comment their guess before swiping
- Keep it fun and playful
- Use 2-4 emojis maximum
- End with "Swipe to see the answer!" or similar

Rules for HASHTAGS:
- Exactly 15 hashtags
- All lowercase, no # symbol
- Mix of: wordgames, puzzle, brainteaser, guesstheword, dailychallenge, etc.

Output ONLY valid JSON matching the schema — no markdown, no commentary.
"""

# ---------------------------------------------------------------------------
# Placeholder Detection
# ---------------------------------------------------------------------------

PLACEHOLDER_MARKERS = ("your_", "changeme", "replace_me", "xxx", "example")


def _looks_like_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def validate_env() -> None:
    """Validate required environment variables."""
    required = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "INSTAGRAM_ACCESS_TOKEN": INSTAGRAM_ACCESS_TOKEN,
        "INSTAGRAM_ACCOUNT_ID": INSTAGRAM_ACCOUNT_ID,
    }
    
    missing = []
    placeholders = []
    
    for name, value in required.items():
        if not value:
            missing.append(name)
        elif _looks_like_placeholder(value):
            placeholders.append(name)
    
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
    if placeholders:
        raise EnvironmentError(f"Placeholder values detected: {', '.join(placeholders)}")
    
    logger.info("Environment validation passed")


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class ClueContent:
    """Data model for a daily clue card."""
    word: str
    clues: list[str]
    caption: str
    hashtags: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClueContent:
        """Create ClueContent from AI-generated dict with validation."""
        word = data.get("word", "").strip().lower()
        if not word or not word.isalpha():
            raise ValueError(f"Invalid word: {word!r}")
        
        clues = data.get("clues", [])
        if not isinstance(clues, list) or len(clues) != 3:
            raise ValueError(f"Expected exactly 3 clues, got {len(clues) if isinstance(clues, list) else 'non-list'}")
        clues = [str(c).strip().upper() for c in clues]
        
        hashtags = [_normalize_hashtag(tag) for tag in data.get("hashtags", [])]
        if len(hashtags) != 15:
            raise ValueError(f"Expected 15 hashtags, got {len(hashtags)}")
        
        caption = data.get("caption", "").strip()
        if not caption:
            raise ValueError("Caption cannot be empty")
        
        return cls(word=word, clues=clues, caption=caption, hashtags=hashtags)

    def full_caption(self) -> str:
        """Return caption with hashtags appended."""
        tags = " ".join(f"#{tag}" for tag in self.hashtags)
        return f"{self.caption}\n\n{tags}"


def _normalize_hashtag(tag: str) -> str:
    """Normalize a hashtag: lowercase, no # prefix, alphanumeric only."""
    tag = tag.strip().lower().lstrip("#")
    return re.sub(r"[^a-z0-9]", "", tag)


# ---------------------------------------------------------------------------
# Word History (Duplicate Prevention)
# ---------------------------------------------------------------------------

def load_word_history() -> list[dict[str, str]]:
    """Load the list of recently published words."""
    if not WORD_HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(WORD_HISTORY_PATH.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        if isinstance(entries, list):
            return entries[-WORD_HISTORY_SIZE:]
    except (OSError, json.JSONDecodeError, TypeError):
        logger.warning("Word history file unreadable — starting fresh")
    return []


def save_word_history(entries: list[dict[str, str]]) -> None:
    """Save the word history to disk."""
    trimmed = entries[-WORD_HISTORY_SIZE:]
    WORD_HISTORY_PATH.write_text(
        json.dumps({"entries": trimmed}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def is_duplicate_word(word: str, history: list[dict[str, str]]) -> bool:
    """Check if word was recently published."""
    word_lower = word.strip().lower()
    for entry in history:
        if entry.get("word", "").strip().lower() == word_lower:
            return True
    return False


def record_published_word(content: ClueContent) -> None:
    """Add word to history after successful publish."""
    history = load_word_history()
    history.append({
        "word": content.word,
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    save_word_history(history)
    logger.info("Recorded word '%s' to history", content.word)


# ---------------------------------------------------------------------------
# Gemini AI Content Generation
# ---------------------------------------------------------------------------

def _gemini_models_to_try() -> list[str]:
    """Return ordered list of models to try."""
    primary = GEMINI_MODEL
    models = [primary] if primary else []
    for m in MODELS_TO_TRY:
        if m not in models:
            models.append(m)
    return models


def build_gemini_prompt(history: list[dict[str, str]], *, duplicate_retry: bool = False) -> str:
    """Build the prompt with banned word list."""
    prompt = GEMINI_SYSTEM_PROMPT
    if history:
        prompt += f"\n\nRecently published — DO NOT REUSE any of these {len(history)} words:\n"
        for entry in history:
            prompt += f"- {entry.get('word')}\n"
        prompt += "\nPick a completely different word not on this list."
    if duplicate_retry:
        prompt += (
            "\n\nYour previous answer duplicated a banned word. "
            "Generate something entirely new that is NOT on the banned list."
        )
    return prompt


def _call_gemini_for_content(prompt: str) -> dict[str, Any]:
    """Call Gemini API and return parsed JSON response."""
    try:
        import google.genai as genai
        from google.genai import types
    except ImportError:
        raise ImportError("google-genai package required. Install with: pip install google-genai")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    config = types.GenerateContentConfig(
        temperature=0.9,
        response_mime_type="application/json",
        response_schema=CONTENT_JSON_SCHEMA,
    )
    
    for model in _gemini_models_to_try():
        for retry_attempt in range(RETRY_ON_503_MAX + 1):
            try:
                logger.info("Trying model %s (attempt %d)", model, retry_attempt + 1)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                
                if not response.text:
                    logger.warning("Empty response from %s", model)
                    break
                
                data = json.loads(response.text)
                logger.info("Successfully generated content with %s", model)
                return data
                
            except genai.errors.ServerError as exc:
                error_str = str(exc)
                is_503 = "503" in error_str or "UNAVAILABLE" in error_str
                if is_503 and retry_attempt < RETRY_ON_503_MAX:
                    logger.warning(
                        "Model %s returned 503 (attempt %d/%d). Waiting %ds...",
                        model, retry_attempt + 1, RETRY_ON_503_MAX, RETRY_ON_503_DELAY
                    )
                    time.sleep(RETRY_ON_503_DELAY)
                    continue
                logger.warning("Server error with %s: %s", model, exc)
                break
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON from %s: %s", model, exc)
                break
            except Exception as exc:
                logger.warning("Error with %s: %s", model, exc)
                break
    
    raise RuntimeError("All Gemini models failed to generate content")


def generate_content() -> ClueContent:
    """Generate clue content using Gemini AI."""
    history = load_word_history()
    
    for attempt in range(DUPLICATE_CONTENT_RETRIES + 1):
        duplicate_retry = attempt > 0
        prompt = build_gemini_prompt(history, duplicate_retry=duplicate_retry)
        
        data = _call_gemini_for_content(prompt)
        content = ClueContent.from_dict(data)
        
        if is_duplicate_word(content.word, history):
            logger.warning(
                "Duplicate word '%s' (attempt %d/%d)",
                content.word, attempt + 1, DUPLICATE_CONTENT_RETRIES + 1
            )
            continue
        
        logger.info("Generated content: word='%s', clues=%s", content.word, content.clues)
        return content
    
    raise RuntimeError("Failed to generate non-duplicate content after retries")


# ---------------------------------------------------------------------------
# Image Generation (Pillow)
# ---------------------------------------------------------------------------

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font with fallback chain."""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    if bold:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf", 
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ] + font_paths
    
    for path in font_paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    
    logger.warning("No system fonts found, using default")
    return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _get_text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Get text width and height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def create_clue_image(content: ClueContent) -> Path:
    """Create the clue card image (Slide 1)."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # Load fonts
    font_header = _load_font(HEADER_FONT_SIZE, bold=True)
    font_clue = _load_font(CLUE_FONT_SIZE, bold=True)
    font_instruction = _load_font(INSTRUCTION_FONT_SIZE)
    font_watermark = _load_font(WATERMARK_FONT_SIZE)
    
    # Header: "GUESS THE WORD!"
    header_text = "GUESS THE WORD!"
    header_w, header_h = _get_text_bbox(draw, header_text, font_header)
    header_x = (CANVAS_WIDTH - header_w) // 2
    header_y = 180
    draw.text((header_x, header_y), header_text, font=font_header, fill=COLOR_RED)
    
    # Clue badges
    badge_width = 700
    badge_height = 100
    badge_radius = 20
    badge_x = (CANVAS_WIDTH - badge_width) // 2
    badge_start_y = 420
    badge_spacing = 140
    
    for i, clue in enumerate(content.clues):
        badge_y = badge_start_y + (i * badge_spacing)
        
        # Draw yellow badge
        _draw_rounded_rect(
            draw,
            (badge_x, badge_y, badge_x + badge_width, badge_y + badge_height),
            radius=badge_radius,
            fill=COLOR_YELLOW,
        )
        
        # Draw clue text centered in badge
        clue_w, clue_h = _get_text_bbox(draw, clue, font_clue)
        clue_x = badge_x + (badge_width - clue_w) // 2
        clue_y = badge_y + (badge_height - clue_h) // 2
        draw.text((clue_x, clue_y), clue, font=font_clue, fill=COLOR_TEXT)
    
    # Instruction: "Swipe to see the answer →"
    instruction_text = "Swipe to see the answer →"
    inst_w, inst_h = _get_text_bbox(draw, instruction_text, font_instruction)
    inst_x = (CANVAS_WIDTH - inst_w) // 2
    inst_y = 1050
    draw.text((inst_x, inst_y), instruction_text, font=font_instruction, fill=COLOR_LIGHT_GRAY)
    
    # Watermark
    wm_w, wm_h = _get_text_bbox(draw, WATERMARK_TEXT, font_watermark)
    wm_x = (CANVAS_WIDTH - wm_w) // 2
    wm_y = CANVAS_HEIGHT - 100
    draw.text((wm_x, wm_y), WATERMARK_TEXT, font=font_watermark, fill=COLOR_LIGHT_GRAY)
    
    canvas.save(OUTPUT_CLUE_IMAGE, format="JPEG", quality=95, optimize=True)
    logger.info("Created clue image: %s", OUTPUT_CLUE_IMAGE)
    return OUTPUT_CLUE_IMAGE


def create_answer_image(content: ClueContent) -> Path:
    """Create the answer reveal image (Slide 2)."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # Load fonts
    font_header = _load_font(HEADER_FONT_SIZE, bold=True)
    font_answer = _load_font(ANSWER_FONT_SIZE, bold=True)
    font_subtext = _load_font(INSTRUCTION_FONT_SIZE)
    font_watermark = _load_font(WATERMARK_FONT_SIZE)
    
    # Header: "THE ANSWER IS..."
    header_text = "THE ANSWER IS..."
    header_w, header_h = _get_text_bbox(draw, header_text, font_header)
    header_x = (CANVAS_WIDTH - header_w) // 2
    header_y = 280
    draw.text((header_x, header_y), header_text, font=font_header, fill=COLOR_TEXT)
    
    # Answer badge (red background)
    answer_text = content.word.upper()
    answer_w, answer_h = _get_text_bbox(draw, answer_text, font_answer)
    
    badge_padding_x = 100
    badge_padding_y = 50
    badge_width = answer_w + badge_padding_x * 2
    badge_height = answer_h + badge_padding_y * 2
    badge_x = (CANVAS_WIDTH - badge_width) // 2
    badge_y = 520
    
    _draw_rounded_rect(
        draw,
        (badge_x, badge_y, badge_x + badge_width, badge_y + badge_height),
        radius=30,
        fill=COLOR_RED,
    )
    
    # Answer text (white on red)
    answer_x = badge_x + badge_padding_x
    answer_y = badge_y + badge_padding_y
    draw.text((answer_x, answer_y), answer_text, font=font_answer, fill=COLOR_WHITE)
    
    # Subtext: "Did you get it right?"
    subtext = "Did you get it right?"
    sub_w, sub_h = _get_text_bbox(draw, subtext, font_subtext)
    sub_x = (CANVAS_WIDTH - sub_w) // 2
    sub_y = 850
    draw.text((sub_x, sub_y), subtext, font=font_subtext, fill=COLOR_TEXT)
    
    # Follow prompt
    follow_text = "Follow for daily clues!"
    follow_w, follow_h = _get_text_bbox(draw, follow_text, font_subtext)
    follow_x = (CANVAS_WIDTH - follow_w) // 2
    follow_y = 950
    draw.text((follow_x, follow_y), follow_text, font=font_subtext, fill=COLOR_YELLOW)
    
    # Watermark
    wm_w, wm_h = _get_text_bbox(draw, WATERMARK_TEXT, font_watermark)
    wm_x = (CANVAS_WIDTH - wm_w) // 2
    wm_y = CANVAS_HEIGHT - 100
    draw.text((wm_x, wm_y), WATERMARK_TEXT, font=font_watermark, fill=COLOR_LIGHT_GRAY)
    
    canvas.save(OUTPUT_ANSWER_IMAGE, format="JPEG", quality=95, optimize=True)
    logger.info("Created answer image: %s", OUTPUT_ANSWER_IMAGE)
    return OUTPUT_ANSWER_IMAGE


# ---------------------------------------------------------------------------
# GitHub Pages Image Hosting
# ---------------------------------------------------------------------------

def upload_image_to_repo(image_path: Path, filename_prefix: str = "post") -> str:
    """Upload image to images/ folder in repo and return raw GitHub URL."""
    repo_env = os.getenv("GITHUB_REPOSITORY", "")
    if not repo_env or "/" not in repo_env:
        raise RuntimeError("GITHUB_REPOSITORY not set or invalid")
    
    owner, repo_name = repo_env.split("/", 1)
    branch = os.getenv("GITHUB_REF_NAME", "main")
    timestamp = int(datetime.now(timezone.utc).timestamp())
    unique_filename = f"{filename_prefix}_{timestamp}.jpg"
    
    # Create images directory if it doesn't exist
    images_dir = Path("images")
    images_dir.mkdir(exist_ok=True)
    
    # Copy image to images folder
    dest_path = images_dir / unique_filename
    shutil.copy2(image_path, dest_path)
    
    # Git add, commit, and push
    subprocess.run(["git", "add", str(dest_path)], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Add image {unique_filename}"],
        check=True, capture_output=True
    )
    subprocess.run(
        ["git", "push", "origin", branch],
        check=True, capture_output=True
    )
    
    logger.info("Pushed %s to repository", unique_filename)
    
    # Raw GitHub URL (works immediately, no waiting needed)
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/images/{unique_filename}"
    
    # Brief wait for GitHub to process
    logger.info("Waiting for raw URL to be accessible: %s", url)
    time.sleep(5)
    
    # Verify URL is accessible
    max_wait = 60
    check_interval = 5
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                logger.info("Image URL accessible after %ds", elapsed)
                return url
        except requests.RequestException:
            pass
        
        time.sleep(check_interval)
        elapsed += check_interval
        logger.info("Waiting for GitHub... (%ds/%ds)", elapsed, max_wait)
    
    raise RuntimeError(f"Image URL not accessible after {max_wait}s: {url}")


def host_image(image_path: Path, prefix: str = "post") -> str:
    """Host an image and return its public URL."""
    return upload_image_to_repo(image_path, prefix)


# ---------------------------------------------------------------------------
# Instagram API
# ---------------------------------------------------------------------------

def _uses_instagram_login_api() -> bool:
    """Check if using Instagram Login API (vs Facebook Graph API)."""
    token = INSTAGRAM_ACCESS_TOKEN or ""
    return token.startswith(("IGAA", "IGQ", "IGQV"))


def _instagram_api_base() -> str:
    """Get the appropriate API base URL."""
    return INSTAGRAM_LOGIN_API_BASE if _uses_instagram_login_api() else GRAPH_API_BASE


def _resolve_instagram_account_id() -> str:
    """Resolve the Instagram account ID."""
    if _uses_instagram_login_api():
        url = f"{INSTAGRAM_LOGIN_API_BASE}/me"
        params = {"access_token": INSTAGRAM_ACCESS_TOKEN, "fields": "id"}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("id", INSTAGRAM_ACCOUNT_ID)
    return INSTAGRAM_ACCOUNT_ID


def _graph_request(
    method: str,
    endpoint: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
) -> dict[str, Any]:
    """Make a request to the Instagram/Facebook Graph API."""
    base = _instagram_api_base()
    url = f"{base}/{endpoint}"
    
    params = params or {}
    params["access_token"] = INSTAGRAM_ACCESS_TOKEN
    
    if method == "GET":
        response = requests.get(url, params=params, timeout=60)
    elif method == "POST":
        response = requests.post(url, params=params, data=data, timeout=60)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    response.raise_for_status()
    return response.json()


def wait_for_container_ready(container_id: str) -> None:
    """Poll until media container is ready."""
    deadline = time.time() + CONTAINER_POLL_TIMEOUT
    
    while time.time() < deadline:
        data = _graph_request(
            "GET",
            container_id,
            params={"fields": "status_code,status"},
        )
        status_code = data.get("status_code", "")
        
        if status_code == "FINISHED":
            logger.info("Container %s ready", container_id)
            return
        if status_code == "ERROR":
            raise RuntimeError(f"Container error: {data.get('status')}")
        
        logger.info("Container status: %s, waiting...", status_code)
        time.sleep(CONTAINER_POLL_INTERVAL)
    
    raise RuntimeError(f"Container {container_id} not ready after {CONTAINER_POLL_TIMEOUT}s")


def publish_carousel_to_instagram(image_urls: list[str], caption: str) -> str:
    """Publish a carousel post to Instagram."""
    account_id = _resolve_instagram_account_id()
    
    # Step 1: Create child containers for each image
    children_ids = []
    for i, url in enumerate(image_urls):
        logger.info("Creating carousel item %d: %s", i + 1, url)
        data = _graph_request(
            "POST",
            f"{account_id}/media",
            data={
                "image_url": url,
                "is_carousel_item": "true",
            },
        )
        child_id = data.get("id")
        if not child_id:
            raise RuntimeError(f"Failed to create carousel item {i + 1}")
        children_ids.append(child_id)
        logger.info("Created carousel item %d: %s", i + 1, child_id)
    
    # Wait a moment for items to process
    time.sleep(5)
    
    # Step 2: Create parent carousel container
    logger.info("Creating carousel container with %d items", len(children_ids))
    carousel_data = _graph_request(
        "POST",
        f"{account_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
        },
    )
    carousel_id = carousel_data.get("id")
    if not carousel_id:
        raise RuntimeError("Failed to create carousel container")
    logger.info("Created carousel container: %s", carousel_id)
    
    # Step 3: Wait for carousel to be ready
    wait_for_container_ready(carousel_id)
    
    # Step 4: Publish
    logger.info("Publishing carousel...")
    publish_data = _graph_request(
        "POST",
        f"{account_id}/media_publish",
        data={"creation_id": carousel_id},
    )
    media_id = publish_data.get("id")
    logger.info("Published carousel! Media ID: %s", media_id)
    
    return media_id


def publish_story_to_instagram(image_url: str) -> str:
    """Publish a story to Instagram."""
    account_id = _resolve_instagram_account_id()
    
    # Create story container
    logger.info("Creating story container: %s", image_url)
    data = _graph_request(
        "POST",
        f"{account_id}/media",
        data={
            "image_url": image_url,
            "media_type": "STORIES",
        },
    )
    container_id = data.get("id")
    if not container_id:
        raise RuntimeError("Failed to create story container")
    
    # Wait for container
    wait_for_container_ready(container_id)
    
    # Publish
    publish_data = _graph_request(
        "POST",
        f"{account_id}/media_publish",
        data={"creation_id": container_id},
    )
    media_id = publish_data.get("id")
    logger.info("Published story! Media ID: %s", media_id)
    
    return media_id


# ---------------------------------------------------------------------------
# Pipeline Orchestration
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full carousel post pipeline."""
    logger.info("=" * 60)
    logger.info("Starting Daily Clue Cards Pipeline")
    logger.info("=" * 60)
    
    # Validate environment
    validate_env()
    
    # Generate content
    logger.info("Generating content with Gemini AI...")
    content = generate_content()
    
    # Create images
    logger.info("Creating clue image...")
    clue_image = create_clue_image(content)
    
    logger.info("Creating answer image...")
    answer_image = create_answer_image(content)
    
    # Host images
    logger.info("Uploading clue image to GitHub Pages...")
    clue_url = host_image(clue_image, "clue")
    
    logger.info("Uploading answer image to GitHub Pages...")
    answer_url = host_image(answer_image, "answer")
    
    # Publish carousel
    logger.info("Publishing carousel to Instagram...")
    media_id = publish_carousel_to_instagram(
        [clue_url, answer_url],
        content.full_caption(),
    )
    
    # Record published word
    record_published_word(content)
    
    logger.info("=" * 60)
    logger.info("Pipeline complete! Media ID: %s", media_id)
    logger.info("=" * 60)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show-history":
            history = load_word_history()
            print(json.dumps({"entries": history}, indent=2))
            return
        elif sys.argv[1] == "--test-generate":
            validate_env()
            content = generate_content()
            print(f"Word: {content.word}")
            print(f"Clues: {content.clues}")
            print(f"Caption: {content.caption[:100]}...")
            return
        elif sys.argv[1] == "--test-images":
            validate_env()
            content = generate_content()
            create_clue_image(content)
            create_answer_image(content)
            print(f"Created: {OUTPUT_CLUE_IMAGE}, {OUTPUT_ANSWER_IMAGE}")
            return
    
    run_pipeline()


if __name__ == "__main__":
    main()
