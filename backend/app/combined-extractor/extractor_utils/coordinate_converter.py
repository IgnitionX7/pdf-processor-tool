"""
Coordinate conversion utilities.

Handles conversion between different coordinate systems:
- PyMuPDF (fitz): Bottom-left origin
- pdfplumber: Top-left origin
- Pixel coordinates: From pdf2image conversion
"""

from typing import List, Tuple, Dict
import fitz


def pixel_bbox_to_pdf_bbox(pixel_bbox: List[int], page_width_pdf: float,
                           page_height_pdf: float, dpi: int = 300) -> List[float]:
    """
    Convert pixel coordinates to PDF coordinates (pdfplumber format).

    Args:
        pixel_bbox: [x1, y1, x2, y2] in pixels
        page_width_pdf: Page width in PDF points
        page_height_pdf: Page height in PDF points
        dpi: DPI used for conversion

    Returns:
        [x0, y0, x1, y1] in PDF coordinates
    """
    x1_px, y1_px, x2_px, y2_px = pixel_bbox

    # Calculate scale
    scale_x = page_width_pdf / ((page_width_pdf / 72) * dpi)
    scale_y = page_height_pdf / ((page_height_pdf / 72) * dpi)

    # Convert to PDF coords
    x0 = x1_px * scale_x
    y0 = y1_px * scale_y
    x1 = x2_px * scale_x
    y1 = y2_px * scale_y

    return [x0, y0, x1, y1]


def extract_exclusion_zones_from_metadata(metadata: Dict, pdf_path: str,
                                          dpi: int = 300) -> Dict[int, List[Dict]]:
    """
    Extract exclusion zones from extraction metadata.

    Args:
        metadata: Extraction metadata dict with 'elements' key
        pdf_path: Path to PDF file (to get page dimensions)
        dpi: DPI used during extraction

    Returns:
        Dict mapping page_num -> list of exclusion zones
        Each zone: {'bbox': [x0, y0, x1, y1], 'type': 'figure'/'table', 'filename': str}
    """
    import pdfplumber

    exclusion_zones = {}

    # Open PDF to get page dimensions
    with pdfplumber.open(pdf_path) as pdf:
        for element in metadata.get('elements', []):
            page_num = element['page']

            if page_num > len(pdf.pages):
                continue

            page = pdf.pages[page_num - 1]
            page_width_pdf = page.width
            page_height_pdf = page.height

            # Get bbox - could be in different formats
            bbox = element.get('bbox')

            if isinstance(bbox, dict):
                # Format: {'x': ..., 'y': ..., 'width': ..., 'height': ...}
                # This is pixel coordinates
                x = bbox.get('x', 0)
                y = bbox.get('y', 0)
                w = bbox.get('width', 0)
                h = bbox.get('height', 0)
                pixel_bbox = [x, y, x + w, y + h]

                # Convert to PDF coordinates
                pdf_bbox = pixel_bbox_to_pdf_bbox(
                    pixel_bbox, page_width_pdf, page_height_pdf, dpi
                )
            elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                # Assume it's already in PDF coordinates
                pdf_bbox = list(bbox)
            else:
                # Skip if bbox format is unknown
                continue

            # Add to exclusion zones
            if page_num not in exclusion_zones:
                exclusion_zones[page_num] = []

            exclusion_zones[page_num].append({
                'bbox': pdf_bbox,
                'type': element.get('type', 'unknown'),
                'filename': element.get('filename', ''),
                'source': element.get('source', '')
            })

    return exclusion_zones


def get_page_dimensions_from_pdf(pdf_path: str, page_num: int) -> Tuple[float, float]:
    """
    Get page dimensions in PDF coordinates.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-indexed)

    Returns:
        (width, height) in PDF points
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if page_num > len(pdf.pages):
            return (0, 0)

        page = pdf.pages[page_num - 1]
        return (page.width, page.height)
