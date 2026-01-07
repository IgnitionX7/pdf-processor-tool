"""Visual-based region detection using computer vision."""

import cv2
import numpy as np
import fitz
import logging
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class VisualDetector:
    """Detect figures and tables using computer vision techniques."""

    def __init__(self, min_area=5000, max_area_ratio=0.70, min_area_ratio=0.01,
                 min_aspect_ratio=0.2, max_aspect_ratio=5.0, min_edge_density=0.01, dpi=300):
        self.min_area = min_area
        self.max_area_ratio = max_area_ratio
        self.min_area_ratio = min_area_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_edge_density = min_edge_density
        self.dpi = dpi

    def detect_regions(self, pdf_path: str, page_num: int) -> List[Dict]:
        """
        Detect visual regions (figures/tables) from a PDF page.

        Args:
            pdf_path: Path to PDF file
            page_num: Zero-indexed page number

        Returns:
            List of detected regions with bbox coordinates
        """
        pdf_path = Path(pdf_path)

        # Open PDF and render page as image
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]

        # Render page to image at specified DPI
        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        # Convert to numpy array
        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        # Convert to BGR for OpenCV
        if pix.n == 4:  # RGBA
            image = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:  # RGB
            image = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
        else:  # Grayscale
            image = cv2.cvtColor(img_data, cv2.COLOR_GRAY2BGR)

        # Convert to grayscale for processing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Calculate page area
        page_area = pix.width * pix.height

        doc.close()

        # Find all potential regions
        regions = self.find_all_regions(image, gray, page_area)

        # Merge nearby regions
        merged_regions = self.merge_nearby_regions(regions, pix.height)

        # Filter and deduplicate
        final_regions = self.filter_regions(merged_regions, page_area)

        # Convert pixel coordinates back to PDF coordinates
        scale = 72 / self.dpi
        result_regions = []
        for region in final_regions:
            x, y, w, h = region['bbox']
            # Convert from image pixels to PDF points
            pdf_bbox = (
                x * scale,
                y * scale,
                (x + w) * scale,
                (y + h) * scale
            )
            result_regions.append({
                'bbox': pdf_bbox,
                'confidence': 1.0,
                'method': region.get('method', 'unknown')
            })

        logger.debug(f"  Visual detector found {len(result_regions)} regions on page {page_num + 1}")
        return result_regions

    def find_all_regions(self, image: np.ndarray, gray: np.ndarray, page_area: float) -> List[Dict]:
        """Find all potential visual regions using multiple methods."""
        regions = []
        regions.extend(self.find_edge_based_regions(gray, page_area))
        regions.extend(self.find_contour_regions(gray, page_area))
        regions.extend(self.find_grid_regions(gray, page_area))
        return regions

    def find_edge_based_regions(self, gray: np.ndarray, page_area: float) -> List[Dict]:
        """Find regions with significant edge content."""
        regions = []
        edges = cv2.Canny(gray, 30, 100)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0

            if area < self.min_area or aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
                continue

            roi = edges[y:y+h, x:x+w]
            edge_density = np.count_nonzero(roi) / area if area > 0 else 0

            if edge_density < self.min_edge_density:
                continue

            regions.append({
                'bbox': (x, y, w, h),
                'area': area,
                'aspect_ratio': aspect_ratio,
                'edge_density': edge_density,
                'method': 'edge_based'
            })

        return regions

    def find_contour_regions(self, gray: np.ndarray, page_area: float) -> List[Dict]:
        """Find regions using contour detection."""
        regions = []
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0

            if area < self.min_area or aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
                continue
            if area / page_area > self.max_area_ratio:
                continue

            regions.append({
                'bbox': (x, y, w, h),
                'area': area,
                'aspect_ratio': aspect_ratio,
                'method': 'contour_based'
            })

        return regions

    def find_grid_regions(self, gray: np.ndarray, page_area: float) -> List[Dict]:
        """Find table regions with grid structures."""
        regions = []
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=2)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=2)

        grid = cv2.bitwise_and(h_lines, v_lines)

        if np.count_nonzero(grid) < 5:
            return []

        table_mask = cv2.addWeighted(h_lines, 0.5, v_lines, 0.5, 0)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        table_mask = cv2.dilate(table_mask, kernel, iterations=3)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0

            if area < self.min_area * 1.5 or aspect_ratio < 0.4 or aspect_ratio > 4.0:
                continue

            roi_grid = grid[y:y+h, x:x+w]
            if np.count_nonzero(roi_grid) < 4:
                continue

            regions.append({
                'bbox': (x, y, w, h),
                'area': area,
                'aspect_ratio': aspect_ratio,
                'method': 'grid_based'
            })

        return regions

    def merge_nearby_regions(self, regions: List[Dict], page_height: int,
                            merge_horizontal_threshold=200, merge_vertical_threshold=100) -> List[Dict]:
        """Merge regions that are close to each other."""
        if not regions:
            return []

        current_regions = [{'bbox': r['bbox'], 'method': r.get('method', 'unknown')} for r in regions]

        changed = True
        max_iterations = 10
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            merged_regions = []
            used = set()

            for i, region1 in enumerate(current_regions):
                if i in used:
                    continue

                x1, y1, w1, h1 = region1['bbox']
                merged_bbox = [x1, y1, x1 + w1, y1 + h1]
                merged_method = region1['method']

                for j, region2 in enumerate(current_regions):
                    if i == j or j in used:
                        continue

                    x2, y2, w2, h2 = region2['bbox']
                    h_gap = max(0, x2 - (x1 + w1), x1 - (x2 + w2))
                    v_gap = max(0, y2 - (y1 + h1), y1 - (y2 + h2))

                    should_merge = False

                    vertical_overlap = min(y1 + h1, y2 + h2) - max(y1, y2)
                    avg_height = (h1 + h2) / 2
                    vertical_overlap_ratio = vertical_overlap / avg_height if avg_height > 0 else 0

                    center_y1 = y1 + h1 / 2
                    center_y2 = y2 + h2 / 2
                    center_y_distance = abs(center_y1 - center_y2)

                    if page_height:
                        row_threshold = page_height * 0.08
                        if (center_y_distance < row_threshold and
                            h_gap < merge_horizontal_threshold * 2.0 and h_gap > 0):
                            should_merge = True

                    if not should_merge and h_gap < merge_horizontal_threshold:
                        center_y_distance_ratio = center_y_distance / avg_height if avg_height > 0 else 1.0
                        if (vertical_overlap_ratio > 0.10 or center_y_distance_ratio < 0.20):
                            should_merge = True

                    if not should_merge and h_gap < merge_horizontal_threshold and v_gap < merge_vertical_threshold:
                        should_merge = True

                    if not should_merge and abs(x1 - x2) < 50 and v_gap < merge_vertical_threshold:
                        should_merge = True

                    if should_merge:
                        merged_bbox[0] = min(merged_bbox[0], x2)
                        merged_bbox[1] = min(merged_bbox[1], y2)
                        merged_bbox[2] = max(merged_bbox[2], x2 + w2)
                        merged_bbox[3] = max(merged_bbox[3], y2 + h2)
                        used.add(j)
                        changed = True

                x = merged_bbox[0]
                y = merged_bbox[1]
                w = merged_bbox[2] - merged_bbox[0]
                h = merged_bbox[3] - merged_bbox[1]

                merged_regions.append({
                    'bbox': (x, y, w, h),
                    'area': w * h,
                    'aspect_ratio': w / h if h > 0 else 0,
                    'method': merged_method
                })
                used.add(i)

            current_regions = merged_regions

        return current_regions

    def filter_regions(self, regions: List[Dict], page_area: float) -> List[Dict]:
        """Filter and remove overlapping/invalid regions."""
        if not regions:
            return []

        filtered = []
        for region in regions:
            area = region['area']
            area_ratio = area / page_area

            if area < self.min_area or area_ratio < self.min_area_ratio or area_ratio > self.max_area_ratio:
                continue

            filtered.append(region)

        def quality_score(region):
            _, _, w, h = region['bbox']
            aspect = w / h if h > 0 else 1
            score = h * 10000 if aspect > 0.5 else region['area']
            if region.get('method') == 'grid_based':
                score *= 1.5
            return score

        filtered = sorted(filtered, key=quality_score, reverse=True)

        final = []
        for region in filtered:
            x1, y1, w1, h1 = region['bbox']
            area1 = w1 * h1
            aspect1 = w1 / h1 if h1 > 0 else 1

            has_overlap = False
            for kept in final:
                x2, y2, w2, h2 = kept['bbox']
                area2 = w2 * h2
                aspect2 = w2 / h2 if h2 > 0 else 1

                iy = max(y1, y2)
                ih = min(y1 + h1, y2 + h2) - iy

                if ih > 0:
                    if aspect1 > 0.5 and aspect2 > 0.5:
                        v_overlap_ratio1 = ih / h1
                        v_overlap_ratio2 = ih / h2
                        if v_overlap_ratio1 > 0.7 or v_overlap_ratio2 > 0.7:
                            has_overlap = True
                            break

                ix = max(x1, x2)
                iw = min(x1 + w1, x2 + w2) - ix

                if iw > 0 and ih > 0:
                    intersection = iw * ih
                    overlap_of_smaller = intersection / min(area1, area2)
                    overlap_of_current = intersection / area1
                    overlap_of_kept = intersection / area2

                    if overlap_of_current > 0.4 or overlap_of_kept > 0.4 or overlap_of_smaller > 0.5:
                        has_overlap = True
                        break

            if not has_overlap:
                final.append(region)

        return final
