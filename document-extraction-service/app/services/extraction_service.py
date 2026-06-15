import structlog

from app.adapters.legacy_adapter import convert_to_legacy
from app.extractors.html_extractor import HtmlExtractor
from app.extractors.registry import get_extractor, supported_formats
from app.models.legacy import DocumentExtractionResult
from app.models.requests import OutputFormat
from app.models.semantic import SemanticExtractionResult
from app.services.language_detector import detect_languages

logger = structlog.get_logger()


def _enrich_blocks(result: SemanticExtractionResult) -> None:
    """Populate source document context on every block so each is self-contained."""
    meta = result.metadata
    for block in result.blocks:
        block.source_filename = meta.source_filename
        block.document_title = meta.title
        block.document_format = meta.format
        if block.page_number is None:
            block.page_number = block.page_start


def extract_file(
    file_bytes: bytes,
    filename: str,
    output_format: OutputFormat = OutputFormat.semantic,
) -> SemanticExtractionResult | DocumentExtractionResult:
    """Extract content from a file and return in the requested format."""
    extractor = get_extractor(filename)
    if extractor is None:
        supported = ", ".join(supported_formats())
        raise ValueError(f"Unsupported file format: {filename}. Supported: {supported}")

    logger.info("extracting_file", filename=filename, extractor=extractor.__class__.__name__)

    result = extractor.extract(file_bytes, filename)

    # Enrich with language detection
    if result.raw_content:
        result.metadata.languages = detect_languages(result.raw_content)

    # Stamp source document context onto every block
    _enrich_blocks(result)

    if output_format == OutputFormat.legacy:
        return convert_to_legacy(result)

    return result


def extract_html(
    html: str,
    output_format: OutputFormat = OutputFormat.semantic,
) -> SemanticExtractionResult | DocumentExtractionResult:
    """Extract content from raw HTML string."""
    extractor = HtmlExtractor()
    result = extractor.extract_from_html(html)

    if result.raw_content:
        result.metadata.languages = detect_languages(result.raw_content)

    _enrich_blocks(result)

    if output_format == OutputFormat.legacy:
        return convert_to_legacy(result)

    return result
