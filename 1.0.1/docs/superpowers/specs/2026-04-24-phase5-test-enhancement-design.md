# L1 Phase 5: Test Enhancement Design

## Overview

Complete the test coverage gaps identified in Phase 2-4 implementations. Phase 2 extended `ErrorHandler` with business error routing stubs, Phase 3 added L4 persistence to session management, and Phase 4 restored `send_response`. These features lack dedicated test coverage. This design covers the 4 new test files specified in the PRD plus targeted additions to existing tests for Phase 3/4 gaps.

## Scope

| Category | Files | Description |
|----------|-------|-------------|
| PRD-mandated new files | 4 | `test_error_handler_business.py`, `test_error_handler_protocol.py`, `test_response_sender.py`, `test_adapter_edge_cases.py` |
| Phase 3/4 gap fixes | 1 (append) | Add L4 persistence tests to `test_l1_basic.py::TestSessionManagement` |

**Exclusions:**
- Business error formatting logic inside `format_for_*` methods (blocked pending L3 `ErrorTranslator` output structure)
- Real-environment tests requiring Telegram Bot Token / network

## Test Strategy

- **Pure unit tests**: Mock all external dependencies (`time.sleep`, `time.time`, `MemoryInterface`)
- **No regression**: All 150+ existing tests must continue to pass
- **Target coverage**: >= 90% for new test files
- **Documentation sync**: Update `src/l1/tests/README.md` for each new file

---

## File 1: `test_error_handler_business.py`

Tests `ErrorHandler.handle_error()` routing and stub output for L3 business errors (dict type).

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_handle_business_error_telegram` | `error={"error_message": "余额不足"}`, `channel="telegram"` | Returns dict with `chat_id` and `text="余额不足"` |
| `test_handle_business_error_websocket` | Same error, `channel="websocket"` | Returns dict with `type="error"`, `message="余额不足"`, `timestamp` |
| `test_handle_business_error_webhook` | Same error, `channel="webhook"` | Returns `(500, {"error": "余额不足"})` |
| `test_handle_business_error_unknown_channel` | `channel="slack"` | Returns `{"error": "余额不足"}` (fallback) |
| `test_handle_business_error_empty_dict` | `error={}` | `error_message` falls back to `"Unknown error"` |
| `test_handle_business_error_missing_message_key` | `error={"code": 403}` | Falls back to default text |

**Mocking**: None required. Pure function tests.

---

## File 2: `test_error_handler_protocol.py`

Tests protocol-level formatting for L1 internal errors and retry boundary conditions.

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_handle_l1_internal_error_telegram` | `error=ValueError("连接超时")`, `channel="telegram"` | Returns dict, text contains exception message |
| `test_handle_unsupported_error_type` | `error="raw string"` | Falls back to `str(error)`, routes normally |
| `test_retry_zero_max_retries` | `execute_with_retry(..., max_retries=0)` | Executes exactly once, raises on failure |
| `test_retry_custom_delay` | `initial_delay=0.01` | Retry interval approximately 0.01s, doubles exponentially |
| `test_retry_non_retryable_exception` | Exception not in `retryable_exceptions` | Raises immediately, no retries |

**Mocking**: Mock `time.sleep` to speed up retry tests.

---

## File 3: `test_response_sender.py`

Tests `UserInteraction.send_response()` all paths and `_response_context_map` behavior.

| Test Case | Scenario | Expected |
|-----------|----------|----------|
| `test_send_response_auto_detect_telegram` | `receive_payload` Telegram message, then `send_response` same user_id | Returns dict with `chat_id` and `text` |
| `test_send_response_auto_detect_websocket` | `receive_payload` WebSocket message, then `send_response` | Returns dict with `connection_id` and `type="response"` |
| `test_send_response_auto_detect_webhook` | `receive_payload` Webhook message, then `send_response` | Returns `(200, {...})` |
| `test_send_response_explicit_channel_override` | Context map says Telegram, explicit `channel="websocket"` | Returns WebSocket format, ignores context map |
| `test_send_response_explicit_metadata_override` | Explicit `metadata={"chat_id": 999}` | Returns dict using 999 instead of context map value |
| `test_send_response_unknown_channel_raises` | No context + explicit `channel="slack"` | Raises `UnsupportedChannelError` |
| `test_send_response_no_context_fallback_unknown` | Never called `receive_payload`, directly `send_response` | `channel` falls back to `"unknown"`, then raises |
| `test_response_context_overwritten_by_new_request` | Same user_id sends Telegram then WebSocket, `send_response` without channel | Returns WebSocket format (verifies overwrite behavior) |

**Mocking**: Mock `time.time()` for stable timestamp assertions.

---

## File 4: `test_adapter_edge_cases.py`

Tests adapter and DataValidator boundary conditions.

### Adapter Boundaries

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_telegram_empty_data` | `{}` | `can_handle` -> False |
| `test_telegram_missing_message` | `{"update_id": 1}` | `parse` raises `ParseError` |
| `test_telegram_missing_user_id` | `{"message": {"text": "hi"}}` | `parse` raises `ParseError` |
| `test_telegram_missing_text` | `{"message": {"from": {"id": 1}}}` | `parse` raises `ParseError` |
| `test_websocket_missing_user_id` | `{"type": "msg", "content": "hi"}` | `parse` raises `ParseError` |
| `test_websocket_missing_content` | `{"type": "msg", "user_id": "u1"}` | `parse` raises `ParseError` |
| `test_webhook_no_matching_format` | `{"foo": "bar"}` | `can_handle` -> False |
| `test_webhook_event_payload_missing_user_id` | `{"event": "x", "payload": {"message": "hi"}}` | `parse` raises `ParseError` |
| `test_webhook_simple_format_missing_user_id` | `{"content": "hi", "headers": {}}` | `parse` raises `ParseError` |

### DataValidator Boundaries

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_xss_script_tag` | `content="<script>alert(1)</script>"` | Raises `ValidationError` |
| `test_xss_javascript_protocol` | `content="javascript:void(0)"` | Raises `ValidationError` |
| `test_xss_event_handler` | `content="onclick=evil()"` | Raises `ValidationError` |
| `test_user_id_too_long` | `user_id="x"*257` | Raises `ValidationError` |
| `test_content_too_long` | `content="x"*10001` | Raises `ValidationError` |
| `test_timestamp_negative` | `timestamp=-1` | Raises `ValidationError` |
| `test_timestamp_too_large` | `timestamp=4102444801` | Raises `ValidationError` |
| `test_timestamp_non_numeric` | `timestamp="not_a_number"` | Raises `ValidationError` |
| `test_invalid_channel` | `channel="email"` | Raises `ValidationError` |

### EventNormalizer Boundaries

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_no_adapter_can_handle` | `{"unknown": "format"}` | Raises `UnsupportedChannelError` |
| `test_explicit_channel_not_found` | `raw_data={}`, `channel="email"` | Raises `UnsupportedChannelError` |

**Mocking**: None required.

---

## File 5: `test_l1_basic.py` Additions (TestSessionManagement)

Extends existing `TestSessionManagement` class with L4 persistence coverage.

| Test Case | Scenario | Expected |
|-----------|----------|----------|
| `test_update_session_mapping_dual_write` | Construct `UserInteraction` with `memory`, call `update_session_mapping` | `memory.save_user_preference` called; memory and L4 values match |
| `test_new_command_clears_memory_and_l4` | `update_session_mapping` then send `/new` | Memory dict has no entry for user; `memory.save_user_preference(..., None)` called |
| `test_l4_restore_on_cache_miss` | Construct UI with `memory`, `memory.load_user_preference` returns `"sess-123"`, call `get_user_session` | Returns `"sess-123"`; memory dict backfilled |
| `test_l4_returns_none_no_mapping` | `memory.load_user_preference` returns `None` | `get_user_session` returns `None` |
| `test_no_memory_fallback_to_in_memory` | Construct `memory=None` UI, complete session flow | Pure memory behavior, no exception, consistent with Phase 1 |
| `test_get_session_id_prefers_memory_over_l4` | Memory has `"A"`, L4 has `"B"`, call `get_user_session` | Returns `"A"` (memory priority) |

**Mocking**: Mock `MemoryInterface` (pure interface mock, no real L4 dependency). Verify call counts and arguments.

---

## Documentation Updates

- `src/l1/tests/README.md`: Register all 4 new test files in the unit test table
- `src/l1/docs/progress.md`: Mark Phase 5 as completed upon implementation

## Acceptance Criteria

- [ ] All 4 new test files created and passing
- [ ] `test_l1_basic.py` additions passing
- [ ] All 150+ existing tests continue to pass (no regression)
- [ ] New test files coverage >= 90%
- [ ] `src/l1/tests/README.md` updated with new file entries
- [ ] `src/l1/docs/progress.md` updated

## Dependencies

- `src/l1/l1_user_interaction.py` (current uncommitted changes with Phase 2/3/4 implementations)
- `pytest` (already in use)
- No new pip dependencies required
