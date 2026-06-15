from enum import Enum

from pydantic import BaseModel

from app.models.legacy import DocumentExtractionResult
from app.models.semantic import SemanticExtractionResult


class OutputFormat(str, Enum):
    semantic = "semantic"
    legacy = "legacy"


class ExtractionResponse(BaseModel):
    success: bool = True
    error: str | None = None
    result: SemanticExtractionResult | DocumentExtractionResult | None = None


class BatchExtractionResponse(BaseModel):
    success: bool = True
    results: list[ExtractionResponse] = []
    total: int = 0
    failed: int = 0


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"


class FormatsResponse(BaseModel):
    formats: list[str] = []
