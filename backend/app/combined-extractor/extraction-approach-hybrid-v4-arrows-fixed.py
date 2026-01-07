"""
Chemistry PDF Text Extractor using Hybrid Approach (PyMuPDF + pdfplumber)

This script extracts text from chemistry exam PDFs, preserving chemical formulas
with subscripts, superscripts, and special notation using a hybrid approach.

This approach is:
- Fast (no GPU required)
- Reliable (no segmentation faults)
- Works offline
- Uses lightweight dependencies

Usage:
    python extraction-approach-hybrid.py <pdf_path> [options]

Example:
    python extraction-approach-hybrid.py "chemistry papers/5070_s22_qp_21.pdf"
    python extraction-approach-hybrid.py "chemistry papers/5070_s22_qp_21.pdf" --output-dir output/hybrid
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json
from collections import defaultdict


def check_dependencies():
    """
    Check if required libraries are installed.
    """
    missing = []

    try:
        import fitz
        print("[OK] PyMuPDF (fitz) is installed")
    except ImportError:
        missing.append("PyMuPDF")

    try:
        import pdfplumber
        print("[OK] pdfplumber is installed")
    except ImportError:
        missing.append("pdfplumber")

    if missing:
        print(f"\n[ERROR] Missing dependencies: {', '.join(missing)}")
        print("\nPlease install using:")
        print(f"    pip install {' '.join(missing)}")
        return False

    return True


def extract_text_with_pymupdf(pdf_path: str) -> Tuple[List[Dict], Dict]:
    """
    Fast extraction with PyMuPDF to get basic structure and detect some superscripts.

    Returns:
        Tuple of (pages_data, metadata)
    """
    import fitz

    print(f"\nOpening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)

    pages_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Get text blocks with formatting info
        blocks = page.get_text("dict")

        # Get plain text for comparison
        plain_text = page.get_text()

        pages_data.append({
            'page_num': page_num + 1,
            'blocks': blocks,
            'plain_text': plain_text
        })

    metadata = {
        'total_pages': len(doc),
        'pdf_path': pdf_path
    }

    doc.close()

    return pages_data, metadata


def analyze_character_positions(pdf_path: str, page_num: int = 0) -> Dict:
    """
    Use pdfplumber to get detailed character-level information.

    This helps us understand how subscripts and superscripts are positioned.
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if page_num >= len(pdf.pages):
            page_num = 0

        page = pdf.pages[page_num]
        chars = page.chars

        if not chars:
            return {}

        # Analyze character sizes and positions
        sizes = [c['size'] for c in chars]
        tops = [c['top'] for c in chars]

        # Find baseline (most common values)
        size_counts = defaultdict(int)
        top_counts = defaultdict(float)

        for size in sizes:
            size_counts[round(size, 1)] += 1

        for top in tops:
            top_counts[round(top, 1)] += 1

        baseline_size = max(size_counts.items(), key=lambda x: x[1])[0]
        baseline_top = max(top_counts.items(), key=lambda x: x[1])[0]

        return {
            'baseline_size': baseline_size,
            'baseline_top': baseline_top,
            'size_range': (min(sizes), max(sizes)),
            'top_range': (min(tops), max(tops)),
            'total_chars': len(chars)
        }


def extract_arrow_graphics(pdf_path: str, page_num: int) -> List[Dict]:
    """
    Extract graphical arrows from a PDF page using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        page_num: Page index (0-based)

    Returns:
        List of arrow dictionaries with position and direction info
    """
    arrows = []

    try:
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        drawings = page.get_drawings()

        # Find horizontal lines that could be arrow shafts
        # Only consider lines that are likely chemical equation arrows:
        # - Length between 8 and 30 pixels (not too short or too long)
        # - Horizontal (vertical delta < 2 pixels)
        # - In the main content area (not in headers/footers)

        page_height = page.rect.height
        content_top = page_height * 0.1   # Exclude top 10% (header)
        content_bottom = page_height * 0.9  # Exclude bottom 10% (footer)

        raw_arrows = []

        for drawing in drawings:
            if 'items' in drawing:
                for item in drawing['items']:
                    if item[0] == 'l':  # Line
                        start = item[1]
                        end = item[2]

                        # Check if it's a horizontal line in content area
                        length = abs(end.x - start.x)
                        in_content_area = content_top <= start.y <= content_bottom

                        # Chemical equation arrows are typically 8-30 pixels long
                        if 8 <= length <= 30 and abs(start.y - end.y) < 2 and in_content_area:
                            # Determine direction
                            if end.x > start.x:
                                direction = 'right'
                            else:
                                direction = 'left'

                            raw_arrows.append({
                                'x_start': min(start.x, end.x),
                                'x_end': max(start.x, end.x),
                                'x_mid': (start.x + end.x) / 2,
                                'y': start.y,
                                'direction': direction,
                                'length': length
                            })

        # Detect equilibrium arrows (two arrows at same position, opposite directions)
        processed = set()

        for i, arrow1 in enumerate(raw_arrows):
            if i in processed:
                continue

            # Check for a matching arrow going the opposite direction
            found_equilibrium = False

            for j, arrow2 in enumerate(raw_arrows):
                if i == j or j in processed:
                    continue

                # Check if at same vertical position and opposite direction
                y_diff = abs(arrow1['y'] - arrow2['y'])
                x_overlap = abs(arrow1['x_mid'] - arrow2['x_mid'])

                if y_diff < 5 and x_overlap < 10 and arrow1['direction'] != arrow2['direction']:
                    # This is an equilibrium arrow!
                    arrows.append({
                        'x_start': min(arrow1['x_start'], arrow2['x_start']),
                        'x_end': max(arrow1['x_end'], arrow2['x_end']),
                        'y': (arrow1['y'] + arrow2['y']) / 2,
                        'direction': '<=>',  # Equilibrium
                        'length': max(arrow1['length'], arrow2['length'])
                    })
                    processed.add(i)
                    processed.add(j)
                    found_equilibrium = True
                    break

            # If not part of equilibrium, add as single arrow
            if not found_equilibrium:
                arrows.append({
                    'x_start': arrow1['x_start'],
                    'x_end': arrow1['x_end'],
                    'y': arrow1['y'],
                    'direction': '->' if arrow1['direction'] == 'right' else '<-',
                    'length': arrow1['length']
                })
                processed.add(i)

        doc.close()
    except Exception:
        # If PyMuPDF not available or error, return empty list
        pass

    return arrows


def reconstruct_text_with_notation(pdf_path: str) -> List[Dict]:
    """
    Reconstruct text with LaTeX-style notation for subscripts and superscripts.

    Uses pdfplumber's detailed character analysis.
    """
    import pdfplumber

    results = []

    print(f"\nProcessing with pdfplumber...")

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            print(f"  Processing page {page_num + 1}/{len(pdf.pages)}...")

            chars = page.chars
            if not chars:
                results.append({
                    'page': page_num + 1,
                    'text': '',
                    'formatted_text': ''
                })
                continue

            # Determine baseline
            sizes = [c['size'] for c in chars]
            tops = [c['top'] for c in chars]

            size_counts = defaultdict(int)
            top_counts = defaultdict(float)

            for size in sizes:
                size_counts[round(size, 1)] += 1

            for top in tops:
                top_counts[round(top, 1)] += 1

            baseline_size = max(size_counts.items(), key=lambda x: x[1])[0]
            baseline_top = max(top_counts.items(), key=lambda x: x[1])[0]

            # Extract arrow graphics from this page
            arrows = extract_arrow_graphics(str(pdf_path), page_num)

            # Reconstruct text with notation
            formatted_text = reconstruct_formulas(
                chars,
                baseline_size,
                baseline_top,
                arrows
            )

            # Also get plain text
            plain_text = page.extract_text()

            results.append({
                'page': page_num + 1,
                'text': plain_text,
                'formatted_text': formatted_text,
                'baseline_size': baseline_size,
                'baseline_top': baseline_top
            })

    return results


def reconstruct_formulas(chars: List[Dict], baseline_size: float, baseline_top: float, arrows: List[Dict] = None) -> str:
    """
    Reconstruct text with LaTeX-style notation for sub/superscripts.

    Key insight: Subscripts/superscripts are horizontally adjacent to base text,
    just positioned slightly lower/higher. We need to group by horizontal position first,
    then by vertical clusters within the same horizontal region.

    Args:
        chars: List of character dictionaries from pdfplumber
        baseline_size: Normal font size
        baseline_top: Normal y-position
        arrows: List of arrow graphics with position and direction info

    Returns:
        Text with LaTeX notation (e.g., "H_{2}O reacts with CO_{2}")
    """
    if not chars:
        return ""

    if arrows is None:
        arrows = []

    # Thresholds for detecting sub/superscripts
    size_threshold = baseline_size * 0.80  # 80% of normal size
    sub_y_threshold = baseline_top + 0.5   # Lower position (larger top value)
    super_y_threshold = baseline_top - 0.5 # Higher position (smaller top value)

    # Group characters into lines (by vertical position)
    # Use a smarter approach: subscripts/superscripts can be on the same line even if slightly offset
    lines = []
    current_line = []
    prev_char = None

    # Sort by vertical position first, then by horizontal position
    sorted_by_y = sorted(chars, key=lambda x: (x['top'], x['x0']))

    for char in sorted_by_y:
        if prev_char is None:
            current_line = [char]
        else:
            # Calculate vertical distance from previous character
            vertical_gap = abs(char['top'] - prev_char['top'])

            # Check if this is a subscript or superscript (small and slightly offset)
            is_small = char['size'] < size_threshold
            is_slightly_offset = vertical_gap < baseline_size * 0.8  # Small vertical offset

            # Decision logic:
            # 1. If character is small and slightly offset -> same line (likely subscript/superscript)
            # 2. If character is normal-sized and gap > 8 pixels -> new line
            # 3. If gap is very small (< 3 pixels) -> same line

            if vertical_gap < 3.0:
                # Very small gap -> definitely same line
                current_line.append(char)
            elif is_small and is_slightly_offset:
                # Small character with small offset -> subscript/superscript, same line
                current_line.append(char)
            elif vertical_gap > 8.0 and char['size'] >= size_threshold:
                # Normal-sized character with significant gap -> new line
                if current_line:
                    lines.append(current_line)
                current_line = [char]
            else:
                # Default: if gap is small enough, keep on same line
                if vertical_gap < baseline_size * 1.5:
                    current_line.append(char)
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = [char]

        prev_char = char

    # Don't forget the last line
    if current_line:
        lines.append(current_line)

    # Process each line
    result = []

    for line_idx, line_chars in enumerate(lines):
        # Sort characters in this line by horizontal position
        line_chars = sorted(line_chars, key=lambda x: x['x0'])

        if not line_chars:
            continue

        # Find the baseline for THIS LINE (most common top position of normal-sized chars)
        normal_size_chars = [c for c in line_chars if c['size'] >= size_threshold]
        if normal_size_chars:
            # Use the most common top position among normal-sized characters
            tops_in_line = [c['top'] for c in normal_size_chars]
            from collections import Counter
            line_baseline_top = Counter([round(t, 1) for t in tops_in_line]).most_common(1)[0][0]
        else:
            # Fallback to global baseline
            line_baseline_top = baseline_top

        # Track which arrows have been inserted on this line
        inserted_arrows = set()

        # Process characters in the line
        prev_x1 = None
        current_format = 'normal'

        for char_idx, char in enumerate(line_chars):
            char_text = char['text']
            char_size = char['size']
            char_top = char['top']
            char_x0 = char['x0']

            # Determine format based on size and vertical position RELATIVE TO LINE BASELINE
            is_subscript = False
            is_superscript = False

            if char_size < size_threshold:
                # It's smaller, check if sub or super based on position relative to this line's baseline
                # Remember: lower top value = higher on page = superscript
                #           higher top value = lower on page = subscript
                if char_top > line_baseline_top + 0.5:
                    is_subscript = True
                elif char_top < line_baseline_top - 0.5:
                    is_superscript = True

            # Check for horizontal gap (word spacing)
            # BUT: Don't add space if the current character is a subscript/superscript
            # (subscripts/superscripts should attach to previous character even if there's a gap)
            if prev_x1 is not None and not is_subscript and not is_superscript:
                horizontal_gap = char_x0 - prev_x1

                # Normal word spacing
                if horizontal_gap > baseline_size * 0.25:
                    if current_format != 'normal':
                        result.append('}')
                        current_format = 'normal'
                    result.append(' ')

            # Handle space characters
            if char_text.strip() == '':
                # This is a space character
                # Check if there's an arrow graphic at this position
                arrow_at_position = None
                arrow_id = None
                char_y = char['top']

                for idx, arrow in enumerate(arrows):
                    # Check if this character is near the arrow position
                    if abs(char_y - arrow['y']) < 10:  # Within 10 pixels vertically
                        # Check if character x position is near arrow start
                        if arrow['x_start'] - 5 <= char['x0'] <= arrow['x_end'] + 5:
                            arrow_at_position = arrow
                            arrow_id = idx
                            break

                if arrow_at_position and arrow_id not in inserted_arrows:
                    # There's an arrow here and we haven't inserted it yet!
                    # Insert the arrow with proper spacing
                    if current_format != 'normal':
                        result.append('}')
                        current_format = 'normal'

                    # Use the detected direction
                    result.append(f' {arrow_at_position["direction"]} ')

                    # Mark this arrow as inserted
                    inserted_arrows.add(arrow_id)

                    # Skip this space and continue
                    prev_x1 = char['x1']
                    continue
                elif arrow_at_position and arrow_id in inserted_arrows:
                    # Already inserted this arrow, skip the space
                    prev_x1 = char['x1']
                    continue

                # No arrow, handle normally
                if char_idx + 1 < len(line_chars):
                    next_char = line_chars[char_idx + 1]

                    # Check if next char is sub/super
                    next_is_sub_or_super = False
                    if next_char['size'] < size_threshold:
                        if next_char['top'] > line_baseline_top + 0.5 or next_char['top'] < line_baseline_top - 0.5:
                            next_is_sub_or_super = True

                    # Skip spaces that appear right before subscripts/superscripts
                    if next_is_sub_or_super:
                        continue

            # Apply the formatting
            if is_subscript:
                # Subscript (positioned lower on page)
                if current_format != 'sub':
                    if current_format == 'super':
                        result.append('}')
                    result.append('_{')
                    current_format = 'sub'
            elif is_superscript:
                # Superscript (positioned higher on page)
                if current_format != 'super':
                    if current_format == 'sub':
                        result.append('}')
                    result.append('^{')
                    current_format = 'super'
            else:
                # Normal size or position
                if current_format != 'normal':
                    result.append('}')
                    current_format = 'normal'

            result.append(char_text)

            # Update previous position
            prev_x1 = char['x1']

        # Close any open formatting at end of line
        if current_format != 'normal':
            result.append('}')
            current_format = 'normal'

        # Add newline if not the last line
        if line_idx < len(lines) - 1:
            result.append('\n')

    return ''.join(result)


def extract_formulas(text: str) -> List[str]:
    """
    Extract chemical formulas from formatted text.

    Looks for patterns like: H_{2}O, CO_{2}, K^{+}, etc.
    """
    formulas = []

    # Pattern for chemical formulas with subscripts/superscripts
    # Matches: H_{2}O, CO_{2}, K^{+}, Mg(NO_{3})_{2}, etc.
    patterns = [
        # Element with subscript(s)
        r'[A-Z][a-z]?(?:_\{[^}]+\})+',
        # Element with superscript(s)
        r'[A-Z][a-z]?(?:\^\{[^}]+\})+',
        # Complex formulas with parentheses
        r'[A-Z][a-z]?(?:_\{[^}]+\}|\^\{[^}]+\})*\([^)]+\)(?:_\{[^}]+\}|\^\{[^}]+\})*',
        # Multi-element formulas
        r'(?:[A-Z][a-z]?(?:_\{[^}]+\}|\^\{[^}]+\})*){2,}',
        # Isotope notation
        r'\^\{[^}]+\}_\{[^}]+\}[A-Z][a-z]?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        formulas.extend(matches)

    # Deduplicate while preserving order
    seen = set()
    unique_formulas = []
    for formula in formulas:
        if formula not in seen and len(formula) > 1:  # Ignore single characters
            seen.add(formula)
            unique_formulas.append(formula)

    return unique_formulas


def categorize_formulas(formulas: List[str]) -> Dict[str, List[str]]:
    """
    Categorize chemical formulas.
    """
    categories = {
        'compounds': [],
        'ions': [],
        'isotopes': [],
        'other': []
    }

    for formula in formulas:
        # Check for isotope notation (^{...}_{...}Element)
        if re.search(r'\^\{[^}]+\}_\{[^}]+\}[A-Z]', formula):
            categories['isotopes'].append(formula)

        # Check for ions (contains charges: ^{+}, ^{-}, ^{2+}, etc.)
        elif re.search(r'\^\{[^}]*[+-][^}]*\}', formula):
            categories['ions'].append(formula)

        # Check for compounds (contains elements and subscripts)
        elif re.search(r'[A-Z][a-z]?_\{[^}]+\}', formula):
            categories['compounds'].append(formula)

        else:
            categories['other'].append(formula)

    return categories


def convert_latex_to_unicode(latex_formula: str) -> str:
    """
    Convert LaTeX notation to Unicode subscripts/superscripts.
    """
    SUB_MAP = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎'
    }

    SUP_MAP = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾'
    }

    result = latex_formula

    # Convert subscripts
    def replace_subscript(match):
        content = match.group(1)
        return ''.join(SUB_MAP.get(c, c) for c in content)

    # Convert superscripts
    def replace_superscript(match):
        content = match.group(1)
        return ''.join(SUP_MAP.get(c, c) for c in content)

    result = re.sub(r'_\{([^}]+)\}', replace_subscript, result)
    result = re.sub(r'\^\{([^}]+)\}', replace_superscript, result)

    return result


def save_outputs(
    pages_data: List[Dict],
    formulas: List[str],
    categorized: Dict[str, List[str]],
    output_dir: str,
    pdf_name: str
):
    """
    Save all outputs to files.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_name = Path(pdf_name).stem

    # 1. Save full extracted text (formatted with LaTeX notation)
    full_text_file = output_path / f"{base_name}_full_latex.txt"
    with open(full_text_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("CHEMISTRY PDF EXTRACTION (LaTeX Format)\n")
        f.write("=" * 80 + "\n\n")

        for page_data in pages_data:
            f.write(f"\n{'='*80}\n")
            f.write(f"PAGE {page_data['page']}\n")
            f.write('='*80 + '\n\n')
            f.write(page_data['formatted_text'])
            f.write('\n\n')

    print(f"\n[OK] Saved formatted text: {full_text_file}")

    # 2. Save formulas (LaTeX format)
    formulas_file = output_path / f"{base_name}_formulas_latex.txt"
    with open(formulas_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("EXTRACTED CHEMICAL FORMULAS (LaTeX Format)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total unique formulas: {len(formulas)}\n\n")

        for i, formula in enumerate(formulas, 1):
            f.write(f"{i:3d}. {formula}\n")

    print(f"[OK] Saved LaTeX formulas: {formulas_file}")

    # 3. Save formulas (Unicode format)
    unicode_file = output_path / f"{base_name}_formulas_unicode.txt"
    with open(unicode_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("EXTRACTED CHEMICAL FORMULAS (Unicode Format)\n")
        f.write("=" * 80 + "\n\n")

        for i, formula in enumerate(formulas, 1):
            unicode_form = convert_latex_to_unicode(formula)
            f.write(f"{i:3d}. LaTeX:   {formula}\n")
            f.write(f"     Unicode: {unicode_form}\n\n")

    print(f"[OK] Saved Unicode formulas: {unicode_file}")

    # 4. Save categorized formulas
    categorized_file = output_path / f"{base_name}_categorized.txt"
    with open(categorized_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("CATEGORIZED CHEMICAL FORMULAS\n")
        f.write("=" * 80 + "\n\n")

        for category, items in categorized.items():
            if items:
                f.write(f"\n{category.upper()} ({len(items)})\n")
                f.write("-" * 80 + "\n")
                for i, formula in enumerate(items, 1):
                    unicode_form = convert_latex_to_unicode(formula)
                    f.write(f"{i:3d}. LaTeX:   {formula}\n")
                    f.write(f"     Unicode: {unicode_form}\n\n")

    print(f"[OK] Saved categorized formulas: {categorized_file}")

    # 5. Save plain text (for reference)
    plain_file = output_path / f"{base_name}_plain.txt"
    with open(plain_file, 'w', encoding='utf-8') as f:
        for page_data in pages_data:
            f.write(f"\n{'='*80}\n")
            f.write(f"PAGE {page_data['page']}\n")
            f.write('='*80 + '\n\n')
            f.write(page_data['text'])
            f.write('\n\n')

    print(f"[OK] Saved plain text: {plain_file}")

    # 6. Save metadata
    metadata_file = output_path / f"{base_name}_metadata.json"
    metadata = {
        'pdf_name': pdf_name,
        'total_pages': len(pages_data),
        'total_formulas': len(formulas),
        'categorized': {k: len(v) for k, v in categorized.items()},
        'output_files': {
            'full_latex': str(full_text_file),
            'formulas_latex': str(formulas_file),
            'formulas_unicode': str(unicode_file),
            'categorized': str(categorized_file),
            'plain_text': str(plain_file)
        }
    }
    metadata_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f"[OK] Saved metadata: {metadata_file}")


def print_summary(formulas: List[str], categorized: Dict[str, List[str]]):
    """
    Print extraction summary.
    """
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    print(f"\nTotal unique formulas extracted: {len(formulas)}")

    print("\nCategorized:")
    for category, items in categorized.items():
        if items:
            print(f"  {category.capitalize()}: {len(items)}")

    print("\n" + "=" * 80)
    print("SAMPLE FORMULAS (First 15)")
    print("=" * 80)

    for i, formula in enumerate(formulas[:15], 1):
        unicode_form = convert_latex_to_unicode(formula)
        print(f"{i:2d}. LaTeX:   {formula:30s} → Unicode: {unicode_form}")

    if len(formulas) > 15:
        print(f"\n... and {len(formulas) - 15} more formulas")


def main():
    """
    Main execution function.
    """
    parser = argparse.ArgumentParser(
        description="Extract text and formulas from chemistry PDFs (Hybrid approach)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extraction-approach-hybrid.py "chemistry papers/5070_s22_qp_21.pdf"
  python extraction-approach-hybrid.py "chemistry papers/5070_s22_qp_21.pdf" --output-dir my_output
  python extraction-approach-hybrid.py "chemistry papers/5070_s22_qp_21.pdf" --analyze-first
        """
    )

    parser.add_argument(
        'pdf_path',
        type=str,
        help='Path to the chemistry PDF file'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/hybrid',
        help='Directory to save output files (default: output/hybrid)'
    )

    parser.add_argument(
        '--analyze-first',
        action='store_true',
        help='Analyze first page to show character positioning info'
    )

    parser.add_argument(
        '--show-preview',
        action='store_true',
        help='Show preview of extracted text in console'
    )

    args = parser.parse_args()

    # Check if PDF exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"\n[ERROR] Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    print("\n" + "=" * 80)
    print("CHEMISTRY PDF TEXT EXTRACTOR (Hybrid: PyMuPDF + pdfplumber)")
    print("=" * 80)

    try:
        # Optional: Analyze first page
        if args.analyze_first:
            print("\nAnalyzing first page character positions...")
            analysis = analyze_character_positions(str(pdf_path), 0)
            print("\nCharacter Analysis:")
            print(f"  Baseline size: {analysis.get('baseline_size', 'N/A')}")
            print(f"  Baseline top: {analysis.get('baseline_top', 'N/A')}")
            print(f"  Size range: {analysis.get('size_range', 'N/A')}")
            print(f"  Top range: {analysis.get('top_range', 'N/A')}")
            print(f"  Total characters: {analysis.get('total_chars', 'N/A')}")
            print("\nThis helps understand how subscripts/superscripts are positioned.")

        # Extract text with detailed character analysis
        pages_data = reconstruct_text_with_notation(str(pdf_path))

        print(f"\n[OK] Extraction complete!")
        print(f"  Total pages: {len(pages_data)}")

        # Show preview if requested
        if args.show_preview and pages_data:
            print("\n" + "=" * 80)
            print("TEXT PREVIEW (First page, first 500 characters)")
            print("=" * 80)
            print(pages_data[0]['formatted_text'][:500])
            if len(pages_data[0]['formatted_text']) > 500:
                print(f"\n... and {len(pages_data[0]['formatted_text']) - 500} more characters")

        # Extract formulas from all pages
        print("\nExtracting chemical formulas...")
        all_formulas = []
        for page_data in pages_data:
            formulas = extract_formulas(page_data['formatted_text'])
            all_formulas.extend(formulas)

        # Deduplicate
        unique_formulas = list(dict.fromkeys(all_formulas))

        print("Categorizing formulas...")
        categorized = categorize_formulas(unique_formulas)

        # Save outputs
        save_outputs(
            pages_data,
            unique_formulas,
            categorized,
            args.output_dir,
            str(pdf_path)
        )

        # Print summary
        print_summary(unique_formulas, categorized)

        print("\n" + "=" * 80)
        print("[OK] EXTRACTION COMPLETE!")
        print("=" * 80)
        print(f"\nAll outputs saved to: {args.output_dir}/")

    except Exception as e:
        print(f"\n[ERROR] Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
