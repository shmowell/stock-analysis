"""
Entry point for the Stock Analysis web GUI.

Usage:
    python run_web.py
"""

import sys
from pathlib import Path

# Add src/ to path so all existing imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

# Also add scripts/ so we can import helper functions from existing scripts
sys.path.insert(0, str(project_root / 'scripts'))

from web import create_app

if __name__ == '__main__':
    app = create_app()
    print("Starting Stock Analysis Web GUI...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
