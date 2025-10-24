"""
Text extraction processor - refactored from extract_full_text.py
"""
import json
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any
import pdfplumber


def read_pdf_text(pdf_path: Path) -> Tuple[List[str], List[int]]:
    """
    Extract text from all pages of a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Tuple of (pages_text, empty_pages)
        - pages_text: List of text content for each page
        - empty_pages: List of page numbers that are empty
    """
    pages_text: List[str] = []
    empty_pages: List[int] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=1) or ""
            normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
            if not normalized_text.strip():
                empty_pages.append(index)
            pages_text.append(normalized_text)

    return pages_text, empty_pages


def write_raw_output(pages_text: List[str], output_txt: Path) -> Dict[str, Any]:
    """
    Write raw extracted text with page separators.

    Args:
        pages_text: List of text content for each page
        output_txt: Path to output text file

    Returns:
        Statistics dictionary
    """
    page_separators = []
    for i in range(1, len(pages_text) + 1):
        page_separators.append(f"\n\n==================== PAGE {i} ====================\n\n")

    combined_lines: List[str] = []
    for i, page_text in enumerate(pages_text):
        combined_lines.append(page_separators[i])
        combined_lines.append(page_text)

    combined_text = "".join(combined_lines)
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_txt.write_text(combined_text, encoding="utf-8")

    total_chars = sum(len(t) for t in pages_text)
    total_words = sum(len(t.split()) for t in pages_text)

    return {
        "pages": len(pages_text),
        "total_characters": total_chars,
        "total_words": total_words,
        "avg_chars_per_page": (total_chars / len(pages_text)) if pages_text else 0,
        "avg_words_per_page": (total_words / len(pages_text)) if pages_text else 0,
    }


def should_skip_page(page_index: int, page_text: str) -> bool:
    """Check if a page should be skipped during cleaning."""
    # Skip first page
    if page_index == 1:
        return True
    # Skip if contains BLANK PAGE (case-insensitive)
    if "blank page" in page_text.lower():
        return True
    return False


# Regex patterns for cleaning
_RE_ONLY_NUMBER = re.compile(r"^\s*\d+\s*$")
_RE_PAGE_CODE_BETWEEN_STARS = re.compile(r"^\s*\*\s*\d{6,}\s*\*\s*$")
_RE_CID_GARBAGE = re.compile(r"\(cid:\d+\)")
_RE_DOTS_LINE = re.compile(r"^[\s\.]{6,}$")
_RE_COPYRIGHT_LINE = re.compile(r"UCLES|Cambridge|\b\d{4}/\d{2}/[A-Z]/[A-Z]/\d{2}\b", re.I)
_RE_ONLY_PUNCT = re.compile(r"^[\W_]{5,}$")

# Mirrored warning tokens (e.g., DO NOT WRITE IN THIS MARGIN)
_MIRRORED_WARNING_TOKENS = {
    "NIGRAM",  # MARGIN
    "SIHT",    # THIS
    "NI",      # IN
    "ETIRW",   # WRITE
    "TON",     # NOT
    "OD",      # DO
}


def _looks_like_mirrored_warning(line: str) -> bool:
    """Check if line looks like a mirrored warning text."""
    tokens = [t for t in re.split(r"\s+", line.strip()) if t]
    if not tokens:
        return False
    # Consider as warning if majority tokens are from mirrored set
    mirrored = sum(1 for t in tokens if t.upper() in _MIRRORED_WARNING_TOKENS)
    return mirrored >= max(2, len(tokens) // 2)


def clean_line(line: str) -> str:
    """Clean a single line of text."""
    # Remove inline (cid:###) garbage
    line = _RE_CID_GARBAGE.sub("", line)
    # Collapse excessive dots to just three
    line = re.sub(r"\.{6,}", "...", line)
    # Normalize spaces
    line = re.sub(r"\s+", " ", line).strip()
    return line


def clean_page_text(page_text: str) -> str:
    """Clean a page's text by removing noise and formatting."""
    cleaned_lines: List[str] = []
    for raw_line in page_text.splitlines():
        line = raw_line.rstrip("\n\r")
        if not line.strip():
            cleaned_lines.append("")
            continue

        # Remove lines we consider noise
        if _RE_ONLY_NUMBER.match(line):
            continue
        if _RE_PAGE_CODE_BETWEEN_STARS.match(line):
            continue
        if _RE_DOTS_LINE.match(line):
            continue
        if _RE_COPYRIGHT_LINE.search(line):
            continue
        if _looks_like_mirrored_warning(line):
            continue
        # Drop single-token mirrored warnings and known short codes like DFD
        upper_stripped = line.strip().upper()
        if upper_stripped in _MIRRORED_WARNING_TOKENS or upper_stripped == "DFD":
            continue
        if _RE_ONLY_PUNCT.match(line):
            continue
        # Remove "[Turn over" noise
        if "[TURN OVER" in upper_stripped or upper_stripped == "[TURN OVER":
            continue

        line = clean_line(line)
        if not line:
            continue
        cleaned_lines.append(line)

    # Collapse multiple blank lines to single
    collapsed: List[str] = []
    blank = False
    for l in cleaned_lines:
        if l == "":
            if not blank:
                collapsed.append("")
            blank = True
        else:
            collapsed.append(l)
            blank = False

    return "\n".join(collapsed).strip()


def write_cleaned_output(pages_text: List[str], output_txt: Path) -> Dict[str, Any]:
    """
    Write cleaned text with noise removed.

    Args:
        pages_text: List of text content for each page
        output_txt: Path to output cleaned text file

    Returns:
        Statistics dictionary including kept page numbers
    """
    cleaned_pages: List[str] = []
    kept_pages_indices: List[int] = []
    empty_after_clean: List[int] = []

    for idx, page_text in enumerate(pages_text, start=1):
        if should_skip_page(idx, page_text):
            continue
        cleaned = clean_page_text(page_text)
        if not cleaned.strip():
            empty_after_clean.append(idx)
            continue
        cleaned_pages.append(cleaned)
        kept_pages_indices.append(idx)

    combined = []
    for i, cleaned_text in enumerate(cleaned_pages, start=1):
        combined.append(f"\n\n==================== CLEANED PAGE {i} ====================\n\n")
        combined.append(cleaned_text)

    combined_text = "".join(combined).lstrip()
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_txt.write_text(combined_text, encoding="utf-8")

    total_chars = sum(len(t) for t in cleaned_pages)
    total_words = sum(len(t.split()) for t in cleaned_pages)

    return {
        "kept_pages": len(cleaned_pages),
        "kept_original_page_numbers": kept_pages_indices,
        "empty_pages_after_cleaning": empty_after_clean,
        "total_characters": total_chars,
        "total_words": total_words,
        "avg_chars_per_page": (total_chars / len(cleaned_pages)) if cleaned_pages else 0,
        "avg_words_per_page": (total_words / len(cleaned_pages)) if cleaned_pages else 0,
    }


def extract_text_from_pdf(
    pdf_path: Path,
    output_dir: Path
) -> Tuple[Path, Path, Dict[str, Any], Dict[str, Any], List[int]]:
    """
    Main function to extract and clean text from PDF.

    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to write output files

    Returns:
        Tuple of (raw_txt_path, cleaned_txt_path, raw_stats, cleaned_stats, empty_pages)
    """
    # Read PDF
    pages_text, empty_pages = read_pdf_text(pdf_path)

    # Write raw output
    raw_txt_path = output_dir / "output.txt"
    raw_stats = write_raw_output(pages_text, raw_txt_path)
    raw_stats["empty_pages"] = empty_pages

    # Write cleaned output
    cleaned_txt_path = output_dir / "output.cleaned.txt"
    cleaned_stats = write_cleaned_output(pages_text, cleaned_txt_path)

    # Save stats to JSON files
    raw_json_path = output_dir / "output.json"
    raw_json_path.write_text(json.dumps(raw_stats, indent=2), encoding="utf-8")

    cleaned_json_path = output_dir / "output.cleaned.json"
    cleaned_json_path.write_text(json.dumps(cleaned_stats, indent=2), encoding="utf-8")

    return raw_txt_path, cleaned_txt_path, raw_stats, cleaned_stats, empty_pages
