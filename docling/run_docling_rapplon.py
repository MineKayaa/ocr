import json
from pathlib import Path
from docling.document_converter import DocumentConverter

HERE = Path(__file__).parent
pdf_path = HERE / "RAPPLON BELT SOLUTION PROVIDER.pdf"

converter = DocumentConverter()
result = converter.convert(str(pdf_path))

md = result.document.export_to_markdown()
data = result.document.export_to_dict()

(HERE / "output3.md").write_text(md)
(HERE / "output3.json").write_text(json.dumps(data, indent=2))

print("=== MARKDOWN (first 3000 chars) ===")
print(md[:3000])
print("...")
print(f"\n[markdown length: {len(md)} chars]")
print(f"[pages: {len(data.get('pages', {}))}]")
print(f"[tables: {len(data.get('tables', []))}]")
print(f"[pictures: {len(data.get('pictures', []))}]")
