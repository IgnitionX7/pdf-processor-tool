"""
Vercel serverless function entry point
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import from main
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import and expose the FastAPI app
from main import app as application

# Vercel looks for either 'app' or 'application'
app = application
