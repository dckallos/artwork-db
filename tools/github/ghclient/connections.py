"""
Read a Snowflake ``connections.toml`` profile into a typed, validated profile.

Pure and fail-aware: the only disk read happens inside :func:`load_profile` at call time
(never at import), so importing this module touches no credentials and starts no process
(the "no import-time side effects" non-negotiable). A missing file, missing profile, or
missing required field raises a file/field-scoped :class:`~ghclient.errors.ConfigError`
whose message points at the exact ``[profile].field`` to fix -- never a bare ``KeyError``.

The connections file is the Snowflake CLI's ``~/.snowflake/connections.toml``: each
top-level TOML table is a named connection profile (``[default]``, ``[prod]``, ...). The
``[default]`` profile is typically OAuth/session (a ``token`` / ``token_file_path`` and no
key pair), which is *not* a durable CI credential -- :meth:`Profile.is_session_token_field`
and :data:`SESSION_TOKEN_FIELDS` let the publisher refuse to route such a token into a
GitHub secret (plan §12.2.5 / H3).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple

from .errors import ConfigError

__all__ = ["Profile", "SESSION_TOKEN_FIELDS", "load_profile"]

# Fields that carry an ephemeral OAuth/session token rather than a durable credential.
# Routing any of these into a GitHub *secret* is the "OAuth-profile footgun" H3 refuses.
SESSION_TOKEN_FIELDS: Tuple[str, ...] = ("token", "token_file_path")

# TOML keys that name a connection's authentication method; used only to describe a profile.
_OAUTH_AUTHENTICATORS = ("oauth", "externalbrowser")


@dataclass(frozen=True)
class Profile:
    """
    A single parsed ``connections.toml`` profile.

    ``name`` is the profile (TOML table) name; ``source`` is the connections file path (for
    error scoping); ``fields`` is the raw key/value mapping exactly as parsed, so callers
    resolve a mapped field by its TOML key without this module enumerating every possible
    Snowflake connection option.
    """

    name: str
    source: str
    fields: Mapping[str, Any]

    @property
    def role(self) -> str | None:
        """
        The connection's ``role`` (used for the H3 least-privilege guard), or ``None``.
        """
        role = self.fields.get("role")
        return role if isinstance(role, str) and role.strip() else None

    @property
    def user(self) -> str | None:
        """
        The connection's ``user`` (the published CI identity), or ``None`` when unset.
        """
        user = self.fields.get("user")
        return user if isinstance(user, str) and user.strip() else None

    def is_session_token_field(self, toml_field: str) -> bool:
        """
        True when ``toml_field`` names an ephemeral OAuth/session token, not a credential.
        """
        return toml_field in SESSION_TOKEN_FIELDS

    def is_session_only(self) -> bool:
        """
        True when this profile authenticates by OAuth/session with no key pair present.

        Such a profile is *not* a CI credential: it carries a short-lived token or drives an
        interactive browser flow, so its identity cannot be published as durable key material.
        """
        authenticator = self.fields.get("authenticator")
        has_token = any(f in self.fields for f in SESSION_TOKEN_FIELDS)
        has_key = any(
            k in self.fields for k in ("private_key_path", "private_key_file", "private_key")
        )
        is_oauth = isinstance(authenticator, str) and authenticator.lower() in _OAUTH_AUTHENTICATORS
        return (is_oauth or has_token) and not has_key

    def require(self, toml_field: str) -> str:
        """
        Return the string value of ``toml_field``, or raise a field-scoped error.

        Missing, empty, or non-string values raise a :class:`ConfigError` scoped to
        ``[<profile>].<field>`` so the message names the exact line to fix.
        """
        if toml_field not in self.fields:
            raise ConfigError(
                self.source,
                f"[{self.name}].{toml_field}",
                "required field is missing from the connections profile",
            )
        value = self.fields[toml_field]
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(
                self.source,
                f"[{self.name}].{toml_field}",
                "expected a non-empty string value",
            )
        return value


def _expand(source: str) -> Path:
    """
    Expand ``~`` and ``$VARS`` in a connections path (done at call time, never at import).
    """
    return Path(os.path.expandvars(os.path.expanduser(source)))


def load_profile(source: str, profile: str) -> Profile:
    """
    Parse ``profile`` out of the ``connections.toml`` at ``source`` into a :class:`Profile`.

    ``source`` may contain ``~``/``$VAR`` (expanded here, not at import). Raises a
    file/field-scoped :class:`ConfigError` for a missing file, unreadable/invalid TOML, or an
    absent profile -- the string form always names the offending file (and profile).
    """
    path = _expand(source)
    display = str(path)

    if not path.is_file():
        raise ConfigError(display, None, "connections file not found")

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(display, None, f"invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(display, None, f"cannot read connections file: {exc}") from exc

    tables = {name: body for name, body in data.items() if isinstance(body, dict)}
    if profile not in tables:
        available = ", ".join(sorted(tables)) or "(none)"
        raise ConfigError(
            display,
            f"[{profile}]",
            f"connection profile not found; available: {available}",
        )

    return Profile(name=profile, source=display, fields=dict(tables[profile]))
