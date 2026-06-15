"""Convert SemanticExtractionResult to legacy DocumentExtractionResult (C# PascalCase)."""

from app.models.legacy import (
    DocumentExtractionResult,
    ExtractedKeyValuePair,
    ExtractedPage,
    ExtractedParagraph,
    ExtractedSection,
    ExtractedTable,
)
from app.models.semantic import BlockType, ContentBlock, SemanticExtractionResult


def convert_to_legacy(result: SemanticExtractionResult) -> DocumentExtractionResult:
    """Convert a semantic extraction result to the legacy C# compatible format."""
    sections: list[ExtractedSection] = []
    tables: list[ExtractedTable] = []
    key_value_pairs: list[ExtractedKeyValuePair] = []
    pages: list[ExtractedPage] = []

    # Build pages list from metadata
    if result.metadata.page_count > 0:
        for i in range(1, result.metadata.page_count + 1):
            pages.append(ExtractedPage(PageNumber=i))
    else:
        pages.append(ExtractedPage(PageNumber=1))

    # Group blocks into sections (flush on each new heading)
    current_section: _SectionBuilder | None = None
    section_index = 0
    table_index = 0

    for block in result.blocks:
        if block.block_type == BlockType.heading:
            # Flush current section
            if current_section and current_section.has_content():
                sections.append(current_section.build(section_index))
                section_index += 1
            current_section = _SectionBuilder(block)

        elif block.block_type == BlockType.table:
            if block.table:
                section_context = " > ".join(block.heading_breadcrumbs) if block.heading_breadcrumbs else ""
                tables.append(
                    ExtractedTable(
                        TableIndex=table_index,
                        StartPageNumber=block.page_start or 0,
                        EndPageNumber=block.page_end or 0,
                        RowCount=block.table.row_count,
                        ColumnCount=block.table.column_count,
                        Headers=block.table.headers,
                        Rows=block.table.rows,
                        SectionContext=section_context,
                        MarkdownContent=block.table.markdown,
                        Caption=block.table.caption or "",
                        Footnotes=block.table.footnotes,
                    )
                )
                table_index += 1

        elif block.block_type == BlockType.key_value_group:
            for kv in block.key_values:
                key_value_pairs.append(
                    ExtractedKeyValuePair(
                        Key=kv.key,
                        Value=kv.value,
                        PageNumber=block.page_start or 0,
                        Confidence=kv.confidence,
                    )
                )

        elif block.block_type in (BlockType.paragraph, BlockType.list, BlockType.code, BlockType.footnote):
            if current_section is None:
                current_section = _SectionBuilder(None)
            role = _block_type_to_role(block.block_type)
            current_section.add_paragraph(block, role)

    # Flush last section
    if current_section and current_section.has_content():
        sections.append(current_section.build(section_index))

    return DocumentExtractionResult(
        RawContent=result.raw_content,
        PageCount=result.metadata.page_count or 1,
        Title=result.metadata.title,
        Languages=result.metadata.languages,
        Pages=pages,
        Tables=tables,
        Sections=sections,
        KeyValuePairs=key_value_pairs,
    )


def _block_type_to_role(block_type: BlockType) -> str:
    mapping = {
        BlockType.heading: "sectionHeading",
        BlockType.paragraph: "content",
        BlockType.list: "content",
        BlockType.code: "content",
        BlockType.footnote: "footnote",
        BlockType.key_value_group: "content",
        BlockType.image: "content",
    }
    return mapping.get(block_type, "content")


class _SectionBuilder:
    def __init__(self, heading_block: ContentBlock | None):
        self.title = ""
        self.start_page = 0
        self.end_page = 0
        self.paragraphs: list[ExtractedParagraph] = []

        if heading_block:
            self.title = heading_block.content
            self.start_page = heading_block.page_start or 0
            self.end_page = heading_block.page_end or 0

    def add_paragraph(self, block: ContentBlock, role: str):
        self.paragraphs.append(
            ExtractedParagraph(
                Content=block.content,
                PageNumber=block.page_start or 0,
                Role=role,
            )
        )
        if block.page_start:
            if self.start_page == 0:
                self.start_page = block.page_start
            self.end_page = max(self.end_page, block.page_end or block.page_start)

    def has_content(self) -> bool:
        return bool(self.title or self.paragraphs)

    def build(self, section_index: int) -> ExtractedSection:
        content = "\n".join(p.Content for p in self.paragraphs)
        return ExtractedSection(
            SectionIndex=section_index,
            Title=self.title,
            StartPageNumber=self.start_page,
            EndPageNumber=self.end_page,
            Content=content,
            Paragraphs=self.paragraphs,
        )
