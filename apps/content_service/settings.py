from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ContentServiceSettings:
    app_name: str = "content-service"
    app_env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 9100
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/content_service"
    api_token: str = ""
    default_page_size: int = 50
    max_page_size: int = 200
    public_base_url: str = "http://127.0.0.1:9100"
    public_feed_default_limit: int = 100
    public_feed_default_hours: int = 72
    public_feed_cache_ttl_seconds: int = 300
    slow_source_threshold_ms: int = 15000


def load_settings() -> ContentServiceSettings:
    return ContentServiceSettings(
        app_name=os.getenv("CONTENT_SERVICE_APP_NAME", "content-service"),
        app_env=os.getenv("CONTENT_SERVICE_APP_ENV", "dev"),
        host=os.getenv("CONTENT_SERVICE_HOST", "127.0.0.1"),
        port=int(os.getenv("CONTENT_SERVICE_PORT", "9100")),
        database_url=os.getenv(
            "CONTENT_SERVICE_DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:5432/content_service",
        ),
        api_token=os.getenv("CONTENT_SERVICE_API_TOKEN", ""),
        default_page_size=int(os.getenv("CONTENT_SERVICE_DEFAULT_PAGE_SIZE", "50")),
        max_page_size=int(os.getenv("CONTENT_SERVICE_MAX_PAGE_SIZE", "200")),
        public_base_url=os.getenv("CONTENT_SERVICE_PUBLIC_BASE_URL", "http://127.0.0.1:9100").rstrip("/"),
        public_feed_default_limit=int(os.getenv("CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_LIMIT", "100")),
        public_feed_default_hours=int(os.getenv("CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_HOURS", "72")),
        public_feed_cache_ttl_seconds=int(os.getenv("CONTENT_SERVICE_PUBLIC_FEED_CACHE_TTL_SECONDS", "300")),
        slow_source_threshold_ms=int(os.getenv("CONTENT_SERVICE_SLOW_SOURCE_THRESHOLD_MS", "15000")),
    )
