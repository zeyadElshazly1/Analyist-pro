"""Structured errors from POST /chat/query when the LLM path is unavailable."""

from app.services.ai_chat.constants import AI_CHAT_UNAVAILABLE_USER_MESSAGE


def test_chat_query_ai_key_missing_structured(client, uploaded_project, consultant_auth_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pid = uploaded_project["id"]
    r = client.post(
        "/chat/query",
        json={"project_id": pid, "message": "What is the average age?"},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 503, r.text
    data = r.json()
    assert data["code"] == "AI_KEY_MISSING"
    assert data["error"] == AI_CHAT_UNAVAILABLE_USER_MESSAGE
    assert isinstance(data.get("suggested_questions"), list)
    assert len(data["suggested_questions"]) >= 1


def test_chat_query_ai_disabled_env(client, uploaded_project, consultant_auth_headers, monkeypatch):
    monkeypatch.setenv("AI_CHAT_DISABLED", "1")
    pid = uploaded_project["id"]
    r = client.post(
        "/chat/query",
        json={"project_id": pid, "message": "Hello"},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 503, r.text
    data = r.json()
    assert data["code"] == "AI_DISABLED"
    assert data["error"] == AI_CHAT_UNAVAILABLE_USER_MESSAGE
    assert isinstance(data.get("suggested_questions"), list)
