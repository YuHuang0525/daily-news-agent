#!/bin/bash
# Daily News Agent - Quick Start (no data fetch)
# Use this to just start the web server with existing data

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Daily News Agent - Quick Start                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found (.venv)"
    exit 1
fi

# Check if data exists
if [ ! -f "data/digests/latest.json" ]; then
    echo "⚠️  Warning: No news data found!"
    echo "Run './run.sh' first to fetch and process news."
    echo ""
    read -p "Start server anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🚀 Starting web server..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

.venv/bin/python3 app.py
