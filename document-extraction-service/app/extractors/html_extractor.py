from bs4 import BeautifulSoup, NavigableString, Tag

from app.extractors.base import BaseExtractor
from app.models.semantic import BlockType, ContentBlock, KeyValuePair, SemanticExtractionResult
from app.utils.heading import build_breadcrumbs, update_heading_stack
from app.utils.text import clean_cell_value, normalize_whitespace

_SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"}
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_CONTAINER_TAGS = {"section", "article", "div", "main", "body"}


class HtmlExtractor(BaseExtractor):
    supported_extensions = ["html", "htm"]

    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        html = file_bytes.decode("utf-8", errors="replace")
        return self.extract_from_html(html, filename)

    def extract_from_html(self, html: str, filename: str = "input.html") -> SemanticExtractionResult:
        soup = BeautifulSoup(html, "html.parser")

        blocks: list[ContentBlock] = []
        heading_stack: dict[int, str] = {}
        block_index = [0]  # mutable counter

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = normalize_whitespace(title_tag.get_text())

        def walk(element):
            nonlocal title
            if isinstance(element, NavigableString):
                return
            if not isinstance(element, Tag):
                return

            tag_name = element.name.lower() if element.name else ""

            if tag_name in _SKIP_TAGS:
                return

            # Headings
            if tag_name in _HEADING_TAGS:
                text = normalize_whitespace(element.get_text())
                if not text:
                    return
                level = _HEADING_TAGS[tag_name]
                if not title:
                    title = text
                blocks.append(self._make_heading_block(block_index[0], text, level, heading_stack))
                block_index[0] += 1
                return

            # Tables
            if tag_name == "table":
                headers, rows = self._parse_html_table(element)
                if headers or rows:
                    caption_tag = element.find("caption")
                    caption = normalize_whitespace(caption_tag.get_text()) if caption_tag else None
                    blocks.append(
                        self._make_table_block(block_index[0], headers, rows, heading_stack, caption=caption)
                    )
                    block_index[0] += 1
                return

            # Lists
            if tag_name in ("ul", "ol"):
                items = []
                for li in element.find_all("li", recursive=False):
                    text = normalize_whitespace(li.get_text())
                    if text:
                        items.append(text)
                if items:
                    blocks.append(self._make_list_block(block_index[0], items, heading_stack))
                    block_index[0] += 1
                return

            # Definition lists → key-value groups
            if tag_name == "dl":
                kv_pairs = []
                current_key = None
                for child in element.children:
                    if isinstance(child, Tag):
                        if child.name == "dt":
                            current_key = normalize_whitespace(child.get_text())
                        elif child.name == "dd" and current_key:
                            value = normalize_whitespace(child.get_text())
                            kv_pairs.append(KeyValuePair(key=current_key, value=value))
                            current_key = None
                if kv_pairs:
                    breadcrumbs = build_breadcrumbs(heading_stack)
                    current_heading = breadcrumbs[-1] if breadcrumbs else None
                    blocks.append(
                        ContentBlock(
                            block_index=block_index[0],
                            block_type=BlockType.key_value_group,
                            content="\n".join(f"{kv.key}: {kv.value}" for kv in kv_pairs),
                            heading_breadcrumbs=breadcrumbs,
                            heading=current_heading,
                            key_values=kv_pairs,
                        )
                    )
                    block_index[0] += 1
                return

            # Preformatted / code blocks
            if tag_name in ("pre", "code"):
                text = element.get_text()
                if text.strip():
                    breadcrumbs = build_breadcrumbs(heading_stack)
                    current_heading = breadcrumbs[-1] if breadcrumbs else None
                    blocks.append(
                        ContentBlock(
                            block_index=block_index[0],
                            block_type=BlockType.code,
                            content=text.strip(),
                            heading_breadcrumbs=breadcrumbs,
                            heading=current_heading,
                        )
                    )
                    block_index[0] += 1
                return

            # Paragraphs
            if tag_name == "p":
                text = normalize_whitespace(element.get_text())
                if text:
                    blocks.append(self._make_paragraph_block(block_index[0], text, heading_stack))
                    block_index[0] += 1
                return

            # Containers — recurse
            if tag_name in _CONTAINER_TAGS or tag_name in ("html", "body", "[document]"):
                for child in element.children:
                    walk(child)
                return

            # Inline or unknown — try to get text
            if tag_name not in _CONTAINER_TAGS:
                # Recurse into children for mixed content
                for child in element.children:
                    walk(child)

        walk(soup)

        metadata = self._create_metadata(filename, title=title)
        raw_content = self._build_raw_content(blocks)

        return SemanticExtractionResult(metadata=metadata, blocks=blocks, raw_content=raw_content)

    def _parse_html_table(self, table_element: Tag) -> tuple[list[str], list[list[str]]]:
        headers: list[str] = []
        rows: list[list[str]] = []

        # Try thead for headers
        thead = table_element.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [clean_cell_value(th.get_text()) for th in header_row.find_all(["th", "td"])]

        # Get data rows from tbody or direct tr children
        tbody = table_element.find("tbody")
        row_container = tbody if tbody else table_element

        for tr in row_container.find_all("tr", recursive=False):
            # Skip header row if already captured
            if tr.parent == thead:
                continue
            cells = [clean_cell_value(td.get_text()) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)

        # If no thead, use first row as headers
        if not headers and rows:
            first_row_element = table_element.find("tr")
            if first_row_element:
                th_cells = first_row_element.find_all("th")
                if th_cells:
                    headers = [clean_cell_value(th.get_text()) for th in th_cells]
                    # Remove first row from data if it was used as headers
                    if rows and rows[0] == headers:
                        rows = rows[1:]
                else:
                    headers = rows[0]
                    rows = rows[1:]

        return headers, rows
