# VClaw Web Test Console 设计文档

**日期**: 2026-04-14  
**作者**: Claude Code (brainstorming session)  
**状态**: 已确认，待实现

---

## 1. 项目背景与目标

### 1.1 背景
VClaw 是一个六层 AI Agent 架构系统（L1-L6），每层都有独立的实现和测试。现有的 `src/l1/tests/test_webhook_server.py` 仅支持 L1 Webhook 适配器的单一测试，无法满足全系统功能和端到端对话测试的需求。

### 1.2 目标
构建一个统一的 Web 测试控制台，运行在 `http://localhost:8000/`，实现：
1. **各层独立功能测试**：为 L1-L6 每层提供可交互的测试界面
2. **端到端对话测试**：模拟完整用户请求链路（L1→L2→L3→L4/L5→L6）
3. **零构建工具依赖**：仅使用 FastAPI + 原生 HTML/CSS/JS

---

## 2. 目录结构

```
src/l1/tests/web_console/
├── __init__.py            # 空文件，使目录成为 Python 包
├── server.py              # FastAPI 入口和 API 路由
├── README.md              # 启动与使用说明
├── templates/
│   └── index.html         # Dashboard 单页应用主页面
└── static/
    ├── app.js             # 前端路由、Tab 切换、API 调用逻辑
    └── style.css          # Dashboard 侧边栏 + 卡片布局样式
```

**兼容性说明**：保留现有的 `src/l1/tests/test_webhook_server.py` 作为兼容层。新的主要启动命令为：
```bash
python src/l1/tests/web_console/server.py
```

---

## 3. 后端 API 设计

### 3.1 系统级端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/` | 返回 Dashboard HTML 页面 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/config` | 返回系统状态：LLM 是否可用、Docker 是否可用、已注册工具列表 |

### 3.2 各层独立测试端点

| 方法 | 端点 | 测试目标 |
|------|------|----------|
| `POST` | `/api/l1/test_adapter` | L1 适配器（Telegram/WebSocket/Webhook） |
| `POST` | `/api/l1/test_validator` | L1 DataValidator |
| `POST` | `/api/l2/test_rate_limit` | L2 限流器（RateLimiter） |
| `POST` | `/api/l2/test_session` | L2 会话管理 |
| `POST` | `/api/l3/test_react` | L3 ReAct 循环 |
| `POST` | `/api/l3/test_security` | L3 安全判断 |
| `POST` | `/api/l4/test_memory` | L4 记忆存储/检索 |
| `POST` | `/api/l4/test_search` | L4 向量搜索 |
| `POST` | `/api/l5/test_tool` | L5 单个工具调用 |
| `POST` | `/api/l5/test_bash` | L5 Bash 命令分析器 |
| `POST` | `/api/l6/test_runtime` | L6 沙箱代码执行 |

### 3.3 端到端对话端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/e2e/chat` | 发送消息，后端自动完成完整 ReAct 循环 |
| `POST` | `/api/e2e/reset` | 重置当前用户会话状态 |

### 3.4 `/api/e2e/chat` 详细行为

**请求体**：
```json
{
  "user_id": "test_user_1",
  "content": "计算 15 乘以 23",
  "channel": "web"
}
```

**处理流程**：
1. **L1**：使用 `EventNormalizer` 将请求解析为 `StandardEvent`（channel="web"）
2. **L2**：调用 `ControlGateway.process_event(event)` 生成 `L3Input`
3. **L3**：首次调用 `Orchestration.run(context)`
4. **ReAct 循环**（后端自动完成）：
   - 若返回 `str` → 直接作为最终答案
   - 若返回 `AgentAction` → 调用 L5 执行工具（若工具需要 L6，则继续调用 L6），生成 `Observation`，再次传给 `Orchestration.run()`
   - 循环直到拿到最终答案或达到 `MAX_ITERATIONS`
5. 返回完整结果

**响应体**：
```json
{
  "final_answer": "15 乘以 23 等于 345",
  "session_id": "uuid-xxx",
  "react_steps": [
    {
      "iteration": 1,
      "thought": "用户要求计算...",
      "action": "calculator",
      "action_input": {"expression": "15*23"},
      "observation": "345",
      "status": "success"
    }
  ],
  "elapsed_ms": 1234
}
```

---

## 4. 前端 Dashboard 设计

### 4.1 整体布局

采用**左侧固定导航栏 + 右侧主内容区**的经典 Dashboard 布局：

- **顶部栏（Header）**：左侧显示 "VClaw Test Console"，右侧显示系统状态指示灯（LLM 可用性、Docker 可用性）
- **左侧导航栏（Sidebar）**：垂直导航菜单
- **右侧主内容区（Main Content）**：根据导航切换显示不同测试面板

### 4.2 导航菜单结构

```
Dashboard 首页
├── L1 测试
│   ├── 适配器测试
│   └── 验证器测试
├── L2 测试
│   ├── 限流测试
│   └── 会话测试
├── L3 测试
│   ├── ReAct 测试
│   └── 安全判断测试
├── L4 测试
│   ├── 记忆存储
│   └── 向量搜索
├── L5 测试
│   ├── 工具调用
│   └── Bash 分析
├── L6 测试
│   └── 代码执行沙箱
└── E2E 对话
```

### 4.3 通用测试页面布局（L1-L6）

每个独立测试页面统一采用**三栏卡片布局**：

1. **左侧配置卡（Input）**
   - JSON 编辑器或表单输入测试参数
   - 提供预设示例（Quick Load）按钮
2. **中间操作卡（Action）**
   - "运行测试" 按钮
   - 请求预览（折叠显示将要发送的 JSON）
3. **右侧结果卡（Result）**
   - 格式化展示 API 返回结果
   - 支持 JSON 语法高亮和折叠展开

### 4.4 E2E 对话页面布局

- **主区域**：聊天窗口（类似 ChatGPT 界面），底部有消息输入框和发送按钮
- **右侧面板**：
  - 当前 `session_id`
  - 最近历史记录（可折叠）
  - ReAct thought chain（按迭代步骤展示）
- **顶部提示**：如果 LLM 不可用，显示红色警告横幅并提示配置 `.env`
- **Loading 状态**：发送消息后显示 "思考中..."，后端自动完成 ReAct 循环，前端只需等待一次响应

### 4.5 前端技术栈

- **HTML5**：单页应用，`index.html` 包含所有页面区块
- **CSS3**：原生 CSS 变量定义主题色，Flexbox/Grid 布局
- **JavaScript**：原生 ES6+，无框架依赖
  - 路由：基于 hash 的简易路由（`#l1-adapter`、`#e2e-chat` 等）
  - 状态：简单的全局 state 对象管理当前视图和会话信息
  - API：原生 `fetch`

---

## 5. 错误处理策略

### 5.1 HTTP 状态码映射

| 场景 | 状态码 | 前端行为 |
|------|--------|----------|
| L1/L2 解析或验证错误 | `400` | 在结果卡中高亮显示错误信息 |
| L3 LLM 不可用（无 API key） | `503` | E2E 页面顶部显示红色警告横幅 |
| L6 Docker 未启动 | `503` | 提示用户启动 Docker Desktop |
| 通用服务器错误 | `500` | 显示异常类型和 trace 前几行 |

### 5.2 L3 特殊处理

- **有 API key**：正常调用真实 LLM，走完整 ReAct 循环
- **无 API key**：`POST /api/l3/test_react` 和 `POST /api/e2e/chat` 返回 `503 Service Unavailable`，响应体包含：`{"detail": "LLM not available. Please configure OPENAI_API_KEY in .env file."}`

### 5.3 L5 工具执行错误

L5 工具执行失败时，错误由 L3 的 `_translate_error()` 方法转译为中文用户友好提示，作为 `final_answer` 正常返回给前端（HTTP 200），前端在聊天消息中显示该提示。

---

## 6. 依赖与运行环境

### 6.1 后端依赖

依赖项目中已有的包：
- `fastapi`
- `uvicorn`
- `jinja2`（FastAPI 模板渲染）
- `pydantic`

无需新增 pip 依赖。

### 6.2 可选外部依赖

- **LLM 测试**：需要有效的 `OPENAI_API_KEY`（从 `.env` 读取）
- **Docker 测试**：需要本地 Docker 守护进程运行（L6 测试）

### 6.3 启动命令

```bash
# 进入项目根目录
conda activate vclaw

# 启动测试控制台
python src/l1/tests/web_console/server.py

# 浏览器访问
open http://localhost:8000
```

---

## 7. 实现范围与边界

### 7.1 在范围内（Must Have）

- [ ] FastAPI 服务器和 Dashboard 前端页面
- [ ] L1-L6 每层至少 1 个独立测试接口和对应 UI
- [ ] E2E 对话接口（后端自动完成 ReAct 循环）
- [ ] 系统状态检测（LLM / Docker 可用性）
- [ ] 结果格式化和 JSON 高亮展示

### 7.2 不在范围内（Won't Have）

- [ ] 用户认证与权限管理（测试工具，仅限本地使用）
- [ ] 持久化的测试历史记录（仅展示当前会话）
- [ ] WebSocket 实时流式响应（首轮实现使用普通 HTTP）
- [ ] 移动端适配优化（以桌面浏览器为主要目标）

---

## 8. 附录：参考文件

| 文件 | 用途 |
|------|------|
| `src/core/models.py` | `StandardEvent`, `SessionContext`, `AgentAction`, `Observation`, `L3Input` 等数据模型 |
| `src/l1/l1_user_interaction.py` | L1 适配器、验证器、规范化器实现 |
| `src/l2/l2_control_gateway.py` | L2 限流器、会话管理、MemoryAccessor、ToolPreparer |
| `src/l3/l3_orchestration.py` | L3 ReActEngine、TaskPlanner、Orchestration |
| `src/l4/core/l4_memory.py` | L4 MemoryKnowledge 实现 |
| `src/l5/l5_tools.py` | L5 ToolsCapabilities、ToolRegistry |
| `src/l6/l6_runtime.py` | L6 RuntimeEnvironment、DockerSandbox |
| `src/l1/tests/test_webhook_server.py` | 现有 Webhook 测试服务器（兼容保留） |
