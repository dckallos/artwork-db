"""
Shared fixtures for the ghclient test suite.

Every test is offline: the ``gh`` seam is replaced by :class:`FakeGhRunner`,
which records commands and returns canned :class:`~ghclient.gh.GhResult`\\s.
The package dir (``tools/github``) is put on ``sys.path`` here so tests import
``ghclient`` without an editable install, and so the suite passes with
``PYTHONPATH`` cleared.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[1]  # tools/github
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from ghclient.gh import GhResult  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class FakeGhRunner:
    """
    A no-network :class:`~ghclient.gh.GhRunner` that records calls.

    ``handler`` maps a request to a :class:`~ghclient.gh.GhResult`. It receives
    ``(kind, method, path, input_body)`` where ``kind`` is ``"api"`` or
    ``"run"``. Every call is appended to :attr:`calls` for assertions.
    """

    def __init__(
        self,
        handler: Optional[Callable[[str, str, str, object], GhResult]] = None,
    ) -> None:
        """
        Store the response handler and initialize the call logs.
        """
        self._handler = handler
        self.calls: list = []
        self.run_inputs: list = []

    def _respond(self, kind: str, method: str, path: str, body: object) -> GhResult:
        """
        Delegate to the handler, defaulting to an empty 200.
        """
        if self._handler is not None:
            return self._handler(kind, method, path, body)
        return GhResult(args=("gh", kind, path), returncode=0, stdout="", stderr="", status_code=200)

    def api(self, path, *, method="GET", input_body=None, headers=None) -> GhResult:
        """
        Record and answer a ``gh api`` call.
        """
        self.calls.append(("api", method, path, input_body))
        return self._respond("api", method, path, input_body)

    def run(self, args, *, input_text=None) -> GhResult:
        """
        Record and answer an arbitrary ``gh`` subcommand.

        ``input_text`` (stdin) is captured in :attr:`run_inputs` keyed by argv so tests can
        assert a secret value was fed via stdin -- and never appears on argv.
        """
        args = tuple(args)
        self.calls.append(("run", "", " ".join(args), None))
        self.run_inputs.append((args, input_text))
        return self._respond("run", "", " ".join(args), None)

    @property
    def api_calls(self) -> list:
        """
        Only the ``gh api`` calls, as ``(method, path, body)`` tuples.
        """
        return [(m, p, b) for (k, m, p, b) in self.calls if k == "api"]


def make_result(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    status_code: Optional[int] = None,
) -> GhResult:
    """
    Build a :class:`~ghclient.gh.GhResult` for a canned response.
    """
    if status_code is None and returncode == 0:
        status_code = 200
    return GhResult(
        args=("gh", "api"),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        status_code=status_code,
    )


def map_handler(responses: Dict[Tuple[str, str], GhResult], default: Optional[GhResult] = None):
    """
    Build a handler that keys on ``(method, path)`` then falls back to ``default``.
    """
    def handler(kind: str, method: str, path: str, body: object) -> GhResult:
        return responses.get((method, path)) or default or make_result(stdout="{}")
    return handler


@pytest.fixture
def fixtures_dir() -> Path:
    """
    Absolute path to the committed ``tests/fixtures`` directory.
    """
    return FIXTURES


@pytest.fixture
def fake_runner_factory():
    """
    Factory returning a fresh :class:`FakeGhRunner` for a given handler.
    """
    def _make(handler=None) -> FakeGhRunner:
        return FakeGhRunner(handler=handler)
    return _make


@pytest.fixture
def gh_result():
    """
    Expose :func:`make_result` as a fixture so tests avoid importing conftest.
    """
    return make_result


@pytest.fixture
def gh_map_handler():
    """
    Expose :func:`map_handler` as a fixture.
    """
    return map_handler
