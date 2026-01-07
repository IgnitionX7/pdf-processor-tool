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

# Import combined pipeline
from combined_pipeline import CombinedPipeline

router = APIRouter(prefix="/api/sessions/{session_id}/enhanced", tags=["enhanced"])


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
        session.status = SessionStatus.PROCESSING
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
    Process PDF using the combined extraction pipeline.
    Extracts figures, tables, and questions with LaTeX support.

    Args:
        session_id: Session identifier

    Returns:
        Processing results with statistics
    """
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

    try:
        # Update session status
        session.status = SessionStatus.PROCESSING
        session.current_stage = 1
        session_manager.update_session(session)

        # Set up pipeline
        pdf_path = Path(session.files["enhanced_pdf"])
        session_dir = session_manager.get_session_dir(session_id)
        output_dir = session_dir / "enhanced"

        pipeline = CombinedPipeline(
            output_dir=str(output_dir),
            skip_first_page=True,
            dpi=300,
            caption_figure_padding=0.0,
            visual_figure_padding=20.0,
            enable_noise_removal=True
        )

        # Process PDF
        result = pipeline.process_pdf(str(pdf_path))

        # Store paths in session
        pdf_stem = pdf_path.stem
        figures_dir = output_dir / pdf_stem / "figures"
        text_dir = output_dir / pdf_stem / "text"

        session.files["enhanced_figures_dir"] = str(figures_dir)
        session.files["enhanced_text_dir"] = str(text_dir)
        session.files["enhanced_metadata"] = str(figures_dir / "extraction_metadata.json")
        session.files["enhanced_questions_latex"] = str(text_dir / f"{pdf_stem}_questions_latex.json")
        session.files["enhanced_questions_plain"] = str(text_dir / f"{pdf_stem}_questions_plain.json")

        session.status = SessionStatus.COMPLETED
        session_manager.update_session(session)

        return {
            "message": "PDF processed successfully",
            "statistics": result['statistics'],
            "question_count_latex": result['question_results']['latex_count'],
            "question_count_plain": result['question_results']['plain_count'],
            "figures_tables_url": f"/api/sessions/{session_id}/enhanced/figures-tables",
            "questions_url": f"/api/sessions/{session_id}/enhanced/questions-latex"
        }

    except Exception as e:
        # Update session with error
        session.status = SessionStatus.ERROR
        session.error = str(e)
        session_manager.update_session(session)

        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(e)}"
        )


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
