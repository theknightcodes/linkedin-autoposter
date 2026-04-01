#!/usr/bin/env bash
set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

echo ""
echo "══════════════════════════════════════════"
echo "  LinkedIn Autoposter — Setup"
echo "══════════════════════════════════════════"

# 1. Conda environment
echo ""
echo "▶ Creating conda environment 'linkedin-autoposter'…"
conda env create -f environment.yml --force
echo "  ✅ Environment ready"

PYTHON="/opt/miniconda3/envs/linkedin-autoposter/bin/python"

# 2. .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "▶ Created .env from template."
  echo "  👉 Open .env and fill in:"
  echo "     ANTHROPIC_API_KEY"
  echo "     LINKEDIN_CLIENT_ID"
  echo "     LINKEDIN_CLIENT_SECRET"
  echo ""
  read -p "  Press ENTER once you've filled in .env…" _
fi

# 3. Init DB
echo ""
echo "▶ Initialising SQLite database…"
$PYTHON -c "from src.post_tracker import init_db; init_db(); print('  ✅ posts.db ready')"

# 4. LinkedIn OAuth
echo ""
echo "▶ Starting LinkedIn OAuth flow…"
echo "  (Your browser will open. Approve the app and the tokens will be saved.)"
echo ""
$PYTHON -m src.oauth_setup

# 5. Dry-run test
echo ""
echo "▶ Running dry-run to verify content generation…"
$PYTHON -m src.main --dry-run

# 6. Schedule (launchd)
PLIST_SRC="$PROJECT_DIR/schedule/com.linkedin.autoposter.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.linkedin.autoposter.plist"
echo ""
echo "▶ Installing launchd schedule (8:30 AM daily)…"
cp "$PLIST_SRC" "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "  ✅ Schedule installed"

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Commands:"
echo "    Post now     : bash scripts/post_now.sh"
echo "    Dry run      : conda run -n linkedin-autoposter python -m src.main --dry-run"
echo "    Stats        : conda run -n linkedin-autoposter python -m src.main --stats"
echo "    Logs         : tail -f logs/autoposter.log"
echo "══════════════════════════════════════════"
echo ""
