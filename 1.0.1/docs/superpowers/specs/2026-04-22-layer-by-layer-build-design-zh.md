# VClaw 逐层构建设计

> **目标：** 通过接口优先对齐的方式，协调全部6层与其XML规范，然后以测试驱动和组件级XML分解独立构建每一层。

**方案：** 关键缺口优先（选项C）
- 第0阶段：锁定核心契约（`core/models.py`、`core/interfaces.py`）
- 第1阶段：修复6个打破层间契约的关键架构缺口
- 第2-7阶段：自下而上逐层构建，每层进行组件级XML分解
- 第8阶段：通过Mock端到端回归进行集成验证

**技术栈：** Python 3.11、Pydantic、pytest、Docker（L6）

---

## 第0阶段：锁定核心契约

在修改任何层之前，先将层间数据模型和抽象接口冻结为与XML规范完全一致。

**需要修改的文件：**
- `src/core/models.py` — StandardEvent、SessionContext、AgentAction、Observation、ExecutionResult等
- `src/core/interfaces.py` — MemoryInterface、ToolsInterface、RuntimeInterface
- `src/core/exceptions.py` — 层特定的异常层次结构

**关键决策：**

| 决策 | XML要求 | 代码当前状态 | 锁定为 |
|------|---------|-------------|--------|
| `RuntimeInterface` | 包含 `run_command(command, timeout)` | 只有 `run_code` | **添加 `run_command`** |
| `MemoryInterface.delete` | `document_id: str` | `document_ids: List[str]` | **保留 `List[str]`（批量是设计意图），更新XML** |
| `ExecutionResult.resource_usage` | `memory_peak`、`cpu_time` | 空 `{}` | **从Docker统计信息填充** |

**产出：** `docs/superpowers/specs/interfaces_lock.md` — 所有接口选择决策的记录日志。

---

## 第1阶段：修复6个关键架构缺口

这些缺口打破了层间契约。在构建功能之前修复它们可防止集成失败。

### 缺口1：L2未调用L3

**问题：** `ControlGateway.process_event()` 返回 `L3Input`，但从未调用 `L3.run()`。XML数据流规定L2编排L3→L5→L6循环，并将错误路由回L1。

**修复：**
- 向 `ControlGateway` 添加 `L3Orchestrator` 依赖注入
- 在 `process_event()` 中组装完 `L3Input` 后，调用 `l3.run(context)`
- 处理 `AgentAction`（路由到L5）或 `str`（直接响应）
- 出错时，包装为 `OrchestrationError` 并通过 `L1.ErrorHandler` 路由返回

**文件：** `src/l2/l2_control_gateway.py`

### 缺口2：L3安全守卫被绕过

**问题：** `Orchestration.run()` 实例化了 `SecurityGuard`，但从未调用 `classify()`。XML强制规定任何请求在进入ReActEngine、TaskPlanner、LLMManager或ToolCaller之前必须通过SecurityGuard。

**修复：**
- 在 `run()` 顶部调用 `security_guard.classify(user_input)`
- `dangerous` 路由到 `_handle_confirmation()`
- `rejected` 返回固定拒绝话术
- `normal` 继续进入ReActEngine

**文件：** `src/l3/l3_orchestration.py`

### 缺口3：L5工具执行器是存根

**问题：** `ToolExecutor.call_tool()` 返回占位 `Observation`。XML要求6步执行链：ToolRegistry → ParameterValidator → PermissionManager → ConfirmationManager → ToolExecutor → ResultFormatter，`python_repl`/`terminal` 需委派给L6。

**修复：**
- 在 `ToolsCapabilities.execute()` 中实现完整的6步链
- 对于 `python_repl`/`terminal` 工具，注入 `RuntimeInterface` 并调用 `run_code()`
- 通过 `ResultFormatter` 返回正确格式化的 `Observation`

**文件：** `src/l5/l5_tools_capabilities.py`、`src/l5/tool_executor.py`

### 缺口4：双工具系统

**问题：** `src/l5/` 和 `src/tools/` 是两个并行的工具系统，名称不同（`file_read` vs `file_reader`）、返回类型不同（`Observation` vs `ToolResult`）、接口也不同。

**修复：**
- 仅将匹配XML定义的工具（`file_read`、`file_write`、`search_web`、`python_repl`、`terminal`、`calculator`、`file_search`）迁移到 `src/l5/`
- 将返回类型统一为 `Observation`
- 更新 `ToolRegistry` 以注册迁移后的工具
- `src/tools/` 中的额外工具（`file_edit`、`glob`、`grep`、`web_fetch`、`todo_write`）不在当前XML规范内 — 移至 `src/l5/experimental/` 或移除

**文件：** `src/l5/`、`src/tools/`

### 缺口5：L3任务规划器被实例化但从未使用

**问题：** `Orchestration` 创建了 `TaskPlanner` 并存储 `current_plan`，但 `run()` 从未将计划输入 `ReActEngine`。

**修复：**
- 在ReAct循环之前调用 `task_planner.create_plan(user_input)`
- 将 `current_plan` 作为结构化上下文传入 `ReActEngine.run()`
- ReActEngine使用计划步骤来引导思考→行动选择

**文件：** `src/l3/l3_orchestration.py`、`src/l3/react_engine.py`

### 缺口6：L6执行日志记录器未使用

**问题：** `ExecutionLogger` 类存在，但 `RuntimeEnvironment.run_code()` 从未调用 `log()`。`resource_usage` 始终为空 `{}`。

**修复：**
- Docker执行完成后，调用 `execution_logger.log(result)`
- 从Docker容器统计API提取 `memory_peak` 和 `cpu_time`
- 填充 `ExecutionResult.resource_usage` 字典

**文件：** `src/l6/l6_runtime.py`

---

## 第2-7阶段：逐层构建（L4 → L6 → L5 → L3 → L2 → L1）

### 每层通用模式

每一层都遵循相同的5步流程：

```
1. 拆分XML → 组件级规范
2. 实现/协调 → 将代码对齐到规范
3. 单元测试 → 模拟所有依赖
4. 层集成测试 → 内部接线
5. 提交
```

### L4：记忆与知识（第2阶段）

**XML拆分为：**
- `docs/03_specs/l4/VectorStore.xml` — ChromaDB、FAISS、Memory后端
- `docs/03_specs/l4/EmbeddingService.xml` — OpenAI、Sentence Transformers
- `docs/03_specs/l4/TextChunker.xml` — Recursive、Token、Markdown分割器
- `docs/03_specs/l4/MemoryStore.xml` — 对话、知识、偏好存储
- `docs/03_specs/l4/IndexManager.xml` — 创建、更新、删除、优化索引
- `docs/03_specs/l4/CacheManager.xml` — LRU + TTL缓存
- `docs/03_specs/l4/integration.xml` — 数据流和调用边

**代码状态：** 最完整的层。主要工作：对齐CacheManager默认值（1000→10000）、添加Pinecone存根（抛出 `NotImplementedError`）、从统一 `MemoryStore` 中提取 `KnowledgeMemory`/`UserPreferenceMemory`。

**测试：** `tests/unit/l4/`、`tests/integration/l4/`

### L6：运行时环境（第3阶段）

**XML拆分为：**
- `docs/03_specs/l6/SandboxManager.xml` — 创建、管理、销毁沙箱
- `docs/03_specs/l6/ResourceLimiter.xml` — CPU、内存、时间、磁盘、网络限制
- `docs/03_specs/l6/CodeExecutor.xml` — 在沙箱中执行代码
- `docs/03_specs/l6/DockerController.xml` — Docker生命周期管理
- `docs/03_specs/l6/SecurityEnforcer.xml` — 语言白名单、禁止模式
- `docs/03_specs/l6/ExecutionLogger.xml` — 执行日志和指标
- `docs/03_specs/l6/integration.xml` — 数据流和调用边

**代码状态：** Docker路径很稳固。主要工作：接入ExecutionLogger、添加 `run_command`、填充 `resource_usage`。

**测试：** `tests/unit/l6/`、`tests/integration/l6/`

### L5：工具与能力（第4阶段）

**XML拆分为：**
- `docs/03_specs/l5/ToolRegistry.xml` — 注册、注销、列出工具
- `docs/03_specs/l5/ParameterValidator.xml` — 类型检查、路径安全、模式验证
- `docs/03_specs/l5/PermissionManager.xml` — 权限规则、通配符匹配
- `docs/03_specs/l5/ConfirmationManager.xml` — 待处理操作、TTL、确认提示
- `docs/03_specs/l5/ToolExecutor.xml` — 执行工具、委派给L6
- `docs/03_specs/l5/ResultFormatter.xml` — 按模板格式化结果
- `docs/03_specs/l5/BashAnalyzer.xml` — 命令分类、破坏性检测
- `docs/03_specs/l5/integration.xml` — 6步执行链

**代码状态：** 组件存在但ToolExecutor是存根，双工具系统未合并。

**测试：** `tests/unit/l5/`、`tests/integration/l5/`

### L3：编排（第5阶段）

**XML拆分为：**
- `docs/03_specs/l3/SecurityGuard.xml` — 分类、固定响应
- `docs/03_specs/l3/ReActEngine.xml` — 思考→行动→观察循环
- `docs/03_specs/l3/TaskPlanner.xml` — 计划创建、步骤跟踪
- `docs/03_specs/l3/LLMManager.xml` — 提供商管理、重试、流式
- `docs/03_specs/l3/ToolCaller.xml` — 调用L5工具
- `docs/03_specs/l3/MemoryAccessor.xml` — 从L4检索上下文
- `docs/03_specs/l3/ErrorTranslator.xml` — 错误类型映射、恢复建议
- `docs/03_specs/l3/integration.xml` — 带强制前置规则的ReAct循环

**代码状态：** 类存在但SecurityGuard未接线、TaskPlanner未使用、ToolCaller是存根。

**测试：** `tests/unit/l3/`、`tests/integration/l3/`

### L2：控制网关（第6阶段）

**XML拆分为：**
- `docs/03_specs/l2/SessionManager.xml` — 创建、获取、更新、过期会话
- `docs/03_specs/l2/RateLimiter.xml` — 令牌桶、用户/IP/全局三级限流
- `docs/03_specs/l2/ContextAssembler.xml` — 构建SessionContext
- `docs/03_specs/l2/HistoryRetriever.xml` — 从L4检索对话历史
- `docs/03_specs/l2/ToolPreparer.xml` — 按用户权限过滤工具
- `docs/03_specs/l2/integration.xml` — 包含L3调用的完整数据流

**代码状态：** 输入组装正常工作，但SessionManager未独立、L3未被调用、错误返回路径缺失。

**测试：** `tests/unit/l2/`、`tests/integration/l2/`

### L1：用户交互（第7阶段）

**XML拆分为：**
- `docs/03_specs/l1/ProtocolAdapter.xml` — Telegram、WebSocket、Webhook适配器
- `docs/03_specs/l1/DataValidator.xml` — 字段验证、注入检测
- `docs/03_specs/l1/EventNormalizer.xml` — 适配器选择、规范化
- `docs/03_specs/l1/ErrorHandler.xml` — 重试、退避、L3错误格式化
- `docs/03_specs/l1/integration.xml` — 载荷处理流水线

**代码状态：** 最成熟的层。主要工作：将ErrorHandler与XML职责对齐、移除SessionManager重复。

**测试：** `tests/unit/l1/`、`tests/integration/l1/`

---

## 第8阶段：集成验证

所有层构建完成后，验证完整流水线：

1. **相邻层集成测试**
   - L1→L2 载荷交接
   - L2→L3 带AgentAction路由的循环
   - L3→L5 工具调用委派
   - L5→L6 代码执行
   - L3→L4 记忆访问

2. **Mock端到端回归**
   - 针对新实现运行全部32个现有测试用例
   - 与 `final_regression` 基线对比结果
   - 目标：通过率零退化

3. **规则引擎检查**
   - 针对最终XML+代码运行 `rule_engine.py`
   - 目标：零R1-R7违规

---

## 测试策略

**单元测试：** 每个组件在隔离环境中测试，依赖项全部模拟。

**层集成测试：** 层内组件连接在一起，外部层通过 `core/interfaces.py` 抽象基类模拟。

**端到端测试：** 使用模拟LLM（确定性响应）的完整流水线，验证数据流。

**测试文件命名约定：**
- `tests/unit/l{层}/test_{组件}.py`
- `tests/integration/l{层}/test_l{层}_flow.py`
- `tests/e2e/test_tc_{编号}.py`

---

## 提交策略

第1阶段后每层一个提交：
- `feat(l4): 对齐XML规范、拆分XML、添加测试`
- `feat(l6): 对齐XML规范、拆分XML、添加测试`
- `feat(l5): 对齐XML规范、统一工具系统、添加测试`
- `feat(l3): 接入SecurityGuard、使用TaskPlanner、实现ToolCaller、添加测试`
- `feat(l2): 添加SessionManager、调用L3、路由错误、添加测试`
- `feat(l1): 对齐ErrorHandler、移除SessionManager重复、添加测试`

第0-1阶段作为一组前置提交：
- `chore(core): 锁定接口到XML契约`
- `fix(l2): 添加L3调用循环`
- `fix(l3): 将SecurityGuard接入强制前置门`
- `fix(l5): 实现ToolExecutor六步链、委派给L6`
- `refactor(l5): 将src/tools/合并到l5、统一名称和返回类型`
- `fix(l3): 将TaskPlanner输入ReActEngine`
- `fix(l6): 接入ExecutionLogger、填充resource_usage`
