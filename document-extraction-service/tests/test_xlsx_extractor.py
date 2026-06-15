from app.extractors.xlsx_extractor import XlsxExtractor
from app.models.semantic import BlockType


class TestXlsxExtractor:
    def test_extract_sheets_as_headings(self, sample_xlsx_bytes):
        extractor = XlsxExtractor()
        result = extractor.extract(sample_xlsx_bytes, "test.xlsx")

        heading_blocks = [b for b in result.blocks if b.block_type == BlockType.heading]
        assert len(heading_blocks) == 2
        assert heading_blocks[0].content == "Products"
        assert heading_blocks[1].content == "Orders"

    def test_extract_tables(self, sample_xlsx_bytes):
        extractor = XlsxExtractor()
        result = extractor.extract(sample_xlsx_bytes, "test.xlsx")

        table_blocks = [b for b in result.blocks if b.block_type == BlockType.table]
        assert len(table_blocks) == 2

        # Products table
        products = table_blocks[0]
        assert products.table is not None
        assert products.table.headers == ["Name", "Price", "Quantity"]
        assert len(products.table.rows) == 2
        assert products.sheet_name == "Products"

    def test_metadata(self, sample_xlsx_bytes):
        extractor = XlsxExtractor()
        result = extractor.extract(sample_xlsx_bytes, "test.xlsx")

        assert result.metadata.format == "xlsx"

    def test_table_markdown(self, sample_xlsx_bytes):
        extractor = XlsxExtractor()
        result = extractor.extract(sample_xlsx_bytes, "test.xlsx")

        table_blocks = [b for b in result.blocks if b.block_type == BlockType.table]
        assert "| Name | Price | Quantity |" in table_blocks[0].table.markdown
