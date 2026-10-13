# L1 层测试文件说明

本文档说明 `src/l1/tests/` 目录下各个测试文件的用途、依赖和运行方法，需要实时更新。

## 测试文件列表

### 单元测试

| 文件 | 用途 | 依赖 | 状态 |
|------|------|------|------|
| `test_l1_basic.py` | L1基础功能单元测试 | 无(标准库+项目代码) | 稳定 |
| `test_adapters.py` | ProtocolAdapter 适配器测试 | 无(标准库+项目代码) | 稳定 |
| `test_validator.py` | DataValidator 数据验证测试 | 无(标准库+项目代码) | 稳定 |
| `test_normalizer.py` | EventNormalizer 事件规范化测试 | 无(标准库+项目代码) | 稳定 |
| `test_error_handler.py` | ErrorHandler 错误处理测试 | 无(标准库+项目代码) | 稳定 |
| `test_integration.py` | L1内部组件集成测试 | 无(标准库+项目代码) | 稳定 |
| `test_l1_comprehensive.py` | L1综合测试套件 | 无(标准库+项目代码) | 稳定 |
| `test_adapters_manual.py` | 手动测试三个适配器(无需网络) | 无(标准库+项目代码) | 稳定 |
| `test_adapter_output_comparison.py` | 对比三种适配器输出结构一致性 | 无(标准库+项目代码) | 稳定 |
| `test_error_handler_business.py` | ErrorHandler 业务错误路由测试 | 无(标准库+项目代码) | 稳定 |
| `test_error_handler_protocol.py` | ErrorHandler 协议格式化 + 重试边界测试 | 无(标准库+项目代码) | 稳定 |
| `test_response_sender.py` | send_response 路径和上下文映射测试 | 无(标准库+项目代码) | 稳定 |
| `test_adapter_edge_cases.py` | Adapter/Validator/EventNormalizer 边界测试 | 无(标准库+项目代码) | 稳定 |

### 真实环境测试

| 文件 | 用途 | 依赖 | 运行环境 |
|------|------|------|----------|
| `test_telegram_polling.py` | 轮询模式真实Telegram消息测试 | `python-telegram-bot` | 本地环境(需网络) |
| `test_telegram_webhook.py` | Telegram Webhook模式测试(需公网IP/ngrok) | `python-telegram-bot`, `fastapi`, `uvicorn` | 生产环境 |
| `test_websocket_server.py` | WebSocket服务端测试(浏览器/Postman连接) | `websockets` | 本地环境 |
| `test_webhook_server.py` | HTTP Webhook服务端测试(curl/浏览器) | `fastapi`, `uvicorn` | 本地环境 |
| `test_l1_to_l2_flow.py` | L1→L2集成测试(验证数据流转换) | `python-telegram-bot` | 本地环境(需网络) |
| `test_l1_l2_contract.py` | L1-L2接口契约测试 | 无(标准库+项目代码) | 本地环境 |

## 测试依赖清单

### 安装所有测试依赖

```bash
# 基础依赖(运行单元测试)
pip install pytest

# L1真实环境测试依赖
pip install python-telegram-bot websockets fastapi uvicorn python-dotenv
```

### 配置 .env 文件

**所有真实环境测试都需要从 .env 文件读取配置**，请在项目根目录创建 `.env` 文件：

```bash
# 在项目根目录创建 .env 文件
touch .env

# 编辑 .env 文件，添加以下内容：
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

**注意**: `.env` 文件已被 `.gitignore` 排除，不会提交到Git仓库。

### 各测试文件依赖详情

| 测试文件 | 依赖包 | 安装命令 |
|----------|--------|----------|
| `test_telegram_polling.py` | `python-telegram-bot` | `pip install python-telegram-bot` |
| `test_telegram_webhook.py` | `python-telegram-bot`, `fastapi`, `uvicorn` | `pip install python-telegram-bot fastapi uvicorn` |
| `test_websocket_server.py` | `websockets` | `pip install websockets` |
| `test_webhook_server.py` | `fastapi`, `uvicorn` | `pip install fastapi uvicorn` |
| `test_l1_to_l2_flow.py` | `python-telegram-bot` | `pip install python-telegram-bot` |
| 其他单元测试 | 无额外依赖 | - |

## 会话管理测试

会话管理测试位于 `test_l1_basic.py` 中的 `TestSessionManagement` 类。

### 会话创建流程

L1 层负责管理 `user_id` -> `session_id` 的映射关系：

```
第1次请求 (用户首次发言)
  │
  ▼
L1: 无现有映射 → metadata["session_id"] = None
  │
  ▼
L2: 创建新 session_id (例如: "abc-123")
  │
  ▼
L1: 保存映射 user_id -> "abc-123" (update_session_mapping)

第2次请求 (同用户再次发言)
  │
  ▼
L1: 找到映射 → metadata["session_id"] = "abc-123"
  │
  ▼
L2: 复用 session_id "abc-123" (同一对话)

/new 命令 (用户主动新建会话)
  │
  ▼
L1: 识别命令 → 清除映射 → metadata["session_id"] = None
  │
  ▼
L2: 创建新 session_id (例如: "xyz-789")
  │
  ▼
L1: 保存新映射 user_id -> "xyz-789"
  │
  ⚠️ 旧会话 "abc-123" 丢失 (Phase 1 设计)
```

### 会话创建测试用例

| 测试用例 | 测试编号 | 描述 |
|----------|----------|------|
| `test_first_request_creates_no_session_id` | TC-L1-SESSION-001 | 首次请求不携带 session_id，由 L2 创建 |
| `test_session_mapping_preserved_across_requests` | TC-L1-SESSION-002 | 同一会话 ID 在多次请求中被保留 |
| `test_new_session_command_clears_mapping` | TC-L1-SESSION-003 | `/new` 命令清除会话映射 |
| `test_various_new_session_commands` | TC-L1-SESSION-004 | 支持多种新建会话命令 (`/new`, `/reset`, `/start`, `新会话`) |
| `test_different_users_have_separate_sessions` | TC-L1-SESSION-005 | 不同用户有独立的会话映射 |

### 新建会话命令

用户可通过以下命令创建新会话：

| 命令 | 说明 |
|------|------|
| `/new` | 创建新会话，丢弃旧会话 |
| `/reset` | 同上 |
| `/start` | 同上 (Telegram 习惯) |
| `新会话` | 中文版本 |

### 运行会话管理测试

```bash
# 运行所有会话管理测试
pytest src/l1/tests/test_l1_basic.py::TestSessionManagement -v

# 运行单个测试
pytest src/l1/tests/test_l1_basic.py::TestSessionManagement::test_new_session_command_clears_mapping -v
```

## 如何运行测试

```bash
# 运行所有单元测试(无外部依赖)
pytest src/l1/tests/test_*.py -v --ignore=src/l1/tests/test_telegram_*.py --ignore=src/l1/tests/test_adapters_manual.py

# 运行手动适配器测试(无需网络,测试Telegram/WebSocket/Webhook适配器)
python src/l1/tests/test_adapters_manual.py

# 运行真实Telegram测试(轮询模式)
# 依赖: python-telegram-bot
python src/l1/tests/test_telegram_polling.py

# 运行真实Telegram测试(Webhook模式)
# 依赖: python-telegram-bot, fastapi, uvicorn
python src/l1/tests/test_telegram_webhook.py

# 运行WebSocket服务端测试
# 依赖: websockets
python src/l1/tests/test_websocket_server.py

# 运行HTTP Webhook服务端测试
# 依赖: fastapi, uvicorn
python src/l1/tests/test_webhook_server.py

# 运行L1-L2接口契约测试
# 依赖: 无
python src/l1/tests/test_l1_l2_contract.py
```

## 注意事项

1. **单元测试**不依赖外部服务，可离线运行
2. **Telegram测试**需要真实的Bot Token和网络连接
3. **.env 文件**: 所有真实环境测试从 `.env` 文件读取配置，不要将隐私信息硬编码在代码中
4. **依赖安装**: 运行真实环境测试前请先安装对应依赖
5. **添加新的测试文件时**: 必须同步更新本文档的依赖列表
6. **Webhook测试**需要额外的公网基础设施

## 隐私信息配置

所有包含敏感信息（Bot Token、API Key等）的测试都从 `.env` 文件读取：

```python
# 测试文件开头会自动加载 .env
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# 然后使用 os.getenv() 读取
import os
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

---
最后更新: 2026-04-11
