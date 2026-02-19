#!/bin/bash
# Daily News Agent - Run Script
# Works locally (with .venv) and on Railway (system Python + gunicorn).

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Daily News Agent - Starting                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Auto-detect Python: prefer venv for local dev, fall back to system
if [ -x ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    PYTHON="python3"
fi

# Ensure data directories exist
mkdir -p data/raw data/processed data/digests data/articles

if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    # On Railway: start gunicorn immediately — health check passes right away.
    # APScheduler inside app.py runs the pipeline in the background on startup,
    # then repeats daily at 7:00 AM PST (15:00 UTC).
    echo "🚀 Starting web server (pipeline will run in background)..."
    exec gunicorn \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers 1 \
        --timeout 120 \
        app:app
else
    # Local: monthly cleanup on the 1st of the month
    CURRENT_DAY=$(TZ=America/Los_Angeles date +%d)
    if [ "$CURRENT_DAY" = "01" ]; then
        echo "📅 1st of the month — clearing old data for a fresh start..."
        rm -rf data/raw/* data/processed/* data/digests/* data/articles/* 2>/dev/null || true
        echo "✅ Data directories cleared."
        echo ""
    fi

    # Local: run pipeline first, then start Flask dev server
    echo "📰 Fetching and processing news..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    PIPELINE_MAX_CONCURRENCY=5 $PYTHON pipeline/run_daily.py && \
        echo -e "\n✅ Pipeline completed successfully!\n" || \
        echo -e "\n⚠️  Pipeline failed — starting server with existing data.\n"

    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║   🌐 http://127.0.0.1:8000  —  Press Ctrl+C to stop         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    exec $PYTHON app.py
fi
