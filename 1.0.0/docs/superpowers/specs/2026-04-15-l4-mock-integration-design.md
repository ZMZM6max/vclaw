# Mock E2E 框架 L4 记忆层集成设计文档

**日期**: 2026-04-15  
**作者**: Claude  
**状态**: 待实现  
**方案**: 混合增强方案 (方案 C)

---

## 1. 背景与问题

当前 `tests/mock/` 和 `tests/e2e/` 中的端到端测试框架使用 6 个真实 LLM 分别模拟 VClaw 的 L1-L6 层。但在实际执行流程中，**L4（记忆与知识层）被完全跳过**：

- `EndToEndRunner.run()` 的执行链为 `L1 → L2 → L3 → L5 → L6 → L5 → L3 → L2 → L1`，没有 `_run_l4()` 调用。
- L2 的 `relevant_memories` 和 `history` 完全由 LLM 凭空调造，没有基于任何真实的向量检索或历史存储。
- 这意味着涉及跨轮次上下文指代（如 TC-11）的测试用例无法得到真实验证。

### 1.1 现状数据流

```
User Request
    ↓
L1 → StandardEvent
    ↓
L2 → SessionContext (relevant_memories = LLM 幻想)
    ↓
L3 → AgentAction / DirectResponse
    ↓
L5/L6 → 工具执行
    ↓
L3 → 最终回复
    ↓
L2/L1 → 返回给用户
```

### 1.2 目标数据流

```
User Request
    ↓
L1 → StandardEvent
    ↓
L2 ─┬─→ L4.retrieve_history() ──→ 真实历史记录
    ├─→ L4.search() ────────────→ 真实记忆片段
    └─→ LLM 基于真实数据组装 SessionContext
    ↓
L3 → AgentAction / DirectResponse
    ↓
L5/L6 → 工具执行
    ↓
L3 → 最终回复
    ↓
L2 ─┬─→ L4.store_conversation() → 持久化本轮 Q&A
    └─→ L1 → 返回给用户
```

---

## 2. 设计原则

本方案采用**混合增强方案（方案 C）**，核心原则如下：

1. **L4 必须真实工作**：调用 `src.l4.MemoryKnowledge` 的真实实现进行历史存储、检索和向量搜索。
2. **LLM 仍负责编排**：L2/L3 的 LLM 负责决定如何使用 L4 返回的数据，而不是被绕过。
3. **零外部依赖**：L4 使用 `mock` embedding + `in-memory` vector store / memory store，不需要 API Key 或本地文件。
4. **对测试运行器透明**：`run_e2e_tests.py` 和 `run_real_e2e_tests.py` 不需要任何改动。

---

## 3. 架构设计

### 3.1 L4 在三个关键触点的行为

| 触点 | 触发位置 | 调用方法 | 输入 | 输出用途 |
|------|----------|----------|------|----------|
| **历史检索** | `_run_l2()` 开始时 | `memory.retrieve_history(session_id, limit=10)` | `session_id` | 注入 L2 Prompt 的 `real_conversation_history` |
| **记忆搜索** | `_run_l2()` 开始时 | `memory.search(current_query, top_k=3)` | `current_query` | 注入 L2 Prompt 的 `real_search_results` |
| **历史存储** | 获得 `final_response` 后 | `memory.store_conversation(session_id, [Q, A])` | 本轮对话 | 持久化到 L4，供下一轮检索 |

### 3.2 EndToEndRunner 内部变化

#### 新增 L4 实例
```python
from src.l4.config.l4_config import get_l4_memory_development

class EndToEndRunner:
    def __init__(self, llm_configs, output_dir=None):
        # ... existing code ...
        self.memory = get_l4_memory_development()  # Mock + In-Memory
```

#### L2 输入增强
在 `_run_l2()` 中，先调用真实 L4，再把结果传给 LLM：

```python
def _run_l2(self, standard_event):
    user_id = standard_event["user_id"]
    query = standard_event["content"]
    session_id = f"session_{user_id}_{int(time.time())}"

    # 调用真实 L4
    history = self.memory.retrieve_history(session_id, limit=10)
    search_results = self.memory.search(query, top_k=3)

    l2_input = {
        "standard_event": standard_event,
        "client_ip": "127.0.0.1",
        "available_tools_from_l5": self._get_l5_tools(),
        "real_conversation_history": history,
        "real_search_results": search_results,
    }
    return self.simulators["L2"].execute(l2_input)
```

#### 对话回写
在 `run()` 方法的最后，统一调用 `store_conversation`：

```python
# 在 final_response 确定后
self.memory.store_conversation(
    session_id,
    [
        {"role": "user", "content": session_context["current_query"]},
        {"role": "assistant", "content": final_response}
    ]
)
```

### 3.3 L2 Prompt 增强

在 `layer_prompts.py` 的 `L2_PROMPT` 中新增以下说明：

```markdown
【新增输入字段】
- `real_conversation_history`: 从 L4 层检索到的真实对话历史（OpenAI 格式列表）
- `real_search_results`: 从 L4 层检索到的与当前查询相关的记忆片段列表

【历史记录生成规则 - 更新】
1. 如果 `real_conversation_history` 非空，必须优先将其作为 `session_context.history` 的值。
2. 如果为空列表，可以基于上下文连贯性生成模拟历史。
3. `relevant_memories` 应优先从 `real_search_results` 中提取和概括，不要编造。
4. 在 `processing_log` 中必须记录：
   - "[X] 历史检索: 从 L4 获取 N 条历史记录"
   - "[Y] 记忆检索: 从 L4 获取 M 条相关记忆"
```

---

## 4. 文件修改清单

| 文件 | 修改类型 | 修改内容 |
|------|----------|----------|
| `tests/mock/e2e_framework.py` | 修改 | 1. 导入 `get_l4_memory_development`<br>2. `EndToEndRunner.__init__()` 中实例化 `self.memory`<br>3. `_run_l2()` 中调用 `retrieve_history` 和 `search`<br>4. 在 `run()` 末尾调用 `store_conversation` |
| `tests/mock/layer_prompts.py` | 修改 | 更新 `L2_PROMPT`，增加 `real_conversation_history` 和 `real_search_results` 字段说明及使用规则 |
| `tests/mock/layer_protocol.py` | 可选修改 | 更新 `EndToEndFlow.example_flow()`，在 L2 和 L3 之间明确加入 L4 调用步骤 |
| `tests/mock/run_e2e_tests.py` | 无需修改 | 对 `TestRunner` 透明 |
| `tests/e2e/run_real_e2e_tests.py` | 无需修改 | 对 `RealLLMTestExecutor` 透明 |

---

## 5. 数据流示例

### 5.1 单轮对话（无历史）

```
用户: "计算 Fibonacci(10)"
L4.retrieve_history("session_test_001_...") → []  # 空历史
L4.search("计算 Fibonacci(10)") → []  # 无相关记忆
L2 Prompt 包含 real_conversation_history=[] 和 real_search_results=[]
L2 LLM 生成 history=[], relevant_memories=[]
L3 决定调用 calculator
L5/L6 执行并返回 55
L3 生成最终回复: "Fibonacci(10) = 55"
L4.store_conversation(session_id, [user_msg, assistant_msg]) → 成功
```

### 5.2 多轮对话（有历史）

```
第1轮: "帮我建个文件叫 test.txt"
... L4 存储了该对话 ...

第2轮（同 session_id）: "把它删掉"
L4.retrieve_history(session_id) → [
    {"role": "user", "content": "帮我建个文件叫 test.txt"},
    {"role": "assistant", "content": "已经为您建好 test.txt"}
]
L4.search("把它删掉") → ["用户之前要求创建 test.txt"]
L2 Prompt 包含真实历史和记忆
L2 LLM 正确组装上下文，L3 理解 "它" 指代 test.txt
L3 生成删除文件的 AgentAction
```

---

## 6. 测试验证计划

实现完成后，通过以下方式验证：

1. **运行 TC-11（跨轮次上下文指代）**
   - 验证 L3 能否基于 L4 存储的真实历史正确理解 "它" 的指代。

2. **手动运行两轮对话测试**
   - 使用同一个 `session_id` 发送两条消息。
   - 第二轮消息依赖第一轮上下文，验证 `retrieve_history` 是否生效。

3. **隔离性测试**
   - 使用不同 `session_id` 发送消息，确保不会读到其他 session 的历史。

4. **运行 P0 套件回归**
   - 确保新增 L4 调用不会破坏现有可自动化用例。

---

## 7. 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| `src.l4` 导入失败 | 高 | 使用 `try/except ImportError` 优雅降级，回退到当前的纯 LLM 模拟模式 |
| L2 LLM 不遵循新 Prompt 规则 | 中 | 在 Prompt 中强调 "必须优先使用" 和 "不要编造"，并在 `_run_l2` 中对 LLM 输出做后校验 |
| 多测试用例间记忆污染 | 中 | 每个用例使用基于 `user_id` 和 `timestamp` 的独立 `session_id`；如需完全隔离，可在 `EndToEndRunner` 中提供 `reset_memory()` 选项 |
| Mock Embedding 性能问题 | 低 | Mock Embedding 是确定性哈希生成，性能开销极小 |

---

## 8. 后续可选增强

- **预置知识库**：在 `EndToEndRunner.__init__()` 中预置一些文档（如"用户偏好 PDF 格式"），让 `search` 在特定测试用例中有更相关的返回。
- **记忆截断可视化**：在 `test_report.md` 中显示 L4 检索到的原始记忆，方便调试。
- **Session 持久化**：当前使用 in-memory store，如需跨进程共享，可切换为 `FileMemoryStore`。

---

## 9. 结论

通过本设计，Mock E2E 框架将从 "L4 被跳过" 的状态演进为 "L4 真实参与但 LLM 主导编排" 的状态。这不仅能更准确验证跨轮次上下文、用户偏好记忆等场景，也保持了框架的轻量级和零外部依赖特性。
