# Workbase AI Server

基于 Python、FastAPI、LangChain 和 LangGraph 的 AI 服务端项目

## 当前状态

截至 2026-11-05，仓库处于初始化阶段：

- 已使用 `uv` 管理依赖，通过 `uv.lock` 锁定依赖版本。
- `main.py` 已提供最小 FastAPI 应用及 `GET /health` 健康检查接口。
- 开发启动支持热更新，提供 Swagger UI 和 ReDoc 接口文档。
- LangChain、LangGraph 等依赖已声明，业务模块、AI 调用、持久化和测试设施尚未实现。

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
uv run uvicorn main:app --reload
```

`--reload` 开启热更新：保存 Python 文件后，服务会自动重启并加载修改。启动日志出现 `Application startup complete.` 表示应用启动完成。按 `Ctrl+C` 停止服务。

也可以通过 Python 入口启动，入口已配置 `reload=True`，同样开启热更新：

```bash
uv run python main.py
```

热更新仅用于开发环境。

### 访问与验证

默认监听 `127.0.0.1:8000`：

| 路径 | 用途 |
| --- | --- |
| [健康检查](http://127.0.0.1:8000/health) | 返回 `{"status":"ok"}` |
| [Swagger UI](http://127.0.0.1:8000/docs) | 交互式 API 文档 |
| [ReDoc](http://127.0.0.1:8000/redoc) | API 参考文档 |
| [OpenAPI](http://127.0.0.1:8000/openapi.json) | 接口定义 |

另开一个终端验证服务：

```bash
curl http://127.0.0.1:8000/health
```

根路径 `/` 暂未定义接口，访问时返回 404 属于正常情况。

如果 8000 端口已被占用，可以指定其他端口并保留热更新：

```bash
uv run uvicorn main:app --reload --port 8001
```

## 当前目录

```text
.
├── main.py          # FastAPI 应用、健康检查和开发启动入口
├── pyproject.toml   # 项目元数据、依赖和 uv 源配置
├── uv.lock          # 依赖锁定文件
├── .python-version # 开发使用的 Python 版本
├── .gitignore      # 本地配置、缓存等忽略规则
└── README.md
```

`config/` 和 `docs/` 当前为空，后续按实际实现补充配置和架构文档。
