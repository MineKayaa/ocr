from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("document_extraction_service_starting", log_level=settings.log_level)
    if settings.tesseract_cmd:
        try:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        except ImportError:
            logger.warning("pytesseract_not_installed")
    yield
    logger.info("document_extraction_service_stopping")


app = FastAPI(
    title="Document Extraction Service",
    description="Extracts structured content from DOCX, PDF, PPTX, XLSX, HTML, CSV documents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import router  # noqa: E402

app.include_router(router)
