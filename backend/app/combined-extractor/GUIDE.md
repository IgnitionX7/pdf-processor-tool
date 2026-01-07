# Combined Figure/Table & Text Extraction Pipeline - Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [File Structure](#file-structure)
3. [How It Works](#how-it-works)
4. [Usage](#usage)
5. [Output Structure](#output-structure)
6. [Configuration Options](#configuration-options)
7. [Examples](#examples)

---

## Overview

This pipeline extracts figures, tables, and text from PDF documents (specifically designed for chemistry exam papers). It:

1. **Extracts figures and tables** as images (both captioned and uncaptioned)
2. **Extracts text** while filtering out figure/table content
3. **Preserves chemical formulas** with LaTeX notation (subscripts, superscripts)
4. **Handles chemical arrows** (→, ⇌, ←)

### Key Features
- ✅ Caption-based extraction (e.g., "Fig. 1.1", "Table 2.1")
- ✅ Visual detection for uncaptioned elements
- ✅ Smart text filtering to avoid duplicate content
- ✅ LaTeX notation for chemical formulas (H₂O → H_{2}O)
- ✅ Configurable figure padding to preserve nearby text labels

---

## File Structure

### Active/Used Files

```
fig-text-extractor-combined/
│
├── combined_pipeline.py              ⭐ MAIN ENTRY POINT - Run this!
│   └── Orchestrates the entire extraction pipeline
│
├── main_extractor.py                 📦 Figure/Table extraction logic
│   └── CombinedExtractor class (caption + visual detection)
│
├── extractors/                       📁 Extraction modules
│   ├── caption_figure_extractor.py   → Extracts figures with captions
│   ├── caption_table_extractor.py    → Extracts tables with captions
│   ├── visual_detector.py            → Visual detection (CV-based)
│   ├── classifier.py                 → Classifies detected regions
│   ├── table_verifier.py             → Verifies table structures
│   └── text_extractor.py             ⭐ Text extraction with filtering
│
├── utils/                            📁 Helper utilities
│   ├── coordinate_converter.py       ⭐ Converts bbox coordinates
│   ├── helpers.py                    → General helper functions
│   └── constants.py                  → Project constants
│
├── extraction-approach-hybrid-v4-arrows-fixed.py  ⭐ LaTeX formula extractor
│   └── Detects subscripts, superscripts, chemical arrows
│
└── GUIDE.md                          📖 This file!
```

### Documentation Files
- `README.md` - Original project README
- `PHASE1_COMPLETE.md` - Phase 1 completion summary
- `FIGURE_PADDING_FEATURE.md` - Figure padding feature details
- `idea.pdf` - Original project concept

### Legacy/Unused Files
- `fig-extractor-combined.py` - Old standalone figure extractor
- `run.py` - Old entry point (replaced by combined_pipeline.py)
- `extraction-approach-hybrid.py` - Old text extractor (replaced by v4)
- `test_*` directories - Test outputs (can be deleted)
- `debug_*.png` - Debug images (can be deleted)

---

## How It Works

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    INPUT: PDF Document                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Extract Figures & Tables                               │
│  ─────────────────────────────────────────────────────────────  │
│  • main_extractor.py (CombinedExtractor)                        │
│                                                                  │
│  Pass 1: Caption-based extraction                               │
│    └─> extractors/caption_figure_extractor.py                   │
│    └─> extractors/caption_table_extractor.py                    │
│                                                                  │
│  Pass 2: Visual detection (no captions)                         │
│    └─> extractors/visual_detector.py                            │
│    └─> extractors/classifier.py                                 │
│    └─> extractors/table_verifier.py                             │
│                                                                  │
│  Output: PNG images + extraction_metadata.json                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Build Exclusion Zones                                  │
│  ─────────────────────────────────────────────────────────────  │
│  • utils/coordinate_converter.py                                │
│                                                                  │
│  Converts bounding boxes from metadata to PDF coordinates       │
│  Maps exclusion zones by page number                            │
│                                                                  │
│  Output: Dict[page_num → List[exclusion_zones]]                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Extract Text with Filtering                            │
│  ─────────────────────────────────────────────────────────────  │
│  • extractors/text_extractor.py (TextExtractor)                 │
│  • extraction-approach-hybrid-v4-arrows-fixed.py                │
│                                                                  │
│  For each page:                                                 │
│    1. Get all characters (pdfplumber)                           │
│    2. Filter chars in exclusion zones (smart padding)           │
│       - Caption figures: 0pt shrink (precise)                   │
│       - Visual figures: 20pt shrink (preserve labels)           │
│       - Tables: exact bbox (0pt)                                │
│    3. Reconstruct with LaTeX notation                           │
│       - Detect subscripts/superscripts                          │
│       - Detect chemical arrows                                  │
│                                                                  │
│  Output: Text with LaTeX formulas (e.g., H_{2}O)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Save Results                                           │
│  ─────────────────────────────────────────────────────────────  │
│  • Formatted text (LaTeX notation)                              │
│  • Plain text (no formatting)                                   │
│  • Text metadata (per-page statistics)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Generate Statistics                                    │
│  ─────────────────────────────────────────────────────────────  │
│  • Total figures/tables extracted                               │
│  • Total characters filtered                                    │
│  • Per-page filtering ratios                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Details

#### Figure/Table Detection
- **Caption-based**: Searches for patterns like "Fig. 1.1", "Table 2.1"
- **Visual-based**: Uses OpenCV for edge detection, contour detection, grid detection
- **Glyph clustering**: Groups non-text glyphs (chemical structures)

#### Text Filtering
- **Spatial filtering**: Checks character overlap with exclusion zones
- **Smart padding**:
  - **Caption-based figures**: 0pt padding (precise extraction, no shrink needed)
  - **Visual-detected figures**: 20pt inward shrink to preserve text labels captured with padding
  - **Tables**: Exact bbox (no padding)
- **LaTeX reconstruction**: Analyzes character size/position for sub/superscripts

#### Coordinate Systems
The pipeline handles three coordinate systems:
1. **Pixel coordinates** (from pdf2image): Used during visual detection
2. **PyMuPDF coordinates** (bottom-left origin): Used for arrow detection
3. **pdfplumber coordinates** (top-left origin): Used for text extraction

---

## Usage

### Basic Command

```bash
python combined_pipeline.py "path/to/your/paper.pdf"
```

This will:
- Extract figures/tables to `combined_output/[pdf_name]/figures/`
- Extract text to `combined_output/[pdf_name]/text/`

### Full Command Syntax

```bash
python combined_pipeline.py <pdf_path> [options]

Arguments:
  pdf_path                        Path to PDF file (required)

Options:
  --output-dir DIR                Output directory (default: combined_output)
  --dpi N                         DPI for image conversion (default: 300)
  --caption-figure-padding N      Shrink caption-based figure bboxes by N points during text filtering
                                  (default: 0.0 - no shrink for precise extraction)
  --visual-figure-padding N       Shrink visual-detected figure bboxes by N points during text filtering
                                  (default: 20.0 - preserves nearby text labels)
  --skip-first-page               Skip first page (default: enabled)
  --no-skip-first-page            Don't skip first page
```

---

## Output Structure

```
output_directory/
└── [pdf_name]/
    ├── figures/
    │   ├── Fig-1-1.png                    # Extracted figure 1.1
    │   ├── Fig-3-1.png                    # Extracted figure 3.1
    │   ├── Table-2-1.png                  # Extracted table 2.1
    │   ├── Table-4-1.png                  # Extracted table 4.1
    │   └── extraction_metadata.json       # Figure/table metadata
    │
    └── text/
        ├── [pdf_name]_full_latex.txt          # Text with LaTeX notation ⭐
        ├── [pdf_name]_plain.txt               # Plain text (no formatting)
        └── [pdf_name]_text_metadata.json      # Text extraction statistics
```

### File Descriptions

#### 1. `extraction_metadata.json`
Contains bounding boxes and metadata for all extracted figures/tables:
```json
{
  "pdf_name": "5070_s22_qp_21.pdf",
  "total_elements": 5,
  "elements": [
    {
      "filename": "Table-2-1.png",
      "page": 4,
      "type": "table",
      "source": "visual",
      "bbox": {"x": 100, "y": 200, "width": 400, "height": 150}
    }
  ]
}
```

#### 2. `[pdf_name]_full_latex.txt` ⭐ MAIN OUTPUT
Extracted text with LaTeX notation for chemical formulas:
```
PAGE 3
================================================================================

1  Choose from the following compounds to answer the questions.
NH_{4}Cl
BaSO_{4}
K_{2}SO_{3}
Mg(NO_{3})_{2}
Na_{2}CO_{3}
...
```

#### 3. `[pdf_name]_plain.txt`
Plain text without special formatting (for reference).

#### 4. `[pdf_name]_text_metadata.json`
Per-page statistics:
```json
{
  "total_pages": 20,
  "pages": [
    {
      "page": 6,
      "exclusion_zones": 1,
      "total_chars": 1180,
      "filtered_chars": 988,
      "filter_ratio": 0.162
    }
  ]
}
```

---

## Configuration Options

### 1. Output Directory

```bash
# Default: combined_output/
python combined_pipeline.py "paper.pdf"

# Custom directory
python combined_pipeline.py "paper.pdf" --output-dir "my_results"
```

### 2. DPI (Image Quality)

Controls the resolution of extracted figure/table images.

```bash
# Default: 300 DPI (high quality)
python combined_pipeline.py "paper.pdf"

# Lower quality, faster (150 DPI)
python combined_pipeline.py "paper.pdf" --dpi 150

# Higher quality, slower (600 DPI)
python combined_pipeline.py "paper.pdf" --dpi 600
```

**Recommended:**
- 150 DPI: Quick tests
- 300 DPI: Production (default)
- 600 DPI: Publication-quality images

### 3. Figure Padding (Smart Text Filtering)

Controls how much to shrink figure bounding boxes when filtering text. The pipeline uses **different padding for different extraction methods**:

#### Caption-Based Figure Padding (default: 0.0)
Caption-based extraction is precise, so no padding shrink is needed.

```bash
# Default: 0 points (no shrink)
python combined_pipeline.py "paper.pdf"

# If caption-based figures still capture nearby text
python combined_pipeline.py "paper.pdf" --caption-figure-padding 5
```

#### Visual-Detected Figure Padding (default: 20.0)
Visual detection adds padding to capture labels, so we shrink during text filtering to preserve those labels in the text output.

```bash
# Default: 20 points (recommended)
python combined_pipeline.py "paper.pdf"

# More aggressive shrinking (if too much unwanted text preserved)
python combined_pipeline.py "paper.pdf" --visual-figure-padding 30

# Less shrinking (if losing important text near figures)
python combined_pipeline.py "paper.pdf" --visual-figure-padding 10

# No shrinking (will filter out text labels captured in figure images)
python combined_pipeline.py "paper.pdf" --visual-figure-padding 0
```

**How it works:**
- **Caption-based figures** (`source='caption'`): Use `--caption-figure-padding` (default: 0pt)
  - Already precise from caption location
- **Visual-detected figures** (`source='visual'`, `'glyph_clustering'`, `'pdfplumber'`): Use `--visual-figure-padding` (default: 20pt)
  - Adds padding during extraction to capture labels
  - Shrinks bbox during text filtering to preserve those labels in text output
- **Tables** (any source): Always use exact bbox (no padding)

**When to adjust:**
- **Caption padding**: Usually keep at 0, increase to 5-10 only if caption-based figures overlap nearby text
- **Visual padding increase (25-30)**: If you're losing important text labels near visual-detected figures
- **Visual padding decrease (10-15)**: If too much unwanted text is being preserved near visual-detected figures

### 4. First Page Handling

```bash
# Default: Skip first page (title/cover page)
python combined_pipeline.py "paper.pdf"

# Include first page
python combined_pipeline.py "paper.pdf" --no-skip-first-page
```

---

## Examples

### Example 1: Basic Usage

```bash
python combined_pipeline.py "chemistry_exam.pdf"
```

**Output:**
```
combined_output/
└── chemistry_exam/
    ├── figures/
    │   └── chemistry_exam/
    │       ├── Fig-1-1.png
    │       ├── Table-2-1.png
    │       └── extraction_metadata.json
    └── text/
        ├── chemistry_exam_full_latex.txt    ← Main output!
        ├── chemistry_exam_plain.txt
        └── chemistry_exam_text_metadata.json
```

### Example 2: Custom Output Directory

```bash
python combined_pipeline.py "paper.pdf" --output-dir "exam_results/2024"
```

**Output:**
```
exam_results/
└── 2024/
    └── paper/
        ├── figures/
        └── text/
```

### Example 3: High-Quality Images

```bash
python combined_pipeline.py "paper.pdf" --dpi 600 --output-dir "high_quality"
```

### Example 4: Batch Processing (Multiple PDFs)

```bash
# Windows (PowerShell)
Get-ChildItem "papers\*.pdf" | ForEach-Object {
    python combined_pipeline.py $_.FullName --output-dir "batch_output"
}

# Linux/Mac
for pdf in papers/*.pdf; do
    python combined_pipeline.py "$pdf" --output-dir "batch_output"
done
```

### Example 5: Fine-Tuning Figure Padding

```bash
# Test different padding values
python combined_pipeline.py "paper.pdf" --figure-padding 0  --output-dir "test_p0"
python combined_pipeline.py "paper.pdf" --figure-padding 10 --output-dir "test_p10"
python combined_pipeline.py "paper.pdf" --figure-padding 20 --output-dir "test_p20"
python combined_pipeline.py "paper.pdf" --figure-padding 30 --output-dir "test_p30"

# Compare the text outputs to find optimal value
```

---

## Understanding the Output

### LaTeX Notation Guide

The extracted text uses LaTeX notation for chemical formulas:

| PDF Display | LaTeX Output | Meaning |
|-------------|--------------|---------|
| H₂O | `H_{2}O` | Subscript 2 |
| CO₂ | `CO_{2}` | Subscript 2 |
| K⁺ | `K^{+}` | Superscript + |
| Cl⁻ | `Cl^{-}` | Superscript - |
| Mg(NO₃)₂ | `Mg(NO_{3})_{2}` | Complex formula |
| → | `->` | Right arrow |
| ⇌ | `<=>` | Equilibrium arrow |

### Reading Statistics

From `[pdf_name]_text_metadata.json`:

```json
{
  "page": 6,
  "exclusion_zones": 1,        // Number of figures/tables on this page
  "total_chars": 1180,         // Total characters before filtering
  "filtered_chars": 988,       // Characters after filtering
  "filter_ratio": 0.162        // 16.2% of characters were filtered out
}
```

**Interpretation:**
- `filter_ratio = 0.0`: No figures/tables on page (no filtering)
- `filter_ratio = 0.1-0.3`: Typical for pages with 1 figure/table
- `filter_ratio = 0.8-0.9`: Page dominated by tables (e.g., data tables)

---

## Troubleshooting

### Issue: Missing figures/tables

**Solution:**
- Check if they have proper captions (e.g., "Fig. 1.1")
- For uncaptioned elements, the visual detector should catch them
- Try adjusting DPI: `--dpi 150` (faster) or `--dpi 600` (more accurate)

### Issue: Missing text near figures

**Solution:**
- Increase figure padding: `--figure-padding 30`
- Check `text_metadata.json` for high filter ratios on those pages

### Issue: Too much unwanted text preserved

**Solution:**
- Decrease figure padding: `--figure-padding 10`
- Or disable: `--figure-padding 0`

### Issue: Chemical formulas not detected

**Solution:**
- Check if `extraction-approach-hybrid-v4-arrows-fixed.py` exists
- Verify the text extractor is loading it (check console output)

---

## Performance Notes

### Typical Processing Times
(For a 20-page chemistry exam PDF)

| DPI | Time | Image Quality |
|-----|------|---------------|
| 150 | ~10s | Good |
| 300 | ~15s | Excellent (default) |
| 600 | ~30s | Publication-quality |

### Memory Usage
- ~500 MB for 300 DPI processing
- ~1 GB for 600 DPI processing

---

## Dependencies

Required Python packages:
```
pdfplumber
PyMuPDF (fitz)
pdf2image
opencv-python (cv2)
numpy
Pillow (PIL)
```

Install all:
```bash
pip install pdfplumber PyMuPDF pdf2image opencv-python numpy Pillow
```

---

## Tips & Best Practices

1. **Always check the output** - Verify figures and text are extracted correctly
2. **Use 300 DPI for production** - Good balance of quality and speed
3. **Keep default figure padding (20)** - Works well for most PDFs
4. **Check metadata files** - Understand filtering statistics
5. **Test on sample pages first** - Before processing large batches

---

## Quick Reference

### Most Common Commands

```bash
# Basic extraction
python combined_pipeline.py "paper.pdf"

# Custom output
python combined_pipeline.py "paper.pdf" --output-dir "results"

# High quality
python combined_pipeline.py "paper.pdf" --dpi 600

# Fine-tune figure padding
python combined_pipeline.py "paper.pdf" --figure-padding 25

# Process multiple PDFs
for pdf in *.pdf; do python combined_pipeline.py "$pdf"; done
```

### Key Output Files

- **`figures/[pdf_name]/extraction_metadata.json`** - Figure/table locations
- **`text/[pdf_name]_full_latex.txt`** ⭐ - Main text output with formulas
- **`text/[pdf_name]_text_metadata.json`** - Filtering statistics

---

## Support & Further Reading

- **PHASE1_COMPLETE.md** - Technical details and implementation
- **FIGURE_PADDING_FEATURE.md** - Deep dive into figure padding
- **README.md** - Original project documentation

---

**Last Updated:** January 2, 2026
**Version:** 1.0
**Default Settings:** DPI=300, Figure Padding=20pt, Skip First Page=True
