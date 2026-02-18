#!/bin/bash
# Daily News Agent - Run Script
# Runs the news pipeline, then starts the web server.
# Works both locally (with .venv) and on Railway (system Python + gunicorn).

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Daily News Agent - Starting Pipeline                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Auto-detect Python: prefer venv for local dev, fall back to system
if [ -x ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    PYTHON="python3"
fi

# Monthly cleanup: wipe data on the 1st of each month for a fresh start
CURRENT_DAY=$(TZ=America/Los_Angeles date +%d)
if [ "$CURRENT_DAY" = "01" ]; then
    echo "📅 1st of the month — clearing old data for a fresh start..."
    rm -rf data/raw/* data/processed/* data/digests/* data/articles/* 2>/dev/null || true
    echo "✅ Data directories cleared."
    echo ""
fi

# Ensure data directories exist (needed after cleanup or first deploy)
mkdir -p data/raw data/processed data/digests data/articles

# Run the daily pipeline
echo "📰 Fetching and processing news..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PIPELINE_MAX_CONCURRENCY=5 $PYTHON pipeline/run_daily.py && \
    echo -e "\n✅ Pipeline completed successfully!\n" || \
    echo -e "\n⚠️  Pipeline failed — starting server with existing data.\n"

# Start web server
echo "🚀 Starting web server..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    exec gunicorn \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers 2 \
        --timeout 120 \
        app:app
else
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║   🌐 http://127.0.0.1:8000  —  Press Ctrl+C to stop         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    exec $PYTHON app.py
fi
