from fastapi import APIRouter, HTTPException
from models import Session, SessionCreate, ErrorResponse
from utils.session_manager import session_manager


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreate)
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


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session details by ID."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its files."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = session_manager.delete_session(session_id)
    if success:
        return {"message": "Session deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete session")
