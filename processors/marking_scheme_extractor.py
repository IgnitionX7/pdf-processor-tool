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
    Normalize question reference by removing 'A' or 'B' prefix if present.

    Examples:
        'A1' -> '1'
        'A2(a)' -> '2(a)'
        'B1' -> '1'
        'B4(a)' -> '4(a)'
        '1' -> '1'
        '3(b)' -> '3(b)'

    Args:
        question_ref: Question reference string (e.g., 'A1', 'B1', '1', 'A2(a)')

    Returns:
        Normalized reference - both 'A' and 'B' prefixes removed
    """
    # Strip leading 'A' or 'B' if it's followed by a digit
    return re.sub(r'^[AB](?=\d)', '', question_ref)


def _find_non_null_columns(table):
    """
    Find columns that contain actual data (not None/empty).
    Returns indices of columns that have data in data rows.
    """
    if not table or len(table) < 2:
        return []

    # Look at data rows (skip potential header rows)
    data_cols = set()
    for row in table[2:]:  # Skip first 2 rows (often headers)
        if row:
            for idx, cell in enumerate(row):
                if cell is not None and str(cell).strip():
                    data_cols.add(idx)

    return sorted(data_cols)


def _extract_row_data(row, data_col_indices):
    """
    Extract question ref, answer, and marks from a row using detected data columns.

    For Cambridge-style marking schemes, the structure is typically:
    - First data column: Question reference (e.g., '1(a)(i)')
    - Second data column: Answer text
    - Third data column: Marks
    """
    if not row or len(data_col_indices) < 2:
        return None, None

    # Get values from detected data columns
    values = []
    for idx in data_col_indices:
        if idx < len(row):
            val = row[idx]
            values.append(val.strip() if val and isinstance(val, str) else val)
        else:
            values.append(None)

    # First non-null column is usually question ref, second is answer
    question_ref = values[0] if len(values) > 0 else None
    answer_text = values[1] if len(values) > 1 else None

    return question_ref, answer_text


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
                # Detect which columns actually contain data
                data_col_indices = _find_non_null_columns(table)

                # Fallback detection methods if no data columns found
                if len(data_col_indices) < 2:
                    # Try older detection method
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
                        for row in table:
                            if row and any(cell for cell in row):
                                num_cols = len(row)
                                if num_cols == 3:
                                    answer_col_idx = 1
                                elif num_cols >= 4:
                                    answer_col_idx = 3
                                else:
                                    answer_col_idx = 1
                                break

                    if answer_col_idx is None:
                        answer_col_idx = 1

                    # Use old method with answer_col_idx
                    for row_idx, row in enumerate(table):
                        if not row or all(cell is None or cell == '' for cell in row):
                            continue

                        if row_idx < len(table) and len(row) > 1 and (row[0] == 'Question' or row[1] == 'Question' or 'Answer' in str(row)):
                            continue

                        question_ref = row[0] if row[0] and str(row[0]).strip() else None
                        answer_text = row[answer_col_idx] if len(row) > answer_col_idx and row[answer_col_idx] else None

                        if not answer_text or not str(answer_text).strip():
                            continue

                        if question_ref:
                            if current_question and current_answer_parts:
                                marking_schemes[current_question] = ' '.join(current_answer_parts)
                            current_question = _normalize_question_reference(str(question_ref).strip())
                            current_answer_parts = [str(answer_text).strip()]
                        else:
                            if current_question and answer_text:
                                current_answer_parts.append(str(answer_text).strip())
                else:
                    # Use new smart column detection
                    for row_idx, row in enumerate(table):
                        # Skip empty rows
                        if not row or all(cell is None or cell == '' for cell in row):
                            continue

                        # Skip header rows (check for 'Question' or 'Answer' keywords)
                        row_str = ' '.join(str(cell) if cell else '' for cell in row)
                        if 'Question' in row_str and 'Answer' in row_str:
                            continue

                        # Extract data using detected columns
                        question_ref, answer_text = _extract_row_data(row, data_col_indices)

                        # Skip rows with no answer text
                        if not answer_text or not str(answer_text).strip():
                            continue

                        # Check if question_ref looks like a valid question reference
                        # (starts with digit or letter followed by digit, like '1(a)(i)' or 'A1')
                        if question_ref and re.match(r'^[A-Za-z]?\d', str(question_ref).strip()):
                            # Save previous question if exists
                            if current_question and current_answer_parts:
                                marking_schemes[current_question] = ' '.join(current_answer_parts)

                            # Start new question - strip 'A' or 'B' prefix if present
                            current_question = _normalize_question_reference(str(question_ref).strip())
                            current_answer_parts = [str(answer_text).strip()]
                        elif current_question and answer_text:
                            # Continue answer for current question (continuation row)
                            current_answer_parts.append(str(answer_text).strip())

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
