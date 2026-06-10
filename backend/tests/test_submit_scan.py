# backend/tests/test_submit_scan.py
import json
from lambdas import submit_scan


def test_validate_rejects_unauthorized():
    err = submit_scan._validate({"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                                 "authorized": False})
    assert err is not None and "authorized" in err.lower()


def test_validate_rejects_bad_port():
    err = submit_scan._validate({"ip": "1.2.3.4", "port": 0, "endpoint": "/",
                                 "authorized": True})
    assert err is not None and "port" in err.lower()


def test_validate_rejects_bad_ip():
    err = submit_scan._validate({"ip": "not-an-ip!!", "port": 80, "endpoint": "/",
                                 "authorized": True})
    assert err is not None


def test_validate_accepts_good_input():
    assert submit_scan._validate({"ip": "1.2.3.4", "port": 8080,
                                  "endpoint": "/login", "authorized": True}) is None


def test_validate_rejects_bad_scheme():
    err = submit_scan._validate({"ip": "1.2.3.4", "port": 443, "endpoint": "/",
                                 "authorized": True, "scheme": "ftp"})
    assert err is not None and "scheme" in err.lower()


def test_validate_accepts_https_scheme():
    assert submit_scan._validate({"ip": "1.2.3.4", "port": 443, "endpoint": "/",
                                  "authorized": True, "scheme": "https"}) is None


def test_validate_rejects_bad_agents():
    err = submit_scan._validate({"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                                 "authorized": True, "agents": 99})
    assert err is not None and "agents" in err.lower()


def test_validate_accepts_agents():
    assert submit_scan._validate({"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                                  "authorized": True, "agents": 5}) is None


def test_response_helper_shapes_cors():
    r = submit_scan._resp(202, {"scan_id": "x"})
    assert r["statusCode"] == 202
    assert r["headers"]["Access-Control-Allow-Origin"] == "*"
    assert json.loads(r["body"])["scan_id"] == "x"
