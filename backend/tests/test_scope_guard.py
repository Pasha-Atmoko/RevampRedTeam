# backend/tests/test_scope_guard.py
import pytest
from common.scope_guard import assert_in_scope, ScopeError


def test_in_scope_host_port_passes():
    assert_in_scope("http://1.2.3.4:8080", allowlist=["1.2.3.4:8080"])


def test_out_of_scope_raises():
    with pytest.raises(ScopeError):
        assert_in_scope("http://9.9.9.9:80", allowlist=["1.2.3.4:8080"])


def test_empty_allowlist_fails_closed():
    with pytest.raises(ScopeError):
        assert_in_scope("http://1.2.3.4:8080", allowlist=[])


def test_cidr_entry_matches():
    assert_in_scope("http://10.0.0.5:80", allowlist=["10.0.0.0/24"])
