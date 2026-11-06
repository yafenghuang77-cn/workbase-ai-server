from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError

from config.settings import Settings


class ChatService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: ChatOpenAI | None = None

    def _get_model(self) -> ChatOpenAI:
        if self._model is None:
            settings = self._settings
            if not all((
                settings.llm_model.strip(),
                settings.llm_api_key.get_secret_value().strip(),
                settings.llm_base_url.strip(),
            )):
                raise HTTPException(status_code=503, detail="大模型配置不完整，请检查 LLM 配置")
            # 复用客户端；仅在首次聊天时初始化，健康检查不依赖模型配置。
            self._model = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=60,
                max_retries=0,
                use_responses_api=False,
            )
        return self._model

    def stream_reply(self, message: str) -> AsyncIterator[str]:
        # 发送 SSE 响应头前检查配置，配置缺失仍返回 HTTP 503。
        model = self._get_model()

        async def generate() -> AsyncIterator[str]:
            has_text = False
            try:
                # 前端断开或生成器关闭时，同时关闭 LangChain 的上游流。
                async with aclosing(model.astream([HumanMessage(content=message)])) as stream:
                    async for chunk in stream:
                        text = chunk.text
                        if text:
                            has_text = has_text or bool(text.strip())
                            yield text
            except APITimeoutError:
                raise HTTPException(status_code=504, detail="大模型响应超时，请稍后重试") from None
            except (APIConnectionError, APIStatusError, ValueError):
                raise HTTPException(status_code=502, detail="大模型服务调用失败，请稍后重试") from None
            if not has_text:
                raise HTTPException(status_code=502, detail="大模型未返回文本回复")

        return generate()

    async def close(self) -> None:
        if self._model is not None:
            await self._model.root_async_client.close()
            self._model.root_client.close()
            self._model = None
