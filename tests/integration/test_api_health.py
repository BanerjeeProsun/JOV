"""API health and diagnostics test."""

from fastapi.testclient import TestClient
from jovsi.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["product"] == "JOV.si"
    assert data["autonomy_level"] == "L0_DRY_RUN"
    assert data["allow_real_submission"] is False


def test_diagnostics_health_endpoint() -> None:
    response = client.get("/diagnostics/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_alive"] is True
    assert "127.0.0.1:8765" in data["submit_host_allowlist"]
