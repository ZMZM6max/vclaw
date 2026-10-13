# L1 Phase 5: Test Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 new test files and extend existing tests to cover Phase 2-4 implementation gaps in L1.

**Architecture:** Pure unit tests with mocks. No external dependencies. Tests verify stub behavior, routing logic, response formatting, adapter/validator boundaries, and L4 persistence hooks.

**Tech Stack:** pytest, unittest.mock (Mock, patch)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `1.0.1/src/l1/tests/test_error_handler_business.py` | Create | L3 business error routing and stub output validation |
| `1.0.1/src/l1/tests/test_error_handler_protocol.py` | Create | L1 internal error routing and retry boundary tests |
| `1.0.1/src/l1/tests/test_response_sender.py` | Create | `send_response` all paths and `_response_context_map` behavior |
| `1.0.1/src/l1/tests/test_adapter_edge_cases.py` | Create | Adapter/Validator/EventNormalizer boundary conditions |
| `1.0.1/src/l1/tests/test_l1_basic.py` | Modify | Append L4 persistence tests to `TestSessionManagement` |
| `1.0.1/src/l1/tests/README.md` | Modify | Register 4 new test files |
| `1.0.1/src/l1/docs/progress.md` | Modify | Mark Phase 5 as completed |

---

### Task 1: `test_error_handler_business.py`

**Files:**
- Create: `1.0.1/src/l1/tests/test_error_handler_business.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for ErrorHandler business error routing (L3 error flow-back).

Covers stub formatting framework until L3 ErrorTranslator output structure
is finalized.
"""
import pytest
from src.l1.l1_user_interaction import ErrorHandler


@pytest.fixture
def error_handler():
    return ErrorHandler()


class TestBusinessErrorRouting:
    def test_handle_business_error_telegram(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="telegram", metadata={"chat_id": 12345})
        assert isinstance(result, dict)
        assert result["chat_id"] == 12345
        assert result["text"] == "余额不足"

    def test_handle_business_error_websocket(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="websocket")
        assert isinstance(result, dict)
        assert result["type"] == "error"
        assert result["message"] == "余额不足"
        assert "timestamp" in result

    def test_handle_business_error_webhook(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="webhook")
        assert isinstance(result, tuple)
        assert result[0] == 500
        assert result[1] == {"error": "余额不足"}

    def test_handle_business_error_unknown_channel(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="slack")
        assert result == {"error": "余额不足"}

    def test_handle_business_error_empty_dict(self, error_handler):
        error = {}
        result = error_handler.handle_error(error, channel="telegram")
        assert result["text"] == "Unknown error"

    def test_handle_business_error_missing_message_key(self, error_handler):
        error = {"code": 403}
        result = error_handler.handle_error(error, channel="telegram")
        assert result["text"] == "Unknown error"
```

- [ ] **Step 2: Run tests**

```bash
conda activate vclaw
pytest 1.0.1/src/l1/tests/test_error_handler_business.py -v
```

Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/test_error_handler_business.py
git commit -m "test(l1): add business error routing tests for ErrorHandler"
```

---

### Task 2: `test_error_handler_protocol.py`

**Files:**
- Create: `1.0.1/src/l1/tests/test_error_handler_protocol.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for ErrorHandler protocol-level formatting and retry boundaries."""
import pytest
from unittest.mock import Mock, patch
from src.l1.l1_user_interaction import ErrorHandler


@pytest.fixture
def error_handler():
    return ErrorHandler()


class TestProtocolFormatting:
    def test_handle_l1_internal_error_telegram(self, error_handler):
        error = ValueError("连接超时")
        result = error_handler.handle_error(error, channel="telegram", metadata={"chat_id": 123})
        assert isinstance(result, dict)
        assert result["chat_id"] == 123
        assert "连接超时" in result["text"]

    def test_handle_unsupported_error_type(self, error_handler):
        error = "raw string"
        result = error_handler.handle_error(error, channel="telegram")
        assert isinstance(result, dict)
        assert result["text"] == "raw string"


class TestRetryBoundaries:
    def test_retry_zero_max_retries(self, error_handler):
        operation = Mock(side_effect=ConnectionError("fail"))
        with patch('src.l1.l1_user_interaction.time.sleep'):
            with pytest.raises(ConnectionError):
                error_handler.execute_with_retry(operation, max_retries=0, retryable_exceptions=(ConnectionError,))
        assert operation.call_count == 1

    def test_retry_custom_delay(self, error_handler):
        operation = Mock(side_effect=[ConnectionError("fail"), "success"])
        with patch('src.l1.l1_user_interaction.time.sleep') as mock_sleep:
            error_handler.execute_with_retry(
                operation,
                max_retries=1,
                initial_delay=0.01,
                retryable_exceptions=(ConnectionError,)
            )
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_once_with(0.01)

    def test_retry_non_retryable_exception(self, error_handler):
        operation = Mock(side_effect=RuntimeError("fail"))
        with patch('src.l1.l1_user_interaction.time.sleep'):
            with pytest.raises(RuntimeError):
                error_handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))
        assert operation.call_count == 1
```

- [ ] **Step 2: Run tests**

```bash
pytest 1.0.1/src/l1/tests/test_error_handler_protocol.py -v
```

Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/test_error_handler_protocol.py
git commit -m "test(l1): add protocol formatting and retry boundary tests"
```

---

### Task 3: `test_response_sender.py`

**Files:**
- Create: `1.0.1/src/l1/tests/test_response_sender.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for UserInteraction.send_response() and response context map."""
import pytest
from unittest.mock import patch
from src.l1.l1_user_interaction import UserInteraction
from src.core.exceptions import UnsupportedChannelError


@pytest.fixture
def ui():
    return UserInteraction()


class TestSendResponse:
    def test_send_response_auto_detect_telegram(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {
                "from": {"id": "u1"},
                "chat": {"id": 999},
                "date": 1234567890,
                "text": "Hello"
            }
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, dict)
        assert result["chat_id"] == 999
        assert result["text"] == "Hi back"

    def test_send_response_auto_detect_websocket(self, ui):
        raw_data = {"type": "msg", "user_id": "u1", "content": "Hello", "connection_id": "conn-1"}
        ui.receive_payload(raw_data, channel="websocket")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, dict)
        assert result["type"] == "response"
        assert result["message"] == "Hi back"
        assert result["connection_id"] == "conn-1"

    def test_send_response_auto_detect_webhook(self, ui):
        raw_data = {"user_id": "u1", "content": "Hello", "headers": {}}
        ui.receive_payload(raw_data, channel="webhook")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, tuple)
        assert result[0] == 200
        assert result[1]["response"] == "Hi back"

    def test_send_response_explicit_channel_override(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 999}, "date": 1234567890, "text": "Hello"}
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back", channel="websocket", metadata={"connection_id": "c2"})
        assert result["type"] == "response"
        assert result["connection_id"] == "c2"

    def test_send_response_explicit_metadata_override(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 111}, "date": 1234567890, "text": "Hello"}
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back", metadata={"chat_id": 999})
        assert result["chat_id"] == 999

    def test_send_response_unknown_channel_raises(self, ui):
        with pytest.raises(UnsupportedChannelError):
            ui.send_response("u1", "Hi", channel="slack")

    def test_send_response_no_context_fallback(self, ui):
        with pytest.raises(UnsupportedChannelError):
            ui.send_response("u1", "Hi")

    def test_response_context_overwritten_by_new_request(self, ui):
        telegram_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 111}, "date": 1234567890, "text": "T"}
        }
        ws_data = {"type": "msg", "user_id": "u1", "content": "W", "connection_id": "conn-2"}
        ui.receive_payload(telegram_data, channel="telegram")
        ui.receive_payload(ws_data, channel="websocket")
        result = ui.send_response("u1", "Hi")
        assert result["type"] == "response"
        assert result["connection_id"] == "conn-2"
```

- [ ] **Step 2: Run tests**

```bash
pytest 1.0.1/src/l1/tests/test_response_sender.py -v
```

Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/test_response_sender.py
git commit -m "test(l1): add send_response path and context map tests"
```

---

### Task 4: `test_adapter_edge_cases.py`

**Files:**
- Create: `1.0.1/src/l1/tests/test_adapter_edge_cases.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for adapter and validator edge cases."""
import pytest
from src.l1.l1_user_interaction import (
    TelegramAdapter, WebSocketAdapter, HttpWebhookAdapter,
    DataValidator, EventNormalizer
)
from src.core.exceptions import ParseError, ValidationError, UnsupportedChannelError


# =============================================================================
# Adapter Edge Cases
# =============================================================================

class TestTelegramAdapterEdgeCases:
    def test_empty_data(self):
        adapter = TelegramAdapter()
        assert adapter.can_handle({}) is False

    def test_missing_message(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"update_id": 1})

    def test_missing_user_id(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"message": {"text": "hi"}})

    def test_missing_text(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"message": {"from": {"id": 1}}})


class TestWebSocketAdapterEdgeCases:
    def test_missing_user_id(self):
        adapter = WebSocketAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"type": "msg", "content": "hi"})

    def test_missing_content(self):
        adapter = WebSocketAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"type": "msg", "user_id": "u1"})


class TestWebhookAdapterEdgeCases:
    def test_no_matching_format(self):
        adapter = HttpWebhookAdapter()
        assert adapter.can_handle({"foo": "bar"}) is False

    def test_event_payload_missing_user_id(self):
        adapter = HttpWebhookAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"event": "x", "payload": {"message": "hi"}})

    def test_simple_format_missing_user_id(self):
        adapter = HttpWebhookAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"content": "hi", "headers": {}})


# =============================================================================
# DataValidator Edge Cases
# =============================================================================

class TestDataValidatorEdgeCases:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    @pytest.mark.parametrize("content", [
        "<script>alert(1)</script>",
        "javascript:void(0)",
        "onclick=evil()",
    ])
    def test_xss_patterns(self, validator, content):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": content})

    def test_user_id_too_long(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "x" * 257, "content": "hi"})

    def test_content_too_long(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "x" * 10001})

    def test_timestamp_negative(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": -1})

    def test_timestamp_too_large(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": 4102444801})

    def test_timestamp_non_numeric(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": "bad"})

    def test_invalid_channel(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "email", "user_id": "u1", "content": "hi"})


# =============================================================================
# EventNormalizer Edge Cases
# =============================================================================

class TestEventNormalizerEdgeCases:
    def test_no_adapter_can_handle(self):
        normalizer = EventNormalizer()
        with pytest.raises(UnsupportedChannelError):
            normalizer.normalize({"unknown": "format"})

    def test_explicit_channel_not_found(self):
        normalizer = EventNormalizer()
        with pytest.raises(UnsupportedChannelError):
            normalizer.normalize({}, channel="email")
```

- [ ] **Step 2: Run tests**

```bash
pytest 1.0.1/src/l1/tests/test_adapter_edge_cases.py -v
```

Expected: all passed (19+ tests)

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/test_adapter_edge_cases.py
git commit -m "test(l1): add adapter and validator edge case tests"
```

---

### Task 5: Extend `test_l1_basic.py`

**Files:**
- Modify: `1.0.1/src/l1/tests/test_l1_basic.py`

- [ ] **Step 1: Append new tests to `TestSessionManagement`**

Insert the following methods into the existing `TestSessionManagement` class (after the last existing method):

```python
    def test_update_session_mapping_dual_write(self):
        """Phase 3: update_session_mapping writes to memory and L4."""
        from unittest.mock import Mock
        memory = Mock(spec=MemoryInterface)
        interaction = UserInteraction(memory=memory)
        interaction.update_session_mapping("user_123", "session-abc")
        assert interaction.get_user_session("user_123") == "session-abc"
        memory.save_user_preference.assert_called_once_with("user_123", "active_session_id", "session-abc")

    def test_new_command_clears_memory_and_l4(self):
        """Phase 3: /new clears both in-memory and L4 mapping."""
        from unittest.mock import Mock
        memory = Mock(spec=MemoryInterface)
        interaction = UserInteraction(memory=memory)
        interaction.update_session_mapping("user_123", "session-abc")
        raw_data = {
            "update_id": 124,
            "message": {
                "message_id": 2,
                "from": {"id": "user_123"},
                "chat": {"id": "user_123"},
                "date": 1234567890,
                "text": "/new"
            }
        }
        event = interaction.receive_payload(raw_data, channel="telegram")
        assert event.metadata.get("session_id") is None
        assert interaction.get_user_session("user_123") is None
        memory.save_user_preference.assert_called_with("user_123", "active_session_id", None)

    def test_l4_restore_on_cache_miss(self):
        """Phase 3: L4 restores session when memory cache misses."""
        from unittest.mock import Mock
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = "sess-123"
        interaction = UserInteraction(memory=memory)
        session_id = interaction.get_user_session("user_123")
        assert session_id == "sess-123"
        assert interaction._user_session_map["user_123"] == "sess-123"

    def test_l4_returns_none_no_mapping(self):
        """Phase 3: L4 returns None when no persistent mapping exists."""
        from unittest.mock import Mock
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = None
        interaction = UserInteraction(memory=memory)
        assert interaction.get_user_session("user_123") is None

    def test_no_memory_fallback_to_in_memory(self):
        """Phase 3: Without memory, behavior is pure in-memory (backward compatible)."""
        interaction = UserInteraction(memory=None)
        interaction.update_session_mapping("user_123", "session-abc")
        assert interaction.get_user_session("user_123") == "session-abc"

    def test_get_session_id_prefers_memory_over_l4(self):
        """Phase 3: Memory cache takes priority over L4 lookup."""
        from unittest.mock import Mock
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = "from-l4"
        interaction = UserInteraction(memory=memory)
        interaction._user_session_map["user_123"] = "from-memory"
        session_id = interaction.get_user_session("user_123")
        assert session_id == "from-memory"
        memory.load_user_preference.assert_not_called()
```

Note: Add `from src.core.interfaces import MemoryInterface` to the imports at the top of `test_l1_basic.py` if not already present.

- [ ] **Step 2: Run tests**

```bash
pytest 1.0.1/src/l1/tests/test_l1_basic.py::TestSessionManagement -v
```

Expected: 11 passed (5 existing + 6 new)

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/test_l1_basic.py
git commit -m "test(l1): add L4 persistence tests to TestSessionManagement"
```

---

### Task 6: Documentation Sync

**Files:**
- Modify: `1.0.1/src/l1/tests/README.md`
- Modify: `1.0.1/src/l1/docs/progress.md`

- [ ] **Step 1: Update `README.md`**

Add the 4 new test files to the unit test table:

```markdown
| `test_error_handler_business.py` | ErrorHandler business error routing | 无 | 稳定 |
| `test_error_handler_protocol.py` | ErrorHandler protocol formatting + retry boundaries | 无 | 稳定 |
| `test_response_sender.py` | send_response path and context map | 无 | 稳定 |
| `test_adapter_edge_cases.py` | Adapter/Validator/EventNormalizer edge cases | 无 | 稳定 |
```

- [ ] **Step 2: Update `progress.md`**

Update the Phase 5 status:

```markdown
| Phase 5 | 测试增强与目录规范化 | **已完成** | **100%** |
```

And add a milestone entry:

```markdown
### 2026-04-24: Phase 5 — 测试增强完成
**做了什么：**
- [x] 新增 `test_error_handler_business.py` — L3 业务错误路由测试
- [x] 新增 `test_error_handler_protocol.py` — 协议格式化 + 重试边界测试
- [x] 新增 `test_response_sender.py` — send_response 全路径测试
- [x] 新增 `test_adapter_edge_cases.py` — 适配器/验证器边界测试
- [x] 补充 `test_l1_basic.py::TestSessionManagement` — L4 持久化测试
- [x] 更新 `src/l1/tests/README.md`
- [x] 全量回归测试通过

**产出：**
- L1 层 Phase 2-4 实现缺口已完全覆盖
- 新增 ~40 个单元测试，全部通过
```

- [ ] **Step 3: Commit**

```bash
git add 1.0.1/src/l1/tests/README.md 1.0.1/src/l1/docs/progress.md
git commit -m "docs(l1): register Phase 5 tests and update progress"
```

---

### Task 7: Final Regression Run

- [ ] **Step 1: Run full L1 test suite**

```bash
pytest 1.0.1/src/l1/tests/test_*.py -v --ignore=1.0.1/src/l1/tests/test_telegram_*.py --ignore=1.0.1/src/l1/tests/test_adapters_manual.py
```

Expected: All existing + new tests pass (150+)

- [ ] **Step 2: Show summary**

```bash
pytest 1.0.1/src/l1/tests/test_*.py --ignore=1.0.1/src/l1/tests/test_telegram_*.py --ignore=1.0.1/src/l1/tests/test_adapters_manual.py -q
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - [x] `test_error_handler_business.py` covers all 6 business error stub cases
   - [x] `test_error_handler_protocol.py` covers L1 internal error routing + 3 retry boundaries
   - [x] `test_response_sender.py` covers all 8 response path scenarios
   - [x] `test_adapter_edge_cases.py` covers 9 adapter + 9 validator + 2 normalizer cases
   - [x] `test_l1_basic.py` additions cover 6 L4 persistence scenarios

2. **Placeholder scan:** No TBD/TODO/fill-in-later steps. All test code is complete.

3. **Type consistency:** All method signatures match `l1_user_interaction.py` current implementation.
