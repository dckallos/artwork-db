"""
Publish a Snowflake connections profile to GitHub Environment secrets/variables.

This is the ``secrets publish`` capability (plan slice 3 / §12.2.4). It maps a parsed
``connections.toml`` profile plus a typed publish set onto GitHub Actions **secrets**
(write-only) and **variables** (readable) for the dbt CI layer, through the injected
:class:`~ghclient.gh.GhRunner` seam.

Design in one breath: a *pure* :func:`build_publish_plan` turns ``(profile, publish_set,
current GitHub state, mode)`` into a tuple of typed :class:`PublishItem`\\s (one per
secret/variable, each with an intended :class:`PublishAction`); :func:`run_publish` renders
that plan (dry-run by default) and, only under ``--apply``, executes exactly the required
``gh`` calls. Nothing here mutates on import.

Hard invariants:
  * **H8** -- a *secret*'s plan/preview shows its name, existence, and intended action only,
    never a value or value-diff; a *variable* (readable) may show an ``old -> new`` diff.
  * **H5** -- a secret value never reaches ``argv``, stdout, the preview, a log line, or an
    exception message. Values are resolved lazily at apply time and handed to ``gh`` via
    stdin (:meth:`GhRunner.run`'s ``input_text``); any diagnostic that could echo one is
    scrubbed with the value before it is surfaced.
  * **H3** -- the connection's role must be least-privilege: ``ACCOUNTADMIN`` is refused
    (override only via an explicit ``--allow-role``), a role absent from the publish-set
    allowlist is refused, an OAuth/session profile is never publishable as a credential,
    and a connection whose user equals the local OS user is refused as a personal identity.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Mapping, Optional, Set, Tuple, Union

from ._paths import quote_segment
from .config import ExtraItem, ExtraSource, GithubClientConfig, ItemKind, MappedField, PublishSet
from .connections import Profile, load_profile
from .errors import ConfigError, GhApiError, GhClientError
from .gh import GhResult, GhRunner

__all__ = [
    "PublishAction",
    "PublishMode",
    "PublishItem",
    "assert_ci_identity",
    "build_publish_plan",
    "run_publish",
]

# Roles that must never back a CI identity regardless of the config allowlist; only an
# explicit ``--allow-role`` override (allow_roles_override) may unlock ACCOUNTADMIN (H3).
_FORBIDDEN_ROLES: Tuple[str, ...] = ("ACCOUNTADMIN",)


class PublishAction(Enum):
    """
    The intended effect on one GitHub item: create it, update it, skip it, or delete it.
    """

    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    DELETE = "delete"


@dataclass(frozen=True)
class PublishMode:
    """
    The overwrite/deletion policy for a publish run (H8 modes).

    ``no_overwrite`` (the default) never clobbers an existing item; ``force`` allows
    updates; ``delete_missing`` removes managed items no longer present in the mapping.
    ``force`` takes precedence over ``no_overwrite``.
    """

    no_overwrite: bool = True
    force: bool = False
    delete_missing: bool = False


@dataclass(frozen=True)
class PublishItem:
    """
    One planned change to a single GitHub secret or variable.

    ``value_preview`` is populated only for *variables* being created/updated (an
    ``old -> new`` string); it is **always** ``None`` for secrets so no secret value can
    ride along in the plan (H8).
    """

    environment: str
    name: str
    kind: ItemKind
    action: PublishAction
    exists: bool
    value_preview: Optional[str] = None


# A publish item's value comes either from a mapped connections field or an extra item.
_Source = Union[MappedField, ExtraItem]
_Prompt = Callable[[str], str]
_FileReader = Callable[[str], str]


def _action_for(exists: bool, mode: PublishMode) -> PublishAction:
    """
    Decide create/update/skip for one item given its existence and the run mode.
    """
    if not exists:
        return PublishAction.CREATE
    if mode.force:
        return PublishAction.UPDATE
    return PublishAction.SKIP


def build_publish_plan(
    profile: Profile,
    publish_set: PublishSet,
    *,
    existing_secrets: Set[str],
    existing_variables: Mapping[str, str],
    mode: PublishMode,
    environment: Optional[str] = None,
) -> Tuple[PublishItem, ...]:
    """
    Build the typed publish plan from a profile, a publish set, and current GitHub state.

    Pure and side-effect-free: it reads no disk and calls no ``gh``. ``existing_secrets`` is
    the set of secret *names* that already exist (values are unreadable, hence a set);
    ``existing_variables`` maps existing variable name to its current value (readable, so a
    diff is possible). ``environment`` overrides the publish set's target when given (the
    ``--env`` flag). Secret items never carry a value (H8).
    """
    env = environment or publish_set.target.name
    items: List[PublishItem] = []
    managed_secrets: Set[str] = set()
    managed_variables: Set[str] = set()

    for mapped in publish_set.mapped:
        name = mapped.gh_name
        if mapped.kind is ItemKind.SECRET:
            managed_secrets.add(name)
            exists = name in existing_secrets
        else:
            managed_variables.add(name)
            exists = name in existing_variables
        action = _action_for(exists, mode)
        preview: Optional[str] = None
        if mapped.kind is ItemKind.VARIABLE and action in (PublishAction.CREATE, PublishAction.UPDATE):
            # Variables are readable and non-secret, so an old -> new diff is safe (H8).
            new_value = profile.require(mapped.toml_field)
            old_value = existing_variables.get(name)
            preview = f"{old_value!r} -> {new_value!r}"
        items.append(PublishItem(env, name, mapped.kind, action, exists, preview))

    for extra in publish_set.extra:
        # Extra items are always secrets (key material / passphrases): no value in the plan.
        name = extra.gh_name
        managed_secrets.add(name)
        exists = name in existing_secrets
        items.append(PublishItem(env, name, ItemKind.SECRET, _action_for(exists, mode), exists, None))

    if mode.delete_missing:
        for name in sorted(set(existing_secrets) - managed_secrets):
            items.append(PublishItem(env, name, ItemKind.SECRET, PublishAction.DELETE, True, None))
        for name in sorted(set(existing_variables) - managed_variables):
            items.append(PublishItem(env, name, ItemKind.VARIABLE, PublishAction.DELETE, True, None))

    return tuple(items)


def assert_ci_identity(
    profile: Profile,
    publish_set: PublishSet,
    *,
    allow_roles_override: Tuple[str, ...] = (),
    local_user: Optional[str] = None,
) -> None:
    """
    Enforce the H3 least-privilege CI-identity rules or raise :class:`GhClientError`.

    Refuses: an OAuth/session profile (no durable key pair), a profile with no ``role``,
    ``ACCOUNTADMIN`` (unless named in ``allow_roles_override`` via ``--allow-role``), a role
    absent from the publish-set allowlist, and a connection ``user`` equal to ``local_user``
    (a personal/interactive identity, not a dedicated CI service account).
    """
    if profile.is_session_only():
        raise GhClientError(
            f"connections profile {profile.name!r} is OAuth/session (no key pair); "
            "refuse to publish an ephemeral token as a durable CI credential (H3)"
        )
    role = profile.role
    if role is None:
        raise GhClientError(
            f"connections profile {profile.name!r} has no 'role'; refuse to publish a "
            "credential without an explicit least-privilege role (H3)"
        )

    override_upper = {r.upper() for r in allow_roles_override}
    allow_upper = {r.upper() for r in publish_set.allow_roles} | override_upper
    role_upper = role.upper()

    if role_upper in {r.upper() for r in _FORBIDDEN_ROLES} and role_upper not in override_upper:
        raise GhClientError(
            f"role {role!r} is forbidden as a CI identity (H3); "
            f"pass --allow-role {role} only if this is a deliberate, reviewed exception"
        )
    if role_upper not in allow_upper:
        allowed = ", ".join(sorted(allow_upper)) or "(none)"
        raise GhClientError(
            f"role {role!r} is not in the publish-set allowlist [{allowed}] (H3); "
            f"add it to allow_roles in config or pass --allow-role {role}"
        )

    if local_user and profile.user and profile.user.strip().lower() == local_user.strip().lower():
        raise GhClientError(
            f"connection user {profile.user!r} equals the local OS user; refuse to publish a "
            "personal/interactive identity as the CI service user -- use a dedicated CI user (H3)"
        )


def _read_file(path: str) -> str:
    """
    Read a value file (e.g. a private key) in full, at apply time only.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _default_prompt(name: str) -> str:
    """
    Prompt interactively for a secret value without echoing it to the terminal.
    """
    import getpass

    return getpass.getpass(f"Value for {name}: ")


def _resolve_value(
    profile: Profile,
    source: _Source,
    *,
    prompt: Optional[_Prompt] = None,
    file_reader: Optional[_FileReader] = None,
) -> str:
    """
    Resolve the concrete value for an item at apply time (never at plan/preview time).

    The returned value is handed straight to ``gh`` via stdin and never stored on an item,
    logged, or placed in an exception; a missing key file raises a path-scoped
    :class:`ConfigError` that names the file, not the value (H5).
    """
    if isinstance(source, MappedField):
        return profile.require(source.toml_field)
    if source.source is ExtraSource.VALUE:
        return source.ref or ""
    if source.source is ExtraSource.FROM_FILE:
        path = os.path.expanduser(source.ref or "")
        reader = file_reader or _read_file
        try:
            return reader(path)
        except OSError:
            raise ConfigError(path, source.gh_name, "value file not found or unreadable") from None
    ask = prompt or _default_prompt
    return ask(source.gh_name)


def _gh_verb(kind: ItemKind) -> str:
    """
    Map an item kind to its ``gh`` subcommand noun (``secret`` or ``variable``).
    """
    return "secret" if kind is ItemKind.SECRET else "variable"


def _check(result: GhResult, *, value: Optional[str]) -> None:
    """
    Raise a redacted :class:`GhApiError` when a ``gh`` mutation failed.

    ``value`` (when given) is scrubbed from the captured stderr before it is placed on the
    exception, so a secret can never leak through an error path (H5). The argv itself never
    contains the value (it is passed on stdin), so echoing it is safe.
    """
    if result.ok:
        return
    stderr = result.stderr or ""
    if value:
        stderr = stderr.replace(value, "[REDACTED]")
    raise GhApiError(
        f"gh exited {result.returncode} (status {result.status_code}): {stderr.strip()}",
        status_code=result.status_code,
        stderr=stderr,
    )


def _list_secret_names(runner: GhRunner, repo: str, env: str) -> Tuple[Optional[Set[str]], GhResult]:
    """
    List existing secret *names* for an environment (values are never returned by GitHub).
    """
    res = runner.run(["secret", "list", "--env", env, "--repo", repo, "--json", "name"])
    if not res.ok:
        return None, res
    rows = json.loads(res.stdout or "[]")
    return {row["name"] for row in rows}, res


def _list_variables(runner: GhRunner, repo: str, env: str) -> Tuple[Optional[Dict[str, str]], GhResult]:
    """
    List existing variables (name + readable value) for an environment.
    """
    res = runner.run(["variable", "list", "--env", env, "--repo", repo, "--json", "name,value"])
    if not res.ok:
        return None, res
    rows = json.loads(res.stdout or "[]")
    return {row["name"]: row.get("value", "") for row in rows}, res


def _render_item(item: PublishItem, repo: str) -> List[str]:
    """
    Render one plan line (and the redacted ``gh`` command shape) for the preview.
    """
    line = f"  [{item.action.value}] {item.environment}/{item.name} ({item.kind.value})"
    if (
        item.kind is ItemKind.VARIABLE
        and item.value_preview
        and item.action in (PublishAction.CREATE, PublishAction.UPDATE)
    ):
        line += f"  {item.value_preview}"
    out = [line]
    verb = _gh_verb(item.kind)
    if item.action in (PublishAction.CREATE, PublishAction.UPDATE):
        suffix = "[REDACTED]" if item.kind is ItemKind.SECRET else "shown above"
        out.append(f"      $ gh {verb} set {item.name} --env {item.environment} --repo {repo}   (value via stdin: {suffix})")
    elif item.action is PublishAction.DELETE:
        out.append(f"      $ gh {verb} delete {item.name} --env {item.environment} --repo {repo}")
    return out


def run_publish(
    runner: GhRunner,
    cfg: GithubClientConfig,
    *,
    profile_set: str,
    env: Optional[str] = None,
    apply: bool = False,
    no_overwrite: bool = True,
    force: bool = False,
    delete_missing: bool = False,
    allow_roles: Tuple[str, ...] = (),
    local_user: Optional[str] = None,
    prompt: Optional[_Prompt] = None,
    file_reader: Optional[_FileReader] = None,
) -> Tuple[int, List[str]]:
    """
    Plan (and, under ``apply``, execute) a secrets/variables publish for one publish set.

    Returns ``(exit_code, lines)``. Dry-run is the default: it verifies the environment
    exists, reads current GitHub state, and prints the full plan without mutating anything.
    ``--apply`` executes exactly the create/update/delete calls in the plan, passing every
    value on stdin (H5). A partial failure reports what was applied, returns a non-zero
    code, and never leaks a value.
    """
    lines: List[str] = []

    try:
        if cfg.secrets is None:
            return 1, ["secrets publish: no 'snowflake_secrets' block is configured"]
        publish_set = cfg.secrets.get(profile_set)
        target_env = env or publish_set.target.name
        profile = load_profile(cfg.secrets.source, publish_set.profile)
        assert_ci_identity(
            profile,
            publish_set,
            allow_roles_override=tuple(allow_roles),
            local_user=local_user,
        )
    except GhClientError as exc:
        return 1, [f"secrets publish: {exc}"]

    repo = cfg.repo

    # Environment existence precheck: we build (and own) the encoding here, so a name that
    # needs percent-encoding is handled safely and a missing environment fails fast (H5).
    pre = runner.api(f"repos/{repo}/environments/{quote_segment(target_env)}")
    if not pre.ok:
        if pre.status_code == 404:
            return 1, [
                f"secrets publish: environment {target_env!r} not found in {repo}; "
                "create the GitHub Environment before publishing into it (§12.2.8)"
            ]
        return 1, [
            f"secrets publish: cannot verify environment {target_env!r} in {repo} "
            f"(gh status {pre.status_code}, rc {pre.returncode})"
        ]

    secrets_names, sres = _list_secret_names(runner, repo, target_env)
    if secrets_names is None:
        return 1, [
            f"secrets publish: cannot list secrets for env {target_env!r} "
            f"(gh status {sres.status_code}, rc {sres.returncode})"
        ]
    variables, vres = _list_variables(runner, repo, target_env)
    if variables is None:
        return 1, [
            f"secrets publish: cannot list variables for env {target_env!r} "
            f"(gh status {vres.status_code}, rc {vres.returncode})"
        ]

    mode = PublishMode(no_overwrite=not force, force=force, delete_missing=delete_missing)
    items = build_publish_plan(
        profile,
        publish_set,
        existing_secrets=secrets_names,
        existing_variables=variables,
        mode=mode,
        environment=target_env,
    )

    header = "APPLY" if apply else "DRY-RUN (no changes; pass --apply to execute)"
    lines.append(f"secrets publish: set={profile_set} repo={repo} env={target_env} [{header}]")
    for item in items:
        lines.extend(_render_item(item, repo))

    if not apply:
        return 0, lines

    sources: Dict[str, _Source] = {m.gh_name: m for m in publish_set.mapped}
    sources.update({e.gh_name: e for e in publish_set.extra})

    exit_code = 0
    for item in items:
        if item.action is PublishAction.SKIP:
            continue
        verb = _gh_verb(item.kind)
        try:
            if item.action is PublishAction.DELETE:
                _check(
                    runner.run([verb, "delete", item.name, "--env", target_env, "--repo", repo]),
                    value=None,
                )
                lines.append(f"  [deleted] {target_env}/{item.name} ({item.kind.value})")
                continue
            value = _resolve_value(profile, sources[item.name], prompt=prompt, file_reader=file_reader)
            _check(
                runner.run(
                    [verb, "set", item.name, "--env", target_env, "--repo", repo],
                    input_text=value,
                ),
                value=value,
            )
            lines.append(f"  [{item.action.value}d] {target_env}/{item.name} ({item.kind.value})")
        except GhClientError as exc:
            # ``exc`` is already redacted by _resolve_value / _check.
            lines.append(f"  [FAILED] {target_env}/{item.name} ({item.kind.value}): {exc}")
            lines.append("secrets publish: aborted after failure; items listed above were applied")
            exit_code = 1
            break

    return exit_code, lines
