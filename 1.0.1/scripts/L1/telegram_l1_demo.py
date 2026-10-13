#!/usr/bin/env python3
"""
Telegram L1 Workflow Demo Script

Demonstrates the complete L1 (User Interaction Layer) workflow for Telegram input,
showing data transformation and detailed logs at every component stage.

Run with:
    python scripts/telegram_l1_demo.py

Requires: pydantic (installed in the vclaw conda environment)
"""

import sys
import os
import json
import logging
import time

# --------------------------------------------------------------------------- #
#  Bootstrap: add project root (1.0.1/) to PYTHONPATH so that imports like
#  `from src.core.models import ...` resolve correctly.
# --------------------------------------------------------------------------- #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.l1.l1_user_interaction import (
    TelegramAdapter,
    WebSocketAdapter,
    HttpWebhookAdapter,
    DataValidator,
    EventNormalizer,
    ErrorHandler,
    UserInteraction,
)
from src.core.models import StandardEvent
from src.core.exceptions import ValidationError, ParseError, UnsupportedChannelError

# --------------------------------------------------------------------------- #
#  Logging configuration: DEBUG level so every component's internal logs
#  are visible on stdout.
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)5s] %(name)-25s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("L1Demo")

# --------------------------------------------------------------------------- #
#  Pretty-print helpers
# --------------------------------------------------------------------------- #

def banner(title: str):
    """Print a section banner."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def data_log(label: str, data):
    """Print a labeled block of JSON-serializable data."""
    print(f"\n>>> {label}")
    try:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"  (not JSON-serializable: {e})")
        print(f"  {data!r}")


# =============================================================================
#  DEMO DATA: Simulated Telegram Bot API update payload
# =============================================================================
RAW_TELEGRAM_PAYLOAD = {
    "update_id": 616877254,
    "message": {
        "message_id": 68,
        "from": {
            "id": 8448390784,
            "is_bot": False,
            "first_name": "lzmzm",
            "last_name": "lzmzm",
            "language_code": "zh-hans",
        },
        "chat": {
            "id": 8448390784,
            "first_name": "lzmzm",
            "last_name": "lzmzm",
            "type": "private",
        },
        "date": 1777280372,
        "text": "11",
    },
}


# =============================================================================
#  MAIN DEMO
# =============================================================================

def demo_step_by_step():
    """
    Walk through every L1 component manually so the data log at each stage
    is explicit and easy to read.
    """
    banner("L1 WORKFLOW DEMO — TELEGRAM INPUT")
    logger.info("Starting L1 step-by-step demonstration")

    # =====================================================================
    #  STEP 0: Raw external input (as if received from Telegram Bot API)
    # =====================================================================
    banner("STEP 0: RAW TELEGRAM INPUT (from Bot API)")
    data_log("Raw Payload", RAW_TELEGRAM_PAYLOAD)

    # =====================================================================
    #  STEP 1: ProtocolAdapters — channel detection & parsing
    # =====================================================================
    banner("STEP 1: PROTOCOL ADAPTERS")
    logger.info("Instantiating all three protocol adapters...")

    telegram_adapter = TelegramAdapter()
    websocket_adapter = WebSocketAdapter()
    webhook_adapter = HttpWebhookAdapter()

    print("\n>>> Adapter Detection Results")
    print(f"    TelegramAdapter.can_handle()   = {telegram_adapter.can_handle(RAW_TELEGRAM_PAYLOAD)}")
    print(f"    WebSocketAdapter.can_handle()  = {websocket_adapter.can_handle(RAW_TELEGRAM_PAYLOAD)}")
    print(f"    HttpWebhookAdapter.can_handle()= {webhook_adapter.can_handle(RAW_TELEGRAM_PAYLOAD)}")

    logger.info("TelegramAdapter matched — calling parse()...")
    parsed_event: StandardEvent = telegram_adapter.parse(RAW_TELEGRAM_PAYLOAD)
    data_log("Parsed StandardEvent (from TelegramAdapter)", parsed_event.model_dump())

    # =====================================================================
    #  STEP 2: EventNormalizer — auto-detect channel & delegate to adapter
    # =====================================================================
    banner("STEP 2: EVENT NORMALIZER")
    logger.info("EventNormalizer iterating adapters to auto-detect channel...")

    normalizer = EventNormalizer()
    normalized_event = normalizer.normalize(RAW_TELEGRAM_PAYLOAD)
    data_log(
        "Normalized Event (auto-detected channel='telegram')",
        normalized_event.model_dump(),
    )

    # =====================================================================
    #  STEP 3: DataValidator — security & schema validation
    # =====================================================================
    banner("STEP 3: DATA VALIDATOR")
    logger.info("Running validation rules on normalized event...")

    validator = DataValidator()
    validation_input = normalized_event.model_dump()
    print("\n>>> Validation Rules")
    print(f"    Required fields : {DataValidator.REQUIRED_FIELDS}")
    print(f"    Valid channels  : {DataValidator.VALID_CHANNELS}")
    print(f"    Max user_id len : {DataValidator.MAX_USER_ID_LENGTH}")
    print(f"    Max content len : {DataValidator.MAX_CONTENT_LENGTH}")
    print(f"    Injection checks: {len(DataValidator.INJECTION_PATTERNS)} patterns")

    is_valid = validator.validate(validation_input)
    print(f"\n>>> Validation Result: {is_valid}")

    # =====================================================================
    #  STEP 4: ErrorHandler — retry mechanism with exponential backoff
    # =====================================================================
    banner("STEP 4: ERROR HANDLER — RETRY MECHANISM")
    logger.info("Demonstrating execute_with_retry() on a flaky operation...")

    error_handler = ErrorHandler(max_retries=3, initial_delay=0.1)

    # A closure that fails twice, then succeeds (to show retry logs)
    attempt_counter = {"count": 0}

    def flaky_operation():
        attempt_counter["count"] += 1
        print(f"    [flaky_operation] Attempt #{attempt_counter['count']} executing...")
        if attempt_counter["count"] < 3:
            raise ParseError(f"Simulated transient failure (#{attempt_counter['count']})")
        return {"status": "ok", "attempts": attempt_counter["count"]}

    retry_result = error_handler.execute_with_retry(
        flaky_operation,
        retryable_exceptions=(ParseError, ConnectionError),
    )
    data_log("Result after retries", retry_result)

    # =====================================================================
    #  STEP 5: Session Management — user_id -> session_id mapping
    # =====================================================================
    banner("STEP 5: SESSION MANAGEMENT")
    logger.info("Demonstrating _get_session_id() behaviour...")

    l1 = UserInteraction()

    # 5a) First-time user — no mapping exists
    session_id_1, is_new_1 = l1._get_session_id("8448390784", "11")
    print("\n>>> 5a) First request (new user, no mapping)")
    print(f"    session_id={session_id_1}, is_new_session_request={is_new_1}")

    # Simulate L2 creating a session and L1 persisting the mapping
    fake_session_id = "sess-a1b2-c3d4-e5f6-7890"
    l1.update_session_mapping("8448390784", fake_session_id)
    print(f"\n>>> Stored mapping: user '8448390784' -> session '{fake_session_id}'")

    # 5b) Follow-up request — mapping exists
    session_id_2, is_new_2 = l1._get_session_id("8448390784", "再来一个问题")
    print("\n>>> 5b) Follow-up request (existing user)")
    print(f"    session_id={session_id_2}, is_new_session_request={is_new_2}")

    # 5c) Explicit new-session command — mapping cleared
    session_id_3, is_new_3 = l1._get_session_id("8448390784", "/new")
    print("\n>>> 5c) Request with '/new' command")
    print(f"    session_id={session_id_3}, is_new_session_request={is_new_3}")

    # =====================================================================
    #  STEP 6: Full receive_payload() — L1 entry point
    # =====================================================================
    banner("STEP 6: FULL receive_payload() — L1 ENTRY POINT")
    logger.info("Calling UserInteraction.receive_payload() with raw Telegram data...")

    final_event = l1.receive_payload(RAW_TELEGRAM_PAYLOAD)
    data_log("StandardEvent produced by receive_payload()", final_event.model_dump())

    # =====================================================================
    #  STEP 7: Response path — send_response() formats output per channel
    # =====================================================================
    banner("STEP 7: SEND RESPONSE — RETURN PATH TO TELEGRAM")
    logger.info("L2/L3 produced an answer; L1 formats it for the original channel...")

    telegram_response = l1.send_response(
        user_id="8448390784",
        content="11",
    )
    data_log("Telegram Bot API sendMessage payload", telegram_response)

    banner("MAIN DEMO COMPLETE")


def demo_error_scenarios():
    """Show validation failures and error formatting."""
    banner("BONUS: ERROR HANDLING SCENARIOS")

    # -----------------------------------------------------------------
    #  A) Injection detection
    # -----------------------------------------------------------------
    print("\n>>> A) Injection Detection")
    validator = DataValidator()
    malicious_event = {
        "channel": "telegram",
        "user_id": "123",
        "content": "<script>alert('xss')</script>",
        "timestamp": 1714204800.0,
    }
    data_log("Malicious input", malicious_event)
    try:
        validator.validate(malicious_event)
    except ValidationError as exc:
        print(f"    Caught ValidationError: {exc}")

    # -----------------------------------------------------------------
    #  B) Unsupported channel / parse failure
    # -----------------------------------------------------------------
    print("\n>>> B) Unsupported Channel / Parse Failure")
    normalizer = EventNormalizer()

    # Payload that no adapter recognises
    truly_bad_data = {"foo": "bar", "unknown": True}
    data_log("Truly unrecognisable payload", truly_bad_data)
    try:
        normalizer.normalize(truly_bad_data)
    except UnsupportedChannelError as exc:
        print(f"    Caught UnsupportedChannelError: {exc}")

    # Payload caught by an adapter but missing required fields
    ws_malformed = {"type": "unknown", "user_id": "123"}
    data_log("Malformed WebSocket payload", ws_malformed)
    try:
        normalizer.normalize(ws_malformed)
    except ParseError as exc:
        print(f"    Caught ParseError: {exc}")

    # -----------------------------------------------------------------
    #  C) Retry exhaustion
    # -----------------------------------------------------------------
    print("\n>>> C) Retry Exhaustion")
    error_handler = ErrorHandler(max_retries=2, initial_delay=0.05)

    def always_fails():
        raise ParseError("Persistent parse error")

    try:
        error_handler.execute_with_retry(
            always_fails,
            retryable_exceptions=(ParseError,),
        )
    except ParseError as exc:
        print(f"    Final exception after all retries: {exc}")

    # -----------------------------------------------------------------
    #  D) L3 business-error flow-back formatting
    # -----------------------------------------------------------------
    print("\n>>> D) L3 Business-Error Flow-back Formatting")
    l3_error = {
        "error_code": "TOOL_NOT_FOUND",
        "error_message": "工具 'calculator_v2' 不存在，请检查名称后重试。",
    }
    data_log("L3 ErrorTranslator output", l3_error)

    error_handler = ErrorHandler()
    for ch in ("telegram", "websocket", "webhook"):
        formatted = error_handler.handle_error(
            l3_error,
            channel=ch,
            metadata={"chat_id": 987654321, "connection_id": "ws-001"},
        )
        data_log(f"Formatted for channel='{ch}'", formatted)


if __name__ == "__main__":
    demo_step_by_step()
    demo_error_scenarios()
