from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from config.settings import Settings, get_settings
from modules.chat.router import router as chat_router
from modules.chat.service import ChatService


def create_app(config: Settings | None = None) -> FastAPI:
    config = config if config is not None else get_settings()
    chat_service = ChatService(config)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            await chat_service.close()

    api = FastAPI(title="Workbase AI Server", lifespan=lifespan)
    api.state.chat_service = chat_service
    api.include_router(chat_router)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if not config.server_base_path:
        return api

    application = FastAPI(
        docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    application.mount(config.server_base_path, api)
    return application


settings = get_settings()
app = create_app(settings)

# logger.debug("调试信息")
# logger.info("普通信息")
# logger.warning("警告")
# logger.error("出错了")
# logger.success("成功了")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
        log_level=settings.logging_level.lower(),
    )
