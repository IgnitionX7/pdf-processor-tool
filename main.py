"""
PDF Processor WebApp - FastAPI Backend
Main application entry point for Vercel deployment
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from config import settings
from routes import sessions, stage1, stage2, stage3, stage4


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting PDF Processor API...")
    print(f"Upload directory: {settings.upload_path}")
    print(f"Debug mode: {settings.debug}")

    # Check if frontend is built
    static_dir = Path(__file__).parent / "frontend" / "dist"
    if static_dir.exists():
        print(f"✓ Frontend build found at: {static_dir}")
    else:
        print(f"⚠ Frontend not built. Static files will not be served.")

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


# Serve static files
static_dir = Path(__file__).parent / "frontend" / "dist"
if static_dir.exists():
    # Mount assets directory first
    assets_path = static_dir / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    # Serve index.html for root path
    @app.get("/")
    async def serve_root():
        """Serve the React frontend"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return {"error": "Frontend not found"}

    print(f"✓ Serving frontend from: {static_dir}")
else:
    @app.get("/")
    async def root_fallback():
        """Development mode"""
        return {
            "name": "PDF Processor API",
            "version": "1.0.0",
            "status": "running",
            "mode": "development",
            "message": "Frontend not built"
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
