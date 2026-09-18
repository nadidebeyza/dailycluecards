# Daily Clue Cards

Automated Instagram content pipeline for a daily word guessing game.

## How It Works

Every day, the bot:
1. **Feed Post (20:00 Turkey)**: Publishes a 2-image carousel
   - Slide 1: Three clue words with "Guess the Word!" header
   - Slide 2: The answer reveal
2. **Story (14:00 Turkey)**: Publishes a promotional teaser

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/dailycluecards.git
cd dailycluecards
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required secrets:
- `GEMINI_API_KEY` - Get from [Google AI Studio](https://aistudio.google.com/apikey)
- `INSTAGRAM_ACCESS_TOKEN` - From Meta Developer Portal
- `INSTAGRAM_ACCOUNT_ID` - Your Instagram Business Account ID

### 3. Enable GitHub Pages

1. Go to your repo Settings > Pages
2. Set source to "Deploy from a branch"
3. Select `gh-pages` branch (create it first if needed)

### 4. Add GitHub Secrets

Add these secrets to your repository (Settings > Secrets > Actions):
- `GEMINI_API_KEY`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`
- `BRAND_NAME`
- `WATERMARK_TEXT`

## Local Testing

```bash
# Test content generation
python main.py --test-generate

# Test image creation (generates both clue and answer images)
python main.py --test-images

# View word history
python main.py --show-history

# Generate static story image only
python story.py --generate-only
```

## Project Structure

```
dailycluecards/
├── main.py              # Feed post pipeline (carousel)
├── story.py             # Story pipeline (static teaser)
├── word_history.json    # Published words tracker
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── daily_post.yml  # GitHub Actions automation
```

## Design

- **Colors**: White background, red (#E63946) and yellow (#FFD166) accents
- **Feed images**: 1080x1350 (4:5 ratio)
- **Story images**: 1080x1920 (9:16 ratio)

## Manual Trigger

You can manually run the workflow from GitHub Actions:
- `both` - Run both feed post and story
- `post_only` - Run only feed post
- `story_only` - Run only story
