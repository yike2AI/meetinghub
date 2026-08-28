from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    glm_api_key: str = ""
    deepseek_api_key: str = ""
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meetinghub"
    redis_url: str = "redis://localhost:6379/0"
    confirm_timeout_minutes: int = 5
    anthropic_base_url: str = "https://open.bigmodel.cn/api/anthropic"
    anthropic_auth_token: str = ""
    anthropic_model: str = "glm-5.1"
    frontend_url: str = "http://localhost:5173"
    data_dir: Path = ROOT / "data"
    models_yaml: Path = ROOT / "models.yaml"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "raw").mkdir(exist_ok=True)
(settings.data_dir / "tmp").mkdir(exist_ok=True)
