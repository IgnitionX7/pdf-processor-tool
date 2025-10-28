"""
Figure & Table Extractor Routes
Handles PDF upload and extraction of figures and tables
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from typing import Dict, Any
import json
import uuid
import shutil
import zipfile
import io

from config import settings
from utils.file_utils import save_upload_file, validate_pdf_file

router = APIRouter(prefix="/api/figure-extractor", tags=["figure-extractor"])


@router.post("/extract")
async def extract_figures_tables(file: UploadFile = File(...)):
    """
    Extract figures and tables from uploaded PDF.

    Args:
        file: PDF file to process

    Returns:
        Extraction results with list of extracted images
    """
    # Validate file
    validate_pdf_file(file.filename)

    # Create temporary working directory
    work_id = str(uuid.uuid4())
    work_dir = settings.upload_path / "figure_extractor" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save uploaded PDF
        pdf_path = work_dir / "input.pdf"
        await save_upload_file(file, pdf_path)

        # Create output directory for extracted images
        output_dir = work_dir / "extracted"
        output_dir.mkdir(exist_ok=True)

        # Lazy import to avoid loading heavy dependencies at startup
        from processors.figure_table_extractor import extract_figures_and_tables

        # Extract figures and tables
        results = extract_figures_and_tables(pdf_path, output_dir)

        # Return results with download URLs
        return {
            "work_id": work_id,
            "total_figures": results["total_figures"],
            "total_tables": results["total_tables"],
            "figures": results["figures"],
            "tables": results["tables"],
            "download_url": f"/api/figure-extractor/download/{work_id}",
            "message": f"Extracted {results['total_figures']} figure(s) and {results['total_tables']} table(s)"
        }

    except Exception as e:
        # Clean up on error
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


@router.get("/download/{work_id}")
async def download_extracted_images(work_id: str):
    """
    Download all extracted images as a ZIP file.

    Args:
        work_id: Work identifier from extraction

    Returns:
        ZIP file containing all extracted images
    """
    work_dir = settings.upload_path / "figure_extractor" / work_id / "extracted"

    if not work_dir.exists():
        raise HTTPException(status_code=404, detail="Extraction results not found")

    try:
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all images to ZIP
            for image_file in work_dir.glob("*.png"):
                zip_file.write(image_file, image_file.name)

        # Reset buffer position
        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=extracted_images_{work_id}.zip"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create download: {str(e)}"
        )


@router.get("/image/{work_id}/{filename}")
async def get_extracted_image(work_id: str, filename: str):
    """
    Get a specific extracted image.

    Args:
        work_id: Work identifier from extraction
        filename: Image filename

    Returns:
        Image file
    """
    work_dir = settings.upload_path / "figure_extractor" / work_id / "extracted"
    image_path = work_dir / filename

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=filename
    )


@router.delete("/cleanup/{work_id}")
async def cleanup_extraction(work_id: str):
    """
    Clean up extraction files.

    Args:
        work_id: Work identifier from extraction

    Returns:
        Success message
    """
    work_dir = settings.upload_path / "figure_extractor" / work_id

    if not work_dir.exists():
        raise HTTPException(status_code=404, detail="Work directory not found")

    try:
        shutil.rmtree(work_dir)
        return {"message": "Cleanup successful"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )
