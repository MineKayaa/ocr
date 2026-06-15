from app.extractors.html_extractor import HtmlExtractor
from app.models.semantic import BlockType


class TestHtmlExtractor:
    def test_extract_headings(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        heading_blocks = [b for b in result.blocks if b.block_type == BlockType.heading]
        assert len(heading_blocks) == 3
        assert heading_blocks[0].content == "Main Title"
        assert heading_blocks[0].heading_level == 1
        assert heading_blocks[1].content == "Section A"
        assert heading_blocks[1].heading_level == 2

    def test_extract_paragraphs(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        para_blocks = [b for b in result.blocks if b.block_type == BlockType.paragraph]
        assert len(para_blocks) >= 2

    def test_extract_tables(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        table_blocks = [b for b in result.blocks if b.block_type == BlockType.table]
        assert len(table_blocks) == 1
        assert table_blocks[0].table is not None
        assert table_blocks[0].table.headers == ["Col1", "Col2"]
        assert len(table_blocks[0].table.rows) == 2

    def test_extract_lists(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        list_blocks = [b for b in result.blocks if b.block_type == BlockType.list]
        assert len(list_blocks) == 1
        assert "Item 1" in list_blocks[0].content
        assert "Item 2" in list_blocks[0].content

    def test_extract_definition_lists(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        kv_blocks = [b for b in result.blocks if b.block_type == BlockType.key_value_group]
        assert len(kv_blocks) == 1
        assert kv_blocks[0].key_values[0].key == "Term"
        assert kv_blocks[0].key_values[0].value == "Definition"

    def test_title_from_title_tag(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        assert result.metadata.title == "Test Page"

    def test_heading_breadcrumbs(self, sample_html):
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(sample_html)

        # Table should be under Section A
        table_blocks = [b for b in result.blocks if b.block_type == BlockType.table]
        assert table_blocks[0].heading == "Section A"
        assert "Main Title" in table_blocks[0].heading_breadcrumbs

    def test_skip_script_and_style(self):
        html = "<html><body><script>alert('x')</script><style>.x{}</style><p>Content</p></body></html>"
        extractor = HtmlExtractor()
        result = extractor.extract_from_html(html)

        assert len(result.blocks) == 1
        assert result.blocks[0].content == "Content"

    def test_extract_from_bytes(self):
        html_bytes = b"<html><body><p>Hello World</p></body></html>"
        extractor = HtmlExtractor()
        result = extractor.extract(html_bytes, "test.html")

        assert len(result.blocks) == 1
        assert result.blocks[0].content == "Hello World"
