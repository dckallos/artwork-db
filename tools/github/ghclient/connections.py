"""
Read ``~/.snowflake/connections.toml`` into a typed profile.

STUB (Area B). The real implementation parses a named connections.toml profile into a
typed ``Profile`` and flags OAuth/session profiles as "not a CI credential" (plan
§12.2.5 / H3). It is intentionally not implemented in Area A; importing this module is
side-effect-free.
"""
from __future__ import annotations

__all__: list = []
