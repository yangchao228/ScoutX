from __future__ import annotations

from fastapi import FastAPI

from apps.content_service.api.routes_contents import router as contents_router
from apps.content_service.api.routes_health import router as health_router
from apps.content_service.api.routes_public_feed import router as public_feed_router
from apps.content_service.api.routes_sources import router as sources_router
from apps.content_service.api.routes_subscriptions import router as subscriptions_router
from apps.content_service.settings import load_settings


def create_app() -> FastAPI:
    app_settings = load_settings()
    app = FastAPI(
        title="Content Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": app_settings.app_name,
            "version": "0.1.0",
            "status": "ok",
            "public_feed_url": f"{app_settings.public_base_url}/v1/public/feed",
        }

    app.include_router(health_router, dependencies=[], responses={})
    app.include_router(contents_router)
    app.include_router(public_feed_router)
    app.include_router(sources_router)
    app.include_router(subscriptions_router)
    return app


app = create_app()


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - local bootstrap convenience
        raise SystemExit(
            "uvicorn is not installed. Install apps/content_service/requirements.txt first."
        ) from exc

    runtime_settings = load_settings()
    uvicorn.run(
        "apps.content_service.main:app",
        host=runtime_settings.host,
        port=runtime_settings.port,
        reload=True,
    )
