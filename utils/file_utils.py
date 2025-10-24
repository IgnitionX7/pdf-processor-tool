import os
import aiofiles
from pathlib import Path
from fastapi import UploadFile, HTTPException
from config import settings


async def save_upload_file(upload_file: UploadFile, destination: Path) -> int:
    """
    Save an uploaded file to disk.

    Args:
        upload_file: The uploaded file from FastAPI
        destination: Path where to save the file

    Returns:
        Size of the saved file in bytes

    Raises:
        HTTPException: If file size exceeds limit or save fails
    """
    try:
        # Create parent directories if they don't exist
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Save file in chunks to handle large files
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        async with aiofiles.open(destination, 'wb') as f:
            while chunk := await upload_file.read(chunk_size):
                file_size += len(chunk)

                # Check file size limit
                if file_size > settings.max_file_size:
                    # Clean up partial file
                    await f.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {settings.max_file_size} bytes"
                    )

                await f.write(chunk)

        return file_size

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )


def validate_pdf_file(filename: str) -> None:
    """
    Validate that uploaded file is a PDF.

    Args:
        filename: Name of the uploaded file

    Raises:
        HTTPException: If file is not a PDF
    """
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes."""
    return file_path.stat().st_size / (1024 * 1024)
