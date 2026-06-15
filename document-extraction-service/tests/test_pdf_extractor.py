"""PDF extractor tests. These require PyMuPDF to create test PDFs."""
import io

import fitz
import pytest

from app.extractors.pdf_extractor import PdfExtractor, _is_readable_text
from app.models.semantic import BlockType


def _create_simple_pdf() -> bytes:
    """Create a minimal PDF with text content for testing."""
    doc = fitz.open()

    # Page 1 with a large heading and body text
    page = doc.new_page()
    # Title (large font)
    page.insert_text((72, 72), "Document Title", fontsize=24)
    # Body text (normal font)
    page.insert_text((72, 120), "This is the first paragraph of the document.", fontsize=12)
    page.insert_text((72, 140), "This is the second paragraph.", fontsize=12)

    # Page 2 with more content
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Section Two", fontsize=18)
    page2.insert_text((72, 120), "Content under section two.", fontsize=12)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestPdfExtractor:
    def test_extract_basic_text(self):
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        result = extractor.extract(pdf_bytes, "test.pdf")

        assert len(result.blocks) > 0
        assert result.metadata.format == "pdf"
        assert result.metadata.page_count == 2

    def test_detect_headings_by_font_size(self):
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        result = extractor.extract(pdf_bytes, "test.pdf")

        heading_blocks = [b for b in result.blocks if b.block_type == BlockType.heading]
        assert len(heading_blocks) >= 1
        # The 24pt text should be detected as a heading
        assert any("Document Title" in b.content for b in heading_blocks)

    def test_paragraphs_extracted(self):
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        result = extractor.extract(pdf_bytes, "test.pdf")

        para_blocks = [b for b in result.blocks if b.block_type == BlockType.paragraph]
        assert len(para_blocks) >= 1

    def test_page_numbers_tracked(self):
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        result = extractor.extract(pdf_bytes, "test.pdf")

        page_1_blocks = [b for b in result.blocks if b.page_start == 1]
        page_2_blocks = [b for b in result.blocks if b.page_start == 2]
        assert len(page_1_blocks) >= 1
        assert len(page_2_blocks) >= 1

    def test_raw_content(self):
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        result = extractor.extract(pdf_bytes, "test.pdf")

        assert "Document Title" in result.raw_content

    def test_digital_pdf_does_not_need_ocr(self):
        """Digital PDF with readable text should not need OCR."""
        pdf_bytes = _create_simple_pdf()
        extractor = PdfExtractor()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert not extractor._needs_ocr(doc)
        doc.close()

    def test_readable_text_detection(self):
        """Normal text should be detected as readable."""
        assert _is_readable_text("This is a normal English sentence with punctuation.")
        assert _is_readable_text("Dit is een Nederlandse zin met speciale tekens: é, ë, ü.")

    def test_garbled_text_detection(self):
        """Garbled text from custom font encoding should be detected as not readable."""
        garbled = "Ã @ × @ Â ¨ © ñ õ ðK ñ õ @ ãÓ @ ÄÜ ©   @ Ó  £@  £ §\u0001© @ £  £ §  § ©"
        assert not _is_readable_text(garbled)

    def test_extract_images(self, sample_pdf_with_image_bytes):
        """PDF with an embedded image should produce an image block."""
        extractor = PdfExtractor()
        result = extractor.extract(sample_pdf_with_image_bytes, "catalog.pdf")

        image_blocks = [b for b in result.blocks if b.block_type == BlockType.image]
        assert len(image_blocks) >= 1

        img_block = image_blocks[0]
        assert img_block.image is not None
        assert img_block.image.format == "png"
        assert img_block.image.width >= 50
        assert img_block.image.height >= 50
        assert len(img_block.image.base64) > 0
        assert img_block.content == "[Image]"
        assert img_block.page_start == 1
