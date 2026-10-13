"""VClaw Web Test Console - FastAPI server."""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Load .env before any imports that may depend on environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env", override=True)
except Exception:
    pass

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
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
    return templates.TemplateResponse(request, "index.html", {})


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
        "tools": [t.name for t in registry.list_tools()]
    }


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


class E2EChatRequest(BaseModel):
    user_id: str
    content: str
    channel: str = "web"


class E2EResetRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# L1 endpoints
# ---------------------------------------------------------------------------


@app.post("/api/l1/test_adapter")
async def l1_test_adapter(req: L1AdapterRequest):
    from src.l1.l1_user_interaction import (
        TelegramAdapter, WebSocketAdapter, HttpWebhookAdapter
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
            # Preprocess common test formats to match adapter expectations
            if "user_id" in raw_data and "message" in raw_data and isinstance(raw_data.get("message"), dict):
                payload = {
                    "user_id": raw_data["user_id"],
                    "message": raw_data["message"].get("text", ""),
                }
                if raw_data.get("timestamp") is not None:
                    payload["timestamp"] = raw_data["timestamp"]
                raw_data = {
                    "event": "message",
                    "payload": payload
                }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

        # For test endpoint, if channel is explicitly specified, try parse even if can_handle is False
        if not adapter.can_handle(raw_data) and channel not in ("webhook", "web"):
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
    memory.store("VClaw is a six-layer AI agent system.", {"doc_id": "doc1", "category": "overview"})
    memory.store("L1 handles user interaction adapters.", {"doc_id": "doc2", "category": "layer"})
    results = memory.search(req.query, top_k=req.top_k)
    return {
        "results": [
            {"content": doc}
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
    parsed = analyzer.analyze_command(req.command)
    return {
        "command": req.command,
        "command_type": parsed.command_type.value,
        "risk_level": "high" if parsed.is_destructive else ("medium" if parsed.command_type.value == "write" else "low"),
        "suggested_action": "review" if parsed.is_destructive else "allow"
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


# ---------------------------------------------------------------------------
# E2E endpoints
# ---------------------------------------------------------------------------

# In-memory state for E2E sessions
e2e_sessions: Dict[str, str] = {}

# Shared L4 memory instance for E2E conversation history
from src.l4 import MemoryKnowledge
e2e_memory = MemoryKnowledge()


@app.post("/api/e2e/chat")
async def e2e_chat(req: E2EChatRequest):
    import uuid
    import time
    from src.l1.l1_user_interaction import UserInteraction
    from src.l2.l2_control_gateway import ControlGateway
    from src.l3.l3_orchestration import Orchestration
    from src.l5.l5_tools import ToolsCapabilities
    from src.core.models import StandardEvent, AgentAction

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
        "event": "message",
        "payload": {
            "user_id": req.user_id,
            "message": req.content,
            "session_id": session_id
        }
    }
    channel = req.channel if req.channel != "web" else "webhook"
    event = l1.receive_payload(raw_data, channel=channel)

    # L2: assemble context (use shared memory so history persists)
    l2 = ControlGateway(memory=e2e_memory)
    l3_input = l2.process_event(event)

    # L3: ReAct loop (use shared memory)
    l3 = Orchestration(memory=e2e_memory)
    context = l3_input.session_context
    context.user_permissions = []  # default empty for testing
    available_tools = l3_input.available_tools

    observation = None
    final_answer = None

    max_iterations = getattr(l3, "MAX_ITERATIONS", 5)
    for iteration in range(1, max_iterations + 1):
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
            # If L5 asks for confirmation, stop the loop gracefully
            if observation.status == "confirmation_required":
                tool_name = observation.metadata.get("tool", "该操作")
                final_answer = f"执行 {tool_name} 需要您的确认。是否继续？（回复\"是\"继续，\"否\"取消）"
                break
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

    # Persist conversation history to L4 (read existing, append new, then save back)
    history = e2e_memory.retrieve_history(context.session_id, limit=100)
    history.append({"role": "user", "content": req.content})
    history.append({"role": "assistant", "content": final_answer})
    e2e_memory.store_conversation(context.session_id, history)

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
    l1.receive_payload(
        {"event": "message", "payload": {"user_id": req.user_id, "message": "/new"}},
        channel="webhook"
    )
    if req.user_id in e2e_sessions:
        del e2e_sessions[req.user_id]
    return {"reset": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
