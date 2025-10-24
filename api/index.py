"""
Vercel serverless function entry point
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import from main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

# Export the app for Vercel
handler = app
