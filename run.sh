#!/bin/bash
# Daily News Agent - Run Script
# This script fetches news, processes it, and starts the web server

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Daily News Agent - Starting Pipeline                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found (.venv)"
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Step 1: Run the daily pipeline
echo "📰 Step 1: Fetching and processing news..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
.venv/bin/python3 pipeline/run_daily.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Pipeline completed successfully!"
    echo ""
else
    echo ""
    echo "❌ Pipeline failed. Please check the errors above."
    exit 1
fi

# Step 2: Start the Flask app
echo "🚀 Step 2: Starting web server..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   🌐 Server Running                            ║"
echo "║                                                                ║"
echo "║   Access your news dashboard at:                              ║"
echo "║   👉  http://127.0.0.1:8000                                   ║"
echo "║                                                                ║"
echo "║   Press Ctrl+C to stop the server                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

.venv/bin/python3 app.py
