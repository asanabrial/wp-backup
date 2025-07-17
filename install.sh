#!/bin/bash
# WordPress Backup Tool - Installation Script
# This script sets up the tool with a virtual environment

echo "🚀 WordPress Backup Tool - Installation"
echo "========================================"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install package
echo "📥 Installing wp-backup..."
pip install -e .

if [ $? -eq 0 ]; then
    echo "✅ Installation completed successfully!"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Activate the environment: source venv/bin/activate"
    echo "2. Initialize configuration: wp-backup init"
    echo "3. Copy configuration: cp .env.example .env.local"
    echo "4. Edit .env.local with your settings"
    echo "5. Configure Google Drive credentials in config/"
    echo ""
    echo "📖 For help: wp-backup --help"
else
    echo "❌ Installation failed"
    exit 1
fi
