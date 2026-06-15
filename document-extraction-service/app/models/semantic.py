from enum import Enum

from pydantic import BaseModel


class BlockType(str, Enum):
    heading = "heading"
    paragraph = "paragraph"
    table = "table"
    list = "list"
    key_value_group = "key_value_group"
    image = "image"
    code = "code"
    footnote = "footnote"


class TableData(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    row_count: int
    column_count: int
    markdown: str
    caption: str | None = None
    footnotes: list[str] = []


class ImageData(BaseModel):
    base64: str
    format: str  # "png", "jpeg", "tiff", etc.
    width: int | None = None
    height: int | None = None
    alt_text: str = ""


class KeyValuePair(BaseModel):
    key: str
    value: str
    confidence: float = 1.0


class ContentBlock(BaseModel):
    """Self-contained semantic unit. Each block carries its own context."""

    block_index: int
    block_type: BlockType
    content: str = ""

    # Heading context
    heading_breadcrumbs: list[str] = []
    heading: str | None = None
    heading_level: int = 0

    # Structured data
    table: TableData | None = None
    key_values: list[KeyValuePair] = []
    image: ImageData | None = None

    # Source document context (populated after extraction for self-contained RAG chunks)
    source_filename: str = ""
    document_title: str = ""
    document_format: str = ""

    # Source location
    page_number: int | None = None    # primary page (alias for simple access)
    page_start: int | None = None
    page_end: int | None = None
    slide_number: int | None = None
    sheet_name: str | None = None


class DocumentMetadata(BaseModel):
    title: str = ""
    languages: list[str] = []
    page_count: int = 0
    format: str = ""
    is_scanned: bool = False
    ocr_applied: bool = False
    extraction_method: str = ""
    source_filename: str = ""


class SemanticExtractionResult(BaseModel):
    metadata: DocumentMetadata
    blocks: list[ContentBlock] = []
    raw_content: str = ""
