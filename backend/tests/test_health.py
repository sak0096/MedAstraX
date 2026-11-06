from fastapi.testclient import TestClient
from hc_analytics.api.app import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "condition" not in body

    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "live"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["participant_launch_allowed"] is False
    assert "correct_ranking" not in ready.text
