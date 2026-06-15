from app.extractors.docx_extractor import DocxExtractor
from app.models.semantic import BlockType


class TestDocxExtractor:
    def test_extract_headings(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        heading_blocks = [b for b in result.blocks if b.block_type == BlockType.heading]
        assert len(heading_blocks) >= 3
        assert heading_blocks[0].content == "Chapter 1"
        assert heading_blocks[0].heading_level == 1

    def test_extract_paragraphs(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        para_blocks = [b for b in result.blocks if b.block_type == BlockType.paragraph]
        assert len(para_blocks) >= 2

    def test_extract_tables(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        table_blocks = [b for b in result.blocks if b.block_type == BlockType.table]
        assert len(table_blocks) == 1
        assert table_blocks[0].table is not None
        assert table_blocks[0].table.headers == ["Name", "Value"]
        assert len(table_blocks[0].table.rows) == 2

    def test_heading_breadcrumbs(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        # Find the paragraph under Section 1.1
        para_under_section = None
        for b in result.blocks:
            if b.block_type == BlockType.paragraph and b.content == "Content under section 1.1.":
                para_under_section = b
                break

        assert para_under_section is not None
        assert "Chapter 1" in para_under_section.heading_breadcrumbs
        assert "Section 1.1" in para_under_section.heading_breadcrumbs

    def test_metadata(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        assert result.metadata.format == "docx"
        assert result.metadata.source_filename == "test.docx"
        assert result.metadata.title == "Test Document"

    def test_raw_content(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        assert len(result.raw_content) > 0
        assert "Chapter 1" in result.raw_content

    def test_block_indices_are_sequential(self, sample_docx_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_bytes, "test.docx")

        indices = [b.block_index for b in result.blocks]
        assert indices == list(range(len(result.blocks)))

    def test_extract_images(self, sample_docx_with_image_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_with_image_bytes, "product.docx")

        image_blocks = [b for b in result.blocks if b.block_type == BlockType.image]
        assert len(image_blocks) >= 1

        img_block = image_blocks[0]
        assert img_block.image is not None
        assert img_block.image.format in ("png", "jpeg")
        assert len(img_block.image.base64) > 0
        # Image should have heading context from "Product Overview"
        assert "Product Overview" in img_block.heading_breadcrumbs

    def test_image_block_indices_sequential(self, sample_docx_with_image_bytes):
        extractor = DocxExtractor()
        result = extractor.extract(sample_docx_with_image_bytes, "product.docx")

        indices = [b.block_index for b in result.blocks]
        assert indices == list(range(len(result.blocks)))
