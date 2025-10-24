"""
Vercel entry point for PDF Processor API
This file serves as the entry point for Vercel deployment
"""
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import the FastAPI app
from app.main import app

# Export the app for Vercel
__all__ = ['app']
