"""
Source-agnostic Snowflake connection provider.

This is what decouples the orchestration layer from any one source's extraction package
(previously ``_snowflake`` reached into a specific museum's extraction config +
uploader). Instead, the orchestration layer opens its ad-hoc metadata/check queries
using the SAME dbt PROFILE the transform layer uses -- the single connection identity
for the whole project.

It reads the dbt ``profiles.yml`` (located via ``config.DBT_PROFILES_DIR``), renders
``{{ env_var('X'[, 'default']) }}`` from the environment, and opens a
``snowflake.connector`` connection. Best-effort by design: callers in ``_snowflake``
swallow failures so a dev shell without a driver or credentials degrades to "could not
verify" rather than crashing a materialization.

Design for testability: the two hot-path pieces are PURE and free of Dagster / the
Snowflake driver, so they can be unit-tested with only PyYAML installed:

* :func:`_resolve_profile` -- parse ``profiles.yml -> profile -> target`` (with
  ``env_var`` rendering) into a typed :class:`ProfileConfig`. Called with no args it
  resolves the DEFAULT profile from the framework config; called with an explicit
  ``profiles_path`` + ``profile`` + ``target`` it is a fixture-driven test seam.
* :func:`build_connect_kwargs` -- map a :class:`ProfileConfig` onto ``snowflake.connector``
  kwargs for EVERY dbt auth method (key-pair, password, externalbrowser, oauth,
  username_password_mfa, and the in-Snowflake session/native path).

``config`` is imported lazily (only when resolving the *default* profile) so importing
this module never triggers the framework/Dagster import chain.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .model import ProfileConfig

# Matches dbt's {{ env_var('NAME') }} and {{ env_var('NAME', 'default') }}.
_ENV_VAR_RE = re.compile(
    r"\{\{\s*env_var\(\s*'([^']+)'\s*(?:,\s*'([^']*)')?\s*\)\s*\}\}"
)

# Where an in-Snowflake (SPCS / native dbt ``target: snowflake``) session drops its OAuth
# login token. Overridable for tests and non-default container layouts.
_SESSION_TOKEN_ENV = "SNOWFLAKE_TOKEN_FILE_PATH"
_DEFAULT_SESSION_TOKEN_PATH = "/snowflake/session/token"


def _render_env_var(value: Any) -> Any:
    """
    Render dbt-style ``env_var`` Jinja in a scalar string; pass through non-strings.
    """
    if not isinstance(value, str):
        return value

    def repl(m: "re.Match[str]") -> str:
        name, default = m.group(1), m.group(2)
        val = os.environ.get(name, default)
        if val is None:
            raise RuntimeError(
                f"profiles.yml references env var {name!r} with no default and it is unset."
            )
        return val

    return _ENV_VAR_RE.sub(repl, value)


def _session_token() -> Optional[str]:
    """
    Return the in-Snowflake session OAuth token, or ``None`` if not running inside one.
    """
    path = os.environ.get(_SESSION_TOKEN_ENV, _DEFAULT_SESSION_TOKEN_PATH)
    try:
        token = Path(path).read_text().strip()
    except OSError:
        return None
    return token or None


def _derive_profile_name(project_dir: Any) -> str:
    """
    Derive the dbt profile name from ``<project_dir>/dbt_project.yml`` (``profile:``).

    This is what lets ``framework.yaml`` OMIT ``connection.profile`` -- the name is
    single-sourced in the dbt project and can never drift from a duplicate. Raises an
    actionable error if it cannot be read.
    """
    dbt_project = Path(project_dir) / "dbt_project.yml"
    try:
        doc = yaml.safe_load(dbt_project.read_text()) or {}
    except OSError as exc:
        raise RuntimeError(
            f"connection.profile is unset and {dbt_project} could not be read to derive "
            f"it ({exc}). Set connection.profile in framework.yaml."
        ) from exc
    name = doc.get("profile") if isinstance(doc, dict) else None
    if not name:
        raise RuntimeError(
            f"connection.profile is unset and {dbt_project} has no 'profile:' key to "
            "derive it from. Set connection.profile in framework.yaml."
        )
    return str(name)


def _resolve_profile(
    profiles_path: Any = None,
    *,
    profile: Optional[str] = None,
    target: Optional[str] = None,
) -> ProfileConfig:
    """
    Resolve ``profiles.yml -> profile -> target`` into a typed :class:`ProfileConfig`.

    Two modes:

    * **Default** (no ``profiles_path``): pull the profiles.yml location, target, and
      profile name from the framework config (``config`` imported lazily). The profile
      name is ``connection.profile`` or, when omitted, derived from ``dbt_project.yml``.
    * **Explicit** (``profiles_path`` given): the unit-test seam -- ``profile`` AND
      ``target`` are required so no framework config / Dagster import is needed.

    Renders ``{{ env_var(...) }}`` tokens from the environment either way. PyYAML only --
    no Dagster, no Snowflake driver.
    """
    if profiles_path is None:
        from .config import DBT_PROFILES_DIR, DBT_PROJECT_DIR, FRAMEWORK  # lazy: avoids Dagster on import

        conn = FRAMEWORK.connection
        profiles_path = DBT_PROFILES_DIR / "profiles.yml"
        profile = profile or conn.profile or _derive_profile_name(DBT_PROJECT_DIR)
        target = target or conn.target
    else:
        if not target:
            raise ValueError("_resolve_profile(profiles_path=...) requires an explicit target=.")
        if not profile:
            raise ValueError("_resolve_profile(profiles_path=...) requires an explicit profile=.")

    path = Path(profiles_path)
    if not path.exists():
        raise RuntimeError(f"profiles.yml not found at {path}")
    doc = yaml.safe_load(path.read_text()) or {}
    try:
        target_block = doc[profile]["outputs"][target]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"profile/target {profile!r}/{target!r} not found in {path}"
        ) from exc
    rendered = {k: _render_env_var(v) for k, v in target_block.items()}
    return ProfileConfig.from_mapping(rendered)


def _auth_kwargs(p: ProfileConfig) -> Dict[str, Any]:
    """
    Map a resolved profile onto ``snowflake.connector`` AUTH kwargs.

    Handles every dbt-snowflake auth method the project uses. Precedence mirrors dbt:
    an explicit key-pair or authenticator wins over a bare password, and the in-Snowflake
    session token is the fallback for the credential-less native ``target: snowflake``.
    """
    authr = (p.authenticator or "").strip().lower()

    # 1. Key-pair (private_key_path -> connector private_key_file). Highest precedence.
    if p.private_key_path:
        out: Dict[str, Any] = {
            "private_key_file": str(Path(p.private_key_path).expanduser())
        }
        if p.private_key_passphrase:
            out["private_key_file_pwd"] = p.private_key_passphrase
        return out

    # 2. externalbrowser (SSO / IdP browser flow) -- no password or token.
    if authr == "externalbrowser":
        return {"authenticator": "externalbrowser"}

    # 3. OAuth -- an explicit bearer token, else the in-Snowflake session token.
    if authr == "oauth":
        return {"authenticator": "oauth", "token": p.token or _session_token()}

    # 4. MFA-cached password login (authenticator: username_password_mfa).
    if authr.startswith("username_password_mfa"):
        return {"authenticator": p.authenticator, "password": p.password}

    # 5. Password (optionally with an explicit authenticator, e.g. 'snowflake').
    if p.password:
        out = {"password": p.password}
        if p.authenticator:
            out["authenticator"] = p.authenticator
        return out

    # 6. Session / native (dbt ``target: snowflake`` run INSIDE Snowflake): the profile
    #    carries no credentials -- inherit the running session via its OAuth token file.
    token = _session_token()
    if token:
        return {"authenticator": "oauth", "token": token}

    # 7. Any other explicit authenticator passthrough (custom connector authenticator).
    if p.authenticator:
        return {"authenticator": p.authenticator}

    return {}


def build_connect_kwargs(p: ProfileConfig) -> Dict[str, Any]:
    """
    Build the full ``snowflake.connector.connect`` kwargs for a profile (pure).

    Combines the identity/session fields with the auth kwargs from :func:`_auth_kwargs`
    and drops any ``None`` values. No Snowflake import -- this is the unit-test seam for
    auth-method coverage.
    """
    kwargs: Dict[str, Any] = {
        "account": p.account,
        "user": p.user,
        "role": p.role,
        "warehouse": p.warehouse,
        "database": p.database,
        "schema": p.schema,
        "host": p.host,
    }
    kwargs.update(_auth_kwargs(p))
    return {k: v for k, v in kwargs.items() if v is not None}


def connect():
    """
    Open a Snowflake connection from the configured dbt profile.

    Supports every dbt auth method via :func:`build_connect_kwargs` (key-pair, password,
    externalbrowser, oauth, username_password_mfa, and the in-Snowflake session/native
    path). Raises on missing driver / credentials; callers treat that as best-effort and
    degrade gracefully.
    """
    import snowflake.connector  # lazy: only needed when actually querying

    kwargs = build_connect_kwargs(_resolve_profile())
    return snowflake.connector.connect(**kwargs)
