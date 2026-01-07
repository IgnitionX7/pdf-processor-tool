"""
Test script for noise removal module.

Tests noise detection and filtering on a sample PDF.
"""

import sys
import json
from pathlib import Path
from typing import Dict

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import pdfplumber
from noise_detector import NoiseDetector
from noise_filter import NoiseFilter


def test_noise_detection(pdf_path: str):
    """Test noise detection on a PDF."""
    print(f"Testing noise detection on: {pdf_path}")
    print("=" * 70)

    # Initialize detector
    detector = NoiseDetector(
        header_threshold=80.0,
        footer_threshold=760.0,
        left_margin_threshold=80.0,
        right_margin_threshold=515.0,
        min_frequency=0.5,
        sample_size=5
    )

    # Detect noise zones
    noise_zones = detector.detect_noise_zones(pdf_path)

    print("\n## DETECTED NOISE ZONES ##\n")

    print("Page dimensions:", noise_zones['page_dimensions'])
    print()

    print("Header zones:")
    for zone in noise_zones['header_zones']:
        print(f"  Y: {zone['y_min']:.1f} - {zone['y_max']:.1f}")
    print()

    print("Footer zones:")
    for zone in noise_zones['footer_zones']:
        print(f"  Y: {zone['y_min']:.1f} - {zone['y_max']:.1f}")
    print()

    print("Left margin zones:")
    for zone in noise_zones['left_margin_zones']:
        print(f"  X: {zone['x_min']:.1f} - {zone['x_max']:.1f}")
    print()

    print("Right margin zones:")
    for zone in noise_zones['right_margin_zones']:
        print(f"  X: {zone['x_min']:.1f} - {zone['x_max']:.1f}")
    print()

    print("## DETECTED NOISE PATTERNS ##\n")

    print("Header patterns:")
    for pattern, count in noise_zones['noise_patterns']['header_patterns'][:5]:
        print(f"  [{count}x] {pattern}")
    print()

    print("Footer patterns:")
    for pattern, count in noise_zones['noise_patterns']['footer_patterns'][:5]:
        print(f"  [{count}x] {pattern}")
    print()

    print("=" * 70)
    print()

    return noise_zones


def test_noise_filtering(pdf_path: str, noise_zones: Dict):
    """Test noise filtering on a PDF page."""
    print(f"Testing noise filtering on first 3 pages")
    print("=" * 70)

    noise_filter = NoiseFilter(noise_zones)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(min(3, len(pdf.pages))):
            page = pdf.pages[page_num]
            print(f"\nPAGE {page_num + 1}:")

            chars = page.chars
            filtered_chars = noise_filter.filter_characters(chars)

            print(f"  Total characters: {len(chars)}")
            print(f"  After filtering: {len(filtered_chars)}")
            print(f"  Removed: {len(chars) - len(filtered_chars)} ({(len(chars) - len(filtered_chars)) / len(chars) * 100:.1f}%)")

            # Show sample of removed text
            removed_chars = [c for c in chars if c not in filtered_chars]
            if removed_chars[:50]:
                removed_text = ''.join([c['text'] for c in removed_chars[:50]])
                print(f"  Sample removed text: {removed_text[:80]}")

    print()
    print("=" * 70)
    print()

    # Show filter statistics
    stats = noise_filter.get_noise_statistics()
    print("## FILTER STATISTICS ##\n")
    print(json.dumps(stats, indent=2))
    print()


if __name__ == "__main__":
    # Test on the sample PDF
    pdf_path = r"../papers/pakistanstudies-papers/2059_s25_qp_02.pdf"

    if not Path(pdf_path).exists():
        print(f"Error: PDF not found at {pdf_path}")
        sys.exit(1)

    # Run detection test
    noise_zones = test_noise_detection(pdf_path)

    # Run filtering test
    test_noise_filtering(pdf_path, noise_zones)

    print("\n[OK] Noise removal tests completed!")
