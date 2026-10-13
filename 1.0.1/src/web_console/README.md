# Web Console 测试文档

## 测试文件列表

| 文件 | 用途 | 依赖 | 状态 |
|------|------|------|------|
| `test_web_console.py` | FastAPI 后端 API 端点测试 | `fastapi`, `httpx` | 可用 |
| `server.py` | FastAPI 服务端实现 | `fastapi`, `jinja2`, `uvicorn` | 可用 |
| `templates/index.html` | Web 控制台前端页面 | 无 | 可用 |
| `static/style.css` | 前端样式表 | 无 | 可用 |
| `static/app.js` | 前端交互逻辑 | 无 | 可用 |

## 依赖清单

| 测试文件 | 依赖包 | 安装命令 |
|----------|--------|----------|
| `test_web_console.py` | `fastapi`, `httpx` | `pip install fastapi httpx` |
| `server.py` | `fastapi`, `jinja2`, `uvicorn` | `pip install fastapi jinja2 uvicorn` |

## 运行方法

### 运行服务端

```bash
conda activate vclaw
python src/l1/tests/web_console/server.py
```

服务启动后访问: http://localhost:8000/

### 运行测试

```bash
pytest src/l1/tests/web_console/test_web_console.py -v
```

### 运行全部 L1 测试

```bash
pytest src/l1/tests/ -v
```

## 注意事项

- L3 测试端点 (`/api/l3/test_react`, `/api/l3/test_security`) 和 E2E 对话端点 (`/api/e2e/chat`) 需要配置 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`，否则返回 503
- L6 代码执行测试 (`/api/l6/test_runtime`) 需要本地 Docker 环境，若 Docker 不可用可能返回 400/500
- E2E 测试使用真实 LLM，可能因 API 限流导致响应较慢
