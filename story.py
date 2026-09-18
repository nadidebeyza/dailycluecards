#!/usr/bin/env python3
"""
Daily Clue Cards - Static Story Pipeline

Publishes static promotional stories (clue + answer) to Instagram.
Uses a fixed example game - no AI generation needed.
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
    COLOR_WHITE,
    COLOR_RED,
    YESEVA_FONT,
    MASCOT_IMAGE,
    _get_text_bbox,
)
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Story Configuration
# ---------------------------------------------------------------------------

STORY_WIDTH = 1080
STORY_HEIGHT = 1920  # 9:16 aspect ratio for stories
STORY_CLUE_PATH = Path("story_clue.jpg")
STORY_ANSWER_PATH = Path("story_answer.jpg")

# Example game for story (different from daily post)
STORY_CLUES = ["Night", "Crater", "Tide"]
STORY_ANSWER = "Moon"

COLOR_BLACK = (0, 0, 0)

# ---------------------------------------------------------------------------
# Static Story Generation
# ---------------------------------------------------------------------------

def create_story_clue() -> Path:
    """Create the story clue image (slide 1)."""
    canvas = Image.new("RGB", (STORY_WIDTH, STORY_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # Load Yeseva One fonts
    if YESEVA_FONT.exists():
        font_header = ImageFont.truetype(str(YESEVA_FONT), 100)
        font_clue = ImageFont.truetype(str(YESEVA_FONT), 75)
        font_instruction = ImageFont.truetype(str(YESEVA_FONT), 36)
        font_cta = ImageFont.truetype(str(YESEVA_FONT), 50)
    else:
        raise RuntimeError("Yeseva One font not found")
    
    # Header: "Guess The Word!"
    header_text = "Guess The Word!"
    header_w, header_h = _get_text_bbox(draw, header_text, font_header)
    draw.text(((STORY_WIDTH - header_w) // 2, 180), header_text, font=font_header, fill=COLOR_RED)
    
    # Clues
    badge_height = 100
    badge_start_y = 350
    badge_spacing = 110
    
    for i, clue in enumerate(STORY_CLUES):
        badge_y = badge_start_y + (i * badge_spacing)
        numbered_clue = f"{i + 1}. {clue}"
        clue_w, clue_h = _get_text_bbox(draw, numbered_clue, font_clue)
        clue_x = (STORY_WIDTH - clue_w) // 2
        clue_y = badge_y + (badge_height - clue_h) // 2
        draw.text((clue_x, clue_y), numbered_clue, font=font_clue, fill=COLOR_BLACK)
    
    # Instruction
    inst_text = "Touch to see the answer >>"
    inst_w, inst_h = _get_text_bbox(draw, inst_text, font_instruction)
    draw.text(((STORY_WIDTH - inst_w) // 2, badge_start_y + (3 * badge_spacing) + 80), inst_text, font=font_instruction, fill=COLOR_BLACK)
    
    # Mascot
    if MASCOT_IMAGE.exists():
        mascot = Image.open(MASCOT_IMAGE).convert("RGBA")
        side_padding = 200
        target_width = STORY_WIDTH - (side_padding * 2)
        target_height = int(target_width * mascot.height / mascot.width)
        mascot = mascot.resize((target_width, target_height), Image.Resampling.LANCZOS)
        mascot_x = (STORY_WIDTH - target_width) // 2
        mascot_y = 900
        canvas.paste(mascot, (mascot_x, mascot_y), mascot)
    
    # CTA at bottom
    cta_text = "Check Our Posts!"
    cta_w, cta_h = _get_text_bbox(draw, cta_text, font_cta)
    draw.text(((STORY_WIDTH - cta_w) // 2, 1700), cta_text, font=font_cta, fill=COLOR_RED)
    
    canvas.save(STORY_CLUE_PATH, format="JPEG", quality=95, optimize=True)
    logger.info("Created story clue image: %s", STORY_CLUE_PATH)
    return STORY_CLUE_PATH


def create_story_answer() -> Path:
    """Create the story answer image (slide 2)."""
    canvas = Image.new("RGB", (STORY_WIDTH, STORY_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(canvas)
    
    # Load Yeseva One fonts
    if YESEVA_FONT.exists():
        font_header = ImageFont.truetype(str(YESEVA_FONT), 90)
        font_answer = ImageFont.truetype(str(YESEVA_FONT), 120)
        font_subtext = ImageFont.truetype(str(YESEVA_FONT), 45)
        font_cta = ImageFont.truetype(str(YESEVA_FONT), 50)
    else:
        raise RuntimeError("Yeseva One font not found")
    
    # Header
    header_text = "The Answer Is..."
    header_w, header_h = _get_text_bbox(draw, header_text, font_header)
    draw.text(((STORY_WIDTH - header_w) // 2, 200), header_text, font=font_header, fill=COLOR_RED)
    
    # Answer in red rectangle
    bbox = draw.textbbox((0, 0), STORY_ANSWER, font=font_answer)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_offset_y = bbox[1]
    
    rect_padding_x = 60
    rect_padding_y = 40
    rect_width = text_width + rect_padding_x * 2
    rect_height = text_height + rect_padding_y * 2
    rect_x = (STORY_WIDTH - rect_width) // 2
    rect_y = 380
    
    draw.rounded_rectangle(
        (rect_x, rect_y, rect_x + rect_width, rect_y + rect_height),
        radius=20,
        fill=COLOR_RED
    )
    
    # Center answer text precisely
    answer_x = rect_x + (rect_width - text_width) // 2
    answer_y = rect_y + rect_padding_y - text_offset_y
    draw.text((answer_x, answer_y), STORY_ANSWER, font=font_answer, fill=COLOR_WHITE)
    
    # Subtext
    subtext = "Follow for more!"
    sub_w, sub_h = _get_text_bbox(draw, subtext, font_subtext)
    draw.text(((STORY_WIDTH - sub_w) // 2, rect_y + rect_height + 80), subtext, font=font_subtext, fill=COLOR_BLACK)
    
    # Mascot
    if MASCOT_IMAGE.exists():
        mascot = Image.open(MASCOT_IMAGE).convert("RGBA")
        side_padding = 200
        target_width = STORY_WIDTH - (side_padding * 2)
        target_height = int(target_width * mascot.height / mascot.width)
        mascot = mascot.resize((target_width, target_height), Image.Resampling.LANCZOS)
        mascot_x = (STORY_WIDTH - target_width) // 2
        mascot_y = 900
        canvas.paste(mascot, (mascot_x, mascot_y), mascot)
    
    # CTA at bottom
    cta_text = "Check Our Posts!"
    cta_w, cta_h = _get_text_bbox(draw, cta_text, font_cta)
    draw.text(((STORY_WIDTH - cta_w) // 2, 1700), cta_text, font=font_cta, fill=COLOR_RED)
    
    canvas.save(STORY_ANSWER_PATH, format="JPEG", quality=95, optimize=True)
    logger.info("Created story answer image: %s", STORY_ANSWER_PATH)
    return STORY_ANSWER_PATH


def create_story_images() -> tuple[Path, Path]:
    """Create both story images."""
    clue_path = create_story_clue()
    answer_path = create_story_answer()
    return clue_path, answer_path


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_story_pipeline() -> None:
    """Execute the story pipeline - publishes 2 stories (clue + answer)."""
    logger.info("=" * 60)
    logger.info("Starting Daily Clue Cards Story Pipeline")
    logger.info("=" * 60)
    
    # Validate environment
    validate_env()
    
    # Create story images
    clue_path, answer_path = create_story_images()
    
    # Host and publish clue story
    logger.info("Uploading clue story...")
    clue_url = host_image(clue_path, "story_clue")
    logger.info("Publishing clue story to Instagram...")
    clue_media_id = publish_story_to_instagram(clue_url)
    logger.info("Clue story published! Media ID: %s", clue_media_id)
    
    # Host and publish answer story
    logger.info("Uploading answer story...")
    answer_url = host_image(answer_path, "story_answer")
    logger.info("Publishing answer story to Instagram...")
    answer_media_id = publish_story_to_instagram(answer_url)
    logger.info("Answer story published! Media ID: %s", answer_media_id)
    
    logger.info("=" * 60)
    logger.info("Story pipeline complete!")
    logger.info("=" * 60)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--generate-only":
            clue_path, answer_path = create_story_images()
            print(f"Created: {clue_path}, {answer_path}")
            return
    
    run_story_pipeline()


if __name__ == "__main__":
    main()
