# Noise Removal Module

Two-stage noise removal system for PDFs:

## Stage 1: Geometry-Based Filtering
Detects and filters out repetitive junk text based on location:
- **Headers** (top of page)
- **Footers** (bottom of page)
- **Left/Right margins** (side text)

## Stage 2: Regex-Based Filtering
Filters text patterns that weren't caught by geometry:
- **Page numbers** (standalone numbers)
- **Page codes** (* 0000800000001 *)
- **Copyright lines** (UCLES, Cambridge, exam codes)
- **Mirrored warnings** (NIGRAM = MARGIN reversed)
- **"[Turn over"** text
- **CID artifacts** ((cid:123))
- **Dots/punctuation-only lines**

## How It Works

### Geometry-Based (Stage 1)

1. **Detection Phase** (`NoiseDetector`):
   - Samples pages from the PDF (first, middle, last)
   - Identifies repetitive text patterns in header/footer/margin zones
   - Determines exact coordinates of noise zones

2. **Filtering Phase** (`NoiseFilter`):
   - Filters out characters that fall within detected noise zones
   - Applied BEFORE figure/table exclusion filtering

### Regex-Based (Stage 2)

3. **Pattern Filtering** (`RegexNoiseFilter`):
   - Applies regex patterns to filter text-level noise
   - Removes lines matching known noise patterns
   - Cleans inline artifacts (CID codes, excessive dots)
   - Applied AFTER all geometry-based filtering

## Usage

### Standalone Testing

```bash
cd noise-removal
python test_noise_removal.py
```

### Integrated with Pipeline

```bash
# Enable noise removal with --enable-noise-removal flag
python combined_pipeline.py "path/to/paper.pdf" --enable-noise-removal
```

## Configuration

Default thresholds in `NoiseDetector`:

```python
NoiseDetector(
    header_threshold=80.0,      # Y-coordinate for header zone (pts from top)
    footer_threshold=760.0,     # Y-coordinate for footer zone (pts from top)
    left_margin_threshold=80.0,  # X-coordinate for left margin (pts from left)
    right_margin_threshold=515.0, # X-coordinate for right margin (pts from left)
    min_frequency=0.5,          # Min % of pages a pattern must appear on
    sample_size=5               # Number of pages to sample for detection
)
```

## Files

- `noise_detector.py` - Detects geometry-based noise zones by analyzing PDF pages
- `noise_filter.py` - Filters characters based on detected geometry zones
- `regex_noise_filter.py` - Filters text using regex patterns for text-level noise
- `test_noise_removal.py` - Test script for geometry-based filtering
- `__init__.py` - Module exports

## Example Output

```
## DETECTED NOISE ZONES ##

Header zones:
  Y: 0.0 - 89.9

Footer zones:
  Y: 770.2 - 841.9

Left margin zones:
  X: 0.0 - 155.7

Right margin zones:
  X: 512.5 - 595.3

## FILTER STATISTICS ##

{
  "header_zones_count": 1,
  "footer_zones_count": 1,
  "left_margin_zones_count": 1,
  "right_margin_zones_count": 1,
  "total_zones": 4,
  "header_height": 89.9,
  "footer_height": 71.7,
  "left_margin_width": 155.7,
  "right_margin_width": 82.8
}
```

On the sample PDF (`2059_s25_qp_02.pdf`), noise removal filtered out **38-53%** of characters per page.

## Integration

The two-stage noise filter is automatically applied when enabled:

1. PDF loaded
2. **Geometry-based noise zones detected** (if `--enable-noise-removal`)
3. Figures/tables extracted
4. **Text extraction**:
   - **Stage 1**: Characters filtered by geometry-based noise zones (headers/footers/margins)
   - Characters filtered by figure/table exclusion zones
   - Text reconstructed
   - **Stage 2**: Text filtered by regex patterns (page numbers, copyright, mirrored text, etc.)
   - LaTeX notation applied
5. Results saved

## Filtering Order

```
Raw PDF Characters
    ↓
[Geometry Filter] → Remove headers/footers/margins (if enabled)
    ↓
[Exclusion Zones] → Remove figure/table content
    ↓
[Text Reconstruction] → Build text from remaining characters
    ↓
[Regex Filter] → Remove text-level noise patterns (if enabled)
    ↓
[LaTeX Notation] → Apply chemical formula formatting
    ↓
Final Clean Text
```
