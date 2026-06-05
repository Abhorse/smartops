from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.latest_app_version,
        docs_url="/docs",
        openapi_url="/api/v1/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_version_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-API-Version"] = "1"
        response.headers["X-Min-Supported-App-Version"] = settings.min_supported_app_version
        response.headers["X-Latest-App-Version"] = settings.latest_app_version
        return response

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
