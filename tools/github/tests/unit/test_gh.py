"""
Unit tests for the GhRunner seam: argv construction + HTTP status parsing.

No subprocess is spawned -- the SubprocessGhRunner's ``_exec`` is monkeypatched
to capture the argv it *would* run.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_network

from ghclient.gh import GhResult, SubprocessGhRunner, parse_http_status


def test_parse_http_status_from_paren_style() -> None:
    assert parse_http_status("gh: Not Found (HTTP 404)") == 404


def test_parse_http_status_from_status_line() -> None:
    assert parse_http_status("", "HTTP/2 403 Forbidden\n") == 403


def test_parse_http_status_none_when_absent() -> None:
    assert parse_http_status("connection timed out", "") is None


def test_api_builds_get_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_exec(self, args, input_text):
        captured["args"] = list(args)
        captured["input"] = input_text
        return GhResult(args=tuple(args), returncode=0, stdout="{}", status_code=200)

    monkeypatch.setattr(SubprocessGhRunner, "_exec", fake_exec)
    SubprocessGhRunner().api("repos/o/r/branches/main/protection")
    assert captured["args"][:3] == ["api", "repos/o/r/branches/main/protection", "--method"]
    assert "GET" in captured["args"]
    assert captured["input"] is None


def test_api_pipes_put_body_via_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_exec(self, args, input_text):
        captured["args"] = list(args)
        captured["input"] = input_text
        return GhResult(args=tuple(args), returncode=0, stdout="", status_code=200)

    monkeypatch.setattr(SubprocessGhRunner, "_exec", fake_exec)
    SubprocessGhRunner().api("repos/o/r", method="PUT", input_body={"a": 1})
    assert "--input" in captured["args"]
    assert captured["args"][captured["args"].index("--input") + 1] == "-"
    assert captured["input"] == '{"a": 1}'


def test_result_ok_and_json() -> None:
    res = GhResult(args=(), returncode=0, stdout='{"x": 1}', status_code=200)
    assert res.ok is True
    assert res.json() == {"x": 1}
    assert GhResult(args=(), returncode=1).ok is False
