"""Tests for the VClaw Web Test Console server."""
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
    data = response.json()
    assert data["status"] == "ok"


def test_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm_available" in data
    assert "docker_available" in data
    assert "tools" in data


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


def test_l1_test_validator():
    payload = {
        "event_dict": {
            "channel": "webhook",
            "user_id": "u1",
            "content": "hello"
        }
    }
    response = client.post("/api/l1/test_validator", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_l2_test_rate_limit():
    payload = {"user_id": "u1", "ip": "127.0.0.1"}
    response = client.post("/api/l2/test_rate_limit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is True


def test_l2_test_session():
    payload = {"user_id": "u1", "content": "hello"}
    response = client.post("/api/l2/test_session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["user_id"] == "u1"


def test_l4_test_memory():
    payload = {
        "session_id": "test-session-001",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
    }
    response = client.post("/api/l4/test_memory", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["stored"] is True
    assert data["retrieved_count"] >= 0


def test_l4_test_search():
    payload = {"query": "AI agent system", "top_k": 3}
    response = client.post("/api/l4/test_search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_l5_test_tool():
    payload = {
        "action": "calculator",
        "params": {"expression": "1+1"},
        "user_permissions": []
    }
    response = client.post("/api/l5/test_tool", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "2" in data["result"]


def test_l5_test_bash():
    payload = {"command": "ls -la"}
    response = client.post("/api/l5/test_bash", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["command"] == "ls -la"
    assert "command_type" in data
    assert "risk_level" in data


def test_l6_test_runtime():
    payload = {"language": "python", "code": "print('ok')"}
    response = client.post("/api/l6/test_runtime", json=payload)
    # Docker may not be available in all test environments
    if response.status_code == 200:
        data = response.json()
        assert "stdout" in data
    else:
        # Accept sandbox-related errors when Docker is unavailable
        assert response.status_code in (400, 500)
        detail = response.json().get("detail", "")
        assert any(
            keyword in detail.lower()
            for keyword in ["docker", "sandbox", "runtime", "execution"]
        )


def test_e2e_chat_structural():
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
