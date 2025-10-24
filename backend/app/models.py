from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Session status enumeration."""
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
    files: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class SessionCreate(BaseModel):
    """Response model for session creation."""
    session_id: str
    created_at: datetime


class FileUploadResponse(BaseModel):
    """Response model for file uploads."""
    file_id: str
    filename: str
    size: int
    message: str


class TextExtractionResponse(BaseModel):
    """Response model for text extraction."""
    raw_text_url: str
    cleaned_text_url: str
    stats: Dict[str, Any]


class TextExtractionStats(BaseModel):
    """Statistics from text extraction."""
    pages: int
    total_characters: int
    total_words: int
    avg_chars_per_page: float
    avg_words_per_page: float
    empty_pages: List[int] = Field(default_factory=list)


class CleanedTextStats(BaseModel):
    """Statistics from cleaned text extraction."""
    kept_pages: int
    kept_original_page_numbers: List[int]
    empty_pages_after_cleaning: List[int]
    total_characters: int
    total_words: int
    avg_chars_per_page: float
    avg_words_per_page: float


class TextUpdateRequest(BaseModel):
    """Request model for updating cleaned text."""
    text: str


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
