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

会话管理相关测试位于 `test_l1_basic.py` 中的 `TestSessionManagement` 类。

**注意：L1 已完全移除 session 管理职责，所有会话逻辑下沉至 L2。**

### 会话创建流程 (新架构)

L1 完全无状态，不负责任何 `user_id` -> `session_id` 映射：

```
第1次请求 (用户首次发言)
  │
  ▼
L1: 解析为 StandardEvent (metadata 中无 session_id)
  │
  ▼
L2: 从 L4 读取 active_session_id → 无 → 创建新 session_id
  │
  ▼
L2: 保存映射到 L4 (save_user_preference)

第2次请求 (同用户再次发言)
  │
  ▼
L1: 解析为 StandardEvent (metadata 中无 session_id)
  │
  ▼
L2: 从 L4 读取 active_session_id → 复用同一对话

/new 命令 (用户主动新建会话)
  │
  ▼
L1: 作为普通消息原样传递 (L1 不做特殊处理)
  │
  ▼
L2: 识别命令 → 清除 L4 映射 → 创建新 session_id → 保存到 L4
```

### 会话创建测试用例

| 测试用例 | 测试编号 | 描述 |
|----------|----------|------|
| `test_standard_event_has_no_session_id` | TC-L1-SESSION-001 | 验证 L1 产出的 StandardEvent 中不包含 session_id |
| `test_new_session_commands_passed_through` | TC-L1-SESSION-002 | `/new` 等命令作为普通消息原样传递给 L2 |

### 新建会话命令

用户可通过以下命令创建新会话：

| 命令 | 说明 |
|------|------|
| `/new` | 创建新会话，丢弃旧会话 |
| `/reset` | 同上 |
| `/start` | 同上 (Telegram 习惯) |
| `新会话` | 中文版本 |

## 响应发送

`UserInteraction` 类新增 `send_response(response: StandardResponse)` 方法，负责将 L2 传来的标准化响应发送回用户：

```
L3 final_answer
    ↓
L2 send_response(event, final_answer) → 构造 StandardResponse
    ↓
L1 send_response(response) → 根据 channel 调用对应发送逻辑
    ↓
用户
```

### StandardResponse 结构

```python
class StandardResponse(BaseModel):
    channel: str           # "telegram", "websocket", "webhook"
    user_id: str
    content: str           # 响应文本
    metadata: Dict         # 包含 chat_id, session_id 等
```

### 渠道支持状态

| 渠道 | 发送实现 | 状态 |
|------|----------|------|
| Telegram | `telegram_bot.send_message(chat_id=..., text=...)` | 已支持 |
| WebSocket | 待实现 | 未支持 |
| Webhook | 待实现 | 未支持 |

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
