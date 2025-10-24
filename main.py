"""
PDF Processor WebApp - FastAPI Backend
Main application entry point for Vercel deployment
"""
import os
import subprocess
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from config import settings
from routes import sessions, stage1, stage2, stage3, stage4


def build_frontend():
    """Build the React frontend for Vercel deployment"""
    print("Building React frontend for Vercel...")
    
    # Get paths
    root_dir = Path(__file__).parent
    frontend_dir = root_dir / "frontend"
    dist_dir = frontend_dir / "dist"
    
    # Check if frontend directory exists
    if not frontend_dir.exists():
        print("Frontend directory not found, skipping build")
        return False
    
    try:
        # Install dependencies if node_modules doesn't exist
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            print("Installing frontend dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Failed to install dependencies: {result.stderr}")
                return False
        
        # Build the frontend
        print("Building frontend...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Frontend build completed successfully!")
            return True
        else:
            print(f"✗ Frontend build failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error building frontend: {str(e)}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting PDF Processor API...")
    print(f"Upload directory: {settings.upload_path}")
    print(f"Debug mode: {settings.debug}")
    
    # Build frontend on startup
    print("Building frontend...")
    build_frontend()

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


# Include routers
app.include_router(sessions.router)
app.include_router(stage1.router)
app.include_router(stage2.router)
app.include_router(stage3.router)
app.include_router(stage4.router)


# API Root endpoint
@app.get("/api")
async def api_root():
    """API root endpoint with API information."""
    return {
        "name": "PDF Processor API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "sessions": "/api/sessions",
            "stage1": "/api/sessions/{session_id}/stage1",
            "stage2": "/api/sessions/{session_id}/stage2",
            "stage3": "/api/sessions/{session_id}/stage3",
            "stage4": "/api/sessions/{session_id}/stage4",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


# Mount static files for React frontend (production mode)
static_dir = Path(__file__).parent / "frontend" / "dist"
if static_dir.exists():
    # Serve frontend static files
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    print(f"✓ Serving frontend from: {static_dir}")
else:
    # Development mode - static files not built yet
    @app.get("/")
    async def root():
        """Root endpoint - development mode."""
        return {
            "name": "PDF Processor API",
            "version": "1.0.0",
            "status": "running",
            "mode": "development",
            "message": "Frontend not built. Run 'npm run build' in frontend directory for production mode.",
            "endpoints": {
                "sessions": "/api/sessions",
                "stage1": "/api/sessions/{session_id}/stage1",
                "stage2": "/api/sessions/{session_id}/stage2",
                "stage3": "/api/sessions/{session_id}/stage3",
                "stage4": "/api/sessions/{session_id}/stage4",
                "docs": "/docs",
                "redoc": "/redoc"
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
