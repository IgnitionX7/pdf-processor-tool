"""
Enhanced Combined Extractor Routes
Handles PDF processing using the combined-extractor pipeline
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any
import json
import sys
import shutil
import base64
import asyncio
import logging

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Import SessionStatus and session_manager
# Check if we're running from root main.py (Vercel) or backend/app/main.py
# by checking if 'models' is available as a top-level module
import importlib.util
if importlib.util.find_spec("models") is not None and importlib.util.find_spec("utils.session_manager") is not None:
    # Running from root main.py - use absolute imports
    from models import SessionStatus
    from utils.session_manager import session_manager
else:
    # Running from backend/app/main.py - use relative imports
    from ..models import SessionStatus
    from ..utils.session_manager import session_manager

# Add combined-extractor to path - it's a sibling directory to routes
# backend/app/routes/enhanced_extractor.py -> backend/app/
backend_app_dir = Path(__file__).parent.parent
combined_extractor_path = backend_app_dir / "combined-extractor"
if str(combined_extractor_path) not in sys.path:
    # Insert at the beginning so it takes priority
    sys.path.insert(0, str(combined_extractor_path))

# Now import - the modules within combined-extractor use relative imports
from combined_pipeline import CombinedPipeline

router = APIRouter(prefix="/api/sessions/{session_id}/enhanced", tags=["enhanced"])

# Keep track of background tasks to prevent garbage collection
background_tasks = set()


def process_pdf_background(session_id: str, pdf_path: Path, output_dir: Path):
    """
    Background processing function that runs in a separate thread.
    Updates session status as it processes.
    """
    try:
        logger.info(f"Background processing started for session {session_id}")

        # Get session
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return

        # Set up pipeline
        pipeline = CombinedPipeline(
            output_dir=str(output_dir),
            skip_first_page=True,
            dpi=300,
            caption_figure_padding=0.0,
            visual_figure_padding=20.0,
            enable_noise_removal=True
        )

        # Process PDF
        logger.info(f"Processing PDF: {pdf_path.name}")
        result = pipeline.process_pdf(str(pdf_path))
        logger.info(f"Processing complete for: {pdf_path.name}")

        # Store paths in session
        pdf_stem = pdf_path.stem
        figures_dir = output_dir / pdf_stem / "figures"
        text_dir = output_dir / pdf_stem / "text"

        session.files["enhanced_figures_dir"] = str(figures_dir)
        session.files["enhanced_text_dir"] = str(text_dir)
        session.files["enhanced_metadata"] = str(figures_dir / "extraction_metadata.json")
        session.files["enhanced_questions_latex"] = str(text_dir / f"{pdf_stem}_questions_latex.json")
        session.files["enhanced_questions_plain"] = str(text_dir / f"{pdf_stem}_questions_plain.json")

        # Store statistics for status endpoint
        session.files["enhanced_stats"] = json.dumps({
            "statistics": result['statistics'],
            "question_count_latex": result['question_results']['latex_count'],
            "question_count_plain": result['question_results']['plain_count']
        })

        # Mark as completed
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        logger.info(f"Background processing completed for session {session_id}")

    except Exception as e:
        logger.error(f"Background processing failed: {str(e)}", exc_info=True)

        # Update session with error
        session = session_manager.get_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            session_manager.update_session(session)


@router.post("/upload-pdf")
async def upload_pdf(session_id: str, file: UploadFile = File(...)):
    """
    Upload question paper PDF for enhanced extraction.

    Args:
        session_id: Session identifier
        file: PDF file to upload

    Returns:
        Upload confirmation with file path
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify file is PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        # Save PDF to session directory
        session_dir = session_manager.get_session_dir(session_id)
        enhanced_dir = session_dir / "enhanced"
        enhanced_dir.mkdir(exist_ok=True)

        pdf_path = enhanced_dir / "question_paper.pdf"

        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update session
        session.files["enhanced_pdf"] = str(pdf_path)
        # Don't set to PROCESSING here - that happens when /process is called
        session_manager.update_session(session)

        return {
            "message": "PDF uploaded successfully",
            "filename": file.filename,
            "path": str(pdf_path)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )


@router.post("/process")
async def process_pdf(session_id: str):
    """
    Start PDF processing in background (returns immediately).
    Use /status endpoint to poll for completion.

    This avoids Render's 30-second timeout by returning immediately
    and processing in a background thread.

    Args:
        session_id: Session identifier

    Returns:
        Status URL for polling
    """
    logger.info(f"Processing request for session: {session_id}")

    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify PDF exists
    if "enhanced_pdf" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="PDF not found. Upload a PDF first."
        )

    # Check if already processing
    if session.status == SessionStatus.PROCESSING:
        return {
            "message": "Processing already in progress",
            "status": "processing",
            "status_url": f"/api/sessions/{session_id}/enhanced/status"
        }

    # Update session status to processing
    session.status = SessionStatus.PROCESSING
    session.current_stage = 1
    session_manager.update_session(session)

    # Get paths
    pdf_path = Path(session.files["enhanced_pdf"])
    session_dir = session_manager.get_session_dir(session_id)
    output_dir = session_dir / "enhanced"

    # Start background processing (non-blocking)
    # Keep reference to task to prevent garbage collection
    logger.info(f"Creating background task for session {session_id}")
    logger.info(f"PDF path: {pdf_path}, Output dir: {output_dir}")

    async def run_background_with_logging():
        """Wrapper to add logging around background task"""
        try:
            logger.info(f"[WRAPPER] Starting background task for {session_id}")
            await asyncio.to_thread(process_pdf_background, session_id, pdf_path, output_dir)
            logger.info(f"[WRAPPER] Background task completed for {session_id}")
        except Exception as e:
            logger.error(f"[WRAPPER] Background task failed for {session_id}: {e}", exc_info=True)

    task = asyncio.create_task(run_background_with_logging())

    # Store task reference and clean up when done
    background_tasks.add(task)
    task.add_done_callback(lambda t: (background_tasks.discard(t), logger.info(f"Task done callback for {session_id}")))

    logger.info(f"Background task created for session {session_id}, tasks in set: {len(background_tasks)}")

    return {
        "message": "Processing started in background",
        "status": "processing",
        "status_url": f"/api/sessions/{session_id}/enhanced/status"
    }


@router.get("/status")
async def get_processing_status(session_id: str):
    """
    Get current processing status (for polling).

    Args:
        session_id: Session identifier

    Returns:
        Current status and results if completed
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    response = {
        "status": session.status.value if hasattr(session.status, 'value') else str(session.status),
        "current_stage": session.current_stage
    }

    # If completed, include results
    if session.status == SessionStatus.COMPLETED and "enhanced_stats" in session.files:
        try:
            stats = json.loads(session.files["enhanced_stats"])
            response.update({
                "message": "Processing completed successfully",
                "statistics": stats.get("statistics", {}),
                "question_count_latex": stats.get("question_count_latex", 0),
                "question_count_plain": stats.get("question_count_plain", 0),
                "figures_tables_url": f"/api/sessions/{session_id}/enhanced/figures-tables",
                "questions_url": f"/api/sessions/{session_id}/enhanced/questions-latex"
            })
        except Exception as e:
            logger.error(f"Failed to parse stats: {e}")
            response["message"] = "Processing completed"

    # If error, include error message
    elif session.status == SessionStatus.ERROR:
        response["error"] = session.error or "Unknown error occurred"

    # If still processing
    elif session.status == SessionStatus.PROCESSING:
        response["message"] = "Processing in progress..."

    return response


@router.get("/figures-tables")
async def get_figures_tables(session_id: str):
    """
    Get extracted figures and tables with metadata.

    Args:
        session_id: Session identifier

    Returns:
        List of extracted elements with base64 image data
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify metadata exists
    if "enhanced_metadata" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="No extraction data found. Process a PDF first."
        )

    try:
        metadata_path = Path(session.files["enhanced_metadata"])
        figures_dir = Path(session.files["enhanced_figures_dir"])

        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Add base64 image data for each element (Vercel-friendly)
        for element in metadata['elements']:
            image_path = figures_dir / element['filename']
            if image_path.exists():
                with open(image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    element['imageData'] = f"data:image/png;base64,{image_data}"

        return {
            "elements": metadata['elements'],
            "total_count": len(metadata['elements']),
            "figures_count": sum(1 for e in metadata['elements'] if e['type'] == 'figure'),
            "tables_count": sum(1 for e in metadata['elements'] if e['type'] == 'table')
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load figures/tables: {str(e)}"
        )


@router.get("/image/{filename}")
async def get_image(session_id: str, filename: str):
    """
    Get individual extracted image.

    Args:
        session_id: Session identifier
        filename: Image filename

    Returns:
        Image file
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if "enhanced_figures_dir" not in session.files:
        raise HTTPException(status_code=400, detail="No extraction data found")

    try:
        figures_dir = Path(session.files["enhanced_figures_dir"])
        image_path = figures_dir / filename

        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load image: {str(e)}"
        )


@router.get("/questions-latex")
async def get_questions_latex(session_id: str):
    """
    Get extracted questions (LaTeX version).

    Args:
        session_id: Session identifier

    Returns:
        List of extracted questions with LaTeX notation
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify questions exist
    if "enhanced_questions_latex" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Questions not found. Process a PDF first."
        )

    try:
        questions_path = Path(session.files["enhanced_questions_latex"])

        if not questions_path.exists():
            raise HTTPException(status_code=404, detail="Questions file not found")

        with open(questions_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        return {
            "questions": questions,
            "total_count": len(questions)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load questions: {str(e)}"
        )


@router.put("/questions-latex")
async def update_questions_latex(session_id: str, questions: List[Dict[str, Any]]):
    """
    Update extracted questions (LaTeX version).

    Args:
        session_id: Session identifier
        questions: Updated questions list

    Returns:
        Update confirmation
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify questions file exists
    if "enhanced_questions_latex" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Questions not found. Process a PDF first."
        )

    try:
        questions_path = Path(session.files["enhanced_questions_latex"])

        # Save updated questions
        with open(questions_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        return {
            "message": "Questions updated successfully",
            "total_count": len(questions)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update questions: {str(e)}"
        )


@router.get("/download/questions")
async def download_questions(session_id: str):
    """
    Download questions as JSON file.

    Args:
        session_id: Session identifier

    Returns:
        JSON file download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify questions exist
    if "enhanced_questions_latex" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Questions not found. Process a PDF first."
        )

    try:
        questions_path = Path(session.files["enhanced_questions_latex"])

        if not questions_path.exists():
            raise HTTPException(status_code=404, detail="Questions file not found")

        return FileResponse(
            path=str(questions_path),
            media_type="application/json",
            filename="questions_latex.json"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download questions: {str(e)}"
        )


@router.get("/download/figures-zip")
async def download_figures_zip(session_id: str):
    """
    Download all figures and tables as ZIP file.

    Args:
        session_id: Session identifier

    Returns:
        ZIP file download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify figures directory exists
    if "enhanced_figures_dir" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="No extraction data found. Process a PDF first."
        )

    try:
        import zipfile
        from io import BytesIO

        figures_dir = Path(session.files["enhanced_figures_dir"])

        # Create ZIP in memory
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all PNG files
            for image_path in figures_dir.glob("*.png"):
                zip_file.write(image_path, arcname=image_path.name)

            # Add metadata JSON
            metadata_path = figures_dir / "extraction_metadata.json"
            if metadata_path.exists():
                zip_file.write(metadata_path, arcname="extraction_metadata.json")

        # Prepare for download
        zip_buffer.seek(0)

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=figures_tables.zip"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP file: {str(e)}"
        )
