import json
from src.handlers.health import handler


def test_health():
    response = handler({}, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"
    assert "POST /tasks" in body["endpoints"]
    assert "PUT /tasks/{taskId}" in body["endpoints"]
    assert "POST /webhook/teams" in body["endpoints"]
