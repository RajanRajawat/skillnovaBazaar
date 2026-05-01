from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from .config.settings import settings
    from .routes.auth import router as auth_router
    from .routes.api import router as api_router
    from .services.auth import auth_middleware
except ImportError:
    from config.settings import settings
    from routes.auth import router as auth_router
    from routes.api import router as api_router
    from services.auth import auth_middleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="SkillNova Bazaar",
        debug=settings.debug,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(auth_middleware)
    app.include_router(auth_router, prefix="/api")
    app.include_router(api_router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "SkillNova Bazaar API",
            "status": "ok",
            "docs": "/api/docs",
            "health": "/api/health",
        }

    @app.exception_handler(Exception)
    async def server_error(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"error": "Server error", "detail": str(error)}, status_code=500)
    return app


app = create_app()


def main() -> None:
    print(f"SkillNova Bazaar running at http://{settings.host}:{settings.port}")
    module_name = f"{__package__}.app" if __package__ else "app"
    uvicorn.run(f"{module_name}:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    main()
