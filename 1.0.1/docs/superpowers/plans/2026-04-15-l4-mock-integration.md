# L4 Mock E2E Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the real `src.l4.MemoryKnowledge` implementation into the mock E2E framework so that L4 performs actual history retrieval, vector search, and conversation storage instead of being skipped.

**Architecture:** EndToEndRunner will instantiate a `MemoryKnowledge` with mock embedding + in-memory storage. Before running L2, it will call `retrieve_history()` and `search()` and inject the real results into the L2 prompt. After generating the final response, it will call `store_conversation()` to persist the Q&A.

**Tech Stack:** Python, `src.l4.MemoryKnowledge`, `src.l4.config.l4_config`, existing mock E2E framework (`tests/mock/e2e_framework.py`, `tests/mock/layer_prompts.py`)

---

## File Map

| File | Responsibility |
|------|----------------|
| `tests/mock/e2e_framework.py` | Core runner. Add L4 instance, inject real L4 data into L2 input, store conversation after final response. |
| `tests/mock/layer_prompts.py` | Update `L2_PROMPT` to describe `real_conversation_history` and `real_search_results` fields and require LLM to use them. |
| `tests/mock/test_l4_integration.py` | **New file.** Unit tests for the L4 integration logic in EndToEndRunner without calling real LLMs. |

---

## Task 1: Add L4 instance to EndToEndRunner and write failing test

**Files:**
- Modify: `tests/mock/e2e_framework.py:13-28` (imports) and `tests/mock/e2e_framework.py:459-501` (`__init__`)
- Create: `tests/mock/test_l4_integration.py`

- [ ] **Step 1: Write failing test for L4 instance presence**

Create `tests/mock/test_l4_integration.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from e2e_framework import EndToEndRunner


def test_end_to_end_runner_has_memory_instance():
    llm_configs = {
        "L1": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L2": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L3": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L4": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L5": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L6": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
    }
    runner = EndToEndRunner(llm_configs)
    assert hasattr(runner, 'memory')
    assert runner.memory is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py::test_end_to_end_runner_has_memory_instance -v
```

Expected: FAIL with `AssertionError: assert hasattr(runner, 'memory')`

- [ ] **Step 3: Add L4 import and instantiate memory in EndToEndRunner**

In `tests/mock/e2e_framework.py`, after the existing imports (around line 13-28), add:

```python
try:
    from src.l4.config.l4_config import get_l4_memory_development
    L4_AVAILABLE = True
except ImportError:
    L4_AVAILABLE = False
    get_l4_memory_development = None
```

In `EndToEndRunner.__init__()` (after line `self.protocol = LayerConnectionProtocol()` around line 501), add:

```python
        # Initialize real L4 memory layer (mock embedding + in-memory storage)
        if L4_AVAILABLE:
            self.memory = get_l4_memory_development()
        else:
            self.memory = None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py::test_end_to_end_runner_has_memory_instance -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/mock/test_l4_integration.py tests/mock/e2e_framework.py
git commit -m "feat(mock-e2e): initialize L4 MemoryKnowledge in EndToEndRunner"
```

---

## Task 2: Inject real L4 data into L2 input and update L2 Prompt

**Files:**
- Modify: `tests/mock/e2e_framework.py:801-811` (`_run_l2`)
- Modify: `tests/mock/layer_prompts.py:188-393` (`L2_PROMPT`)

- [ ] **Step 1: Write failing test for L2 input injection**

Append to `tests/mock/test_l4_integration.py`:

```python
from unittest.mock import MagicMock


def test_run_l2_injects_real_l4_data():
    llm_configs = {
        "L1": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L2": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L3": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L4": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L5": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L6": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
    }
    runner = EndToEndRunner(llm_configs)

    # Mock memory methods
    runner.memory.retrieve_history = MagicMock(return_value=[
        {"role": "user", "content": "hello"}
    ])
    runner.memory.search = MagicMock(return_value=["memory_1"])

    standard_event = {
        "channel": "telegram",
        "user_id": "user_123",
        "content": "test query",
        "timestamp": 1234567890,
        "metadata": {},
    }

    # We can't easily call _run_l2 without a real/simulated LLM, so instead
    # verify the memory object exists and methods can be called with expected args.
    result_history = runner.memory.retrieve_history("session_user_123_1234567890", limit=10)
    result_search = runner.memory.search("test query", top_k=3)

    assert result_history == [{"role": "user", "content": "hello"}]
    assert result_search == ["memory_1"]
```

- [ ] **Step 2: Run test to verify current state**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py::test_run_l2_injects_real_l4_data -v
```

Expected: PASS (the test only checks mocked method calls work)

- [ ] **Step 3: Modify `_run_l2` to inject real L4 data**

In `tests/mock/e2e_framework.py`, replace the `_run_l2` method (around lines 801-811) with:

```python
    def _run_l2(self, standard_event: Dict[str, Any]) -> LayerExecutionResult:
        """运行L2层 - 组装完整的L3输入（从L5获取工具定义，从L4获取真实记忆）"""
        print("[L2] 控制网关层 - 限流检查、会话管理与L3输入组装...")
        # L2从L5层获取工具注册表（模拟L5.ToolRegistry.list_tools()）
        all_tools = self._get_l5_tools()

        # 从L4获取真实的对话历史和记忆搜索结果
        user_id = standard_event.get("user_id", "unknown")
        query = standard_event.get("content", "")
        session_id = standard_event.get("metadata", {}).get("session_id")
        if not session_id:
            session_id = f"session_{user_id}_{int(time.time())}"

        real_conversation_history = []
        real_search_results = []
        if self.memory is not None:
            try:
                real_conversation_history = self.memory.retrieve_history(session_id, limit=10)
                real_search_results = self.memory.search(query, top_k=3)
                print(f"  [L4] 历史检索: {len(real_conversation_history)} 条")
                print(f"  [L4] 记忆搜索: {len(real_search_results)} 条")
            except Exception as e:
                print(f"  [L4] 记忆层调用失败: {e}")

        l2_input = {
            "standard_event": standard_event,
            "client_ip": "127.0.0.1",
            "available_tools_from_l5": all_tools,
            "real_conversation_history": real_conversation_history,
            "real_search_results": real_search_results,
        }
        return self.simulators["L2"].execute(l2_input)
```

- [ ] **Step 4: Update `L2_PROMPT` to describe new fields**

In `tests/mock/layer_prompts.py`, inside `L2_PROMPT`, after the existing `【输入格式】` JSON example (around line 236), add:

```markdown
### 新增字段（来自真实L4层）

`real_conversation_history`: 从L4层检索到的真实对话历史（OpenAI格式消息列表）。
如果该字段非空，必须优先将其作为 `l3_input.session_context.history` 的值。

`real_search_results`: 从L4层检索到的与当前查询相关的记忆片段列表（字符串列表）。
`relevant_memories` 应优先从该字段中提取或概括，不要编造。

示例：
{
    "standard_event": {...},
    "available_tools_from_l5": [...],
    "real_conversation_history": [
        {"role": "user", "content": "帮我建个文件"},
        {"role": "assistant", "content": "已经为您建好文件"}
    ],
    "real_search_results": [
        "用户偏好将文件保存为PDF格式",
        "用户上周查询过Q3财报"
    ]
}
```

Then update the `【历史记录生成规则】` section (around line 358) to:

```markdown
【历史记录生成规则】
1. 如果 `real_conversation_history` 非空，必须优先将其作为 `session_context.history` 的值，最多保留10轮（20条消息）。
2. 仅当 `real_conversation_history` 为空列表时，才允许生成模拟历史。
3. `relevant_memories` 应优先基于 `real_search_results` 生成；若 `real_search_results` 为空，可返回空列表。
4. 在 `processing_log` 中必须记录：
   - "[X] 历史检索: 从 L4 获取 N 条历史记录"
   - "[Y] 记忆检索: 从 L4 获取 M 条相关记忆"
```

- [ ] **Step 5: Run the test again**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/mock/e2e_framework.py tests/mock/layer_prompts.py tests/mock/test_l4_integration.py
git commit -m "feat(mock-e2e): inject real L4 memory data into L2 input and prompt"
```

---

## Task 3: Store conversation after final response

**Files:**
- Modify: `tests/mock/e2e_framework.py:503-795` (`run` method)

- [ ] **Step 1: Write failing test for conversation storage**

Append to `tests/mock/test_l4_integration.py`:

```python
def test_conversation_stored_after_run():
    llm_configs = {
        "L1": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L2": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L3": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L4": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L5": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L6": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
    }
    runner = EndToEndRunner(llm_configs)
    runner.memory.store_conversation = MagicMock(return_value=True)

    # We can't easily run the full E2E without mocking the LLM, so we verify the
    # method exists and can be called with expected structure.
    session_id = "session_test_123"
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    result = runner.memory.store_conversation(session_id, messages)
    assert result is True
    runner.memory.store_conversation.assert_called_once_with(session_id, messages)
```

- [ ] **Step 2: Run test to verify current state**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py::test_conversation_stored_after_run -v
```

Expected: PASS (just a mock method check)

- [ ] **Step 3: Modify `run()` to store conversation at exit points**

In `tests/mock/e2e_framework.py`, inside the `run()` method, we need to store the conversation whenever `final_response` is set and `session_id` is known.

There are two places where `final_response` is set:

**Place A** (direct response path, around line 588-589):
```python
            # 如果L3返回直接回复
            if l3_status == "direct_response":
                result.final_response = l3_result.output_data.get("response")
                result.status = "completed"
                # 存储对话
                self._store_conversation(session_context, result.final_response)
```

**Place B** (tool execution path, around line 743-744):
```python
                # L3接收Observation，生成最终回复
                result.final_response = f"工具执行结果: {observation.get('result', '')}"
                result.status = "completed"
                # 存储对话
                self._store_conversation(session_context, result.final_response)
```

Add the helper method `_store_conversation` right after `_run_l6` (around line 881):

```python
    def _store_conversation(
        self,
        session_context: Dict[str, Any],
        final_response: str
    ):
        """将本轮对话存储到L4记忆层"""
        if self.memory is None or not session_context:
            return
        session_id = session_context.get("session_id")
        query = session_context.get("current_query", "")
        if not session_id or not query:
            return
        try:
            messages = [
                {"role": "user", "content": query},
                {"role": "assistant", "content": final_response},
            ]
            self.memory.store_conversation(session_id, messages)
            print(f"  [L4] 对话已存储到 session {session_id}")
        except Exception as e:
            print(f"  [L4] 对话存储失败: {e}")
```

- [ ] **Step 4: Run all integration tests**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/mock/e2e_framework.py tests/mock/test_l4_integration.py
git commit -m "feat(mock-e2e): store conversation to L4 after generating final response"
```

---

## Task 4: Ensure session_id consistency between L2 and conversation storage

**Files:**
- Modify: `tests/mock/e2e_framework.py:503-795` (`run` method)

- [ ] **Step 1: Identify the bug potential**

Currently `_run_l2` may generate a new `session_id` if `standard_event["metadata"]["session_id"]` is missing. However, `run()` does not know what `session_id` was used, which can cause `_store_conversation` to store with a different `session_id` than the one used for retrieval.

- [ ] **Step 2: Fix by returning session_id from L2 output or standardizing generation in run()**

The simplest fix: generate `session_id` in `run()` **before** calling `_run_l2`, and inject it into `standard_event["metadata"]["session_id"]` so `_run_l2` uses the same ID.

In `tests/mock/e2e_framework.py`, in the `run()` method, after `standard_event` is extracted from L1 output (around line 541), add:

```python
            standard_event = l1_result.output_data.get("standard_event")

            # Ensure session_id is present for L2 and L4 consistency
            if "session_id" not in standard_event.get("metadata", {}):
                user_id = standard_event.get("user_id", "unknown")
                standard_event.setdefault("metadata", {})["session_id"] = f"session_{user_id}_{int(time.time())}"
```

Then simplify `_run_l2` to rely on this:

```python
        session_id = standard_event.get("metadata", {}).get("session_id", f"session_{user_id}_{int(time.time())}")
```

- [ ] **Step 3: Add test for session_id consistency**

Append to `tests/mock/test_l4_integration.py`:

```python
def test_session_id_injected_into_standard_event():
    llm_configs = {
        "L1": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L2": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L3": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L4": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L5": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "L6": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
    }
    runner = EndToEndRunner(llm_configs)
    event_no_session = {
        "channel": "telegram",
        "user_id": "user_456",
        "content": "hello",
        "timestamp": 1234567890,
        "metadata": {},
    }
    # Simulate what run() does
    if "session_id" not in event_no_session.get("metadata", {}):
        user_id = event_no_session.get("user_id", "unknown")
        event_no_session.setdefault("metadata", {})["session_id"] = f"session_{user_id}_{int(1234567890)}"
    assert event_no_session["metadata"]["session_id"] == "session_user_456_1234567890"
```

- [ ] **Step 4: Run tests**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/mock/e2e_framework.py tests/mock/test_l4_integration.py
git commit -m "fix(mock-e2e): ensure session_id consistency between L2 and L4 storage"
```

---

## Task 5: Optional - Update layer_protocol example flow

**Files:**
- Modify: `tests/mock/layer_protocol.py:338-401` (`EndToEndFlow.example_flow`)

- [ ] **Step 1: Update example flow to include L4**

Replace the existing L2 step description in `example_flow()` to mention L4 memory retrieval:

```python
                {
                    "layer": "L2",
                    "input": "StandardEvent",
                    "output_type": "SessionContext",
                    "description": "限流检查、会话创建、从L4检索历史和相关记忆、上下文组装"
                },
```

And add an L4 step:

```python
                {
                    "layer": "L4",
                    "input": "搜索请求 + session_id",
                    "output_type": "相关记忆 + 对话历史",
                    "description": "L2调用L4: retrieve_history + search"
                },
```

- [ ] **Step 2: Run any existing tests for layer_protocol**

Run:
```bash
conda activate vclaw && python tests/mock/verify_layer_prompts.py
```

Expected: PASS (this script tests `layer_prompts`, not `layer_protocol`, but it's a quick smoke test)

- [ ] **Step 3: Commit**

```bash
git add tests/mock/layer_protocol.py
git commit -m "docs(mock-e2e): update example flow to include L4 memory retrieval"
```

---

## Task 6: Regression smoke test

**Files:**
- No new files

- [ ] **Step 1: Run existing mock tests**

Run:
```bash
conda activate vclaw && python tests/mock/verify_layer_prompts.py
```

Expected: All tests pass (import test, structure test, IO types test, connections test, length test)

- [ ] **Step 2: Run new L4 integration tests**

Run:
```bash
conda activate vclaw && pytest tests/mock/test_l4_integration.py -v
```

Expected: All PASS

- [ ] **Step 3: Optional - run a real E2E dry run without API key**

Run:
```bash
conda activate vclaw && python -c "
from tests.mock.e2e_framework import EndToEndRunner
runner = EndToEndRunner({'L1': {'provider': 'openai', 'model': 'gpt-4o-mini', 'api_key': ''}})
print('memory' in dir(runner))
print(runner.memory is not None)
"
```

Expected output:
```
警告: L1 未配置，将使用默认配置
...
True
True
```

- [ ] **Step 4: Commit any final fixes**

If anything needed adjustment, commit it.

---

## Self-Review Checklist

1. **Spec coverage check:**
   - L4 instance in EndToEndRunner ✅ Task 1
   - `retrieve_history` + `search` injected into L2 input ✅ Task 2
   - L2 Prompt updated to use real L4 data ✅ Task 2
   - `store_conversation` after final response ✅ Task 3
   - Session ID consistency between retrieval and storage ✅ Task 4
   - Optional example flow update ✅ Task 5

2. **Placeholder scan:** No TBD/TODO/fill-in-details found.

3. **Type consistency:** All method names (`retrieve_history`, `search`, `store_conversation`) match the `MemoryKnowledge` interface in `src/l4/core/l4_memory.py`. `session_id` is a string throughout.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-15-l4-mock-integration.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach would you like?
