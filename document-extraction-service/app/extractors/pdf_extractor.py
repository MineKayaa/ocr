import base64
import io
import re
import statistics

import fitz  # PyMuPDF
import pdfplumber
import structlog

from app.extractors.base import BaseExtractor
from app.models.semantic import (
    BlockType,
    ContentBlock,
    ImageData,
    KeyValuePair,
    SemanticExtractionResult,
)
from app.utils.heading import build_breadcrumbs
from app.utils.text import clean_cell_value, normalize_whitespace

logger = structlog.get_logger()

# Pattern for key-value detection: "Label: Value" or "Label\tValue"
_KV_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 _/()-]{1,50})[:]\s+(.+)$")

# A "word" is a sequence of letter/digit characters (Unicode-aware)
_WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)

# Patterns that indicate a page footer/header
_PAGE_FOOTER_PATTERNS = [
    re.compile(r"^\d{1,4}\s+\S+\.\w{2,4}$"),
    re.compile(r"^\S+\.\w{2,4}\s+\d{1,4}$"),
    re.compile(r"^www\.\S+\.\w{2,4}$", re.IGNORECASE),
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^page\s+\d+", re.IGNORECASE),
    re.compile(r"^\d{1,4}\s*[/|]\s*\d{1,4}$"),
]

# Labels commonly found in product spec key-value pairs
_COMMON_KV_LABELS = {
    "MATERIAL", "COLOUR", "COLOR", "TYPE", "SIZE", "WEIGHT",
    "WIDTH", "HEIGHT", "LENGTH", "THICKNESS", "HARDNESS",
    "TEMPERATURE", "SPEED", "DENSITY", "GRADE", "STANDARD",
    "FINISH", "SURFACE", "COATING", "CERTIFICATION",
}


def _is_readable_text(text: str, threshold: float = 0.3) -> bool:
    """Check whether extracted text is readable or garbled."""
    if not text or len(text.strip()) < 10:
        return False
    sample = text[:5000]
    words = _WORD_PATTERN.findall(sample)
    real_word_chars = sum(len(w) for w in words if len(w) >= 3)
    non_ws_chars = sum(1 for ch in sample if not ch.isspace())
    if non_ws_chars == 0:
        return False
    return (real_word_chars / non_ws_chars) >= threshold


def _is_page_footer_or_header(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    return any(p.match(text) for p in _PAGE_FOOTER_PATTERNS)


def _is_kv_table(headers: list[str], rows: list[list[str]]) -> bool:
    """Check if a 2-column table is actually a key-value listing."""
    if len(headers) != 2:
        return False
    total_rows = len(rows) + 1
    if total_rows > 10:
        return False
    all_col1 = [headers[0]] + [row[0] for row in rows if len(row) >= 2]
    label_count = 0
    for val in all_col1:
        val_clean = val.strip().upper()
        if val_clean in _COMMON_KV_LABELS or (val == val.upper() and len(val) < 30) or len(val) < 20:
            label_count += 1
    return label_count >= len(all_col1) * 0.5


def _split_kv_table(headers: list[str], rows: list[list[str]]) -> tuple[list[KeyValuePair], list[str]]:
    """Split a 2-column KV table into key-value pairs and leftover description text."""
    kv_pairs: list[KeyValuePair] = []
    descriptions: list[str] = []
    all_rows = [headers] + rows
    for row in all_rows:
        if len(row) < 2:
            continue
        col1 = clean_cell_value(row[0]).strip()
        col2 = clean_cell_value(row[1]).strip()
        if not col1:
            continue
        col1_upper = col1.upper()
        is_label = (
            col1_upper in _COMMON_KV_LABELS
            or (col1 == col1.upper() and len(col1) < 25 and " " not in col1.strip())
            or len(col1) < 15
        )
        if is_label and col2:
            kv_pairs.append(KeyValuePair(key=col1, value=col2))
        else:
            text = col1
            if col2:
                text = f"{col1} {col2}"
            descriptions.append(normalize_whitespace(text))
    return kv_pairs, descriptions


# ---------------------------------------------------------------------------
# Spatial sorting helpers
# ---------------------------------------------------------------------------

def _detect_column_boundaries(x_centers: list[float], page_width: float) -> list[float]:
    """Detect column boundaries from x-center positions of elements."""
    if not x_centers:
        return [0, page_width]

    sorted_x = sorted(set(round(x, 0) for x in x_centers))
    if len(sorted_x) < 3:
        return [0, page_width]

    # Cluster nearby x-positions
    cluster_tolerance = page_width * 0.05
    clusters: list[float] = []
    current_cluster = [sorted_x[0]]
    for x in sorted_x[1:]:
        if x - current_cluster[-1] <= cluster_tolerance:
            current_cluster.append(x)
        else:
            clusters.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [x]
    clusters.append(sum(current_cluster) / len(current_cluster))

    if len(clusters) < 2:
        return [0, page_width]

    # Find gaps between clusters (>10% of page width → column boundary)
    min_gap = page_width * 0.10
    boundaries = [0.0]
    for i in range(len(clusters) - 1):
        if clusters[i + 1] - clusters[i] > min_gap:
            boundaries.append((clusters[i] + clusters[i + 1]) / 2)
    boundaries.append(page_width)
    return boundaries


def _sort_elements_spatially(elements: list[dict], page_width: float) -> list[dict]:
    """Sort page elements for correct reading order in multi-column layouts.

    Strategy:
    1. Separate full-width elements (section headings) from column elements.
    2. Full-width elements act as section separators.
    3. Within each section (between full-width separators), sort column elements
       by column first, then y-position within each column.

    This ensures that in a 3-column product grid, each product heading is
    immediately followed by its associated data before moving to the next column.
    """
    if len(elements) < 2:
        return elements

    # Classify elements by width
    fw_elements: list[dict] = []
    col_elements: list[dict] = []
    for elem in elements:
        bbox = elem["bbox"]
        elem_width = bbox[2] - bbox[0]
        if elem_width > page_width * 0.55:
            fw_elements.append(elem)
        else:
            col_elements.append(elem)

    fw_elements.sort(key=lambda e: e["bbox"][1])

    if not col_elements:
        return fw_elements

    # Detect column structure
    x_centers = [(e["bbox"][0] + e["bbox"][2]) / 2 for e in col_elements]
    col_boundaries = _detect_column_boundaries(x_centers, page_width)
    num_cols = len(col_boundaries) - 1

    if num_cols <= 1:
        # Single column — just sort everything by y
        return sorted(elements, key=lambda e: e["bbox"][1])

    def get_col_idx(elem):
        x_c = (elem["bbox"][0] + elem["bbox"][2]) / 2
        for i in range(num_cols):
            if col_boundaries[i] <= x_c < col_boundaries[i + 1]:
                return i
        return num_cols - 1

    if not fw_elements:
        # No full-width separators — sort all by column then y
        return sorted(col_elements, key=lambda e: (get_col_idx(e), e["bbox"][1]))

    # Build result: interleave full-width separators with column-sorted sections
    result: list[dict] = []
    prev_y_bottom = 0.0

    for fw in fw_elements:
        fw_y_top = fw["bbox"][1]
        # Column elements between prev section bottom and this fw element
        section = [e for e in col_elements
                   if e["bbox"][1] >= prev_y_bottom - 2 and e["bbox"][1] < fw_y_top - 2]
        section.sort(key=lambda e: (get_col_idx(e), e["bbox"][1]))
        result.extend(section)
        result.append(fw)
        prev_y_bottom = fw["bbox"][3]

    # Column elements after the last full-width element
    remaining = [e for e in col_elements if e["bbox"][1] >= prev_y_bottom - 2]
    remaining.sort(key=lambda e: (get_col_idx(e), e["bbox"][1]))
    result.extend(remaining)

    return result


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class PdfExtractor(BaseExtractor):
    supported_extensions = ["pdf"]

    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        needs_ocr = self._needs_ocr(doc)
        if needs_ocr:
            return self._extract_scanned(file_bytes, filename, doc)
        return self._extract_digital(file_bytes, filename, doc)

    def _needs_ocr(self, doc: fitz.Document) -> bool:
        if len(doc) == 0:
            return False
        pages_to_check = min(3, len(doc))
        all_text = []
        for i in range(pages_to_check):
            all_text.append(doc[i].get_text().strip())
        combined = "\n".join(all_text)
        if len(combined) < 10:
            logger.info("pdf_needs_ocr", reason="no_text")
            return True
        if not _is_readable_text(combined):
            logger.info("pdf_needs_ocr", reason="garbled_text", sample=combined[:200])
            return True
        return False

    def _extract_digital(
        self, file_bytes: bytes, filename: str, doc: fitz.Document
    ) -> SemanticExtractionResult:
        blocks: list[ContentBlock] = []
        heading_stack: dict[int, str] = {}
        block_index = 0
        title = ""

        # Median font size for heading detection (sample first 5 pages)
        median_font = self._compute_median_font(doc)
        repeated_texts = self._detect_repeated_headers_footers(doc)

        plumber_pdf = pdfplumber.open(io.BytesIO(file_bytes))

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_number = page_num + 1
            page_width = page.rect.width

            # Collect ALL elements (text + tables + images) with bounding boxes
            elements = self._collect_page_elements(
                page, plumber_pdf, page_num, median_font, repeated_texts, doc=doc
            )

            # Sort spatially (column-aware for grid layouts)
            elements = _sort_elements_spatially(elements, page_width)

            # Process elements in spatial order
            for elem in elements:
                if elem["kind"] == "text":
                    heading_level = self._classify_heading(
                        elem["font_size"], median_font, elem["is_bold"]
                    )
                    if heading_level:
                        if not title:
                            title = elem["text"]
                        blocks.append(self._make_heading_block(
                            block_index, elem["text"], heading_level, heading_stack,
                            page_start=page_number, page_end=page_number,
                        ))
                        block_index += 1
                    else:
                        kv_match = _KV_PATTERN.match(elem["text"])
                        if kv_match:
                            breadcrumbs = build_breadcrumbs(heading_stack)
                            current_heading = breadcrumbs[-1] if breadcrumbs else None
                            kv = KeyValuePair(
                                key=kv_match.group(1).strip(),
                                value=kv_match.group(2).strip(),
                            )
                            blocks.append(ContentBlock(
                                block_index=block_index,
                                block_type=BlockType.key_value_group,
                                content=elem["text"],
                                heading_breadcrumbs=breadcrumbs,
                                heading=current_heading,
                                key_values=[kv],
                                page_start=page_number,
                                page_end=page_number,
                            ))
                        else:
                            blocks.append(self._make_paragraph_block(
                                block_index, elem["text"], heading_stack,
                                page_start=page_number, page_end=page_number,
                            ))
                        block_index += 1

                elif elem["kind"] == "table":
                    headers = elem["headers"]
                    rows = elem["rows"]
                    if _is_kv_table(headers, rows):
                        kv_pairs, descriptions = _split_kv_table(headers, rows)
                        if kv_pairs:
                            breadcrumbs = build_breadcrumbs(heading_stack)
                            current_heading = breadcrumbs[-1] if breadcrumbs else None
                            kv_content = "\n".join(
                                f"{kv.key}: {kv.value}" for kv in kv_pairs
                            )
                            blocks.append(ContentBlock(
                                block_index=block_index,
                                block_type=BlockType.key_value_group,
                                content=kv_content,
                                heading_breadcrumbs=breadcrumbs,
                                heading=current_heading,
                                key_values=kv_pairs,
                                page_start=page_number,
                                page_end=page_number,
                            ))
                            block_index += 1
                        for desc in descriptions:
                            if desc:
                                blocks.append(self._make_paragraph_block(
                                    block_index, desc, heading_stack,
                                    page_start=page_number, page_end=page_number,
                                ))
                                block_index += 1
                    else:
                        blocks.append(self._make_table_block(
                            block_index, headers, rows, heading_stack,
                            page_start=page_number, page_end=page_number,
                        ))
                        block_index += 1

                elif elem["kind"] == "image":
                    image_data = ImageData(
                        base64=elem["base64"],
                        format=elem["format"],
                        width=elem["width"],
                        height=elem["height"],
                    )
                    blocks.append(self._make_image_block(
                        block_index, image_data, heading_stack,
                        page_start=page_number, page_end=page_number,
                    ))
                    block_index += 1

        page_count = len(doc)
        doc.close()
        plumber_pdf.close()

        metadata = self._create_metadata(
            filename, title=title, page_count=page_count,
            extraction_method="pymupdf+pdfplumber",
        )
        raw_content = self._build_raw_content(blocks)
        return SemanticExtractionResult(
            metadata=metadata, blocks=blocks, raw_content=raw_content
        )

    # ------------------------------------------------------------------
    # Element collection
    # ------------------------------------------------------------------

    def _collect_page_elements(
        self,
        page: fitz.Page,
        plumber_pdf,
        page_index: int,
        median_font: float,
        repeated_texts: set[str],
        doc: fitz.Document | None = None,
    ) -> list[dict]:
        """Collect all text and table elements from a page with bounding boxes.

        Returns a flat list of element dicts, each with a 'kind' ('text' or 'table')
        and a 'bbox' tuple for spatial sorting.
        """
        elements: list[dict] = []

        # Get table bounding boxes from pdfplumber (for excluding text in table regions)
        table_bboxes: list[tuple] = []
        plumber_tables = []
        try:
            if page_index < len(plumber_pdf.pages):
                plumber_page = plumber_pdf.pages[page_index]
                found_tables = plumber_page.find_tables()
                for table in found_tables:
                    table_bboxes.append(table.bbox)
                    table_data = table.extract()
                    if table_data and table_data[0]:
                        headers = [clean_cell_value(c) for c in table_data[0]]
                        rows = [[clean_cell_value(c) for c in row]
                                for row in table_data[1:]]
                        plumber_tables.append({
                            "kind": "table",
                            "bbox": table.bbox,
                            "headers": headers,
                            "rows": rows,
                        })
        except Exception as e:
            logger.warning("table_collection_failed", page=page_index, error=str(e))

        # Collect text blocks from PyMuPDF (skip those overlapping tables)
        text_dict = page.get_text("dict")
        for block_data in text_dict.get("blocks", []):
            if block_data.get("type") != 0:
                continue
            bbox = tuple(block_data.get("bbox", (0, 0, 0, 0)))
            if self._overlaps_any(bbox, table_bboxes):
                continue

            text_parts: list[str] = []
            max_font_size = 0.0
            is_bold = False

            for line in block_data.get("lines", []):
                line_parts = []
                for span in line.get("spans", []):
                    t = span.get("text", "")
                    if t.strip():
                        line_parts.append(t)
                        s = span.get("size", 12.0)
                        if s > max_font_size:
                            max_font_size = s
                        if span.get("flags", 0) & (1 << 4):
                            is_bold = True
                if line_parts:
                    text_parts.append(" ".join(line_parts))

            full_text = normalize_whitespace(" ".join(text_parts))
            if not full_text:
                continue
            if _is_page_footer_or_header(full_text):
                continue
            if full_text in repeated_texts:
                continue

            elements.append({
                "kind": "text",
                "bbox": bbox,
                "text": full_text,
                "font_size": max_font_size,
                "is_bold": is_bold,
            })

        # Collect images from PyMuPDF
        if doc is not None:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    # Convert CMYK to RGB
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    # Skip tiny images (likely decorative dots, lines, icons)
                    if pix.width < 50 or pix.height < 50:
                        pix = None
                        continue
                    # Get image bounding box on page
                    img_rects = page.get_image_rects(xref)
                    bbox = tuple(img_rects[0]) if img_rects else (0, 0, pix.width, pix.height)
                    img_bytes = pix.tobytes("png")
                    b64 = base64.b64encode(img_bytes).decode("ascii")
                    elements.append({
                        "kind": "image",
                        "bbox": bbox,
                        "base64": b64,
                        "format": "png",
                        "width": pix.width,
                        "height": pix.height,
                    })
                    pix = None  # free memory
                except Exception as e:
                    logger.warning("image_extraction_failed", xref=xref, error=str(e))

        elements.extend(plumber_tables)
        return elements

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_median_font(self, doc: fitz.Document) -> float:
        font_sizes: list[float] = []
        for i in range(min(5, len(doc))):
            text_dict = doc[i].get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            font_sizes.append(span["size"])
        return statistics.median(font_sizes) if font_sizes else 12.0

    def _detect_repeated_headers_footers(self, doc: fitz.Document) -> set[str]:
        if len(doc) < 3:
            return set()
        pages_to_check = min(10, len(doc))
        text_counts: dict[str, int] = {}
        for i in range(pages_to_check):
            text_dict = doc[i].get_text("dict")
            page_texts: set[str] = set()
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                full_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        full_text += span.get("text", "")
                full_text = normalize_whitespace(full_text)
                if full_text and len(full_text) < 100:
                    page_texts.add(full_text)
            for text in page_texts:
                text_counts[text] = text_counts.get(text, 0) + 1
        threshold = pages_to_check * 0.6
        return {text for text, count in text_counts.items() if count >= threshold}

    def _extract_scanned(
        self, file_bytes: bytes, filename: str, doc: fitz.Document
    ) -> SemanticExtractionResult:
        blocks: list[ContentBlock] = []
        heading_stack: dict[int, str] = {}
        block_index = 0
        page_count = len(doc)
        doc.close()
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            images = convert_from_bytes(file_bytes, dpi=300)
            for page_num, image in enumerate(images, start=1):
                text = pytesseract.image_to_string(image)
                text = normalize_whitespace(text)
                if text:
                    blocks.append(self._make_paragraph_block(
                        block_index, text, heading_stack,
                        page_start=page_num, page_end=page_num,
                    ))
                    block_index += 1
        except ImportError:
            pass
        metadata = self._create_metadata(
            filename, page_count=page_count, is_scanned=True,
            ocr_applied=block_index > 0, extraction_method="tesseract-ocr",
        )
        raw_content = self._build_raw_content(blocks)
        return SemanticExtractionResult(
            metadata=metadata, blocks=blocks, raw_content=raw_content
        )

    def _classify_heading(
        self, font_size: float, median_size: float, is_bold: bool
    ) -> int | None:
        if median_size <= 0:
            return None
        ratio = font_size / median_size
        if ratio >= 2.0:
            return 1
        if ratio >= 1.6:
            return 2
        if ratio >= 1.3:
            return 3
        if ratio >= 1.15 and is_bold:
            return 4
        if is_bold and ratio >= 1.0:
            return 5
        return None

    def _overlaps_any(self, block_bbox: tuple, table_bboxes: list[tuple]) -> bool:
        bx0, by0, bx1, by1 = block_bbox
        for tx0, ty0, tx1, ty1 in table_bboxes:
            if bx0 < tx1 and bx1 > tx0 and by0 < ty1 and by1 > ty0:
                return True
        return False
