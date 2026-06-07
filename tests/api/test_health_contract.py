from unittest.mock import Mock

from fastapi.testclient import TestClient

from sentinel_common.config import Settings
from sentinel_common.http import create_app


def test_liveness_contract() -> None:
    settings = Settings(
        entra_audience="api://test",
        service_name="contract-test",
    )
    app = create_app(settings, Mock())
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Correlation-ID"]


def test_cookie_authenticated_mutation_requires_same_origin() -> None:
    settings = Settings(
        entra_audience="api://test",
        service_name="contract-test",
        cors_origins=("https://sentinel.example",),
    )
    app = create_app(settings, Mock())

    @app.post("/mutation")
    async def mutation() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, "session")
    assert client.post("/mutation").status_code == 403
    assert (
        client.post(
            "/mutation",
            headers={"Origin": "https://sentinel.example"},
        ).status_code
        == 200
    )
