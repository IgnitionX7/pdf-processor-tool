"""
Combined pipeline orchestrator.

Runs figure/table extraction first, then text extraction with spatial filtering.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from main_extractor import CombinedExtractor
from extractors.text_extractor import TextExtractor
from extractors.question_extractor import extract_questions_from_text
from extractor_utils.coordinate_converter import extract_exclusion_zones_from_metadata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import noise removal modules (optional)
try:
    import sys
    noise_removal_path = Path(__file__).parent / "noise-removal"
    if str(noise_removal_path) not in sys.path:
        sys.path.insert(0, str(noise_removal_path))
    from noise_detector import NoiseDetector  # type: ignore
    from noise_filter import NoiseFilter  # type: ignore
    from regex_noise_filter import RegexNoiseFilter  # type: ignore
    NOISE_REMOVAL_AVAILABLE = True
except ImportError:
    NOISE_REMOVAL_AVAILABLE = False
    logger.warning("Noise removal module not available")


class CombinedPipeline:
    """Orchestrates figure/table extraction and text extraction."""

    def __init__(self, output_dir: str = "combined_output", skip_first_page: bool = True,
                 dpi: int = 300,
                 caption_figure_padding: float = 0.0,
                 visual_figure_padding: float = 20.0,
                 enable_noise_removal: bool = True,
                 exclude_figures: bool = True,
                 exclude_tables: bool = True):
        """
        Initialize the combined pipeline.

        Args:
            output_dir: Output directory for all results
            skip_first_page: Skip first page during extraction
            dpi: DPI for image conversion
            caption_figure_padding: Amount (in PDF points) to shrink caption-based figure bboxes when filtering text.
                                   Default: 0.0 (no shrink, precise extraction)
            visual_figure_padding: Amount (in PDF points) to shrink visual-detected figure bboxes when filtering text.
                                  Preserves text labels captured with padding. Default: 20.0
            enable_noise_removal: Enable removal of headers, footers, and margin junk text.
                                 Default: True (enabled by default)
            exclude_figures: Whether to exclude figure regions from text extraction.
                           Default: True (exclude figures)
            exclude_tables: Whether to exclude table regions from text extraction.
                          Default: True (exclude tables)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.skip_first_page = skip_first_page
        self.dpi = dpi
        self.caption_figure_padding = caption_figure_padding
        self.visual_figure_padding = visual_figure_padding
        self.enable_noise_removal = enable_noise_removal
        self.exclude_figures = exclude_figures
        self.exclude_tables = exclude_tables

    def phase1_extract_figures_and_tables(self, pdf_path: str) -> dict:
        """
        Phase 1: Extract figures/tables and save metadata (NO text extraction).

        This phase runs figure/table extraction and builds exclusion zones, but does NOT
        extract any text. The metadata is saved for use in phase2.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with:
                - pdf_name: PDF filename
                - output_dir: Output directory path
                - figures_dir: Figures directory path
                - figure_results: List of extracted figures/tables
                - metadata_file: Path to extraction_metadata.json
                - exclusion_zones: Preliminary exclusion zones (for info)
                - statistics: Basic stats (total_figures, total_tables, total_pages)
        """
        pdf_path = Path(pdf_path)
        logger.info(f"\n{'='*70}")
        logger.info(f"PHASE 1: FIGURES/TABLES EXTRACTION - {pdf_path.name}")
        logger.info(f"{'='*70}")

        # Create output subdirectories
        pdf_output_dir = self.output_dir / pdf_path.stem
        figures_dir = pdf_output_dir / "figures"
        figures_dir.mkdir(exist_ok=True, parents=True)

        # ===================================================================
        # STEP 1: Extract Figures and Tables
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 1: EXTRACTING FIGURES AND TABLES")
        logger.info("="*70)

        figure_extractor = CombinedExtractor(
            output_dir=str(figures_dir),
            skip_first_page=self.skip_first_page,
            dpi=self.dpi,
            create_pdf_subdir=False
        )

        figure_results = figure_extractor.extract_from_pdf(str(pdf_path))

        # Load metadata
        metadata_file = figures_dir / "extraction_metadata.json"

        if not metadata_file.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            metadata = {'elements': []}
        else:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

        logger.info(f"\nExtracted {len(figure_results)} figure/table elements")

        # ===================================================================
        # STEP 2: Detect Noise Zones (if enabled)
        # ===================================================================
        if self.enable_noise_removal and NOISE_REMOVAL_AVAILABLE:
            logger.info("\n" + "="*70)
            logger.info("STEP 2: DETECTING NOISE ZONES (HEADERS/FOOTERS/MARGINS)")
            logger.info("="*70)

            detector = NoiseDetector(
                header_threshold=30.0,
                footer_threshold=780.0,
                left_margin_threshold=40.0,
                right_margin_threshold=570.0,
                min_frequency=0.5,
                sample_size=5
            )

            noise_zones = detector.detect_noise_zones(str(pdf_path))
            noise_filter = NoiseFilter(noise_zones)

            stats = noise_filter.get_noise_statistics()
            logger.info(f"Detected {stats['total_zones']} geometry-based noise zones")

        # ===================================================================
        # STEP 3: Build Exclusion Zones (for reference)
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 3: BUILDING FIGURE/TABLE EXCLUSION ZONES")
        logger.info("="*70)

        all_exclusion_zones = extract_exclusion_zones_from_metadata(
            metadata, str(pdf_path), self.dpi
        )

        total_zones = sum(len(zones) for zones in all_exclusion_zones.items())
        logger.info(f"Built {total_zones} preliminary exclusion zones")
        logger.info("  (These will be filtered based on user preferences in Phase 2)")

        # Calculate statistics
        figures_count = sum(1 for elem in metadata.get('elements', []) if elem.get('type') == 'figure')
        tables_count = sum(1 for elem in metadata.get('elements', []) if elem.get('type') == 'table')

        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)

        statistics = {
            'total_figures': figures_count,
            'total_tables': tables_count,
            'total_pages': total_pages,
            'total_elements': len(figure_results)
        }

        logger.info("\n" + "="*70)
        logger.info("PHASE 1 COMPLETE")
        logger.info("="*70)
        logger.info(f"Figures extracted: {figures_count}")
        logger.info(f"Tables extracted: {tables_count}")
        logger.info(f"Total pages: {total_pages}")
        logger.info(f"\nMetadata saved to: {metadata_file}")
        logger.info("="*70 + "\n")

        return {
            'pdf_name': pdf_path.name,
            'output_dir': str(pdf_output_dir),
            'figures_dir': str(figures_dir),
            'figure_results': figure_results,
            'metadata_file': str(metadata_file),
            'exclusion_zones': all_exclusion_zones,
            'statistics': statistics
        }

    def phase2_extract_text_with_exclusions(
        self,
        pdf_path: str,
        metadata_file: str,
        exclude_figures: bool = True,
        exclude_tables: bool = True
    ) -> dict:
        """
        Phase 2: Extract text using saved metadata with user-chosen exclusion zones.

        This phase loads the metadata from phase1 and extracts text with spatial filtering
        based on user preferences.

        Args:
            pdf_path: Path to PDF file
            metadata_file: Path to extraction_metadata.json from Phase 1
            exclude_figures: Whether to exclude figure regions from text
            exclude_tables: Whether to exclude table regions from text

        Returns:
            Dict with:
                - pdf_name: PDF filename
                - text_file: Path to extracted text file
                - questions_file: Path to extracted questions JSON
                - text_results: List of page text data
                - question_results: Question extraction results
                - statistics: Text extraction stats
        """
        pdf_path = Path(pdf_path)
        metadata_file = Path(metadata_file)

        logger.info(f"\n{'='*70}")
        logger.info(f"PHASE 2: TEXT EXTRACTION - {pdf_path.name}")
        logger.info(f"Exclusion settings: Figures={exclude_figures}, Tables={exclude_tables}")
        logger.info(f"{'='*70}")

        # Load metadata from Phase 1
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        logger.info(f"Loaded metadata with {len(metadata.get('elements', []))} elements")

        # Create text output directory
        pdf_output_dir = self.output_dir / pdf_path.stem
        text_dir = pdf_output_dir / "text"
        text_dir.mkdir(exist_ok=True, parents=True)

        # ===================================================================
        # STEP 1: Detect Noise Zones (if enabled)
        # ===================================================================
        noise_filter = None
        regex_filter = None

        if self.enable_noise_removal and NOISE_REMOVAL_AVAILABLE:
            logger.info("\n" + "="*70)
            logger.info("STEP 1: DETECTING NOISE ZONES")
            logger.info("="*70)

            detector = NoiseDetector(
                header_threshold=30.0,
                footer_threshold=780.0,
                left_margin_threshold=40.0,
                right_margin_threshold=570.0,
                min_frequency=0.5,
                sample_size=5
            )

            noise_zones = detector.detect_noise_zones(str(pdf_path))
            noise_filter = NoiseFilter(noise_zones)

            stats = noise_filter.get_noise_statistics()
            logger.info(f"Detected {stats['total_zones']} geometry-based noise zones")

            regex_filter = RegexNoiseFilter(
                filter_page_numbers=True,
                filter_copyright=True,
                filter_mirrored=True,
                filter_turn_over=True,
                filter_cid_garbage=True,
                filter_dots_punct=True
            )
            logger.info("Enabled regex-based text noise filtering")

        # ===================================================================
        # STEP 2: Build Exclusion Zones with User Preferences
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 2: BUILDING EXCLUSION ZONES (USER PREFERENCES)")
        logger.info("="*70)

        all_exclusion_zones = extract_exclusion_zones_from_metadata(
            metadata, str(pdf_path), self.dpi
        )

        # Filter exclusion zones based on user preferences
        exclusion_zones = {}
        for page_num, zones in all_exclusion_zones.items():
            filtered_zones = []
            for zone in zones:
                zone_type = zone.get('type', '').lower()
                if (zone_type == 'figure' and exclude_figures) or \
                   (zone_type == 'table' and exclude_tables):
                    filtered_zones.append(zone)

            if filtered_zones:
                exclusion_zones[page_num] = filtered_zones

        total_zones = sum(len(zones) for zones in exclusion_zones.values())
        total_original_zones = sum(len(zones) for zones in all_exclusion_zones.values())
        logger.info(f"Created {total_zones} exclusion zones from {total_original_zones} detections")
        logger.info(f"  Excluding figures: {exclude_figures}, Excluding tables: {exclude_tables}")

        # ===================================================================
        # STEP 3: Extract Text with Filtering
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 3: EXTRACTING TEXT (WITH FILTERING)")
        logger.info("="*70)

        text_extractor = TextExtractor(
            exclusion_zones=exclusion_zones,
            caption_figure_padding_shrink=self.caption_figure_padding,
            visual_figure_padding_shrink=self.visual_figure_padding,
            noise_filter=noise_filter,
            regex_filter=regex_filter,
            skip_first_page=self.skip_first_page
        )
        text_results = text_extractor.extract_from_pdf(str(pdf_path))

        logger.info(f"Extracted text from {len(text_results)} pages")

        # ===================================================================
        # STEP 4: Save Text Results
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 4: SAVING TEXT EXTRACTION RESULTS")
        logger.info("="*70)

        self._save_text_results(text_results, text_dir, pdf_path.stem)
        self._save_cleaned_text_for_questions(text_results, text_dir, pdf_path.stem)

        # ===================================================================
        # STEP 5: Extract Questions from Text
        # ===================================================================
        logger.info("\n" + "="*70)
        logger.info("STEP 5: EXTRACTING QUESTIONS FROM TEXT")
        logger.info("="*70)

        question_results = self._extract_questions(text_dir, pdf_path.stem)

        # ===================================================================
        # STEP 6: Generate Statistics
        # ===================================================================
        total_chars_before = sum(p.get('total_char_count', 0) for p in text_results)
        total_chars_after = sum(p.get('filtered_char_count', 0) for p in text_results)
        chars_filtered = total_chars_before - total_chars_after
        filter_percentage = (chars_filtered / total_chars_before * 100) if total_chars_before > 0 else 0
        pages_with_text = sum(1 for p in text_results if p.get('filtered_char_count', 0) > 0)

        statistics = {
            'pages_with_text': pages_with_text,
            'total_chars': total_chars_after,
            'total_words': sum(len(p.get('text', '').split()) for p in text_results),
            'filter_percentage': filter_percentage,
            'total_questions': question_results['latex_count']
        }

        logger.info("\n" + "="*70)
        logger.info("PHASE 2 COMPLETE")
        logger.info("="*70)
        logger.info(f"Pages with text: {pages_with_text}")
        logger.info(f"Total characters: {total_chars_after}")
        logger.info(f"Filter percentage: {filter_percentage:.1f}%")
        logger.info(f"Questions extracted: {question_results['latex_count']}")
        logger.info("="*70 + "\n")

        text_file = text_dir / f"{pdf_path.stem}_full_latex.txt"
        questions_file = text_dir / f"{pdf_path.stem}_questions_latex.json"

        return {
            'pdf_name': pdf_path.name,
            'text_file': str(text_file),
            'questions_file': str(questions_file) if questions_file.exists() else None,
            'text_results': text_results,
            'question_results': question_results,
            'statistics': statistics
        }

    def process_pdf(self, pdf_path: str) -> dict:
        """
        Process a PDF: extract figures/tables, then extract text with filtering.

        This method maintains backwards compatibility by calling both phases internally.
        For new code, consider using phase1 and phase2 separately for more control.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with processing results and statistics (merged from both phases)
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"COMBINED PIPELINE (BACKWARDS COMPATIBLE): {Path(pdf_path).name}")
        logger.info(f"Using two-phase architecture internally")
        logger.info(f"{'='*70}")

        # Phase 1: Extract figures/tables
        phase1_results = self.phase1_extract_figures_and_tables(pdf_path)

        # Phase 2: Extract text with configured exclusion settings
        phase2_results = self.phase2_extract_text_with_exclusions(
            pdf_path,
            phase1_results['metadata_file'],
            exclude_figures=self.exclude_figures,
            exclude_tables=self.exclude_tables
        )

        # Merge results for backwards compatibility
        merged_stats = {
            **phase1_results['statistics'],
            **phase2_results['statistics'],
            'total_figures': phase1_results['statistics']['total_figures'],
            'total_chars_before': sum(p.get('total_char_count', 0) for p in phase2_results['text_results']),
            'total_chars_after': phase2_results['statistics']['total_chars'],
            'chars_filtered': sum(p.get('total_char_count', 0) for p in phase2_results['text_results']) - phase2_results['statistics']['total_chars']
        }

        logger.info("\n" + "="*70)
        logger.info("COMBINED PIPELINE COMPLETE")
        logger.info("="*70)
        logger.info(f"Output directory: {phase1_results['output_dir']}")
        logger.info("="*70 + "\n")

        return {
            'pdf_name': phase1_results['pdf_name'],
            'output_dir': phase1_results['output_dir'],
            'figure_results': phase1_results['figure_results'],
            'text_results': phase2_results['text_results'],
            'question_results': phase2_results['question_results'],
            'statistics': merged_stats
        }

    def _save_text_results(self, text_results: list, text_dir: Path, pdf_stem: str):
        """Save text extraction results to files."""

        # Save full text (formatted with LaTeX notation)
        full_text_file = text_dir / f"{pdf_stem}_full_latex.txt"
        with open(full_text_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("EXTRACTED TEXT (LaTeX Format, Filtered)\n")
            f.write("=" * 80 + "\n\n")

            for page_data in text_results:
                f.write(f"\n==================== CLEANED PAGE {page_data['page']} ====================\n\n")
                f.write(page_data['formatted_text'])
                f.write('\n\n')

        logger.info(f"[OK] Saved formatted text: {full_text_file}")

        # Save plain text
        plain_text_file = text_dir / f"{pdf_stem}_plain.txt"
        with open(plain_text_file, 'w', encoding='utf-8') as f:
            for page_data in text_results:
                f.write(f"\n==================== CLEANED PAGE {page_data['page']} ====================\n\n")
                f.write(page_data['text'])
                f.write('\n\n')

        logger.info(f"[OK] Saved plain text: {plain_text_file}")

        # Save metadata
        metadata_file = text_dir / f"{pdf_stem}_text_metadata.json"
        metadata = {
            'total_pages': len(text_results),
            'pages': []
        }

        for page_data in text_results:
            metadata['pages'].append({
                'page': page_data['page'],
                'exclusion_zones': page_data.get('exclusion_zones', 0),
                'total_chars': page_data.get('total_char_count', 0),
                'filtered_chars': page_data.get('filtered_char_count', 0),
                'filter_ratio': (
                    1 - (page_data.get('filtered_char_count', 0) / page_data.get('total_char_count', 1))
                    if page_data.get('total_char_count', 0) > 0 else 0
                )
            })

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"[OK] Saved text metadata: {metadata_file}")

    def _save_cleaned_text_for_questions(self, text_results: list, text_dir: Path, pdf_stem: str):
        """Save cleaned text files in format expected by question extractor."""

        # Save cleaned plain text for question extraction
        cleaned_plain_file = text_dir / f"{pdf_stem}_cleaned_plain.txt"
        with open(cleaned_plain_file, 'w', encoding='utf-8') as f:
            for page_data in text_results:
                # Write page separator in format expected by question extractor
                f.write(f"==================== CLEANED PAGE {page_data['page']} ====================\n\n")
                f.write(page_data['text'])
                f.write('\n\n')

        logger.info(f"[OK] Saved cleaned plain text for questions: {cleaned_plain_file}")

        # Save cleaned LaTeX text for question extraction
        cleaned_latex_file = text_dir / f"{pdf_stem}_cleaned_latex.txt"
        with open(cleaned_latex_file, 'w', encoding='utf-8') as f:
            for page_data in text_results:
                # Write page separator in format expected by question extractor
                f.write(f"==================== CLEANED PAGE {page_data['page']} ====================\n\n")
                f.write(page_data['formatted_text'])
                f.write('\n\n')

        logger.info(f"[OK] Saved cleaned LaTeX text for questions: {cleaned_latex_file}")

    def _extract_questions(self, text_dir: Path, pdf_stem: str) -> dict:
        """Extract questions from both plain and LaTeX text files."""
        results = {
            'plain_questions': None,
            'latex_questions': None,
            'plain_count': 0,
            'latex_count': 0
        }

        # Extract from cleaned plain text
        plain_text_file = text_dir / f"{pdf_stem}_cleaned_plain.txt"
        if plain_text_file.exists():
            try:
                plain_json_output = text_dir / f"{pdf_stem}_questions_plain.json"
                plain_questions = extract_questions_from_text(plain_text_file, plain_json_output)
                results['plain_questions'] = plain_questions
                results['plain_count'] = len(plain_questions)
                logger.info(f"[OK] Extracted {len(plain_questions)} questions from plain text")
                logger.info(f"     Saved to: {plain_json_output}")
            except Exception as e:
                logger.warning(f"Failed to extract questions from plain text: {e}")

        # Extract from cleaned LaTeX formatted text
        latex_text_file = text_dir / f"{pdf_stem}_cleaned_latex.txt"
        if latex_text_file.exists():
            try:
                latex_json_output = text_dir / f"{pdf_stem}_questions_latex.json"
                latex_questions = extract_questions_from_text(latex_text_file, latex_json_output)
                results['latex_questions'] = latex_questions
                results['latex_count'] = len(latex_questions)
                logger.info(f"[OK] Extracted {len(latex_questions)} questions from LaTeX text")
                logger.info(f"     Saved to: {latex_json_output}")
            except Exception as e:
                logger.warning(f"Failed to extract questions from LaTeX text: {e}")

        return results

    def _generate_statistics(self, text_results: list, figure_results: list) -> dict:
        """Generate extraction statistics."""
        total_chars_before = sum(p.get('total_char_count', 0) for p in text_results)
        total_chars_after = sum(p.get('filtered_char_count', 0) for p in text_results)
        chars_filtered = total_chars_before - total_chars_after

        filter_percentage = (chars_filtered / total_chars_before * 100) if total_chars_before > 0 else 0

        pages_with_text = sum(1 for p in text_results if p.get('filtered_char_count', 0) > 0)

        return {
            'total_figures': len(figure_results),
            'pages_with_text': pages_with_text,
            'total_chars_before': total_chars_before,
            'total_chars_after': total_chars_after,
            'chars_filtered': chars_filtered,
            'filter_percentage': filter_percentage
        }


def main():
    """Main entry point for combined pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Combined figure/table + text extraction pipeline'
    )
    parser.add_argument(
        'pdf_path',
        type=str,
        help='Path to PDF file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='combined_output',
        help='Output directory (default: combined_output)'
    )
    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help='DPI for image conversion (default: 300)'
    )
    parser.add_argument(
        '--skip-first-page',
        action='store_true',
        default=True,
        help='Skip first page (default: True)'
    )
    parser.add_argument(
        '--no-skip-first-page',
        dest='skip_first_page',
        action='store_false',
        help='Do not skip first page'
    )
    parser.add_argument(
        '--caption-figure-padding',
        type=float,
        default=0.0,
        help='Shrink caption-based figure bboxes by N points when filtering text (default: 0.0 - no shrink for precise extraction)'
    )
    parser.add_argument(
        '--visual-figure-padding',
        type=float,
        default=20.0,
        help='Shrink visual-detected figure bboxes by N points when filtering text (default: 20.0 - preserves nearby labels)'
    )
    parser.add_argument(
        '--enable-noise-removal',
        action='store_true',
        default=True,
        help='Enable removal of headers, footers, and margin junk text (default: enabled)'
    )
    parser.add_argument(
        '--disable-noise-removal',
        dest='enable_noise_removal',
        action='store_false',
        help='Disable noise removal'
    )

    args = parser.parse_args()

    pipeline = CombinedPipeline(
        output_dir=args.output_dir,
        skip_first_page=args.skip_first_page,
        dpi=args.dpi,
        caption_figure_padding=args.caption_figure_padding,
        visual_figure_padding=args.visual_figure_padding,
        enable_noise_removal=args.enable_noise_removal
    )

    try:
        result = pipeline.process_pdf(args.pdf_path)
        print(f"\n[OK] Pipeline completed successfully!")
        print(f"Results saved to: {result['output_dir']}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
