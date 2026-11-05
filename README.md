# Workbase AI Server

基于 Python、FastAPI、LangChain 和 LangGraph 的 AI 服务端项目

## 当前状态

截至 2026-11-05，仓库处于初始化阶段：

- 已使用 `uv` 管理依赖，通过 `uv.lock` 锁定依赖版本。
- `main.py` 已提供 FastAPI 应用及健康检查接口，默认访问路径为 `GET /workbase-ai/health`。
- 开发启动支持热更新，提供 Swagger UI 和 ReDoc 接口文档。
- 已提供本地、测试、预发和生产 YAML 配置，支持通过 `APP_ENV` 选择环境及系统环境变量覆盖配置。
- 支持配置服务路径前缀；YAML 新增字段会自动加载，无需逐个修改配置模型。
- MySQL 已支持配置加载与校验，尚未安装数据库驱动或实现连接。
- LangChain、LangGraph 等依赖已声明，业务模块、AI 调用和持久化尚未实现；配置加载已有单元测试。

## 本地开发与启动

### 环境准备

- 安装 `uv`。
- 使用 Python 3.13（`.python-version` 指定的开发版本；项目要求 Python >= 3.13）。
- 以下命令均在仓库根目录执行。

当前健康检查接口不依赖数据库、外部 AI 服务或 API Key，无需创建 `.env` 即可启动。

### 安装依赖

```bash
uv sync
```

该命令会根据 `uv.lock` 安装依赖到 `.venv`，无需手动激活虚拟环境。如果依赖声明发生变化，uv 会按需更新锁文件。

### 启动开发服务（开启热更新）

```bash
uv run python main.py
```

默认使用 `local` 环境，从 `config/local.yaml` 读取启动参数，其中 `server.reload: true` 开启热更新。保存 Python 文件后，服务会自动重启并加载修改。启动日志出现 `Application startup complete.` 表示应用启动完成。按 `Ctrl+C` 停止服务。

也可以直接使用 Uvicorn 命令，此时监听地址、端口和热更新由命令行参数控制：

```bash
uv run uvicorn main:app --reload
```

使用 Python 入口时，热更新由所选 YAML 的 `server.reload` 控制。本地开发保持 `true`；生产部署前应将 `config/production.yaml` 的 `server.reload` 设置为 `false`。

### 根据环境启动

在仓库根目录使用以下命令（适用于 macOS/Linux 的 zsh、bash 等 Shell）：

```bash
# 默认启动本地环境，加载 config/local.yaml，开启热更新
uv run python main.py

# 显式指定本地环境
APP_ENV=local uv run python main.py

# 测试环境
APP_ENV=test uv run python main.py

# 预发环境
APP_ENV=staging uv run python main.py

# 生产环境
APP_ENV=production uv run python main.py
```

当前配置值如下，启动命令本身不会自动更改端口或热更新开关：

| 环境 | `APP_ENV` | 配置文件 | 监听地址 | 热更新 |
| --- | --- | --- | --- | --- |
| 本地（默认） | `local` | `config/local.yaml` | `127.0.0.1:8000` | 开启 |
| 测试 | `test` | `config/test.yaml` | `127.0.0.1:9999` | 开启 |
| 预发 | `staging` | `config/staging.yaml` | `127.0.0.1:9999` | 开启 |
| 生产 | `production` | `config/production.yaml` | `127.0.0.1:9999` | 开启（部署前关闭） |

测试、预发和生产当前使用相同端口，在同一台机器上同时启动时需指定不同端口。例如：

```bash
APP_ENV=test APP_SERVER__PORT=9001 uv run python main.py
```

四个环境的路径前缀当前均为 `/workbase-ai`。默认启动及环境切换已验证，服务启动后 `/workbase-ai/health` 和接口文档可访问。服务验证临时使用环境变量覆盖端口，以避免占用已有服务端口；表中的 YAML 原始端口已单独核对。

### 访问与验证

默认监听 `127.0.0.1:8000`：

| 路径 | 用途 |
| --- | --- |
| [健康检查](http://127.0.0.1:8000/workbase-ai/health) | 返回 `{"status":"ok"}` |
| [Swagger UI](http://127.0.0.1:8000/workbase-ai/docs) | 交互式 API 文档 |
| [ReDoc](http://127.0.0.1:8000/workbase-ai/redoc) | API 参考文档 |
| [OpenAPI](http://127.0.0.1:8000/workbase-ai/openapi.json) | 接口定义 |

另开一个终端验证服务：

```bash
curl http://127.0.0.1:8000/workbase-ai/health
```

根路径 `/` 暂未定义接口，访问时返回 404 属于正常情况。

如果 8000 端口已被占用，可以指定其他端口并保留热更新：

```bash
APP_SERVER__PORT=8001 uv run python main.py
```

### 服务路径前缀

通过各环境 YAML 的 `server.base_path` 配置类似前端 basename 的统一访问前缀。当前值为 `/workbase-ai`，接口和 Swagger、ReDoc、OpenAPI 文档都位于该路径下；未带前缀的 `/health`、`/docs` 等路径返回 404。业务路由仍写 `/health`，应用工厂通过挂载整个应用统一添加前缀。

`base_path` 可使用多级路径，例如 `/api/v1`。非空值须以 `/` 开头，每段只包含字母、数字、下划线或短横线，末尾的 `/` 会自动去掉。设为 `""`、`/` 或省略该字段时，不使用前缀。

可以通过环境变量临时覆盖，无需修改 YAML：

```bash
# 使用 /api/v1/health、/api/v1/docs 等地址
APP_SERVER__BASE_PATH=/api/v1 uv run python main.py

# 关闭前缀，使用 /health、/docs 等地址
APP_SERVER__BASE_PATH='' uv run python main.py
```

### 本地配置

每个环境只加载一个完整的 YAML 文件，不合并公共配置。未设置 `APP_ENV` 时使用 `local`，也可以显式指定：

```bash
APP_ENV=local uv run python main.py
```

当前 `config/local.yaml`：

```yaml
server:
  host: 127.0.0.1
  port: 8000
  reload: true
  base_path: /workbase-ai

logging:
  level: DEBUG

mysql:
  host: 127.0.0.1
  port: 3306
  database: workbase_ai
  username: root
  password: ""
  charset: utf8mb4
```

配置优先级为：**系统环境变量 > 当前环境 YAML**。嵌套字段使用 `APP_` 前缀和双下划线，例如 `APP_SERVER__PORT`、`APP_LOGGING__LEVEL`。已有的启动、日志和 MySQL 字段保留 Pydantic 校验，端口必须在 1–65535 之间；日志级别使用大写。

YAML 中新增的顶层配置节、嵌套字段和列表会自动保留，不需要在 `settings.py` 中逐个声明。例如添加：

```yaml
redis:
  host: localhost
  port: 6379
  tls:
    enabled: false
```

即可在代码中读取：

```python
from config.settings import get_settings

settings = get_settings()
settings.redis.host
settings.redis.tls.enabled
settings["redis"]["port"]
```

字段名与配置对象的方法重名时，使用方括号读取。已有配置节也可以直接添加新字段，例如 `mysql.pool.size`。新增字段保留 YAML 的值类型，不自动附加业务校验；需要特定规则时再为对应字段补充校验。

新增字段同样支持环境变量，例如 `APP_REDIS__PORT=6380`、`APP_REDIS__TLS__ENABLED=true`。环境变量会保留 YAML 中已有字符串字段的字符串类型；其他值尝试按 JSON 解析数字、布尔值、列表或对象，无法解析时作为字符串。更具体的嵌套变量会覆盖同一配置节的 JSON 对象变量。

不自动读取 `.env`。密钥通过系统环境变量注入，不写入 YAML 或提交到仓库。修改 YAML 或环境变量后需手动重启服务；Python 代码修改会自动重启。

MySQL 配置目前仅加载并校验，不建立连接、创建数据库或执行 SQL，因此无需运行 MySQL 即可启动服务。上述数据库名和用户名为本地配置初始值，可按需修改；空密码为占位值，真实密码通过 `APP_MYSQL__PASSWORD` 注入。其他字段同样支持环境变量覆盖，例如：

```bash
APP_MYSQL__HOST=127.0.0.1 APP_MYSQL__PORT=3307 uv run python main.py
```

`mysql.password` 使用 `SecretStr` 保存，配置对象的常规打印及 JSON 序列化会隐藏该字段。自动加载的新增字段不自动识别为密钥，避免打印包含敏感字段的完整配置。

环境名支持 `local`、`test`、`staging`、`production`，四个环境文件均已填写。环境名无效、配置文件缺失、为空或字段不合法时，启动会报错。

### 运行测试

使用 pytest 运行配置测试和健康检查接口测试。`uv sync` 默认安装测试所需的开发依赖 `pytest` 和 `httpx`。

```bash
uv run pytest
```

配置测试覆盖默认环境、环境变量覆盖、环境选择、字段校验、密码隐藏和动态新增字段。测试通过 fixture 使用独立的临时 YAML 文件，隔离 `APP_` 环境变量和配置缓存，不依赖本机 `local.yaml` 的具体内容。接口测试使用 FastAPI TestClient，验证有前缀和无前缀时的健康检查与文档地址，无需单独启动服务或连接 MySQL。

只运行配置测试或查看详细结果：

```bash
uv run pytest tests/test_settings.py -v
```

## 当前目录

```text
.
├── main.py          # FastAPI 应用、健康检查和开发启动入口
├── config/
│   ├── settings.py  # 配置模型、环境选择及加载逻辑
│   ├── local.yaml   # 本地开发配置，开启热更新
│   ├── test.yaml    # 测试环境配置
│   ├── staging.yaml # 预发环境配置
│   └── production.yaml # 生产环境配置
├── tests/           # pytest fixture、配置加载和健康检查接口测试
├── pyproject.toml   # 项目元数据、依赖和 uv 源配置
├── uv.lock          # 依赖锁定文件
├── .python-version # 开发使用的 Python 版本
├── .gitignore      # 本地配置、缓存等忽略规则
└── README.md
```

`docs/` 当前为空，后续按实际实现补充架构文档。
