import structlog

logger = structlog.get_logger()


def is_scanned_pdf(file_bytes: bytes) -> bool:
    """Detect if a PDF is scanned (image-based) rather than digital text."""
    try:
        import fitz

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_to_check = min(3, len(doc))
        for i in range(pages_to_check):
            page = doc[i]
            text = page.get_text().strip()
            if len(text) > 10:
                doc.close()
                return False
        doc.close()
        return True
    except Exception:
        logger.warning("scanned_pdf_detection_failed")
        return False


def ocr_pdf_pages(file_bytes: bytes) -> list[str]:
    """Run Tesseract OCR on each page of a scanned PDF. Returns list of text per page."""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        images = convert_from_bytes(file_bytes, dpi=300)
        results = []
        for image in images:
            text = pytesseract.image_to_string(image)
            results.append(text.strip())
        return results
    except ImportError:
        logger.warning("ocr_dependencies_not_installed", hint="Install pytesseract and pdf2image")
        return []
    except Exception as e:
        logger.error("ocr_failed", error=str(e))
        return []
