import json

from app.api.envelope import error_envelope, success_envelope


def test_success_envelope_shape() -> None:
    response = success_envelope({"value": 1})
    body = json.loads(response.body.decode("utf-8"))
    assert body["ok"] is True
    assert body["data"] == {"value": 1}
    assert isinstance(body.get("meta"), dict)


def test_error_envelope_shape() -> None:
    response = error_envelope(code="bad_request", message="Invalid", status_code=400, details={"field": "x"})
    body = json.loads(response.body.decode("utf-8"))
    assert body["ok"] is False
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["message"] == "Invalid"
