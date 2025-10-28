"""
GCS Uploader Routes
Handles uploading images to Google Cloud Storage
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from pathlib import Path
from typing import List, Optional
import uuid
import shutil

from ..config import settings
from ..processors.gcs_uploader import upload_images_to_gcs, save_urls_to_file, VALID_SUBJECTS


router = APIRouter(prefix="/api/gcs-uploader", tags=["gcs-uploader"])


@router.post("/upload")
async def upload_to_gcs(
    subject: str = Form(...),
    paper_folder: str = Form(...),
    files: List[UploadFile] = File(...),
    credentials_path: Optional[str] = Form(None)
):
    """
    Upload images to Google Cloud Storage.

    Args:
        subject: Subject name (Biology, Chemistry, or Physics)
        paper_folder: Paper folder name (format: Subject-Year-paper-Number)
        files: List of image files to upload
        credentials_path: Optional path to GCS credentials (uses env var if not provided)

    Returns:
        Upload results with list of URLs
    """
    # Create temporary working directory
    work_id = str(uuid.uuid4())
    work_dir = settings.upload_path / "gcs_uploader" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save uploaded files to temp directory
        for uploaded_file in files:
            file_path = work_dir / uploaded_file.filename
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)

        # Determine credentials path
        creds_path = None
        if credentials_path:
            creds_path = credentials_path
        else:
            # Check if local credentials file exists
            local_creds = Path(__file__).resolve().parents[3] / "keys" / "gcs-service-account.json"
            if local_creds.exists():
                creds_path = str(local_creds)

        # Upload to GCS
        urls = upload_images_to_gcs(
            subject=subject,
            paper_folder=paper_folder,
            source_dir=work_dir,
            credentials_path=creds_path
        )

        # Save URLs to file
        urls_file = work_dir / "uploaded_urls.txt"
        save_urls_to_file(urls, urls_file)

        return {
            "work_id": work_id,
            "uploaded_count": len(urls),
            "urls": urls,
            "urls_file_url": f"/api/gcs-uploader/urls/{work_id}",
            "message": f"Successfully uploaded {len(urls)} image(s) to GCS"
        }

    except ValueError as e:
        # Clean up on validation error
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Clean up on error
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/urls/{work_id}")
async def get_urls_file(work_id: str):
    """
    Get the URLs text file.

    Args:
        work_id: Work identifier from upload

    Returns:
        Plain text file with URLs
    """
    work_dir = settings.upload_path / "gcs_uploader" / work_id
    urls_file = work_dir / "uploaded_urls.txt"

    if not urls_file.exists():
        raise HTTPException(status_code=404, detail="URLs file not found")

    try:
        content = urls_file.read_text(encoding="utf-8")
        return PlainTextResponse(
            content=content,
            headers={"Content-Disposition": "attachment; filename=uploaded_urls.txt"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read URLs file: {str(e)}"
        )


@router.get("/subjects")
async def get_valid_subjects():
    """
    Get list of valid subjects.

    Returns:
        List of valid subject names
    """
    return {"subjects": VALID_SUBJECTS}


@router.delete("/cleanup/{work_id}")
async def cleanup_upload(work_id: str):
    """
    Clean up upload files.

    Args:
        work_id: Work identifier from upload

    Returns:
        Success message
    """
    work_dir = settings.upload_path / "gcs_uploader" / work_id

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
