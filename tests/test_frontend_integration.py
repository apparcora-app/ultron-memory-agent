import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path
from app import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def _mock_agent():
    mock_ag = MagicMock()
    mock_ag.memory = MagicMock()
    mock_ag.memory.get_all_skills.return_value = []
    with patch("app.get_or_create_agent", return_value=mock_ag):
        yield

def test_static_index_served():
    """Verify that root / serves the newly compiled Stitch frontend."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Ultron Protocol // Vivid Sky Blue Edition" in response.text
    assert "Nunito+Sans" in response.text

def test_api_providers():
    """Verify /api/providers returns valid model providers."""
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)

def test_api_sessions_lifecycle():
    """Verify sessions listing and creation for user boss."""
    res = client.get("/api/sessions?user_id=boss")
    assert res.status_code == 200
    
    # Create new session
    form_data = {
        "user_id": "boss",
        "module_id": "default",
        "title": "Stitch Verification Session",
    }
    create_res = client.post("/api/sessions/new", data=form_data)
    assert create_res.status_code == 200
    session_data = create_res.json()
    assert "session" in session_data
    assert "id" in session_data["session"]

def test_api_skills():
    """Verify /api/skills returns skill matrix items."""
    res = client.get("/api/skills?user_id=boss")
    assert res.status_code == 200
    data = res.json()
    assert "skills" in data
