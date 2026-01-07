"""Caption-based figure extractor."""

import re
import fitz
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CaptionFigureExtractor:
    """Extract figures from PDFs by detecting caption patterns."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.figure_count = 0

    def find_figure_captions(self, page) -> List[Dict]:
        """Find all figure captions on a page (e.g., "Fig. 1.1", "Fig. 2.3")."""
        captions = []
        fig_pattern = r'Fig\.\s*(\d+)\.(\d+)'
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block['type'] != 0:
                continue

            block_text = ""
            for line in block["lines"]:
                for span in line["spans"]:
                    block_text += span["text"] + " "

            block_text = block_text.strip()
            matches = re.finditer(fig_pattern, block_text, re.IGNORECASE)

            for match in matches:
                fig_num = f"{match.group(1)}.{match.group(2)}"
                bbox = block['bbox']

                if len(block_text) > 25:
                    continue

                verb_patterns = ['shows', 'show', 'sketch', 'draw', 'calculate',
                                'find', 'determine', 'use', 'complete', 'label']
                if any(verb in block_text.lower() for verb in verb_patterns):
                    continue

                if not block_text.startswith('Fig.') and len(block_text) > 15:
                    continue

                captions.append({
                    'fig_num': fig_num,
                    'caption_text': block_text,
                    'caption_bbox': bbox,
                    'page_num': page.number + 1
                })

        unique_captions = []
        seen = set()
        for cap in captions:
            key = (cap['page_num'], cap['fig_num'])
            if key not in seen:
                seen.add(key)
                unique_captions.append(cap)

        return unique_captions

    def find_text_boundary_above_figure(self, page, figure_y_top: float) -> float:
        """Find the boundary above the figure by detecting full text lines."""
        blocks = page.get_text("dict")["blocks"]
        text_lines_above = []

        for block in blocks:
            if block['type'] != 0:
                continue

            block_bbox = block['bbox']
            block_y_bottom = block_bbox[3]
            block_width = block_bbox[2] - block_bbox[0]

            if block_y_bottom < figure_y_top:
                block_text = ""
                for line in block['lines']:
                    for span in line['spans']:
                        block_text += span['text']

                page_width = page.rect.width
                is_full_line = (block_width > 0.4 * page_width and
                               len(block_text.split()) >= 4)

                text_lines_above.append({
                    'bbox': block_bbox,
                    'y_bottom': block_y_bottom,
                    'is_full_line': is_full_line,
                    'text': block_text[:50]
                })

        if not text_lines_above:
            return figure_y_top - 10

        text_lines_above.sort(key=lambda x: x['y_bottom'], reverse=True)

        for text_line in text_lines_above:
            if text_line['is_full_line']:
                return text_line['y_bottom'] + 5

        return text_lines_above[-1]['bbox'][1] - 10

    def find_figure_region_above_caption(self, page, caption_bbox: List[float]) -> Optional[List[float]]:
        """Find the figure region DIRECTLY above a caption."""
        caption_y_top = caption_bbox[1]
        page_width = page.rect.width
        page_height = page.rect.height
        MAX_GAP = 150

        images = page.get_images(full=True)
        nearby_image_regions = []

        for img_idx, img_info in enumerate(images):
            xref = img_info[0]
            img_rects = page.get_image_rects(xref)

            for rect in img_rects:
                gap = caption_y_top - rect.y1
                if 0 <= gap <= MAX_GAP:
                    nearby_image_regions.append({
                        'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                        'gap': gap,
                        'y_bottom': rect.y1
                    })

        drawings = page.get_drawings()

        # STEP 1: Collect ALL drawings above the caption (including small ones)
        all_drawings_above = []
        for drawing in drawings:
            rect = drawing['rect']
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0

            # Filter out page-wide borders only
            if width > 0.8 * page_width or height > 0.8 * page.rect.height:
                continue

            # Check if drawing is above caption (within MAX_GAP)
            gap = caption_y_top - rect.y1
            if 0 <= gap <= MAX_GAP:
                all_drawings_above.append({
                    'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                    'gap': gap,
                    'y_bottom': rect.y1,
                    'width': width,
                    'height': height
                })

        # STEP 2: Group nearby small drawings into clusters
        nearby_drawing_regions = []

        if all_drawings_above:
            all_drawings_above.sort(key=lambda d: d['bbox'][1])

            clusters = []
            for drawing in all_drawings_above:
                added_to_cluster = False

                for cluster in clusters:
                    for cluster_drawing in cluster:
                        dx0 = abs(drawing['bbox'][0] - cluster_drawing['bbox'][0])
                        dy0 = abs(drawing['bbox'][1] - cluster_drawing['bbox'][1])

                        if dx0 < 50 and dy0 < 30:
                            cluster.append(drawing)
                            added_to_cluster = True
                            break

                    if added_to_cluster:
                        break

                if not added_to_cluster:
                    clusters.append([drawing])

            for cluster in clusters:
                if not cluster:
                    continue

                all_x0 = [d['bbox'][0] for d in cluster]
                all_y0 = [d['bbox'][1] for d in cluster]
                all_x1 = [d['bbox'][2] for d in cluster]
                all_y1 = [d['bbox'][3] for d in cluster]

                cluster_bbox = [min(all_x0), min(all_y0), max(all_x1), max(all_y1)]
                cluster_height = cluster_bbox[3] - cluster_bbox[1]

                if cluster_height >= 20 or len(cluster) >= 10:
                    nearby_drawing_regions.append({
                        'bbox': cluster_bbox,
                        'gap': caption_y_top - cluster_bbox[3],
                        'y_bottom': cluster_bbox[3],
                        'cluster_size': len(cluster)
                    })

        all_nearby = nearby_image_regions + nearby_drawing_regions

        if not all_nearby:
            return None

        all_nearby.sort(key=lambda x: x['y_bottom'], reverse=True)

        main_region = all_nearby[0]
        figure_regions = [main_region]

        for region in all_nearby[1:]:
            if abs(region['y_bottom'] - main_region['y_bottom']) < 50:
                figure_regions.append(region)

        all_x0 = [r['bbox'][0] for r in figure_regions]
        all_y0 = [r['bbox'][1] for r in figure_regions]
        all_x1 = [r['bbox'][2] for r in figure_regions]
        all_y1 = [r['bbox'][3] for r in figure_regions]

        figure_top = min(all_y0)
        figure_bottom = max(all_y1)

        smart_top = self.find_text_boundary_above_figure(page, figure_top)
        page_left_margin = 36
        page_right_margin = page_width - 36
        padding_bottom = 10
        caption_y_bottom = caption_bbox[3]
        smart_bottom = min(page_height, caption_y_bottom + padding_bottom)

        figure_bbox = [
            page_left_margin,
            smart_top,
            page_right_margin,
            smart_bottom
        ]

        return figure_bbox

    def extract_figure_image(self, page, bbox: List[float], fig_num: str) -> Optional[str]:
        """Extract the figure region as a high-resolution image."""
        try:
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            mat = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            fig_filename = f"Fig-{fig_num.replace('.', '-')}.png"
            fig_path = self.output_dir / fig_filename

            pix.save(str(fig_path))
            self.figure_count += 1

            return fig_filename

        except Exception as e:
            logger.error(f"  [ERROR] Failed to extract figure: {e}")
            return None

    def extract_all_figures(self, doc) -> List[Dict]:
        """Extract all figures from the PDF document."""
        all_figures = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            captions = self.find_figure_captions(page)

            if not captions:
                continue

            logger.info(f"Page {page_num + 1}: Found {len(captions)} figure(s)")

            for caption in captions:
                fig_num = caption['fig_num']
                caption_bbox = caption['caption_bbox']

                logger.info(f"  Fig. {fig_num}: Locating figure region...")

                figure_bbox = self.find_figure_region_above_caption(page, caption_bbox)

                if figure_bbox:
                    filename = self.extract_figure_image(page, figure_bbox, fig_num)

                    if filename:
                        logger.info(f"    [OK] Extracted: {filename}")

                        all_figures.append({
                            'fig_num': fig_num,
                            'filename': filename,
                            'page': page_num + 1,
                            'bbox': figure_bbox,
                            'caption': caption['caption_text'][:100]
                        })
                    else:
                        logger.info(f"    [FAILED] Could not extract image")
                else:
                    logger.info(f"    [SKIP] No figure found within 150px of caption")

        return all_figures
