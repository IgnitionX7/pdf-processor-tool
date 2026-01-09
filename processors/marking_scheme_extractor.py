"""
Marking scheme extraction processor - refactored from marking_scheme_extractor.py
"""
import json
import re
from pathlib import Path
from typing import Dict
import pdfplumber


def _normalize_question_reference(question_ref: str) -> str:
    """
    Normalize question reference by removing 'A' prefix if present.

    Examples:
        'A1' -> '1'
        'A2(a)' -> '2(a)'
        '1' -> '1'
        '3(b)' -> '3(b)'

    Args:
        question_ref: Question reference string (e.g., 'A1', '1', 'A2(a)')

    Returns:
        Normalized reference without 'A' prefix
    """
    # Strip leading 'A' if it's followed by a digit
    return re.sub(r'^A(?=\d)', '', question_ref)


def extract_marking_schemes(pdf_path: Path, start_page: int = 8) -> Dict[str, str]:
    """
    Extract marking schemes from a PDF file starting from a specific page.

    Args:
        pdf_path: Path to the PDF file
        start_page: Page number to start extraction from (1-indexed)

    Returns:
        Dictionary mapping question references to marking scheme answers
    """
    marking_schemes = {}
    current_question = None
    current_answer_parts = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        # Convert to 0-indexed page number
        start_idx = start_page - 1

        for page_num in range(start_idx, len(pdf.pages)):
            page = pdf.pages[page_num]
            tables = page.extract_tables()

            if not tables:
                continue

            # Process each table on the page
            for table in tables:
                # Auto-detect table format by looking at header row
                answer_col_idx = None
                for row in table[:5]:  # Check first 5 rows for header
                    if row and 'Answer' in [str(cell).strip() if cell else '' for cell in row]:
                        # Found header row, determine answer column index
                        for idx, cell in enumerate(row):
                            if cell and str(cell).strip() == 'Answer':
                                answer_col_idx = idx
                                break
                        break

                # If no header found, use heuristics based on column count
                if answer_col_idx is None:
                    # Check column count of first data row
                    for row in table:
                        if row and any(cell for cell in row):
                            num_cols = len(row)
                            if num_cols == 3:
                                # Format: Question | Answer | Marks
                                answer_col_idx = 1
                            elif num_cols >= 4:
                                # Format: ? | Question | ? | Answer | Marks (or similar)
                                answer_col_idx = 3
                            else:
                                answer_col_idx = 1  # Default
                            break

                if answer_col_idx is None:
                    answer_col_idx = 1  # Final fallback

                for row_idx, row in enumerate(table):
                    # Skip header rows and empty rows
                    if not row or all(cell is None or cell == '' for cell in row):
                        continue

                    # Check if this is a header row
                    if row_idx < len(table) and len(row) > 1 and (row[0] == 'Question' or row[1] == 'Question' or 'Answer' in str(row)):
                        continue

                    # Extract question reference (column 0) and answer (dynamic column)
                    question_ref = row[0] if row[0] and row[0].strip() else None
                    answer_text = row[answer_col_idx] if len(row) > answer_col_idx and row[answer_col_idx] else None

                    # Skip rows with no answer text
                    if not answer_text or answer_text.strip() == '':
                        continue

                    if question_ref:
                        # Save previous question if exists
                        if current_question and current_answer_parts:
                            marking_schemes[current_question] = ' '.join(current_answer_parts)

                        # Start new question - strip 'A' prefix if present
                        current_question = _normalize_question_reference(question_ref.strip())
                        current_answer_parts = [answer_text.strip()]
                    else:
                        # Continue answer for current question
                        if current_question and answer_text:
                            current_answer_parts.append(answer_text.strip())

        # Save the last question
        if current_question and current_answer_parts:
            marking_schemes[current_question] = ' '.join(current_answer_parts)

    return marking_schemes


def clean_marking_scheme(text: str) -> str:
    """Clean up marking scheme text"""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove common artifacts
    text = text.replace('�', '°')  # Fix degree symbol
    return text


def extract_marking_schemes_from_pdf(
    pdf_path: Path,
    output_json_path: Path,
    start_page: int = 8
) -> Dict[str, str]:
    """
    Main function to extract marking schemes from PDF.

    Args:
        pdf_path: Path to marking scheme PDF
        output_json_path: Path to write marking schemes JSON
        start_page: Page number to start extraction (1-indexed)

    Returns:
        Dictionary of marking schemes
    """
    marking_schemes = extract_marking_schemes(pdf_path, start_page)

    # Clean the marking schemes
    cleaned_schemes = {
        ref: clean_marking_scheme(answer)
        for ref, answer in marking_schemes.items()
    }

    # Write to JSON file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_schemes, f, indent=2, ensure_ascii=False)

    return cleaned_schemes
