"""Caption-based table extractor."""

import re
import fitz
import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CaptionTableExtractor:
    """Extract tables from PDFs by detecting caption patterns at the top."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.table_count = 0

    def find_table_captions(self, page) -> List[Dict]:
        """Find all table captions on a page (e.g., "Table 1.1", "Table 2.3")."""
        captions = []
        table_pattern = r'Table\s+(\d+)\.(\d+)'
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block['type'] != 0:
                continue

            block_text = ""
            for line in block["lines"]:
                for span in line["spans"]:
                    block_text += span["text"] + " "

            block_text = block_text.strip()
            matches = re.finditer(table_pattern, block_text, re.IGNORECASE)

            for match in matches:
                table_num = f"{match.group(1)}.{match.group(2)}"
                bbox = block['bbox']

                if len(block_text) > 30:
                    continue

                verb_patterns = ['shows', 'show', 'complete', 'use',
                                'calculate', 'find', 'determine', 'write']
                if any(verb in block_text.lower() for verb in verb_patterns):
                    continue

                if not block_text.startswith('Table') and len(block_text) > 20:
                    continue

                captions.append({
                    'table_num': table_num,
                    'caption_text': block_text,
                    'caption_bbox': bbox,
                    'page_num': page.number + 1
                })

        unique_captions = []
        seen = set()
        for cap in captions:
            key = (cap['page_num'], cap['table_num'])
            if key not in seen:
                seen.add(key)
                unique_captions.append(cap)

        return unique_captions

    def find_table_region_below_caption(self, page, caption_bbox: List[float], pdf_path: Optional[Path] = None) -> Optional[List[float]]:
        """Find the table region DIRECTLY below a caption."""
        caption_y_bottom = caption_bbox[3]
        page_width = page.rect.width
        page_height = page.rect.height
        page_num = page.number
        MAX_GAP = 150

        # Try pdfplumber first
        if pdf_path and pdf_path.exists():
            try:
                with pdfplumber.open(str(pdf_path)) as pdf:
                    if page_num < len(pdf.pages):
                        pdf_page = pdf.pages[page_num]

                        try:
                            pdf_tables = pdf_page.find_tables()
                            best_match = None
                            best_gap = float('inf')

                            for pdf_table in pdf_tables:
                                table_bbox_obj = None
                                if hasattr(pdf_table, 'bbox') and pdf_table.bbox:
                                    table_bbox_obj = pdf_table.bbox
                                elif hasattr(pdf_table, 'rect') and pdf_table.rect:
                                    rect = pdf_table.rect
                                    table_bbox_obj = (rect.x0, rect.y0, rect.x1, rect.y1)

                                if table_bbox_obj and len(table_bbox_obj) >= 4:
                                    table_y_top_pdfplumber = table_bbox_obj[1]
                                    gap = table_y_top_pdfplumber - caption_y_bottom

                                    if 0 <= gap <= MAX_GAP and gap < best_gap:
                                        best_gap = gap
                                        best_match = [
                                            table_bbox_obj[0],
                                            table_bbox_obj[1],
                                            table_bbox_obj[2],
                                            table_bbox_obj[3]
                                        ]

                            if best_match:
                                logger.info(f"    [pdfplumber] Found table with bbox: {best_match}")
                                return best_match
                        except Exception as e:
                            logger.debug(f"    [pdfplumber] find_tables() issue: {e}")
            except Exception as e:
                logger.debug(f"    [pdfplumber] Error: {e}")

        # Fallback: Find vector graphics below caption
        drawings = page.get_drawings()
        nearby_table_regions = []

        for drawing in drawings:
            rect = drawing['rect']
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0

            if width > 0.8 * page_width or height > 0.8 * page.rect.height:
                continue
            if height < 10:
                continue

            gap = rect.y0 - caption_y_bottom
            if 0 <= gap <= MAX_GAP:
                nearby_table_regions.append({
                    'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                    'gap': gap,
                    'y_top': rect.y0,
                    'y_bottom': rect.y1
                })

        if not nearby_table_regions:
            return None

        nearby_table_regions.sort(key=lambda x: x['y_top'])
        main_region = nearby_table_regions[0]
        table_regions = [main_region]

        for region in nearby_table_regions[1:]:
            if abs(region['y_top'] - main_region['y_top']) < 50:
                table_regions.append(region)

        all_x0 = [r['bbox'][0] for r in table_regions]
        all_y0 = [r['bbox'][1] for r in table_regions]
        all_x1 = [r['bbox'][2] for r in table_regions]
        all_y1 = [r['bbox'][3] for r in table_regions]

        table_top = min(all_y0)
        table_bottom = max(all_y1)
        table_left = min(all_x0)
        table_right = max(all_x1)

        padding_above_caption = 10
        smart_top = max(0, caption_bbox[1] - padding_above_caption)

        page_left_margin = 36
        page_right_margin = page_width - 36

        smart_left = max(page_left_margin, table_left - 10)
        smart_right = min(page_right_margin, table_right + 10)
        smart_bottom = table_bottom + 10

        table_bbox = [smart_left, smart_top, smart_right, smart_bottom]

        return table_bbox

    def extract_table_image(self, page, bbox: List[float], table_num: str) -> Optional[str]:
        """Extract the table region as a high-resolution image."""
        try:
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            mat = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            table_filename = f"Table-{table_num.replace('.', '-')}.png"
            table_path = self.output_dir / table_filename

            pix.save(str(table_path))
            self.table_count += 1

            return table_filename

        except Exception as e:
            logger.error(f"  [ERROR] Failed to extract table: {e}")
            return None

    def extract_all_tables(self, doc, pdf_path: Optional[Path] = None) -> List[Dict]:
        """Extract all tables from the PDF document."""
        all_tables = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            captions = self.find_table_captions(page)

            if not captions:
                continue

            logger.info(f"Page {page_num + 1}: Found {len(captions)} table(s)")

            for caption in captions:
                table_num = caption['table_num']
                caption_bbox = caption['caption_bbox']

                logger.info(f"  Table {table_num}: Locating table region...")

                table_bbox = self.find_table_region_below_caption(page, caption_bbox, pdf_path)

                if table_bbox:
                    filename = self.extract_table_image(page, table_bbox, table_num)

                    if filename:
                        logger.info(f"    [OK] Extracted: {filename}")

                        all_tables.append({
                            'table_num': table_num,
                            'filename': filename,
                            'page': page_num + 1,
                            'bbox': table_bbox,
                            'caption': caption['caption_text'][:100]
                        })
                    else:
                        logger.info(f"    [FAILED] Could not extract image")
                else:
                    logger.info(f"    [SKIP] No table found within 150px of caption")

        return all_tables
