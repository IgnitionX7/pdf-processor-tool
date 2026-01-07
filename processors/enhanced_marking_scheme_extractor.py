"""
Enhanced marking scheme extraction with LaTeX support - Root level wrapper.
This imports from the backend.app.processors version for code reuse.
"""
import sys
from pathlib import Path

# Add backend directory to path so we can import app as a package
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Import from the backend.app.processors implementation
# Use the full package path to avoid circular import
from app.processors.enhanced_marking_scheme_extractor import (
    extract_marking_schemes_with_latex,
    extract_marking_schemes_from_pdf_enhanced,
    clean_marking_scheme
)

__all__ = [
    'extract_marking_schemes_with_latex',
    'extract_marking_schemes_from_pdf_enhanced',
    'clean_marking_scheme'
]
