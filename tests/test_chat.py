import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_openai import ChatOpenAI

import modules.chat.service as chat_service_module


def read_events(response):
    events = []
    for block in response.text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def upstream(monkeypatch):
    monkeypatch.setenv("APP_LLM_MODEL", "test-model")
    monkeypatch.setenv("APP_LLM_API_KEY", "test-secret")
    monkeypatch.setenv("APP_LLM_BASE_URL", "https://model.test/v1")
    state = {
        "requests": [], "status": 200,
        "chunks": ["你好，", "我能帮你什么？"],
        "stream_closed": False,
    }

    class StreamingBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            for index, text in enumerate(state["chunks"]):
                chunk = {
                    "id": "test-completion", "object": "chat.completion.chunk",
                    "model": "test-model",
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
                if index == 0 and state.get("midstream_timeout"):
                    raise httpx.ReadTimeout("private test-secret")
                if state.get("hold_open"):
                    await asyncio.Event().wait()
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            state["stream_closed"] = True

    def handle(request):
        state["requests"].append(request)
        if state.get("timeout"):
            raise httpx.ReadTimeout("private test-secret", request=request)
        if state["status"] != 200:
            return httpx.Response(state["status"], json={
                "error": {"message": "private test-secret", "type": "api_error"},
            })
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=StreamingBody())

    def create_model(**kwargs):
        state["async_client"] = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        state["sync_client"] = httpx.Client(transport=httpx.MockTransport(handle))
        return ChatOpenAI(
            **kwargs, http_async_client=state["async_client"], http_client=state["sync_client"],
        )

    monkeypatch.setattr(chat_service_module, "ChatOpenAI", create_model)
    return state


def test_chat_streams_user_content_and_completes(upstream, client):
    response = client.post("/chat", json={"message": "  你好  "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"
    assert read_events(response) == [
        ("delta", {"content": "你好，"}),
        ("delta", {"content": "我能帮你什么？"}),
        ("done", {}),
    ]
    request = upstream["requests"][0]
    assert str(request.url) == "https://model.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-secret"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["stream"] is True
    assert body["messages"] == [{"role": "user", "content": "你好"}]
    assert upstream["stream_closed"]
    assert "test-secret" not in response.text


def test_stream_preserves_multiline_text_and_skips_empty_chunks(upstream, client):
    upstream["chunks"] = ["", "第一行\n第二行", "\"引用\"", ""]

    assert read_events(client.post("/chat", json={"message": "你好"})) == [
        ("delta", {"content": "第一行\n第二行"}),
        ("delta", {"content": '"引用"'}),
        ("done", {}),
    ]


@pytest.mark.parametrize("message", ["", "  ", "x" * 20001, None, 123])
def test_invalid_message_does_not_call_model(upstream, client, message):
    assert client.post("/chat", json={"message": message}).status_code == 422
    assert not upstream["requests"]


def test_rejects_client_supplied_api_configuration(upstream, client):
    response = client.post("/chat", json={"message": "你好", "api_key": "client-key"})
    assert response.status_code == 422
    assert not upstream["requests"]


def test_missing_configuration_returns_http_error_before_stream(client):
    response = client.post("/chat", json={"message": "你好"})
    assert response.status_code == 503
    assert response.json()["detail"] == "大模型配置不完整，请检查 LLM 配置"


@pytest.mark.parametrize("status", [401, 429, 500])
def test_upstream_errors_are_sanitized_sse_events(upstream, client, status):
    upstream["status"] = status
    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 200
    assert read_events(response) == [("error", {"code": 502, "message": "大模型服务调用失败，请稍后重试"})]
    assert "test-secret" not in response.text
    assert "private" not in response.text
    assert len(upstream["requests"]) == 1


def test_timeout_is_reported_as_sse_error(upstream, client):
    upstream["timeout"] = True
    response = client.post("/chat", json={"message": "你好"})

    assert read_events(response) == [("error", {"code": 504, "message": "大模型响应超时，请稍后重试"})]
    assert "private" not in response.text


def test_midstream_failure_closes_upstream_and_does_not_emit_done(upstream, client):
    upstream["midstream_timeout"] = True
    response = client.post("/chat", json={"message": "你好"})

    assert read_events(response) == [
        ("delta", {"content": "你好，"}),
        ("error", {"code": 504, "message": "大模型响应超时，请稍后重试"}),
    ]
    assert upstream["stream_closed"]


def test_empty_model_reply_emits_error(upstream, client):
    upstream["chunks"] = [""]
    response = client.post("/chat", json={"message": "你好"})

    assert read_events(response) == [("error", {"code": 502, "message": "大模型未返回文本回复"})]


@pytest.mark.parametrize("prefix", ["", "/workbase-ai"])
def test_chat_respects_prefix_and_closes_clients(upstream, monkeypatch, prefix):
    monkeypatch.setenv("APP_SERVER_BASE_PATH", prefix)
    from main import create_app

    with TestClient(create_app()) as client:
        assert read_events(client.post(f"{prefix}/chat", json={"message": "你好"}))[-1] == ("done", {})
        operation = client.get(f"{prefix}/openapi.json").json()["paths"]["/chat"]["post"]
        assert "text/event-stream" in operation["responses"]["200"]["content"]
        if prefix:
            assert client.post("/chat", json={"message": "你好"}).status_code == 404

    assert upstream["async_client"].is_closed
    assert upstream["sync_client"].is_closed


def test_disconnect_cancels_and_closes_upstream(upstream):
    # 在首个 delta 到达时断开，不等待模型生成结束。
    upstream["hold_open"] = True

    async def run():
        from main import create_app
        app = create_app()
        disconnected = asyncio.Event()
        body_sent = False
        received = []

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": b'{"message":"hello"}', "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                received.append(message.get("body", b""))
                if b"event: delta" in message.get("body", b""):
                    disconnected.set()

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/chat", "raw_path": b"/chat", "root_path": "", "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "server": ("test", 80), "client": ("test", 1234),
        }
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(app(scope, receive, send), timeout=3)
        assert disconnected.is_set()
        assert b"event: done" not in b"".join(received)
        assert b"event: error" not in b"".join(received)

    asyncio.run(run())
    assert upstream["stream_closed"]
