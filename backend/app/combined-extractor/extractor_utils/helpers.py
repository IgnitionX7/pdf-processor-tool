"""Helper utility functions for PDF extraction."""

import re
from typing import List, Optional
from .constants import (
    FOOTER_Y_CUTOFF, X0_LEFT_COLUMN_MAX, QNUM_CHAR_MARGIN,
    TYPICAL_QNUM_X0, TOP_REGION_Y
)


def parse_caption_to_question_number(caption_text: str) -> Optional[int]:
    """
    Parse caption like 'Fig. 1.1' or 'Table 2.3' to extract question number.
    Returns the first number (e.g., 1 from '1.1', 2 from '2.3').
    """
    match = re.search(r'(?:Fig\.|Table)\s*(\d+)\.(\d+)', caption_text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def calculate_iou(bbox1: List[float], bbox2: List[float]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.
    Bboxes are in format [x0, y0, x1, y1].
    """
    x1_min, y1_min, x1_max, y1_max = bbox1
    x2_min, y2_min, x2_max, y2_max = bbox2

    # Calculate intersection
    ix_min = max(x1_min, x2_min)
    iy_min = max(y1_min, y2_min)
    ix_max = min(x1_max, x2_max)
    iy_max = min(y1_max, y2_max)

    if ix_max < ix_min or iy_max < iy_min:
        return 0.0

    intersection_area = (ix_max - ix_min) * (iy_max - iy_min)

    # Calculate union
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = area1 + area2 - intersection_area

    if union_area == 0:
        return 0.0

    return intersection_area / union_area


def convert_pdf_bbox_to_pixel_bbox(pdf_bbox: List[float], dpi: int, pdf_page_height: float) -> List[float]:
    """
    Convert PDF coordinates (points) to image pixel coordinates.

    Args:
        pdf_bbox: [x0, y0, x1, y1] in PDF points
        dpi: DPI used for image conversion
        pdf_page_height: Height of PDF page in points

    Returns:
        [x0, y0, x1, y1] in pixels
    """
    scale = dpi / 72.0  # 72 points per inch

    x0_px = pdf_bbox[0] * scale
    y0_px = pdf_bbox[1] * scale
    x1_px = pdf_bbox[2] * scale
    y1_px = pdf_bbox[3] * scale

    return [x0_px, y0_px, x1_px, y1_px]


def extract_question_starts_from_page(page, expected_q_number=None):
    """
    Extract question numbers from a pdfplumber page.
    Returns list of question starts with their full question numbers.
    """
    chars = page.chars
    if not chars:
        return []

    # Get digits in top region first (higher priority)
    top_region_digits = [
        c for c in chars
        if c['text'].isdigit() and c['x0'] < X0_LEFT_COLUMN_MAX
        and c['top'] < TOP_REGION_Y and c['top'] < FOOTER_Y_CUTOFF
    ]

    # Fallback to all digits if no top region digits found
    if top_region_digits:
        candidate_digits = top_region_digits
    else:
        candidate_digits = [
            c for c in chars
            if c['text'].isdigit() and c['x0'] < X0_LEFT_COLUMN_MAX and c['top'] < FOOTER_Y_CUTOFF
        ]

    if not candidate_digits:
        return []

    # Use weighted scoring to determine best X0 position
    x0_scores = {}

    for digit in candidate_digits:
        x0 = round(digit['x0'], 2)
        if x0 not in x0_scores:
            x0_scores[x0] = {'count': 0, 'has_expected': False, 'distance': abs(x0 - TYPICAL_QNUM_X0)}
        x0_scores[x0]['count'] += 1

    # Calculate weighted scores
    scored_x0s = []
    for x0, info in x0_scores.items():
        score = info['count']
        distance_bonus = max(0, 10 - info['distance'] * 2)
        score += distance_bonus

        # Extra bonus if this X0 contains the expected question number
        if expected_q_number is not None:
            digits_at_x0 = [
                c for c in candidate_digits
                if abs(round(c['x0'], 2) - x0) < QNUM_CHAR_MARGIN
            ]

            y_groups = {}
            for c in digits_at_x0:
                y_key = round(c['top'], 2)
                if y_key not in y_groups:
                    y_groups[y_key] = []
                y_groups[y_key].append(c)

            for digits_on_line in y_groups.values():
                sorted_digits = sorted(digits_on_line, key=lambda d: d['x0'])
                qnum_str = ''.join(d['text'] for d in sorted_digits)
                try:
                    if int(qnum_str) == expected_q_number:
                        score += 50
                        info['has_expected'] = True
                        break
                except ValueError:
                    pass

        scored_x0s.append((x0, score, info))

    # Sort by score and pick the best X0
    scored_x0s.sort(key=lambda x: x[1], reverse=True)
    if not scored_x0s:
        return []
    QUESTION_X0_TARGET = scored_x0s[0][0]

    # Two-Pass Filtering to find ALL question digits
    confirmed_qnum_y_tops = set()
    for char in chars:
        if char['text'].isdigit() and abs(char['x0'] - QUESTION_X0_TARGET) < QNUM_CHAR_MARGIN and char['top'] < FOOTER_Y_CUTOFF:
            confirmed_qnum_y_tops.add(round(char['top'], 2))

    # Pre-check: For each confirmed Y line, find the rightmost digit at QUESTION_X0_TARGET
    y_line_max_x = {}
    for y_line in confirmed_qnum_y_tops:
        digits_at_target = [
            c for c in chars
            if c['text'].isdigit()
            and abs(round(c['x0'], 2) - round(QUESTION_X0_TARGET, 2)) < QNUM_CHAR_MARGIN
            and round(c['top'], 2) == y_line
        ]
        if digits_at_target:
            max_x1 = max(c['x1'] for c in digits_at_target)
            y_line_max_x[y_line] = max_x1

    MAX_MULTIDIGIT_DISTANCE = 10.0

    all_question_digits = []
    for char in chars:
        char_x0_rounded = round(char['x0'], 2)
        target_x0_rounded = round(QUESTION_X0_TARGET, 2)
        char_y_rounded = round(char['top'], 2)

        is_at_target = abs(char_x0_rounded - target_x0_rounded) < QNUM_CHAR_MARGIN

        is_adjacent_multi_digit = False
        if char_y_rounded in y_line_max_x:
            max_x1_at_target = y_line_max_x[char_y_rounded]
            distance_from_qnum = char['x0'] - max_x1_at_target
            is_adjacent_multi_digit = (distance_from_qnum >= -2.0 and distance_from_qnum < MAX_MULTIDIGIT_DISTANCE)

        if (char['text'].isdigit()
            and char_y_rounded in y_line_max_x
            and (is_at_target or is_adjacent_multi_digit)):
            all_question_digits.append({
                'text': char['text'],
                'bbox': (char['x0'], char['top'], char['x1'], char['bottom'])
            })

    if not all_question_digits:
        return []

    # Group digits by Y-position and reconstruct full question numbers
    question_starts_map = {}
    for q_char in all_question_digits:
        q_top_key = round(q_char['bbox'][1], 2)
        if q_top_key not in question_starts_map:
            question_starts_map[q_top_key] = []
        question_starts_map[q_top_key].append(q_char)

    question_starts = []
    for y_top, digits_on_line in question_starts_map.items():
        sorted_digits = sorted(digits_on_line, key=lambda d: d['bbox'][0])
        qnum_str = ''.join(d['text'] for d in sorted_digits)
        try:
            qnum = int(qnum_str)
            first_digit = sorted_digits[0]
            question_starts.append({
                'qnum': qnum,
                'bbox': first_digit['bbox'],
                'char_data': first_digit
            })
        except ValueError:
            pass

    return sorted(question_starts, key=lambda q: q['bbox'][1])
