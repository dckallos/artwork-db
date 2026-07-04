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
from enum import Enum
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
class CiCfg:
    """
    The ``ci`` block: which workflows feed the required-check reconcile and the name of
    the always-emitting aggregate context (H2).

    ``aggregate_context`` is the single stable status name that ``ci reconcile`` sets as
    the branch's required check -- never a path-filtered job name (which would deadlock
    docs-only PRs). ``workflows`` are repo-relative paths (e.g.
    ``.github/workflows/ci.yml``); the aggregate job must be defined in one of them.
    ``aggregate_workflow`` (optional, C2) names the ONE workflow that actually emits the
    aggregate; the rest are *informational* (their jobs feed the gate but are not the
    required check). When set, ``ci reconcile`` validates that workflow's shape (C3).
    ``source`` is the config file path so consumers can raise file-scoped errors.
    """

    workflows: Tuple[str, ...]
    aggregate_context: str
    aggregate_workflow: Optional[str] = None
    required_checks: str = "auto"
    source: str = _CONFIG_REL

    @property
    def informational_workflows(self) -> Tuple[str, ...]:
        """
        The configured workflows that are NOT the aggregate emitter (feed it, not required).
        """
        if self.aggregate_workflow is None:
            return ()
        return tuple(wf for wf in self.workflows if wf != self.aggregate_workflow)


class ItemKind(Enum):
    """
    Whether a published item is a GitHub Actions **secret** (write-only, value never
    readable) or a **variable** (readable, value may be diffed). Drives H8 semantics.
    """

    SECRET = "secret"
    VARIABLE = "variable"


class TargetType(Enum):
    """
    Where published items land. v1 supports GitHub deployment **environments** only;
    ``repo``/``org`` targets are an additive future extension (plan §4.2).
    """

    ENVIRONMENT = "environment"


class ExtraSource(Enum):
    """
    Where an ``extra`` item's value comes from when it is not a connections.toml field:
    a file on disk (key material), an interactive prompt, or an inline literal.
    """

    FROM_FILE = "from_file"
    PROMPT = "prompt"
    VALUE = "value"


@dataclass(frozen=True)
class TargetRef:
    """
    The publish target: a type (v1: environment) plus its name (e.g. ``prod``).
    """

    type: TargetType
    name: str


@dataclass(frozen=True)
class MappedField:
    """
    One connections.toml field routed to a GitHub item.

    ``toml_field`` is the profile key to read (e.g. ``account``); ``gh_name`` is the
    GitHub secret/variable name to write (e.g. ``SNOWFLAKE_ACCOUNT``); ``kind`` selects
    secret vs variable (H8).
    """

    toml_field: str
    gh_name: str
    kind: ItemKind


@dataclass(frozen=True)
class ExtraItem:
    """
    A published item whose value is *not* in the connections.toml profile.

    ``source`` says where the value comes from; ``ref`` is the file path (``FROM_FILE``)
    or inline literal (``VALUE``), and ``None`` for ``PROMPT``. Extra items are always
    secrets (key material / passphrases), so the raw value never enters config or logs.
    """

    gh_name: str
    kind: ItemKind
    source: ExtraSource
    ref: Optional[str]


@dataclass(frozen=True)
class PublishSet:
    """
    One named publish set: a connections.toml profile mapped onto a GitHub target.

    ``allow_roles`` is the per-set role allowlist (H3); a connection whose role is absent
    from it (or is ``ACCOUNTADMIN``) is refused unless the CLI passes an explicit
    ``--allow-role`` override.
    """

    name: str
    profile: str
    target: TargetRef
    mapped: Tuple[MappedField, ...]
    extra: Tuple[ExtraItem, ...]
    allow_roles: Tuple[str, ...]


@dataclass(frozen=True)
class SecretsCfg:
    """
    The ``snowflake_secrets`` block: the connections.toml source plus named publish sets.

    ``source`` is the raw (unexpanded) path exactly as written; ``~`` is expanded by
    :mod:`ghclient.connections` at run time, never at import. ``source_file`` is the
    config file path so lookups raise file-scoped errors.
    """

    source: str
    profiles: Mapping[str, PublishSet]
    source_file: str = _CONFIG_REL

    def get(self, name: str) -> PublishSet:
        """
        Return the publish set ``name``, or raise a scoped :class:`ConfigError`.
        """
        publish_set = self.profiles.get(name)
        if publish_set is None:
            available = ", ".join(sorted(self.profiles)) or "(none)"
            raise ConfigError(
                self.source_file,
                "snowflake_secrets.profiles",
                f"{name!r} is not a configured publish set; available: {available}",
            )
        return publish_set


@dataclass(frozen=True)
class GithubClientConfig:
    """
    The parsed, validated client configuration.

    ``secrets`` is the typed Area-B ``snowflake_secrets`` block (connections source +
    named publish sets), or ``None`` when the config declares no ``snowflake_secrets:``
    section. ``ci`` is the typed Area-C block, or ``None`` when there is no ``ci:``.
    """

    repo: str
    branch_protection: BranchProtectionCfg
    config_path: Path
    base_dir: Path
    secrets: Optional[SecretsCfg]
    ci: Optional[CiCfg]

    @property
    def exports_dir(self) -> Path:
        """
        Where before-state snapshots are written (gitignored): ``policies/exports/``.
        """
        return self.base_dir / "policies" / "exports"

    @property
    def repo_root(self) -> Path:
        """
        The repository root, derived from the config file's standard ``<root>/config/``
        location; ``ci.workflows`` (repo-relative paths) resolve against it.
        """
        return self.config_path.resolve().parent.parent


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

    secrets = _parse_secrets(source, top["snowflake_secrets"]) if "snowflake_secrets" in top else None
    ci = _parse_ci(source, top.get("ci")) if "ci" in top else None

    return GithubClientConfig(
        repo=repo,
        branch_protection=branch_protection,
        config_path=path,
        base_dir=root,
        secrets=secrets,
        ci=ci,
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


_CI_ALLOWED_KEYS = {"workflows", "required_checks", "aggregate_context", "aggregate_workflow"}
_CI_REQUIRED_CHECK_MODES = {"auto"}


def _parse_ci(source: str, value: Any) -> CiCfg:
    """
    Validate the ``ci`` block into a :class:`CiCfg` (workflows, mode, aggregate context).

    ``workflows`` must be a non-empty list of workflow paths, ``aggregate_context`` a
    non-empty string, and ``required_checks`` (optional, default ``auto``) one of the
    supported modes. Every failure is scoped to ``ci.<field>``.
    """
    block = _require_mapping(source, "ci", value)
    _reject_unknown(source, "ci", block, _CI_ALLOWED_KEYS)

    if "workflows" not in block:
        raise ConfigError(source, "ci.workflows", "required key is missing")
    workflows_raw = block["workflows"]
    if not isinstance(workflows_raw, list) or not workflows_raw:
        raise ConfigError(source, "ci.workflows", "expected a non-empty list of workflow paths")
    workflows = tuple(
        _require_str(source, f"ci.workflows[{i}]", wf) for i, wf in enumerate(workflows_raw)
    )

    if "aggregate_context" not in block:
        raise ConfigError(source, "ci.aggregate_context", "required key is missing")
    aggregate_context = _require_str(source, "ci.aggregate_context", block["aggregate_context"])

    required_checks = block.get("required_checks", "auto")
    if not isinstance(required_checks, str) or required_checks not in _CI_REQUIRED_CHECK_MODES:
        allowed = ", ".join(sorted(_CI_REQUIRED_CHECK_MODES))
        raise ConfigError(
            source,
            "ci.required_checks",
            f"expected one of: {allowed}",
        )

    aggregate_workflow = block.get("aggregate_workflow")
    if aggregate_workflow is not None:
        aggregate_workflow = _require_str(source, "ci.aggregate_workflow", aggregate_workflow)
        if aggregate_workflow not in workflows:
            raise ConfigError(
                source,
                "ci.aggregate_workflow",
                f"{aggregate_workflow!r} is not one of ci.workflows {list(workflows)}",
            )

    return CiCfg(
        workflows=workflows,
        aggregate_context=aggregate_context,
        aggregate_workflow=aggregate_workflow,
        required_checks=required_checks,
        source=source,
    )


_SECRETS_ALLOWED_KEYS = {"source", "profiles"}
_PUBLISH_SET_ALLOWED_KEYS = {"profile", "target", "map", "extra", "allow_roles"}
_TARGET_ALLOWED_KEYS = {"type", "name"}
_ITEM_ALLOWED_KEYS = {"secret", "variable"}
_EXTRA_ALLOWED_KEYS = {"from_file", "prompt", "value"}


def _parse_secrets(source: str, value: Any) -> SecretsCfg:
    """
    Validate the ``snowflake_secrets`` block into a :class:`SecretsCfg`.

    Requires a ``source`` path and an optional ``profiles`` map of named publish sets.
    Every failure is scoped to ``snowflake_secrets.<field>`` so the message points at the
    exact line; unknown keys are rejected.
    """
    block = _require_mapping(source, "snowflake_secrets", value)
    _reject_unknown(source, "snowflake_secrets", block, _SECRETS_ALLOWED_KEYS)

    if "source" not in block:
        raise ConfigError(source, "snowflake_secrets.source", "required key is missing")
    toml_source = _require_str(source, "snowflake_secrets.source", block["source"])

    profiles_raw = _require_mapping(
        source, "snowflake_secrets.profiles", block.get("profiles", {})
    )
    profiles = {
        name: _parse_publish_set(source, name, spec) for name, spec in profiles_raw.items()
    }
    return SecretsCfg(source=toml_source, profiles=profiles, source_file=source)


def _parse_publish_set(source: str, name: str, value: Any) -> PublishSet:
    """
    Validate one named publish set (``snowflake_secrets.profiles.<name>``).
    """
    field = f"snowflake_secrets.profiles.{name}"
    block = _require_mapping(source, field, value)
    _reject_unknown(source, field, block, _PUBLISH_SET_ALLOWED_KEYS)

    if "profile" not in block:
        raise ConfigError(source, f"{field}.profile", "required key is missing")
    profile = _require_str(source, f"{field}.profile", block["profile"])

    target = _parse_target(source, f"{field}.target", block.get("target"))
    mapped = _parse_map(source, f"{field}.map", block.get("map", {}))
    extra = _parse_extra(source, f"{field}.extra", block.get("extra", {}))
    allow_roles = _parse_allow_roles(source, f"{field}.allow_roles", block.get("allow_roles", []))

    if not mapped and not extra:
        raise ConfigError(source, field, "must publish at least one item (map or extra)")

    seen: Dict[str, str] = {}
    for gh_name in [m.gh_name for m in mapped] + [e.gh_name for e in extra]:
        if gh_name in seen:
            raise ConfigError(source, field, f"duplicate GitHub item name {gh_name!r}")
        seen[gh_name] = gh_name

    return PublishSet(
        name=name,
        profile=profile,
        target=target,
        mapped=mapped,
        extra=extra,
        allow_roles=allow_roles,
    )


def _parse_target(source: str, field: str, value: Any) -> TargetRef:
    """
    Validate a publish set's ``target`` (type + name).
    """
    if value is None:
        raise ConfigError(source, field, "required key is missing")
    block = _require_mapping(source, field, value)
    _reject_unknown(source, field, block, _TARGET_ALLOWED_KEYS)

    if "type" not in block:
        raise ConfigError(source, f"{field}.type", "required key is missing")
    type_raw = _require_str(source, f"{field}.type", block["type"])
    try:
        target_type = TargetType(type_raw)
    except ValueError:
        allowed = ", ".join(t.value for t in TargetType)
        raise ConfigError(source, f"{field}.type", f"expected one of: {allowed}")

    if "name" not in block:
        raise ConfigError(source, f"{field}.name", "required key is missing")
    target_name = _require_str(source, f"{field}.name", block["name"])
    return TargetRef(type=target_type, name=target_name)


def _parse_item_kind(source: str, field: str, value: Any) -> Tuple[str, "ItemKind"]:
    """
    Parse a ``{secret: NAME}`` or ``{variable: NAME}`` spec into ``(gh_name, kind)``.
    """
    block = _require_mapping(source, field, value)
    _reject_unknown(source, field, block, _ITEM_ALLOWED_KEYS)
    if len(block) != 1:
        raise ConfigError(source, field, "expected exactly one of: secret, variable")
    if "secret" in block:
        return _require_str(source, f"{field}.secret", block["secret"]), ItemKind.SECRET
    return _require_str(source, f"{field}.variable", block["variable"]), ItemKind.VARIABLE


def _parse_map(source: str, field: str, value: Any) -> Tuple[MappedField, ...]:
    """
    Validate the ``map`` block (connections.toml field -> GitHub secret/variable).
    """
    block = _require_mapping(source, field, value)
    items = []
    for toml_field, spec in block.items():
        gh_name, kind = _parse_item_kind(source, f"{field}.{toml_field}", spec)
        items.append(MappedField(toml_field=toml_field, gh_name=gh_name, kind=kind))
    return tuple(items)


def _parse_extra(source: str, field: str, value: Any) -> Tuple[ExtraItem, ...]:
    """
    Validate the ``extra`` block (values not in the connections.toml, always secrets).
    """
    block = _require_mapping(source, field, value)
    items = []
    for gh_name, spec in block.items():
        sub = f"{field}.{gh_name}"
        spec_map = _require_mapping(source, sub, spec)
        _reject_unknown(source, sub, spec_map, _EXTRA_ALLOWED_KEYS)
        if len(spec_map) != 1:
            raise ConfigError(source, sub, "expected exactly one of: from_file, prompt, value")
        if "from_file" in spec_map:
            ref = _require_str(source, f"{sub}.from_file", spec_map["from_file"])
            item_source = ExtraSource.FROM_FILE
        elif "value" in spec_map:
            ref = _require_str(source, f"{sub}.value", spec_map["value"])
            item_source = ExtraSource.VALUE
        else:
            if spec_map.get("prompt") is not True:
                raise ConfigError(source, f"{sub}.prompt", "expected the literal true")
            ref = None
            item_source = ExtraSource.PROMPT
        items.append(
            ExtraItem(gh_name=gh_name, kind=ItemKind.SECRET, source=item_source, ref=ref)
        )
    return tuple(items)


def _parse_allow_roles(source: str, field: str, value: Any) -> Tuple[str, ...]:
    """
    Validate the optional ``allow_roles`` list (H3 role allowlist for the publish set).
    """
    if not isinstance(value, list):
        raise ConfigError(source, field, "expected a list of role names")
    return tuple(_require_str(source, f"{field}[{i}]", role) for i, role in enumerate(value))
