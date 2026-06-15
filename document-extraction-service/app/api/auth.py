from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Validate API key from X-API-Key header."""
    allowed_keys = settings.api_key_list
    if not allowed_keys:
        # No keys configured — allow all requests (dev mode)
        return "dev"
    if not api_key or api_key not in allowed_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
