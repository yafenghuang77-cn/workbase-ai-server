from fastapi import FastAPI
from loguru import logger

from config.settings import Settings, get_settings


def create_app(config: Settings | None = None) -> FastAPI:
    config = config if config is not None else get_settings()
    api = FastAPI(title="Workbase AI Server")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if not config.server.base_path:
        return api

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    application.mount(config.server.base_path, api)
    return application


settings = get_settings()
app = create_app(settings)

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告")
logger.error("出错了")
logger.success("成功了")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        log_level=settings.logging.level.lower(),
    )
