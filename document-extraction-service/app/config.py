from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_keys: str = ""
    max_upload_size: int = 100 * 1024 * 1024  # 100MB
    tesseract_cmd: str | None = None
    log_level: str = "info"

    @property
    def api_key_list(self) -> list[str]:
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
