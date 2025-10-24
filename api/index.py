"""
Vercel entry point for PDF Processor API
This file serves as the entry point for Vercel deployment
"""
import sys
import os

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

# Change to backend directory to make relative imports work
os.chdir(backend_path)

# Import the FastAPI app
from app.main import app

# Export the app for Vercel
__all__ = ['app']
