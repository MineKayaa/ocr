"""Run both docling and the in-repo PdfExtractor service on the same PDFs
and save outputs side-by-side so we can compare extraction quality.

Layout produced:
  results/
    docling/<stem>/output.md
    docling/<stem>/output.json
    extractor_service/<stem>/output.md   (synthesized from blocks)
    extractor_service/<stem>/output.json (full SemanticExtractionResult)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PDF_DIR = HERE / "docling"
RESULTS = HERE / "results"

PDFS = [
    PDF_DIR / "md_broc_en_energy_web.pdf",
    PDF_DIR / "md_broc_en_corporate_web_0.pdf",
    PDF_DIR / "RAPPLON BELT SOLUTION PROVIDER.pdf",
]

# Make the extraction service importable as a package
sys.path.insert(0, str(HERE / "document-extraction-service"))


def run_docling(pdf: Path) -> None:
    from docling.document_converter import DocumentConverter

    out_dir = RESULTS / "docling" / pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    converter = DocumentConverter()
    result = converter.convert(str(pdf))
    md = result.document.export_to_markdown()
    data = result.document.export_to_dict()
    dt = time.time() - t0

    (out_dir / "output.md").write_text(md)
    (out_dir / "output.json").write_text(json.dumps(data, indent=2))
    print(
        f"[docling] {pdf.name}: {len(md)} md chars, "
        f"{len(data.get('tables', []))} tables, "
        f"{len(data.get('pictures', []))} pictures, {dt:.1f}s"
    )


def blocks_to_markdown(result) -> str:
    """Synthesize a markdown view from SemanticExtractionResult blocks."""
    lines: list[str] = []
    meta = result.metadata
    if meta and getattr(meta, "document_title", None):
        lines.append(f"# {meta.document_title}")
        lines.append("")

    for b in result.blocks:
        bt = b.block_type.value if hasattr(b.block_type, "value") else str(b.block_type)
        if bt == "heading":
            lvl = max(1, min(6, b.heading_level or 2))
            lines.append(f"{'#' * lvl} {b.content}")
        elif bt == "table":
            if b.table and b.table.markdown:
                lines.append(b.table.markdown)
            else:
                lines.append(b.content)
        elif bt == "key_value_group":
            lines.append(b.content)
        elif bt == "image":
            lines.append(f"![image](<{len(b.image.base64) if b.image else 0} bytes>)")
        elif bt == "list":
            lines.append(b.content)
        else:
            lines.append(b.content)
        lines.append("")
    return "\n".join(lines)


def run_extractor_service(pdf: Path) -> None:
    from app.extractors.pdf_extractor import PdfExtractor

    out_dir = RESULTS / "extractor_service" / pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    file_bytes = pdf.read_bytes()
    t0 = time.time()
    extractor = PdfExtractor()
    result = extractor.extract(file_bytes, pdf.name)
    dt = time.time() - t0

    md = blocks_to_markdown(result)
    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result.dict()

    (out_dir / "output.md").write_text(md)
    (out_dir / "output.json").write_text(json.dumps(data, indent=2))

    n_tables = sum(
        1 for b in result.blocks if (b.block_type.value if hasattr(b.block_type, "value") else b.block_type) == "table"
    )
    n_headings = sum(
        1 for b in result.blocks if (b.block_type.value if hasattr(b.block_type, "value") else b.block_type) == "heading"
    )
    n_images = sum(
        1 for b in result.blocks if (b.block_type.value if hasattr(b.block_type, "value") else b.block_type) == "image"
    )
    print(
        f"[extractor] {pdf.name}: {len(md)} md chars, "
        f"{len(result.blocks)} blocks ({n_headings} headings, {n_tables} tables, {n_images} images), {dt:.1f}s"
    )


def main() -> None:
    for pdf in PDFS:
        if not pdf.exists():
            print(f"MISSING: {pdf}")
            continue
        print(f"\n=== {pdf.name} ===")
        try:
            run_docling(pdf)
        except Exception as e:
            print(f"[docling] FAILED: {e}")
        try:
            run_extractor_service(pdf)
        except Exception as e:
            print(f"[extractor] FAILED: {e}")


if __name__ == "__main__":
    main()
