# Workbase AI Server

基于 Python、FastAPI、LangChain 和 LangGraph 的 AI 服务端项目，使用 uv 管理依赖，要求 Python >= 3.13。

## 安装与启动

```bash
uv sync
uv run python main.py
```

默认读取项目根目录的 `.env.local`，本地监听 `127.0.0.1:8000`，开启热更新。默认地址：

| 地址 | 用途 |
| --- | --- |
| http://127.0.0.1:8000/workbase-ai/health | 健康检查，返回 `{"status":"ok"}` |
| http://127.0.0.1:8000/workbase-ai/docs | Swagger UI |
| http://127.0.0.1:8000/workbase-ai/redoc | ReDoc |
| http://127.0.0.1:8000/workbase-ai/openapi.json | OpenAPI 定义 |

也可通过 Uvicorn 启动，此时监听地址、端口和热更新由命令行控制：

```bash
uv run uvicorn main:app --reload
```

## 环境配置

使用 `pydantic-settings` 读取 `.env` 格式文件及系统环境变量，不使用 YAML 或 PyYAML。

| 环境 | APP_ENV | 根目录配置文件 | 当前端口 | 热更新 |
| --- | --- | --- | --- | --- |
| 本地（默认） | local | `.env.local` | 8000 | 开启 |
| 测试 | test | `.env.test` | 9999 | 开启 |
| 预发 | staging | `.env.staging` | 9999 | 开启 |
| 生产 | production | `.env.production` | 9999 | 关闭 |

每次只读取所选环境文件，不合并其他文件。配置文件路径相对于项目根目录，不受启动工作目录影响。

```bash
# 本地环境
uv run python main.py

# 测试环境
APP_ENV=test uv run python main.py

# 预发环境
APP_ENV=staging uv run python main.py

# 生产环境
APP_ENV=production uv run python main.py
```

`.env.local` 配置格式如下；其他环境使用相同的字段名：

```dotenv
APP_SERVER_HOST=127.0.0.1
APP_SERVER_PORT=8000
APP_SERVER_RELOAD=true
APP_SERVER_BASE_PATH=/workbase-ai
APP_LOGGING_LEVEL=DEBUG

APP_MYSQL_HOST=127.0.0.1
APP_MYSQL_PORT=3306
APP_MYSQL_DATABASE=workbase_ai
APP_MYSQL_USERNAME=root
APP_MYSQL_PASSWORD=
APP_MYSQL_CHARSET=utf8mb4

APP_LLM_MODEL=
APP_LLM_API_KEY=
APP_LLM_BASE_URL=
```

现有 `.env.*` 文件保留在本机，并由 `.gitignore` 忽略；不提供 `.example` 文件。新环境可按上述字段创建文件，或者直接由部署平台注入系统环境变量。

配置优先级为：**系统环境变量 > 当前环境文件 > 字段默认值**。例如临时覆盖端口或模型配置：

```bash
APP_SERVER_PORT=8001 uv run python main.py

APP_LLM_MODEL='your-model-name' \
APP_LLM_API_KEY='your-api-key' \
APP_LLM_BASE_URL='https://ai.example.com/v1' \
uv run python main.py
```

变量名现使用单下划线，例如 `APP_SERVER_PORT`；旧的 `APP_SERVER__PORT` 等双下划线变量不再使用。`APP_ENV` 由启动环境设置，用于选择文件，不写入 `.env.*` 文件。

`config/settings.py` 中的 `Settings` 类统一声明配置类型，Pydantic 自动处理环境变量读取、类型转换和校验。新增配置时，添加对应字段及 `.env` 配置项即可，不需要编写解析或覆盖逻辑。无效环境名、缺失必填字段或不合法字段值会在启动时失败。如果部署平台已注入所有必填变量，可以不提供 `.env` 文件。

密码和 API Key 使用 `SecretStr`，常规打印和 JSON 序列化会脱敏；实际使用时读取原值：

```python
from config.settings import get_settings

settings = get_settings()
model = settings.llm_model
base_url = settings.llm_base_url
api_key = settings.llm_api_key.get_secret_value()
```

配置读取使用 `lru_cache` 缓存。修改 `.env` 或系统环境变量后需要重启进程；Python 代码的热更新由 `APP_SERVER_RELOAD` 控制。

MySQL 目前仅加载配置，不建立数据库连接。LLM 配置由聊天接口使用；允许留空以便健康检查启动，但配置不完整时聊天接口返回 503。

## 服务路径前缀

`APP_SERVER_BASE_PATH` 控制接口和文档的统一路径前缀，默认 `/workbase-ai`。支持 `/api/v1` 等多级路径，每段使用字母、数字、下划线或短横线；末尾斜线会移除。留空或设为 `/` 时不使用前缀。

```bash
APP_SERVER_BASE_PATH=/api/v1 uv run python main.py
APP_SERVER_BASE_PATH='' uv run python main.py
```

应用入口直接使用已校验的配置挂载 FastAPI 子应用，没有额外的路由配置模块。

## 聊天接口（SSE 流式响应）

`POST /workbase-ai/chat` 接收 JSON 消息，使用 LangChain `ChatOpenAI.astream()` 逐块生成回复，并通过 `sse-starlette` 返回 `text/event-stream`。前缀由 `APP_SERVER_BASE_PATH` 决定。供应商需要兼容 OpenAI Chat Completions 的流式协议，模型配置仍使用 `APP_LLM_MODEL`、`APP_LLM_API_KEY`、`APP_LLM_BASE_URL`。

```bash
curl -N -X POST http://127.0.0.1:8000/workbase-ai/chat \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"message":"你好，请介绍一下你自己"}'
```

响应示例，每个事件之间有一个空行：

```text
event: delta
data: {"content":"你好！"}

event: delta
data: {"content":"我是你的 AI 助手。"}

event: done
data: {}

```

| 事件 | data 内容 | 前端处理 |
| --- | --- | --- |
| delta | `{"content":"新增文本"}` | 追加文本到当前回复 |
| done | `{}` | 本次回复正常完成 |
| error | `{"code":504,"message":"大模型响应超时，请稍后重试"}` | 展示错误并结束接收，不会再发送 done |

文本块可能包含换行或引号，均通过 JSON 编码。每 15 秒发送 SSE 注释心跳，前端忽略即可；设置响应头关闭代理缓冲。如果部署的代理仍缓冲响应，还需要在代理侧关闭缓冲。

前端通过同域地址或开发代理使用 `fetch` 接收 POST 流。网络数据块不等于完整事件，必须保留未解析完的数据，不能直接对每次读取结果执行 `JSON.parse`：

```javascript
async function chat(message, onDelta, signal) {
  const response = await fetch('/workbase-ai/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(JSON.stringify(error.detail));
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  let reply = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw new Error('连接提前关闭，未收到完成事件');
      buffer = (buffer + value).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const lines = frame.split('\n');
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim();
        if (!event) continue; // 忽略注释心跳
        const data = JSON.parse(lines
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trimStart())
          .join('\n'));
        if (event === 'delta') {
          reply += data.content;
          onDelta(data.content);
        } else if (event === 'done') {
          return reply;
        } else if (event === 'error') {
          throw new Error(data.message);
        }
      }
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}

const controller = new AbortController();
const reply = await chat('你好', text => {
  console.log(text); // 追加到界面；不要覆盖此前已收到的文本
}, controller.signal);
// 用户点击停止时调用 controller.abort()；调用方可捕获 AbortError。
```

每次请求只发送一条消息，不保存聊天历史。去除首尾空白后的消息须为 1–20000 个字符。模型网络请求超时为 60 秒，不自动重试；向前端发送数据超过 30 秒未完成会断开连接。前端断开或取消请求时，后端关闭上游生成流；应用退出时关闭复用的模型客户端。

输入不合法时返回 HTTP 422，模型配置缺失时在发送流之前返回 HTTP 503。流开始后 HTTP 状态已固定为 200，供应商连接、鉴权等错误通过 `error` 事件的 `code: 502` 传递，超时使用 `code: 504`，上游未返回文本使用 `code: 502`。供应商错误原文和 API Key 不返回前端。健康检查不发起模型请求。

## 测试

```bash
uv run pytest
uv run pytest tests/test_settings.py tests/test_chat.py -v
```

测试覆盖 `.env` 环境选择、系统变量覆盖、类型转换、必填字段和端口校验、密钥脱敏、配置缓存、路径前缀及健康检查。聊天测试通过模拟上游 HTTP 服务，覆盖内容转发、分块事件、完成事件、输入校验、错误脱敏、中途超时、断线取消与客户端关闭。测试使用临时 `.env.local` 并隔离 `APP_` 环境变量，不读取本机真实密钥，也不依赖 MySQL 或模型服务。

## 目录

```text
.
├── main.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── .env.local
├── .env.test
├── .env.staging
├── .env.production
├── modules/
│   └── chat/         # 聊天路由、请求响应模型及 LangChain 调用服务
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```

已通过 LangChain 实现 SSE 流式单次聊天；LangGraph 工作流、聊天历史及持久化尚未实现。
