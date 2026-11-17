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

    ai_enabled: bool = False
    ai_api_key: str = ""
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-flash"
    ai_timeout_seconds: float = 25.0
    ai_enable_thinking: bool | None = None

    # 查战绩（第三方站点）只由后端调用：token/账号密码只放服务端 .env。
    lzyumi_base_url: str = "https://l.lzyumi.top/lzyumi/lol/info"
    lzyumi_token: str = ""
    lzyumi_user: str = ""
    lzyumi_pwd: str = ""
    zj_min_interval_seconds: float = 2.5
    zj_batch_max_players: int = 10
    zj_batch_ttl_minutes: int = 30
    zj_cache_ttl_seconds: int = 300

    @property
    def using_dev_secret(self) -> bool:
        return self.jwt_secret == DEV_SECRET

    @property
    def ai_ready(self) -> bool:
        return bool(self.ai_enabled and self.ai_api_key.strip())

    @property
    def lzyumi_ready(self) -> bool:
        """有 token 或有能自动登录的账号密码，才算可用。"""
        return bool(
            self.lzyumi_token.strip()
            or (self.lzyumi_user.strip() and self.lzyumi_pwd.strip())
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
