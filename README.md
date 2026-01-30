# Daily News Agent

Local, file-system based news agent that aggregates tech, finance, and global
politics with China/US emphasis. Produces a bilingual daily digest by 8:00 AM
PST and serves a local web UI for daily reading and discussion.

## Features
- Bilingual summaries (EN + ZH)
- Credibility scoring with a separate low-credibility lane
- Implication analysis per item
- Local file storage, no database required
- Extensible source registry
- Local web UI with digest + deep dive entry points
- Beautiful animated Galaxy background using OGL WebGL

## Setup
1) Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Create a `.env` file (copy from example):

```bash
cp .env.example .env
```

4) Set your API key in `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

5) Review and edit `config/sources.yml` and `config/preferences.json`.

6) Install Node.js dependencies and build the frontend:

```bash
npm install
npm run build
```

## Run daily pipeline
```bash
python pipeline/run_daily.py
```

## Run local web app
```bash
python app.py
```

Open `http://127.0.0.1:8000`.

## Cron (8:00 AM PST)
Add a cron entry (example):

```bash
0 8 * * * cd /Users/jameshuang/Documents/test-01-29-2026 && /path/to/python pipeline/run_daily.py >> logs/cron.log 2>&1
```

## Data layout
- `data/raw/YYYY-MM-DD/` raw source payloads
- `data/processed/YYYY-MM-DD/` normalized items
- `data/digests/YYYY-MM-DD/` daily outputs
- `data/digests/latest.json` latest digest for UI

## Customizing the Galaxy Background

The Galaxy background is built with OGL and can be customized in `src/main.js`. Available options:

```javascript
{
  mouseRepulsion: true,        // Enable mouse repulsion effect
  mouseInteraction: true,      // Enable mouse interaction
  density: 1,                  // Star density (0.5 - 2.0)
  glowIntensity: 0.3,         // Star glow intensity (0 - 1)
  saturation: 0,              // Color saturation (0 - 1)
  hueShift: 140,              // Base hue (0 - 360)
  twinkleIntensity: 0.3,      // Star twinkle effect (0 - 1)
  rotationSpeed: 0.1,         // Scene rotation speed
  repulsionStrength: 2,       // Mouse repulsion strength
  starSpeed: 0.5,             // Star movement speed
  speed: 1                    // Overall animation speed
}
```

After making changes, rebuild:

```bash
npm run build
```

For development with hot reload:

```bash
npm run dev
```

## Notes
- Rednote/Xiaohongshu ingestion is intentionally deferred. The pipeline is
  designed so you can add it later by extending the source registry.
