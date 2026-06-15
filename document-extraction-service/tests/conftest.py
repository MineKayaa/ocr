import io
import os

import pytest
from fastapi.testclient import TestClient

# Ensure no API keys required during tests
os.environ["API_KEYS"] = ""


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def sample_docx_bytes():
    """Create a minimal DOCX file in memory."""
    from docx import Document

    doc = Document()
    doc.core_properties.title = "Test Document"
    doc.add_heading("Chapter 1", level=1)
    doc.add_paragraph("This is the first paragraph under chapter 1.")
    doc.add_heading("Section 1.1", level=2)
    doc.add_paragraph("Content under section 1.1.")

    # Add a table
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Name"
    table.rows[0].cells[1].text = "Value"
    table.rows[1].cells[0].text = "Item A"
    table.rows[1].cells[1].text = "100"
    table.rows[2].cells[0].text = "Item B"
    table.rows[2].cells[1].text = "200"

    doc.add_heading("Chapter 2", level=1)
    doc.add_paragraph("Final paragraph.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_bytes():
    """Create a minimal PPTX file in memory."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide_layout = prs.slide_layouts[1]  # Title and Content

    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Slide One"
    slide.placeholders[1].text = "Bullet point content"

    slide2 = prs.slides.add_slide(slide_layout)
    slide2.shapes.title.text = "Slide Two"
    slide2.placeholders[1].text = "More content here"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_bytes():
    """Create a minimal XLSX file in memory."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    ws.append(["Name", "Price", "Quantity"])
    ws.append(["Widget", "9.99", "100"])
    ws.append(["Gadget", "19.99", "50"])

    ws2 = wb.create_sheet("Orders")
    ws2.append(["OrderID", "Product", "Amount"])
    ws2.append(["001", "Widget", "5"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_html():
    return """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Main Title</h1>
    <p>Introduction paragraph.</p>
    <h2>Section A</h2>
    <p>Content under section A.</p>
    <table>
        <thead><tr><th>Col1</th><th>Col2</th></tr></thead>
        <tbody>
            <tr><td>A1</td><td>B1</td></tr>
            <tr><td>A2</td><td>B2</td></tr>
        </tbody>
    </table>
    <h2>Section B</h2>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    <dl>
        <dt>Term</dt>
        <dd>Definition</dd>
    </dl>
</body>
</html>"""


@pytest.fixture
def sample_csv_bytes():
    return b"Name,Age,City\nAlice,30,Amsterdam\nBob,25,Berlin\n"


@pytest.fixture
def sample_tsv_bytes():
    return b"Name\tAge\tCity\nAlice\t30\tAmsterdam\nBob\t25\tBerlin\n"


@pytest.fixture
def sample_docx_with_image_bytes():
    """Create a DOCX with an inline image."""
    from docx import Document
    from docx.shared import Inches

    doc = Document()
    doc.add_heading("Product Overview", level=1)
    doc.add_paragraph("Below is the product image.")
    # Create a minimal 2x2 red PNG image (smallest valid PNG)
    import struct
    import zlib

    def _make_png(width: int, height: int) -> bytes:
        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr = _chunk(b"IHDR", ihdr_data)
        # Red pixels (RGB)
        raw_data = b""
        for _ in range(height):
            raw_data += b"\x00" + b"\xff\x00\x00" * width
        idat = _chunk(b"IDAT", zlib.compress(raw_data))
        iend = _chunk(b"IEND", b"")
        return header + ihdr + idat + iend

    png_bytes = _make_png(100, 80)
    # Write PNG to a temp BytesIO and add to document
    img_stream = io.BytesIO(png_bytes)
    doc.add_picture(img_stream, width=Inches(2))
    doc.add_paragraph("Caption for the product image.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_with_image_bytes():
    """Create a PPTX with a picture on a slide."""
    from pptx import Presentation
    from pptx.util import Inches
    import struct
    import zlib

    def _make_png(width: int, height: int) -> bytes:
        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr = _chunk(b"IHDR", ihdr_data)
        raw_data = b""
        for _ in range(height):
            raw_data += b"\x00" + b"\x00\xff\x00" * width
        idat = _chunk(b"IDAT", zlib.compress(raw_data))
        iend = _chunk(b"IEND", b"")
        return header + ihdr + idat + iend

    prs = Presentation()
    slide_layout = prs.slide_layouts[5]  # Blank layout
    slide = prs.slides.add_slide(slide_layout)

    # Add a title textbox
    from pptx.util import Pt
    txBox = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(6), Inches(1))
    txBox.text_frame.text = "Slide With Image"

    # Add picture
    png_bytes = _make_png(120, 90)
    img_stream = io.BytesIO(png_bytes)
    slide.shapes.add_picture(img_stream, Inches(1), Inches(2), Inches(3), Inches(2))

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pdf_with_image_bytes():
    """Create a minimal PDF with an embedded image."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Product Catalog", fontsize=24)
    page.insert_text((72, 120), "Below is a product image.", fontsize=12)

    # Create a 100x80 red image and insert it
    import struct
    import zlib

    def _make_png(width: int, height: int) -> bytes:
        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr = _chunk(b"IHDR", ihdr_data)
        raw_data = b""
        for _ in range(height):
            raw_data += b"\x00" + b"\xff\x00\x00" * width
        idat = _chunk(b"IDAT", zlib.compress(raw_data))
        iend = _chunk(b"IEND", b"")
        return header + ihdr + idat + iend

    png_bytes = _make_png(100, 80)
    rect = fitz.Rect(72, 150, 272, 310)
    page.insert_image(rect, stream=png_bytes)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
