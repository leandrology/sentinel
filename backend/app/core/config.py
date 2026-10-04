from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load root .env whether CWD is repo root (".env") or backend/ ("../.env").
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    simulator_url: str = "ws://localhost:8765"
    ingest_enabled: bool = False
    ingest_queue_size: int = 500
    ingest_workers: int = 4
    reconnect_base_s: float = 1.0
    reconnect_max_s: float = 30.0

    ai_provider: str = "mock"  # mock | gemini | deepseek | fallback
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    ai_timeout_s: float = 8.0
    ai_max_retries: int = 3
    ai_max_concurrent: int = 8

    video_source: str = ""
    video_sample_fps: float = 2.0
    video_preview_fps: float = 15.0
    video_file_realtime: bool = True
    video_motion_threshold: float = 25.0
    video_min_area: float = 500.0
    video_enabled: bool = False
    video_cooldown_s: float = 5.0
    video_site_id: str = "site-100"
    video_zone: str = "north-perimeter"
    video_upload_dir: str = "./data/uploads"
    video_max_mb: int = 100

    vision_provider: str = "mock"  # mock | gemini | twelvelabs | disabled
    vision_enabled: bool = True
    vision_cooldown_s: float = 10.0
    vision_max_concurrent: int = 2
    vision_timeout_s: float = 15.0
    google_ai_api_key: str = ""
    google_ai_model: str = "gemini-3.5-flash-lite"
    google_ai_base_url: str = "https://generativelanguage.googleapis.com"
    twelvelabs_api_key: str = ""
    twelvelabs_model: str = "marengo2.6"
    twelvelabs_base_url: str = "https://api.twelvelabs.io"

    corr_window_s: int = 300
    corr_threshold: int = 3

    database_url: str = "sqlite:///./sentinel.db"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
