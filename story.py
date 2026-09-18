#!/usr/bin/env python3
"""
Daily Clue Cards - Static Story Pipeline

Publishes a static promotional story to Instagram.
The story is always the same teaser image - no AI generation needed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from main import (
    validate_env,
    host_image,
    publish_story_to_instagram,
    logger,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    COLOR_WHITE,
    COLOR_RED,
    COLOR_YELLOW,
    COLOR_TEXT,
    COLOR_LIGHT_GRAY,
    WATERMARK_TEXT,
    _load_font,
    _draw_rounded_rect,
    _get_text_bbox,
)
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Story Configuration
# ---------------------------------------------------------------------------

STORY_WIDTH = 1080
STORY_HEIGHT = 1920  # 9:16 aspect ratio for stories
STATIC_STORY_PATH = Path("static_story.jpg")

# ---------------------------------------------------------------------------
# Static Story Generation
# ---------------------------------------------------------------------------

def create_static_story() -> Path:
    """Create the static promotional story image."""
    canvas = Image.new("RGB", (STORY_WIDTH, STORY_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # Load fonts
    font_title = _load_font(64, bold=True)
    font_subtitle = _load_font(48, bold=True)
    font_clue = _load_font(40, bold=True)
    font_small = _load_font(32)
    font_watermark = _load_font(28)
    
    # Title: "DAILY CLUE CARDS"
    title_text = "DAILY CLUE CARDS"
    title_w, title_h = _get_text_bbox(draw, title_text, font_title)
    title_x = (STORY_WIDTH - title_w) // 2
    title_y = 200
    draw.text((title_x, title_y), title_text, font=font_title, fill=COLOR_RED)
    
    # Subtitle: "Can you guess the word?"
    subtitle_text = "Can you guess the word?"
    sub_w, sub_h = _get_text_bbox(draw, subtitle_text, font_subtitle)
    sub_x = (STORY_WIDTH - sub_w) // 2
    sub_y = 300
    draw.text((sub_x, sub_y), subtitle_text, font=font_subtitle, fill=COLOR_TEXT)
    
    # Sample card preview
    card_width = 800
    card_height = 700
    card_x = (STORY_WIDTH - card_width) // 2
    card_y = 480
    
    # Card background (light shadow effect)
    shadow_offset = 8
    draw.rounded_rectangle(
        (card_x + shadow_offset, card_y + shadow_offset, 
         card_x + card_width + shadow_offset, card_y + card_height + shadow_offset),
        radius=20,
        fill=(230, 230, 230),
    )
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_width, card_y + card_height),
        radius=20,
        fill=COLOR_WHITE,
        outline=COLOR_LIGHT_GRAY,
        width=2,
    )
    
    # Card header
    card_header = "GUESS THE WORD!"
    header_w, header_h = _get_text_bbox(draw, card_header, font_subtitle)
    header_x = card_x + (card_width - header_w) // 2
    header_y = card_y + 50
    draw.text((header_x, header_y), card_header, font=font_subtitle, fill=COLOR_RED)
    
    # Sample clue badges
    badge_width = 500
    badge_height = 70
    badge_x = card_x + (card_width - badge_width) // 2
    sample_clues = ["CLUE 1", "CLUE 2", "CLUE 3"]
    badge_start_y = card_y + 180
    badge_spacing = 100
    
    for i, clue in enumerate(sample_clues):
        badge_y = badge_start_y + (i * badge_spacing)
        
        _draw_rounded_rect(
            draw,
            (badge_x, badge_y, badge_x + badge_width, badge_y + badge_height),
            radius=15,
            fill=COLOR_YELLOW,
        )
        
        clue_w, clue_h = _get_text_bbox(draw, clue, font_clue)
        clue_x = badge_x + (badge_width - clue_w) // 2
        clue_y = badge_y + (badge_height - clue_h) // 2
        draw.text((clue_x, clue_y), clue, font=font_clue, fill=COLOR_TEXT)
    
    # "?" in a circle
    question_y = card_y + card_height - 130
    question_size = 80
    question_x = card_x + (card_width - question_size) // 2
    draw.ellipse(
        (question_x, question_y, question_x + question_size, question_y + question_size),
        fill=COLOR_RED,
    )
    q_font = _load_font(48, bold=True)
    q_w, q_h = _get_text_bbox(draw, "?", q_font)
    draw.text(
        (question_x + (question_size - q_w) // 2, question_y + (question_size - q_h) // 2 - 3),
        "?",
        font=q_font,
        fill=COLOR_WHITE,
    )
    
    # Call to action
    cta_text = "Play Every Day!"
    cta_w, cta_h = _get_text_bbox(draw, cta_text, font_subtitle)
    cta_x = (STORY_WIDTH - cta_w) // 2
    cta_y = 1300
    draw.text((cta_x, cta_y), cta_text, font=font_subtitle, fill=COLOR_RED)
    
    # Arrow down
    arrow_text = "↓"
    arrow_font = _load_font(60)
    arrow_w, arrow_h = _get_text_bbox(draw, arrow_text, arrow_font)
    arrow_x = (STORY_WIDTH - arrow_w) // 2
    arrow_y = 1400
    draw.text((arrow_x, arrow_y), arrow_text, font=arrow_font, fill=COLOR_YELLOW)
    
    # "Check our posts!"
    posts_text = "Check our posts!"
    posts_w, posts_h = _get_text_bbox(draw, posts_text, font_small)
    posts_x = (STORY_WIDTH - posts_w) // 2
    posts_y = 1500
    draw.text((posts_x, posts_y), posts_text, font=font_small, fill=COLOR_TEXT)
    
    # Watermark
    wm_w, wm_h = _get_text_bbox(draw, WATERMARK_TEXT, font_watermark)
    wm_x = (STORY_WIDTH - wm_w) // 2
    wm_y = STORY_HEIGHT - 150
    draw.text((wm_x, wm_y), WATERMARK_TEXT, font=font_watermark, fill=COLOR_LIGHT_GRAY)
    
    canvas.save(STATIC_STORY_PATH, format="JPEG", quality=95, optimize=True)
    logger.info("Created static story image: %s", STATIC_STORY_PATH)
    return STATIC_STORY_PATH


def ensure_static_story_exists() -> Path:
    """Ensure the static story image exists, create if needed."""
    if not STATIC_STORY_PATH.exists():
        logger.info("Static story not found, creating...")
        return create_static_story()
    return STATIC_STORY_PATH


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_story_pipeline() -> None:
    """Execute the static story pipeline."""
    logger.info("=" * 60)
    logger.info("Starting Daily Clue Cards Story Pipeline")
    logger.info("=" * 60)
    
    # Validate environment
    validate_env()
    
    # Ensure static story exists
    story_path = ensure_static_story_exists()
    
    # Host image
    logger.info("Uploading story to GitHub Pages...")
    story_url = host_image(story_path, "story")
    
    # Publish story
    logger.info("Publishing story to Instagram...")
    media_id = publish_story_to_instagram(story_url)
    
    logger.info("=" * 60)
    logger.info("Story pipeline complete! Media ID: %s", media_id)
    logger.info("=" * 60)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--generate-only":
            create_static_story()
            print(f"Created: {STATIC_STORY_PATH}")
            return
    
    run_story_pipeline()


if __name__ == "__main__":
    main()
