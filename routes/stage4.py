"""
Stage 4: Merge Routes
Handles merging of marking schemes into questions
"""
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Dict, Any, List
import json

from models import SessionStatus
from utils.session_manager import session_manager
from processors.merger import merge_files


router = APIRouter(prefix="/api/sessions/{session_id}/stage4", tags=["stage4"])


@router.post("/merge")
async def merge_marking_schemes(session_id: str):
    """
    Merge marking schemes into questions.

    Args:
        session_id: Session identifier

    Returns:
        Merged questions with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify questions exist (support both old and enhanced workflows)
    questions_key = None
    if "questions" in session.files:
        questions_key = "questions"
    elif "enhanced_questions_latex" in session.files:
        questions_key = "enhanced_questions_latex"
    else:
        raise HTTPException(
            status_code=400,
            detail="Questions not found. Complete Stage 2 first."
        )

    # Verify marking schemes exist
    if "marking_schemes" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Marking schemes not found. Complete Stage 3 first."
        )

    try:
        # Update session status
        session.status = SessionStatus.PROCESSING
        session.current_stage = 4
        session_manager.update_session(session)

        # Merge
        questions_file = Path(session.files[questions_key])
        marking_schemes_file = Path(session.files["marking_schemes"])
        session_dir = session_manager.get_session_dir(session_id)
        merged_file = session_dir / "merged.json"

        merged_questions, merge_stats = merge_files(
            questions_file, marking_schemes_file, merged_file
        )

        # Update session with output files
        session.files["merged"] = str(merged_file)
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        return {
            "merged_url": f"/api/sessions/{session_id}/stage4/merged",
            "stats": merge_stats,
            "questions": merged_questions
        }

    except Exception as e:
        # Update session with error
        session.status = SessionStatus.ERROR
        session.error = str(e)
        session_manager.update_session(session)

        raise HTTPException(
            status_code=500,
            detail=f"Merge failed: {str(e)}"
        )


@router.get("/merged")
async def get_merged_data(session_id: str):
    """
    Get merged questions with marking schemes.

    Args:
        session_id: Session identifier

    Returns:
        Merged questions list
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if merged data exists
    if "merged" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Merged data not found. Run merge first."
        )

    try:
        file_path = Path(session.files["merged"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Merged file not found on disk")

        # Read and return JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            merged_data = json.load(f)
        return merged_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read merged file: {str(e)}"
        )


@router.get("/statistics")
async def get_merge_statistics(session_id: str):
    """
    Get detailed merge statistics.

    Args:
        session_id: Session identifier

    Returns:
        Statistics about the merge
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if merged data exists
    if "merged" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Merged data not found. Run merge first."
        )

    try:
        file_path = Path(session.files["merged"])
        with open(file_path, 'r', encoding='utf-8') as f:
            merged_data = json.load(f)

        # Calculate statistics
        total_questions = len(merged_data)
        total_parts = 0
        parts_with_schemes = 0
        total_marks = 0

        def count_parts(parts):
            nonlocal total_parts, parts_with_schemes
            for part in parts:
                # Only count parts that have marks (actual question parts, not containers)
                if part.get('marks') is not None:
                    total_parts += 1
                    if part.get('markingScheme'):
                        parts_with_schemes += 1
                # Still recurse into nested parts
                if part.get('parts'):
                    count_parts(part['parts'])

        for question in merged_data:
            count_parts(question['parts'])
            total_marks += question.get('totalMarks', 0) or 0

        return {
            "total_questions": total_questions,
            "total_parts": total_parts,
            "parts_with_schemes": parts_with_schemes,
            "parts_without_schemes": total_parts - parts_with_schemes,
            "coverage_percentage": (parts_with_schemes / total_parts * 100) if total_parts > 0 else 0,
            "total_marks": total_marks
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate statistics: {str(e)}"
        )


@router.put("/merged")
async def update_merged_data(
    session_id: str,
    questions: List[Dict[str, Any]]
):
    """
    Update merged data with user edits.

    Args:
        session_id: Session identifier
        questions: Updated questions list

    Returns:
        Success message with statistics
    """
    print(f"[DEBUG] Received update_merged_data request for session: {session_id}")
    print(f"[DEBUG] Questions type: {type(questions)}")
    print(f"[DEBUG] Questions length: {len(questions) if isinstance(questions, list) else 'N/A'}")
    print(f"[DEBUG] First question sample: {questions[0] if questions else 'Empty'}")

    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if merged data exists
    if "merged" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Merged data not found. Run merge first."
        )

    try:
        file_path = Path(session.files["merged"])

        # Save updated data
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        # Calculate statistics
        total_questions = len(questions)
        total_parts = 0
        parts_with_schemes = 0

        def count_parts(parts):
            nonlocal total_parts, parts_with_schemes
            for part in parts:
                # Only count parts that have marks (actual question parts, not containers)
                if part.get('marks') is not None:
                    total_parts += 1
                    if part.get('markingScheme'):
                        parts_with_schemes += 1
                # Still recurse into nested parts
                if part.get('parts'):
                    count_parts(part['parts'])

        for question in questions:
            count_parts(question['parts'])

        return {
            "message": "Merged data updated successfully",
            "stats": {
                "total_questions": total_questions,
                "total_parts": total_parts,
                "parts_with_schemes": parts_with_schemes,
                "coverage_percentage": (parts_with_schemes / total_parts * 100) if total_parts > 0 else 0
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update merged data: {str(e)}"
        )


@router.get("/download")
async def download_merged_data(session_id: str):
    """
    Download merged JSON file.

    Args:
        session_id: Session identifier

    Returns:
        File download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if merged data exists
    if "merged" not in session.files:
        raise HTTPException(
            status_code=404,
            detail="Merged data not found. Run merge first."
        )

    try:
        file_path = Path(session.files["merged"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            path=file_path,
            filename="merged.json",
            media_type="application/json"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
