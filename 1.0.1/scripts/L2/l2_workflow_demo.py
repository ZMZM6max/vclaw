#!/usr/bin/env python3
"""
L2 Control Gateway Workflow Demo Script

Demonstrates the complete L2 (Control Gateway Layer) workflow:
    StandardEvent -> RateLimit -> SessionMgmt -> ContextAssembly
    -> ToolPreparation -> MemoryRetrieval -> L3Input

Input data is the user's Telegram StandardEvent (already normalized by L1).

Run with:
    python scripts/L2/l2_workflow_demo.py

Requires: pydantic (installed in the vclaw conda environment)
"""

import sys
import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Fix Windows terminal encoding issues
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def safe_print(text: str):
    """Print text safely, replacing characters the terminal cannot encode."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace problematic characters with '?'
        print(text.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))

# --------------------------------------------------------------------------- #
#  Bootstrap: add project root (1.0.1/) to PYTHONPATH
# --------------------------------------------------------------------------- #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from src.l2.l2_control_gateway import (
    ControlGateway,
    RateLimiter,
    MemoryAccessor,
    ToolPreparer,
    ContextAssembler,
    HistoryRetriever,
)
from src.core.models import StandardEvent, SessionContext, L3Input
from src.core.exceptions import RateLimitExceeded

# --------------------------------------------------------------------------- #
#  Logging configuration
# --------------------------------------------------------------------------- #
LOG_DIR = Path(PROJECT_ROOT) / "src" / "l2" / "tests" / "results"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"l2_demo_{TIMESTAMP}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)5s] %(name)-25s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("L2Demo")

# --------------------------------------------------------------------------- #
#  Pretty-print helpers
# --------------------------------------------------------------------------- #


def banner(title: str):
    """Print a section banner."""
    line = f"\n{'=' * 70}\n  {title}\n{'=' * 70}"
    print(line)
    logger.info(f"=== {title} ===")


def data_log(label: str, data):
    """Print a labeled block of JSON-serializable data."""
    print(f"\n>>> {label}")
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        print(text)
        return text
    except Exception as e:
        text = f"  (not JSON-serializable: {e})\n  {data!r}"
        print(text)
        return text


# =============================================================================
#  DEMO DATA: StandardEvent from L1 (Telegram)
# =============================================================================
INPUT_EVENT_DATA = {
    "channel": "telegram",
    "user_id": "8448390784",
    "content": "11",
    "timestamp": 1777280372.0,
    "metadata": {
        "chat_id": 8448390784,
        "message_id": 68,
        "first_name": "lzmzm",
        "username": None,
        "update_id": 616877254,
        "session_id": None,
        "is_new_session_request": False,
    },
}


# =============================================================================
#  MAIN DEMO
# =============================================================================


def demo_step_by_step():
    """
    Walk through every L2 component manually so the data log at each stage
    is explicit and easy to read.
    """
    banner("L2 WORKFLOW DEMO — CONTROL GATEWAY")
    logger.info("Starting L2 step-by-step demonstration")

    # =====================================================================
    #  STEP 0: Input StandardEvent (from L1)
    # =====================================================================
    banner("STEP 0: INPUT StandardEvent (from L1)")
    event = StandardEvent(**INPUT_EVENT_DATA)
    data_log("StandardEvent", event.model_dump())

    # =====================================================================
    #  STEP 1: RateLimiter — check request allowance
    # =====================================================================
    banner("STEP 1: RATE LIMITER")
    logger.info("Instantiating RateLimiter with default limits...")

    rate_limiter = RateLimiter()
    print(f"\n>>> Default Limits")
    print(f"    user   : {rate_limiter.limits['user']}")
    print(f"    ip     : {rate_limiter.limits['ip']}")
    print(f"    global : {rate_limiter.limits['global']}")

    allowed, reason = rate_limiter.is_allowed(
        user_id=event.user_id,
        ip=event.metadata.get("client_ip"),
    )
    print(f"\n>>> Rate Limit Check")
    print(f"    user_id : {event.user_id}")
    print(f"    allowed : {allowed}")
    print(f"    reason  : {reason}")

    # =====================================================================
    #  STEP 2: ControlGateway — main L2 entry point
    # =====================================================================
    banner("STEP 2: CONTROL GATEWAY INITIALISATION")
    logger.info("Instantiating ControlGateway...")

    gateway = ControlGateway()
    print(f"\n>>> ControlGateway Components")
    print(f"    rate_limiter   : {type(gateway.rate_limiter).__name__}")
    print(f"    memory         : {type(gateway.memory).__name__}")
    print(f"    tools          : {type(gateway.tools).__name__}")
    print(f"    l1_sender      : {gateway.l1_sender}")
    print(f"    session_max_age: {gateway.session_max_age}s")

    # =====================================================================
    #  STEP 3: process_event() — complete L2 workflow
    # =====================================================================
    banner("STEP 3: process_event() — COMPLETE L2 WORKFLOW")
    logger.info("Calling ControlGateway.process_event()...")

    start_time = time.time()
    try:
        l3_input: L3Input = gateway.process_event(event)
        elapsed = time.time() - start_time
        print(f"\n>>> process_event() completed in {elapsed:.4f}s")
    except RateLimitExceeded as exc:
        elapsed = time.time() - start_time
        print(f"\n>>> process_event() FAILED after {elapsed:.4f}s")
        print(f"    RateLimitExceeded: {exc}")
        logger.error(f"Rate limit exceeded: {exc}")
        return

    # =====================================================================
    #  STEP 4: Inspect L3Input result
    # =====================================================================
    banner("STEP 4: L3Input OUTPUT (L2 -> L3)")
    logger.info("Inspecting assembled L3Input...")

    # 4x) 完整 L3Input 总览
    print("\n>>> 4x) 完整 L3Input（L2 拼接后输出给 L3 的整体上下文）")
    data_log("L3Input", l3_input.model_dump())

    # 4a) SessionContext
    ctx: SessionContext = l3_input.session_context
    print("\n>>> 4a) SessionContext")
    data_log("SessionContext", ctx.model_dump())

    # 4b) Available Tools
    print("\n>>> 4b) Available Tools (filtered by permissions)")
    print(f"    tool count: {len(l3_input.available_tools)}")
    for idx, tool in enumerate(l3_input.available_tools, 1):
        tool_name = tool.get("name", "unknown")
        tool_desc = tool.get("description", "")
        safe_print(f"    [{idx}] {tool_name}: {tool_desc}")
    data_log("available_tools", l3_input.available_tools)

    # 4c) Relevant Memories
    print("\n>>> 4c) Relevant Memories (from L4)")
    print(f"    memory count: {len(l3_input.relevant_memories)}")
    for idx, mem in enumerate(l3_input.relevant_memories, 1):
        print(f"    [{idx}] {mem}")
    data_log("relevant_memories", l3_input.relevant_memories)

    # =====================================================================
    #  STEP 5: Session state inspection
    # =====================================================================
    banner("STEP 5: SESSION STATE")
    logger.info("Inspecting internal session store...")

    print(f"\n>>> Active sessions in ControlGateway")
    print(f"    total sessions: {len(gateway.sessions)}")
    for sid, sdata in gateway.sessions.items():
        print(f"    session_id : {sid}")
        print(f"    user_id    : {sdata.get('user_id')}")
        print(f"    created_at : {sdata.get('created_at')}")

    # =====================================================================
    #  STEP 6: Follow-up request (same user, same session)
    # =====================================================================
    banner("STEP 6: FOLLOW-UP REQUEST (session reuse)")
    logger.info("Sending a second event to verify session reuse...")

    follow_up_event = StandardEvent(
        channel="telegram",
        user_id="8448390784",
        content="再来一条消息",
        timestamp=1777280373.0,
        metadata={
            "chat_id": 8448390784,
            "message_id": 69,
            "first_name": "lzmzm",
            "username": None,
            "update_id": 616877255,
            "session_id": ctx.session_id,  # inject the session_id from step 4
            "is_new_session_request": False,
        },
    )

    l3_input_2 = gateway.process_event(follow_up_event)
    ctx_2 = l3_input_2.session_context

    print(f"\n>>> First  session_id : {ctx.session_id}")
    print(f">>> Second session_id : {ctx_2.session_id}")
    print(f">>> Session reused    : {ctx.session_id == ctx_2.session_id}")

    # =====================================================================
    #  STEP 7: New session command (/new)
    # =====================================================================
    banner("STEP 7: NEW SESSION COMMAND (/new)")
    logger.info("Sending /new to trigger session reset...")

    new_session_event = StandardEvent(
        channel="telegram",
        user_id="8448390784",
        content="/new",
        timestamp=1777280374.0,
        metadata={
            "chat_id": 8448390784,
            "message_id": 70,
            "first_name": "lzmzm",
            "username": None,
            "update_id": 616877256,
            "session_id": ctx.session_id,
            "is_new_session_request": True,  # <-- explicit new session
        },
    )

    l3_input_3 = gateway.process_event(new_session_event)
    ctx_3 = l3_input_3.session_context

    print(f"\n>>> Old session_id : {ctx.session_id}")
    print(f">>> New session_id : {ctx_3.session_id}")
    print(f">>> Session changed: {ctx.session_id != ctx_3.session_id}")

    # =====================================================================
    #  STEP 8: Response path (L2 -> L1)
    # =====================================================================
    banner("STEP 8: SEND RESPONSE (L2 -> L1)")
    logger.info("Demonstrating send_response()...")

    result = gateway.send_response(event, "这是L3返回的最终答案")
    print(f"\n>>> send_response() returned: {result}")

    banner("MAIN DEMO COMPLETE")
    logger.info(f"Log saved to: {LOG_FILE}")
    print(f"\n[Log file] {LOG_FILE}")


def demo_rate_limit_exceeded():
    """Demonstrate rate limit exhaustion."""
    banner("BONUS: RATE LIMIT EXHAUSTION")
    logger.info("Demonstrating rate limit exhaustion...")

    limiter = RateLimiter(limits={"user": (3, 60), "ip": (10, 60), "global": (100, 1)})
    user_id = "rate_test_user"

    for i in range(1, 6):
        allowed, reason = limiter.is_allowed(user_id)
        status = "ALLOWED" if allowed else f"BLOCKED ({reason})"
        print(f"    Request #{i}: {status}")


if __name__ == "__main__":
    demo_step_by_step()
    demo_rate_limit_exceeded()
