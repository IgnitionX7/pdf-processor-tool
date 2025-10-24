"""
PDF Processor WebApp - FastAPI Backend
Main application entry point for Vercel deployment
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from enum import Enum
from pydantic import BaseModel

# Pydantic models for session management
class SessionStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Session(BaseModel):
    """Session model for tracking processing state."""
    session_id: str
    created_at: datetime
    status: SessionStatus = SessionStatus.CREATED
    current_stage: int = 0
    error: Optional[str] = None

class SessionCreate(BaseModel):
    """Response model for session creation."""
    session_id: str
    created_at: datetime

# Simple settings for Vercel deployment
class Settings:
    def __init__(self):
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.upload_path = Path("/tmp/uploads")  # Vercel uses /tmp for temporary files
        self.cors_origins_list = ["*"]  # Allow all origins for now

settings = Settings()

# Simple session manager for Vercel
class SessionManager:
    """Simple session manager for Vercel deployment."""
    
    def __init__(self):
        self.upload_path = settings.upload_path
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self) -> Session:
        """Create a new processing session."""
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            created_at=datetime.now(),
            status=SessionStatus.CREATED,
            current_stage=0
        )
        
        # Create session directory
        session_dir = self.upload_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save session metadata
        self._save_session(session)
        self.sessions[session_id] = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try to load from disk
        session_file = self.upload_path / session_id / "session.json"
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                session = Session(**session_data)
                self.sessions[session_id] = session
                return session
        
        return None
    
    def _save_session(self, session: Session) -> None:
        """Save session metadata to disk."""
        session_dir = self.upload_path / session.session_id
        session_file = session_dir / "session.json"
        
        with open(session_file, 'w', encoding='utf-8') as f:
            session_dict = session.model_dump()
            session_dict['created_at'] = session.created_at.isoformat()
            json.dump(session_dict, f, indent=2)

# Global session manager instance
session_manager = SessionManager()

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

# Session management endpoints
@app.post("/api/sessions", response_model=SessionCreate)
async def create_session():
    """Create a new processing session."""
    try:
        session = session_manager.create_session()
        return SessionCreate(
            session_id=session.session_id,
            created_at=session.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@app.get("/api/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session details by ID."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

# Mount static files for React frontend (production mode)
static_dir = Path(__file__).resolve().parent / "backend" / "dist"
if static_dir.exists():
    # Serve frontend static files
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
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
