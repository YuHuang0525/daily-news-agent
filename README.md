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

## Quick Start

Run the complete pipeline and start the server:

```bash
./run.sh
```

This will:
1. Fetch news from all sources
2. Process and analyze articles with AI (with progress bar)
3. Start the web server at http://127.0.0.1:8000

Or start just the web server (using existing data):

```bash
./start.sh
```

## Manual Commands

Run daily pipeline:
```bash
.venv/bin/python3 pipeline/run_daily.py
```

Run local web app:
```bash
.venv/bin/python3 app.py
```

Open `http://127.0.0.1:8000`.

## Cron (8:00 AM PST)
Add a cron entry (example):

```bash
0 8 * * * cd /path/to/daily-news-agent && /path/to/.venv/bin/python3 pipeline/run_daily.py >> logs/cron.log 2>&1
```

## License

This project is licensed under a **Non-Commercial License**.

**⚠️ Commercial use is NOT permitted.**

- ✅ Personal use
- ✅ Educational use
- ✅ Research use
- ❌ Commercial use (selling, revenue generation, commercial services)

For commercial licensing, please contact the author. See the [LICENSE](LICENSE) file for full details.
