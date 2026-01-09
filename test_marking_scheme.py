import pdfplumber
import json

pdf_path = r'D:\Work-ETL\RazorTalon\pdf-processor-tool\5070_w16_ms_22.pdf'

with pdfplumber.open(pdf_path) as pdf:
    # Check a few pages
    for page_num in range(1, min(4, len(pdf.pages))):
        page = pdf.pages[page_num]
        tables = page.find_tables()

        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1}")
        print(f"{'='*80}")
        print(f"Tables found: {len(tables)}")

        if tables:
            for table_idx, table in enumerate(tables):
                print(f"\n--- Table {table_idx + 1} ---")
                table_data = table.extract()

                if table_data:
                    # Show first 5 rows
                    for row_idx, row in enumerate(table_data[:5]):
                        print(f"Row {row_idx}: {row}")
                else:
                    print("No data extracted")
