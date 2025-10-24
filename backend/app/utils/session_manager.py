import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
from ..config import settings
from ..models import Session, SessionStatus


class SessionManager:
    """Manages session creation, retrieval, and cleanup."""

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
            current_stage=0,
            files={}
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
        # Try to get from memory
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

    def update_session(self, session: Session) -> None:
        """Update session data."""
        self.sessions[session.session_id] = session
        self._save_session(session)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its files."""
        session_dir = self.upload_path / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)

        if session_id in self.sessions:
            del self.sessions[session_id]

        return True

    def get_session_dir(self, session_id: str) -> Path:
        """Get the directory path for a session."""
        return self.upload_path / session_id

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions. Returns count of deleted sessions."""
        expiry_time = datetime.now() - timedelta(hours=settings.session_expiry_hours)
        deleted_count = 0

        for session_dir in self.upload_path.iterdir():
            if not session_dir.is_dir():
                continue

            session_file = session_dir / "session.json"
            if session_file.exists():
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    created_at = datetime.fromisoformat(session_data['created_at'])

                    if created_at < expiry_time:
                        self.delete_session(session_dir.name)
                        deleted_count += 1

        return deleted_count

    def _save_session(self, session: Session) -> None:
        """Save session metadata to disk."""
        session_dir = self.upload_path / session.session_id
        session_file = session_dir / "session.json"

        with open(session_file, 'w', encoding='utf-8') as f:
            # Convert datetime to ISO format for JSON serialization
            session_dict = session.model_dump()
            session_dict['created_at'] = session.created_at.isoformat()
            json.dump(session_dict, f, indent=2)


# Global session manager instance
session_manager = SessionManager()
