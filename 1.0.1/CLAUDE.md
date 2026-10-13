# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VClaw** is a six-layer AI Agent system with strict layered architecture and unidirectional dependencies. The project follows TDD (Test-Driven Development) methodology.

## Architecture (6 Layers)

```
L1: User Interaction (用户接入层)     - Protocol adaptation, data validation
L2: Control Gateway (控制网关层)      - Rate limiting, session management
L3: Orchestration (逻辑编排层)        - Intent recognition, ReAct loop, LLM management
L4: Memory & Knowledge (记忆与知识层)  - RAG, vector indexing, long-term memory
L5: Tools & Capabilities (能力抽象层)  - Tool routing, permission validation
L6: Runtime & Environment (环境执行层) - Sandbox isolation, code execution
```

**Key Principle**: Unidirectional dependencies (upper → lower). L3 uses L4/L5 via dependency injection.

## Development Environment

**Required:** Use conda environment `vclaw` for all development and testing.

```bash
# Activate environment (ALWAYS do this first)
conda activate vclaw

# Install dependencies
pip install -r requirements.txt
```

## Common Commands

```bash
# Run all tests
pytest src/ tests/ -v

# Run specific layer tests (tests are now in src/l*/tests/)
pytest src/l1/tests/ -v
pytest src/l2/tests/ -v
pytest src/l3/tests/ -v
pytest src/l4/tests/ -v
pytest src/l5/tests/ -v
pytest src/l6/tests/ -v

# Run single test
pytest src/l1/tests/test_adapters.py::TestTelegramAdapter::test_parse_valid_telegram_data -v
pytest src/l6/tests/test_l6.py::TestRuntimeEnvironment::test_run_python_success -v

# Run with coverage
pytest src/ tests/ --cov=src --cov-report=html
```

## Key Files

| File | Purpose |
|------|---------|
| `src/core/models.py` | Pydantic data models (StandardEvent, SessionContext, AgentAction, Observation, ExecutionResult) |
| `src/core/interfaces.py` | Abstract base classes for DI (MemoryInterface, ToolsInterface, RuntimeInterface) |
| `src/core/exceptions.py` | Centralized exception definitions |
| `src/l1/l1_user_interaction.py` | L1: Event normalization from various channels |
| `src/l2/l2_control_gateway.py` | L2: Rate limiting, session context assembly |
| `src/l3/l3_orchestration.py` | L3: ReAct loop, intent recognition, LLM manager |
| `src/l4/core/l4_memory.py` | L4: Vector search, conversation history, embedding (Mock) |
| `src/l5/l5_tools.py` | L5: Tool execution, parameter validation, security |
| `src/l5/task_manager.py` | L5: Task lifecycle management (pending, active, completed, failed) |
| `src/l5/bash_analyzer.py` | L5: Bash command classification (safe, read, write, network, exec) |
| `src/l6/l6_runtime.py` | L6: Main RuntimeEnvironment implementing RuntimeInterface |
| `src/l6/docker_sandbox.py` | L6: High-level Docker sandbox management |
| `src/l6/docker_controller.py` | L6: Docker API wrapper with lazy initialization |
| `src/l6/security_enforcer.py` | L6: Security checks (forbidden patterns, resource limits) |
| `src/l6/config.py` | L6: SandboxConfig dataclass |
| `src/l*/tests/` | Layer-specific unit tests |

## Data Flow

1. **L1** receives raw payload → outputs `StandardEvent`
2. **L2** processes event (rate limit) → assembles complete L3 input (SessionContext + available_tools + relevant_memories)
3. **L3** runs ReAct loop:
   - Security judgment: classify requests (sensitive/malicious/high-risk/normal)
   - May call L4.search() for knowledge retrieval
   - May output `AgentAction` → L5 → (optional L6) → `Observation` → back to L3
   - Handles L5 errors: converts errors to user-friendly responses
   - Final output: response text
4. **L2** sends response via **L1**

## Layer Interface Contract

**L3 depends on L4/L5 via interfaces:**
```python
class Orchestration:
    def __init__(self, memory: MemoryInterface = None, tools: ToolsInterface = None):
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
```

## Project Structure Rules

1. **ALWAYS place source files in the appropriate layer folder** - never in `src/` root
2. **ALWAYS place layer tests in `src/l*/tests/`** - not in top-level tests/
3. **ALWAYS place planning files in `.claude/planning/`** - not in project root
4. **Update imports** when moving files between folders

## Test Folder Documentation Rule

**Each test folder MUST have a `README.md` documenting all test files.**

### README.md 必须包含以下内容：

| 章节 | 要求 |
|------|------|
| **测试文件列表** | File / Purpose / Dependencies / Status 表格 |
| **依赖清单** | 每个测试文件的 pip 依赖包，安装命令 |
| **运行方法** | 如何运行各个测试的具体命令 |
| **注意事项** | 外部服务需求、网络要求等 |

### 依赖文档格式

每个真实环境测试必须列出依赖：

```markdown
| 测试文件 | 依赖包 | 安装命令 |
|----------|--------|----------|
| `test_xxx.py` | `package1`, `package2` | `pip install package1 package2` |
```

### 测试目录对应表

| Test Folder | Documentation |
|-------------|---------------|
| `src/l1/tests/` | `src/l1/tests/README.md` |
| `src/l2/tests/` | `src/l2/tests/README.md` |
| `src/l3/tests/` | `src/l3/tests/README.md` |
| `src/l4/tests/` | `src/l4/tests/README.md` |
| `src/l5/tests/` | `src/l5/tests/README.md` |
| `src/l6/tests/` | `src/l6/tests/README.md` |
| `tests/mock/` | `tests/mock/README.md` (if exists) |
| `tests/integration/` | Document in `tests/README.md` |

## Mock E2E Testing Framework

Located in `tests/mock/`, this framework uses **six real LLMs** to simulate all 6 layers.

**Key files:**
- `e2e_framework.py` - Core framework with `EndToEndRunner`, `LLMClient`
- `layer_prompts.py` - System prompts for L1-L6 LLM simulation (Chinese)
- `test_cases.py` - 32 end-to-end test cases
- `run_e2e_tests.py` - Test runner supporting suites (p0/automated)

**Documentation Sync Rule:** When modifying code, you MUST同步更新相关文档.

| File Change | Documents to Update |
|-------------|---------------------|
| `tests/mock/layer_prompts.py` changes | `tests/mock/README.md` |
| `src/l1/*.py` implementation changes | `src/l1/tests/README.md` |
| `src/l2/*.py` implementation changes | `src/l2/tests/README.md` |
| `src/l*/tests/` new test files | `src/l*/tests/README.md` |
| `tests/integration/` new test files | `tests/integration/README.md` |
| Core models/interfaces changes | `tests/integration/README.md` + 受影响的层 README |

**开发测试时必须同时兼顾：**
1. **代码实现** (`src/l*/*.py`)
2. **测试文档** (`src/l*/tests/README.md`、对应跨层测试目录的 `README.md`)

**注意**：`docs/*.xml` 为架构设计文档，涉及整体系统结构，非架构变更请勿修改。

## Testing Policy

### LLM Testing Requirements

**L3层所有测试必须使用真实LLM**

| 功能测试 | 测试类型 | 说明 |
|----------|----------|------|
| 安全判断测试 | 真实LLM | 验证提示词能否引导LLM识别恶意请求 |
| 错误处理测试 | 真实LLM | 验证LLM转译错误信息的质量 |
| 路径处理测试 | 真实LLM | 验证LLM能否遵循提示词指导处理路径 |
| 任务规划测试 | 真实LLM | 验证LLM能否正确拆解任务 |

**重要规则**:
- ⚠️ **不使用真实LLM时，必须提前告知用户并获得确认**
- L3层功能（安全判断、错误处理、路径处理）都依赖LLM语义理解
- 所有测试位于 `src/l3/tests/test_l3.py`，调用真实LLM API
- 无API key时测试自动跳过

### API Key Setup for Testing

本项目使用第三方API平台，默认API地址为 `https://api.qingyuntop.top/v1`。

```bash
# 第三方API平台配置（默认使用青云端）
export API_BASE_URL="https://api.qingyuntop.top/v1"
export OPENAI_API_KEY="sk-..."

# Anthropic (optional)
export ANTHROPIC_API_KEY="..."

# Test configuration (使用青云端第三方API平台)
export TEST_LLM_PROVIDER="openai"
export TEST_LLM_MODEL="gpt-5.4-mini"  # 或其他可用模型
```

### Running Real LLM Tests

```bash
# Run real LLM tests
pytest src/l3/tests/test_l3_real_llm.py -v

# Run all tests (skips real LLM tests if no API key)
pytest src/l3/tests/ -v
```

## Layer Responsibilities Summary

| Layer | Core Responsibilities |
|-------|----------------------|
| L1 | Protocol adaptation, input normalization |
| L2 | Rate limiting, session management, **tool permission filtering** |
| L3 | **Security judgment**, ReAct loop, tool selection, **L5 error handling** |
| L4 | Memory retrieval, history management |
| L5 | Tool execution, parameter validation, **tool registry**, **task management**, **bash analysis** |
| L6 | Sandboxed code execution with Docker isolation |

## L6: Runtime Environment Implementation

L6 provides secure, isolated code execution using Docker containers:

### Components

| Component | Purpose |
|-----------|---------|
| `RuntimeEnvironment` | Main class implementing `RuntimeInterface`, orchestrates execution |
| `DockerSandbox` | High-level sandbox lifecycle management (create, execute, destroy) |
| `DockerController` | Low-level Docker API wrapper with lazy initialization |
| `SecurityEnforcer` | Pre-execution security checks (forbidden patterns, resource limits) |
| `SandboxConfig` | Configuration dataclass for resource limits |

### Supported Languages

- **Python** (python:3.11-alpine)
- **JavaScript** (node:18-alpine)
- **Bash** (alpine:latest)

### Security Features

- **Forbidden patterns**: `os.system`, `subprocess`, `eval(`, `exec(`, `__import__`
- **Resource limits**: Memory (512MB), CPU (1 core), timeout (30s), disk (100MB)
- **Network isolation**: Disabled by default (`enable_network=False`)
- **Code size limit**: 100KB maximum

### Usage Example

```python
from src.l6.l6_runtime import RuntimeEnvironment
from src.l6.config import SandboxConfig

# With default config
runtime = RuntimeEnvironment()
result = runtime.run_code("python", "print('Hello World')")

# With custom config
config = SandboxConfig(memory_limit=1024, timeout=60)
runtime = RuntimeEnvironment(config)
result = runtime.run_code("javascript", "console.log('Hello')")

# Result contains: exit_code, stdout, stderr, execution_time
print(result.stdout)  # "Hello World"
```

## L1 Real-World Testing

### Telegram Bot Testing

**Current Status:** Using Polling mode for local development (no public IP required)

**TODO:** Migrate to Webhook mode for production deployment

#### Two Modes Comparison

| Mode | Direction | Public IP | Delay | Use Case |
|------|-----------|-----------|-------|----------|
| **Polling** | Bot → Telegram API | ❌ No | 1-2s | Development, local testing |
| **Webhook** | Telegram → Bot | ✅ Yes (ngrok) | Real-time | Production |

#### Testing Scripts

**1. Polling Mode (Current)**
```bash
# Run polling test (no ngrok needed)
python src/l1/tests/test_telegram_polling.py
# Then send message to Bot in Telegram
```

**2. Webhook Mode (Future)**
```bash
# 1. Start ngrok
ngrok http 8000

# 2. Copy ngrok HTTPS URL

# 3. Run webhook test
python src/l1/tests/test_telegram_webhook.py

# 4. Enter ngrok URL when prompted
```

#### Migration Plan

**Phase 1: Polling (Current)**
- ✅ `test_telegram_polling.py` - Working, no external dependencies
- Use for L1 parsing validation
- Use for development iteration

**Phase 2: Webhook (TODO)**
- ⏳ `test_telegram_webhook.py` - Ready but requires ngrok
- Use for production-like testing
- Use for response latency testing

**Decision:** Keep both scripts. Polling for dev, Webhook for prod testing.

For detailed documentation, see `README.md` and `docs/` directory.

## Export Rules

When exporting files (e.g., conversation logs, test results, data exports):

- **Location**: Always save to `.claude/` directory
- **Naming format**: Use current date and time in `MMDDHHMM.txt` format
  - Example: `04111656.txt` (April 11, 16:56)
- **Do not** create files in project root unless explicitly required

| Export Type | Destination Example |
|-------------|---------------------|
| Conversation logs | `.claude/04111656.txt` |
| Test results | `.claude/04111656_test_results.txt` |
| Data exports | `.claude/04111656_export.txt` |

### How to Export

Claude Code's `/export` command saves to project root by default. Use this workflow:

```bash
# Step 1: Export conversation
/export

# Step 2: Move to .claude/ with correct naming
python .claude/export_helper.py
```

Or manually:
```bash
# After /export, move the file
mv 2026-04-11-*.txt .claude/04111658.txt
```

## Session Management TODO

### Phase 1: L1 Stateless + L2 Session Management (✅ Completed)

- [x] L1 `UserInteraction` manages `user_id -> session_id` mapping (in-memory)
- [x] L2 `ControlGateway` manages `session_id -> SessionContext` lifecycle
- [ ] Session mapping persisted to L4 via `save_user_preference` / `load_user_preference` — **WIP: interface added, L2 integration pending**
- [x] Support `/new`, `/reset`, `/start`, "新会话" commands in L1 to trigger new session
- [ ] L1 & L2 tests updated to reflect persistent session architecture
- [ ] Session survives restart via L4 persistence — **current: 3600s TTL in memory only**

### Phase 2: Session Recovery & Multi-Session

- [ ] Support listing user's historical sessions
- [ ] Support `/sessions` command to list sessions
- [ ] Support `/switch <session_id>` to resume old session
- [ ] Long-term session archive (auto-cleanup after 7 days)

### Phase 3: Multi-Session Management

- [ ] Support multiple active sessions per user
- [ ] Session naming/renaming (`/name <session_name>`)
- [ ] Session metadata (created_at, last_active, message_count)
- [ ] Session pinning (keep important sessions)

### Phase 4: Advanced Features

- [ ] Session sharing (share conversation with other users)
- [ ] Session export/import
- [ ] Session templates (save as template for new conversations)

## Session Data Flow

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  L1 UserInteraction                                      │
│  1. Parse raw payload into StandardEvent                 │
│  2. Check user_id → session_id mapping (in-memory)       │
│  3. Inject session_id into metadata (None if new user)   │
│  4. If /new command: clear mapping, session_id = None    │
└─────────────────────────────────────────────────────────┘
    │
    │ StandardEvent (with session_id in metadata)
    ▼
┌─────────────────────────────────────────────────────────┐
│  L2 ControlGateway                                       │
│  1. Get session_id from event.metadata                   │
│  2. If session_id present and valid in memory: reuse     │
│  3. If session_id is None or invalid: create new UUID    │
│  4. Store session in memory (3600s TTL, restart lost)    │
│  5. Return SessionContext with session_id                │
│                                                          │
│  TODO: L4 persistence via save/load_user_preference(     │
│    user_id, "active_session_id", session_id)             │
│  (Interface added, L2 integration pending)               │
└─────────────────────────────────────────────────────────┘
    │
    │ SessionContext(session_id)
    ▼
   L3 → L5 → ... → Final Answer
    │
    ▼
  L2 sends response via L1
```

### Commands Reference

| Command | Description | Availability |
|---------|-------------|--------------|
| `/new` | Create new session, lose old one | ✅ Phase 1 |
| `/reset` | Same as `/new` | ✅ Phase 1 |
| `/start` | Same as `/new` (Telegram convention) | ✅ Phase 1 |
| `新会话` | Chinese version | ✅ Phase 1 |
| `/sessions` | List all sessions | ⏳ Phase 2 |
| `/switch <id>` | Switch to session | ⏳ Phase 2 |

## L5: Tools & Capabilities Additions

### TaskManager

Located in `src/l5/task_manager.py`, manages asynchronous task lifecycle:

```python
from src.l5.task_manager import TaskManager, TaskStatus

manager = TaskManager()
task_id = manager.submit_task(
    task_type="file_analysis",
    payload={"file_path": "/path/to/file"},
    priority=5
)

# Check status
status = manager.get_task_status(task_id)  # pending, active, completed, failed

# Get result
result = manager.get_task_result(task_id)
```

**Task States**: `pending` → `active` → `completed`/`failed`

### BashAnalyzer

Located in `src/l5/bash_analyzer.py`, classifies bash commands by risk level:

```python
from src.l5.bash_analyzer import BashAnalyzer, CommandType

analyzer = BashAnalyzer()
classification = analyzer.analyze("cat /etc/passwd")
print(classification.command_type)  # CommandType.READ
print(classification.risk_level)    # "low"
```

**Command Types**:
| Type | Description | Examples |
|------|-------------|----------|
| `SAFE` | Read-only operations | `ls`, `cat`, `grep`, `echo` |
| `READ` | File reading | `cat`, `head`, `less` |
| `WRITE` | Destructive writes | `rm`, `mv`, `>` |
| `NETWORK` | Network access | `curl`, `wget`, `ssh` |
| `EXEC` | Code execution | `bash`, `python`, `make` |

**Risk Levels**: `minimal` < `low` < `medium` < `high` < `critical`

## L4 Memory & Knowledge Layer Configuration

### Quick Start

```python
from src.l4.config.l4_config import get_l4_memory_production

# Initialize L4 with production config (OpenAI + ChromaDB)
memory = get_l4_memory_production()

# Store documents
memory.store("Document content", {"doc_id": "doc1", "category": "tech"})

# Search
results = memory.search("query text", top_k=5)

# Store conversation history
memory.store_conversation("session-123", [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
])

# Retrieve history
history = memory.retrieve_history("session-123", limit=10)
```

### Environment Configuration (.env)

```env
# L4: Memory & Knowledge Layer Configuration
# --------------------------------------------

# Embedding Service
L4_EMBEDDING_PROVIDER=openai  # openai | sentence-transformers | mock
L4_EMBEDDING_MODEL=text-embedding-3-small

# Vector Store
L4_VECTOR_STORE_TYPE=chroma   # memory | chroma | faiss
L4_CHROMA_COLLECTION_NAME=vclaw_knowledge
L4_CHROMA_PERSIST_DIR=./src/l4/data/chroma_db

# Memory Store
L4_MEMORY_STORE_TYPE=file     # memory | file
L4_MEMORY_STORAGE_DIR=./src/l4/data/conversations

# Cache
L4_CACHE_ENABLED=true
L4_CACHE_MAX_SIZE=1000
L4_CACHE_DEFAULT_TTL=3600
```

### Initialization

```bash
# Create data directories and run tests
python init_l4.py
```

### Data Directories

```
src/l4/data/
├── chroma_db/          # ChromaDB vector database
└── conversations/      # Conversation history storage
```

### L4 Directory Structure

```
src/l4/
├── __init__.py              # Package exports
├── core/                    # Core implementation
│   ├── __init__.py
│   └── l4_memory.py         # Main MemoryKnowledge class
├── services/                # Service implementations
│   ├── __init__.py
│   ├── embedding.py         # Embedding services (OpenAI, Local, Mock)
│   └── text_chunker.py      # Text chunking strategies
├── storage/                 # Storage implementations
│   ├── __init__.py
│   ├── vector_store.py      # Vector databases (ChromaDB, FAISS, Memory)
│   ├── memory_store.py      # Conversation & preference storage
│   └── cache_manager.py     # LRU cache with TTL
├── index/                   # Index management
│   ├── __init__.py
│   └── index_manager.py     # Vector index lifecycle
└── tests/                   # Unit tests
    ├── test_embedding.py
    ├── test_text_chunker.py
    ├── test_vector_store.py
    ├── test_memory_store.py
    ├── test_cache_manager.py
    ├── test_l4_memory.py
    └── test_l4.py
```

### Components

| Component | Implementations | Description |
|-----------|-----------------|-------------|
| **EmbeddingService** | OpenAI, Sentence Transformers, Mock | Text to vector embedding |
| **VectorStore** | ChromaDB, FAISS, Memory | Vector storage and search |
| **TextChunker** | Recursive, Token, Markdown, Character | Text splitting strategies |
| **MemoryStore** | File, InMemory | Conversation history storage |
| **CacheManager** | LRU + TTL | Embedding and search result caching |
| **IndexManager** | Chroma, Memory | Vector index lifecycle management |


## L3 Enhancement TODO

### 2026-04-12: L3 层功能增强设计

**设计文档**: `.claude/planning/2026-04-12-l3-enhancement-design.md`

#### 当前开发内容

| 功能 | 方案 | 状态 |
|------|------|------|
| **安全判断** | Prompt 内建安全指令，LLM 自行判断恶意请求 | 🚧 待实现 |
| **L5 错误处理** | LLM 转译错误信息为用户友好中文提示 | 🚧 待实现 |
| **路径转换规则** | ReAct 引导 LLM 自主处理，检查目录存在性并询问用户 | 🚧 待实现 |

#### 延后功能

| 功能 | 延后原因 | 计划实现时间 |
|------|----------|--------------|
| **思维链展示** | 1. 需要修改 L3 返回值结构<br>2. 需要 L2/L1 适配<br>3. 多渠道展示复杂度高 | 系统整体完成后 |

**思维链展示后续方案**:
- L3 返回结构增加 `thought_chain` 字段
- L1 根据渠道类型适配展示（Telegram Inline Keyboard、Web 折叠面板等）
- 用户可通过按钮切换显示/隐藏思维链

### L3 系统提示词配置

**文件位置**: `src/l3/l3_orchestration.py` 中的 `_build_messages()` 方法

系统提示词需要包含以下内容，修改时同步更新此处文档：

```python
L3_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

SECURITY POLICY:
If the user request involves malicious operations (destroying system, deleting important data, hacking, etc.), 
you MUST refuse the request politely and explain why.

Examples of malicious requests to refuse:
- Formatting disk, deleting system files
- Hacking, cracking, unauthorized access
- Creating malware, viruses
- Any operation that could harm the system or data

FILE PATH HANDLING:
When the user mentions a file path in natural language (e.g., "桌面", "下载", "文档"),
simply pass the path as-is in the tool parameters. The system will automatically resolve it.
Examples:
- "桌面/文件.txt" -> the user's real Desktop
- "下载/报告.pdf" -> the user's real Downloads folder
- "文档/笔记.md" -> the user's real Documents folder
- Single filename like "test.txt" -> defaults to Documents folder
- "documents/..." -> project sandbox directory (backward compatible)

For normal requests, assist the user as usual."""
```

**修改提示词后需要**:
1. 更新上面的代码块内容
2. 同步更新 `src/l3/l3_orchestration.py` 中的实际代码
3. 如有行为变更，更新相关测试用例

## Development Workflow Rules

### 提交规则

**更改完成后不要自动提交，由用户自行提交。**

- 完成代码/文档修改后，执行 `git diff` 或 `git status` 展示更改
- 等待用户确认后再提交（如果用户要求提交）
- 用户明确说"提交"或"commit"时才执行提交操作
- 默认情况下让用户自己控制提交时机

### 隐私信息管理规则

**所有隐私信息（API Key、Bot Token等）必须存放在 `.env` 文件中**

- `.env` 文件位于项目根目录
- `.env` 文件已被 `.gitignore` 排除，不会提交到Git
- 代码中通过 `os.getenv()` 或 `python-dotenv` 读取环境变量
- 不要直接在代码中硬编码API key等隐私信息

**示例 `.env` 文件：**
```bash
# 第三方API平台配置（默认使用青云端）
API_BASE_URL=https://api.qingyuntop.top/v1
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=...

# Telegram Bot Token (L1 tests)
TELEGRAM_BOT_TOKEN=...

# Test Configuration (使用青云端第三方API平台)
TEST_LLM_PROVIDER=openai
TEST_LLM_MODEL=gpt-5.4-mini
```

**读取方式：**
```python
from dotenv import load_dotenv
import os

load_dotenv()  # 加载 .env 文件

api_key = os.getenv("OPENAI_API_KEY")
```

### 真实LLM测试规则

**不使用真实LLM时必须提前告知用户并获得确认**

- 功能验证测试（安全判断、错误处理、路径处理）必须使用真实LLM
- 如使用Mock测试，需明确告知用户并获得同意
- 真实LLM测试从 `.env` 文件读取 API key：`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

### 文件存放位置规则

**测试结果和输出文件必须存放在对应层的 tests/results/ 文件夹下**

| 文件类型 | 存放位置 | 禁止位置 |
|----------|----------|----------|
| 测试结果输出 | `src/l*/tests/results/` | ❌ 项目根目录 |
| 测试日志 | `src/l*/tests/results/` | ❌ `.claude/` 根目录 |
| LLM 响应结果 | `src/l*/tests/results/` | ❌ 临时文件夹 |

**示例：**
- L3 层测试结果 → `src/l3/tests/results/`
- L1 层测试结果 → `src/l1/tests/results/`

### 文档同步规则

**修改代码时必须同步更新相关文档**

| 修改内容 | 需要更新的文档 |
|----------|----------------|
| `src/l*/` 代码 | `src/l*/tests/README.md` |
| `tests/mock/` prompts | `tests/mock/README.md` |
| 核心模型/接口 | `tests/integration/README.md` + 受影响的层 README |
| 系统提示词 | `CLAUDE.md` 对应章节 + 代码文件 |

---

## TaskPlanner 与 Multi-Agent 系统规划

### 当前状态

**L3层目前使用纯ReAct实现**，TaskPlanner已创建但**未在流程中使用**。

```python
# 当前实现
Orchestration.run():
    - 使用 ReActEngine.generate_thought() 进行动态决策
    - 不使用 TaskPlanner 创建的计划
    - 适合简单对话和单步工具调用
```

### TaskPlanner 设计用途

根据 `docs/L3_Orchestration.xml`，TaskPlanner 负责：

1. **任务分解** - 将复杂请求拆解为可执行步骤
2. **依赖管理** - 管理步骤间的依赖关系 (`depends_on`)
3. **执行规划** - 为ReAct提供结构化参考框架

### 何时需要整合 TaskPlanner

**当前纯ReAct已足够**：
- 简单对话回复
- 单步工具调用（计算器、文件读写）
- 无需复杂规划的场景

**未来需要TaskPlanner**：
- 多步骤复杂任务（研究→总结→生成报告）
- 步骤间有依赖关系（步骤2依赖步骤1的结果）
- 需要并行执行多个子任务
- 多Agent协作场景

### Multi-Agent 系统设计（TODO）

**Phase 1: 整合 TaskPlanner + ReAct**

```python
# 方案：ReAct为主，TaskPlanner为辅
def run(self, context, observation=None):
    # 第一轮：生成参考计划（不强制按步骤执行）
    if not self.current_plan:
        self.current_plan = self.task_planner.create_plan(...)
    
    # ReAct动态决策，参考但不强制按计划
    react_result = self.react_engine.generate_thought(
        query=context.current_query,
        plan_hint=self.current_plan,  # 作为参考
        observation=observation
    )
```

**Phase 2: Multi-Agent 系统**

```
主Agent (Orchestrator)
    ├── 规划Agent (Planner) - 负责任务分解
    ├── 执行Agent (Executor) - 负责工具调用
    ├── 验证Agent (Validator) - 负责结果验证
    └── 总结Agent (Summarizer) - 负责最终输出
```

**关键设计**：
- 各Agent通过消息队列通信
- Shared Context 共享状态
- TaskPlanner 生成子任务分配给各Agent
- ReActEngine 在每个Agent内部做决策

### 实施优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 保持纯ReAct | 当前实现已满足基本需求 |
| P1 | 整合TaskPlanner | 在复杂任务场景中启用 |
| P2 | Multi-Agent | 系统整体稳定后实现 |

### 相关文件

| 文件 | 当前状态 | 后续计划 |
|------|----------|----------|
| `src/l3/l3_orchestration.py` | ReActEngine已实现，TaskPlanner已实例化但未使用 | 根据需求整合两者 |
| `docs/L3_Orchestration.xml` | 设计包含两者 | 代码实现需对齐设计 |
| `src/l3/tests/test_task_planner.py` | 测试TaskPlanner独立功能 | 保留用于后续验证 |

---
最后更新: 2026-04-13

---

## L3 工具调用执行流程（详细说明）

### 问题背景
当L3返回 `AgentAction` 后，**谁负责调用L5执行工具？**

### 当前设计

```
用户请求
    ↓
┌─────────────────────────────────────────────────────────────┐
│ L1: 接收输入 → StandardEvent                                │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ L2: 组装完整上下文 (SessionContext + available_tools)       │
│     调用 L3.run(context)                                     │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ L3: ReAct循环                                                │
│     ├── 生成 Thought                                        │
│     ├── 决定 Action                                         │
│     └── 返回:                                               │
│         ├── AgentAction (需要调用工具) ──────┐              │
│         └── str (最终答案) ──────────────────┼──┐           │
└─────────────────────────────────────────────────────────────┘  │
    ↓                                                            │
    │         ┌────────────────────────────────────────────────┘
    │         │
    │    ┌────┴─────────────────────────────────────────────┐
    │    │ L2: 接收AgentAction                               │
    │    │     - 检查权限 (user_permissions)                  │
    │    │     - 调用 L5.execute(action, params)             │
    │    │     - 接收 Observation                           │
    │    │     - 再次调用 L3.run(context, observation)       │
    │    └──────────────────────────────────────────────────┘
    │                        ↓
    │                   ┌────┴─────┐
    │                   │   L5     │
    │                   │ (L6可选) │
    │                   └────┬─────┘
    │                        ↓
    │                   Observation
    │                        ↓
    └────────────────────────┘
                             ↓
                    最终答案 (str)
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ L2: 发送响应给用户                                           │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计决策

**由L2负责调用L5，而不是L3自己调用：**

1. **架构分层**：
   - L3是"决策者"（Decider）：决定**调用什么工具**
   - L2是"协调者"（Coordinator）：负责**执行工具调用**
   - L5是"执行者"（Executor）：实际**执行工具**

2. **权限控制**：
   - L2在调用L5前检查用户权限
   - 如果用户没有权限，直接返回错误，不调用L5

3. **状态管理**：
   - L2管理整个请求-响应周期
   - 包括多次L3调用（ReAct循环）

### 代码实现

**当前L3职责（已实现）**：
```python
class Orchestration:
    def run(self, context, observation=None):
        # 1. 生成Thought
        # 2. 决定Action
        # 3. 返回 AgentAction 或 str
        
        if need_tool:
            return AgentAction(action="calculator", action_input={"expression": "1+1"})
        else:
            return "最终答案"
```

**L2职责（待实现）**：
```python
class ControlGateway:
    def process(self, event):
        # 1. 组装SessionContext
        context = SessionContext(...)
        
        # 2. 调用L3
        result = self.l3.run(context)
        
        # 3. 处理AgentAction
        if isinstance(result, AgentAction):
            # 检查权限
            if not self.check_permission(result.action, user_permissions):
                return "权限不足"
            
            # 调用L5
            observation = self.l5.execute(result.action, result.action_input)
            
            # 再次调用L3，传递Observation
            final_result = self.l3.run(context, observation)
            return final_result
        
        # 4. 返回最终结果
        return result
```

### 澄清

**L3不直接调用L5的原因**：
- L3通过接口 `ToolsInterface` 与L5解耦
- L3只负责"决策"，不负责"执行"
- L2作为中间层，协调L3和L5之间的交互
- 这符合"控制反转"（IoC）原则

---
最后更新: 2026-04-13

---

## Observation返回流程详细说明

### 问题
**L5执行完工具后，Observation如何返回到L3？**

### 答案：通过L2协调返回

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           完整工具调用与返回流程                           │
└─────────────────────────────────────────────────────────────────────────┘

用户: "计算15乘以23"
    │
    ▼
┌───────────────┐
│  L1: User     │  接收用户输入
│  Interaction  │  → StandardEvent
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  L2: Control  │  组装SessionContext
│  Gateway      │  调用L3.run(context)
└───────┬───────┘
        │
        ▼
┌───────────────┐     ┌─────────────────────────────────────────┐
│  L3:          │     │ 第1轮:                                  │
│  Orchestration│     │   - 生成Thought                         │
│               │     │   - 决定Action                          │
│               │     │   - 返回AgentAction                     │
│               │     │                                         │
│  AgentAction  │◄────┤   action: "calculator"                  │
│  (工具调用)    │     │   action_input: {"expression": "15*23"} │
└───────┬───────┘     └─────────────────────────────────────────┘
        │
        │ 返回给L2
        ▼
┌───────────────┐
│  L2: Control  │  接收AgentAction
│  Gateway      │  检查权限
│               │  调用L5.execute("calculator", params)
└───────┬───────┘
        │
        ▼
┌───────────────┐     ┌─────────────────────────────────────────┐
│  L5: Tools    │     │ 执行calculator工具                      │
│  Capabilities │────►│ 参数: {"expression": "15*23"}            │
│               │     │ 结果: 345                               │
└───────┬───────┘     └─────────────────────────────────────────┘
        │
        │ 返回Observation
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ Observation对象                                                  │
│   status: "success"                                              │
│   result: "345"                                                  │
│   execution_time: 0.001                                          │
│   metadata: {}                                                   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────┐
│  L2: Control  │  接收Observation
│  Gateway      │  再次调用L3.run(context, observation)
└───────┬───────┘
        │
        ▼
┌───────────────┐     ┌─────────────────────────────────────────┐
│  L3:          │     │ 第2轮:                                  │
│  Orchestration│     │   - 接收Observation                     │
│               │────►│   - 记录到ReAct历史                     │
│  ReAct Engine │     │   - 基于Observation生成新Thought        │
│               │     │   - 返回最终答案                        │
│               │     │                                         │
│  最终答案(str) │◄────┤   "15乘以23等于345"                     │
└───────┬───────┘     └─────────────────────────────────────────┘
        │
        │ 返回给L2
        ▼
┌───────────────┐
│  L2: Control  │  接收最终答案
│  Gateway      │  调用L1发送响应
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  L1: User     │  发送给用户
│  Interaction  │
└───────────────┘
        │
        ▼
用户: "15乘以23等于345"
```

### Observation对象结构

```python
class Observation(BaseModel):
    """L5输出 / L3输入 - 工具执行结果"""
    status: str           # "success" 或 "error"
    result: str           # 执行结果（最多10000字符）
    execution_time: float # 执行时间（秒）
    metadata: Dict        # 额外元数据
```

### L3如何处理Observation

```python
def run(self, context, observation=None):
    # 如果observation存在，说明是ReAct循环的第2+轮
    if observation:
        # 1. 记录Observation到ReAct历史
        self.react_engine.add_to_history(
            thought="Received tool execution result",
            action=f"Observation: {observation.status}",
            observation=observation.result
        )
        
        # 2. 基于Observation生成新Thought
        react_result = self.react_engine.generate_thought(
            query=context.current_query,
            observation=observation,  # ← 传递给LLM
            available_tools=available_tools,
            knowledge=knowledge
        )
        
        # 3. 决定下一步：继续调用工具或返回最终答案
        if react_result["action_type"] == "final_answer":
            return react_result["action"]  # 最终答案(str)
        else:
            return AgentAction(...)         # 继续调用工具
```

### 关键设计点

1. **Observation是单向传递**
   - L5 → L2 → L3
   - 不反向传递

2. **L3通过参数接收Observation**
   ```python
   def run(self, context, observation=None):
       # observation参数承载L5的执行结果
   ```

3. **ReAct循环依赖Observation**
   - 没有Observation：第1轮，生成初始Thought
   - 有Observation：第2+轮，基于结果再思考

4. **错误Observation特殊处理**
   ```python
   if observation and observation.status == "error":
       return self._translate_error(observation)  # 错误转译
   ```

### 对比：成功 vs 错误 Observation

| 场景 | Observation.status | L3处理方式 | 返回结果 |
|------|-------------------|-----------|---------|
| 工具执行成功 | "success" | 基于结果生成新Thought | AgentAction 或 str |
| 工具执行失败 | "error" | 转译为友好错误提示 | str (错误信息) |

### 代码示例

```python
# L5执行工具并返回Observation
def execute(self, action_name, params) -> Observation:
    try:
        result = self._execute_calculator(params)
        return Observation(
            status="success",
            result=str(result),
            execution_time=0.001,
            metadata={}
        )
    except Exception as e:
        return Observation(
            status="error",
            result=str(e),
            execution_time=0.0,
            metadata={"error_type": type(e).__name__}
        )

# L3接收Observation
def run(self, context, observation=None):
    if observation:
        if observation.status == "error":
            return f"操作失败: {observation.result}"
        
        # 成功：继续ReAct循环
        react_result = self.react_engine.generate_thought(
            observation=observation  # 传递Observation
        )
        ...
```

---
最后更新: 2026-04-13
