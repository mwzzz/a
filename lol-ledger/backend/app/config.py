"""运行配置。全部可通过环境变量覆盖，方便 systemd 注入。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

DEV_SECRET = "dev-only-secret-please-change-me-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LOL 记录管理"
    db_path: Path = BASE_DIR / "data" / "ledger.db"
    jwt_secret: str = DEV_SECRET
    token_ttl_hours: int = 12
    debug: bool = False
    cors_origins: str = "http://localhost:5173"

    @property
    def using_dev_secret(self) -> bool:
        return self.jwt_secret == DEV_SECRET

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
