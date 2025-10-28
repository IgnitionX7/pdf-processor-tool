"""
Upload figures and tables to Google Cloud Storage bucket.

This module uploads images to a GCS bucket with a specific directory structure
and generates a text file containing URLs of all uploaded images.
"""
import json
import os
import re
from pathlib import Path
from typing import List, Optional
from google.cloud import storage
from google.oauth2 import service_account


# Valid subjects
VALID_SUBJECTS = ['Biology', 'Chemistry', 'Physics']

# Base GCS path configuration
BASE_URL = 'https://storage.googleapis.com/razarotalon-knowledgebase/ol-past-papers/ol-diagrams/'
BUCKET_NAME = 'razarotalon-knowledgebase'
BASE_BLOB_PREFIX = 'ol-past-papers/ol-diagrams/'


def validate_subject(subject: str) -> str:
    """Validate that the subject is one of the allowed subjects."""
    if subject not in VALID_SUBJECTS:
        raise ValueError(f"Invalid subject '{subject}'. Must be one of: {', '.join(VALID_SUBJECTS)}")
    return subject


def validate_paper_folder(paper_folder: str, subject: str) -> str:
    """
    Validate paper folder format: Subject-Year-paper-Number
    Also verify that the subject in the folder name matches the subject argument.
    """
    # Pattern: Subject-Year-paper-Number (e.g., Physics-2025-paper-1)
    pattern = r'^([A-Za-z]+)-(\d{4})-paper-(\d+)$'
    match = re.match(pattern, paper_folder)

    if not match:
        raise ValueError(
            f"Invalid paper folder format '{paper_folder}'. "
            f"Expected format: Subject-Year-paper-Number (e.g., Physics-2025-paper-1)"
        )

    folder_subject = match.group(1)
    year = match.group(2)
    paper_number = match.group(3)

    # Check if subject in folder name matches the subject argument
    if folder_subject != subject:
        raise ValueError(
            f"Subject mismatch: folder name has '{folder_subject}' but subject argument is '{subject}'"
        )

    return paper_folder


def get_gcs_client(credentials_path: Optional[str] = None):
    """
    Initialize and return a GCS client using credentials from:
    1. Provided credentials file path, or
    2. GCS_SERVICE_ACCOUNT_KEY environment variable, or
    3. Default application credentials

    Returns:
        storage.Client: Initialized GCS client
    """
    # Option 1: Use provided credentials file
    if credentials_path:
        print(f"Using credentials from file: {credentials_path}")
        return storage.Client.from_service_account_json(credentials_path)

    # Option 2: Try to use environment variable
    env_creds = os.environ.get('GCS_SERVICE_ACCOUNT_KEY')
    if env_creds:
        print("Using credentials from GCS_SERVICE_ACCOUNT_KEY environment variable")
        try:
            credentials_info = json.loads(env_creds)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            return storage.Client(credentials=credentials, project=credentials_info.get('project_id'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse GCS_SERVICE_ACCOUNT_KEY environment variable: {e}")

    # Option 3: Use default credentials (from GOOGLE_APPLICATION_CREDENTIALS or gcloud)
    print("Using default application credentials")
    return storage.Client()


def get_image_files(source_dir: Path) -> List[Path]:
    """Get all image files from the source directory."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    image_files = [
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if not image_files:
        raise ValueError(f"No image files found in {source_dir}")

    return sorted(image_files)


def upload_images_to_gcs(
    subject: str,
    paper_folder: str,
    source_dir: Path,
    credentials_path: Optional[str] = None
) -> List[str]:
    """
    Upload images to Google Cloud Storage and return list of URLs.

    Args:
        subject: Subject name (Biology, Chemistry, or Physics)
        paper_folder: Paper folder name (e.g., Physics-2025-paper-1)
        source_dir: Directory containing images to upload
        credentials_path: Path to GCS service account credentials JSON file (optional)

    Returns:
        List of URLs of uploaded images
    """
    # Validate inputs
    validate_subject(subject)
    validate_paper_folder(paper_folder, subject)

    # Initialize GCS client (will use env var if credentials_path is None)
    client = get_gcs_client(credentials_path)
    bucket = client.bucket(BUCKET_NAME)

    # Get all image files
    image_files = get_image_files(source_dir)

    print(f"\nFound {len(image_files)} image(s) to upload:")
    for img in image_files:
        print(f"  - {img.name}")

    # Upload each image
    uploaded_urls = []

    print(f"\nUploading to: {subject}/{paper_folder}/")

    for image_file in image_files:
        # Construct blob path: ol-past-papers/ol-diagrams/Subject/Paper-Folder/filename
        blob_name = f"{BASE_BLOB_PREFIX}{subject}/{paper_folder}/{image_file.name}"
        blob = bucket.blob(blob_name)

        # Upload the file
        print(f"  Uploading {image_file.name}...", end='')
        blob.upload_from_filename(str(image_file))
        print(" ✓")

        # Construct the public URL
        url = f"{BASE_URL}{subject}/{paper_folder}/{image_file.name}"
        uploaded_urls.append(url)

    return uploaded_urls


def save_urls_to_file(urls: List[str], output_file: Path) -> None:
    """Save URLs to a text file, one per line."""
    with open(output_file, 'w') as f:
        for url in urls:
            f.write(url + '\n')

    print(f"\n✓ URLs saved to: {output_file}")
