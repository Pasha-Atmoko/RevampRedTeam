# backend/tests/test_store.py
import os
import boto3
import pytest
from moto import mock_aws

TABLE = "tier2-scans-test"


@pytest.fixture
def table(monkeypatch):
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        monkeypatch.setenv("SCANS_TABLE", TABLE)
        import importlib
        from common import store
        importlib.reload(store)
        yield store


def test_create_and_get_job(table):
    store = table
    store.create_job("s1", {"ip": "1.2.3.4", "port": 8080, "endpoint": "/x",
                            "url": "http://1.2.3.4:8080"})
    job = store.get_scan("s1")
    assert job["status"] == "QUEUED"
    assert job["target"]["port"] == 8080
    assert job["findings"] == []


def test_update_status_and_findings(table):
    store = table
    store.create_job("s2", {"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                            "url": "http://1.2.3.4:80"})
    store.update_job("s2", status="RUNNING", scenario="# s", engine="offline-sim",
                     profile={"alias": "a"})
    store.put_finding("s2", {"finding_id": "f1", "title": "t", "severity": "low",
                             "endpoint": "/", "evidence": "e", "poc": "",
                             "remediation": "", "attack_method": "", "persona": ""})
    job = store.get_scan("s2")
    assert job["status"] == "RUNNING"
    assert job["scenario"] == "# s"
    assert len(job["findings"]) == 1
    assert job["findings"][0]["title"] == "t"


def test_put_agent_and_findings_dedupe(table):
    store = table
    store.create_job("s4", {"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                            "url": "http://1.2.3.4:80"})
    store.put_agent("s4", 0, {"alias": "a", "archetype": "X"}, "# scen0", "offline-sim")
    store.put_agent("s4", 1, {"alias": "b", "archetype": "Y"}, "# scen1", "offline-sim")
    # identical finding reported by two different agents -> deduped to one
    for fid, persona in (("f1", "X"), ("f2", "Y")):
        store.put_finding("s4", {"finding_id": fid, "title": "Dup", "severity": "low",
                                 "endpoint": "/x", "evidence": "e", "poc": "",
                                 "remediation": "", "attack_method": "", "persona": persona})
    job = store.get_scan("s4")
    assert len(job["agents"]) == 2
    assert job["agents"][0]["index"] == 0
    assert len(job["findings"]) == 1  # deduped across agents


def test_profile_with_floats_roundtrips(table):
    """Regression: attacker profiles contain floats (stealth/aggressiveness);
    DynamoDB rejects float, so store must convert to Decimal and back."""
    store = table
    store.create_job("s3", {"ip": "1.2.3.4", "port": 80, "endpoint": "/",
                            "url": "http://1.2.3.4:80"})
    profile = {"alias": "ghost01", "stealth": 0.8, "aggressiveness": 0.3,
               "preferred_ttps": ["a", "b"], "nested": {"score": 0.55}}
    store.update_job("s3", status="RUNNING", profile=profile)
    job = store.get_scan("s3")
    assert job["profile"]["stealth"] == 0.8          # comes back as float, not Decimal/str
    assert job["profile"]["aggressiveness"] == 0.3
    assert job["profile"]["nested"]["score"] == 0.55
    assert job["target"]["port"] == 80               # integral Decimal -> int
