"""
Enhanced Combined Extractor Routes - Root Level Wrapper
This file re-exports the enhanced_extractor router from backend.app.routes
for compatibility with the root-level main.py (Vercel deployment).
"""
import sys
from pathlib import Path

# Add backend directory to Python path so we can import app as a package
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Import the actual router from backend.app.routes
# This avoids circular import since we're importing from the backend package
from app.routes.enhanced_extractor import router

# Re-export the router
__all__ = ['router']
