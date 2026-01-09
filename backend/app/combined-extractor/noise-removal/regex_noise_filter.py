"""
Regex-based noise filter for removing text-based noise patterns.

This is applied AFTER geometry-based filtering to catch noise that wasn't
removed by spatial filtering (headers, footers, margins).

Patterns filtered:
- Page numbers (standalone numbers)
- Page codes (* 0000800000001 *)
- Copyright lines (UCLES, Cambridge, exam codes)
- Mirrored warning text (NIGRAM = MARGIN reversed)
- "[Turn over" text
- CID encoding artifacts
- Lines with only dots or punctuation
- Page metadata (PAGE X, Exclusion zones: X, Characters: X / X, separator lines)
"""

import re
from typing import List, Set


class RegexNoiseFilter:
    """Filters text using regex patterns to remove common PDF noise."""

    # Compiled regex patterns for efficiency
    _RE_ONLY_NUMBER = re.compile(r"^\s*\d+\s*$")
    _RE_PAGE_CODE_BETWEEN_STARS = re.compile(r"^\s*\*\s*\d{6,}\s*\*\s*$")
    _RE_CID_GARBAGE = re.compile(r"\(cid:\d+\)")
    _RE_DOTS_LINE = re.compile(r"^[\s\.]{6,}$")
    _RE_COPYRIGHT_LINE = re.compile(r"UCLES|Cambridge|\b\d{4}/\d{2}/[A-Z]/[A-Z]/\d{2}\b", re.I)
    _RE_ONLY_PUNCT = re.compile(r"^[\W_]{5,}$")
    _RE_TURN_OVER = re.compile(r"\[?\s*TURN\s+OVER\s*\]?", re.I)
    _RE_PAGE_METADATA = re.compile(r"^(PAGE\s+\d+|Exclusion zones:\s*\d+|Characters:\s*\d+\s*/\s*\d+|={10,})\s*$", re.I)

    # Mirrored warning tokens (e.g., DO NOT WRITE IN THIS MARGIN)
    _MIRRORED_WARNING_TOKENS: Set[str] = {
        "NIGRAM",   # MARGIN
        "SIHT",     # THIS
        "NI",       # IN
        "ETIRW",    # WRITE
        "TON",      # NOT
        "OD",       # DO
        "KCALB",    # BLACK
        "EGAP",     # PAGE
        "DNA",      # AND
        "KNALB",    # BLANK
    }

    # Known short noise codes
    _NOISE_CODES: Set[str] = {
        "DFD",
        "DC",
        "WW",
        "CGW",
    }

    def __init__(self,
                 filter_page_numbers: bool = True,
                 filter_copyright: bool = True,
                 filter_mirrored: bool = True,
                 filter_turn_over: bool = True,
                 filter_cid_garbage: bool = True,
                 filter_dots_punct: bool = True,
                 filter_page_metadata: bool = True):
        """
        Initialize regex noise filter.

        Args:
            filter_page_numbers: Remove standalone page numbers
            filter_copyright: Remove copyright/exam code lines
            filter_mirrored: Remove mirrored warning text
            filter_turn_over: Remove "[Turn over" text
            filter_cid_garbage: Remove CID encoding artifacts
            filter_dots_punct: Remove lines with only dots/punctuation
            filter_page_metadata: Remove extraction metadata (PAGE X, Exclusion zones, Characters, separators)
        """
        self.filter_page_numbers = filter_page_numbers
        self.filter_copyright = filter_copyright
        self.filter_mirrored = filter_mirrored
        self.filter_turn_over = filter_turn_over
        self.filter_cid_garbage = filter_cid_garbage
        self.filter_dots_punct = filter_dots_punct
        self.filter_page_metadata = filter_page_metadata

    def should_filter_line(self, line: str) -> bool:
        """
        Check if a line should be filtered out as noise.

        Args:
            line: Text line to check

        Returns:
            True if line should be filtered out
        """
        if not line.strip():
            return False  # Keep blank lines for now

        # Filter page numbers
        if self.filter_page_numbers and self._RE_ONLY_NUMBER.match(line):
            return True

        # Filter page codes (e.g., * 0000800000001 *)
        if self.filter_page_numbers and self._RE_PAGE_CODE_BETWEEN_STARS.match(line):
            return True

        # Filter dots-only lines
        if self.filter_dots_punct and self._RE_DOTS_LINE.match(line):
            return True

        # Filter punctuation-only lines
        if self.filter_dots_punct and self._RE_ONLY_PUNCT.match(line):
            return True

        # Filter copyright lines
        if self.filter_copyright and self._RE_COPYRIGHT_LINE.search(line):
            return True

        # Filter "[Turn over" text
        if self.filter_turn_over and self._RE_TURN_OVER.search(line):
            return True

        # Filter page metadata (PAGE X, Exclusion zones, Characters, separator lines)
        if self.filter_page_metadata and self._RE_PAGE_METADATA.match(line):
            return True

        # Filter mirrored warning lines
        if self.filter_mirrored and self._looks_like_mirrored_warning(line):
            return True

        # Filter single-token mirrored warnings and noise codes
        if self.filter_mirrored:
            upper_stripped = line.strip().upper()
            if upper_stripped in self._MIRRORED_WARNING_TOKENS:
                return True
            if upper_stripped in self._NOISE_CODES:
                return True

        return False

    def clean_line(self, line: str) -> str:
        """
        Clean a line by removing inline noise patterns.

        Args:
            line: Text line to clean

        Returns:
            Cleaned line
        """
        # Remove inline CID garbage
        if self.filter_cid_garbage:
            line = self._RE_CID_GARBAGE.sub("", line)

        # Remove LaTeX-wrapped page codes: ^{*0000800000002*}
        line = re.sub(r"\^\{\*\d{6,}\*\}", "", line)

        # Remove empty LaTeX superscripts/subscripts: ^{} or _{}
        line = re.sub(r"[\^_]\{\}", "", line)

        # Collapse excessive dots to just three
        line = re.sub(r"\.{6,}", "...", line)

        # Normalize spaces
        line = re.sub(r"\s+", " ", line).strip()

        return line

    def filter_text(self, text: str) -> str:
        """
        Filter noise from text.

        Args:
            text: Text to filter

        Returns:
            Filtered text with noise removed
        """
        cleaned_lines: List[str] = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip("\n\r")

            # Keep blank lines
            if not line.strip():
                cleaned_lines.append("")
                continue

            # Check if line should be filtered out
            if self.should_filter_line(line):
                continue

            # Clean the line
            line = self.clean_line(line)

            # Skip if empty after cleaning
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

    def _looks_like_mirrored_warning(self, line: str) -> bool:
        """
        Check if line looks like a mirrored warning text.

        Args:
            line: Text line to check

        Returns:
            True if line appears to be mirrored warning text
        """
        tokens = [t for t in re.split(r"\s+", line.strip()) if t]
        if not tokens:
            return False

        # Consider as warning if majority tokens are from mirrored set
        mirrored = sum(1 for t in tokens if t.upper() in self._MIRRORED_WARNING_TOKENS)
        return mirrored >= max(2, len(tokens) // 2)

    def get_statistics(self, original_text: str, filtered_text: str) -> dict:
        """
        Get statistics about filtering.

        Args:
            original_text: Original text before filtering
            filtered_text: Text after filtering

        Returns:
            Dictionary with filtering statistics
        """
        orig_lines = original_text.splitlines()
        filtered_lines = filtered_text.splitlines()

        orig_chars = len(original_text)
        filtered_chars = len(filtered_text)

        return {
            "original_lines": len(orig_lines),
            "filtered_lines": len(filtered_lines),
            "lines_removed": len(orig_lines) - len(filtered_lines),
            "original_chars": orig_chars,
            "filtered_chars": filtered_chars,
            "chars_removed": orig_chars - filtered_chars,
            "removal_percentage": ((orig_chars - filtered_chars) / orig_chars * 100) if orig_chars > 0 else 0
        }
