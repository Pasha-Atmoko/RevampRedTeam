from common.models import Severity, Finding, Target, ScanContext


def test_severity_rank_orders_critical_highest():
    assert Severity.CRITICAL.rank > Severity.HIGH.rank > Severity.INFO.rank


def test_finding_roundtrips_to_item():
    f = Finding(scan_id="s1", finding_id="f1", title="t", severity=Severity.HIGH,
                endpoint="/x", evidence="e", poc="p", remediation="r",
                attack_method="m", persona="ghost")
    item = f.to_item()
    assert item["severity"] == "high"
    assert Finding.from_item(item).severity is Severity.HIGH


def test_target_from_parts_builds_url():
    t = Target.from_parts("1.2.3.4", 8080, "/login")
    assert t.url == "http://1.2.3.4:8080"
    assert t.endpoint == "/login"
