# VClaw Mock E2E 测试框架 PPT 设计文档

## 项目背景

为 VClaw 项目的 `tests/mock` 和 `tests/e2e` 目录下的 Mock E2E 测试框架制作一份技术分享 PPT，面向团队内部的技术评审与分享，目标是让大家快速理解该框架的设计思路、核心组件和实际价值。

## 目标受众

- 技术团队成员
- 参与评审的架构师/开发同事
- 对 VClaw 六层架构已有基本了解

## 设计原则

- **精简为主**：10-15 页，不堆砌代码
- **问题驱动**：先讲痛点，再引出解法
- **架构+实例结合**：用架构图建立全局认知，用单用例旅程展示数据流转
- **视觉优先**：每一页都有图表或结构图，避免纯文字堆砌

## PPT 结构（共 11 页）

### 第 1 页：封面
- **标题**：VClaw Mock E2E 测试框架
- **副标题**：基于六层 LLM 模拟的端到端测试方案
- **视觉**：左侧大标题，右侧简化的六层堆叠架构示意图

### 第 2 页：为什么要做？——测试痛点
- 痛点 1：VClaw 是六层系统，E2E 测试依赖完整真实环境（L1-L6 全部启动）
- 痛点 2：真实 LLM 调用成本高、耗时长、结果不稳定，难以 CI 集成
- 痛点 3：真实环境配置复杂（Docker、API Key、向量数据库），新成员上手门槛高
- **结论**：需要一个低成本、可复现、易部署的 E2E 测试方案

### 第 3 页：核心解法——用 6 个 LLM 模拟 6 层系统
- 解法：每个层次用一个 LLM + 系统提示词模拟其行为
- 关键优势：
  - 无需启动完整服务，即可验证 L1-L6 串联逻辑
  - 结果可复现、成本可控、部署零依赖
  - 支持真实 LLM（生产验证）和 Mock 模式（快速回归）

### 第 4 页：框架架构总览
- 三个核心模块：
  1. `e2e_framework.py` —— `EndToEndRunner` + `LayerSimulator` + `LLMClient`
  2. `layer_protocol.py` —— 层间数据传输的 Pydantic 模型定义
  3. `test_cases.py` / `run_e2e_tests.py` —— 32 个用例 + 套件运行器
- 配图：模块关系图

### 第 5 页：六层模拟架构
- 表格展示 L1-L6 的职责和核心输出：

| 层次 | 模拟职责 | 核心输出 |
|------|---------|---------|
| L1 | 协议适配、输入标准化 | `StandardEvent` |
| L2 | 限流、会话组装、权限筛选 | `SessionContext` |
| L3 | 安全判断、ReAct 循环、工具决策 | `AgentAction` / 直接回复 |
| L4 | 记忆检索、对话历史存储 | `SearchResult` / `HistoryOutput` |
| L5 | 工具路由、参数验证、权限检查 | `Observation` |
| L6 | 沙盒隔离、代码执行 | `ExecutionResult` |

### 第 6 页：层间数据协议
- 所有层间通信通过 Pydantic 模型严格约束
- 关键数据流：
  - `L1Output.standard_event` → L2
  - `L2Output.l3_input` → L3（含 session_context + available_tools + memories）
  - `L3Output.agent_action` → L5
  - `L5Output.observation` → 回传 L3
  - `L6Output.execution_result` → 回传 L5
- 配图：数据流转箭头图

### 第 7 页：测试用例设计
- 32 个测试用例，覆盖 8 大场景：
  - 正常功能（P0 必过）
  - 模糊/异常指令
  - 高危操作拦截
  - 幻觉检测
  - 记忆/上下文
  - 联网功能
  - 权限/沙盒安全
  - UX 体验
- 每个用例包含：`user_input`、`precondition`、`react_flow`、`expected_result`、`risk_level`、`priority`、`tags`

### 第 8 页：测试运行器能力
- `run_e2e_tests.py` 支持多种执行模式：
  - `--suite p0`：P0 必过套件
  - `--suite automated`：全部可自动化用例
  - `--cases TC-01 TC-06`：指定用例
  - `--category 安全`：按分类运行
- 每个用例独立目录输出 JSON 结果和报告
- 配图：命令行示例 + 输出目录结构树

### 第 9 页：一个实例的完整旅程（TC-01）
- 用例："帮我在桌面上建个文档，写上今天下午3点开周会"
- 流程：
  1. L1：解析 Telegram 消息 → `StandardEvent`
  2. L2：创建 session，检索历史，筛选工具 → `SessionContext`
  3. L3：识别意图，决策调用 `file_write` → `AgentAction`
  4. L5：验证权限和路径安全 → `Observation`
  5. L6（如需要）：沙盒执行 → `ExecutionResult`
  6. 回传 L3：生成最终回复
- 配图：时间轴/流程图

### 第 10 页：真实 LLM E2E 测试
- `tests/e2e/` 在 mock 框架之上增加了真实 LLM 调用能力
- `RealLLMTestExecutor` 特性：
  - 支持 OpenAI / Anthropic / Moonshot 混合配置
  - 自动成本估算（token 数、USD）
  - 自动验证结果（状态检查、关键词匹配）
  - 生成 Markdown 测试报告
- 配图：Mock 框架 vs 真实 LLM E2E 对比表

### 第 11 页：总结与展望
- **已实现**：32 用例覆盖、6 层 LLM 模拟、Pydantic 协议约束、多模式运行器、真实 LLM 验证
- **价值**：显著降低 E2E 测试门槛，支持快速回归和 CI 集成
- **下一步**：完善 L4 真实内存集成、增加边界用例、优化 ReAct 循环验证策略

## 视觉风格

- **主色调**：深海蓝 `#065A82`
- **辅助色**：青绿色 `#1C7293`
- **强调色**：亮青色 `#02C39A`
- **背景**：浅灰白 `#F8F9FA`
- **字体**：标题用 Arial Black / Impact，正文用 Calibri Light

## 输出文件

- PPT 文件保存位置：`.claude/0415_vclaw_mock_e2e.pptx`

## 相关代码文件

- `tests/mock/e2e_framework.py`
- `tests/mock/layer_protocol.py`
- `tests/mock/layer_prompts.py`
- `tests/mock/test_cases.py`
- `tests/mock/run_e2e_tests.py`
- `tests/e2e/run_real_e2e_tests.py`
