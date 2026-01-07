"""Table verification using pdfplumber."""

import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TableVerifier:
    """Verify and extract tables using pdfplumber."""

    def __init__(self, dpi=300):
        self.dpi = dpi

    def get_verified_tables_on_page(self, pdf_path: Path, page_num: int) -> List[Dict]:
        """
        Get all tables detected by pdfplumber on a specific page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)

        Returns:
            List of table bounding boxes in pixel coordinates
        """
        verified_tables = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num - 1 >= len(pdf.pages):
                    return []

                page = pdf.pages[page_num - 1]
                page_height_pdf = page.height

                # Find all tables using pdfplumber
                tables = page.find_tables()

                for table in tables:
                    if not hasattr(table, 'bbox') or not table.bbox:
                        continue

                    # Get bbox in PDF coordinates (points, bottom-left origin)
                    table_bbox_pdf = table.bbox  # (x0, y0, x1, y1)

                    # Convert to pixel coordinates (top-left origin)
                    scale = self.dpi / 72.0

                    bbox_pixels = [
                        table_bbox_pdf[0] * scale,  # x0
                        (page_height_pdf - table_bbox_pdf[3]) * scale,  # y0 (top)
                        table_bbox_pdf[2] * scale,  # x1
                        (page_height_pdf - table_bbox_pdf[1]) * scale   # y1 (bottom)
                    ]

                    width = bbox_pixels[2] - bbox_pixels[0]
                    height = bbox_pixels[3] - bbox_pixels[1]

                    verified_tables.append({
                        'bbox_pixels': bbox_pixels,
                        'bbox_pdf': list(table_bbox_pdf),
                        'area': width * height,
                        'width': width,
                        'height': height,
                        'aspect_ratio': width / height if height > 0 else 0,
                        'verified_by_pdfplumber': True
                    })

                logger.debug(f"  Page {page_num}: pdfplumber found {len(verified_tables)} table(s)")

        except Exception as e:
            logger.warning(f"  Error getting tables from page {page_num}: {e}")

        return verified_tables

    def does_region_contain_verified_table(
        self, pdf_path: Path, page_num: int, bbox_pixels: List[float], min_overlap: float = 0.3
    ) -> Optional[Dict]:
        """
        Check if a region overlaps with a pdfplumber-verified table.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            bbox_pixels: Bounding box in pixels [x0, y0, x1, y1]
            min_overlap: Minimum overlap ratio to consider it a match

        Returns:
            Table info dict if overlap found, None otherwise
        """
        verified_tables = self.get_verified_tables_on_page(pdf_path, page_num)

        for table in verified_tables:
            table_bbox = table['bbox_pixels']

            # Calculate intersection
            x_overlap = min(bbox_pixels[2], table_bbox[2]) - max(bbox_pixels[0], table_bbox[0])
            y_overlap = min(bbox_pixels[3], table_bbox[3]) - max(bbox_pixels[1], table_bbox[1])

            if x_overlap > 0 and y_overlap > 0:
                intersection_area = x_overlap * y_overlap
                table_area = (table_bbox[2] - table_bbox[0]) * (table_bbox[3] - table_bbox[1])
                overlap_ratio = intersection_area / table_area if table_area > 0 else 0

                if overlap_ratio >= min_overlap:
                    logger.debug(f"    Region overlaps with verified table ({overlap_ratio*100:.0f}% overlap)")
                    return table

        return None

    def find_unextracted_tables(
        self, pdf_path: Path, page_num: int, extracted_regions: List[Dict]
    ) -> List[Dict]:
        """
        Find tables detected by pdfplumber that haven't been extracted yet.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            extracted_regions: List of already extracted region bboxes

        Returns:
            List of unextracted table dictionaries
        """
        verified_tables = self.get_verified_tables_on_page(pdf_path, page_num)
        unextracted = []

        for table in verified_tables:
            table_bbox = table['bbox_pixels']

            # Check if this table overlaps with any extracted region
            is_extracted = False
            for extracted in extracted_regions:
                if extracted['page'] != page_num:
                    continue

                ext_bbox = extracted['bbox_pixels']

                # Calculate intersection
                x_overlap = min(table_bbox[2], ext_bbox[2]) - max(table_bbox[0], ext_bbox[0])
                y_overlap = min(table_bbox[3], ext_bbox[3]) - max(table_bbox[1], ext_bbox[1])

                if x_overlap > 0 and y_overlap > 0:
                    intersection_area = x_overlap * y_overlap
                    table_area = (table_bbox[2] - table_bbox[0]) * (table_bbox[3] - table_bbox[1])
                    overlap_ratio = intersection_area / table_area if table_area > 0 else 0

                    if overlap_ratio > 0.5:
                        is_extracted = True
                        break

            if not is_extracted:
                unextracted.append(table)

        return unextracted
