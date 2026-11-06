import json
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from modules.chat.schemas import ChatRequest
from modules.chat.service import ChatService

router = APIRouter(prefix="/chat", tags=["聊天"])


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.post(
    "",
    response_class=EventSourceResponse,
    summary="发送消息并流式接收大模型回复",
    responses={200: {
        "description": "SSE 事件流：delta 为新增文本，done 为完成，error 为失败",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }},
)
async def chat(
    body: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> EventSourceResponse:
    stream = service.stream_reply(body.message)

    async def events():
        try:
            async with aclosing(stream):
                async for text in stream:
                    yield {"event": "delta", "data": json.dumps({"content": text}, ensure_ascii=False)}
        except HTTPException as error:
            # SSE 开始后不能修改 HTTP 状态，通过 error 事件通知前端。
            yield {"event": "error", "data": json.dumps({
                "code": error.status_code, "message": error.detail,
            }, ensure_ascii=False)}
        except Exception:
            yield {"event": "error", "data": json.dumps({
                "code": 502, "message": "大模型服务调用失败，请稍后重试",
            }, ensure_ascii=False)}
        else:
            yield {"event": "done", "data": "{}"}

    return EventSourceResponse(
        events(),
        ping=15,
        send_timeout=30,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
