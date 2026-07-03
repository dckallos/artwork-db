"""
Load and validate ``config/github-client-config.yml`` into frozen dataclasses.

Same discipline as the orchestration loader: parse once, reject unknown keys, and raise
:class:`~ghclient.errors.ConfigError` scoped to the offending file and dotted field.
Nothing here reaches the network; the only disk read is the config file (and a stat to
confirm each referenced policy body exists).

Path resolution:
  * The default config path is ``<repo-root>/config/github-client-config.yml``.
  * ``branch_protection.*.policy`` values resolve relative to ``tools/github/`` (the
    package home), matching the layout in the plan's §4.1 tree, so short paths like
    ``policies/policy.main.json`` work regardless of the caller's CWD.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import yaml

from .errors import ConfigError

# tools/github/ghclient/config.py -> ghclient -> github (package home) -> tools -> repo.
_PACKAGE_DIR = Path(__file__).resolve().parent
_BASE_DIR = _PACKAGE_DIR.parent            # tools/github
_REPO_ROOT = _BASE_DIR.parent.parent       # repo root
_CONFIG_REL = "config/github-client-config.yml"


def default_config_path() -> Path:
    """
    Return the repo-default config location, ``<repo-root>/config/github-client-config.yml``.
    """
    return _REPO_ROOT / _CONFIG_REL


@dataclass(frozen=True)
class BranchPolicyCfg:
    """
    Desired-state protection for one branch.

    ``policy_path`` is the resolved absolute path to the JSON body; ``policy_rel`` is the
    value exactly as written in the config (used in messages so errors echo the file).
    """

    branch: str
    policy_rel: str
    policy_path: Path
    required_checks_from_workflows: bool


@dataclass(frozen=True)
class BranchProtectionCfg:
    """
    The set of protected branches (Model A: ``main`` only, extensible via config).

    ``source`` is the config file path so :meth:`get` can raise a file-scoped error.
    """

    branches: Tuple[BranchPolicyCfg, ...]
    source: str = _CONFIG_REL

    def get(self, branch: str) -> BranchPolicyCfg:
        """
        Return the policy for ``branch``, or raise a scoped :class:`ConfigError`.
        """
        for policy in self.branches:
            if policy.branch == branch:
                return policy
        available = ", ".join(self.names()) or "(none)"
        raise ConfigError(
            self.source,
            "branch_protection.branches",
            f"{branch!r} is not a configured protected branch; available: {available}",
        )

    def names(self) -> list:
        """
        The governed branch names, in config order.
        """
        return [policy.branch for policy in self.branches]


@dataclass(frozen=True)
class GithubClientConfig:
    """
    The parsed, validated client configuration.

    ``raw_secrets`` / ``raw_ci`` are the untouched blocks consumed by Areas B/C; Area A
    validates only that they are mappings so the schema stays stable without coupling to
    behavior that does not exist yet.
    """

    repo: str
    branch_protection: BranchProtectionCfg
    config_path: Path
    base_dir: Path
    raw_secrets: Mapping[str, Any]
    raw_ci: Mapping[str, Any]

    @property
    def exports_dir(self) -> Path:
        """
        Where before-state snapshots are written (gitignored): ``policies/exports/``.
        """
        return self.base_dir / "policies" / "exports"


# --------------------------------------------------------------------------- #
# Validation helpers (file/field-scoped, mirroring the orchestration loader).
# --------------------------------------------------------------------------- #
def _reject_unknown(
    source: str, field: str, mapping: Mapping[str, Any], allowed: set
) -> None:
    """
    Raise :class:`ConfigError` if ``mapping`` has keys outside ``allowed``.
    """
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ConfigError(
            source,
            field,
            f"unknown key(s): {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}",
        )


def _require_mapping(source: str, field: str, value: Any) -> Dict[str, Any]:
    """
    Return ``value`` as a dict, or raise a scoped error if it is not a mapping.
    """
    if not isinstance(value, dict):
        raise ConfigError(source, field, f"expected a mapping, got {type(value).__name__}")
    return value


def _require_str(source: str, field: str, value: Any) -> str:
    """
    Return ``value`` as a non-empty string, or raise a scoped error.
    """
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(source, field, "expected a non-empty string")
    return value


def load_config(
    config_path: Optional[Path] = None, *, package_dir: Optional[Path] = None
) -> GithubClientConfig:
    """
    Parse and validate the client config, returning a :class:`GithubClientConfig`.

    ``config_path`` defaults to :func:`default_config_path`; ``package_dir`` (the root that
    ``policy`` paths resolve against) defaults to ``tools/github/``. Both are injectable
    so tests point at fixtures without touching the repo layout.
    """
    path = Path(config_path) if config_path is not None else default_config_path()
    root = Path(package_dir) if package_dir is not None else _BASE_DIR
    source = str(path)

    if not path.is_file():
        raise ConfigError(source, None, "config file not found")

    try:
        loaded = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(source, None, f"invalid YAML: {exc}") from exc

    top = _require_mapping(source, "<root>", loaded)
    _reject_unknown(source, "<root>", top, {"repo", "branch_protection", "snowflake_secrets", "ci"})

    if "repo" not in top:
        raise ConfigError(source, "repo", "required key is missing")
    repo = _require_str(source, "repo", top["repo"])
    parts = repo.split("/")
    if len(parts) != 2 or not all(p and not any(c.isspace() for c in p) for p in parts):
        raise ConfigError(source, "repo", f"invalid repo {repo!r}; expected 'owner/name'")

    branch_protection = _parse_branch_protection(source, root, top.get("branch_protection", {}))

    raw_secrets = _require_mapping(source, "snowflake_secrets", top.get("snowflake_secrets", {}))
    raw_ci = _require_mapping(source, "ci", top.get("ci", {}))

    return GithubClientConfig(
        repo=repo,
        branch_protection=branch_protection,
        config_path=path,
        base_dir=root,
        raw_secrets=raw_secrets,
        raw_ci=raw_ci,
    )


def _parse_branch_protection(source: str, base_dir: Path, value: Any) -> BranchProtectionCfg:
    """
    Validate the ``branch_protection`` block and resolve each branch's policy file.
    """
    block = _require_mapping(source, "branch_protection", value)
    _reject_unknown(source, "branch_protection", block, {"branches"})
    branches_raw = _require_mapping(
        source, "branch_protection.branches", block.get("branches", {})
    )

    policies = []
    for name, spec in branches_raw.items():
        field = f"branch_protection.branches.{name}"
        spec_map = _require_mapping(source, field, spec)
        _reject_unknown(
            source, field, spec_map, {"policy", "required_checks_from_workflows"}
        )
        if "policy" not in spec_map:
            raise ConfigError(source, f"{field}.policy", "required key is missing")
        policy_rel = _require_str(source, f"{field}.policy", spec_map["policy"])
        policy_path = (base_dir / policy_rel).resolve()
        if not policy_path.is_file():
            raise ConfigError(source, f"{field}.policy", f"file not found: {policy_path}")

        required_flag = spec_map.get("required_checks_from_workflows", False)
        if not isinstance(required_flag, bool):
            raise ConfigError(
                source,
                f"{field}.required_checks_from_workflows",
                "expected a boolean",
            )

        policies.append(
            BranchPolicyCfg(
                branch=name,
                policy_rel=policy_rel,
                policy_path=policy_path,
                required_checks_from_workflows=required_flag,
            )
        )

    return BranchProtectionCfg(branches=tuple(policies), source=source)
