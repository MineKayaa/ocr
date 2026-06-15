from app.extractors.pptx_extractor import PptxExtractor
from app.models.semantic import BlockType


class TestPptxExtractor:
    def test_extract_slide_titles(self, sample_pptx_bytes):
        extractor = PptxExtractor()
        result = extractor.extract(sample_pptx_bytes, "test.pptx")

        heading_blocks = [b for b in result.blocks if b.block_type == BlockType.heading]
        assert len(heading_blocks) >= 2
        assert heading_blocks[0].content == "Slide One"
        assert heading_blocks[0].slide_number == 1

    def test_extract_content(self, sample_pptx_bytes):
        extractor = PptxExtractor()
        result = extractor.extract(sample_pptx_bytes, "test.pptx")

        para_blocks = [b for b in result.blocks if b.block_type == BlockType.paragraph]
        assert len(para_blocks) >= 2

    def test_metadata(self, sample_pptx_bytes):
        extractor = PptxExtractor()
        result = extractor.extract(sample_pptx_bytes, "test.pptx")

        assert result.metadata.format == "pptx"
        assert result.metadata.page_count == 2
        assert result.metadata.title == "Slide One"

    def test_slide_numbers_tracked(self, sample_pptx_bytes):
        extractor = PptxExtractor()
        result = extractor.extract(sample_pptx_bytes, "test.pptx")

        slide_1_blocks = [b for b in result.blocks if b.slide_number == 1]
        slide_2_blocks = [b for b in result.blocks if b.slide_number == 2]
        assert len(slide_1_blocks) >= 1
        assert len(slide_2_blocks) >= 1

    def test_extract_images(self, sample_pptx_with_image_bytes):
        extractor = PptxExtractor()
        result = extractor.extract(sample_pptx_with_image_bytes, "slides.pptx")

        image_blocks = [b for b in result.blocks if b.block_type == BlockType.image]
        assert len(image_blocks) >= 1

        img_block = image_blocks[0]
        assert img_block.image is not None
        assert img_block.image.format in ("png", "jpeg")
        assert len(img_block.image.base64) > 0
        assert img_block.slide_number == 1
        assert img_block.image.width is not None
        assert img_block.image.height is not None
