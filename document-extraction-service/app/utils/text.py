import re


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces and strip."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_newlines(text: str) -> str:
    """Normalize line endings and collapse excessive blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_table_markdown(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a markdown table from headers and rows."""
    if not headers and not rows:
        return ""

    if not headers and rows:
        headers = [f"Col{i + 1}" for i in range(len(rows[0]))]

    # Ensure all rows have the same number of columns as headers
    col_count = len(headers)
    normalized_rows = []
    for row in rows:
        if len(row) < col_count:
            normalized_rows.append(row + [""] * (col_count - len(row)))
        else:
            normalized_rows.append(row[:col_count])

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in normalized_rows:
        # Escape pipe characters in cell values
        escaped = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")

    return "\n".join(lines)


def clean_cell_value(value) -> str:
    """Convert a cell value to a clean string."""
    if value is None:
        return ""
    return str(value).strip()
