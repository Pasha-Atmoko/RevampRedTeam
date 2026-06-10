# backend/tests/test_get_scope.py
import json
from lambdas import get_scope


def test_returns_targets(monkeypatch):
    monkeypatch.setattr(get_scope, "_load_allowlist",
                        lambda: ["54.84.126.64:80", "10.0.0.0/24"])
    out = get_scope.handler({"httpMethod": "GET"}, None)
    assert out["statusCode"] == 200
    body = json.loads(out["body"])
    assert body["targets"] == ["54.84.126.64:80", "10.0.0.0/24"]
    assert out["headers"]["Access-Control-Allow-Origin"] == "*"


def test_empty_on_error(monkeypatch):
    def boom():
        raise RuntimeError("ParameterNotFound")
    monkeypatch.setattr(get_scope, "_load_allowlist", boom)
    out = get_scope.handler({"httpMethod": "GET"}, None)
    assert out["statusCode"] == 200
    body = json.loads(out["body"])
    assert body["targets"] == []
    assert "ParameterNotFound" in body["error"]
