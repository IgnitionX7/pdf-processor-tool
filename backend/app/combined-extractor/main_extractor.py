"""Main combined extractor orchestrator."""

import cv2
import json
import fitz
import numpy as np
import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict, Optional
from pdf2image import convert_from_path

from extractors.caption_figure_extractor import CaptionFigureExtractor
from extractors.caption_table_extractor import CaptionTableExtractor
from extractors.visual_detector import VisualDetector
from extractors.classifier import ElementClassifier
from extractors.table_verifier import TableVerifier
from extractor_utils.helpers import (
    parse_caption_to_question_number,
    convert_pdf_bbox_to_pixel_bbox,
    extract_question_starts_from_page
)

logger = logging.getLogger(__name__)


class CombinedExtractor:
    """
    Combined extractor using both caption-based and visual detection methods.
    """

    def __init__(self, output_dir: str = "extracted", skip_first_page: bool = True, dpi: int = 300,
                 create_pdf_subdir: bool = True):
        """Initialize the combined extractor.

        Args:
            output_dir: Base output directory
            skip_first_page: Skip first page during extraction
            dpi: DPI for image conversion
            create_pdf_subdir: If True, creates a subdirectory named after the PDF.
                              If False, saves directly to output_dir.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.skip_first_page = skip_first_page
        self.dpi = dpi
        self.create_pdf_subdir = create_pdf_subdir

        # Shared tracking across both methods
        self.question_figure_counts = {}
        self.question_table_counts = {}
        self.extracted_regions = []

        # Initialize components
        self.visual_detector = VisualDetector(
            min_area=10000,  # Higher threshold to avoid capturing text
            max_area_ratio=0.70,
            min_area_ratio=0.01,
            min_aspect_ratio=0.2,
            max_aspect_ratio=8.0,  # Allow wider for chemical structures
            min_edge_density=0.01
        )
        self.classifier = ElementClassifier(dpi=dpi)
        self.table_verifier = TableVerifier(dpi=dpi)

    def extract_from_pdf(self, pdf_path: str) -> List[Dict]:
        """Main extraction method combining both approaches."""
        pdf_path = Path(pdf_path)
        logger.info(f"\n{'='*70}")
        logger.info(f"COMBINED EXTRACTION: {pdf_path.name}")
        logger.info(f"{'='*70}")

        # Use subdirectory if requested, otherwise use output_dir directly
        if self.create_pdf_subdir:
            pdf_output_dir = self.output_dir / pdf_path.stem
            pdf_output_dir.mkdir(exist_ok=True)
        else:
            pdf_output_dir = self.output_dir

        # Reset tracking
        self.question_figure_counts = {}
        self.question_table_counts = {}
        self.extracted_regions = []

        all_extractions = []

        # FIRST PASS: Caption-Based Extraction
        logger.info("\n" + "="*70)
        logger.info("PASS 1: CAPTION-BASED EXTRACTION")
        logger.info("="*70)

        caption_extractions = self._extract_with_captions(pdf_path, pdf_output_dir)
        all_extractions.extend(caption_extractions)

        logger.info(f"\nPass 1 Complete: Extracted {len(caption_extractions)} elements with captions")

        # SECOND PASS: Visual Detection
        logger.info("\n" + "="*70)
        logger.info("PASS 2: VISUAL DETECTION (NO-CAPTION)")
        logger.info("="*70)

        visual_extractions = self._extract_without_captions(pdf_path, pdf_output_dir)
        all_extractions.extend(visual_extractions)

        logger.info(f"\nPass 2 Complete: Extracted {len(visual_extractions)} elements (figures + tables)")

        # Save Metadata
        self._save_metadata(all_extractions, pdf_output_dir)

        logger.info(f"\n{'='*70}")
        logger.info(f"EXTRACTION COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Total elements extracted: {len(all_extractions)}")
        logger.info(f"  - With captions: {len(caption_extractions)}")
        logger.info(f"  - Without captions: {len(visual_extractions)}")
        logger.info(f"Output directory: {pdf_output_dir}")
        logger.info(f"{'='*70}\n")

        return all_extractions

    def _extract_with_captions(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """First pass: Extract figures and tables with captions."""
        all_extractions = []

        doc = fitz.open(str(pdf_path))

        # Extract figures with captions
        logger.info("\nExtracting figures with captions...")
        figure_extractor = CaptionFigureExtractor(output_dir=str(output_dir))
        figures = figure_extractor.extract_all_figures(doc)

        for fig in figures:
            question_num = parse_caption_to_question_number(fig.get('caption', ''))
            if question_num is not None:
                if question_num not in self.question_figure_counts:
                    self.question_figure_counts[question_num] = 0
                self.question_figure_counts[question_num] += 1

            page_num = fig['page']
            page = doc[page_num - 1]
            pdf_bbox = fig['bbox']
            pixel_bbox = convert_pdf_bbox_to_pixel_bbox(
                pdf_bbox, self.dpi, page.rect.height
            )

            self.extracted_regions.append({
                'page': page_num,
                'bbox_pixels': pixel_bbox,
                'filename': fig['filename'],
                'source': 'caption',
                'type': 'figure'
            })

            all_extractions.append({
                'page': page_num,
                'type': 'figure',
                'question_num': question_num,
                'bbox': pdf_bbox,
                'filename': fig['filename'],
                'source': 'caption',
                'caption': fig.get('caption', '')
            })

        logger.info(f"Found {len(figures)} figure(s) with captions")

        # Extract tables with captions
        logger.info("\nExtracting tables with captions...")
        table_extractor = CaptionTableExtractor(output_dir=str(output_dir))
        tables = table_extractor.extract_all_tables(doc, pdf_path=pdf_path)

        for tbl in tables:
            question_num = parse_caption_to_question_number(tbl.get('caption', ''))
            if question_num is not None:
                if question_num not in self.question_table_counts:
                    self.question_table_counts[question_num] = 0
                self.question_table_counts[question_num] += 1

            page_num = tbl['page']
            page = doc[page_num - 1]
            pdf_bbox = tbl['bbox']
            pixel_bbox = convert_pdf_bbox_to_pixel_bbox(
                pdf_bbox, self.dpi, page.rect.height
            )

            self.extracted_regions.append({
                'page': page_num,
                'bbox_pixels': pixel_bbox,
                'filename': tbl['filename'],
                'source': 'caption',
                'type': 'table'
            })

            all_extractions.append({
                'page': page_num,
                'type': 'table',
                'question_num': question_num,
                'bbox': pdf_bbox,
                'filename': tbl['filename'],
                'source': 'caption',
                'caption': tbl.get('caption', '')
            })

        logger.info(f"Found {len(tables)} table(s) with captions")

        doc.close()

        return all_extractions

    def _extract_without_captions(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """Second pass: Extract figures and tables without captions."""
        all_extractions = []

        logger.info(f"Converting PDF to images at {self.dpi} DPI...")
        images = convert_from_path(str(pdf_path), dpi=self.dpi)

        logger.info("Detecting question numbers...")
        question_positions = self._extract_question_positions(pdf_path, len(images))

        current_question_context = {'last_question': None}
        start_page = 2 if self.skip_first_page else 1

        for page_num, image in enumerate(images, start=1):
            if page_num < start_page:
                logger.info(f"Skipping page {page_num}")
                continue

            logger.info(f"Processing page {page_num}/{len(images)}")

            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            page_question_positions = question_positions.get(page_num, [])

            if page_question_positions:
                current_question_context['last_question'] = page_question_positions[-1]['qnum']

            # Extract tables using pdfplumber (simple and reliable)
            table_extractions = self._extract_tables_from_page(
                pdf_path, page_num, output_dir, img_cv,
                page_question_positions, current_question_context
            )
            all_extractions.extend(table_extractions)

            # Extract figures using glyph clustering (smart detection for chemical structures)
            figure_extractions = self._extract_figures_using_glyphs(
                pdf_path, page_num, output_dir, img_cv,
                page_question_positions, current_question_context
            )
            all_extractions.extend(figure_extractions)

        return all_extractions

    def _extract_question_positions(self, pdf_path: Path, total_pages: int) -> Dict[int, List[Dict]]:
        """Extract question positions from all pages using pdfplumber."""
        question_positions = {}
        expected_q_number = 1

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                start_page_idx = 1 if self.skip_first_page else 0

                for page_idx in range(start_page_idx, min(len(pdf.pages), total_pages)):
                    page = pdf.pages[page_idx]
                    page_num = page_idx + 1

                    question_starts = extract_question_starts_from_page(page, expected_q_number=expected_q_number)

                    if question_starts:
                        page_questions = []
                        for q_start in question_starts:
                            detected_qnum = q_start.get('qnum')

                            if detected_qnum == expected_q_number:
                                page_questions.append({
                                    'qnum': detected_qnum,
                                    'y_relative': q_start['bbox'][1] / page.height,
                                    'y_absolute': q_start['bbox'][1]
                                })
                                expected_q_number += 1
                            elif detected_qnum > expected_q_number:
                                logger.warning(f"Page {page_num}: Detected Q{detected_qnum} but expected Q{expected_q_number}")

                        if page_questions:
                            question_positions[page_num] = page_questions
                            logger.info(f"Page {page_num}: Found {len(page_questions)} question(s)")

        except Exception as e:
            logger.warning(f"Error extracting question positions: {e}")

        return question_positions

    def _expand_region_to_include_text_labels(self, image: np.ndarray, x: int, y: int, w: int, h: int,
                                               pdf_path: Path, page_num: int) -> tuple:
        """
        Expand a figure region to include text labels above and below.
        Returns expanded (x1, y1, x2, y2) coordinates.
        """
        page_height, page_width = image.shape[:2]

        # Initial bounds
        x1, y1, x2, y2 = x, y, x + w, y + h

        try:
            import pdfplumber
            pdf = pdfplumber.open(str(pdf_path))
            page = pdf.pages[page_num - 1]

            # Get all text on the page
            words = page.extract_words()

            if not words:
                pdf.close()
                return x1, y1, x2, y2

            # Convert PDF coordinates to pixel coordinates
            scale_x = page_width / page.width
            scale_y = page_height / page.height

            # Find text lines above the region (within reasonable distance)
            search_distance_above = int(page_height * 0.05)  # 5% of page height
            text_above = []

            for word in words:
                word_x0 = word['x0'] * scale_x
                word_y0 = word['top'] * scale_y
                word_x1 = word['x1'] * scale_x
                word_y1 = word['bottom'] * scale_y

                # Check if text is above and near the region
                if word_y1 < y1 and word_y1 > (y1 - search_distance_above):
                    # Check horizontal overlap
                    if not (word_x1 < x1 or word_x0 > x2):
                        text_above.append(word_y0)

            # Find text lines below the region
            search_distance_below = int(page_height * 0.03)  # 3% of page height
            text_below = []

            for word in words:
                word_x0 = word['x0'] * scale_x
                word_y0 = word['top'] * scale_y
                word_x1 = word['x1'] * scale_x
                word_y1 = word['bottom'] * scale_y

                # Check if text is below and near the region
                if word_y0 > y2 and word_y0 < (y2 + search_distance_below):
                    # Check horizontal overlap
                    if not (word_x1 < x1 or word_x0 > x2):
                        text_below.append(word_y1)

            # Expand to include closest text line above
            if text_above:
                closest_text_top = min(text_above)
                y1 = max(0, int(closest_text_top))

            # Expand to include closest text line below
            if text_below:
                closest_text_bottom = max(text_below)
                y2 = min(page_height, int(closest_text_bottom))

            pdf.close()

        except Exception as e:
            logger.debug(f"Could not expand region for text labels: {e}")

        return x1, y1, x2, y2

    def _extract_tables_from_page(self, pdf_path: Path, page_num: int, output_dir: Path,
                                   image: np.ndarray, page_question_positions: List[Dict],
                                   current_question_context: Dict) -> List[Dict]:
        """Extract tables using pdfplumber only - simple and reliable."""
        import pdfplumber

        extractions = []
        page_height, page_width = image.shape[:2]

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                page = pdf.pages[page_num - 1]
                tables = page.find_tables()

                if not tables:
                    return []

                logger.info(f"  Found {len(tables)} table(s) via pdfplumber")

                for idx, table in enumerate(tables):
                    # Get table bbox in PDF coordinates
                    bbox_pdf = table.bbox  # (x0, y0, x1, y1) in PDF coords

                    # Convert to pixel coordinates
                    scale_x = page_width / page.width
                    scale_y = page_height / page.height

                    x1 = int(bbox_pdf[0] * scale_x)
                    y1 = int(bbox_pdf[1] * scale_y)
                    x2 = int(bbox_pdf[2] * scale_x)
                    y2 = int(bbox_pdf[3] * scale_y)

                    # Ensure bounds are valid
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(page_width, x2), min(page_height, y2)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    bbox_pixels = [x1, y1, x2, y2]

                    # Check for duplicates
                    if self._is_duplicate_region(page_num, bbox_pixels):
                        logger.info(f"  Skipping duplicate table on page {page_num}")
                        continue

                    # Extract image
                    extracted_img = image[y1:y2, x1:x2]

                    # Determine question number
                    center_y = (y1 + y2) / 2
                    question_num = self._determine_question_number(
                        center_y, page_height, page_question_positions, current_question_context
                    )

                    # Generate filename
                    if question_num is not None:
                        if question_num not in self.question_table_counts:
                            self.question_table_counts[question_num] = 0
                        self.question_table_counts[question_num] += 1
                        table_index = self.question_table_counts[question_num]
                        filename = f"Table-{question_num}-{table_index}.png"
                    else:
                        filename = f"{pdf_path.stem}_page{page_num}_table{idx+1}.png"

                    # Save image
                    filepath = output_dir / filename
                    cv2.imwrite(str(filepath), extracted_img)

                    # Track extracted region
                    self.extracted_regions.append({
                        'page': page_num,
                        'bbox_pixels': bbox_pixels,
                        'filename': filename,
                        'source': 'pdfplumber',
                        'type': 'table'
                    })

                    extractions.append({
                        'page': page_num,
                        'type': 'table',
                        'question_num': question_num,
                        'bbox': {'x': x1, 'y': y1, 'width': x2-x1, 'height': y2-y1},
                        'filename': filename,
                        'source': 'pdfplumber',
                        'pdf_name': pdf_path.stem
                    })

                    if question_num is not None:
                        logger.info(f"  ✓ Extracted table -> Q{question_num} ({filename})")
                    else:
                        logger.info(f"  ✓ Extracted table ({filename})")

        except Exception as e:
            logger.warning(f"Error extracting tables from page {page_num}: {e}")

        return extractions

    def _extract_figures_using_glyphs(self, pdf_path: Path, page_num: int, output_dir: Path,
                                       image: np.ndarray, page_question_positions: List[Dict],
                                       current_question_context: Dict) -> List[Dict]:
        """Extract figures by detecting glyph clusters (chemical structures, diagrams)."""
        import pdfplumber
        from collections import defaultdict

        extractions = []
        page_height, page_width = image.shape[:2]
        page_area = page_height * page_width

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                page = pdf.pages[page_num - 1]

                # Get all chars, lines, and rects (all contribute to figures)
                chars = page.chars
                lines = page.lines if hasattr(page, 'lines') else []
                rects = page.rects if hasattr(page, 'rects') else []

                # Combine all elements as "glyphs" with normalized structure
                # BUT exclude small dots/segments that are part of dotted answer lines
                all_glyphs = []

                # Add chars (but exclude very small dots)
                for char in chars:
                    char_width = char['x1'] - char['x0']
                    char_height = char['bottom'] - char['top']

                    # Skip tiny dots (< 3 units in width or height)
                    if char_width < 3 and char_height < 3:
                        continue

                    all_glyphs.append({
                        'x0': char['x0'],
                        'top': char['top'],
                        'x1': char['x1'],
                        'bottom': char['bottom'],
                        'type': 'char'
                    })

                # Add lines (but exclude tiny dot-like line segments)
                for line in lines:
                    line_width = abs(line['x1'] - line['x0'])
                    line_height = abs(line['bottom'] - line['top'])

                    # Skip very small line segments that are likely dots in dotted lines
                    # (e.g., width < 5 AND horizontal)
                    if line_height < 2 and line_width < 5:
                        continue

                    all_glyphs.append({
                        'x0': line['x0'],
                        'top': line['top'],
                        'x1': line['x1'],
                        'bottom': line['bottom'],
                        'type': 'line'
                    })

                # Add rects (but exclude tiny dot-like rects)
                for rect in rects:
                    rect_width = rect['x1'] - rect['x0']
                    rect_height = rect['bottom'] - rect['top']

                    # Skip tiny rectangles (< 3 units)
                    if rect_width < 3 and rect_height < 3:
                        continue

                    all_glyphs.append({
                        'x0': rect['x0'],
                        'top': rect['top'],
                        'x1': rect['x1'],
                        'bottom': rect['bottom'],
                        'type': 'rect'
                    })

                if not all_glyphs:
                    return []

                # Convert to pixel coordinates
                scale_x = page_width / page.width
                scale_y = page_height / page.height

                # Identify text lines (lines that START near left margin)
                text_lines = []
                LEFT_MARGIN_THRESHOLD = page.width * 0.15  # Text starts within 15% from left

                # Group char glyphs by Y position
                y_groups = defaultdict(list)
                for glyph in all_glyphs:
                    if glyph['type'] == 'char':
                        y_key = round(glyph['top'], 1)
                        y_groups[y_key].append(glyph)

                for y_pos, glyphs_on_line in y_groups.items():
                    if len(glyphs_on_line) >= 5:  # 5+ chars on same line
                        # Sort by x position to find first char
                        glyphs_sorted = sorted(glyphs_on_line, key=lambda g: g['x0'])
                        first_char_x = glyphs_sorted[0]['x0']

                        # Only consider it a text line if it starts near left margin
                        if first_char_x < LEFT_MARGIN_THRESHOLD:
                            y_pixel = int(y_pos * scale_y)
                            text_lines.append(y_pixel)

                text_lines = sorted(text_lines)

                # Detect dotted answer lines (many small line segments at same Y)
                dotted_line_y_positions = []
                if lines:
                    from collections import Counter
                    # Group lines by Y position
                    y_line_counts = Counter()
                    line_segments_by_y = defaultdict(list)

                    for line in lines:
                        # Check if it's a horizontal line segment
                        if abs(line['y0'] - line['y1']) < 2:  # Horizontal
                            line_width = abs(line['x1'] - line['x0'])

                            # Detect both short dotted segments AND continuous long lines
                            # Short segments (dots): width < 15
                            # Long continuous lines: width > page.width * 0.3
                            if line_width < 15 or line_width > page.width * 0.3:
                                y_key = round(line['y0'], 0)
                                y_line_counts[y_key] += 1
                                line_segments_by_y[y_key].append(line_width)

                    # If there are 10+ short segments OR 1+ long line at same Y, it's a dotted/answer line
                    for y_pos, count in y_line_counts.items():
                        segments = line_segments_by_y[y_pos]
                        max_segment = max(segments) if segments else 0

                        # Dotted line: many short segments
                        # Continuous answer line: one or more long segments
                        if count >= 10 or max_segment > page.width * 0.3:
                            y_pixel = int(y_pos * scale_y)
                            dotted_line_y_positions.append(y_pixel)

                # Find glyph clusters (chars + lines + rects that are NOT text lines or dotted lines)
                non_text_glyphs = []

                # Track which char glyphs are dots (.) for filtering
                dot_char_indices = set()
                for i, char in enumerate(chars):
                    if char.get('text') == '.':
                        dot_char_indices.add(i)

                char_index = 0
                for glyph in all_glyphs:
                    glyph_y_pixel = int(glyph['top'] * scale_y)

                    # Skip if it's part of a text line
                    is_text_line = any(abs(glyph_y_pixel - tl) < 10 for tl in text_lines)
                    if is_text_line:
                        if glyph['type'] == 'char':
                            char_index += 1
                        continue

                    # Skip if it's part of a dotted answer line (with wider tolerance)
                    # Dotted lines include the line segments AND surrounding dots/marks
                    is_dotted_line = any(abs(glyph_y_pixel - dl) < 20 for dl in dotted_line_y_positions)
                    if is_dotted_line:
                        if glyph['type'] == 'char':
                            char_index += 1
                        continue

                    # Skip dot characters (.) completely - they're never part of meaningful figures
                    if glyph['type'] == 'char':
                        if char_index in dot_char_indices:
                            char_index += 1
                            continue
                        char_index += 1

                    non_text_glyphs.append(glyph)

                # Cluster glyphs into figure regions
                MIN_GLYPHS = 25  # Minimum glyphs to be a figure (filters out small junk)

                if len(non_text_glyphs) < MIN_GLYPHS:
                    return []

                # Spatial clustering
                figure_regions = []
                CLUSTER_DISTANCE = 50  # PDF units

                visited = set()
                for i, glyph in enumerate(non_text_glyphs):
                    if i in visited:
                        continue

                    cluster = [glyph]
                    visited.add(i)

                    # Find nearby glyphs
                    changed = True
                    while changed:
                        changed = False
                        for j, other_glyph in enumerate(non_text_glyphs):
                            if j in visited:
                                continue

                            for c in cluster:
                                dx = abs(other_glyph['x0'] - c['x0'])
                                dy = abs(other_glyph['top'] - c['top'])
                                if dx < CLUSTER_DISTANCE and dy < CLUSTER_DISTANCE:
                                    cluster.append(other_glyph)
                                    visited.add(j)
                                    changed = True
                                    break

                    if len(cluster) >= MIN_GLYPHS:
                        # Calculate bounding box
                        x0 = min(c['x0'] for c in cluster)
                        y0 = min(c['top'] for c in cluster)
                        x1 = max(c['x1'] for c in cluster)
                        y1 = max(c['bottom'] for c in cluster)

                        # Filter out answer line clusters and text-heavy content
                        # Only keep true chemical structures/molecular diagrams
                        cluster_width = x1 - x0
                        cluster_height = y1 - y0

                        # Count different types of glyphs
                        line_glyphs = sum(1 for g in cluster if g['type'] == 'line')
                        rect_glyphs = sum(1 for g in cluster if g['type'] == 'rect')
                        char_glyphs = sum(1 for g in cluster if g['type'] == 'char')

                        line_ratio = line_glyphs / len(cluster) if len(cluster) > 0 else 0
                        rect_ratio = rect_glyphs / len(cluster) if len(cluster) > 0 else 0

                        # Chemical structures have good balance of lines/rects and chars
                        # NOT mostly chars (that's text), NOT mostly lines (that's answer lines)
                        structural_glyphs = line_glyphs + rect_glyphs
                        structural_ratio = structural_glyphs / len(cluster) if len(cluster) > 0 else 0

                        # Check if cluster is on the right side of the page
                        is_right_aligned = x1 > page.width * 0.85

                        if cluster_height > 0:
                            cluster_aspect = cluster_width / cluster_height

                            # RULE 1: Skip if very wide and short (answer lines)
                            if cluster_aspect > 20:
                                logger.debug(f"  Skipping answer line cluster (aspect={cluster_aspect:.1f})")
                                continue

                            # RULE 2: Skip if mostly lines with high aspect ratio (dotted lines)
                            if line_ratio > 0.7 and cluster_aspect > 10:
                                logger.debug(f"  Skipping line-heavy cluster (lines={line_ratio:.1%}, aspect={cluster_aspect:.1f})")
                                continue

                            # RULE 3: Skip very short clusters (height < 30 PDF units)
                            if cluster_height < 30:
                                logger.debug(f"  Skipping very short cluster (height={cluster_height:.1f})")
                                continue

                            # RULE 4: Skip sparse clusters (few chars + mostly lines = answer line)
                            if char_glyphs < 20 and line_ratio > 0.6:
                                logger.debug(f"  Skipping sparse text + line cluster (chars={char_glyphs}, line_ratio={line_ratio:.1%})")
                                continue

                            # RULE 5: Skip right-aligned short content (mark indicators)
                            if is_right_aligned and cluster_height < 40:
                                logger.debug(f"  Skipping right-aligned mark indicator (height={cluster_height:.1f})")
                                continue

                            # RULE 6: Chemical structures must have significant structural elements
                            # If cluster is mostly chars (>80%) and few structural elements, it's text not a diagram
                            char_ratio = char_glyphs / len(cluster) if len(cluster) > 0 else 0
                            if char_ratio > 0.8 and structural_ratio < 0.2:
                                logger.debug(f"  Skipping text-heavy cluster (chars={char_ratio:.1%}, structural={structural_ratio:.1%})")
                                continue

                            # RULE 7: Clusters must have minimum structural complexity
                            # Chemical structures need at least 15 structural glyphs (lines/rects)
                            if structural_glyphs < 15:
                                logger.debug(f"  Skipping low structural complexity (structural_glyphs={structural_glyphs})")
                                continue

                        figure_regions.append({
                            'bbox_pdf': (x0, y0, x1, y1),
                            'glyph_count': len(cluster)
                        })

                # Extract each figure region
                for idx, region in enumerate(figure_regions):
                    x0_pdf, y0_pdf, x1_pdf, y1_pdf = region['bbox_pdf']

                    # Convert to pixels for Y coordinates
                    y1 = int(y0_pdf * scale_y)
                    y2 = int(y1_pdf * scale_y)

                    # Expand to FULL PAGE WIDTH
                    x1 = 0
                    x2 = page_width

                    # Find text line above and crop BELOW it (exclude the text line itself)
                    text_above = [tl for tl in text_lines if tl < y1]
                    if text_above:
                        closest_above = max(text_above)
                        # Start crop BELOW this text line (add ~30 pixels to skip the text)
                        y1 = closest_above + 30

                    # Find text line below and crop ABOVE it (exclude the text line itself)
                    text_below = [tl for tl in text_lines if tl > y2]
                    if text_below:
                        closest_below = min(text_below)
                        # End crop ABOVE this text line (subtract ~10 pixels to exclude it)
                        y2 = closest_below - 10

                    # Add padding top and bottom
                    y1 = max(0, y1 - 10)
                    y2 = min(page_height, y2 + 10)

                    bbox_pixels = [x1, y1, x2, y2]

                    # Filter out regions that are too small after expansion
                    region_area = (x2 - x1) * (y2 - y1)
                    MIN_REGION_AREA = page_area * 0.005  # At least 0.5% of page area
                    if region_area < MIN_REGION_AREA:
                        continue

                    # Filter out dotted answer lines and single-line elements
                    region_width = x2 - x1
                    region_height = y2 - y1

                    # Filter by absolute height (answer lines are typically < 250 pixels at 300dpi)
                    MAX_SINGLE_LINE_HEIGHT = 250
                    if region_height < MAX_SINGLE_LINE_HEIGHT:
                        # Further check: if aspect ratio is high, it's definitely a line
                        if region_height > 0:
                            aspect_ratio = region_width / region_height
                            # If aspect ratio > 8 (very wide, very short), it's likely a line/junk
                            if aspect_ratio > 8:
                                logger.debug(f"  Filtering out thin horizontal line/element (h={region_height}px, aspect={aspect_ratio:.1f})")
                                continue

                    # Check for duplicates
                    if self._is_duplicate_region(page_num, bbox_pixels):
                        continue

                    # Extract image
                    extracted_img = image[y1:y2, x1:x2]

                    # Determine question number
                    center_y = (y1 + y2) / 2
                    question_num = self._determine_question_number(
                        center_y, page_height, page_question_positions, current_question_context
                    )

                    # Generate filename
                    if question_num is not None:
                        if question_num not in self.question_figure_counts:
                            self.question_figure_counts[question_num] = 0
                        self.question_figure_counts[question_num] += 1
                        fig_index = self.question_figure_counts[question_num]
                        filename = f"Fig-{question_num}-{fig_index}.png"
                    else:
                        filename = f"{pdf_path.stem}_page{page_num}_fig{idx+1}.png"

                    # Save image
                    filepath = output_dir / filename
                    cv2.imwrite(str(filepath), extracted_img)

                    # Track extracted region
                    self.extracted_regions.append({
                        'page': page_num,
                        'bbox_pixels': bbox_pixels,
                        'filename': filename,
                        'source': 'glyph_clustering',
                        'type': 'figure'
                    })

                    extractions.append({
                        'page': page_num,
                        'type': 'figure',
                        'question_num': question_num,
                        'bbox': {'x': x1, 'y': y1, 'width': x2-x1, 'height': y2-y1},
                        'filename': filename,
                        'source': 'glyph_clustering',
                        'glyph_count': region['glyph_count'],
                        'pdf_name': pdf_path.stem
                    })

                    if question_num is not None:
                        logger.info(f"  ✓ Extracted figure -> Q{question_num} ({filename}) [{region['glyph_count']} glyphs]")
                    else:
                        logger.info(f"  ✓ Extracted figure ({filename}) [{region['glyph_count']} glyphs]")

        except Exception as e:
            logger.warning(f"Error extracting figures from page {page_num}: {e}")

        return extractions

    def _extract_from_page(
        self, image: np.ndarray, page_num: int, output_dir: Path, pdf_name: str, pdf_path: Path,
        page_question_positions: List[Dict], current_question_context: Dict
    ) -> List[Dict]:
        """Extract figures from a page using visual detection, filtering duplicates."""
        page_height, page_width = image.shape[:2]
        page_area = page_height * page_width

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        all_regions = self.visual_detector.find_all_regions(image, gray, page_area)
        merged_regions = self.visual_detector.merge_nearby_regions(all_regions, page_height)
        final_regions = self.visual_detector.filter_regions(merged_regions, page_area)

        extractions = []
        for idx, region in enumerate(final_regions):
            x, y, w, h = region['bbox']
            aspect_ratio = w / h if h > 0 else 1

            if aspect_ratio > 0.5:
                page_margin = 80
                x1 = page_margin
                x2 = page_width - page_margin
            else:
                h_padding = 40
                x1 = max(0, x - h_padding)
                x2 = min(page_width, x + w + h_padding)

            v_padding_top = 25
            v_padding_bottom = 60
            y1 = max(0, y - v_padding_top)
            y2 = min(page_height, y + h + v_padding_bottom)

            bbox_pixels = [x1, y1, x2, y2]
            if self._is_duplicate_region(page_num, bbox_pixels):
                logger.info(f"  Skipping duplicate region on page {page_num}")
                continue

            extracted_img = image[y1:y2, x1:x2]
            element_type = self.classifier.classify_element(extracted_img, region)

            # Filter out pure text regions early (before expansion)
            if self.classifier.is_regular_text_region(pdf_path, page_num, bbox_pixels):
                logger.info(f"  Skipping text region on page {page_num}")
                continue

            # For figures, expand to include text labels above and below
            if element_type == 'figure':
                x1_expanded, y1_expanded, x2_expanded, y2_expanded = self._expand_region_to_include_text_labels(
                    image, x, y, w, h, pdf_path, page_num
                )
                bbox_pixels = [x1_expanded, y1_expanded, x2_expanded, y2_expanded]
                # Re-check for duplicates with expanded bbox
                if self._is_duplicate_region(page_num, bbox_pixels):
                    logger.info(f"  Skipping duplicate figure region on page {page_num}")
                    continue
                # Re-extract with expanded bbox
                x1, y1, x2, y2 = x1_expanded, y1_expanded, x2_expanded, y2_expanded
                extracted_img = image[y1:y2, x1:x2]

            # Verify tables using pdfplumber
            if element_type == 'table':
                verified_table = self.table_verifier.does_region_contain_verified_table(
                    pdf_path, page_num, bbox_pixels, min_overlap=0.3
                )

                if verified_table:
                    logger.debug(f"  Table verified by pdfplumber on page {page_num}")
                else:
                    # Not verified by pdfplumber - reclassify as figure
                    # (could be a diagram or chemical structure misclassified as table)
                    logger.debug(f"  Table not verified by pdfplumber, reclassifying as figure")
                    element_type = 'figure'
                    # Expand to include labels now that it's a figure
                    x1_expanded, y1_expanded, x2_expanded, y2_expanded = self._expand_region_to_include_text_labels(
                        image, x, y, w, h, pdf_path, page_num
                    )
                    bbox_pixels = [x1_expanded, y1_expanded, x2_expanded, y2_expanded]
                    if self._is_duplicate_region(page_num, bbox_pixels):
                        logger.info(f"  Skipping duplicate reclassified figure on page {page_num}")
                        continue
                    x1, y1, x2, y2 = x1_expanded, y1_expanded, x2_expanded, y2_expanded
                    extracted_img = image[y1:y2, x1:x2]

            question_num = self._determine_question_number(
                y, page_height, page_question_positions, current_question_context
            )

            if question_num is not None:
                if element_type == 'figure':
                    if question_num not in self.question_figure_counts:
                        self.question_figure_counts[question_num] = 0
                    self.question_figure_counts[question_num] += 1
                    figure_index = self.question_figure_counts[question_num]
                    filename = f"Fig-{question_num}-{figure_index}.png"
                else:
                    if question_num not in self.question_table_counts:
                        self.question_table_counts[question_num] = 0
                    self.question_table_counts[question_num] += 1
                    table_index = self.question_table_counts[question_num]
                    filename = f"Table-{question_num}-{table_index}.png"
            else:
                logger.warning(f"  Could not determine question for {element_type} on page {page_num}")
                filename = f"{pdf_name}_page{page_num}_{element_type}{idx+1}.png"

            filepath = output_dir / filename
            cv2.imwrite(str(filepath), extracted_img)

            self.extracted_regions.append({
                'page': page_num,
                'bbox_pixels': bbox_pixels,
                'filename': filename,
                'source': 'visual',
                'type': element_type
            })

            extractions.append({
                'page': page_num,
                'type': element_type,
                'question_num': question_num,
                'bbox': {'x': x1, 'y': y1, 'width': x2-x1, 'height': y2-y1},
                'area': region['area'],
                'aspect_ratio': round(region['aspect_ratio'], 2),
                'filename': filename,
                'method': region.get('method', 'merged'),
                'source': 'visual',
                'pdf_name': pdf_name
            })

            if question_num is not None:
                logger.info(f"  ✓ Extracted {element_type} -> Q{question_num} ({filename})")
            else:
                logger.info(f"  ✓ Extracted {element_type} ({filename})")

        return extractions

    def _is_duplicate_region(self, page_num: int, bbox_pixels: List[float]) -> bool:
        """Check if a region overlaps significantly with already extracted regions."""
        for extracted in self.extracted_regions:
            if extracted['page'] != page_num:
                continue

            x_left = max(bbox_pixels[0], extracted['bbox_pixels'][0])
            y_top = max(bbox_pixels[1], extracted['bbox_pixels'][1])
            x_right = min(bbox_pixels[2], extracted['bbox_pixels'][2])
            y_bottom = min(bbox_pixels[3], extracted['bbox_pixels'][3])

            if x_right < x_left or y_bottom < y_top:
                continue

            intersection_area = (x_right - x_left) * (y_bottom - y_top)

            area1 = (bbox_pixels[2] - bbox_pixels[0]) * (bbox_pixels[3] - bbox_pixels[1])
            area2 = (extracted['bbox_pixels'][2] - extracted['bbox_pixels'][0]) * \
                    (extracted['bbox_pixels'][3] - extracted['bbox_pixels'][1])

            smaller_area = min(area1, area2)
            overlap_ratio = intersection_area / smaller_area if smaller_area > 0 else 0

            if overlap_ratio > 0.5:
                logger.debug(f"  Duplicate detected (overlap={overlap_ratio:.2f}) with {extracted['filename']} (source: {extracted['source']}), skipping")
                return True

        return False

    def _determine_question_number(
        self, figure_y: int, page_height: int,
        page_question_positions: List[Dict], current_question_context: Dict
    ) -> Optional[int]:
        """Determine which question a figure belongs to based on its Y position."""
        if not page_question_positions:
            return current_question_context.get('last_question')

        figure_y_relative = figure_y / page_height
        sorted_questions = sorted(page_question_positions, key=lambda q: q['y_relative'])

        for i, question in enumerate(sorted_questions):
            question_y_relative = question['y_relative']

            if figure_y_relative >= question_y_relative:
                if i + 1 < len(sorted_questions):
                    next_question_y_relative = sorted_questions[i + 1]['y_relative']
                    if figure_y_relative < next_question_y_relative:
                        return question['qnum']
                else:
                    return question['qnum']

        if sorted_questions:
            first_question = sorted_questions[0]
            if figure_y_relative < first_question['y_relative'] + 0.2:
                return first_question['qnum']

        return None

    def _extract_verified_tables(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """Third pass: Extract tables verified by pdfplumber that weren't caught in previous passes."""
        all_extractions = []

        logger.info(f"Converting PDF to images at {self.dpi} DPI...")
        images = convert_from_path(str(pdf_path), dpi=self.dpi)

        logger.info("Detecting question numbers...")
        question_positions = self._extract_question_positions(pdf_path, len(images))

        current_question_context = {'last_question': None}
        start_page = 2 if self.skip_first_page else 1

        doc = fitz.open(str(pdf_path))

        for page_num, image in enumerate(images, start=1):
            if page_num < start_page:
                logger.info(f"Skipping page {page_num}")
                continue

            logger.info(f"Processing page {page_num}/{len(images)}")

            # Update question context
            page_question_positions = question_positions.get(page_num, [])
            if page_question_positions:
                current_question_context['last_question'] = page_question_positions[-1]['qnum']

            # Find unextracted tables on this page
            unextracted_tables = self.table_verifier.find_unextracted_tables(
                pdf_path, page_num, self.extracted_regions
            )

            if not unextracted_tables:
                continue

            logger.info(f"  Found {len(unextracted_tables)} unextracted pdfplumber table(s)")

            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            page_height, page_width = img_cv.shape[:2]
            page = doc[page_num - 1]

            for idx, table_info in enumerate(unextracted_tables):
                bbox_pixels = table_info['bbox_pixels']
                x1, y1, x2, y2 = [int(v) for v in bbox_pixels]

                # Ensure bounds are within image
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(page_width, x2)
                y2 = min(page_height, y2)

                if x2 <= x1 or y2 <= y1:
                    logger.warning(f"  Invalid bbox for table on page {page_num}, skipping")
                    continue

                # Check for duplicates
                bbox_pixels_adjusted = [x1, y1, x2, y2]
                if self._is_duplicate_region(page_num, bbox_pixels_adjusted):
                    logger.info(f"  Skipping duplicate verified table on page {page_num}")
                    continue

                # Extract image
                extracted_img = img_cv[y1:y2, x1:x2]

                # Determine question number
                center_y = (y1 + y2) / 2
                question_num = self._determine_question_number(
                    center_y, page_height, page_question_positions, current_question_context
                )

                # Generate filename
                if question_num is not None:
                    if question_num not in self.question_table_counts:
                        self.question_table_counts[question_num] = 0
                    self.question_table_counts[question_num] += 1
                    table_index = self.question_table_counts[question_num]
                    filename = f"Table-{question_num}-{table_index}.png"
                else:
                    logger.warning(f"  Could not determine question for verified table on page {page_num}")
                    filename = f"{pdf_path.stem}_page{page_num}_verified_table{idx+1}.png"

                # Save image
                filepath = output_dir / filename
                cv2.imwrite(str(filepath), extracted_img)

                # Track extracted region
                self.extracted_regions.append({
                    'page': page_num,
                    'bbox_pixels': bbox_pixels_adjusted,
                    'filename': filename,
                    'source': 'pdfplumber_verified',
                    'type': 'table'
                })

                # Convert to PDF bbox for metadata
                pdf_bbox = table_info.get('bbox_pdf', [])

                all_extractions.append({
                    'page': page_num,
                    'type': 'table',
                    'question_num': question_num,
                    'bbox': pdf_bbox if pdf_bbox else {'x': x1, 'y': y1, 'width': x2-x1, 'height': y2-y1},
                    'filename': filename,
                    'source': 'pdfplumber_verified',
                    'verified_by_pdfplumber': True,
                    'pdf_name': pdf_path.stem
                })

                if question_num is not None:
                    logger.info(f"  ✓ Extracted verified table -> Q{question_num} ({filename})")
                else:
                    logger.info(f"  ✓ Extracted verified table ({filename})")

        doc.close()
        return all_extractions

    def _save_metadata(self, extractions: List[Dict], output_dir: Path):
        """Save extraction metadata to JSON file."""
        metadata_file = output_dir / "extraction_metadata.json"

        with open(metadata_file, 'w') as f:
            json.dump({
                'total_elements': len(extractions),
                'elements': extractions
            }, f, indent=2)

        logger.info(f"Metadata saved to: {metadata_file}")
