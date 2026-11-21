import argparse
import logging
from collections.abc import Sequence

from pathlib import Path

from fastapi import FastAPI

from src.infraestructure.api_router.collection_router import router as collection_router
from src.infraestructure.api_router.item_collection_router import router as item_collection_router
from src.infraestructure.api_router.openapi import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    LICENSE_INFO,
    OPENAPI_TAGS,
    openapi_json,
)
from src.infraestructure.api_router.user_router import router as user_router
from src.infraestructure.bootstrap.lifespan import build_lifespan
from src.infraestructure.persistence.database_provider import DatabaseSettings


def create_app(database_settings: DatabaseSettings | None = None) -> FastAPI:
    """
    Application factory. ``database_settings`` chooses the database explicitly. If it is None, the
    database is read from the DATABASE_* / POSTGRES_* environment variables at startup.
    """
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        license_info=LICENSE_INFO,
        lifespan=build_lifespan(database_settings),
    )
    app.include_router(user_router)
    app.include_router(item_collection_router)
    app.include_router(collection_router)

    @app.get("/", tags=["status"], summary="Check the service is running")
    def main():
        return {"message": "Hello World"}

    return app


# Used by `fastapi dev` / `uvicorn main:app`: the database comes from environment variables.
app = create_app()


def export_openapi(path: Path) -> None:
    """
    Writes the OpenAPI spec of the application to ``path`` (docs/openapi.json in the repository).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(openapi_json(app), encoding="utf-8")


def parse_startup_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the collector evaluator API.")
    parser.add_argument("--database-url", help="PostgreSQL URL, e.g. postgresql://user:pass@host:5432/db")
    parser.add_argument("--database-name", help="database to use on the configured PostgreSQL server")
    parser.add_argument("--no-memory-fallback", action="store_true",
                        help="fail at startup instead of using an in-memory database if PostgreSQL is unavailable")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--export-openapi", metavar="PATH", type=Path,
                        help="write the OpenAPI spec (e.g. docs/openapi.json) and exit, without starting the server")
    return parser.parse_args(argv)


def database_settings_from_args(args: argparse.Namespace) -> DatabaseSettings:
    # Only pass the arguments that were given, so environment variables still apply to the rest.
    overrides = {}
    if args.database_url:
        overrides["url"] = args.database_url
    if args.database_name:
        overrides["name"] = args.database_name
    if args.no_memory_fallback:
        overrides["fallback_to_memory"] = False
    return DatabaseSettings(**overrides)


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    startup_args = parse_startup_args()
    if startup_args.export_openapi:
        export_openapi(startup_args.export_openapi)
        print(f"OpenAPI spec written to {startup_args.export_openapi}")
        raise SystemExit(0)
    uvicorn.run(create_app(database_settings_from_args(startup_args)), host=startup_args.host, port=startup_args.port)
