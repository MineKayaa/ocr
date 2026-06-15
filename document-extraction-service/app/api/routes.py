import asyncio
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, HTTPException
from pydantic import BaseModel

from app.api.auth import require_api_key
from app.config import settings
from app.extractors.registry import supported_formats
from app.models.requests import (
    BatchExtractionResponse,
    ExtractionResponse,
    FormatsResponse,
    HealthResponse,
    OutputFormat,
)
from app.services.extraction_service import extract_file, extract_html

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.get("/formats", response_model=FormatsResponse)
async def formats():
    return FormatsResponse(formats=supported_formats())


@router.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...),
    output_format: OutputFormat = Query(default=OutputFormat.semantic),
    _api_key: str = Depends(require_api_key),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_bytes = await file.read()

    if len(file_bytes) > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size} bytes",
        )

    try:
        result = await asyncio.to_thread(extract_file, file_bytes, file.filename, output_format)
        return ExtractionResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("extraction_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/batch", response_model=BatchExtractionResponse)
async def extract_batch(
    files: list[UploadFile] = File(...),
    output_format: OutputFormat = Query(default=OutputFormat.semantic),
    _api_key: str = Depends(require_api_key),
):
    results: list[ExtractionResponse] = []
    failed = 0

    async def process_file(f: UploadFile) -> ExtractionResponse:
        nonlocal failed
        if not f.filename:
            failed += 1
            return ExtractionResponse(success=False, error="Filename is required")

        file_bytes = await f.read()
        if len(file_bytes) > settings.max_upload_size:
            failed += 1
            return ExtractionResponse(success=False, error="File too large")

        try:
            result = await asyncio.to_thread(extract_file, file_bytes, f.filename, output_format)
            return ExtractionResponse(result=result)
        except Exception as e:
            failed += 1
            logger.error("batch_extraction_failed", filename=f.filename, error=str(e))
            return ExtractionResponse(success=False, error=str(e))

    tasks = [process_file(f) for f in files]
    results = await asyncio.gather(*tasks)

    return BatchExtractionResponse(
        results=list(results),
        total=len(files),
        failed=failed,
    )


class HtmlExtractionRequest(BaseModel):
    html: str
    output_format: OutputFormat = OutputFormat.semantic


@router.post("/extract/html", response_model=ExtractionResponse)
async def extract_html_endpoint(
    request: HtmlExtractionRequest,
    _api_key: str = Depends(require_api_key),
):
    try:
        result = await asyncio.to_thread(extract_html, request.html, request.output_format)
        return ExtractionResponse(result=result)
    except Exception as e:
        logger.error("html_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
