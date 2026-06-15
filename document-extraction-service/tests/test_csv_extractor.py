from app.extractors.csv_extractor import CsvExtractor
from app.models.semantic import BlockType


class TestCsvExtractor:
    def test_extract_csv(self, sample_csv_bytes):
        extractor = CsvExtractor()
        result = extractor.extract(sample_csv_bytes, "data.csv")

        assert len(result.blocks) == 1
        block = result.blocks[0]
        assert block.block_type == BlockType.table
        assert block.table is not None
        assert block.table.headers == ["Name", "Age", "City"]
        assert len(block.table.rows) == 2
        assert block.table.rows[0] == ["Alice", "30", "Amsterdam"]

    def test_extract_tsv(self, sample_tsv_bytes):
        extractor = CsvExtractor()
        result = extractor.extract(sample_tsv_bytes, "data.tsv")

        assert len(result.blocks) == 1
        block = result.blocks[0]
        assert block.table is not None
        assert block.table.headers == ["Name", "Age", "City"]
        assert len(block.table.rows) == 2

    def test_metadata(self, sample_csv_bytes):
        extractor = CsvExtractor()
        result = extractor.extract(sample_csv_bytes, "data.csv")

        assert result.metadata.format == "csv"

    def test_markdown_content(self, sample_csv_bytes):
        extractor = CsvExtractor()
        result = extractor.extract(sample_csv_bytes, "data.csv")

        assert "| Name | Age | City |" in result.blocks[0].table.markdown
        assert "| Alice | 30 | Amsterdam |" in result.blocks[0].table.markdown
