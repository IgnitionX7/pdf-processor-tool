"""
Stage 1: Text Extraction Routes
Handles question paper upload and text extraction
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from pathlib import Path
from typing import Dict, Any
import json

from ..models import (
    FileUploadResponse,
    TextExtractionResponse,
    TextUpdateRequest,
    SessionStatus,
    ErrorResponse
)
from ..utils.session_manager import session_manager
from ..utils.file_utils import save_upload_file, validate_pdf_file
from ..processors.text_extractor import extract_text_from_pdf


router = APIRouter(prefix="/api/sessions/{session_id}/stage1", tags=["stage1"])


@router.post("/upload-question-paper", response_model=FileUploadResponse)
async def upload_question_paper(session_id: str, file: UploadFile = File(...)):
    """
    Upload question paper PDF for a session.

    Args:
        session_id: Session identifier
        file: PDF file to upload

    Returns:
        Upload confirmation with file details
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate file
    validate_pdf_file(file.filename)

    try:
        # Save uploaded file
        session_dir = session_manager.get_session_dir(session_id)
        pdf_path = session_dir / "question_paper.pdf"

        file_size = await save_upload_file(file, pdf_path)

        # Update session - store both path and original filename
        session.files["question_paper"] = str(pdf_path)
        session.files["question_paper_name"] = file.filename  # Store original filename
        session_manager.update_session(session)

        return FileUploadResponse(
            file_id="question_paper",
            filename=file.filename,
            size=file_size,
            message="Question paper uploaded successfully"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.post("/extract-text", response_model=TextExtractionResponse)
async def extract_text(session_id: str):
    """
    Extract text from uploaded question paper PDF.

    Args:
        session_id: Session identifier

    Returns:
        URLs to raw and cleaned text files with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify question paper was uploaded
    if "question_paper" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Question paper not uploaded yet"
        )

    try:
        # Update session status
        session.status = SessionStatus.PROCESSING
        session.current_stage = 1
        session_manager.update_session(session)

        # Extract text
        pdf_path = Path(session.files["question_paper"])
        session_dir = session_manager.get_session_dir(session_id)

        raw_txt, cleaned_txt, raw_stats, cleaned_stats, empty_pages = extract_text_from_pdf(
            pdf_path, session_dir
        )

        # Update session with output files
        session.files["raw_text"] = str(raw_txt)
        session.files["cleaned_text"] = str(cleaned_txt)
        session.files["raw_stats"] = str(session_dir / "output.json")
        session.files["cleaned_stats"] = str(session_dir / "output.cleaned.json")
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        return TextExtractionResponse(
            raw_text_url=f"/api/sessions/{session_id}/stage1/text/raw",
            cleaned_text_url=f"/api/sessions/{session_id}/stage1/text/cleaned",
            stats={
                "raw": raw_stats,
                "cleaned": cleaned_stats
            }
        )

    except Exception as e:
        # Update session with error
        session.status = SessionStatus.ERROR
        session.error = str(e)
        session_manager.update_session(session)

        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(e)}"
        )


@router.get("/text/{text_type}")
async def get_text(session_id: str, text_type: str):
    """
    Get extracted text (raw or cleaned).

    Args:
        session_id: Session identifier
        text_type: Type of text to retrieve ('raw' or 'cleaned')

    Returns:
        Plain text content
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Determine which file to return
    if text_type == "raw":
        file_key = "raw_text"
    elif text_type == "cleaned":
        file_key = "cleaned_text"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid text_type. Must be 'raw' or 'cleaned'"
        )

    # Check if file exists
    if file_key not in session.files:
        raise HTTPException(
            status_code=404,
            detail=f"{text_type.capitalize()} text not found. Run extraction first."
        )

    try:
        file_path = Path(session.files[file_key])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Text file not found on disk")

        # Return as plain text
        content = file_path.read_text(encoding="utf-8")
        return PlainTextResponse(content=content)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read text file: {str(e)}"
        )


@router.get("/stats/{stats_type}")
async def get_stats(session_id: str, stats_type: str):
    """
    Get extraction statistics.

    Args:
        session_id: Session identifier
        stats_type: Type of stats to retrieve ('raw' or 'cleaned')

    Returns:
        JSON statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Determine which stats file to return
    if stats_type == "raw":
        file_key = "raw_stats"
    elif stats_type == "cleaned":
        file_key = "cleaned_stats"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid stats_type. Must be 'raw' or 'cleaned'"
        )

    # Check if file exists
    if file_key not in session.files:
        raise HTTPException(
            status_code=404,
            detail=f"{stats_type.capitalize()} stats not found. Run extraction first."
        )

    try:
        file_path = Path(session.files[file_key])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Stats file not found on disk")

        # Read and return JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read stats file: {str(e)}"
        )


@router.put("/text/cleaned")
async def update_cleaned_text(session_id: str, request: TextUpdateRequest):
    """
    Update cleaned text with user edits.

    Args:
        session_id: Session identifier
        request: Updated text content

    Returns:
        Success message
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if cleaned text exists
    if "cleaned_text" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Cleaned text not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["cleaned_text"])

        # Save updated text
        file_path.write_text(request.text, encoding="utf-8")

        return {
            "message": "Cleaned text updated successfully",
            "characters": len(request.text),
            "words": len(request.text.split())
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update text: {str(e)}"
        )


@router.get("/download/{file_type}")
async def download_file(session_id: str, file_type: str):
    """
    Download a file from Stage 1.

    Args:
        session_id: Session identifier
        file_type: Type of file ('raw' for raw text, 'cleaned' for cleaned text)

    Returns:
        File download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Map file type to session file key
    file_mapping = {
        "raw": "raw_text",
        "cleaned": "cleaned_text"
    }

    if file_type not in file_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type. Must be one of: {', '.join(file_mapping.keys())}"
        )

    file_key = file_mapping[file_type]

    # Check if file exists
    if file_key not in session.files:
        raise HTTPException(
            status_code=404,
            detail=f"File not found. Run extraction first."
        )

    try:
        file_path = Path(session.files[file_key])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="text/plain"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
