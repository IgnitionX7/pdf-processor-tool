"""
Noise detector for identifying headers, footers, and margin junk text in PDFs.

Analyzes PDF pages to detect repetitive text patterns in:
- Headers (top of page)
- Footers (bottom of page)
- Left/right margins
"""

import pdfplumber
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter


class NoiseDetector:
    """Detects headers, footers, and margin noise in PDF documents."""

    def __init__(self,
                 header_threshold: float = 30.0,
                 footer_threshold: float = 780.0,
                 left_margin_threshold: float = 40.0,
                 right_margin_threshold: float = 570.0,
                 min_frequency: float = 0.5,
                 sample_size: int = 5):
        """
        Initialize noise detector.

        Args:
            header_threshold: Y-coordinate threshold for header detection (default: 80pt from top)
            footer_threshold: Y-coordinate threshold for footer detection (default: 760pt from top)
            left_margin_threshold: X-coordinate threshold for left margin (default: 80pt from left)
            right_margin_threshold: X-coordinate threshold for right margin (default: 515pt from left)
            min_frequency: Minimum frequency (0-1) for text to be considered noise (default: 0.5)
            sample_size: Number of pages to sample for pattern detection (default: 5)
        """
        self.header_threshold = header_threshold
        self.footer_threshold = footer_threshold
        self.left_margin_threshold = left_margin_threshold
        self.right_margin_threshold = right_margin_threshold
        self.min_frequency = min_frequency
        self.sample_size = sample_size

    def detect_noise_zones(self, pdf_path: str) -> Dict[str, any]:
        """
        Detect noise zones (headers, footers, margins) in a PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict containing noise zone information:
            {
                'header_zones': List of y-coordinate ranges for headers,
                'footer_zones': List of y-coordinate ranges for footers,
                'left_margin_zones': List of x-coordinate ranges for left margins,
                'right_margin_zones': List of x-coordinate ranges for right margins,
                'page_dimensions': (width, height),
                'noise_patterns': List of detected noise text patterns
            }
        """
        pdf_path = Path(pdf_path)

        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)

            # Sample pages for analysis (first, middle, last few pages)
            sample_indices = self._get_sample_page_indices(total_pages)

            # Collect text patterns from sampled pages
            header_texts = defaultdict(int)
            footer_texts = defaultdict(int)
            left_margin_texts = defaultdict(int)
            right_margin_texts = defaultdict(int)

            page_width = 0
            page_height = 0

            for page_idx in sample_indices:
                page = pdf.pages[page_idx]
                page_width = page.width
                page_height = page.height

                words = page.extract_words()

                for word in words:
                    text = word['text'].strip()
                    if not text:
                        continue

                    x0, top = word['x0'], word['top']

                    # Check if in header zone
                    if top < self.header_threshold:
                        # Normalize text for pattern matching
                        normalized = self._normalize_text(text)
                        if normalized:
                            header_texts[normalized] += 1

                    # Check if in footer zone
                    if top > self.footer_threshold:
                        normalized = self._normalize_text(text)
                        if normalized:
                            footer_texts[normalized] += 1

                    # Check if in left margin
                    if x0 < self.left_margin_threshold:
                        normalized = self._normalize_text(text)
                        if normalized:
                            left_margin_texts[normalized] += 1

                    # Check if in right margin
                    if x0 > self.right_margin_threshold:
                        normalized = self._normalize_text(text)
                        if normalized:
                            right_margin_texts[normalized] += 1

            # Identify repetitive patterns (noise)
            num_samples = len(sample_indices)
            min_occurrences = max(2, int(num_samples * self.min_frequency))

            noise_patterns = {
                'header_patterns': self._filter_patterns(header_texts, min_occurrences),
                'footer_patterns': self._filter_patterns(footer_texts, min_occurrences),
                'left_margin_patterns': self._filter_patterns(left_margin_texts, min_occurrences),
                'right_margin_patterns': self._filter_patterns(right_margin_texts, min_occurrences)
            }

            # Determine exact zones by analyzing Y/X coordinates of noise patterns
            header_zones = self._determine_header_zones(pdf, noise_patterns['header_patterns'])
            footer_zones = self._determine_footer_zones(pdf, noise_patterns['footer_patterns'])
            left_margin_zones = self._determine_margin_zones(pdf, noise_patterns['left_margin_patterns'], 'left')
            right_margin_zones = self._determine_margin_zones(pdf, noise_patterns['right_margin_patterns'], 'right')

            return {
                'header_zones': header_zones,
                'footer_zones': footer_zones,
                'left_margin_zones': left_margin_zones,
                'right_margin_zones': right_margin_zones,
                'page_dimensions': (page_width, page_height),
                'noise_patterns': noise_patterns,
                'thresholds': {
                    'header_y': self.header_threshold,
                    'footer_y': self.footer_threshold,
                    'left_x': self.left_margin_threshold,
                    'right_x': self.right_margin_threshold
                }
            }

    def _get_sample_page_indices(self, total_pages: int) -> List[int]:
        """Get page indices to sample for noise detection."""
        if total_pages <= self.sample_size:
            return list(range(total_pages))

        # Sample: first 2 pages, middle page, last 2 pages
        indices = set()
        indices.add(0)  # First page
        if total_pages > 1:
            indices.add(1)  # Second page
        if total_pages > 2:
            indices.add(total_pages // 2)  # Middle page
        if total_pages > 3:
            indices.add(total_pages - 2)  # Second to last
        indices.add(total_pages - 1)  # Last page

        return sorted(list(indices))[:self.sample_size]

    def _normalize_text(self, text: str) -> Optional[str]:
        """
        Normalize text for pattern matching.

        Removes page numbers, dates, and other variable content while preserving structure.
        """
        # Skip very short text
        if len(text) < 3:
            return None

        # Skip pure numbers (likely page numbers)
        if text.isdigit():
            return None

        # Skip text with encoding issues (cid:)
        if 'cid:' in text.lower():
            return None

        # Normalize multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Replace numbers with placeholder for pattern matching
        # Keep structure like "* 0000800000001 *" -> "* [NUM] *"
        if re.match(r'^[\*\[\(\{].*\d+.*[\*\]\)\}]$', text):
            text = re.sub(r'\d+', '[NUM]', text)

        return text.strip()

    def _filter_patterns(self, text_counts: Dict[str, int], min_occurrences: int) -> List[Tuple[str, int]]:
        """Filter text patterns that appear frequently enough to be considered noise."""
        patterns = [(text, count) for text, count in text_counts.items()
                   if count >= min_occurrences]
        return sorted(patterns, key=lambda x: x[1], reverse=True)

    def _determine_header_zones(self, pdf, patterns: List[Tuple[str, int]]) -> List[Dict]:
        """Determine exact Y-coordinate ranges for header zones."""
        if not patterns:
            return []

        zones = []

        # Find max Y coordinate of header patterns across all pages
        for page in pdf.pages[:min(10, len(pdf.pages))]:
            words = page.extract_words()

            max_y = 0
            for word in words:
                if word['top'] < self.header_threshold:
                    # Check if this word matches any noise pattern
                    normalized = self._normalize_text(word['text'])
                    if any(normalized == pattern[0] for pattern in patterns):
                        max_y = max(max_y, word['bottom'])

            if max_y > 0:
                zones.append({
                    'y_min': 0,
                    'y_max': max_y + 5,  # Add small buffer
                    'type': 'header'
                })

        # Merge overlapping zones
        if zones:
            return [{'y_min': 0, 'y_max': max(z['y_max'] for z in zones), 'type': 'header'}]

        return []

    def _determine_footer_zones(self, pdf, patterns: List[Tuple[str, int]]) -> List[Dict]:
        """Determine exact Y-coordinate ranges for footer zones."""
        if not patterns:
            return []

        zones = []

        # Find min Y coordinate of footer patterns across all pages
        for page in pdf.pages[:min(10, len(pdf.pages))]:
            words = page.extract_words()
            page_height = page.height

            min_y = page_height
            for word in words:
                if word['top'] > self.footer_threshold:
                    # Check if this word matches any noise pattern
                    normalized = self._normalize_text(word['text'])
                    if any(normalized == pattern[0] for pattern in patterns):
                        min_y = min(min_y, word['top'])

            if min_y < page_height:
                zones.append({
                    'y_min': min_y - 5,  # Add small buffer
                    'y_max': page_height,
                    'type': 'footer'
                })

        # Merge overlapping zones
        if zones:
            return [{'y_min': min(z['y_min'] for z in zones), 'y_max': max(z['y_max'] for z in zones), 'type': 'footer'}]

        return []

    def _determine_margin_zones(self, pdf, patterns: List[Tuple[str, int]], side: str) -> List[Dict]:
        """Determine exact X-coordinate ranges for margin zones."""
        if not patterns:
            return []

        zones = []

        for page in pdf.pages[:min(10, len(pdf.pages))]:
            words = page.extract_words()
            page_width = page.width

            if side == 'left':
                max_x = 0
                for word in words:
                    if word['x0'] < self.left_margin_threshold:
                        normalized = self._normalize_text(word['text'])
                        if any(normalized == pattern[0] for pattern in patterns):
                            max_x = max(max_x, word['x1'])

                if max_x > 0:
                    zones.append({
                        'x_min': 0,
                        'x_max': max_x + 5,
                        'type': 'left_margin'
                    })
            else:  # right
                min_x = page_width
                for word in words:
                    if word['x0'] > self.right_margin_threshold:
                        normalized = self._normalize_text(word['text'])
                        if any(normalized == pattern[0] for pattern in patterns):
                            min_x = min(min_x, word['x0'])

                if min_x < page_width:
                    zones.append({
                        'x_min': min_x - 5,
                        'x_max': page_width,
                        'type': 'right_margin'
                    })

        # Merge overlapping zones
        if zones:
            if side == 'left':
                return [{'x_min': 0, 'x_max': max(z['x_max'] for z in zones), 'type': 'left_margin'}]
            else:
                return [{'x_min': min(z['x_min'] for z in zones), 'x_max': max(z['x_max'] for z in zones), 'type': 'right_margin'}]

        return []
