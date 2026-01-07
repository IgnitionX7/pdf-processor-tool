"""Element classification and text filtering."""

import cv2
import numpy as np
import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class ElementClassifier:
    """Classify and filter extracted elements."""

    def __init__(self, dpi=300):
        self.dpi = dpi

    def classify_element(self, image: np.ndarray, region: Dict) -> str:
        """Classify extracted element as figure or table."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        h_line_count = np.count_nonzero(h_lines)
        v_line_count = np.count_nonzero(v_lines)

        # Strong table indicator: both horizontal AND vertical lines
        if h_line_count > 1000 and v_line_count > 1000:
            return 'table'

        # Grid-based detection method suggests table
        if region.get('method') == 'grid_based':
            return 'table'

        # High aspect ratio alone is NOT enough to classify as table
        # Chemical structures and diagrams can be wide but are still figures
        # Only classify as table if we have strong structural evidence
        if region['aspect_ratio'] > 3.5 and h_line_count > 2000:
            # Very wide with many horizontal lines might be a data table
            return 'table'

        # Default to figure for chemical diagrams, plots, etc.
        return 'figure'

    def is_regular_text_region(self, pdf_path: Path, page_num: int, bbox_pixels: List[float]) -> bool:
        """
        Check if a detected table region is actually just regular text.

        Uses character-level analysis to distinguish between:
        - Regular text: High char density, left-aligned, few lines, no column structure
        - Actual tables: Lower char density, multi-column, structured gaps

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)
            bbox_pixels: Bounding box in pixels [x0, y0, x1, y1]

        Returns:
            True if this appears to be regular text (should be filtered out)
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num - 1]
                page_height_pdf = page.height

                # Convert pixel bbox to PDF points
                scale = 72.0 / self.dpi

                # Convert to pdfplumber coords (bottom-left origin)
                plumber_bbox = (
                    bbox_pixels[0] * scale,
                    page_height_pdf - (bbox_pixels[3] * scale),
                    bbox_pixels[2] * scale,
                    page_height_pdf - (bbox_pixels[1] * scale)
                )

                # FIRST: Check if pdfplumber detects table structure in this region
                try:
                    all_page_tables = page.find_tables()

                    for table in all_page_tables:
                        table_bbox = table.bbox

                        # Calculate intersection
                        x_overlap = min(plumber_bbox[2], table_bbox[2]) - max(plumber_bbox[0], table_bbox[0])
                        y_overlap = min(plumber_bbox[3], table_bbox[3]) - max(plumber_bbox[1], table_bbox[1])

                        if x_overlap > 0 and y_overlap > 0:
                            intersection_area = x_overlap * y_overlap
                            table_area = (table_bbox[2] - table_bbox[0]) * (table_bbox[3] - table_bbox[1])
                            overlap_ratio = intersection_area / table_area if table_area > 0 else 0

                            # If >30% of the table is in our bbox, it's a real table
                            if overlap_ratio > 0.3:
                                logger.debug(f"  Region overlaps with table ({overlap_ratio*100:.0f}% overlap), NOT filtering")
                                return False
                except Exception as e_table:
                    logger.warning(f"  Could not detect tables on page: {e_table}")

                # Get characters in this region
                chars = page.within_bbox(plumber_bbox).chars

                if not chars or len(chars) < 5:
                    return False

                # Group characters by Y position (into lines)
                lines = {}
                for char in chars:
                    y = round(char['top'], 1)
                    if y not in lines:
                        lines[y] = []
                    lines[y].append(char)

                line_list = list(lines.values())
                num_lines = len(line_list)

                # Calculate average characters per line
                avg_chars_per_line = len(chars) / num_lines if num_lines > 0 else 0

                # Count distinct X-position clusters (columns)
                x_positions = sorted([round(char['x0'], 1) for char in chars])

                # Group X positions that are within 5 points of each other
                x_clusters = 1
                for i in range(1, len(x_positions)):
                    if x_positions[i] - x_positions[i-1] > 5:
                        x_clusters += 1

                # Normalize by number of characters to get column count estimate
                x_clusters = max(1, x_clusters // max(5, num_lines))

                # Filter if ANY of these strong indicators of regular text:
                is_regular_text = (
                    # Very short with very high character density = question text
                    (num_lines <= 2 and avg_chars_per_line > 50) or
                    # Single-column sentence text or bullet lists
                    (x_clusters <= 1 and avg_chars_per_line > 40)
                )

                if is_regular_text:
                    logger.debug(f"    Filtering: {avg_chars_per_line:.0f} chars/line, "
                               f"{x_clusters} columns, {num_lines} lines")

                return is_regular_text

        except Exception as e:
            logger.debug(f"  Could not analyze text structure: {e}")
            return False
