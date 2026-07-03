"""
H1 fail-closed export/rollback matrix (no network).

A *verified* HTTP 404 is the only failure that yields a ``null`` (delete-eligible)
snapshot; every other failure raises and writes nothing, so "couldn't reach GitHub" is
never mistaken for "there were no rules." Corrupt/untrusted snapshots are refused.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp
from ghclient.branch_protection import Snapshot
from ghclient.errors import GhApiError, GhClientError

_REPO = "octocat/hello-world"


def test_verified_404_yields_null_snapshot(fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404))
    snap = bp.export_snapshot(runner, _REPO, "main")
    assert snap.is_null
    assert snap.source == "verified-404"


@pytest.mark.parametrize(
    "returncode,stderr,status",
    [
        (1, "Forbidden (HTTP 403)", 403),
        (1, "Server Error (HTTP 500)", 500),
        (1, "connection timed out", None),  # transport failure: no HTTP status at all
    ],
)
def test_non_404_failures_fail_closed(fake_runner_factory, gh_result, returncode, stderr, status) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=returncode, stderr=stderr, status_code=status))
    with pytest.raises(GhApiError) as exc:
        bp.export_snapshot(runner, _REPO, "main")
    assert exc.value.status_code == status  # no snapshot object is ever returned


def test_success_with_malformed_json_fails_closed(fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0, stdout="{not json", status_code=200))
    with pytest.raises(GhApiError):
        bp.export_snapshot(runner, _REPO, "main")


def test_null_snapshot_roundtrips_and_is_delete_eligible(tmp_path: Path) -> None:
    snap = Snapshot(branch="main", body=None, source="verified-404")
    out = bp.write_snapshot(snap, tmp_path)
    assert out.read_text().strip() == "null"
    reloaded = bp.read_snapshot(out, "main")
    assert reloaded.is_null and reloaded.source == "verified-404"
    assert bp.plan_rollback(_REPO, reloaded).kind.value == "DELETE"


def test_untrusted_null_provenance_is_refused() -> None:
    # A null body that did NOT come from a verified 404 must never delete protection.
    tainted = Snapshot(branch="main", body=None, source="error")
    with pytest.raises(GhClientError, match="untrusted provenance"):
        bp.plan_rollback(_REPO, tainted)


def test_corrupt_snapshot_rollback_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "main.json"
    bad.write_text("{ this is not json ")
    with pytest.raises(GhClientError, match="corrupt snapshot"):
        bp.read_snapshot(bad, "main")


def test_missing_snapshot_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(GhClientError, match="no snapshot"):
        bp.read_snapshot(tmp_path / "absent.json", "main")
