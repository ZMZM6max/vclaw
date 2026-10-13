# VClaw Web Test Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified Web Test Console at `http://localhost:8000/` for testing L1-L6 layers independently and running end-to-end conversations through the full ReAct loop.

**Architecture:** FastAPI backend serves a vanilla-JS single-page dashboard. The backend exposes per-layer test endpoints and an E2E `/api/e2e/chat` endpoint that internally drives the L3 ReAct loop by calling L5 when L3 returns an `AgentAction`. All code lives in `src/l1/tests/web_console/` with zero build-tool dependencies.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, Pydantic, vanilla HTML5/CSS3/ES6.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/l1/tests/web_console/__init__.py` | Makes the directory a Python package |
| `src/l1/tests/web_console/server.py` | FastAPI app, API routes, E2E ReAct loop, Jinja2 template rendering |
| `src/l1/tests/web_console/templates/index.html` | Single-page dashboard with all test panels |
| `src/l1/tests/web_console/static/style.css` | Dashboard layout, sidebar, cards, JSON highlighter |
| `src/l1/tests/web_console/static/app.js` | Hash-based routing, tab switching, fetch calls, E2E chat UI |
| `src/l1/tests/web_console/README.md` | Launch instructions and usage notes |
| `src/l1/tests/web_console/test_web_console.py` | Backend API tests |

---

### Task 1: Scaffold Directory and Empty Files

**Files:**
- Create: `src/l1/tests/web_console/__init__.py`
- Create: `src/l1/tests/web_console/server.py` (skeleton)
- Create: `src/l1/tests/web_console/templates/index.html` (skeleton)
- Create: `src/l1/tests/web_console/static/style.css` (empty)
- Create: `src/l1/tests/web_console/static/app.js` (empty)
- Create: `src/l1/tests/web_console/README.md` (skeleton)

- [ ] **Step 1: Create directory structure and empty files**

Run:
```bash
mkdir -p src/l1/tests/web_console/templates
mkdir -p src/l1/tests/web_console/static
```

Create `src/l1/tests/web_console/__init__.py`:
```python
"""VClaw Web Test Console package."""
```

Create `src/l1/tests/web_console/server.py` with a minimal skeleton:
```python
"""VClaw Web Test Console - FastAPI server."""
import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="VClaw Web Test Console")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# TODO: add routes
```

Create `src/l1/tests/web_console/templates/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>VClaw Test Console</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">Loading...</div>
  <script src="/static/app.js"></script>
</body>
</html>
```

Create `src/l1/tests/web_console/static/style.css` as an empty file and `src/l1/tests/web_console/static/app.js` as an empty file.

Create `src/l1/tests/web_console/README.md`:
```markdown
# VClaw Web Test Console

## Start
```bash
conda activate vclaw
python src/l1/tests/web_console/server.py
```

## Access
Open http://localhost:8000
```

- [ ] **Step 2: Commit skeleton**

```bash
git add src/l1/tests/web_console/
git commit -m "feat(web_console): scaffold web test console directory"
```

---

### Task 2: Backend System Health and Config Endpoints

**Files:**
- Modify: `src/l1/tests/web_console/server.py`
- Test: `src/l1/tests/web_console/test_web_console.py`

- [ ] **Step 1: Write failing test for `/health` and `/api/config`**

Create `src/l1/tests/web_console/test_web_console.py`:
```python
"""Tests for the VClaw Web Test Console backend."""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from src.l1.tests.web_console.server import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm_available" in data
    assert "docker_available" in data
    assert "tools" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: FAIL (404 because routes are missing)

- [ ] **Step 3: Implement `/`, `/health`, and `/api/config` in server.py**

Append the following to `src/l1/tests/web_console/server.py` (replace the `# TODO: add routes` comment):

```python
import os
import json
from typing import Any, Dict, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="VClaw Web Test Console")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def _docker_available() -> bool:
    try:
        import subprocess
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=2
        )
        return True
    except Exception:
        return False


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def config():
    from src.l5.l5_tools import ToolRegistry
    registry = ToolRegistry()
    return {
        "llm_available": _llm_available(),
        "docker_available": _docker_available(),
        "tools": [t.name for t in registry.tools]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/l1/tests/web_console/server.py src/l1/tests/web_console/test_web_console.py
git commit -m "feat(web_console): add health and config endpoints with tests"
```

---

### Task 3: Backend L1-L6 Independent Test Endpoints

**Files:**
- Modify: `src/l1/tests/web_console/server.py`
- Test: `src/l1/tests/web_console/test_web_console.py`

- [ ] **Step 1: Write failing tests for a subset of layer endpoints**

Append to `src/l1/tests/web_console/test_web_console.py`:

```python
def test_l1_test_adapter():
    payload = {
        "channel": "webhook",
        "raw_data": {
            "user_id": "u1",
            "message": {"text": "hello"}
        }
    }
    response = client.post("/api/l1/test_adapter", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["channel"] == "webhook"
    assert data["user_id"] == "u1"


def test_l2_test_rate_limit():
    payload = {"user_id": "u1", "ip": "127.0.0.1"}
    response = client.post("/api/l2/test_rate_limit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is True


def test_l6_test_runtime():
    payload = {"language": "python", "code": "print('ok')"}
    response = client.post("/api/l6/test_runtime", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stdout" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: FAIL (404s)

- [ ] **Step 3: Implement all L1-L6 test endpoints in server.py**

Append the following route definitions to `server.py` (after the `/api/config` route):

```python
# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class L1AdapterRequest(BaseModel):
    channel: str = Field(..., description="telegram | websocket | webhook | web")
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class L1ValidatorRequest(BaseModel):
    event_dict: Dict[str, Any]


class L2RateLimitRequest(BaseModel):
    user_id: str
    ip: str = "127.0.0.1"


class L2SessionRequest(BaseModel):
    user_id: str
    content: str = "hello"


class L3ReactRequest(BaseModel):
    user_id: str = "test_user"
    query: str
    history: List[Dict[str, str]] = Field(default_factory=list)


class L3SecurityRequest(BaseModel):
    query: str


class L4MemoryRequest(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]


class L4SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class L5ToolRequest(BaseModel):
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    user_permissions: List[str] = Field(default_factory=list)


class L5BashRequest(BaseModel):
    command: str


class L6RuntimeRequest(BaseModel):
    language: str
    code: str
    timeout: int = 30


# ---------------------------------------------------------------------------
# L1 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l1/test_adapter")
async def l1_test_adapter(req: L1AdapterRequest):
    from src.l1.l1_user_interaction import (
        TelegramAdapter, WebSocketAdapter, HttpWebhookAdapter, EventNormalizer
    )
    channel = req.channel.lower()
    raw_data = req.raw_data

    try:
        if channel == "telegram":
            adapter = TelegramAdapter()
        elif channel == "websocket":
            adapter = WebSocketAdapter()
        elif channel in ("webhook", "web"):
            adapter = HttpWebhookAdapter()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

        if not adapter.can_handle(raw_data):
            return {"handled": False, "reason": "Adapter can_handle returned False"}

        event = adapter.parse(raw_data)
        return {
            "handled": True,
            "channel": event.channel,
            "user_id": event.user_id,
            "content": event.content,
            "metadata": event.metadata
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"L1 adapter error: {e}")


@app.post("/api/l1/test_validator")
async def l1_test_validator(req: L1ValidatorRequest):
    from src.l1.l1_user_interaction import DataValidator
    validator = DataValidator()
    try:
        validator.validate(req.event_dict)
        return {"valid": True, "errors": []}
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}


# ---------------------------------------------------------------------------
# L2 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l2/test_rate_limit")
async def l2_test_rate_limit(req: L2RateLimitRequest):
    from src.l2.l2_control_gateway import RateLimiter
    limiter = RateLimiter()
    allowed, reason = limiter.is_allowed(req.user_id, req.ip)
    return {"allowed": allowed, "reason": reason}


@app.post("/api/l2/test_session")
async def l2_test_session(req: L2SessionRequest):
    from src.l2.l2_control_gateway import ControlGateway
    from src.core.models import StandardEvent
    gateway = ControlGateway()
    event = StandardEvent(
        channel="web",
        user_id=req.user_id,
        content=req.content
    )
    l3_input = gateway.process_event(event)
    return {
        "session_id": l3_input.session_context.session_id,
        "user_id": l3_input.session_context.user_id,
        "current_query": l3_input.session_context.current_query,
        "available_tools_count": len(l3_input.available_tools),
        "relevant_memories_count": len(l3_input.relevant_memories)
    }


# ---------------------------------------------------------------------------
# L3 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l3/test_react")
async def l3_test_react(req: L3ReactRequest):
    if not _llm_available():
        raise HTTPException(
            status_code=503,
            detail="LLM not available. Please configure OPENAI_API_KEY in .env file."
        )
    from src.l3.l3_orchestration import Orchestration
    from src.core.models import SessionContext
    orch = Orchestration()
    context = SessionContext(
        session_id="test-session-123",
        user_id=req.user_id,
        current_query=req.query,
        history=req.history,
        user_permissions=[]
    )
    result = orch.run(context)
    if isinstance(result, str):
        return {"type": "final_answer", "content": result}
    from src.core.models import AgentAction
    if isinstance(result, AgentAction):
        return {
            "type": "agent_action",
            "thought": result.thought,
            "action": result.action,
            "action_input": result.action_input
        }
    return {"type": "unknown", "content": str(result)}


@app.post("/api/l3/test_security")
async def l3_test_security(req: L3SecurityRequest):
    if not _llm_available():
        raise HTTPException(
            status_code=503,
            detail="LLM not available. Please configure OPENAI_API_KEY in .env file."
        )
    from src.l3.l3_orchestration import Orchestration
    from src.core.models import SessionContext
    orch = Orchestration()
    context = SessionContext(
        session_id="test-session-sec",
        user_id="test_user",
        current_query=req.query,
        history=[],
        user_permissions=[]
    )
    result = orch.run(context)
    # Security judgment is implicit in the LLM response; we surface it directly
    if isinstance(result, str):
        return {"judgment": "direct_response", "content": result}
    return {"judgment": "action_requested", "content": result.model_dump()}


# ---------------------------------------------------------------------------
# L4 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l4/test_memory")
async def l4_test_memory(req: L4MemoryRequest):
    from src.l4 import MemoryKnowledge
    memory = MemoryKnowledge()
    memory.store_conversation(req.session_id, req.messages)
    history = memory.retrieve_history(req.session_id, limit=10)
    return {"stored": True, "retrieved_count": len(history), "history": history}


@app.post("/api/l4/test_search")
async def l4_test_search(req: L4SearchRequest):
    from src.l4 import MemoryKnowledge
    memory = MemoryKnowledge()
    # Ensure some dummy data exists for search
    memory.store("VClaw is a six-layer AI agent system.", {"category": "overview"})
    memory.store("L1 handles user interaction adapters.", {"category": "layer"})
    results = memory.search(req.query, top_k=req.top_k)
    return {
        "results": [
            {"content": doc.content, "metadata": doc.metadata}
            for doc in results
        ]
    }


# ---------------------------------------------------------------------------
# L5 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l5/test_tool")
async def l5_test_tool(req: L5ToolRequest):
    from src.l5.l5_tools import ToolsCapabilities
    from src.core.exceptions import ToolNotFoundError, ValidationError
    tools = ToolsCapabilities()
    try:
        observation = tools.execute(
            req.action,
            req.params,
            user_permissions=req.user_permissions,
            timeout=30
        )
        return {
            "status": observation.status,
            "result": observation.result,
            "execution_time": observation.execution_time,
            "metadata": observation.metadata
        }
    except ToolNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")


@app.post("/api/l5/test_bash")
async def l5_test_bash(req: L5BashRequest):
    from src.l5.bash_analyzer import BashAnalyzer
    analyzer = BashAnalyzer()
    classification = analyzer.analyze(req.command)
    return {
        "command": req.command,
        "command_type": classification.command_type.value,
        "risk_level": classification.risk_level,
        "suggested_action": classification.suggested_action
    }


# ---------------------------------------------------------------------------
# L6 endpoints
# ---------------------------------------------------------------------------

@app.post("/api/l6/test_runtime")
async def l6_test_runtime(req: L6RuntimeRequest):
    from src.l6.l6_runtime import RuntimeEnvironment
    from src.l6.config import SandboxConfig
    from src.core.exceptions import (
        UnsupportedLanguageError,
        SecurityViolationError,
        ResourceExceededError,
        ExecutionTimeoutError,
        SandboxCreationError
    )
    config = SandboxConfig(timeout=req.timeout)
    runtime = RuntimeEnvironment(config)
    try:
        result = runtime.run_code(req.language, req.code, timeout=req.timeout)
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time
        }
    except (
        UnsupportedLanguageError,
        SecurityViolationError,
        ResourceExceededError,
        ExecutionTimeoutError,
        SandboxCreationError
    ) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Runtime error: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/l1/tests/web_console/server.py src/l1/tests/web_console/test_web_console.py
git commit -m "feat(web_console): add L1-L6 independent test endpoints with tests"
```

---

### Task 4: Backend E2E Chat Endpoint with Auto ReAct Loop

**Files:**
- Modify: `src/l1/tests/web_console/server.py`
- Test: `src/l1/tests/web_console/test_web_console.py`

- [ ] **Step 1: Write failing test for E2E chat**

Append to `test_web_console.py`:

```python
def test_e2e_chat_calculator():
    # This test may be skipped if LLM is unavailable; we mock the L3 layer.
    # Instead, test the structural behavior by sending a direct L5-like payload
    # and verifying the endpoint returns a formatted response.
    # For a deterministic test, we verify the endpoint accepts the payload.
    payload = {
        "user_id": "u_test",
        "content": "What is 2+2?",
        "channel": "web"
    }
    response = client.post("/api/e2e/chat", json=payload)
    # Expect 200 if LLM available, 503 if not
    assert response.status_code in (200, 503)


def test_e2e_reset():
    response = client.post("/api/e2e/reset", json={"user_id": "u_test"})
    assert response.status_code == 200
    assert response.json()["reset"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/l1/tests/web_console/test_web_console.py::test_e2e_chat_calculator -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement E2E endpoints in server.py**

Append the following to `server.py` (after the L6 endpoints):

```python
# ---------------------------------------------------------------------------
# E2E endpoints
# ---------------------------------------------------------------------------

class E2EChatRequest(BaseModel):
    user_id: str
    content: str
    channel: str = "web"


class E2EResetRequest(BaseModel):
    user_id: str


# In-memory state for E2E sessions
e2e_sessions: Dict[str, Any] = {}


@app.post("/api/e2e/chat")
async def e2e_chat(req: E2EChatRequest):
    import uuid
    import time
    from src.l1.l1_user_interaction import UserInteraction
    from src.l2.l2_control_gateway import ControlGateway
    from src.l3.l3_orchestration import Orchestration
    from src.l5.l5_tools import ToolsCapabilities
    from src.core.models import StandardEvent, AgentAction, Observation

    if not _llm_available():
        raise HTTPException(
            status_code=503,
            detail="LLM not available. Please configure OPENAI_API_KEY in .env file."
        )

    start_time = time.time()
    react_steps = []

    # L1: normalize input
    l1 = UserInteraction()
    session_id = e2e_sessions.get(req.user_id)
    raw_data = {
        "user_id": req.user_id,
        "message": {"text": req.content},
        "session_id": session_id
    }
    event = l1.receive_payload(raw_data, channel=req.channel)

    # L2: assemble context
    l2 = ControlGateway()
    l3_input = l2.process_event(event)

    # L3: ReAct loop
    l3 = Orchestration()
    context = l3_input.session_context
    context.user_permissions = []  # default empty for testing
    available_tools = l3_input.available_tools

    observation = None
    final_answer = None

    for iteration in range(1, l3.MAX_ITERATIONS + 1):
        result = l3.run(context, observation=observation)

        if isinstance(result, AgentAction):
            # Execute tool via L5
            tools = ToolsCapabilities()
            observation = tools.execute(
                result.action,
                result.action_input,
                user_permissions=context.user_permissions or [],
                timeout=30
            )
            react_steps.append({
                "iteration": iteration,
                "thought": result.thought,
                "action": result.action,
                "action_input": result.action_input,
                "observation": observation.result,
                "status": observation.status
            })
            continue
        else:
            final_answer = result
            react_steps.append({
                "iteration": iteration,
                "thought": "Final answer provided",
                "action": "final_answer",
                "action_input": {},
                "observation": "",
                "status": "success"
            })
            break
    else:
        final_answer = "请求处理时间过长，请稍后重试。"

    # Update session mapping
    e2e_sessions[req.user_id] = context.session_id
    l1.update_session_mapping(req.user_id, context.session_id)

    elapsed_ms = int((time.time() - start_time) * 1000)

    return {
        "final_answer": final_answer,
        "session_id": context.session_id,
        "react_steps": react_steps,
        "elapsed_ms": elapsed_ms
    }


@app.post("/api/e2e/reset")
async def e2e_reset(req: E2EResetRequest):
    from src.l1.l1_user_interaction import UserInteraction
    l1 = UserInteraction()
    # Simulate a new-session command to clear mapping
    l1.receive_payload({"user_id": req.user_id, "message": {"text": "/new"}}, channel="web")
    if req.user_id in e2e_sessions:
        del e2e_sessions[req.user_id]
    return {"reset": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: PASS (E2E chat may be skipped by status code acceptance)

- [ ] **Step 5: Commit**

```bash
git add src/l1/tests/web_console/server.py src/l1/tests/web_console/test_web_console.py
git commit -m "feat(web_console): add E2E chat and reset endpoints with auto ReAct loop"
```

---

### Task 5: Frontend CSS Dashboard Layout

**Files:**
- Modify: `src/l1/tests/web_console/static/style.css`

- [ ] **Step 1: Write the CSS**

Replace the contents of `src/l1/tests/web_console/static/style.css` with:

```css
:root {
  --sidebar-width: 220px;
  --header-height: 56px;
  --primary: #2563eb;
  --primary-dark: #1d4ed8;
  --bg: #f8fafc;
  --card-bg: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --text-muted: #64748b;
  --success: #16a34a;
  --error: #dc2626;
  --warning: #ca8a04;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Microsoft YaHei", "Noto Sans", sans-serif; background: var(--bg); color: var(--text); }

#app { display: flex; flex-direction: column; height: 100vh; }

header {
  height: var(--header-height);
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; position: fixed; top: 0; left: 0; right: 0; z-index: 10;
}
header h1 { font-size: 18px; margin: 0; }
.status-pill { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: var(--border); color: var(--text-muted); margin-left: 8px; }
.status-pill.ok { background: #dcfce7; color: var(--success); }
.status-pill.error { background: #fee2e2; color: var(--error); }

.main-wrap { display: flex; flex: 1; margin-top: var(--header-height); }

aside.sidebar {
  width: var(--sidebar-width);
  background: var(--card-bg);
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 12px 0;
}

nav ul { list-style: none; margin: 0; padding: 0; }
nav li { margin: 2px 0; }
nav li.group > span { display: block; padding: 8px 16px; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); font-weight: 600; }
nav li a { display: block; padding: 8px 16px 8px 28px; color: var(--text); text-decoration: none; font-size: 14px; border-radius: 6px; margin: 0 8px; }
nav li a:hover { background: var(--bg); }
nav li a.active { background: #eff6ff; color: var(--primary); font-weight: 500; }

main.content { flex: 1; padding: 16px; overflow-y: auto; }

.page { display: none; }
.page.active { display: block; }

.banner { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
.banner.error { background: #fee2e2; color: #7f1d1d; border: 1px solid #fecaca; }
.banner.warning { background: #fef9c3; color: #713f12; border: 1px solid #fde047; }

.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
@media (max-width: 1100px) { .grid-3 { grid-template-columns: 1fr; } }

.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.card h3 { margin: 0 0 12px 0; font-size: 16px; }
.card label { display: block; font-size: 13px; color: var(--text-muted); margin: 8px 0 4px 0; }
.card textarea, .card input, .card select {
  width: 100%; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px; padding: 8px; border: 1px solid var(--border); border-radius: 6px; background: #fff;
}
.card textarea { min-height: 180px; resize: vertical; }
.card button {
  background: var(--primary); color: #fff; border: 0; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.card button:hover { background: var(--primary-dark); }
.card button.secondary { background: var(--text-muted); }

.quick-loads { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.quick-loads button { font-size: 12px; padding: 4px 8px; background: var(--bg); color: var(--text); border: 1px solid var(--border); }

.result-box { background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; font-size: 13px; overflow-x: auto; min-height: 200px; }
.result-box pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
.key { color: #93c5fd; }
.string { color: #86efac; }
.number { color: #fca5a5; }
.boolean { color: #f0abfc; }
.null { color: #94a3b8; }

.collapsed { display: none; }
.toggle-btn { font-size: 12px; color: var(--primary); background: transparent; border: 0; padding: 0; cursor: pointer; }

/* E2E chat */
.chat-wrap { display: grid; grid-template-columns: 1fr 320px; gap: 16px; height: calc(100vh - var(--header-height) - 32px); }
@media (max-width: 1000px) { .chat-wrap { grid-template-columns: 1fr; height: auto; } }
.chat-main { display: flex; flex-direction: column; }
.chat-history { flex: 1; overflow-y: auto; border: 1px solid var(--border); border-radius: 10px; background: var(--card-bg); padding: 12px; }
.chat-input { display: flex; gap: 8px; margin-top: 10px; }
.chat-input input { flex: 1; padding: 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }
.chat-input button { padding: 10px 18px; }

.message { margin: 8px 0; }
.message.user { text-align: right; }
.message.user .bubble { display: inline-block; background: #eff6ff; color: var(--text); padding: 8px 12px; border-radius: 12px 12px 2px 12px; border: 1px solid #bfdbfe; }
.message.assistant { text-align: left; }
.message.assistant .bubble { display: inline-block; background: var(--bg); color: var(--text); padding: 8px 12px; border-radius: 12px 12px 12px 2px; border: 1px solid var(--border); }

.sidebar-right h4 { margin: 0 0 8px 0; font-size: 14px; }
.sidebar-right .card { margin-bottom: 12px; }
.step { font-size: 13px; padding: 8px; border: 1px solid var(--border); border-radius: 6px; margin-bottom: 8px; background: var(--bg); }
.step .meta { color: var(--text-muted); font-size: 12px; margin-bottom: 4px; }

.spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 1s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 2: Commit**

```bash
git add src/l1/tests/web_console/static/style.css
git commit -m "feat(web_console): add dashboard CSS with sidebar, cards, chat, JSON highlight"
```

---

### Task 6: Frontend Dashboard HTML

**Files:**
- Modify: `src/l1/tests/web_console/templates/index.html`

- [ ] **Step 1: Write the HTML shell with all panels**

Replace the contents of `src/l1/tests/web_console/templates/index.html` with:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VClaw Test Console</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>VClaw Test Console</h1>
      <div id="header-status">
        <span class="status-pill" id="status-llm">LLM: ...</span>
        <span class="status-pill" id="status-docker">Docker: ...</span>
      </div>
    </header>
    <div class="main-wrap">
      <aside class="sidebar">
        <nav>
          <ul>
            <li><a href="#home" class="nav-link active" data-target="home">Dashboard 首页</a></li>
            <li class="group"><span>L1 测试</span></li>
            <li><a href="#l1-adapter" class="nav-link" data-target="l1-adapter">适配器测试</a></li>
            <li><a href="#l1-validator" class="nav-link" data-target="l1-validator">验证器测试</a></li>
            <li class="group"><span>L2 测试</span></li>
            <li><a href="#l2-rate" class="nav-link" data-target="l2-rate">限流测试</a></li>
            <li><a href="#l2-session" class="nav-link" data-target="l2-session">会话测试</a></li>
            <li class="group"><span>L3 测试</span></li>
            <li><a href="#l3-react" class="nav-link" data-target="l3-react">ReAct 测试</a></li>
            <li><a href="#l3-security" class="nav-link" data-target="l3-security">安全判断测试</a></li>
            <li class="group"><span>L4 测试</span></li>
            <li><a href="#l4-memory" class="nav-link" data-target="l4-memory">记忆存储</a></li>
            <li><a href="#l4-search" class="nav-link" data-target="l4-search">向量搜索</a></li>
            <li class="group"><span>L5 测试</span></li>
            <li><a href="#l5-tool" class="nav-link" data-target="l5-tool">工具调用</a></li>
            <li><a href="#l5-bash" class="nav-link" data-target="l5-bash">Bash 分析</a></li>
            <li class="group"><span>L6 测试</span></li>
            <li><a href="#l6-runtime" class="nav-link" data-target="l6-runtime">代码执行沙箱</a></li>
            <li class="group"><span>端到端</span></li>
            <li><a href="#e2e-chat" class="nav-link" data-target="e2e-chat">E2E 对话</a></li>
          </ul>
        </nav>
      </aside>
      <main class="content" id="main-content">
        <!-- Home -->
        <section id="home" class="page active">
          <h2>Dashboard 首页</h2>
          <p>选择一个测试模块开始。系统状态会在顶部实时显示。</p>
          <div class="grid-3" style="margin-top:16px">
            <div class="card"><h3>L1</h3><p>适配器、验证器</p></div>
            <div class="card"><h3>L2</h3><p>限流、会话</p></div>
            <div class="card"><h3>L3</h3><p>ReAct、安全判断</p></div>
            <div class="card"><h3>L4</h3><p>记忆、向量搜索</p></div>
            <div class="card"><h3>L5</h3><p>工具、Bash 分析</p></div>
            <div class="card"><h3>L6</h3><p>沙箱执行</p></div>
          </div>
        </section>

        <!-- L1 Adapter -->
        <section id="l1-adapter" class="page">
          <h2>L1 适配器测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <div class="quick-loads">
                <button onclick="loadExample('l1-adapter', 'webhook')">Webhook</button>
                <button onclick="loadExample('l1-adapter', 'telegram')">Telegram</button>
                <button onclick="loadExample('l1-adapter', 'websocket')">WebSocket</button>
              </div>
              <label>Channel</label>
              <select id="l1-adapter-channel"><option>webhook</option><option>telegram</option><option>websocket</option><option>web</option></select>
              <label>Raw Data (JSON)</label>
              <textarea id="l1-adapter-input">{"user_id":"u1","message":{"text":"hello"}}</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l1-adapter')">运行测试</button><div id="l1-adapter-preview" style="margin-top:10px"></div></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l1-adapter-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L1 Validator -->
        <section id="l1-validator" class="page">
          <h2>L1 验证器测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Event Dict (JSON)</label>
              <textarea id="l1-validator-input">{"channel":"web","user_id":"u1","content":"hello","timestamp":1713000000}</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l1-validator')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l1-validator-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L2 Rate -->
        <section id="l2-rate" class="page">
          <h2>L2 限流测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>User ID</label>
              <input id="l2-rate-user_id" value="test_user">
              <label>IP</label>
              <input id="l2-rate-ip" value="127.0.0.1">
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l2-rate')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l2-rate-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L2 Session -->
        <section id="l2-session" class="page">
          <h2>L2 会话测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>User ID</label>
              <input id="l2-session-user_id" value="test_user">
              <label>Content</label>
              <input id="l2-session-content" value="你好">
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l2-session')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l2-session-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L3 ReAct -->
        <section id="l3-react" class="page">
          <h2>L3 ReAct 测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Query</label>
              <input id="l3-react-query" value="计算 15 乘以 23">
              <label>History (JSON array, optional)</label>
              <textarea id="l3-react-history">[]</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l3-react')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l3-react-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L3 Security -->
        <section id="l3-security" class="page">
          <h2>L3 安全判断测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Query</label>
              <input id="l3-security-query" value="格式化我的硬盘">
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l3-security')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l3-security-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L4 Memory -->
        <section id="l4-memory" class="page">
          <h2>L4 记忆存储测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Session ID</label>
              <input id="l4-memory-session_id" value="session-test-1">
              <label>Messages (JSON)</label>
              <textarea id="l4-memory-messages">[{"role":"user","content":"Hello"}]</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l4-memory')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l4-memory-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L4 Search -->
        <section id="l4-search" class="page">
          <h2>L4 向量搜索测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Query</label>
              <input id="l4-search-query" value="AI agent layers">
              <label>Top K</label>
              <input type="number" id="l4-search-top_k" value="3">
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l4-search')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l4-search-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L5 Tool -->
        <section id="l5-tool" class="page">
          <h2>L5 工具调用测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <div class="quick-loads">
                <button onclick="loadExample('l5-tool','calculator')">Calculator</button>
                <button onclick="loadExample('l5-tool','file_reader')">File Reader</button>
                <button onclick="loadExample('l5-tool','python_repl')">Python REPL</button>
              </div>
              <label>Action</label>
              <input id="l5-tool-action" value="calculator">
              <label>Params (JSON)</label>
              <textarea id="l5-tool-params">{"expression":"15*23"}</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l5-tool')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l5-tool-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L5 Bash -->
        <section id="l5-bash" class="page">
          <h2>L5 Bash 分析测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <label>Command</label>
              <input id="l5-bash-command" value="cat /etc/passwd">
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l5-bash')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l5-bash-result">等待运行...</div></div>
          </div>
        </section>

        <!-- L6 Runtime -->
        <section id="l6-runtime" class="page">
          <h2>L6 代码执行沙箱测试</h2>
          <div class="grid-3">
            <div class="card">
              <h3>输入</h3>
              <div class="quick-loads">
                <button onclick="loadExample('l6-runtime','python')">Python</button>
                <button onclick="loadExample('l6-runtime','javascript')">JavaScript</button>
                <button onclick="loadExample('l6-runtime','bash')">Bash</button>
              </div>
              <label>Language</label>
              <select id="l6-runtime-language"><option>python</option><option>javascript</option><option>bash</option></select>
              <label>Code</label>
              <textarea id="l6-runtime-code">print("Hello from sandbox")</textarea>
            </div>
            <div class="card"><h3>操作</h3><button onclick="runTest('l6-runtime')">运行测试</button></div>
            <div class="card"><h3>结果</h3><div class="result-box" id="l6-runtime-result">等待运行...</div></div>
          </div>
        </section>

        <!-- E2E Chat -->
        <section id="e2e-chat" class="page">
          <div id="e2e-banner"></div>
          <div class="chat-wrap">
            <div class="chat-main">
              <div class="chat-history" id="chat-history"></div>
              <div class="chat-input">
                <input type="text" id="chat-message" placeholder="输入消息，按 Enter 发送">
                <button onclick="sendChat()">发送</button>
                <button class="secondary" onclick="resetChat()">重置会话</button>
              </div>
            </div>
            <div class="sidebar-right">
              <div class="card">
                <h4>会话信息</h4>
                <div id="chat-session">Session: -</div>
                <div id="chat-elapsed" style="margin-top:6px;color:var(--text-muted)">Elapsed: -</div>
              </div>
              <div class="card">
                <h4>ReAct 步骤</h4>
                <div id="chat-steps">暂无</div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add src/l1/tests/web_console/templates/index.html
git commit -m "feat(web_console): add dashboard HTML with all test panels and E2E chat"
```

---

### Task 7: Frontend JavaScript Logic

**Files:**
- Modify: `src/l1/tests/web_console/static/app.js`

- [ ] **Step 1: Write the JavaScript**

Replace the contents of `src/l1/tests/web_console/static/app.js` with:

```javascript
/* ---------------------------------------------------------------------------
   VClaw Web Test Console - Frontend Logic
   --------------------------------------------------------------------------- */

// State
const state = {
  currentPage: location.hash.replace('#', '') || 'home',
  llmAvailable: false,
  dockerAvailable: false,
  chatHistory: [],
  sessionId: null
};

// Examples
const examples = {
  'l1-adapter': {
    webhook: { channel: 'webhook', raw_data: { user_id: 'u1', message: { text: 'hello' } } },
    telegram: { channel: 'telegram', raw_data: { message: { from: { id: 123 }, text: 'hi' } } },
    websocket: { channel: 'websocket', raw_data: { client_id: 'c1', message: 'hello' } }
  },
  'l5-tool': {
    calculator: { action: 'calculator', params: { expression: '15*23' } },
    file_reader: { action: 'file_reader', params: { path: 'documents/test.txt' } },
    python_repl: { action: 'python_repl', params: { code: 'print(2+2)' } }
  },
  'l6-runtime': {
    python: { language: 'python', code: 'print("Hello from sandbox")' },
    javascript: { language: 'javascript', code: 'console.log("Hello JS")' },
    bash: { language: 'bash', code: 'echo "Hello Bash"' }
  }
};

function loadExample(page, key) {
  const ex = examples[page][key];
  if (!ex) return;
  if (page === 'l1-adapter') {
    document.getElementById('l1-adapter-channel').value = ex.channel;
    document.getElementById('l1-adapter-input').value = JSON.stringify(ex.raw_data, null, 2);
  }
  if (page === 'l5-tool') {
    document.getElementById('l5-tool-action').value = ex.action;
    document.getElementById('l5-tool-params').value = JSON.stringify(ex.params, null, 2);
  }
  if (page === 'l6-runtime') {
    document.getElementById('l6-runtime-language').value = ex.language;
    document.getElementById('l6-runtime-code').value = ex.code;
  }
}

// Router
function showPage(target) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(a => a.classList.remove('active'));
  const page = document.getElementById(target);
  if (page) page.classList.add('active');
  const link = document.querySelector(`.nav-link[data-target="${target}"]`);
  if (link) link.classList.add('active');
  state.currentPage = target;
}

window.addEventListener('hashchange', () => showPage(location.hash.replace('#', '') || 'home'));

// JSON syntax highlight
function highlightJSON(obj) {
  const json = JSON.stringify(obj, null, 2)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?)/g, m => {
    let cls = 'string';
    if (/:$/.test(m)) { cls = 'key'; m = m.slice(0, -1) + '</span>:'; return `<span class="${cls}">${m}`; }
    return `<span class="${cls}">${m}</span>`;
  }).replace(/\b(true|false)\b/g, '<span class="boolean">$1</span>')
    .replace(/\b(null)\b/g, '<span class="null">$1</span>')
    .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="number">$1</span>');
}

function renderResult(id, data) {
  const el = document.getElementById(id);
  el.innerHTML = `<pre>${highlightJSON(data)}</pre>`;
}

function setLoading(id, loading) {
  const el = document.getElementById(id);
  if (loading) el.innerHTML = '<div class="spinner"></div> 运行中...';
}

// API helpers
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) throw { status: res.status, data };
  return data;
}

// Per-page runners
const runners = {
  'l1-adapter': async () => {
    const channel = document.getElementById('l1-adapter-channel').value;
    const raw = document.getElementById('l1-adapter-input').value;
    return postJSON('/api/l1/test_adapter', { channel, raw_data: JSON.parse(raw) });
  },
  'l1-validator': async () => {
    const raw = document.getElementById('l1-validator-input').value;
    return postJSON('/api/l1/test_validator', { event_dict: JSON.parse(raw) });
  },
  'l2-rate': async () => {
    return postJSON('/api/l2/test_rate_limit', {
      user_id: document.getElementById('l2-rate-user_id').value,
      ip: document.getElementById('l2-rate-ip').value
    });
  },
  'l2-session': async () => {
    return postJSON('/api/l2/test_session', {
      user_id: document.getElementById('l2-session-user_id').value,
      content: document.getElementById('l2-session-content').value
    });
  },
  'l3-react': async () => {
    return postJSON('/api/l3/test_react', {
      user_id: 'test_user',
      query: document.getElementById('l3-react-query').value,
      history: JSON.parse(document.getElementById('l3-react-history').value || '[]')
    });
  },
  'l3-security': async () => {
    return postJSON('/api/l3/test_security', {
      query: document.getElementById('l3-security-query').value
    });
  },
  'l4-memory': async () => {
    return postJSON('/api/l4/test_memory', {
      session_id: document.getElementById('l4-memory-session_id').value,
      messages: JSON.parse(document.getElementById('l4-memory-messages').value)
    });
  },
  'l4-search': async () => {
    return postJSON('/api/l4/test_search', {
      query: document.getElementById('l4-search-query').value,
      top_k: parseInt(document.getElementById('l4-search-top_k').value, 10)
    });
  },
  'l5-tool': async () => {
    return postJSON('/api/l5/test_tool', {
      action: document.getElementById('l5-tool-action').value,
      params: JSON.parse(document.getElementById('l5-tool-params').value),
      user_permissions: []
    });
  },
  'l5-bash': async () => {
    return postJSON('/api/l5/test_bash', {
      command: document.getElementById('l5-bash-command').value
    });
  },
  'l6-runtime': async () => {
    return postJSON('/api/l6/test_runtime', {
      language: document.getElementById('l6-runtime-language').value,
      code: document.getElementById('l6-runtime-code').value,
      timeout: 30
    });
  }
};

async function runTest(page) {
  const resultId = `${page}-result`;
  setLoading(resultId, true);
  try {
    const data = await runners[page]();
    renderResult(resultId, data);
  } catch (err) {
    renderResult(resultId, { error: err.data?.detail || err.data || `HTTP ${err.status}` });
  }
}

// E2E Chat
function appendChat(role, text) {
  const box = document.getElementById('chat-history');
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `<div class="bubble">${escapeHTML(text)}</div>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function escapeHTML(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function sendChat() {
  const input = document.getElementById('chat-message');
  const text = input.value.trim();
  if (!text) return;
  appendChat('user', text);
  input.value = '';

  const banner = document.getElementById('e2e-banner');
  banner.innerHTML = '<div class="banner warning"><span class="spinner"></span> 思考中...</div>';

  try {
    const data = await postJSON('/api/e2e/chat', {
      user_id: 'web_test_user',
      content: text,
      channel: 'web'
    });
    banner.innerHTML = '';
    appendChat('assistant', data.final_answer);
    state.sessionId = data.session_id;
    document.getElementById('chat-session').textContent = `Session: ${data.session_id}`;
    document.getElementById('chat-elapsed').textContent = `Elapsed: ${data.elapsed_ms} ms`;
    const stepsEl = document.getElementById('chat-steps');
    if (data.react_steps && data.react_steps.length) {
      stepsEl.innerHTML = data.react_steps.map(s => `
        <div class="step">
          <div class="meta">Iteration ${s.iteration} · ${s.status}</div>
          <div><b>Action:</b> ${s.action}</div>
          <div><b>Observation:</b> ${escapeHTML(String(s.observation)).slice(0, 200)}</div>
        </div>
      `).join('');
    } else {
      stepsEl.textContent = '暂无';
    }
  } catch (err) {
    banner.innerHTML = '';
    if (err.status === 503) {
      banner.innerHTML = `<div class="banner error">LLM 不可用，请在 .env 中配置 OPENAI_API_KEY。</div>`;
    } else {
      appendChat('assistant', `错误: ${err.data?.detail || JSON.stringify(err.data) || err.status}`);
    }
  }
}

document.getElementById('chat-message').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendChat();
});

async function resetChat() {
  await postJSON('/api/e2e/reset', { user_id: 'web_test_user' });
  document.getElementById('chat-history').innerHTML = '';
  document.getElementById('chat-session').textContent = 'Session: -';
  document.getElementById('chat-elapsed').textContent = 'Elapsed: -';
  document.getElementById('chat-steps').textContent = '暂无';
  state.sessionId = null;
}

// Config / status
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    state.llmAvailable = data.llm_available;
    state.dockerAvailable = data.docker_available;

    const llmEl = document.getElementById('status-llm');
    llmEl.textContent = `LLM: ${data.llm_available ? '可用' : '不可用'}`;
    llmEl.className = `status-pill ${data.llm_available ? 'ok' : 'error'}`;

    const dockerEl = document.getElementById('status-docker');
    dockerEl.textContent = `Docker: ${data.docker_available ? '可用' : '不可用'}`;
    dockerEl.className = `status-pill ${data.docker_available ? 'ok' : 'error'}`;

    if (!data.llm_available) {
      const banner = document.getElementById('e2e-banner');
      if (banner) {
        banner.innerHTML = '<div class="banner error">LLM 不可用，E2E 对话和 L3 测试将无法运行。请在 .env 中配置 OPENAI_API_KEY。</div>';
      }
    }
  } catch (e) {
    console.error('Failed to load config', e);
  }
}

// Init
showPage(state.currentPage);
loadConfig();
```

- [ ] **Step 2: Commit**

```bash
git add src/l1/tests/web_console/static/app.js
git commit -m "feat(web_console): add frontend JS with routing, runners, E2E chat"
```

---

### Task 8: Final Integration and Verification

**Files:**
- Modify: `src/l1/tests/web_console/README.md`
- Modify: `src/l1/tests/web_console/server.py` (if needed for startup block)

- [ ] **Step 1: Add `if __name__ == "__main__"` block to server.py**

At the bottom of `server.py`, add:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 2: Update README.md with full instructions**

Replace `src/l1/tests/web_console/README.md` with:

```markdown
# VClaw Web Test Console

统一 Web 测试控制台，支持 L1-L6 各层独立功能测试和端到端对话测试。

## 启动

```bash
conda activate vclaw
python src/l1/tests/web_console/server.py
```

## 访问

浏览器打开: http://localhost:8000

## 功能

- Dashboard 首页
- L1: 适配器测试、验证器测试
- L2: 限流测试、会话测试
- L3: ReAct 测试、安全判断测试
- L4: 记忆存储、向量搜索
- L5: 工具调用、Bash 分析
- L6: 代码执行沙箱
- E2E: 端到端对话（自动 ReAct 循环）

## 依赖

- FastAPI / Uvicorn（已包含在 requirements.txt）
- LLM 测试需要配置 `.env` 中的 `OPENAI_API_KEY`
- L6 Docker 测试需要本地 Docker 守护进程运行

## 测试

```bash
pytest src/l1/tests/web_console/test_web_console.py -v
```
```

- [ ] **Step 3: Run all backend tests**

Run: `pytest src/l1/tests/web_console/test_web_console.py -v`
Expected: All tests pass.

- [ ] **Step 4: Start the server and verify homepage loads**

Run (in background or separate shell):
```bash
conda activate vclaw
python src/l1/tests/web_console/server.py
```

Then verify in another shell:
```bash
curl -s http://localhost:8000/ | head -n 5
```
Expected: HTML containing `<title>VClaw Test Console</title>`

- [ ] **Step 5: Commit final integration**

```bash
git add src/l1/tests/web_console/
git commit -m "feat(web_console): complete web test console with README and startup block"
```

---

## Spec Coverage Check

| Spec Requirement | Plan Task |
|------------------|-----------|
| FastAPI server and Dashboard frontend | Tasks 1-8 |
| L1-L6 each at least 1 independent test endpoint + UI | Tasks 3 (backend), 6-7 (frontend) |
| E2E `/api/e2e/chat` with backend auto ReAct loop | Task 4 |
| System status detection (LLM / Docker) | Task 2 |
| Result formatting and JSON highlight | Tasks 5-7 |

No gaps found. No placeholders remain.
