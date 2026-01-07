"""
Stage 3: Marking Scheme Extraction Routes
Handles extraction of marking schemes from PDF
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Dict
import json

from models import FileUploadResponse, SessionStatus
from utils.session_manager import session_manager
from utils.file_utils import save_upload_file, validate_pdf_file
from processors.marking_scheme_extractor import extract_marking_schemes_from_pdf
from processors.enhanced_marking_scheme_extractor import extract_marking_schemes_from_pdf_enhanced


router = APIRouter(prefix="/api/sessions/{session_id}/stage3", tags=["stage3"])


@router.post("/upload-marking-scheme", response_model=FileUploadResponse)
async def upload_marking_scheme(session_id: str, file: UploadFile = File(...)):
    """
    Upload marking scheme PDF for a session.

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
        pdf_path = session_dir / "marking_scheme.pdf"

        file_size = await save_upload_file(file, pdf_path)

        # Update session
        session.files["marking_scheme"] = str(pdf_path)
        session_manager.update_session(session)

        return FileUploadResponse(
            file_id="marking_scheme",
            filename=file.filename,
            size=file_size,
            message="Marking scheme uploaded successfully"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.post("/extract-marking-schemes")
async def extract_marking_schemes(
    session_id: str,
    start_page: int = 8,
    use_latex: bool = False
):
    """
    Extract marking schemes from uploaded PDF.

    Args:
        session_id: Session identifier
        start_page: Page number to start extraction (default: 8)
        use_latex: Use enhanced extraction with LaTeX support (default: False)

    Returns:
        Extracted marking schemes with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify marking scheme was uploaded
    if "marking_scheme" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Marking scheme not uploaded yet"
        )

    # Auto-detect if we should use LaTeX based on the workflow
    # If the session has enhanced_questions_latex, use LaTeX for consistency
    if "enhanced_questions_latex" in session.files:
        use_latex = True

    try:
        # Update session status
        session.status = SessionStatus.PROCESSING
        session.current_stage = 3
        session_manager.update_session(session)

        # Extract marking schemes
        pdf_path = Path(session.files["marking_scheme"])
        session_dir = session_manager.get_session_dir(session_id)
        marking_schemes_json_path = session_dir / "marking_schemes.json"

        # Choose extraction method based on use_latex parameter
        if use_latex:
            marking_schemes = extract_marking_schemes_from_pdf_enhanced(
                pdf_path, marking_schemes_json_path, start_page
            )
        else:
            marking_schemes = extract_marking_schemes_from_pdf(
                pdf_path, marking_schemes_json_path, start_page
            )

        # Update session with output files
        session.files["marking_schemes"] = str(marking_schemes_json_path)
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        return {
            "marking_schemes_url": f"/api/sessions/{session_id}/stage3/marking-schemes",
            "stats": {
                "total_entries": len(marking_schemes),
                "marking_schemes": marking_schemes
            }
        }

    except Exception as e:
        # Update session with error
        session.status = SessionStatus.ERROR
        session.error = str(e)
        session_manager.update_session(session)

        raise HTTPException(
            status_code=500,
            detail=f"Marking scheme extraction failed: {str(e)}"
        )


@router.get("/marking-schemes")
async def get_marking_schemes(session_id: str):
    """
    Get extracted marking schemes.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary of marking schemes
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if marking schemes exist
    if "marking_schemes" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Marking schemes not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["marking_schemes"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Marking schemes file not found on disk")

        # Read and return JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            marking_schemes = json.load(f)
        return marking_schemes

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read marking schemes file: {str(e)}"
        )


@router.put("/marking-schemes")
async def update_marking_schemes(session_id: str, marking_schemes: Dict[str, str]):
    """
    Update marking schemes with user edits.

    Args:
        session_id: Session identifier
        marking_schemes: Updated marking schemes dictionary

    Returns:
        Success message with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if marking schemes exist
    if "marking_schemes" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Marking schemes not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["marking_schemes"])

        # Save updated marking schemes
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(marking_schemes, f, indent=2, ensure_ascii=False)

        return {
            "message": "Marking schemes updated successfully",
            "stats": {
                "total_entries": len(marking_schemes)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update marking schemes: {str(e)}"
        )


@router.get("/download")
async def download_marking_schemes(session_id: str):
    """
    Download marking schemes JSON file.

    Args:
        session_id: Session identifier

    Returns:
        File download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if marking schemes exist
    if "marking_schemes" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Marking schemes not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["marking_schemes"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            path=file_path,
            filename="marking_schemes.json",
            media_type="application/json"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
