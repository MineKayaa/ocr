from app.extractors.base import BaseExtractor
from app.extractors.csv_extractor import CsvExtractor
from app.extractors.docx_extractor import DocxExtractor
from app.extractors.html_extractor import HtmlExtractor
from app.extractors.pdf_extractor import PdfExtractor
from app.extractors.pptx_extractor import PptxExtractor
from app.extractors.xlsx_extractor import XlsxExtractor

_EXTRACTORS: list[BaseExtractor] = [
    DocxExtractor(),
    PdfExtractor(),
    PptxExtractor(),
    XlsxExtractor(),
    HtmlExtractor(),
    CsvExtractor(),
]

_EXTENSION_MAP: dict[str, BaseExtractor] = {}
for extractor in _EXTRACTORS:
    for ext in extractor.supported_extensions:
        _EXTENSION_MAP[ext.lower().lstrip(".")] = extractor


def get_extractor(filename: str) -> BaseExtractor | None:
    """Return the extractor for the given filename, or None if unsupported."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXTENSION_MAP.get(ext)


def supported_formats() -> list[str]:
    """Return list of supported file extensions."""
    return sorted(_EXTENSION_MAP.keys())
