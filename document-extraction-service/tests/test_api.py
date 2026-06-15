import io
import json

import pytest


class TestHealthEndpoint:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestFormatsEndpoint:
    def test_formats(self, client):
        response = client.get("/formats")
        assert response.status_code == 200
        data = response.json()
        assert "docx" in data["formats"]
        assert "pdf" in data["formats"]
        assert "xlsx" in data["formats"]
        assert "html" in data["formats"]
        assert "csv" in data["formats"]
        assert "pptx" in data["formats"]


class TestExtractEndpoint:
    def test_extract_docx(self, client, sample_docx_bytes):
        response = client.post(
            "/extract",
            files={"file": ("test.docx", io.BytesIO(sample_docx_bytes), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] is not None
        assert "blocks" in data["result"]
        assert len(data["result"]["blocks"]) > 0

        # Every block should carry source document context
        block = data["result"]["blocks"][0]
        assert block["source_filename"] == "test.docx"
        assert block["document_format"] == "docx"
        assert block["document_title"] == "Test Document"
        assert block["page_number"] is not None or block["page_start"] is None

    def test_extract_docx_legacy(self, client, sample_docx_bytes):
        response = client.post(
            "/extract?output_format=legacy",
            files={"file": ("test.docx", io.BytesIO(sample_docx_bytes), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        result = data["result"]
        # Legacy format should have PascalCase keys
        assert "RawContent" in result
        assert "Sections" in result
        assert "Tables" in result

    def test_extract_csv(self, client, sample_csv_bytes):
        response = client.post(
            "/extract",
            files={"file": ("data.csv", io.BytesIO(sample_csv_bytes), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_extract_unsupported_format(self, client):
        response = client.post(
            "/extract",
            files={"file": ("test.xyz", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_extract_xlsx(self, client, sample_xlsx_bytes):
        response = client.post(
            "/extract",
            files={"file": ("test.xlsx", io.BytesIO(sample_xlsx_bytes), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_extract_pptx(self, client, sample_pptx_bytes):
        response = client.post(
            "/extract",
            files={"file": ("test.pptx", io.BytesIO(sample_pptx_bytes), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestExtractHtmlEndpoint:
    def test_extract_html(self, client, sample_html):
        response = client.post(
            "/extract/html",
            json={"html": sample_html},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "blocks" in data["result"]

    def test_extract_html_legacy(self, client, sample_html):
        response = client.post(
            "/extract/html",
            json={"html": sample_html, "output_format": "legacy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Sections" in data["result"]


class TestBatchEndpoint:
    def test_batch_extract(self, client, sample_docx_bytes, sample_csv_bytes):
        response = client.post(
            "/extract/batch",
            files=[
                ("files", ("test.docx", io.BytesIO(sample_docx_bytes), "application/octet-stream")),
                ("files", ("data.csv", io.BytesIO(sample_csv_bytes), "text/csv")),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2


class TestApiKeyAuth:
    def test_no_key_required_when_not_configured(self, client, sample_csv_bytes):
        """When API_KEYS is empty, requests should pass without a key."""
        response = client.post(
            "/extract",
            files={"file": ("data.csv", io.BytesIO(sample_csv_bytes), "text/csv")},
        )
        assert response.status_code == 200
