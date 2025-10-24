"""
PDF Processor WebApp - FastAPI Backend
Main application entry point for Vercel deployment
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from pathlib import Path

# Simple settings for Vercel deployment
class Settings:
    def __init__(self):
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.upload_path = Path("/tmp/uploads")  # Vercel uses /tmp for temporary files
        self.cors_origins_list = ["*"]  # Allow all origins for now

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting PDF Processor API...")
    print(f"Upload directory: {settings.upload_path}")
    print(f"Debug mode: {settings.debug}")
    
    # Create upload directory if it doesn't exist
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    print("Shutting down PDF Processor API...")

# Create FastAPI app
app = FastAPI(
    title="PDF Processor API",
    description="Backend API for processing exam paper PDFs and marking schemes",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Root endpoint
@app.get("/api")
async def api_root():
    """API root endpoint with API information."""
    return {
        "name": "PDF Processor API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "upload_dir_exists": settings.upload_path.exists()
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "PDF Processor API",
        "version": "1.0.0",
        "status": "running",
        "message": "API is running successfully on Vercel!",
        "endpoints": {
            "api": "/api",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )
