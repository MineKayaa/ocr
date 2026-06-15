import base64
import io

import structlog
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.extractors.base import BaseExtractor
from app.models.semantic import BlockType, ContentBlock, ImageData, SemanticExtractionResult
from app.utils.text import clean_cell_value, normalize_whitespace

logger = structlog.get_logger()

# Style name prefixes that map to heading levels
_HEADING_STYLE_MAP: dict[str, int] = {
    "Heading 1": 1,
    "heading 1": 1,
    "Heading 2": 2,
    "heading 2": 2,
    "Heading 3": 3,
    "heading 3": 3,
    "Heading 4": 4,
    "heading 4": 4,
    "Heading 5": 5,
    "heading 5": 5,
    "Heading 6": 6,
    "heading 6": 6,
    "Title": 1,
    "Subtitle": 2,
}

_LIST_STYLES = {"List Paragraph", "List Bullet", "List Number", "List Continue"}


class DocxExtractor(BaseExtractor):
    supported_extensions = ["docx"]

    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        doc = Document(io.BytesIO(file_bytes))
        blocks: list[ContentBlock] = []
        heading_stack: dict[int, str] = {}
        block_index = 0
        list_buffer: list[str] = []

        title = ""
        if doc.core_properties.title:
            title = doc.core_properties.title

        def flush_list():
            nonlocal block_index
            if list_buffer:
                blocks.append(self._make_list_block(block_index, list(list_buffer), heading_stack))
                block_index += 1
                list_buffer.clear()

        # Walk body children to preserve paragraph/table interleaving
        for element in doc.element.body:
            if element.tag == qn("w:p"):
                para = Paragraph(element, doc)
                text = normalize_whitespace(para.text)

                if text:
                    style_name = para.style.name if para.style else ""

                    # Check for heading
                    heading_level = _HEADING_STYLE_MAP.get(style_name)
                    if heading_level:
                        flush_list()
                        if not title:
                            title = text
                        blocks.append(self._make_heading_block(block_index, text, heading_level, heading_stack))
                        block_index += 1

                    # Check for list
                    elif style_name in _LIST_STYLES or self._is_list_paragraph(element):
                        list_buffer.append(text)

                    # Regular paragraph
                    else:
                        flush_list()
                        blocks.append(self._make_paragraph_block(block_index, text, heading_stack))
                        block_index += 1

                # Extract inline images from this paragraph (even if paragraph has no text)
                for blip in element.findall(".//" + qn("a:blip")):
                    r_embed = blip.get(qn("r:embed"))
                    if r_embed:
                        try:
                            image_part = doc.part.related_parts[r_embed]
                            img_bytes = image_part.blob
                            content_type = image_part.content_type or "image/png"
                            img_format = content_type.split("/")[-1] if "/" in content_type else "png"
                            width, height = self._get_image_dimensions(blip)
                            alt_text = self._get_image_alt_text(blip)
                            b64 = base64.b64encode(img_bytes).decode("ascii")
                            image_data = ImageData(
                                base64=b64, format=img_format,
                                width=width, height=height, alt_text=alt_text,
                            )
                            flush_list()
                            blocks.append(self._make_image_block(block_index, image_data, heading_stack))
                            block_index += 1
                        except (KeyError, Exception) as e:
                            logger.warning("docx_image_failed", rId=r_embed, error=str(e))

            elif element.tag == qn("w:tbl"):
                flush_list()
                table = Table(element, doc)
                headers, rows = self._parse_table(table)
                if headers or rows:
                    blocks.append(self._make_table_block(block_index, headers, rows, heading_stack))
                    block_index += 1

        flush_list()

        metadata = self._create_metadata(filename, title=title)
        raw_content = self._build_raw_content(blocks)

        return SemanticExtractionResult(metadata=metadata, blocks=blocks, raw_content=raw_content)

    def _parse_table(self, table: Table) -> tuple[list[str], list[list[str]]]:
        all_rows = []
        for row in table.rows:
            cells = [clean_cell_value(cell.text) for cell in row.cells]
            all_rows.append(cells)

        if not all_rows:
            return [], []

        headers = all_rows[0]
        data_rows = all_rows[1:]
        return headers, data_rows

    def _is_list_paragraph(self, element) -> bool:
        """Check if paragraph has list numbering properties."""
        num_pr = element.find(qn("w:pPr"))
        if num_pr is not None:
            return num_pr.find(qn("w:numPr")) is not None
        return False

    def _get_image_dimensions(self, blip) -> tuple[int | None, int | None]:
        """Read image dimensions from a:ext elements (EMUs → pixels)."""
        # Walk up to find the extent element
        drawing = blip
        for _ in range(10):
            parent = drawing.getparent()
            if parent is None:
                break
            drawing = parent
            ext = drawing.find(".//" + qn("a:ext"))
            if ext is not None:
                cx = ext.get("cx")
                cy = ext.get("cy")
                if cx and cy:
                    try:
                        return round(int(cx) / 9525), round(int(cy) / 9525)
                    except (ValueError, TypeError):
                        pass
        return None, None

    def _get_image_alt_text(self, blip) -> str:
        """Read alt text from wp:docPr descr attribute."""
        drawing = blip
        for _ in range(10):
            parent = drawing.getparent()
            if parent is None:
                break
            drawing = parent
            doc_pr = drawing.find(".//" + qn("wp:docPr"))
            if doc_pr is not None:
                return doc_pr.get("descr", "")
        return ""
