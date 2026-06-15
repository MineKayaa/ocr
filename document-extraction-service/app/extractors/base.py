from abc import ABC, abstractmethod

from app.models.semantic import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    ImageData,
    SemanticExtractionResult,
    TableData,
)
from app.utils.heading import build_breadcrumbs, update_heading_stack
from app.utils.text import generate_table_markdown, normalize_whitespace


class BaseExtractor(ABC):
    """Base class for all document extractors."""

    supported_extensions: list[str] = []

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        """Extract semantic content from file bytes."""
        ...

    def _create_metadata(self, filename: str, **kwargs) -> DocumentMetadata:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        defaults = {
            "source_filename": filename,
            "format": ext,
            "extraction_method": self.__class__.__name__,
        }
        defaults.update(kwargs)
        return DocumentMetadata(**defaults)

    def _make_heading_block(
        self,
        index: int,
        text: str,
        level: int,
        heading_stack: dict[int, str],
        **kwargs,
    ) -> ContentBlock:
        text = normalize_whitespace(text)
        update_heading_stack(heading_stack, level, text)
        return ContentBlock(
            block_index=index,
            block_type=BlockType.heading,
            content=text,
            heading_level=level,
            heading=text,
            heading_breadcrumbs=build_breadcrumbs(heading_stack),
            **kwargs,
        )

    def _make_paragraph_block(
        self,
        index: int,
        text: str,
        heading_stack: dict[int, str],
        **kwargs,
    ) -> ContentBlock:
        text = normalize_whitespace(text)
        breadcrumbs = build_breadcrumbs(heading_stack)
        current_heading = breadcrumbs[-1] if breadcrumbs else None
        return ContentBlock(
            block_index=index,
            block_type=BlockType.paragraph,
            content=text,
            heading_breadcrumbs=breadcrumbs,
            heading=current_heading,
            **kwargs,
        )

    def _make_table_block(
        self,
        index: int,
        headers: list[str],
        rows: list[list[str]],
        heading_stack: dict[int, str],
        caption: str | None = None,
        **kwargs,
    ) -> ContentBlock:
        markdown = generate_table_markdown(headers, rows)
        breadcrumbs = build_breadcrumbs(heading_stack)
        current_heading = breadcrumbs[-1] if breadcrumbs else None
        table_data = TableData(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers) if headers else (len(rows[0]) if rows else 0),
            markdown=markdown,
            caption=caption,
        )
        return ContentBlock(
            block_index=index,
            block_type=BlockType.table,
            content=markdown,
            heading_breadcrumbs=breadcrumbs,
            heading=current_heading,
            table=table_data,
            **kwargs,
        )

    def _make_image_block(
        self,
        index: int,
        image_data: ImageData,
        heading_stack: dict[int, str],
        **kwargs,
    ) -> ContentBlock:
        breadcrumbs = build_breadcrumbs(heading_stack)
        current_heading = breadcrumbs[-1] if breadcrumbs else None
        content = f"[Image: {image_data.alt_text}]" if image_data.alt_text else "[Image]"
        return ContentBlock(
            block_index=index,
            block_type=BlockType.image,
            content=content,
            heading_breadcrumbs=breadcrumbs,
            heading=current_heading,
            image=image_data,
            **kwargs,
        )

    def _make_list_block(
        self,
        index: int,
        items: list[str],
        heading_stack: dict[int, str],
        **kwargs,
    ) -> ContentBlock:
        content = "\n".join(f"- {item}" for item in items)
        breadcrumbs = build_breadcrumbs(heading_stack)
        current_heading = breadcrumbs[-1] if breadcrumbs else None
        return ContentBlock(
            block_index=index,
            block_type=BlockType.list,
            content=content,
            heading_breadcrumbs=breadcrumbs,
            heading=current_heading,
            **kwargs,
        )

    def _build_raw_content(self, blocks: list[ContentBlock]) -> str:
        parts = []
        for block in blocks:
            if block.content:
                parts.append(block.content)
        return "\n\n".join(parts)
