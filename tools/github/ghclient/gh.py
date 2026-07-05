"""
The single subprocess seam to the ``gh`` CLI.

Everything that talks to GitHub goes through a :class:`GhRunner`. One place builds the
argv; production code uses :class:`SubprocessGhRunner`; tests inject a fake that records
commands and returns scripted results, so the whole client is exercised offline with no
live GitHub calls (mirrors ``orchestration/artwork_orchestration/_runner.py``).

Design notes:
  * :class:`SubprocessGhRunner` builds argv in one place and funnels every process
    launch through ``_exec``; callers use ``api``/``run`` and never assemble commands.
  * :class:`GhResult` carries the parsed HTTP ``status_code`` (extracted from ``gh``'s
    ``(HTTP NNN)`` diagnostic or a ``HTTP/x NNN`` status line) so H1 can tell a
    *verified* 404 from any other failure.
  * Import-safe: importing this module starts no process and reads no credentials.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Protocol, Sequence, runtime_checkable

# ``gh`` signals the HTTP status two ways: the diagnostic ``gh: Not Found (HTTP 404)`` on
# stderr, and (with ``--include``/verbose) a ``HTTP/2 403 ...`` status line. We parse both
# rather than depend on header ordering.
_HTTP_PAREN_RE = re.compile(r"\(HTTP (\d{3})\)")
_HTTP_STATUS_LINE_RE = re.compile(r"HTTP/[\d.]+\s+(\d{3})")


def parse_http_status(stderr: str, stdout: str = "") -> Optional[int]:
    """
    Return the HTTP status embedded in ``gh`` output, or ``None`` when absent.

    Looks at ``stderr`` first (where ``gh`` prints ``(HTTP NNN)`` diagnostics), then
    ``stdout`` (where a ``HTTP/x NNN`` status line may appear). ``None`` for transport
    failures (timeouts, missing binary) that carry no HTTP status.
    """
    for text in (stderr, stdout):
        if not text:
            continue
        match = _HTTP_PAREN_RE.search(text) or _HTTP_STATUS_LINE_RE.search(text)
        if match:
            return int(match.group(1))
    return None


@dataclass(frozen=True)
class GhResult:
    """
    The outcome of a single ``gh`` invocation.

    ``args`` is the full argv (minus the ``gh`` binary). ``status_code`` is the HTTP
    status parsed from ``stderr``/``stdout`` when the call was an API request that
    returned an HTTP error; it is ``None`` for success and for transport failures.
    """

    args: Sequence[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    status_code: Optional[int] = None

    @property
    def ok(self) -> bool:
        """
        True when ``gh`` exited zero.
        """
        return self.returncode == 0

    def json(self) -> Any:
        """
        Parse ``stdout`` as JSON (``null`` when empty), raising on malformed output.
        """
        return json.loads(self.stdout or "null")


_ACCEPT_HEADER = "Accept: application/vnd.github+json"


@runtime_checkable
class GhRunner(Protocol):
    """
    The injectable seam to ``gh``: one ``api`` method for REST calls and one ``run``
    method for arbitrary subcommands (e.g. ``gh auth status``).

    Production code uses :class:`SubprocessGhRunner`; tests inject a fake that records
    calls and returns scripted :class:`GhResult`\\s, so the whole client runs offline.
    """

    def api(
        self,
        path: str,
        *,
        method: str = "GET",
        input_body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Sequence[str]] = None,
    ) -> GhResult:
        """
        Issue ``gh api`` against ``path`` and return the structured result.
        """
        ...

    def run(self, args: Sequence[str], *, input_text: Optional[str] = None) -> GhResult:
        """
        Execute an arbitrary ``gh <args...>`` subcommand and return the result.

        ``input_text``, when given, is fed to the process on stdin -- the way a secret
        value reaches ``gh secret set`` without ever appearing on argv or in any log (H5).
        """
        ...


class SubprocessGhRunner:
    """
    Production :class:`GhRunner`: shells out to the real ``gh`` binary.

    The binary path is injectable (defaults to ``gh`` on ``PATH``) so tests never need
    it and alternate installs are supported. All process execution funnels through the
    single ``_exec`` seam, which tests monkeypatch to capture argv without spawning.
    """

    def __init__(self, gh_bin: str = "gh", *, timeout: Optional[float] = None) -> None:
        """
        Configure the runner with a ``gh`` binary path and optional per-call timeout.
        """
        self._gh_bin = gh_bin
        self._timeout = timeout

    def _exec(self, args: Sequence[str], input_text: Optional[str]) -> GhResult:
        """
        Run ``gh <args...>`` once, capturing output and parsing any HTTP status.

        Missing binaries and timeouts are returned as structured failures rather than
        escaping as Python tracebacks, so callers render actionable diagnostics and tests
        can assert the same failure model as HTTP errors.
        """
        try:
            proc = subprocess.run(
                [self._gh_bin, *args],
                input=input_text,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            return GhResult(
                args=tuple(args),
                returncode=127,
                stdout="",
                stderr=f"gh executable not found: {self._gh_bin}",
                status_code=None,
            )
        except subprocess.TimeoutExpired:
            return GhResult(
                args=tuple(args),
                returncode=124,
                stdout="",
                stderr=f"gh command timed out after {self._timeout} seconds",
                status_code=None,
            )
        status = parse_http_status(proc.stderr, proc.stdout)
        return GhResult(
            args=tuple(args),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            status_code=status,
        )

    def api(
        self,
        path: str,
        *,
        method: str = "GET",
        input_body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Sequence[str]] = None,
    ) -> GhResult:
        """
        Build and run a ``gh api`` call; a body (``input_body``) is piped via stdin.

        Passing the body through stdin (``--input -``) keeps it out of argv and any log.
        """
        args: List[str] = ["api", path, "--method", method, "-H", _ACCEPT_HEADER]
        for header in headers or ():
            args += ["-H", header]
        input_text: Optional[str] = None
        if input_body is not None:
            args += ["--input", "-"]
            input_text = json.dumps(input_body)
        return self._exec(args, input_text)

    def run(self, args: Sequence[str], *, input_text: Optional[str] = None) -> GhResult:
        """
        Execute an arbitrary ``gh <args...>`` subcommand, optionally feeding stdin.

        ``input_text`` is passed to the process on stdin (never on argv), so a secret
        value handed to ``gh secret set NAME --env ...`` stays off the process list (H5).
        """
        return self._exec(list(args), input_text)
