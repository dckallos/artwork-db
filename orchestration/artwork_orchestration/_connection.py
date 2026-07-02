"""Source-agnostic Snowflake connection provider.

This is what decouples the orchestration layer from any one source's extraction package
(previously ``_snowflake`` reached into a specific museum's extraction config +
uploader). Instead, the orchestration layer opens its ad-hoc metadata/check queries
using the SAME dbt PROFILE the transform layer uses -- the single connection identity
for the whole project.

It reads ``framework.yaml -> connection`` (profile / target / profiles_dir), loads that
dbt ``profiles.yml``, renders ``{{ env_var('X'[, 'default']) }}`` from the environment,
and opens a ``snowflake.connector`` connection (key-pair or password). Best-effort by
design: callers in ``_snowflake`` swallow failures so a dev shell without a driver or
credentials degrades to "could not verify" rather than crashing a materialization.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import yaml

from .config import FRAMEWORK, REPO_ROOT

# Matches dbt's {{ env_var('NAME') }} and {{ env_var('NAME', 'default') }}.
_ENV_VAR_RE = re.compile(
    r"\{\{\s*env_var\(\s*'([^']+)'\s*(?:,\s*'([^']*)')?\s*\)\s*\}\}"
)


def _render_env_var(value: Any) -> Any:
    """Render dbt-style ``env_var`` Jinja in a scalar string; pass through non-strings."""
    if not isinstance(value, str):
        return value
    import os

    def repl(m: "re.Match[str]") -> str:
        name, default = m.group(1), m.group(2)
        val = os.environ.get(name, default)
        if val is None:
            raise RuntimeError(
                f"profiles.yml references env var {name!r} with no default and it is unset."
            )
        return val

    return _ENV_VAR_RE.sub(repl, value)


def _resolve_profile() -> Dict[str, Any]:
    """Return the rendered output block for the configured profile + target."""
    conn = FRAMEWORK.connection
    profiles_path = (REPO_ROOT / conn.profiles_dir / "profiles.yml").resolve()
    if not profiles_path.exists():
        raise RuntimeError(f"profiles.yml not found at {profiles_path}")
    doc = yaml.safe_load(profiles_path.read_text()) or {}
    try:
        outputs = doc[conn.profile]["outputs"]
        target = outputs[conn.target]
    except KeyError as exc:
        raise RuntimeError(
            f"profile/target {conn.profile!r}/{conn.target!r} not found in {profiles_path}"
        ) from exc
    return {k: _render_env_var(v) for k, v in target.items()}


def connect():
    """Open a Snowflake connection from the configured dbt profile.

    Supports key-pair auth (``private_key_path`` -> connector ``private_key_file``) and
    password auth. Raises on missing driver / credentials; callers treat that as
    best-effort and degrade gracefully.
    """
    import snowflake.connector  # lazy: only needed when actually querying

    p = _resolve_profile()
    kwargs: Dict[str, Any] = {
        "account": p.get("account"),
        "user": p.get("user"),
        "role": p.get("role"),
        "warehouse": p.get("warehouse"),
        "database": p.get("database"),
        "schema": p.get("schema"),
    }
    key_path = p.get("private_key_path")
    if key_path:
        kwargs["private_key_file"] = str(Path(str(key_path)).expanduser())
        passphrase = p.get("private_key_passphrase")
        if passphrase:
            kwargs["private_key_file_pwd"] = passphrase
    elif p.get("password"):
        kwargs["password"] = p["password"]
    if p.get("authenticator"):
        kwargs["authenticator"] = p["authenticator"]

    return snowflake.connector.connect(**{k: v for k, v in kwargs.items() if v is not None})
