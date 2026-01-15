#!/usr/bin/env python3
"""
Upload figures and tables to Google Cloud Storage bucket.

This script uploads images to a GCS bucket with a specific directory structure
and generates a text file containing URLs of all uploaded images.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account


# Valid subjects
VALID_SUBJECTS = ['Biology', 'Chemistry', 'Physics', 'PakistanStudies']

# Base GCS path configuration
BASE_URL = 'https://storage.googleapis.com/razarotalon-knowledgebase/ol-past-papers/ol-diagrams/'
BUCKET_NAME = 'razarotalon-knowledgebase'
BASE_BLOB_PREFIX = 'ol-past-papers/ol-diagrams/'


def validate_subject(subject):
    """Validate that the subject is one of the allowed subjects."""
    if subject not in VALID_SUBJECTS:
        raise ValueError(f"Invalid subject '{subject}'. Must be one of: {', '.join(VALID_SUBJECTS)}")
    return subject


def validate_paper_folder(paper_folder, subject):
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


def get_gcs_client(credentials_path=None):
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


def get_image_files(source_dir):
    """Get all image files from the source directory."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}
    source_path = Path(source_dir)

    if not source_path.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    if not source_path.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    image_files = [
        f for f in source_path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if not image_files:
        raise ValueError(f"No image files found in {source_dir}")

    return sorted(image_files)


def upload_images_to_gcs(subject, paper_folder, source_dir, credentials_path):
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
        # Replace https://storage.googleapis.com/razarotalon-knowledgebase with gs://razarotalon-knowledgebase
        url = url.replace('https://storage.googleapis.com/razarotalon-knowledgebase', 'gs://razarotalon-knowledgebase')
        uploaded_urls.append(url)

    return uploaded_urls


def save_urls_to_file(urls, output_file):
    """Save URLs to a text file, one per line."""
    with open(output_file, 'w') as f:
        for url in urls:
            f.write(url + '\n')

    print(f"\n✓ URLs saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Upload figures and tables to GCS bucket',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable (GCS_SERVICE_ACCOUNT_KEY)
  python upload_figures_to_gcs.py Biology Biology-2025-paper-1 ./images

  # Using credentials file
  python upload_figures_to_gcs.py Physics Physics-2025-paper-1 ./figures --credentials ./service-account.json

Environment Variables:
  GCS_SERVICE_ACCOUNT_KEY    Google Cloud service account JSON credentials (as string)
        """
    )

    parser.add_argument(
        'subject',
        help=f"Subject name (must be one of: {', '.join(VALID_SUBJECTS)})"
    )

    parser.add_argument(
        'paper_folder',
        help='Paper folder name (format: Subject-Year-paper-Number, e.g., Physics-2025-paper-1)'
    )

    parser.add_argument(
        'source_dir',
        help='Directory containing images to upload'
    )

    parser.add_argument(
        '--credentials',
        help='Path to GCS service account credentials JSON file (optional if using GCS_SERVICE_ACCOUNT_KEY env var)',
        default=None
    )

    parser.add_argument(
        '--output',
        help='Output text file for URLs (default: uploaded_urls.txt)',
        default='uploaded_urls.txt'
    )

    args = parser.parse_args()

    try:
        # Validate arguments
        print("Validating arguments...")
        validate_subject(args.subject)
        validate_paper_folder(args.paper_folder, args.subject)

        print(f"✓ Subject: {args.subject}")
        print(f"✓ Paper folder: {args.paper_folder}")
        print(f"✓ Source directory: {args.source_dir}")

        # Upload images
        urls = upload_images_to_gcs(
            args.subject,
            args.paper_folder,
            args.source_dir,
            args.credentials
        )

        # Save URLs to file
        save_urls_to_file(urls, args.output)

        print(f"\n✓ Successfully uploaded {len(urls)} image(s)!")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
