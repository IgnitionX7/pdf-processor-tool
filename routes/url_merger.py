"""
URL Merger Routes
Handles merging image URLs into questions JSON
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
import json
import uuid
import shutil

from config import settings

router = APIRouter(prefix="/api/url-merger", tags=["url-merger"])


@router.post("/merge")
async def merge_urls(
    questions_file: UploadFile = File(...),
    urls_file: UploadFile = File(...)
):
    """
    Merge image URLs into questions JSON.

    Args:
        questions_file: JSON file containing questions
        urls_file: Text file containing image URLs (one per line)

    Returns:
        Merged JSON with download URL
    """
    # Validate file extensions
    if not questions_file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Questions file must be a JSON file")

    if not urls_file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="URLs file must be a TXT file")

    # Create temporary working directory
    work_id = str(uuid.uuid4())
    work_dir = settings.upload_path / "url_merger" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Read uploaded files
        questions_content = (await questions_file.read()).decode('utf-8')
        urls_content = (await urls_file.read()).decode('utf-8')

        # Lazy import to avoid loading heavy dependencies at startup
        from processors.url_merger import (
            load_urls_from_string,
            load_questions_from_string,
            merge_urls_to_questions,
            save_merged_json
        )

        # Parse inputs
        questions_data = load_questions_from_string(questions_content)
        urls = load_urls_from_string(urls_content)

        # Merge URLs into questions
        merged_data = merge_urls_to_questions(questions_data, urls)

        # Save merged result
        output_filename = questions_file.filename.replace('.json', '_merged.json')
        output_path = work_dir / output_filename
        save_merged_json(merged_data, output_path)

        return {
            "work_id": work_id,
            "output_filename": output_filename,
            "merged_data": merged_data,
            "download_url": f"/api/url-merger/download/{work_id}/{output_filename}",
            "message": "URLs merged successfully into questions"
        }

    except json.JSONDecodeError as e:
        # Clean up on JSON parse error
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON format: {str(e)}"
        )

    except Exception as e:
        # Clean up on error
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Merge failed: {str(e)}"
        )


@router.get("/download/{work_id}/{filename}")
async def download_merged_json(work_id: str, filename: str):
    """
    Download the merged JSON file.

    Args:
        work_id: Work identifier from merge
        filename: Output filename

    Returns:
        JSON file download
    """
    work_dir = settings.upload_path / "url_merger" / work_id
    file_path = work_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Merged file not found")

    return FileResponse(
        path=file_path,
        media_type="application/json",
        filename=filename
    )


@router.get("/preview/{work_id}/{filename}")
async def preview_merged_json(work_id: str, filename: str):
    """
    Preview the merged JSON content.

    Args:
        work_id: Work identifier from merge
        filename: Output filename

    Returns:
        JSON content
    """
    work_dir = settings.upload_path / "url_merger" / work_id
    file_path = work_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Merged file not found")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read merged file: {str(e)}"
        )


@router.delete("/cleanup/{work_id}")
async def cleanup_merge(work_id: str):
    """
    Clean up merge files.

    Args:
        work_id: Work identifier from merge

    Returns:
        Success message
    """
    work_dir = settings.upload_path / "url_merger" / work_id

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
