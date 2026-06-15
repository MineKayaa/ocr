import json
from pathlib import Path
from docling.document_converter import DocumentConverter

HERE = Path(__file__).parent
pdf_path = HERE / "md_broc_en_energy_web.pdf"

converter = DocumentConverter()
result = converter.convert(str(pdf_path))

md = result.document.export_to_markdown()
data = result.document.export_to_dict()

(HERE / "output.md").write_text(md)
(HERE / "output.json").write_text(json.dumps(data, indent=2))

print("=== MARKDOWN (first 3000 chars) ===")
print(md[:3000])
print("...")
print(f"\n[markdown length: {len(md)} chars]")
print(f"[json keys: {list(data.keys())}]")
