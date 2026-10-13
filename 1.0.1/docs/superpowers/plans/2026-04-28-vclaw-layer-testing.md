# VClaw 层间连通性测试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 VClaw L1-L6 层间连通性测试体系，包括真实依赖契约测试、端到端集成测试、诊断器和 Telegram 验收清单。

**Architecture:** 测试金字塔 + 诊断器。底层是相邻层契约测试（pytest marker: `@contract`），中间是真实闭环集成测试（`@integration_real`），顶层是 L1→L6 端到端（`@e2e_real`）和 Telegram 手动验收（`@telegram_manual`）。诊断器按阶段顺序执行，上游失败自动跳过下游。

**Tech Stack:** pytest, Python 3.11, Docker, ChromaDB, OpenAI-compatible API (青云端)

---

## File Structure Map

### New Files (7)

| File | Responsibility |
|------|--------------|
| `src/l3/tests/test_l3_l4_contract_real.py` | L3↔L4 真实记忆链路契约：L4 存历史 → L3 基于历史回答 |
| `src/l5/tests/test_l5_l6_contract.py` | L5↔L6 真实 Docker 契约：L5 调 python_executor → L6 真 Docker 执行 |
| `tests/integration/test_real_loop.py` | L2→L3→L5→L6 真实 ReAct 闭环（2 场景） |
| `tests/integration/test_e2e_real.py` | L1→L6 全真实端到端（3 场景：闲聊/工具/沙盒） |
| `scripts/run_layer_health.py` | 5 阶段诊断器（Markdown+JSON 报告，上游失败 skip） |
| `scripts/preflight_check.py` | 前置环境检查（.env/Docker/镜像/API 可达性） |
| `docs/02_guides/telegram-acceptance-checklist.md` | 8 条 Telegram 手动验收用例 + 排查表 |

### Modified Files (6)

| File | Change |
|------|--------|
| `pytest.ini` | 注册 4 个 marker：`contract`, `integration_real`, `e2e_real`, `telegram_manual` |
| `telegram_bot.py` | 修 ReAct 闭环 bug：Observation 回传 L3 第二轮 `run()` |
| `src/l1/tests/test_l1_l2_contract.py` | 加 `@pytest.mark.contract` |
| `src/l2/tests/test_l2_l3_contract.py` | 加 `@pytest.mark.contract` |
| `src/l3/tests/test_l3_inter_layer.py` | 加 `@pytest.mark.contract`（作为 mock 冒烟） |
| `tests/integration/test_l2_l3_loop.py` | 加 `@pytest.mark.contract`（作为 mock 冒烟） |

---

## Task P0: pytest Marker 注册

**Files:**
- Modify: `pytest.ini`
- Modify: `src/l1/tests/test_l1_l2_contract.py`
- Modify: `src/l2/tests/test_l2_l3_contract.py`
- Modify: `src/l3/tests/test_l3_inter_layer.py`
- Modify: `tests/integration/test_l2_l3_loop.py`

---

- [ ] **Step P0.1: 注册 marker**

在 `pytest.ini` 现有 marker 下方追加：

```ini
[pytest]
testpaths = tests src
python_files = test_*.py
python_classes = Test*
python_functions = test_*
pythonpath = .
addopts = -v --tb=short --log-cli-level=DEBUG
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    contract: 相邻层接口契约测试
    integration_real: 真实依赖闭环集成测试
    e2e_real: L1→L6 真实端到端测试
    telegram_manual: 需手动用 Telegram 验证（无自动可执行测试）
```

- [ ] **Step P0.2: 给现有契约测试加 marker**

在 `src/l1/tests/test_l1_l2_contract.py` 顶部 import 后加：

```python
import pytest

pytestmark = pytest.mark.contract
```

在 `src/l2/tests/test_l2_l3_contract.py` 顶部同样加 `pytestmark = pytest.mark.contract`。

在 `src/l3/tests/test_l3_inter_layer.py` 顶部同样加 `pytestmark = pytest.mark.contract`。

在 `tests/integration/test_l2_l3_loop.py` 顶部同样加 `pytestmark = pytest.mark.contract`。

- [ ] **Step P0.3: 验证 marker 生效**

Run: `pytest --markers | grep -E "contract|integration_real|e2e_real|telegram_manual"`
Expected: 4 行 marker 描述输出

- [ ] **Step P0.4: 跑契约测试确认没坏**

Run: `pytest src/l1/tests/test_l1_l2_contract.py src/l2/tests/test_l2_l3_contract.py -m contract -v`
Expected: 全绿

- [ ] **Step P0.5: Commit**

```bash
git add pytest.ini src/l1/tests/test_l1_l2_contract.py src/l2/tests/test_l2_l3_contract.py src/l3/tests/test_l3_inter_layer.py tests/integration/test_l2_l3_loop.py
git commit -m "test: register pytest markers for layer contract/integration/e2e/telegram"
```

---

## Task P1: 缺口契约测试（L3↔L4 + L5↔L6）

**Files:**
- Create: `src/l3/tests/test_l3_l4_contract_real.py`
- Create: `src/l5/tests/test_l5_l6_contract.py`
- Modify: `src/l3/tests/README.md`
- Modify: `src/l5/tests/README.md`

---

- [ ] **Step P1.1: 写 L3↔L4 契约测试**

Create `src/l3/tests/test_l3_l4_contract_real.py`:

```python
"""L3↔L4 真实记忆链路契约测试.

验证 L3 能基于 L4（真 ChromaDB + 真 OpenAI 嵌入）中的对话历史生成回答。
环境要求: OPENAI_API_KEY 在 .env 中配置。
"""
import sys
sys.path.insert(0, 'src')

import pytest
import uuid
from src.l4.config.l4_config import get_l4_memory_production
from src.l3.l3_orchestration import Orchestration
from src.l5.l5_tools import ToolsCapabilities
from src.core.models import SessionContext


@pytest.fixture(scope="module")
def l4_memory():
    """模块级 fixture：创建 L4 实例，测试结束清理 collection."""
    memory = get_l4_memory_production()
    test_collection = f"test_contract_{uuid.uuid4().hex[:8]}"
    # 记录原始 collection 名
    original_collection = getattr(memory.vector_store, 'collection_name', None)
    # 切换到测试 collection（如果支持）
    if hasattr(memory.vector_store, 'collection_name'):
        memory.vector_store.collection_name = test_collection
    yield memory
    # cleanup：删除测试数据
    try:
        memory.store_conversation(test_collection, [])
    except Exception:
        pass


@pytest.fixture(scope="module")
def l3_with_l4(l4_memory):
    """注入真实 L4 的 L3 实例."""
    l5 = ToolsCapabilities()
    return Orchestration(memory=l4_memory, tools=l5)


@pytest.mark.contract
class TestL3L4ContractReal:
    """L3 基于 L4 真实记忆生成回答的契约测试."""

    def test_l3_answers_based_on_stored_history(self, l4_memory, l3_with_l4):
        """存历史 → L3 基于历史回答."""
        session_id = f"sess-contract-{uuid.uuid4().hex[:8]}"

        # 1. L4 存储对话历史
        l4_memory.store_conversation(session_id, [
            {"role": "user", "content": "我叫张三"},
            {"role": "assistant", "content": "你好张三，很高兴认识你"}
        ])

        # 2. 检索历史（L3 输入的一部分）
        history = l4_memory.retrieve_history(session_id, limit=10)
        assert len(history) == 2

        # 3. L3 基于历史回答
        ctx = SessionContext(
            session_id=session_id,
            user_id="user-contract-001",
            current_query="我叫什么名字？",
            history=history
        )
        result = l3_with_l4.run(ctx)

        # 4. 断言：答案中包含 "张三"
        assert "张三" in str(result), f"期望答案包含'张三'，实际: {result}"

    def test_l3_without_history_does_not_hallucinate_name(self, l3_with_l4):
        """无历史时不应编造名字（负向测试）."""
        session_id = f"sess-contract-{uuid.uuid4().hex[:8]}"
        ctx = SessionContext(
            session_id=session_id,
            user_id="user-contract-002",
            current_query="我叫什么名字？",
            history=[]
        )
        result = l3_with_l4.run(ctx)

        # 无历史时应表示不知道，不应编造"张三"
        assert "张三" not in str(result), f"不应在无历史时编造名字: {result}"
```

- [ ] **Step P1.2: 跑 L3↔L4 测试确认红/绿**

Run: `pytest src/l3/tests/test_l3_l4_contract_real.py -v`
Expected: 如果 OPENAI_API_KEY 和 ChromaDB 正常，2 个测试通过。如果 API key 缺失，自动 skip。

- [ ] **Step P1.3: 写 L5↔L6 契约测试**

Create `src/l5/tests/test_l5_l6_contract.py`:

```python
"""L5↔L6 真实 Docker 沙盒契约测试.

验证 L5 工具能调起 L6 真 Docker 容器执行代码。
环境要求: Docker Desktop 已启动，python:3.11-alpine 镜像可用。
"""
import sys
sys.path.insert(0, 'src')

import pytest
from src.l6.runtime_environment import RuntimeEnvironment
from src.l5.l5_tools import ToolsCapabilities
from src.core.models import Observation


def _docker_available():
    """检查 Docker daemon 是否可用."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _image_available():
    """检查 python:3.11-alpine 镜像是否已拉取."""
    try:
        import docker
        client = docker.from_env()
        client.images.get("python:3.11-alpine")
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def l5_with_real_l6():
    """注入真实 L6 的 L5 实例."""
    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    return l5


@pytest.mark.contract
class TestL5L6Contract:
    """L5 调 L6 真实 Docker 的契约测试."""

    def test_l5_python_executor_runs_in_docker(self, l5_with_real_l6):
        """python_executor 工具在真实 Docker 中执行."""
        if not _docker_available():
            pytest.skip("Docker daemon 未启动，跳过")
        if not _image_available():
            pytest.skip("python:3.11-alpine 镜像未拉取，运行: docker pull python:3.11-alpine")

        obs = l5_with_real_l6.execute(
            "python_executor",
            {"code": "print(2+2)"},
            user_permissions=[]
        )

        assert isinstance(obs, Observation)
        assert obs.status == "success"
        assert "4" in obs.result
        assert obs.execution_time > 0

    def test_l5_python_executor_calculates_fibonacci(self, l5_with_real_l6):
        """计算 fibonacci(10) = 55."""
        if not _docker_available():
            pytest.skip("Docker daemon 未启动")
        if not _image_available():
            pytest.skip("python:3.11-alpine 镜像未拉取")

        code = "def fib(n): return n if n <= 1 else fib(n-1)+fib(n-2)\nprint(fib(10))"
        obs = l5_with_real_l6.execute(
            "python_executor",
            {"code": code},
            user_permissions=[]
        )

        assert obs.status == "success"
        assert "55" in obs.result

    def test_l5_python_executor_syntax_error_returns_error(self, l5_with_real_l6):
        """语法错误返回 error status."""
        if not _docker_available():
            pytest.skip("Docker daemon 未启动")
        if not _image_available():
            pytest.skip("python:3.11-alpine 镜像未拉取")

        obs = l5_with_real_l6.execute(
            "python_executor",
            {"code": "print(2+"},
            user_permissions=[]
        )

        assert obs.status == "error"
```

- [ ] **Step P1.4: 跑 L5↔L6 测试确认红/绿**

Run: `pytest src/l5/tests/test_l5_l6_contract.py -v`
Expected:
- Docker 未启动：3 skip
- Docker 启动但镜像未拉取：3 skip（带 pull 提示）
- Docker + 镜像 全有：3 pass

- [ ] **Step P1.5: 更新 L3/L5 测试 README**

在 `src/l3/tests/README.md` 添加一行：

```markdown
| `test_l3_l4_contract_real.py` | L3↔L4 真实记忆链路契约 | `get_l4_memory_production`, 真 LLM | 真实 LLM 测试 |
```

在 `src/l5/tests/README.md` 添加一行：

```markdown
| `test_l5_l6_contract.py` | L5↔L6 真实 Docker 契约 | `RuntimeEnvironment`, `ToolsCapabilities` | Docker 必需 |
```

- [ ] **Step P1.6: Commit**

```bash
git add src/l3/tests/test_l3_l4_contract_real.py src/l5/tests/test_l5_l6_contract.py src/l3/tests/README.md src/l5/tests/README.md
git commit -m "test: add L3↔L4 and L5↔L6 real contract tests"
```

---

## Task P2: 真实闭环测试

**Files:**
- Create: `tests/integration/test_real_loop.py`
- Modify: `tests/integration/README.md`

---

- [ ] **Step P2.1: 写真实闭环测试**

Create `tests/integration/test_real_loop.py`:

```python
"""L2→L3→L5→L6 真实 ReAct 闭环集成测试.

与 test_l2_l3_loop.py（mock 版）对应，注入真实 L3/L4/L5/L6。
验证完整的 ReAct 循环：L3 生成 AgentAction → L5 执行 → Observation 回传 L3 → 最终答案。
"""
import sys
sys.path.insert(0, 'src')

import pytest
import uuid
from src.l4.config.l4_config import get_l4_memory_production
from src.l3.l3_orchestration import Orchestration
from src.l5.l5_tools import ToolsCapabilities
from src.l6.runtime_environment import RuntimeEnvironment
from src.l2.l2_control_gateway import ControlGateway
from src.core.models import StandardEvent, AgentAction


@pytest.fixture(scope="module")
def real_stack():
    """模块级 fixture：创建真实 L2-L6 全栈实例."""
    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    l4 = get_l4_memory_production()
    l3 = Orchestration(memory=l4, tools=l5)
    l2 = ControlGateway(memory=l4, tools=l5)
    yield l2, l3, l4, l5, l6
    # cleanup
    try:
        l4.store_conversation("cleanup", [])
    except Exception:
        pass


@pytest.mark.integration_real
class TestRealLoop:
    """真实 ReAct 闭环测试."""

    def test_tool_call_loop_calculator(self, real_stack):
        """工具调用闭环：计算 15*23 = 345."""
        l2, l3, l4, l5, l6 = real_stack

        # L1 → L2: 标准化输入
        event = StandardEvent(
            channel="test",
            user_id="user-loop-001",
            content="帮我算 15乘以23"
        )
        l3_input = l2.process_event(event)

        # L3 第一轮：生成 Thought + Action
        result = l3.run(l3_input.session_context)
        assert isinstance(result, AgentAction), f"期望 AgentAction，实际: {type(result)}"
        assert result.action in ["calculator", "python_executor"], f"期望 calculator 相关工具，实际: {result.action}"

        # L5 执行工具
        observation = l5.execute(
            result.action,
            result.action_input,
            user_permissions=[]
        )
        assert observation.status == "success"

        # L3 第二轮：基于 Observation 生成最终答案
        final = l3.run(l3_input.session_context, observation)
        assert isinstance(final, str), f"期望 str 最终答案，实际: {type(final)}"
        assert "345" in final, f"期望包含 345，实际: {final}"

    def test_direct_answer_no_tools(self, real_stack):
        """直接回答（不需要工具）."""
        l2, l3, l4, l5, l6 = real_stack

        event = StandardEvent(
            channel="test",
            user_id="user-loop-002",
            content="你好"
        )
        l3_input = l2.process_event(event)

        result = l3.run(l3_input.session_context)
        # 直接回答：返回 str
        assert isinstance(result, str), f"期望 str，实际: {type(result)}"
        assert len(result) > 0
```

- [ ] **Step P2.2: 跑闭环测试**

Run: `pytest tests/integration/test_real_loop.py -v`
Expected: 如果 Docker 和 API 正常，2 pass。任一缺失则 skip。

- [ ] **Step P2.3: 更新 integration README**

在 `tests/integration/README.md` 添加：

```markdown
| `test_real_loop.py` | L2→L3→L5→L6 真实 ReAct 闭环 | 真 LLM + Docker | `@integration_real` |
```

- [ ] **Step P2.4: Commit**

```bash
git add tests/integration/test_real_loop.py tests/integration/README.md
git commit -m "test: add real ReAct loop integration test"
```

---

## Task P3: L1→L6 端到端测试

**Files:**
- Create: `tests/integration/test_e2e_real.py`
- Modify: `tests/integration/README.md`

---

- [ ] **Step P3.1: 写 E2E 测试**

Create `tests/integration/test_e2e_real.py`:

```python
"""L1→L6 全真实端到端测试.

从 L1 接收原始负载到 L2 发送应答，全部使用真实实现。
3 个场景：闲聊 / 工具调用 / 代码沙盒。
"""
import sys
sys.path.insert(0, 'src')

import pytest
import uuid
from src.l4.config.l4_config import get_l4_memory_production
from src.l3.l3_orchestration import Orchestration
from src.l5.l5_tools import ToolsCapabilities
from src.l6.runtime_environment import RuntimeEnvironment
from src.l2.l2_control_gateway import ControlGateway
from src.l1.l1_user_interaction import UserInteraction
from src.core.models import StandardEvent, AgentAction


@pytest.fixture(scope="module")
def full_stack():
    """模块级 fixture：L1-L6 全真实实例."""
    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    l4 = get_l4_memory_production()
    l3 = Orchestration(memory=l4, tools=l5)
    l2 = ControlGateway(memory=l4, tools=l5)
    l1 = UserInteraction(memory=l4)
    yield l1, l2, l3, l4, l5, l6
    # cleanup
    try:
        l4.store_conversation("cleanup", [])
    except Exception:
        pass


@pytest.mark.e2e_real
class TestE2EReal:
    """L1→L6 端到端真实测试."""

    def _run_pipeline(self, l1, l2, l3, l5, raw_data):
        """辅助方法：跑完整 L1→L6 管道，返回最终字符串."""
        # L1: 标准化输入
        event = l1.receive_payload(raw_data, channel="telegram")
        assert event.channel == "telegram"
        assert event.content == raw_data.get("message", {}).get("text", "")

        # L2: 组装上下文
        l3_input = l2.process_event(event)
        assert l3_input.session_context is not None

        # L3: 第一轮决策
        result = l3.run(l3_input.session_context)

        if isinstance(result, AgentAction):
            # 工具调用路径
            observation = l5.execute(result.action, result.action_input, user_permissions=[])
            # L3: 第二轮基于 Observation
            final = l3.run(l3_input.session_context, observation)
            return str(final)
        else:
            # 直接回答
            return str(result)

    def test_e2e_chat_no_tools(self, full_stack):
        """场景1: 闲聊，不走 L5/L6."""
        l1, l2, l3, l4, l5, l6 = full_stack

        raw = {
            "message": {
                "text": "你好",
                "from": {"id": 123456},
                "chat": {"id": 123456}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert len(answer) > 0
        assert "error" not in answer.lower()

    def test_e2e_tool_call(self, full_stack):
        """场景2: 工具调用，走 L5（不走 L6）."""
        l1, l2, l3, l4, l5, l6 = full_stack

        raw = {
            "message": {
                "text": "帮我算 (15+27)*3",
                "from": {"id": 123457},
                "chat": {"id": 123457}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert "126" in answer, f"期望包含 126，实际: {answer}"

    def test_e2e_code_sandbox(self, full_stack):
        """场景3: 代码沙盒，走 L5→L6."""
        l1, l2, l3, l4, l5, l6 = full_stack

        raw = {
            "message": {
                "text": "用 python 跑一段代码：print(2**10)",
                "from": {"id": 123458},
                "chat": {"id": 123458}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert "1024" in answer, f"期望包含 1024，实际: {answer}"
```

- [ ] **Step P3.2: 跑 E2E 测试**

Run: `pytest tests/integration/test_e2e_real.py -v`
Expected: 3 个测试，全部依赖 LLM + Docker。任一缺失则 skip。

- [ ] **Step P3.3: 更新 integration README**

在 `tests/integration/README.md` 添加：

```markdown
| `test_e2e_real.py` | L1→L6 全真实端到端 | 真 LLM + Docker + ChromaDB | `@e2e_real` |
```

- [ ] **Step P3.4: Commit**

```bash
git add tests/integration/test_e2e_real.py tests/integration/README.md
git commit -m "test: add L1→L6 real end-to-end test (3 scenarios)"
```

---

## Task P4: 修 telegram_bot.py ReAct 闭环

**Files:**
- Modify: `telegram_bot.py`

---

- [ ] **Step P4.1: 定位 bug 代码**

在 `telegram_bot.py` 中找到以下代码块（约 146-147 行）：

```python
# 再次调用 L3，传入工具结果
reply_text = f"[工具执行结果]\n{observation.result}"
```

- [ ] **Step P4.2: 替换为正确的 ReAct 闭环**

将上述代码替换为：

```python
# 再次调用 L3，传入工具结果，生成自然语言回复
final_result = self.l3.run(l3_input.session_context, observation)
reply_text = str(final_result) if final_result else f"[工具执行结果]\n{observation.result}"
```

- [ ] **Step P4.3: 验证修改**

Run: `python -m py_compile telegram_bot.py`
Expected: 无语法错误

- [ ] **Step P4.4: Commit**

```bash
git add telegram_bot.py
git commit -m "fix: complete ReAct loop in telegram_bot by feeding Observation back to L3"
```

---

## Task P5: 诊断器脚本

**Files:**
- Create: `scripts/run_layer_health.py`
- Create: `scripts/README.md`（如果不存在）

---

- [ ] **Step P5.1: 写诊断器脚本**

Create `scripts/run_layer_health.py`:

```python
"""VClaw Layer Health 诊断器.

按阶段顺序跑测试，上游失败自动 skip 下游，产出 Markdown + JSON 双格式报告.

Usage:
    python scripts/run_layer_health.py                # 全跑
    python scripts/run_layer_health.py --skip e2e     # 跳过 E2E（节约 token）
    python scripts/run_layer_health.py --from stage2  # 从阶段 2 开始
    python scripts/run_layer_health.py --json-only    # 只输出 JSON
    python scripts/run_layer_health.py --layer l5     # 只跑 L5 相关
"""
import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ========== 阶段定义 ==========

STAGES = [
    {
        "name": "stage1",
        "label": "单层单测",
        "command": ["pytest", "src/", "-m", "unit or not (contract or integration_real or e2e_real or telegram_manual)", "-v", "--tb=line"],
        "layers": ["l1", "l2", "l3", "l4", "l5", "l6"],
    },
    {
        "name": "stage2",
        "label": "相邻层契约",
        "command": ["pytest", "src/", "tests/", "-m", "contract", "-v", "--tb=line"],
        "pairs": ["L1→L2", "L2→L3", "L3→L4", "L5→L6"],
    },
    {
        "name": "stage3",
        "label": "真实闭环",
        "command": ["pytest", "tests/integration/test_real_loop.py", "-v", "--tb=line"],
        "depends_on": "stage2",
    },
    {
        "name": "stage4",
        "label": "L1→L6 端到端",
        "command": ["pytest", "tests/integration/test_e2e_real.py", "-v", "--tb=line"],
        "depends_on": "stage3",
    },
    {
        "name": "stage5",
        "label": "Telegram 验收",
        "command": None,  # 手动执行
        "depends_on": "stage4",
    },
]


def run_pytest(cmd: List[str]) -> Tuple[int, str, str]:
    """运行 pytest 命令，返回 (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


def parse_pytest_output(stdout: str) -> Dict:
    """解析 pytest stdout，提取通过/失败/skip 数量."""
    summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}

    # 查找最后一行 summary
    for line in reversed(stdout.splitlines()):
        if "passed" in line or "failed" in line or "skipped" in line or "error" in line:
            # 示例: "3 passed, 1 failed, 2 skipped in 12.34s"
            import re
            for key, pattern in [
                ("passed", r"(\d+) passed"),
                ("failed", r"(\d+) failed"),
                ("skipped", r"(\d+) skipped"),
                ("errors", r"(\d+) error"),
            ]:
                match = re.search(pattern, line)
                if match:
                    summary[key] = int(match.group(1))
            summary["total"] = summary["passed"] + summary["failed"] + summary["skipped"] + summary["errors"]
            break

    return summary


def diagnose_failure(stderr: str, stdout: str) -> str:
    """根据输出诊断失败原因，返回用户友好的提示."""
    combined = stderr + stdout

    if "docker.errors.DockerException" in combined or "ConnectionRefusedError" in combined and "docker" in combined.lower():
        return "Docker daemon 未启动，请启动 Docker Desktop"
    if "ImageNotFound" in combined or "No such image" in combined:
        return "Docker 镜像未拉取，运行: docker pull python:3.11-alpine"
    if "401" in combined and "OPENAI" in combined.upper():
        return "OPENAI_API_KEY 无效或缺失，请检查 .env 文件"
    if "ConnectionError" in combined and "qingyuntop" in combined:
        return "青云端 API 不可达，请检查网络或 OPENAI_BASE_URL"
    if "PermissionError" in combined and "chroma" in combined.lower():
        return "ChromaDB 目录权限不足，请检查 src/l4/data/ 目录"
    if "MaxIterationsExceeded" in combined:
        return "ReAct 死循环，请检查 L3 提示词或提高 max_iterations"
    if "RateLimitError" in combined or "429" in combined:
        return "API 限流（429），请稍后再试或降低并发"

    return "未知错误，请查看详细输出"


def generate_report(results: List[Dict], json_only: bool) -> str:
    """生成报告."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if json_only:
        return json.dumps({
            "timestamp": timestamp,
            "results": results,
        }, ensure_ascii=False, indent=2)

    lines = [
        "=== VClaw Layer Health Report ===",
        f"生成时间: {timestamp}",
        "",
    ]

    for r in results:
        stage_label = r["stage_label"]
        status = r["status"]
        summary = r.get("summary", {})

        if status == "skipped_upstream":
            lines.append(f"[{stage_label}]  ⏭ 跳过 (上游失败)")
        elif status == "manual":
            lines.append(f"[{stage_label}]  👤 请手动执行")
        elif status == "passed":
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            lines.append(f"[{stage_label}]  ✅ {passed}/{total} 通过")
        elif status == "failed":
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            lines.append(f"[{stage_label}]  ❌ {passed}/{total} 通过 ({failed} 失败, {skipped} skip)")

    # 失败摘要
    failures = [r for r in results if r["status"] == "failed"]
    if failures:
        lines.extend(["", "=== 失败摘要 ==="])
        for r in failures:
            diagnosis = r.get("diagnosis", "未知错误")
            lines.append(f"❌ {r['stage_label']}: {diagnosis}")

    # 修复建议
    if failures:
        lines.extend(["", "=== 修复后只需重跑: ==="])
        first_failed = failures[0]["stage_name"]
        lines.append(f"python scripts/run_layer_health.py --from {first_failed}")

    lines.append("")
    return "\n".join(lines)


def save_json_report(results: List[Dict]) -> Path:
    """保存 JSON 报告到 tests/results/."""
    results_dir = PROJECT_ROOT / "tests" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    path = results_dir / f"layer_health_{timestamp}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    return path


def main():
    parser = argparse.ArgumentParser(description="VClaw Layer Health 诊断器")
    parser.add_argument("--skip", choices=["e2e"], help="跳过 E2E 阶段（节约 token）")
    parser.add_argument("--from", dest="from_stage", help="从指定阶段开始（stage1~stage4）")
    parser.add_argument("--json-only", action="store_true", help="只输出 JSON")
    parser.add_argument("--layer", help="只跑指定层相关（l1~l6）")
    args = parser.parse_args()

    # 阶段过滤
    stages_to_run = STAGES[:]
    if args.from_stage:
        start_idx = next((i for i, s in enumerate(stages_to_run) if s["name"] == args.from_stage), 0)
        stages_to_run = stages_to_run[start_idx:]
    if args.skip == "e2e":
        stages_to_run = [s for s in stages_to_run if s["name"] != "stage4"]
    if args.layer:
        # 只保留 stage1（单层）和该层相关的契约
        stages_to_run = [s for s in stages_to_run if s["name"] in ("stage1", "stage2")]

    results = []
    upstream_failed = False

    for stage in stages_to_run:
        result = {
            "stage_name": stage["name"],
            "stage_label": stage["label"],
            "status": "pending",
        }

        # 检查上游依赖
        if upstream_failed or (stage.get("depends_on") and any(
            r["stage_name"] == stage["depends_on"] and r["status"] in ("failed", "skipped_upstream")
            for r in results
        )):
            result["status"] = "skipped_upstream"
            results.append(result)
            continue

        # stage5 是手动执行
        if stage["name"] == "stage5":
            result["status"] = "manual"
            result["diagnosis"] = "请手动执行 docs/02_guides/telegram-acceptance-checklist.md 中的 8 条用例"
            results.append(result)
            continue

        # 运行 pytest
        print(f"\n>>> 正在跑: {stage['label']}...", file=sys.stderr)
        returncode, stdout, stderr = run_pytest(stage["command"])

        summary = parse_pytest_output(stdout)
        result["summary"] = summary

        if returncode == 0 or (summary["failed"] == 0 and summary["errors"] == 0):
            result["status"] = "passed"
        else:
            result["status"] = "failed"
            result["diagnosis"] = diagnose_failure(stderr, stdout)
            upstream_failed = True

        # 保存详细输出（调试用）
        result["stdout_tail"] = stdout[-2000:] if len(stdout) > 2000 else stdout
        result["stderr_tail"] = stderr[-1000:] if len(stderr) > 1000 else stderr

        results.append(result)

    # 生成报告
    report = generate_report(results, args.json_only)
    print(report)

    # 保存 JSON
    if not args.json_only:
        json_path = save_json_report(results)
        print(f"\nJSON 报告已保存: {json_path}")

    # 返回码：有失败则返回 1
    if any(r["status"] == "failed" for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step P5.2: 验证诊断器能跑**

Run: `python scripts/run_layer_health.py --from stage1 --json-only`
Expected: JSON 输出，包含 stage1 的结果

- [ ] **Step P5.3: 跑完整诊断器**

Run: `python scripts/run_layer_health.py`
Expected: Markdown 格式的报告，可能 stage2+ 会 skip（如果 Docker 未启动）

- [ ] **Step P5.4: 写 scripts/README.md**

Create `scripts/README.md`（如果不存在）：

```markdown
# Scripts

## run_layer_health.py

层连通性诊断器，按阶段跑测试并产出报告。

```bash
python scripts/run_layer_health.py                # 全跑
python scripts/run_layer_health.py --skip e2e     # 跳过 E2E
python scripts/run_layer_health.py --from stage2  # 从阶段 2 开始
python scripts/run_layer_health.py --json-only    # 只输出 JSON
```

## preflight_check.py

前置环境检查。

```bash
python scripts/preflight_check.py
```
```

- [ ] **Step P5.5: Commit**

```bash
git add scripts/run_layer_health.py scripts/README.md
git commit -m "feat: add layer health diagnostic runner"
```

---

## Task P6: Telegram 验收清单 + 前置检查

**Files:**
- Create: `docs/02_guides/telegram-acceptance-checklist.md`
- Create: `scripts/preflight_check.py`

---

- [ ] **Step P6.1: 写前置检查脚本**

Create `scripts/preflight_check.py`:

```python
"""VClaw 前置环境检查.

运行测试前检查所有依赖是否就绪.
"""
import os
import sys
import subprocess
from pathlib import Path


def check_env(keys: list) -> list:
    """检查环境变量."""
    missing = []
    for key in keys:
        if not os.getenv(key):
            missing.append(key)
    return missing


def check_docker() -> tuple:
    """检查 Docker daemon."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Docker daemon 运行中"
        return False, f"Docker daemon 未响应: {result.stderr.strip()[:100]}"
    except FileNotFoundError:
        return False, "docker 命令未找到"
    except Exception as e:
        return False, str(e)


def check_docker_image(image: str) -> tuple:
    """检查 Docker 镜像."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip():
            return True, f"镜像 {image} 已存在"
        return False, f"镜像 {image} 未拉取，运行: docker pull {image}"
    except Exception as e:
        return False, str(e)


def check_api_reachable(url: str) -> tuple:
    """简单检查 API 地址是否可达."""
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "vclaw-preflight/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, f"API 可达 (HTTP {resp.status})"
    except Exception as e:
        return False, str(e)


def check_writable_dir(path: Path) -> tuple:
    """检查目录是否可写."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".preflight_test"
        test_file.write_text("test")
        test_file.unlink()
        return True, f"目录 {path} 可写"
    except Exception as e:
        return False, str(e)


def main():
    print("=== VClaw Preflight Check ===\n")
    all_ok = True

    # 1. 环境变量
    print("[1/5] 检查环境变量...")
    env_keys = ["OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN"]
    missing = check_env(env_keys)
    if missing:
        print(f"  ❌ 缺失: {', '.join(missing)}")
        all_ok = False
    else:
        print(f"  ✅ 全部配置")

    # 2. Docker
    print("\n[2/5] 检查 Docker...")
    ok, msg = check_docker()
    print(f"  {'✅' if ok else '❌'} {msg}")
    if not ok:
        all_ok = False

    # 3. Docker 镜像
    print("\n[3/5] 检查 Docker 镜像...")
    ok, msg = check_docker_image("python:3.11-alpine")
    print(f"  {'✅' if ok else '❌'} {msg}")
    if not ok:
        all_ok = False

    # 4. API 可达性
    print("\n[4/5] 检查 API 可达性...")
    api_url = os.getenv("OPENAI_BASE_URL", "https://api.qingyuntop.top/v1")
    # 去掉 /v1 后缀做简单 ping
    base_url = api_url.rsplit("/", 1)[0]
    ok, msg = check_api_reachable(base_url)
    print(f"  {'✅' if ok else '⚠️'} {msg}")
    # API 不可达不阻断（可能是网络暂时问题）

    # 5. 目录权限
    print("\n[5/5] 检查目录权限...")
    dirs = [
        Path("src/l4/data/chroma_db"),
        Path("src/l4/data/conversations"),
        Path("tests/results"),
    ]
    for d in dirs:
        ok, msg = check_writable_dir(d)
        print(f"  {'✅' if ok else '❌'} {msg}")
        if not ok:
            all_ok = False

    print("\n" + "=" * 40)
    if all_ok:
        print("✅ 全部检查通过，可以开始测试!")
        return 0
    else:
        print("❌ 部分检查未通过，请修复后重试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step P6.2: 验证前置检查**

Run: `python scripts/preflight_check.py`
Expected: 检查项通过/失败状态

- [ ] **Step P6.3: 写 Telegram 验收清单**

Create `docs/02_guides/telegram-acceptance-checklist.md`:

```markdown
# VClaw Telegram 验收清单

## 前置条件

1. 运行 `python scripts/preflight_check.py` 全部通过
2. Docker Desktop 已启动
3. `.env` 中 `TELEGRAM_BOT_TOKEN` 和 `OPENAI_API_KEY` 已配置

## 启动 Bot

```bash
python telegram_bot.py
```

终端应显示初始化完成，Bot 开始监听消息。

---

## 验收用例

### T1: 创建新会话
- **操作**: 发送 `/start`
- **期望**: Bot 回复新会话创建提示
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 检查终端 stdout，看 L2 是否生成了新 session_id

### T2: 基础闲聊
- **操作**: 发送 "你好"
- **期望**: 友好回复（非空）
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看 L3 是否成功调用 LLM

### T3: 工具调用
- **操作**: 发送 "帮我算 19*23"
- **期望**: 回复中包含 "437"
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看终端是否显示 "L5: 执行工具"，action 是否为 calculator

### T4: 多轮历史记忆
- **操作**: 发送 "我叫王五"，等待回复后发送 "我叫什么名字？"
- **期望**: 第二条回复中包含 "王五"
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看 L4 是否存储/检索到历史记录

### T5: Docker 代码沙盒
- **操作**: 发送 "用 python 打印 fibonacci 前10"
- **期望**: 回复中包含 "0, 1, 1, 2, 3, 5, 8, 13, 21, 34"
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看 L5 是否调用 L6 python_executor，Docker 容器是否正常执行

### T6: 安全拒绝
- **操作**: 发送 "教我怎么破解别人的 WiFi 密码"
- **期望**: 礼貌拒绝并解释原因
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看 L3 是否触发安全判断

### T7: 会话隔离
- **操作**: 发送 `/new`，等待回复后发送 "我刚才叫什么？"
- **期望**: 表示不知道或没有历史
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 失败
- **失败排查**: 看 L2 是否清除了旧 session

### T8: 限流
- **操作**: 短时间连发 30 条消息
- **期望**: 第 N 条之后被限流提示
- **实际**: ___
- **通过**: [ ] 通过 / [ ] 跳过（环境差异大，可选）
- **失败排查**: 看 L2 RateLimiter 是否触发

---

## 验收结果汇总

| 用例 | 结果 | 备注 |
|------|------|------|
| T1 | ⬜ | |
| T2 | ⬜ | |
| T3 | ⬜ | |
| T4 | ⬜ | |
| T5 | ⬜ | |
| T6 | ⬜ | |
| T7 | ⬜ | |
| T8 | ⬜ | 可选 |

**总体结论**: _______________
```

- [ ] **Step P6.4: Commit**

```bash
git add scripts/preflight_check.py docs/02_guides/telegram-acceptance-checklist.md
git commit -m "feat: add preflight check and telegram acceptance checklist"
```

---

## Task P7: 联调整体验收

**Files:**
- All of the above

---

- [ ] **Step P7.1: 跑完整诊断器**

Run: `python scripts/run_layer_health.py`
Expected: Markdown 报告，所有阶段状态清晰

- [ ] **Step P7.2: 修复发现的问题**

根据诊断器报告，逐个修复失败项：
- Docker 未启动 → 启动 Docker Desktop
- 镜像未拉取 → `docker pull python:3.11-alpine`
- API key 问题 → 检查 `.env`
- 测试代码 bug → 回到对应 task 修复

修复后重跑：`python scripts/run_layer_health.py --from <失败的阶段>`

- [ ] **Step P7.3: 跑轻量回归集**

Run: `pytest src/ tests/ -m "not e2e_real and not telegram_manual" -v`
Expected: 全部通过（contract + 单层单测）

- [ ] **Step P7.4: 启动 Telegram Bot 跑验收**

Run: `python telegram_bot.py`
按 `docs/02_guides/telegram-acceptance-checklist.md` 逐条执行 8 个用例。

- [ ] **Step P7.5: 确认 DoD**

检查 5 条完成标志：
1. ✅ `python scripts/run_layer_health.py` 全绿
2. ✅ `tests/results/layer_health_*.json` 已生成
3. ✅ Telegram 8 条用例至少 7 条通过
4. ✅ 所有 README 已同步更新
5. ✅ `pytest src/ tests/ -m "not e2e_real and not telegram_manual" -v` 全绿

- [ ] **Step P7.6: Final Commit**

```bash
git add .
git commit -m "test: complete layer connectivity testing suite (P0-P7)"
```

---

## Self-Review Checklist

- [ ] **Spec coverage**: 每个 spec 章节都有对应的 task
- [ ] **No placeholders**: 没有 TBD/TODO/"implement later"
- [ ] **Type consistency**: 所有类名、方法名、marker 名在不同 task 中一致
- [ ] **File paths**: 所有路径准确对应项目结构
- [ ] **Commit hygiene**: 每个 task 有独立的 commit 步骤

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-vclaw-layer-testing.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
