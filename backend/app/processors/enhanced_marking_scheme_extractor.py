"""
Enhanced marking scheme extraction with LaTeX support.
Uses the same text extraction pipeline as the enhanced question extractor.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import logging
import pdfplumber

# Add combined-extractor to path for importing TextExtractor
backend_app_dir = Path(__file__).parent.parent
combined_extractor_path = backend_app_dir / "combined-extractor"
if str(combined_extractor_path) not in sys.path:
    sys.path.insert(0, str(combined_extractor_path))

from extractors.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


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
    import re
    # Strip leading 'A' or 'B' if it's followed by a digit
    return re.sub(r'^[AB](?=\d)', '', question_ref)


def extract_marking_schemes_with_latex(
    pdf_path: Path,
    start_page: int = 8,
    skip_first_page: bool = False
) -> Dict[str, str]:
    """
    Extract marking schemes from a PDF with LaTeX notation support.

    Uses two-pass extraction:
    1. Get table cell bounding boxes from pdfplumber
    2. Re-extract text from each cell using character-level data with LaTeX reconstruction

    Args:
        pdf_path: Path to the PDF file
        start_page: Page number to start extraction from (1-indexed)
        skip_first_page: Whether to skip the first page (default: False for marking schemes)

    Returns:
        Dictionary mapping question references to marking scheme answers with LaTeX
    """
    marking_schemes = {}

    logger.info(f"Extracting marking scheme with LaTeX (two-pass) from: {pdf_path.name}")

    # Two-pass extraction approach
    # Pass 1: Get table structure (bounding boxes only)
    # Pass 2: Extract text from each cell bbox with LaTeX reconstruction

    current_question = None
    current_answer_parts = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        # Convert to 0-indexed page number
        start_idx = start_page - 1

        for page_num in range(start_idx, len(pdf.pages)):
            page = pdf.pages[page_num]

            # PASS 1: Get table structure (bounding boxes only)
            tables = page.find_tables()

            if not tables:
                continue

            logger.info(f"Processing page {page_num + 1}: found {len(tables)} table(s)")

            # Process each table on the page
            for table in tables:
                # Use extract() to get properly parsed rows with merged cells handled
                # This is more reliable than trying to reconstruct from table.cells
                table_data = table.extract()

                if not table_data:
                    logger.warning(f"Table on page {page_num + 1} has no data, skipping")
                    continue

                logger.info(f"Table has {len(table_data)} rows")

                # Auto-detect table format by looking at header row
                answer_col_idx = None
                for row in table_data[:5]:  # Check first 5 rows for header
                    if row and 'Answer' in [str(cell).strip() for cell in row if cell]:
                        # Found header row, determine answer column index
                        for idx, cell in enumerate(row):
                            if cell and str(cell).strip() == 'Answer':
                                answer_col_idx = idx
                                logger.info(f"Detected answer column at index {answer_col_idx}")
                                break
                        break

                # If no header found, use heuristics based on column count
                if answer_col_idx is None:
                    # Check column count of first data row
                    for row in table_data:
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
                            logger.info(f"Auto-detected answer column at index {answer_col_idx} (based on {num_cols} columns)")
                            break

                if answer_col_idx is None:
                    answer_col_idx = 1  # Final fallback

                # Process each row
                for row_idx, row in enumerate(table_data):
                    # Skip header rows and empty rows
                    if not row or all(cell is None or cell == '' for cell in row):
                        continue

                    # Check if this is a header row
                    if row_idx < len(table_data) and len(row) > 1 and (row[0] == 'Question' or row[1] == 'Question' or 'Answer' in str(row)):
                        logger.info(f"Skipping header row: {row}")
                        continue

                    # Extract question reference (column 0) and answer (dynamic column)
                    question_ref = row[0] if row[0] and str(row[0]).strip() else None
                    answer_text = row[answer_col_idx] if len(row) > answer_col_idx and row[answer_col_idx] else None

                    # Skip rows with no answer text
                    if not answer_text or not str(answer_text).strip():
                        continue

                    # Apply LaTeX conversion to the answer
                    answer_latex = _convert_to_latex_simple(str(answer_text).strip())

                    if question_ref:
                        # Save previous question if exists
                        if current_question and current_answer_parts:
                            marking_schemes[current_question] = ' '.join(current_answer_parts)

                        # Start new question - strip 'A' or 'B' prefix if present
                        current_question = _normalize_question_reference(str(question_ref).strip())
                        current_answer_parts = [answer_latex]
                        logger.info(f"New question: {current_question} - {answer_latex[:30]}...")
                    else:
                        # Continue answer for current question (multi-row answers)
                        if current_question and answer_latex:
                            current_answer_parts.append(answer_latex)
                            logger.info(f"Continue question {current_question} - {answer_latex[:30]}...")

        # Save the last question
        if current_question and current_answer_parts:
            marking_schemes[current_question] = ' '.join(current_answer_parts)

    logger.info(f"Extracted {len(marking_schemes)} marking scheme entries with LaTeX")
    return marking_schemes


def _group_cells_by_row(cells, tolerance=3):
    """
    Group table cells by row based on their vertical position (top coordinate).

    pdfplumber's table.cells returns a flat list of (x0, top, x1, bottom) tuples.
    We need to group cells that have similar 'top' values into rows, then sort
    each row by x0 (left to right) to get proper column ordering.

    Args:
        cells: Flat list of cell bounding boxes as (x0, top, x1, bottom) tuples
        tolerance: Maximum vertical distance (in points) for cells to be in the same row

    Returns:
        List of rows, where each row is a list of cell bboxes sorted left-to-right
    """
    rows = []

    # Sort cells by top coordinate first
    sorted_cells = sorted(cells, key=lambda c: c[1])

    # Group cells with similar top values into rows
    for cell in sorted_cells:
        placed = False

        # Try to find an existing row this cell belongs to
        for row in rows:
            # Compare with the first cell in the row (they should have similar tops)
            if abs(row[0][1] - cell[1]) <= tolerance:
                row.append(cell)
                placed = True
                break

        # If no matching row found, create a new row
        if not placed:
            rows.append([cell])

    # Sort cells within each row by x0 (left to right)
    for row in rows:
        row.sort(key=lambda c: c[0])

    return rows


def _extract_latex_from_cell(page, cell_bbox) -> str:
    """
    Extract text from a table cell with LaTeX notation support.

    Uses the same character-level extraction and LaTeX reconstruction
    logic as the main TextExtractor, but scoped to a single cell.

    Args:
        page: pdfplumber page object
        cell_bbox: Cell bounding box (x0, top, x1, bottom)

    Returns:
        Text with LaTeX subscript/superscript notation
    """
    import sys
    import os
    import importlib.util
    from collections import defaultdict

    # Extract characters within this cell bbox
    chars = page.within_bbox(cell_bbox).chars

    if not chars:
        return ""

    # Determine baseline for this cell (same logic as TextExtractor)
    sizes = [c['size'] for c in chars]
    tops = [c['top'] for c in chars]

    size_counts = defaultdict(int)
    top_counts = defaultdict(float)

    for size in sizes:
        size_counts[round(size, 1)] += 1

    for top in tops:
        top_counts[round(top, 1)] += 1

    baseline_size = max(size_counts.items(), key=lambda x: x[1])[0] if size_counts else 10.0
    baseline_top = max(top_counts.items(), key=lambda x: x[1])[0] if top_counts else 0.0

    # Try to use the same reconstruction logic from the extraction module
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    combined_extractor_dir = os.path.join(parent_dir, 'app', 'combined-extractor')

    try:
        # Try the v4 version first (better formula detection)
        v4_path = os.path.join(combined_extractor_dir, 'extraction-approach-hybrid-v4-arrows-fixed.py')
        regular_path = os.path.join(combined_extractor_dir, 'extraction-approach-hybrid.py')

        extractor_module = None

        if os.path.exists(v4_path):
            spec = importlib.util.spec_from_file_location("extractor_module", v4_path)
            extractor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(extractor_module)
        elif os.path.exists(regular_path):
            spec = importlib.util.spec_from_file_location("extractor_module", regular_path)
            extractor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(extractor_module)

        if extractor_module:
            # Use the same LaTeX reconstruction logic
            formatted_text = extractor_module.reconstruct_formulas(
                chars,
                baseline_size,
                baseline_top,
                arrows=[]  # No arrows in table cells typically
            )
            return formatted_text.strip()

    except Exception as e:
        logger.warning(f"Could not use advanced LaTeX reconstruction: {e}")

    # Fallback: simple extraction
    return page.within_bbox(cell_bbox).extract_text() or ""


def _convert_to_latex_simple(text: str) -> str:
    """
    Convert plain text to LaTeX format using simple pattern matching.

    Handles common cases where pdfplumber splits chemical formulas across lines.
    Examples:
        "H O\\n2" -> "H_2O"
        "CO\\n2" -> "CO_2"
        "Fe O\\n2 3" -> "Fe_2O_3"
        "SO\\n2" -> "SO_2"

    Args:
        text: Plain text from pdfplumber table cell

    Returns:
        Text with LaTeX subscript notation
    """
    import re

    # Remove newlines and normalize whitespace
    normalized = text.replace('\n', ' ').strip()

    # Pattern 1: Handle split formulas like "H O 2" or "Fe O 2 3"
    # This needs to be done first before other patterns
    # Match: Element(s) followed by trailing number(s)
    # "H O 2" should become "H_2O", "Fe O 2 3" should become "Fe_2O_3"

    # Strategy: Find sequences of elements and numbers, then reconstruct
    # Split by whitespace
    parts = normalized.split()

    # Try to identify if this looks like a chemical formula pattern
    # Pattern: [Element] [Element]? [Digit]+
    if len(parts) >= 2 and parts[-1].isdigit():
        # Last part is a number - likely a subscript
        # Check if we have elements before it
        elements = []
        numbers = []

        for part in parts:
            if part.isdigit():
                numbers.append(part)
            elif re.match(r'^[A-Z][a-z]?$', part):
                elements.append(part)
            else:
                # Mixed content, use original
                break
        else:
            # All parts matched - reconstruct formula
            # Common patterns:
            # ["H", "O", "2"] -> "H_2O"
            # ["Fe", "O", "2", "3"] -> "Fe_2O_3"
            # ["CO", "2"] -> "CO_2"

            if len(elements) == 2 and len(numbers) == 1:
                # "H O 2" -> "H_2O"
                return f"{elements[0]}_{numbers[0]}{elements[1]}"
            elif len(elements) == 2 and len(numbers) == 2:
                # "Fe O 2 3" -> "Fe_2O_3"
                return f"{elements[0]}_{numbers[0]}{elements[1]}_{numbers[1]}"
            elif len(elements) == 1 and len(numbers) == 1:
                # "CO 2" -> "CO_2" or "SO 2" -> "SO_2"
                return f"{elements[0]}_{numbers[0]}"
            elif len(elements) == 1 and len(numbers) >= 2:
                # "Si O 2" where "Si" is treated as one element -> "SiO_2"?
                # Actually this is complex, fall through to pattern 2
                pass

    # Pattern 2: Element followed by space(s) and number(s)
    # "CO 2" -> "CO_2", "SiO 2" -> "SiO_2"
    normalized = re.sub(r'([A-Z][a-z]?[a-z]?)\s+(\d+)', r'\1_\2', normalized)

    # Pattern 3: Single element followed by number (already together, no spaces)
    # "SO2" or "CO2" -> "SO_2", "CO_2"
    normalized = re.sub(r'([A-Z][a-z]?)(\d+)', r'\1_\2', normalized)

    # Pattern 3: Handle superscripts (like charges: +, -, 2+, 3-)
    # "Cu 2+" -> "Cu^{2+}"
    normalized = re.sub(r'([A-Z][a-z]?)\s+([\d]*[+-])', r'\1^{\2}', normalized)

    return normalized


def extract_marking_schemes_from_pdf_enhanced(
    pdf_path: Path,
    output_json_path: Path,
    start_page: int = 8,
    skip_first_page: bool = False
) -> Dict[str, str]:
    """
    Main function to extract marking schemes from PDF with LaTeX support.

    Args:
        pdf_path: Path to marking scheme PDF
        output_json_path: Path to write marking schemes JSON
        start_page: Page number to start extraction (1-indexed)
        skip_first_page: Whether to skip the first page

    Returns:
        Dictionary of marking schemes with LaTeX notation
    """
    marking_schemes = extract_marking_schemes_with_latex(
        pdf_path,
        start_page=start_page,
        skip_first_page=skip_first_page
    )

    # Clean up marking schemes
    cleaned_schemes = {
        key: clean_marking_scheme(value)
        for key, value in marking_schemes.items()
    }

    # Save to JSON
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_schemes, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved marking schemes to: {output_json_path}")
    return cleaned_schemes


def clean_marking_scheme(text: str) -> str:
    """
    Clean up marking scheme text while preserving LaTeX notation.

    Args:
        text: Marking scheme text (may contain LaTeX)

    Returns:
        Cleaned text with LaTeX preserved
    """
    # Remove extra whitespace but preserve LaTeX subscripts/superscripts
    # Don't use aggressive whitespace removal as it might break LaTeX

    # Remove multiple spaces
    import re
    text = re.sub(r' +', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    # Fix common artifacts
    text = text.replace('�', '°')  # Fix degree symbol

    return text
