import structlog
from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException

logger = structlog.get_logger()


def detect_languages(text: str, max_languages: int = 3) -> list[str]:
    """Detect languages in the given text. Returns ISO 639-1 codes."""
    if not text or len(text.strip()) < 20:
        return []
    try:
        # Use a sample for efficiency
        sample = text[:5000]
        results = detect_langs(sample)
        return [r.lang for r in results[:max_languages] if r.prob > 0.1]
    except LangDetectException:
        return []
    except Exception as e:
        logger.warning("language_detection_failed", error=str(e))
        return []
