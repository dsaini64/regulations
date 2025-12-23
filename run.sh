#!/bin/bash

# Regulation Search System Startup Script

echo "🚀 Starting Regulation Search System..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Use venv's Python directly (more reliable than activating)
VENV_PYTHON="./venv/bin/python"
VENV_PIP="./venv/bin/python -m pip"

# Install dependencies
echo "📥 Installing dependencies..."
$VENV_PIP install -q -r requirements.txt

# Check if database exists
if [ ! -f "regulations.db" ]; then
    echo "💾 Database will be created on first run..."
fi

# Start the application
echo ""
echo "✅ Starting Flask application..."
echo "🌐 Open your browser to: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

$VENV_PYTHON app.py

