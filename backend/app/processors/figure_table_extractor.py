"""
PDF Figure & Table Extractor - Unified extraction tool
Extracts figures and tables from PDFs by detecting caption patterns
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

import fitz  # PyMuPDF
from PIL import Image
import numpy as np


class FigureExtractor:
    """Extract figures from PDFs by detecting caption patterns"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.figure_count = 0

    def find_figure_captions(self, page) -> List[Dict]:
        """
        Find all figure captions on a page (e.g., "Fig. 1.1", "Fig. 2.3")
        Only detects standalone captions, not references in question text
        """
        captions = []

        # Pattern to match Fig. X.Y (with various spacing)
        fig_pattern = r'Fig\.\s*(\d+)\.(\d+)'

        # Get text blocks with positions
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block['type'] != 0:  # Not a text block
                continue

            # Extract text from block
            block_text = ""
            for line in block["lines"]:
                for span in line["spans"]:
                    block_text += span["text"] + " "

            block_text = block_text.strip()

            # Search for figure caption pattern
            matches = re.finditer(fig_pattern, block_text, re.IGNORECASE)

            for match in matches:
                fig_num = f"{match.group(1)}.{match.group(2)}"
                bbox = block['bbox']

                # CRITICAL: Only accept SHORT captions (actual figure labels)
                # Actual captions are typically < 25 characters
                # Examples: "Fig. 1.1", "Fig. 2.3 [2]", "Fig. 10.5"

                # Exclude long text that mentions figures
                if len(block_text) > 25:
                    continue

                # Exclude text with verbs (question/instruction text)
                verb_patterns = ['shows', 'show', 'sketch', 'draw', 'calculate',
                                'find', 'determine', 'use', 'complete', 'label']
                if any(verb in block_text.lower() for verb in verb_patterns):
                    continue

                # Must start with Fig. or be very short
                if not block_text.startswith('Fig.') and len(block_text) > 15:
                    continue

                captions.append({
                    'fig_num': fig_num,
                    'caption_text': block_text,
                    'caption_bbox': bbox,
                    'page_num': page.number + 1
                })

        # Remove duplicates (same fig_num on same page)
        unique_captions = []
        seen = set()
        for cap in captions:
            key = (cap['page_num'], cap['fig_num'])
            if key not in seen:
                seen.add(key)
                unique_captions.append(cap)

        return unique_captions

    def find_text_boundary_above_figure(self, page, figure_y_top: float) -> float:
        """
        Find the boundary above the figure by detecting full text lines
        Returns the Y coordinate just below the last full text line
        """
        # Get all text blocks on the page
        blocks = page.get_text("dict")["blocks"]

        # Find text blocks above the figure
        text_lines_above = []

        for block in blocks:
            if block['type'] != 0:  # Not a text block
                continue

            block_bbox = block['bbox']
            block_y_bottom = block_bbox[3]
            block_width = block_bbox[2] - block_bbox[0]

            # Check if this block is above the figure
            if block_y_bottom < figure_y_top:
                # Extract text to check if it's a full line
                block_text = ""
                for line in block['lines']:
                    for span in line['spans']:
                        block_text += span['text']

                # Consider it a "full text line" if:
                # 1. It's relatively wide (> 40% of page width)
                # 2. It contains multiple words (not just a label)
                page_width = page.rect.width
                is_full_line = (block_width > 0.4 * page_width and
                               len(block_text.split()) >= 4)

                text_lines_above.append({
                    'bbox': block_bbox,
                    'y_bottom': block_y_bottom,
                    'is_full_line': is_full_line,
                    'text': block_text[:50]  # For debugging
                })

        if not text_lines_above:
            # No text above, use figure top with small padding
            return figure_y_top - 10

        # Sort by y_bottom (descending) - closest to figure first
        text_lines_above.sort(key=lambda x: x['y_bottom'], reverse=True)

        # Find the first full text line (closest to figure going up)
        for text_line in text_lines_above:
            if text_line['is_full_line']:
                # Return just below this full line
                return text_line['y_bottom'] + 5

        # No full text line found, return the topmost text above with padding
        return text_lines_above[-1]['bbox'][1] - 10

    def find_figure_region_above_caption(self, page, caption_bbox: List[float]) -> Optional[List[float]]:
        """
        Find the figure region DIRECTLY above a caption
        Uses smart boundaries: text detection for top, page margins for sides
        """
        caption_y_top = caption_bbox[1]  # Top of caption
        page_width = page.rect.width
        page_height = page.rect.height

        # Maximum vertical gap between figure and caption (in PDF points)
        MAX_GAP = 150

        # Method 1: Check for raster images CLOSE to caption
        images = page.get_images(full=True)
        nearby_image_regions = []

        for img_idx, img_info in enumerate(images):
            xref = img_info[0]
            img_rects = page.get_image_rects(xref)

            for rect in img_rects:
                # Check if image is directly above caption (within MAX_GAP)
                gap = caption_y_top - rect.y1
                if 0 <= gap <= MAX_GAP:
                    nearby_image_regions.append({
                        'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                        'gap': gap,
                        'y_bottom': rect.y1
                    })

        # Method 2: Check for vector graphics CLOSE to caption
        drawings = page.get_drawings()
        nearby_drawing_regions = []

        for drawing in drawings:
            rect = drawing['rect']
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0

            # Filter out page borders and separators
            if width > 0.8 * page_width or height > 0.8 * page.rect.height:
                continue
            if height < 20:  # Too small
                continue

            # Check if drawing is directly above caption (within MAX_GAP)
            gap = caption_y_top - rect.y1
            if 0 <= gap <= MAX_GAP:
                nearby_drawing_regions.append({
                    'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                    'gap': gap,
                    'y_bottom': rect.y1
                })

        # Combine nearby regions
        all_nearby = nearby_image_regions + nearby_drawing_regions

        if not all_nearby:
            return None  # No figure found near caption

        # Find the regions that are closest to the caption
        # Sort by y_bottom (descending) - we want the one just above the caption
        all_nearby.sort(key=lambda x: x['y_bottom'], reverse=True)

        # Take regions that are part of the same figure (close together vertically)
        main_region = all_nearby[0]
        figure_regions = [main_region]

        for region in all_nearby[1:]:
            # If this region is close to our main region, include it
            if abs(region['y_bottom'] - main_region['y_bottom']) < 50:
                figure_regions.append(region)

        # Calculate bounding box
        all_x0 = [r['bbox'][0] for r in figure_regions]
        all_y0 = [r['bbox'][1] for r in figure_regions]
        all_x1 = [r['bbox'][2] for r in figure_regions]
        all_y1 = [r['bbox'][3] for r in figure_regions]

        # Get figure content boundaries
        figure_top = min(all_y0)
        figure_bottom = max(all_y1)

        # ============================================================
        # SMART BOUNDARY CONFIGURATION
        # ============================================================

        # 1. TOP BOUNDARY: Find text above and stop at full text lines
        smart_top = self.find_text_boundary_above_figure(page, figure_top)

        # 2. LEFT/RIGHT BOUNDARIES: Extend to page margins
        # Standard PDF margins are typically 36-72 points (0.5-1 inch)
        # We'll use a conservative margin detection
        page_left_margin = 36   # ~0.5 inch from left edge
        page_right_margin = page_width - 36  # ~0.5 inch from right edge

        # 3. BOTTOM BOUNDARY: Include caption with padding
        padding_bottom = 10  # Small padding below caption
        caption_y_bottom = caption_bbox[3]
        smart_bottom = min(page_height, caption_y_bottom + padding_bottom)

        # ============================================================

        figure_bbox = [
            page_left_margin,   # Left: page margin
            smart_top,          # Top: just below full text line
            page_right_margin,  # Right: page margin
            smart_bottom        # Bottom: caption + padding
        ]

        return figure_bbox

    def extract_figure_image(self, page, bbox: List[float], fig_num: str) -> Optional[str]:
        """
        Extract the figure region as a high-resolution image
        """
        try:
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

            # Render at high resolution
            mat = fitz.Matrix(3, 3)  # 3x zoom
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Save image
            fig_filename = f"Fig-{fig_num.replace('.', '-')}.png"
            fig_path = self.output_dir / fig_filename

            pix.save(str(fig_path))

            self.figure_count += 1

            return fig_filename

        except Exception as e:
            print(f"  [ERROR] Failed to extract figure: {e}")
            return None

    def extract_all_figures(self, doc) -> List[Dict]:
        """
        Extract all figures from the PDF document
        """
        all_figures = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Find captions on this page
            captions = self.find_figure_captions(page)

            if not captions:
                continue

            print(f"Page {page_num + 1}: Found {len(captions)} figure(s)")

            for caption in captions:
                fig_num = caption['fig_num']
                caption_bbox = caption['caption_bbox']

                print(f"  Fig. {fig_num}: Locating figure region...")

                # Find figure region above caption
                figure_bbox = self.find_figure_region_above_caption(page, caption_bbox)

                if figure_bbox:
                    # Extract the figure
                    filename = self.extract_figure_image(page, figure_bbox, fig_num)

                    if filename:
                        print(f"    [OK] Extracted: {filename}")

                        all_figures.append({
                            'fig_num': fig_num,
                            'filename': filename,
                            'page': page_num + 1,
                            'bbox': figure_bbox,
                            'caption': caption['caption_text'][:100]
                        })
                    else:
                        print(f"    [FAILED] Could not extract image")
                else:
                    print(f"    [SKIP] No figure found within 150px of caption")

        return all_figures


class TableExtractor:
    """Extract tables from PDFs by detecting caption patterns at the top"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.table_count = 0

    def find_table_captions(self, page) -> List[Dict]:
        """
        Find all table captions on a page (e.g., "Table 1.1", "Table 2.3")
        Only detects standalone captions, not references in text
        """
        captions = []

        # Pattern to match Table X.Y (with various spacing)
        table_pattern = r'Table\s+(\d+)\.(\d+)'

        # Get text blocks with positions
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block['type'] != 0:  # Not a text block
                continue

            # Extract text from block
            block_text = ""
            for line in block["lines"]:
                for span in line["spans"]:
                    block_text += span["text"] + " "

            block_text = block_text.strip()

            # Search for table caption pattern
            matches = re.finditer(table_pattern, block_text, re.IGNORECASE)

            for match in matches:
                table_num = f"{match.group(1)}.{match.group(2)}"
                bbox = block['bbox']

                # CRITICAL: Only accept SHORT captions (actual table labels)
                # Exclude long text that mentions tables
                if len(block_text) > 30:
                    continue

                # Exclude text with verbs (question/instruction text)
                verb_patterns = ['shows', 'show', 'complete', 'use',
                                'calculate', 'find', 'determine', 'write']
                if any(verb in block_text.lower() for verb in verb_patterns):
                    continue

                # Must start with Table or be very short
                if not block_text.startswith('Table') and len(block_text) > 20:
                    continue

                captions.append({
                    'table_num': table_num,
                    'caption_text': block_text,
                    'caption_bbox': bbox,
                    'page_num': page.number + 1
                })

        # Remove duplicates (same table_num on same page)
        unique_captions = []
        seen = set()
        for cap in captions:
            key = (cap['page_num'], cap['table_num'])
            if key not in seen:
                seen.add(key)
                unique_captions.append(cap)

        return unique_captions

    def find_text_boundary_below_table(self, page, table_y_bottom: float) -> float:
        """
        Find the boundary below the table by detecting full text lines
        Returns the Y coordinate just above the first full text line
        """
        # Get all text blocks on the page
        blocks = page.get_text("dict")["blocks"]

        # Find text blocks below the table
        text_lines_below = []

        for block in blocks:
            if block['type'] != 0:  # Not a text block
                continue

            block_bbox = block['bbox']
            block_y_top = block_bbox[1]
            block_width = block_bbox[2] - block_bbox[0]

            # Check if this block is below the table
            if block_y_top > table_y_bottom:
                # Extract text to check if it's a full line
                block_text = ""
                for line in block['lines']:
                    for span in line['spans']:
                        block_text += span['text']

                # Consider it a "full text line" if:
                # 1. It's relatively wide (> 40% of page width)
                # 2. It contains multiple words (not just a label)
                page_width = page.rect.width
                is_full_line = (block_width > 0.4 * page_width and
                               len(block_text.split()) >= 4)

                text_lines_below.append({
                    'bbox': block_bbox,
                    'y_top': block_y_top,
                    'is_full_line': is_full_line,
                    'text': block_text[:50]  # For debugging
                })

        if not text_lines_below:
            # No text below, use table bottom with small padding
            return table_y_bottom + 10

        # Sort by y_top (ascending) - closest to table first
        text_lines_below.sort(key=lambda x: x['y_top'])

        # Find the first full text line (closest to table going down)
        for text_line in text_lines_below:
            if text_line['is_full_line']:
                # Return just above this full line
                return text_line['y_top'] - 5

        # No full text line found, return the bottom-most text below with padding
        return text_lines_below[-1]['bbox'][3] + 10

    def find_table_region_below_caption(self, page, caption_bbox: List[float]) -> Optional[List[float]]:
        """
        Find the table region DIRECTLY below a caption
        Uses smart boundaries: caption at top, text detection for bottom, page margins for sides
        """
        caption_y_bottom = caption_bbox[3]  # Bottom of caption
        page_width = page.rect.width
        page_height = page.rect.height

        # Maximum vertical gap between caption and table (in PDF points)
        MAX_GAP = 150

        # Find vector graphics (table borders/lines) below caption
        drawings = page.get_drawings()
        nearby_table_regions = []

        for drawing in drawings:
            rect = drawing['rect']
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0

            # Filter out page borders
            if width > 0.8 * page_width or height > 0.8 * page.rect.height:
                continue
            if height < 10:  # Too small
                continue

            # Check if drawing is directly below caption (within MAX_GAP)
            gap = rect.y0 - caption_y_bottom
            if 0 <= gap <= MAX_GAP:
                nearby_table_regions.append({
                    'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                    'gap': gap,
                    'y_top': rect.y0,
                    'y_bottom': rect.y1
                })

        if not nearby_table_regions:
            return None  # No table found near caption

        # Sort by y_top (ascending) - closest to caption first
        nearby_table_regions.sort(key=lambda x: x['y_top'])

        # Take the closest region to caption
        main_region = nearby_table_regions[0]
        table_regions = [main_region]

        # Add other regions that are part of the same table (vertically close)
        for region in nearby_table_regions[1:]:
            if abs(region['y_top'] - main_region['y_top']) < 50:
                table_regions.append(region)

        # Calculate bounding box
        all_x0 = [r['bbox'][0] for r in table_regions]
        all_y0 = [r['bbox'][1] for r in table_regions]
        all_x1 = [r['bbox'][2] for r in table_regions]
        all_y1 = [r['bbox'][3] for r in table_regions]

        # Get table content boundaries
        table_top = min(all_y0)
        table_bottom = max(all_y1)

        # ============================================================
        # SMART BOUNDARY CONFIGURATION
        # ============================================================

        # 1. TOP BOUNDARY: Include caption with small padding above
        padding_above_caption = 10
        smart_top = max(0, caption_bbox[1] - padding_above_caption)

        # 2. BOTTOM BOUNDARY: Find text below and stop at full text lines
        smart_bottom = self.find_text_boundary_below_table(page, table_bottom)

        # 3. LEFT/RIGHT BOUNDARIES: Extend to page margins (same as figures)
        page_left_margin = 36   # ~0.5 inch from left edge
        page_right_margin = page_width - 36  # ~0.5 inch from right edge

        # ============================================================

        table_bbox = [
            page_left_margin,   # Left: page margin
            smart_top,          # Top: caption with padding above
            page_right_margin,  # Right: page margin
            smart_bottom        # Bottom: just above full text line
        ]

        return table_bbox

    def extract_table_image(self, page, bbox: List[float], table_num: str) -> Optional[str]:
        """
        Extract the table region as a high-resolution image
        """
        try:
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

            # Render at high resolution
            mat = fitz.Matrix(3, 3)  # 3x zoom
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Save image
            table_filename = f"Table-{table_num.replace('.', '-')}.png"
            table_path = self.output_dir / table_filename

            pix.save(str(table_path))

            self.table_count += 1

            return table_filename

        except Exception as e:
            print(f"  [ERROR] Failed to extract table: {e}")
            return None

    def extract_all_tables(self, doc) -> List[Dict]:
        """
        Extract all tables from the PDF document
        """
        all_tables = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Find captions on this page
            captions = self.find_table_captions(page)

            if not captions:
                continue

            print(f"Page {page_num + 1}: Found {len(captions)} table(s)")

            for caption in captions:
                table_num = caption['table_num']
                caption_bbox = caption['caption_bbox']

                print(f"  Table {table_num}: Locating table region...")

                # Find table region below caption
                table_bbox = self.find_table_region_below_caption(page, caption_bbox)

                if table_bbox:
                    # Extract the table
                    filename = self.extract_table_image(page, table_bbox, table_num)

                    if filename:
                        print(f"    [OK] Extracted: {filename}")

                        all_tables.append({
                            'table_num': table_num,
                            'filename': filename,
                            'page': page_num + 1,
                            'bbox': table_bbox,
                            'caption': caption['caption_text'][:100]
                        })
                    else:
                        print(f"    [FAILED] Could not extract image")
                else:
                    print(f"    [SKIP] No table found within 150px of caption")

        return all_tables


def extract_figures_and_tables(pdf_path: Path, output_dir: Path) -> Dict:
    """
    Process the PDF: extract both figures and tables

    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to save extracted images

    Returns:
        Dictionary containing extraction results
    """
    print(f"\n{'='*60}")
    print("PDF PROCESSOR - Unified Figure & Table Extraction")
    print(f"{'='*60}")
    print(f"Input PDF: {pdf_path}")
    print(f"Output Directory: {output_dir}")
    print(f"{'='*60}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Open PDF document
    doc = fitz.open(str(pdf_path))
    print(f"Total pages: {len(doc)}\n")

    # Extract figures
    print("="*60)
    print("EXTRACTING FIGURES")
    print("="*60)
    figure_extractor = FigureExtractor(output_dir=str(output_dir))
    figures = figure_extractor.extract_all_figures(doc)
    print(f"Extracted {len(figures)} figure(s)\n")

    # Extract tables
    print("="*60)
    print("EXTRACTING TABLES")
    print("="*60)
    table_extractor = TableExtractor(output_dir=str(output_dir))
    tables = table_extractor.extract_all_tables(doc)
    print(f"Extracted {len(tables)} table(s)\n")

    # Close document
    doc.close()

    # Prepare results
    results = {
        'pdf_path': str(pdf_path),
        'output_dir': str(output_dir),
        'total_figures': len(figures),
        'total_tables': len(tables),
        'figures': figures,
        'tables': tables
    }

    # Print summary
    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total Figures: {len(figures)}")
    print(f"Total Tables: {len(tables)}")
    print(f"Output Directory: {output_dir}")
    print(f"{'='*60}\n")

    return results
