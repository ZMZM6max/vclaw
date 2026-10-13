# Mock 驱动 XML 优化设计方案

**版本**: v1.0  
**日期**: 2026-04-16  
**目标**: 建立一套以 Mock E2E 测试结果为探测器、反向定位并优化 L1-L6 XML 架构文档的系统化方法论。

---

## 1. 背景与问题

### 1.1 Mock 系统的设计初衷
VClaw 的 Mock E2E 测试框架（`tests/mock/`）使用 6 个大模型分别模拟 L1-L6 层，目的是在理想环境下验证：框架是否能满足 PRD 描述的基本需求。测试用例（32 条）直接来源于 PRD，覆盖正常功能、异常处理、安全拦截、UX 体验等场景。

### 1.2 当前核心问题
经过对齐修复后，Mock 系统仍存在一个关键缺陷：**它是以"层"为粒度进行黑盒模拟的，无法精确追踪层内具体组件的执行状态。**

这导致：
- 当某个测试用例失败时，只能定位到"L2 输出异常"或"L3 决策错误"，但无法判断是 L2 内部的 `RateLimiter`、`SessionManager` 还是 `ToolPreparer` 出了问题。
- 当测试通过时，也无法确认中间组件（如 L4 的 `CacheManager`、L5 的 `PermissionManager`）是否真正生效，可能只是 LLM 的幻觉通过了语义校验。
- 无法将测试结果直接映射为 XML 文档中某个组件的增删改需求。

### 1.3 设计目标
本方案旨在解决上述问题，建立以下能力：
1. **组件级可追溯性**：Mock 测试结果能精确指向 L1-L6 中某个组件的设计缺陷。
2. **三方对齐机制**：确保 XML 规范、真实代码（`src/l*/`）、Mock 模拟三者的契约一致。
3. **闭环验证**：修改 XML 后，通过升级 Mock 提示词并重新跑测试，确认新架构能支撑测试通过。

---

## 2. 现状分析

### 2.1 各层保真度

| 层级 | XML 规范关键要求 | 真实实现 (`src/`) | Mock 系统 | 保真度 |
|------|------------------|-------------------|-----------|--------|
| **L1** | ProtocolAdapter, DataValidator, ErrorHandler, SessionManager | 完整实现 | LLM 模拟输出 StandardEvent | 高 |
| **L2** | RateLimiter(令牌桶), MemoryAccessor, ToolPreparer, UUID v4 会话 | 完整实现，含真实令牌桶 | LLM 模拟，无限流真实计算 | 中 |
| **L3** | ReAct Engine(≤5轮), TaskPlanner, LLMManager, 错误转译 | ReActEngine 完整；TaskPlanner 已写但未使用 | LLM 按 prompt 模拟 ReAct | 中偏低 |
| **L4** | VectorStore, EmbeddingService, TextChunker, MemoryStore, CacheManager | MemoryKnowledge 完整（mock/chroma/faiss 可选） | LLM 返回模拟记忆，无真实 embedding | 中偏低 |
| **L5** | ToolRegistry, ParameterValidator, PermissionManager, ConfirmationManager | ToolsCapabilities 完整，含路径安全、权限规则 | LLM 返回模拟 Observation，无真实校验 | 中偏低 |
| **L6** | DockerSandbox, SecurityEnforcer, ResourceLimiter, ExecutionLogger | RuntimeEnvironment 完整，Docker 隔离 | LLM 返回模拟执行结果，无真实沙盒 | 低 |

### 2.2 测试用例可验证性

- **可被 Mock 有效验证**（约 12 条）：主要依赖 L3 语义决策和最终回复质量，如安全拦截、模糊指令拒绝、错误转译、幻觉检测。
- **部分可验证但保真不足**（约 10 条）：流程能跑通，但无法验证真实物理结果。例如文件创建、跨轮次上下文、联网搜索。
- **基本无法验证**（约 10 条）：真实框架当前**缺失对应实现**：
  - **飞书集成**（TC-15/16/17/31）：L1 没有 FeishuAdapter。
  - **任务进度与取消**（TC-26/27）：`src/l5/task_manager.py` 存在但未被主流程集成，没有进度推送和中断机制。
  - **链式任务**（TC-30）：需要 TaskPlanner 或多步状态机，当前纯 ReAct 难以稳定完成。
  - **真实 OS 异常**（TC-22/24）：Mock 无法模拟文件占用、磁盘满等真实系统状态。

### 2.3 核心结论
Mock 系统擅长验证 **"在理想环境下，LLM 的语义决策是否符合 PRD 预期"**，但无法验证 **"真实组件的边界条件、状态持久化、权限机制、OS 交互是否正确"**。当 PRD 测试用例要求的功能在真实框架中完全不存在时，Mock 系统可能"假装"测试通过，掩盖架构缺口。

---

## 3. 总体方法论：混合迭代法（Hybrid Iterative）

整个优化过程分为 **3 轮迭代**，每轮有明确的输入、动作和输出。

### 第 1 轮：热修复冲刺（Failure-Driven Gap Analysis）

**目标**：让全部 P0 必过用例在 Mock 中通过，并产出高优先级 XML 缺陷清单。

**输入**：
- 修正对齐后的 Mock 系统（`tests/mock/`）
- 32 条测试用例（重点关注 P0_REQUIRED_SUITE 的 16 条）

**动作**：
1. 跑通 P0 用例，记录每条失败用例的根因。
2. 根因分类到 4 个象限：
   - **设计缺失**：XML 里没定义这个能力（如飞书集成、任务取消）。
   - **语义不足**：XML 定义了，但接口/提示词描述不够精确（如 L3 ReAct 的 Observation 处理规则）。
   - **流程断裂**：XML 定义的数据流和实际代码不一致（如 L3→L5→L3 的 Observation 闭环）。
   - **接口歧义**：XML 里接口参数、异常类型、返回值和真实代码对不上。
3. 对 L2/L3/L5 的 Mock Prompt 进行热修复，强制输出**结构化组件级 trace**（详见第 4 章）。

**输出**：
- `mock_results_round1.json`：P0 用例执行结果（含 component_trace）。
- `xml_gap_report_round1.md`：高优先级 XML 缺陷清单（每条缺陷关联到具体测试用例和 XML 章节）。
- 修复后的 `tests/mock/layer_prompts.py` 和 `layer_protocol.py`（增加 component_trace 字段）。

### 第 2 轮：架构契约审计（Contract Audit Loop）

**目标**：系统性地发现 XML 的结构性错位（过度规定、规定不足、矛盾规定）。

**输入**：
- 最新版 XML 文档（`docs/03_specs/L1-L6.xml`）
- 真实实现代码（`src/l*/`）
- 第 1 轮修复后的 Mock Prompts

**动作**：
1. **三方契约提取**：
   - 从 XML 提取：组件列表、接口签名、异常列表、数据流步骤。
   - 从代码提取：实际类、方法签名、抛出异常、依赖关系。
   - 从 Mock 提取：Prompt 中隐含的契约（工具列表、安全规则、输入输出假设）。
2. **三方 Diff 分析**：找出以下 3 类问题：
   - **过度规定**：XML 写了但代码没做（如 XML 中 L2 的 SessionManager 定义较完整，但代码里只是简单 dict）。
   - **规定不足**：代码做了但 XML 没提（如 L5 的 `BashAnalyzer`、L3 的错误转译逻辑）。
   - **矛盾规定**：XML 和代码/Mock 都不一致（如之前 session_id 格式问题）。
3. **关键结构性问题排查**：
   - L3 的 `TaskPlanner`：XML 有，代码里闲置。需要裁决：是 XML 降级删除，还是代码补全整合？
   - L5 的 `BashAnalyzer`：代码里有，XML 描述不足。需要补充到 `L5_ToolsCapabilities.xml`。
   - L2 的认证检查：`tests/integration/test_integration.py` 里明确注释 "Authentication removed"，但 XML 仍在提。需要同步删除。
   - L6 的 `ExecutionLogger`：代码里只有基础 logging，XML 定义较完整。需要判断是否需要降级。

**输出**：
- `contract_audit_report.md`：三方 diff 的完整分析报告。
- `xml_refactor_plan.md`：XML 结构性重构建议（含组件增删、接口调整、异常边界明确化）。

### 第 3 轮：Mock 升级与闭环验证

**目标**：根据重构后的 XML，升级 Mock 系统，使其成为"对齐新架构的理想参照系"，并补充测试覆盖。

**输入**：
- 重构后的 XML 文档
- 真实的 `src/l*/` 代码（如需同步修改）

**动作**：
1. **升级 Mock Prompts**：
   - 新增/删除的组件必须在对应层的 Prompt 中有明确体现。
   - 每个 Prompt 必须包含"当收到 XXX 输入时，YYY 组件应如何处理"的示例。
   - 明确组件间的调用顺序，使 Mock LLM 的输出尽量贴近真实代码逻辑。
2. **补充测试用例**：针对第 2 轮发现的 XML 边界条件，编写新的 Mock E2E 用例。
3. **全量回归测试**：跑全部 32 条 + 新增用例，验证闭环。

**输出**：
- 升级后的 `tests/mock/layer_prompts.py`
- 新版测试用例 `tests/mock/test_cases.py`
- `mock_final_report.md`：最终验证报告，明确哪些测试用例能验证真实框架，哪些只能验证理想语义。

---

## 4. 关键技术升级：结构化组件级 Trace

### 4.1 问题定义
当前 Mock 系统以"层"为粒度模拟，无法定位层内具体组件。这是用 Mock 结果反向优化 XML 的最大瓶颈。

### 4.2 解决方案：强制 LLM 输出组件执行状态表

**协议层修改**（`tests/mock/layer_protocol.py`）：

在每个层的 Output 结构里增加 `component_trace` 字段：

```python
class ComponentTraceItem(BaseModel):
    component: str = Field(..., description="组件名称")
    status: str = Field(..., description="success / skipped / error")
    reason: Optional[str] = Field(None, description="状态说明")
    output_summary: Optional[str] = Field(None, description="输出摘要")

class L2Output(BaseModel):
    status: LayerStatus
    session_context: Optional[SessionContext] = None
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)  # 新增
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    rate_limit: Optional[RateLimitInfo] = None
    processing_log: List[str] = Field(default_factory=list)
```

同理，为 `L1Output`、`L3Output`、`L4SearchOutput`、`L5Output`、`L6Output` 都增加 `component_trace`。

**Prompt 层修改**（`tests/mock/layer_prompts.py`）：

在每个层的 system prompt 末尾增加强制规则：

```text
【组件追踪要求】
你在处理请求时，必须按顺序“执行”以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. RateLimiter - 限流检查
2. SessionManager - 会话管理
3. MemoryAccessor - 记忆检索
4. ToolPreparer - 工具准备
5. ContextAssembler - 上下文组装

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
```

### 4.3 Trace 驱动的 XML 优化映射表

有了 `component_trace` 后，"测试失败 → XML 优化"的映射将非常直接：

| Mock 测试失败现象 | Component Trace 定位 | 对应的 XML 优化动作 |
|------------------|---------------------|---------------------|
| TC-06 删除未触发二次确认 | L3:SecurityGuard → status: skipped | 在 `L3_Orchestration.xml` 的 SecurityGuard 组件里明确增加"删除操作需触发 confirmation_required"规则 |
| TC-14 断网后报错含技术术语 | L3:ErrorTranslator → status: error / 未调用 | 在 `L3_Orchestration.xml` 里新增 ErrorTranslator 组件的职责定义和输入输出规范 |
| TC-11 跨轮次指代失败 | L4:MemoryStore → history 为空 | 在 `L4_MemoryKnowledge.xml` 的 MemoryStore 接口里明确 `retrieve_history` 的上下文窗口和会话隔离规则 |
| TC-26 长任务无进度反馈 | L3:TaskPlanner → status: skipped | 在 `L3_Orchestration.xml` 里明确 TaskPlanner 需识别 long_running 任务并触发 progress notification |
| TC-20 恶意代码未拦截 | L3:SecurityGuard → status: success（错误地允许了） | 在 `L3_Orchestration.xml` 的 SecurityGuard 安全策略列表里补充"禁止生成/执行破坏性代码"的明确示例 |

---

## 5. 裁决规则：改 XML 还是改代码？

在三方对齐过程中，经常会遇到"实现偷懒但 XML 更合理"的争议。建立以下裁决规则：

### 5.1 应该修改 XML 的情况
1. **XML 超前于当前阶段**：XML 里定义了 Phase 2/3 的功能（如会话恢复、多会话管理），但真实代码只实现了 Phase 1。
   - **裁决**：在 XML 中增加 `implementation_phase` 标记，明确哪些组件是当前已实现，哪些是规划中。
2. **XML 接口和代码实现矛盾，但代码是正确的**：例如 XML 要求 session_id 为时间戳格式，但代码已正确实现为 UUID v4。
   - **裁决**：修改 XML 以匹配代码。
3. **XML 缺少关键安全/异常边界**：测试发现某类异常没有对应处理流程，代码里也没写。
   - **裁决**：先在 XML 中补全设计，再决定是否在下个迭代排期实现代码。

### 5.2 应该修改代码的情况
1. **XML 定义合理且已稳定，但代码未实现或实现错误**：例如 L3 的 `TaskPlanner` 在 XML 中已有明确设计，但代码里完全未使用。
   - **裁决**：代码需要补全实现。但如果当前排期不允许，可在 XML 中标记为 `implemented=false`。
2. **代码实现违反了 XML 中明确的安全规则**：例如 XML 要求 file_delete 必须二次确认，但代码中某条路径绕过了确认。
   - **裁决**：修复代码，保持 XML 不变。

### 5.3 应该同时修改的情况
1. **XML 和代码都有部分道理，但需要统一**：例如 L5 的权限检查，XML 定义了一种规则引擎，代码里用 `PermissionManager` 实现了另一种。
   - **裁决**：选择其中一种作为标准，同时修改 XML 和代码使其对齐。

---

## 6. 工具与自动化

### 6.1 映射表模板
每个测试用例的验证结果应按以下结构记录：

```yaml
test_case: TC-06
name: 删除单一重要文件
status: failed  # passed / failed / skipped / unverifiable
layer_of_failure: L3
component_of_failure: SecurityGuard
failure_category: 语义不足
xml_reference: docs/03_specs/L3_Orchestration.xml#SecurityGuard
xml_action: 增加"文件删除操作必须触发二次确认"的明确规则
needs_code_change: false
needs_mock_upgrade: true
notes: Mock L3 Prompt 中缺少对"删除操作确认机制"的明确示例
```

### 6.2 自动化脚本建议
在第 1 轮和第 3 轮中，可开发辅助脚本：
- `scripts/analyze_mock_results.py`：读取 `test_report.json`，自动提取 `component_trace` 中为 `error` 或 `skipped` 的条目，并按组件聚合失败次数。
- `scripts/xml_gap_mapper.py`：输入测试用例 ID 和组件名，自动查找对应 XML 文件中的相关章节，生成 diff 建议。

---

## 7. 风险与限制

1. **LLM 幻觉风险**：即使强制要求 `component_trace`，LLM 仍可能虚构未执行组件的状态。需要配合 `verify_layer_prompts.py` 进行格式校验，并对关键失败进行人工复核。
2. **无法验证物理状态**：Mock L6 无法真正执行 Docker 沙盒，因此 TC-20/21 等安全测试只能验证"L3/L5 是否按规则拒绝了"，无法验证沙盒是否真正防住了攻击。这类测试的 XML 优化结论需要参考真实 L6 的单测结果。
3. **未实现功能的虚假通过**：如果 Mock LLM 非常"听话"，它可能在没有真实组件支撑的情况下也输出"正确"结果。必须通过 component_trace 中的 `skipped` 状态来发现这类问题。

---

## 8. 执行计划摘要

| 轮次 | 周期 | 核心动作 | 产出物 |
|------|------|----------|--------|
| 第 1 轮 | 1-2 天 | P0 热修复 + 增加 component_trace | P0 通过 + 高优先级 XML 缺陷清单 |
| 第 2 轮 | 2-3 天 | 三方契约审计 | 架构审计报告 + XML 重构计划 |
| 第 3 轮 | 2-3 天 | 升级 Mock Prompts + 补充用例 + 回归 | 最终验证报告 + 对齐的 XML 文档 |

---

## 9. 验收标准

本方案成功的标准是：
1. Mock 测试结果能精确到具体组件（通过 `component_trace`）。
2. 每个失败的测试用例都能映射到 XML 的某个可修改点（组件、接口、数据流或异常定义）。
3. 经过 3 轮迭代后，XML 文档和真实代码的契约差异清单为空（或全部标记为 `implementation_phase` 延后）。
4. P0 必过用例在 Mock 系统中 100% 通过，且有明确的 component_trace 证明各关键组件生效。
