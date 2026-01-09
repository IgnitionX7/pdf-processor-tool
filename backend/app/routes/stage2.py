"""
Stage 2: Question Extraction Routes
Handles extraction of questions from cleaned text
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any
import json

from ..models import SessionStatus
from ..utils.session_manager import session_manager
from ..processors.question_extractor import extract_questions_from_text


router = APIRouter(prefix="/api/sessions/{session_id}/stage2", tags=["stage2"])


@router.post("/extract-questions")
async def extract_questions(session_id: str):
    """
    Extract questions from cleaned text.

    Args:
        session_id: Session identifier

    Returns:
        Extracted questions with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify cleaned text exists
    if "cleaned_text" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Cleaned text not found. Complete Stage 1 first."
        )

    try:
        # Update session status
        session.status = SessionStatus.PROCESSING
        session.current_stage = 2
        session_manager.update_session(session)

        # Extract questions
        cleaned_text_path = Path(session.files["cleaned_text"])
        session_dir = session_manager.get_session_dir(session_id)
        questions_json_path = session_dir / "questions.json"

        questions = extract_questions_from_text(cleaned_text_path, questions_json_path)

        # Update session with output files
        session.files["questions"] = str(questions_json_path)
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        # Calculate statistics
        total_questions = len(questions)
        total_parts = sum(len(q['parts']) for q in questions)
        total_marks = sum(q.get('totalMarks', 0) or 0 for q in questions)

        return {
            "questions_url": f"/api/sessions/{session_id}/stage2/questions",
            "stats": {
                "total_questions": total_questions,
                "total_parts": total_parts,
                "total_marks": total_marks,
                "questions": questions
            }
        }

    except Exception as e:
        # Update session with error
        session.status = SessionStatus.ERROR
        session.error = str(e)
        session_manager.update_session(session)

        raise HTTPException(
            status_code=500,
            detail=f"Question extraction failed: {str(e)}"
        )


@router.get("/questions")
async def get_questions(session_id: str):
    """
    Get extracted questions.

    Args:
        session_id: Session identifier

    Returns:
        List of extracted questions
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if questions exist
    if "questions" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Questions not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["questions"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Questions file not found on disk")

        # Read and return JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        return questions

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read questions file: {str(e)}"
        )


@router.put("/questions")
async def update_questions(session_id: str, questions: List[Dict[str, Any]]):
    """
    Update questions with user edits.

    Args:
        session_id: Session identifier
        questions: Updated questions list

    Returns:
        Success message with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if questions exist
    if "questions" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Questions not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["questions"])

        # Save updated questions
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        # Calculate statistics
        total_questions = len(questions)
        total_parts = sum(len(q['parts']) for q in questions)
        total_marks = sum(q.get('totalMarks', 0) or 0 for q in questions)

        return {
            "message": "Questions updated successfully",
            "stats": {
                "total_questions": total_questions,
                "total_parts": total_parts,
                "total_marks": total_marks
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update questions: {str(e)}"
        )


@router.post("/validate")
async def validate_questions(session_id: str):
    """
    Validate questions structure.

    Args:
        session_id: Session identifier

    Returns:
        Validation results with errors/warnings
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if questions exist
    if "questions" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Questions not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["questions"])
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        errors = []
        warnings = []

        for q in questions:
            q_num = q.get('questionNumber')

            # Check for missing marks
            if not q.get('totalMarks'):
                warnings.append(f"Question {q_num}: No total marks found")

            # Check parts
            if not q.get('parts'):
                warnings.append(f"Question {q_num}: No parts found")
            else:
                for part in q['parts']:
                    part_label = part.get('partLabel')

                    # Check for empty text
                    if not part.get('text') or not part.get('text').strip():
                        errors.append(f"Question {q_num}, part {part_label}: Empty text")

                    # Check for missing marks
                    if part.get('marks') is None:
                        warnings.append(f"Question {q_num}, part {part_label}: No marks found")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": {
                "total_errors": len(errors),
                "total_warnings": len(warnings)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate questions: {str(e)}"
        )


@router.get("/download")
async def download_questions(session_id: str):
    """
    Download questions JSON file.

    Args:
        session_id: Session identifier

    Returns:
        File download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if questions exist
    if "questions" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Questions not found. Run extraction first."
        )

    try:
        file_path = Path(session.files["questions"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        # Get original PDF filename to use in questions filename
        original_pdf_name = session.files.get("question_paper_name", "question_paper.pdf")
        pdf_stem = Path(original_pdf_name).stem
        questions_filename = f"{pdf_stem}_questions.json"

        return FileResponse(
            path=file_path,
            filename=questions_filename,
            media_type="application/json"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
