"""
H1 fail-closed export + A1/A2 snapshot-envelope matrix (no network).

Export: a *verified* HTTP 404 is the only failure that yields a delete-eligible
(verified-404) capture; every other failure raises and writes nothing, so "couldn't
reach GitHub" is never mistaken for "there were no rules."

Persistence (A1/A2): a snapshot is stored as a schema-versioned envelope carrying a
PUT-ready ``restore_body`` (a raw GET response is not a valid PUT payload). A bare
``null`` file is refused, and only a ``verified-404`` envelope is delete-eligible.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp
from ghclient.branch_protection import ProtectionSnapshot, Snapshot
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


def test_verified_404_envelope_roundtrips_and_is_delete_eligible(tmp_path: Path) -> None:
    env = bp.build_snapshot(_REPO, Snapshot(branch="main", body=None, source="verified-404"))
    out = bp.write_snapshot(env, tmp_path)
    # Persisted as a schema-versioned envelope object, NOT a bare `null` (A2).
    assert out.read_text().strip() != "null"
    reloaded = bp.read_snapshot(out, "main")
    assert reloaded.is_null and reloaded.source == "verified-404"
    assert bp.plan_rollback(_REPO, reloaded).kind.value == "DELETE"


def test_live_get_response_normalizes_to_valid_put_body(tmp_path: Path) -> None:
    # A realistic GET response: {"enabled": ...} wrappers, url fields, nested user objects.
    live = {
        "url": "https://api.github.com/…/protection",
        "required_status_checks": {"url": "…", "strict": True, "contexts": [], "checks": [{"context": "ci-required", "app_id": 42}]},
        "enforce_admins": {"url": "…", "enabled": False},
        "required_pull_request_reviews": {"url": "…", "dismiss_stale_reviews": True, "required_approving_review_count": 1},
        "restrictions": {"url": "…", "users": [{"login": "octocat"}], "teams": [{"slug": "core"}], "apps": []},
        "required_linear_history": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
    }
    env = bp.build_snapshot(_REPO, Snapshot(branch="main", body=live, source="live"))
    rb = env.restore_body
    # {"enabled": ...} wrappers flattened to booleans; url fields dropped.
    assert rb["enforce_admins"] is False
    assert rb["required_linear_history"] is True
    assert rb["allow_force_pushes"] is False
    assert rb["required_status_checks"] == {"strict": True, "checks": [{"context": "ci-required", "app_id": 42}], "contexts": []}
    assert rb["required_pull_request_reviews"] == {"dismiss_stale_reviews": True, "required_approving_review_count": 1}
    assert rb["restrictions"] == {"users": ["octocat"], "teams": ["core"], "apps": []}
    # The raw response is preserved for audit but never PUT.
    assert env.live_response == live
    put = bp.plan_rollback(_REPO, bp.read_snapshot(bp.write_snapshot(env, tmp_path), "main"))
    assert put.kind.value == "PUT"
    assert put.body == rb


def test_bare_null_file_is_refused(tmp_path: Path) -> None:
    # A hand-written `echo null` must NOT be treated as a delete-eligible verified 404 (A2).
    bad = tmp_path / "main.json"
    bad.write_text("null\n")
    with pytest.raises(GhClientError, match="bare-null"):
        bp.read_snapshot(bad, "main")


def test_untrusted_provenance_envelope_is_refused() -> None:
    # A null restore_body whose source is NOT a verified 404 must never delete protection.
    tainted = ProtectionSnapshot(
        schema_version=1, repo=_REPO, branch="main", captured_at="t",
        source="live", live_response=None, restore_body=None,
    )
    with pytest.raises(GhClientError):
        bp.plan_rollback(_REPO, tainted)


def test_corrupt_snapshot_rollback_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "main.json"
    bad.write_text("{ this is not json ")
    with pytest.raises(GhClientError, match="corrupt snapshot"):
        bp.read_snapshot(bad, "main")


def test_missing_snapshot_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(GhClientError, match="no snapshot"):
        bp.read_snapshot(tmp_path / "absent.json", "main")
