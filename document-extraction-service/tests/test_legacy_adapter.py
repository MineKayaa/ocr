from app.adapters.legacy_adapter import convert_to_legacy
from app.models.semantic import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KeyValuePair,
    SemanticExtractionResult,
    TableData,
)


def _make_result() -> SemanticExtractionResult:
    """Create a sample SemanticExtractionResult for testing conversion."""
    blocks = [
        ContentBlock(
            block_index=0,
            block_type=BlockType.heading,
            content="Introduction",
            heading_level=1,
            heading="Introduction",
            heading_breadcrumbs=["Introduction"],
            page_start=1,
            page_end=1,
        ),
        ContentBlock(
            block_index=1,
            block_type=BlockType.paragraph,
            content="First paragraph content.",
            heading_breadcrumbs=["Introduction"],
            heading="Introduction",
            page_start=1,
            page_end=1,
        ),
        ContentBlock(
            block_index=2,
            block_type=BlockType.table,
            content="| A | B |\n| --- | --- |\n| 1 | 2 |",
            heading_breadcrumbs=["Introduction"],
            heading="Introduction",
            table=TableData(
                headers=["A", "B"],
                rows=[["1", "2"]],
                row_count=1,
                column_count=2,
                markdown="| A | B |\n| --- | --- |\n| 1 | 2 |",
            ),
            page_start=1,
            page_end=1,
        ),
        ContentBlock(
            block_index=3,
            block_type=BlockType.key_value_group,
            content="Author: John Doe",
            heading_breadcrumbs=["Introduction"],
            heading="Introduction",
            key_values=[KeyValuePair(key="Author", value="John Doe", confidence=0.95)],
            page_start=2,
            page_end=2,
        ),
        ContentBlock(
            block_index=4,
            block_type=BlockType.heading,
            content="Chapter 2",
            heading_level=1,
            heading="Chapter 2",
            heading_breadcrumbs=["Chapter 2"],
            page_start=2,
            page_end=2,
        ),
        ContentBlock(
            block_index=5,
            block_type=BlockType.paragraph,
            content="Second chapter text.",
            heading_breadcrumbs=["Chapter 2"],
            heading="Chapter 2",
            page_start=2,
            page_end=2,
        ),
    ]

    return SemanticExtractionResult(
        metadata=DocumentMetadata(
            title="Test Doc",
            languages=["en"],
            page_count=2,
            format="docx",
            source_filename="test.docx",
        ),
        blocks=blocks,
        raw_content="Introduction\n\nFirst paragraph content.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nChapter 2\n\nSecond chapter text.",
    )


class TestLegacyAdapter:
    def test_basic_conversion(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        assert legacy.Title == "Test Doc"
        assert legacy.PageCount == 2
        assert legacy.Languages == ["en"]
        assert legacy.RawContent != ""

    def test_sections_created(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        assert len(legacy.Sections) == 2
        assert legacy.Sections[0].Title == "Introduction"
        assert legacy.Sections[1].Title == "Chapter 2"

    def test_section_paragraphs(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        section = legacy.Sections[0]
        assert len(section.Paragraphs) == 1
        assert section.Paragraphs[0].Content == "First paragraph content."
        assert section.Paragraphs[0].Role == "content"

    def test_tables_converted(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        assert len(legacy.Tables) == 1
        table = legacy.Tables[0]
        assert table.Headers == ["A", "B"]
        assert table.RowCount == 1
        assert table.SectionContext == "Introduction"

    def test_key_value_pairs(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        assert len(legacy.KeyValuePairs) == 1
        kv = legacy.KeyValuePairs[0]
        assert kv.Key == "Author"
        assert kv.Value == "John Doe"
        assert kv.Confidence == 0.95

    def test_pages_created(self):
        result = _make_result()
        legacy = convert_to_legacy(result)

        assert len(legacy.Pages) == 2
        assert legacy.Pages[0].PageNumber == 1
        assert legacy.Pages[1].PageNumber == 2

    def test_pascal_case_serialization(self):
        result = _make_result()
        legacy = convert_to_legacy(result)
        data = legacy.model_dump()

        # Verify PascalCase keys
        assert "RawContent" in data
        assert "PageCount" in data
        assert "KeyValuePairs" in data
        assert "raw_content" not in data
