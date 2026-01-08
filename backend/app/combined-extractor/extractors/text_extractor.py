"""
Text extractor with support for exclusion zones.

Extracts text from PDFs while filtering out regions containing figures/tables,
preserving chemical formulas with subscripts, superscripts, and special notation.
"""

import pdfplumber
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class TextExtractor:
    """Extract text from PDFs with spatial filtering for exclusion zones."""

    def __init__(self, exclusion_zones: Optional[Dict[int, List[Dict]]] = None,
                 caption_figure_padding_shrink: float = 0.0,
                 visual_figure_padding_shrink: float = 20.0,
                 noise_filter: Optional['NoiseFilter'] = None,
                 regex_filter: Optional['RegexNoiseFilter'] = None,
                 skip_first_page: bool = True):
        """
        Initialize text extractor.

        Args:
            exclusion_zones: Dict mapping page_num -> list of exclusion zone dicts
                            Each zone dict should have: {'bbox': [x0, y0, x1, y1], 'type': 'figure'/'table', 'source': 'caption'/'visual'/etc}
            caption_figure_padding_shrink: Amount (in PDF points) to shrink caption-based figure bboxes inward when filtering text.
                                          Default: 0.0 points (no shrink for precise caption-based extraction).
            visual_figure_padding_shrink: Amount (in PDF points) to shrink visual-detected figure bboxes inward when filtering text.
                                         This preserves text labels that were captured with padding in the figure image.
                                         Default: 20.0 points.
            noise_filter: Optional NoiseFilter instance for removing headers/footers/margins (geometry-based).
                         If provided, noise filtering will be applied before exclusion zone filtering.
            regex_filter: Optional RegexNoiseFilter instance for removing text-based noise patterns.
                         If provided, regex filtering will be applied after all other filtering.
            skip_first_page: Skip first page during text extraction (default: True)
        """
        self.exclusion_zones = exclusion_zones or {}
        self.caption_figure_padding_shrink = caption_figure_padding_shrink
        self.visual_figure_padding_shrink = visual_figure_padding_shrink
        self.noise_filter = noise_filter
        self.regex_filter = regex_filter
        self.skip_first_page = skip_first_page

    def extract_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Extract text from all pages with exclusion zone filtering.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of dicts with page data: {'page': int, 'text': str, 'formatted_text': str}
        """
        results = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Skip first page if configured
                if self.skip_first_page and page_num == 1:
                    print(f"  Skipping page 1 (skip_first_page=True)")
                    continue

                print(f"  Extracting text from page {page_num}/{len(pdf.pages)}...")

                chars = page.chars
                if not chars:
                    results.append({
                        'page': page_num,
                        'text': '',
                        'formatted_text': ''
                    })
                    continue

                # Step 1: Apply noise filtering (headers/footers/margins) if enabled
                if self.noise_filter:
                    chars = self.noise_filter.filter_characters(chars)

                if not chars:
                    results.append({
                        'page': page_num,
                        'text': '',
                        'formatted_text': ''
                    })
                    continue

                # Step 2: Filter out chars in exclusion zones (figures/tables)
                exclusions_for_page = self.exclusion_zones.get(page_num, [])
                filtered_chars = self._filter_chars_by_exclusion_zones(chars, exclusions_for_page)

                if not filtered_chars:
                    results.append({
                        'page': page_num,
                        'text': '',
                        'formatted_text': ''
                    })
                    continue

                # Determine baseline for this page
                sizes = [c['size'] for c in filtered_chars]
                tops = [c['top'] for c in filtered_chars]

                size_counts = defaultdict(int)
                top_counts = defaultdict(float)

                for size in sizes:
                    size_counts[round(size, 1)] += 1

                for top in tops:
                    top_counts[round(top, 1)] += 1

                baseline_size = max(size_counts.items(), key=lambda x: x[1])[0] if size_counts else 10.0
                baseline_top = max(top_counts.items(), key=lambda x: x[1])[0] if top_counts else 0.0

                # Extract arrow graphics (if any)
                import sys
                import os
                import importlib.util

                # Add parent directory to path
                parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

                try:
                    # Try the v4 version first (better formula detection)
                    v4_path = os.path.join(parent_dir, 'extraction-approach-hybrid-v4-arrows-fixed.py')
                    regular_path = os.path.join(parent_dir, 'extraction-approach-hybrid.py')

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
                        arrows = extractor_module.extract_arrow_graphics(str(pdf_path), page_num - 1)

                        # Reconstruct text with LaTeX notation using filtered chars
                        formatted_text = extractor_module.reconstruct_formulas(
                            filtered_chars,
                            baseline_size,
                            baseline_top,
                            arrows
                        )
                    else:
                        raise ImportError("Could not load extractor module")

                except Exception as e:
                    # Fallback if import fails
                    arrows = []
                    formatted_text = self._reconstruct_plain_text(filtered_chars)

                # Get plain text from filtered chars
                plain_text = self._reconstruct_plain_text(filtered_chars)

                # Step 3: Apply LaTeX normalization to formatted text (nuclide repair, element wrapping)
                try:
                    # Import LaTeX normalizer from extractor_utils
                    extractor_utils_dir = os.path.join(parent_dir, 'extractor_utils')
                    if extractor_utils_dir not in sys.path:
                        sys.path.insert(0, extractor_utils_dir)

                    from latex_normalizer import normalize_latex
                    formatted_text = normalize_latex(formatted_text)
                except Exception as e:
                    # If normalization fails, continue without it
                    print(f"    Warning: LaTeX normalization failed: {e}")

                # Step 4: Apply regex-based filtering if enabled (text-level noise removal)
                if self.regex_filter:
                    plain_text = self.regex_filter.filter_text(plain_text)
                    formatted_text = self.regex_filter.filter_text(formatted_text)

                results.append({
                    'page': page_num,
                    'text': plain_text,
                    'formatted_text': formatted_text,
                    'baseline_size': baseline_size,
                    'baseline_top': baseline_top,
                    'filtered_char_count': len(filtered_chars),
                    'total_char_count': len(chars),
                    'exclusion_zones': len(exclusions_for_page)
                })

        return results

    def _filter_chars_by_exclusion_zones(self, chars: List[Dict], exclusion_zones: List[Dict]) -> List[Dict]:
        """
        Filter out characters that fall within exclusion zones.

        For caption-based figures: uses exact bbox or minimal shrink (precise extraction).
        For visual-detected figures: shrinks bbox inward to preserve text labels that were captured with padding.
        For tables: uses exact bbox for precise filtering.

        Args:
            chars: List of character dicts from pdfplumber
            exclusion_zones: List of exclusion zone dicts with 'bbox', 'type', and 'source' keys

        Returns:
            Filtered list of characters
        """
        if not exclusion_zones:
            return chars

        filtered = []

        for char in chars:
            char_bbox = (char['x0'], char['top'], char['x1'], char['bottom'])

            # Check if char overlaps with any exclusion zone
            is_excluded = False
            for zone in exclusion_zones:
                zone_bbox = zone['bbox']  # [x0, y0, x1, y1] in PDF coords
                zone_type = zone.get('type', 'unknown')
                zone_source = zone.get('source', '')

                # Determine padding based on type and source
                padding_shrink = 0.0

                if zone_type == 'figure':
                    # Caption-based figures: use caption padding (default 0)
                    if zone_source == 'caption':
                        padding_shrink = self.caption_figure_padding_shrink
                    # Visual-detected figures: use visual padding (default 20)
                    else:
                        # Sources: 'visual', 'glyph_clustering', 'pdfplumber', 'pdfplumber_verified'
                        padding_shrink = self.visual_figure_padding_shrink
                # Tables and other types: no padding (0)
                else:
                    padding_shrink = 0.0

                # Apply padding shrink if needed
                if padding_shrink > 0:
                    adjusted_bbox = [
                        zone_bbox[0] + padding_shrink,  # x0 (shrink right)
                        zone_bbox[1] + padding_shrink,  # y0 (shrink down)
                        zone_bbox[2] - padding_shrink,  # x1 (shrink left)
                        zone_bbox[3] - padding_shrink   # y1 (shrink up)
                    ]
                else:
                    # Use exact bbox
                    adjusted_bbox = zone_bbox

                if self._bbox_overlap(char_bbox, adjusted_bbox):
                    is_excluded = True
                    break

            if not is_excluded:
                filtered.append(char)

        return filtered

    def _bbox_overlap(self, bbox1: Tuple, bbox2: List) -> bool:
        """
        Check if two bounding boxes overlap.

        Args:
            bbox1: (x0, y0, x1, y1) - first bbox
            bbox2: [x0, y0, x1, y1] - second bbox

        Returns:
            True if bboxes overlap
        """
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2

        # Check for no overlap
        if x1_1 < x0_2 or x1_2 < x0_1:
            return False
        if y1_1 < y0_2 or y1_2 < y0_1:
            return False

        return True

    def _reconstruct_plain_text(self, chars: List[Dict]) -> str:
        """
        Reconstruct plain text from filtered characters.

        Args:
            chars: List of character dicts

        Returns:
            Plain text string
        """
        if not chars:
            return ""

        # Sort by vertical position, then horizontal
        sorted_chars = sorted(chars, key=lambda x: (x['top'], x['x0']))

        lines = []
        current_line = []
        prev_char = None

        for char in sorted_chars:
            if prev_char is None:
                current_line.append(char['text'])
            else:
                # Check vertical gap
                vertical_gap = abs(char['top'] - prev_char['top'])

                if vertical_gap > 8.0:
                    # New line
                    lines.append(''.join(current_line))
                    current_line = [char['text']]
                else:
                    # Same line - check horizontal gap for space
                    horizontal_gap = char['x0'] - prev_char['x1']

                    if horizontal_gap > 2.0:
                        current_line.append(' ')

                    current_line.append(char['text'])

            prev_char = char

        # Don't forget last line
        if current_line:
            lines.append(''.join(current_line))

        return '\n'.join(lines)
