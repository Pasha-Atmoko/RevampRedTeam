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
