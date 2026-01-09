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


def process_phase1_background(session_id: str, pdf_path: Path, output_dir: Path):
    """
    Phase 1 background processing: Extract figures and tables only (NO text extraction).

    Args:
        session_id: Session identifier
        pdf_path: Path to PDF file
        output_dir: Output directory
    """
    try:
        logger.info(f"Phase 1 processing started for session {session_id}")

        # Get session
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return

        # Set up pipeline
        pipeline = CombinedPipeline(
            output_dir=str(output_dir),
            skip_first_page=True,
            dpi=200,
            caption_figure_padding=0.0,
            visual_figure_padding=20.0,
            enable_noise_removal=True
        )

        # Run Phase 1 only
        logger.info(f"Extracting figures/tables from: {pdf_path.name}")
        result = pipeline.phase1_extract_figures_and_tables(str(pdf_path))
        logger.info(f"Phase 1 complete for: {pdf_path.name}")

        # Store paths in session
        pdf_stem = pdf_path.stem
        figures_dir = output_dir / pdf_stem / "figures"

        session.files["enhanced_figures_dir"] = str(figures_dir)
        session.files["enhanced_metadata"] = str(figures_dir / "extraction_metadata.json")
        session.files["enhanced_output_dir"] = result["output_dir"]

        # Store Phase 1 statistics
        session.files["enhanced_phase1_stats"] = json.dumps({
            "statistics": result['statistics'],
            "figure_results": result['figure_results']
        })

        # Mark as completed
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        logger.info(f"Phase 1 completed for session {session_id}")

    except Exception as e:
        logger.error(f"Phase 1 processing failed: {str(e)}", exc_info=True)

        # Update session with error
        session = session_manager.get_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            session_manager.update_session(session)


def process_phase2_background(session_id: str, pdf_path: Path, output_dir: Path,
                              metadata_file: Path, exclude_figures: bool = True,
                              exclude_tables: bool = True):
    """
    Phase 2 background processing: Extract text using saved metadata with exclusion zones.

    Args:
        session_id: Session identifier
        pdf_path: Path to PDF file
        output_dir: Output directory
        metadata_file: Path to extraction_metadata.json from Phase 1
        exclude_figures: Whether to exclude figure regions from text extraction
        exclude_tables: Whether to exclude table regions from text extraction
    """
    try:
        logger.info(f"Phase 2 processing started for session {session_id}")
        logger.info(f"Exclusion settings - Figures: {exclude_figures}, Tables: {exclude_tables}")

        # Get session
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return

        # Set up pipeline
        pipeline = CombinedPipeline(
            output_dir=str(output_dir),
            skip_first_page=True,
            dpi=200,
            caption_figure_padding=0.0,
            visual_figure_padding=20.0,
            enable_noise_removal=True
        )

        # Run Phase 2
        logger.info(f"Extracting text from: {pdf_path.name}")
        result = pipeline.phase2_extract_text_with_exclusions(
            str(pdf_path),
            str(metadata_file),
            exclude_figures=exclude_figures,
            exclude_tables=exclude_tables
        )
        logger.info(f"Phase 2 complete for: {pdf_path.name}")

        # Store paths in session
        pdf_stem = pdf_path.stem
        text_dir = output_dir / pdf_stem / "text"

        session.files["enhanced_text_dir"] = str(text_dir)
        session.files["enhanced_extracted_text"] = result["text_file"]
        session.files["enhanced_questions_latex"] = result.get("questions_file", "")
        session.files["enhanced_questions_plain"] = str(text_dir / f"{pdf_stem}_questions_plain.json")

        # Merge Phase 1 and Phase 2 statistics
        phase1_stats = {}
        if "enhanced_phase1_stats" in session.files:
            try:
                phase1_stats = json.loads(session.files["enhanced_phase1_stats"])
            except json.JSONDecodeError:
                pass

        session.files["enhanced_stats"] = json.dumps({
            **phase1_stats,
            "text_statistics": result['statistics'],
            "question_count_latex": result['question_results']['latex_count'],
            "question_count_plain": result['question_results']['plain_count'],
            "exclusion_settings": {
                "exclude_figures": exclude_figures,
                "exclude_tables": exclude_tables
            }
        })

        # Mark as completed
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        logger.info(f"Phase 2 completed for session {session_id}")

    except Exception as e:
        logger.error(f"Phase 2 processing failed: {str(e)}", exc_info=True)

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

        # Update session - store both path and original filename
        session.files["enhanced_pdf"] = str(pdf_path)
        session.files["enhanced_pdf_name"] = file.filename  # Store original filename
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
    Phase 1: Start figure/table extraction in background (returns immediately).
    NO text extraction occurs in this phase.

    After completion, user should review figures and call /extract-text endpoint.
    Use /status endpoint to poll for completion.

    Args:
        session_id: Session identifier

    Returns:
        Status URL for polling
    """
    logger.info(f"Phase 1 processing request for session: {session_id}")

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
            "message": "Phase 1 processing already in progress",
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

    # Start Phase 1 background processing (non-blocking)
    logger.info(f"Creating Phase 1 background task for session {session_id}")
    logger.info(f"PDF path: {pdf_path}, Output dir: {output_dir}")

    async def run_background_with_logging():
        """Wrapper to add logging around background task"""
        try:
            logger.info(f"[WRAPPER] Starting Phase 1 task for {session_id}")
            await asyncio.to_thread(process_phase1_background, session_id, pdf_path, output_dir)
            logger.info(f"[WRAPPER] Phase 1 task completed for {session_id}")
        except Exception as e:
            logger.error(f"[WRAPPER] Phase 1 task failed for {session_id}: {e}", exc_info=True)

    task = asyncio.create_task(run_background_with_logging())

    # Store task reference and clean up when done
    background_tasks.add(task)
    task.add_done_callback(lambda t: (background_tasks.discard(t), logger.info(f"Phase 1 task done callback for {session_id}")))

    logger.info(f"Background task created for session {session_id}, tasks in set: {len(background_tasks)}")

    return {
        "message": "Phase 1 processing started in background",
        "status": "processing",
        "status_url": f"/api/sessions/{session_id}/enhanced/status"
    }


@router.post("/extract-text")
async def extract_text(
    session_id: str,
    exclude_figures: bool = True,
    exclude_tables: bool = True
):
    """
    Phase 2: Extract text using saved metadata with user-chosen exclusion zones.

    Must be called after /process endpoint completes (Phase 1).
    Use /status endpoint to poll for completion.

    Args:
        session_id: Session identifier
        exclude_figures: Whether to exclude figure regions from text extraction
        exclude_tables: Whether to exclude table regions from text extraction

    Returns:
        Status URL for polling
    """
    logger.info(f"Phase 2 processing request for session: {session_id}")
    logger.info(f"Exclusion settings - Figures: {exclude_figures}, Tables: {exclude_tables}")

    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify Phase 1 completed
    if "enhanced_metadata" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Phase 1 not completed. Run /process endpoint first to extract figures/tables."
        )

    # Verify PDF exists
    if "enhanced_pdf" not in session.files:
        raise HTTPException(status_code=400, detail="PDF not found")

    # Check if already processing
    if session.status == SessionStatus.PROCESSING:
        return {
            "message": "Phase 2 processing already in progress",
            "status": "processing",
            "status_url": f"/api/sessions/{session_id}/enhanced/status"
        }

    # Update session status to processing
    session.status = SessionStatus.PROCESSING
    session.current_stage = 2
    session_manager.update_session(session)

    # Get paths
    pdf_path = Path(session.files["enhanced_pdf"])
    metadata_file = Path(session.files["enhanced_metadata"])
    output_dir = Path(session.files["enhanced_output_dir"])

    # Start Phase 2 background processing (non-blocking)
    logger.info(f"Creating Phase 2 background task for session {session_id}")

    async def run_background_with_logging():
        """Wrapper to add logging around background task"""
        try:
            logger.info(f"[WRAPPER] Starting Phase 2 task for {session_id}")
            await asyncio.to_thread(
                process_phase2_background,
                session_id,
                pdf_path,
                output_dir,
                metadata_file,
                exclude_figures,
                exclude_tables
            )
            logger.info(f"[WRAPPER] Phase 2 task completed for {session_id}")
        except Exception as e:
            logger.error(f"[WRAPPER] Phase 2 task failed for {session_id}: {e}", exc_info=True)

    task = asyncio.create_task(run_background_with_logging())

    # Store task reference and clean up when done
    background_tasks.add(task)
    task.add_done_callback(lambda t: (background_tasks.discard(t), logger.info(f"Phase 2 task done callback for {session_id}")))

    logger.info(f"Phase 2 task created for session {session_id}, tasks in set: {len(background_tasks)}")

    return {
        "message": "Phase 2 (text extraction) started in background",
        "status": "processing",
        "status_url": f"/api/sessions/{session_id}/enhanced/status",
        "exclusion_settings": {
            "exclude_figures": exclude_figures,
            "exclude_tables": exclude_tables
        }
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


@router.get("/extracted-text")
async def get_extracted_text(session_id: str):
    """
    Get extracted text (LaTeX formatted).

    Args:
        session_id: Session identifier

    Returns:
        Extracted text with statistics
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify text file exists
    if "enhanced_extracted_text" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Extracted text not found. Process a PDF first."
        )

    try:
        text_path = Path(session.files["enhanced_extracted_text"])

        if not text_path.exists():
            raise HTTPException(status_code=404, detail="Text file not found")

        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read()

        # Calculate statistics
        char_count = len(text_content)
        line_count = len(text_content.split('\n'))

        return {
            "text": text_content,
            "char_count": char_count,
            "line_count": line_count
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load extracted text: {str(e)}"
        )


@router.put("/extracted-text")
async def update_extracted_text(session_id: str, data: Dict[str, str]):
    """
    Update extracted text.

    Args:
        session_id: Session identifier
        data: Dictionary with 'text' key containing the updated text

    Returns:
        Update confirmation
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify text file exists
    if "enhanced_extracted_text" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Extracted text not found. Process a PDF first."
        )

    try:
        text_path = Path(session.files["enhanced_extracted_text"])
        text_content = data.get("text", "")

        # Save updated text
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        return {
            "message": "Text updated successfully",
            "char_count": len(text_content)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update text: {str(e)}"
        )


@router.get("/download/extracted-text")
async def download_extracted_text(session_id: str):
    """
    Download extracted text as TXT file.

    Args:
        session_id: Session identifier

    Returns:
        TXT file download
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify text file exists
    if "enhanced_extracted_text" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Extracted text not found. Process a PDF first."
        )

    try:
        text_path = Path(session.files["enhanced_extracted_text"])

        if not text_path.exists():
            raise HTTPException(status_code=404, detail="Text file not found")

        # Get original PDF filename to use in text filename
        original_pdf_name = session.files.get("enhanced_pdf_name", "question_paper.pdf")
        pdf_stem = Path(original_pdf_name).stem
        text_filename = f"{pdf_stem}_extracted_text.txt"

        return FileResponse(
            path=str(text_path),
            media_type="text/plain",
            filename=text_filename
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download text: {str(e)}"
        )


def extract_questions_background(session_id: str, text_path: Path, text_dir: Path, pdf_stem: str):
    """
    Background function to extract questions from current text file.

    Args:
        session_id: Session identifier
        text_path: Path to the text file to extract questions from
        text_dir: Directory to save question results
        pdf_stem: PDF filename stem for output naming
    """
    try:
        logger.info(f"Question extraction started for session {session_id}")

        # Get session
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return

        # Import question extraction function
        from extractors.question_extractor import extract_questions_from_text

        # Read the current text file
        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read()

        # Create cleaned text file in the format expected by question extractor
        # The question extractor expects page separators
        cleaned_text_file = text_dir / f"{pdf_stem}_cleaned_latex.txt"
        with open(cleaned_text_file, 'w', encoding='utf-8') as f:
            # If the text doesn't have page separators, add a single page
            if "==================== CLEANED PAGE" not in text_content:
                f.write(f"==================== CLEANED PAGE 1 ====================\n\n")
                f.write(text_content)
            else:
                # Already has page separators
                f.write(text_content)

        logger.info(f"Extracting questions from: {cleaned_text_file}")

        # Extract questions
        latex_json_output = text_dir / f"{pdf_stem}_questions_latex.json"
        latex_questions = extract_questions_from_text(cleaned_text_file, latex_json_output)

        # Update session with new question count
        question_count = len(latex_questions)
        logger.info(f"Extracted {question_count} questions")

        # Update session files
        session.files["enhanced_questions_latex"] = str(latex_json_output)

        # Update statistics
        if "enhanced_stats" in session.files:
            stats = json.loads(session.files["enhanced_stats"])
            stats["question_count_latex"] = question_count
            session.files["enhanced_stats"] = json.dumps(stats)

        # Mark as completed
        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        logger.info(f"Question extraction completed for session {session_id}")

    except Exception as e:
        logger.error(f"Question extraction failed: {str(e)}", exc_info=True)

        # Update session with error
        session = session_manager.get_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = f"Question extraction failed: {str(e)}"
            session_manager.update_session(session)


@router.post("/extract-questions")
async def extract_questions_from_current_text(session_id: str):
    """
    Re-extract questions from the current (potentially edited) text file.
    This runs in background and can be polled via /status endpoint.

    Args:
        session_id: Session identifier

    Returns:
        Status indicating extraction has started
    """
    logger.info(f"Question extraction request for session: {session_id}")

    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify text file exists
    if "enhanced_extracted_text" not in session.files:
        raise HTTPException(
            status_code=400,
            detail="Extracted text not found. Process a PDF first."
        )

    # Check if already processing
    if session.status == SessionStatus.PROCESSING:
        return {
            "message": "Question extraction already in progress",
            "status": "processing",
            "status_url": f"/api/sessions/{session_id}/enhanced/status"
        }

    try:
        # Get paths
        text_path = Path(session.files["enhanced_extracted_text"])
        text_dir = text_path.parent
        pdf_stem = text_path.stem.replace("_full_latex", "")

        if not text_path.exists():
            raise HTTPException(status_code=404, detail="Text file not found")

        # Update session status to processing
        session.status = SessionStatus.PROCESSING
        session.current_stage = 3  # Question extraction stage
        session_manager.update_session(session)

        # Start background processing
        logger.info(f"Creating background task for question extraction in session {session_id}")

        async def run_extraction_background():
            """Wrapper for background extraction"""
            try:
                logger.info(f"[WRAPPER] Starting question extraction for {session_id}")
                await asyncio.to_thread(extract_questions_background, session_id, text_path, text_dir, pdf_stem)
                logger.info(f"[WRAPPER] Question extraction completed for {session_id}")
            except Exception as e:
                logger.error(f"[WRAPPER] Question extraction failed for {session_id}: {e}", exc_info=True)

        task = asyncio.create_task(run_extraction_background())

        # Store task reference
        background_tasks.add(task)
        task.add_done_callback(lambda t: (background_tasks.discard(t), logger.info(f"Question extraction task done for {session_id}")))

        logger.info(f"Question extraction task created for session {session_id}")

        return {
            "message": "Question extraction started in background",
            "status": "processing",
            "status_url": f"/api/sessions/{session_id}/enhanced/status"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start question extraction: {str(e)}"
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

        # Get original PDF filename to use in questions filename
        original_pdf_name = session.files.get("enhanced_pdf_name", "question_paper.pdf")
        pdf_stem = Path(original_pdf_name).stem
        questions_filename = f"{pdf_stem}_questions_latex.json"

        return FileResponse(
            path=str(questions_path),
            media_type="application/json",
            filename=questions_filename
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

        # Get original PDF filename to use in zip filename
        original_pdf_name = session.files.get("enhanced_pdf_name", "question_paper.pdf")
        pdf_stem = Path(original_pdf_name).stem  # Remove .pdf extension
        zip_filename = f"{pdf_stem}_figures_tables.zip"

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
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP file: {str(e)}"
        )
