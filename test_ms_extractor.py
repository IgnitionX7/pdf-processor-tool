import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.processors.enhanced_marking_scheme_extractor import extract_marking_schemes_from_pdf_enhanced

pdf_path = Path(r'D:\Work-ETL\RazorTalon\pdf-processor-tool\5070_w16_ms_22.pdf')
output_json = Path(r'D:\Work-ETL\RazorTalon\pdf-processor-tool\test_output_ms.json')

# Extract starting from page 2 (index 1, but function uses 1-indexed page numbers)
result = extract_marking_schemes_from_pdf_enhanced(
    pdf_path=pdf_path,
    output_json_path=output_json,
    start_page=2,  # Start from page 2 (1-indexed)
    skip_first_page=False
)

print(f"\nExtracted {len(result)} marking scheme entries")
print("\nFirst 5 entries:")
for i, (key, value) in enumerate(list(result.items())[:5]):
    print(f"{key}: {value[:100]}...")
