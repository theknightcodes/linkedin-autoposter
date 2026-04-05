# Session Memory — LinkedIn Autoposter

## Current Branch
`v2` — **DO NOT merge to `main` yet**

---

## What's Done (v2)

### Remotion Subproject (`remotion/`)
- `PostCard.tsx` — dark gradient card, 1200×627px, topic badge, headline, insight, author footer
- `index.tsx` — Remotion composition registration
- `package.json` + `package-lock.json` — Remotion 4.x, React 19, TypeScript

### Python Pipeline (`src/`)
- `image_generator.py` — Gemini extracts `{headline, insight}` from post → `npx remotion still` renders PNG
- `linkedin_client.py` — `upload_image()` (LinkedIn Images API) + `create_post()` with `image_urn`
- `main.py` — full v2 flow: generate → extract props → render image → upload → post; `--no-image` flag
- `post_tracker.py` — `image_urn` column added + auto-migration for existing DBs
- `config.py` — `ENABLE_IMAGES`, `IMAGE_OUTPUT_DIR` settings

### CI/CD
- `daily_post.yml` — Node.js 20 + `npm ci` in `remotion/` + `ENABLE_IMAGES=true` added

### Tests
- `tests/test_image_generator.py` — 9 tests (all passing)
- `tests/test_linkedin_client.py` — 5 tests (all passing)

---

## What Needs Work ❌

### Remotion PostCard — NEEDS REDESIGN
- The current `PostCard.tsx` design is NOT what was intended
- User will provide a reference/example next session
- **Do not ship the current PostCard design — wait for the example**

---

## Key Notes
- Run tests with: `/opt/miniconda3/envs/linkedin-autoposter/bin/python -m pytest tests/`
- Render a test card: `cd remotion && npx remotion still src/index.tsx PostCard /tmp/out.png --props='{"headline":"...","insight":"...","topic":"ai_tips"}'`
- Gemini model in use: `gemini-2.5-flash` (set via `GEMINI_MODEL` env var)
- Topic colours: `ai_tips`→indigo, `claude_features`→amber, `copilot_tricks`→emerald, `data_engineering_ai`→blue, `lessons_learned`→pink
- `remotion/node_modules/` is gitignored — run `npm ci` inside `remotion/` after cloning
