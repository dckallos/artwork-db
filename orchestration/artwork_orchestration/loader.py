"""ConfigLoader: parse + VALIDATE YAML into the typed in-memory model.

Two entry points:

* :func:`load_framework_config` -> :class:`~artwork_orchestration.model.FrameworkConfig`
  from ``framework.yaml`` (Layer A -- the internal engine config).
* :func:`load_source_specs` -> a list of :class:`~artwork_orchestration.spec.SourceSpec`
  built by SCANNING ``sources/*.yaml`` (Layer B -- the dead-simple user files). No source
  is ever named in Python: the registry is the directory listing, sorted by key.

Every value that looks like ``${ENV_VAR:default}`` is resolved from the environment, so
env-var NAMES live in YAML and never in framework ``.py``. Validation is two-layered:
an optional JSON Schema pass (only if ``jsonschema`` is importable) followed by semantic
checks that raise :class:`ConfigError` with a file/step/field-scoped, actionable message.
"""
from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

from .model import (
    BatchingCfg,
    BronzeCfg,
    ConnectionCfg,
    DefaultsCfg,
    FrameworkConfig,
    FreshnessCfg,
    RateLimitCfg,
    RetryCfg,
    TagsCfg,
    TimeoutsCfg,
)
from .spec import (
    ExtractionStep,
    HealthCheck,
    PartitionDim,
    Produces,
    SourceSpec,
)

# ---------------------------------------------------------------------------
# Paths (computed from this file so importing never triggers the sources package
# __init__ -- that is what keeps loader <-> sources import-cycle-free).
# ---------------------------------------------------------------------------
_PKG_DIR = Path(__file__).resolve().parent
FRAMEWORK_YAML = _PKG_DIR / "framework.yaml"
SOURCES_DIR = _PKG_DIR / "sources"
SCHEMAS_DIR = _PKG_DIR / "schemas"


class ConfigError(ValueError):
    """Raised on any invalid or malformed configuration, with an actionable message."""


# ---------------------------------------------------------------------------
# ${ENV_VAR:default} interpolation
# ---------------------------------------------------------------------------
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _interp(value: Any) -> Any:
    """Resolve ``${VAR}`` / ``${VAR:default}`` in strings; recurse into dicts/lists."""
    if isinstance(value, str):
        def repl(m: "re.Match[str]") -> str:
            name, default = m.group(1), m.group(2)
            return os.environ.get(name, default if default is not None else "")
        return _ENV_RE.sub(repl, value)
    if isinstance(value, Mapping):
        return {k: _interp(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interp(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Small typed getters with actionable errors
# ---------------------------------------------------------------------------
def _require(d: Mapping, key: str, where: str) -> Any:
    if not isinstance(d, Mapping) or key not in d:
        raise ConfigError(f"{where}: missing required key '{key}'.")
    return d[key]


def _as_int(v: Any, where: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ConfigError(f"{where}: expected an integer, got {v!r}.")


def _as_float(v: Any, where: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ConfigError(f"{where}: expected a number, got {v!r}.")


def _reject_unknown(d: Mapping, allowed: set, where: str) -> None:
    extra = set(d) - allowed
    if extra:
        raise ConfigError(
            f"{where}: unknown key(s) {sorted(extra)}. Allowed: {sorted(allowed)}. "
            "(Check for a typo -- see SCHEMA.md.)"
        )


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        return _interp(yaml.safe_load(path.read_text()) or {})
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: invalid YAML -- {exc}") from exc


# ---------------------------------------------------------------------------
# Optional JSON Schema validation (no hard dependency)
# ---------------------------------------------------------------------------
def _jsonschema_validate(instance: Any, schema_name: str, where: str) -> None:
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.exists():
        return
    try:
        import jsonschema  # type: ignore
    except Exception:  # noqa: BLE001 -- optional; semantic checks below still run
        return
    schema = json.loads(schema_path.read_text())
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ConfigError(f"{where}: schema violation at '{loc}': {exc.message}") from exc


# ===========================================================================
# Layer A -- framework.yaml
# ===========================================================================
@functools.lru_cache(maxsize=1)
def load_framework_config(path: Optional[str] = None) -> FrameworkConfig:
    """Parse + validate ``framework.yaml`` into a :class:`FrameworkConfig` (cached)."""
    p = Path(path) if path else FRAMEWORK_YAML
    raw = _read_yaml(p)
    where = p.name
    _jsonschema_validate(raw, "framework.schema.json", where)
    _reject_unknown(raw, {"connection", "bronze", "defaults", "tags", "freshness"}, where)

    conn = _require(raw, "connection", where)
    _reject_unknown(conn, {"profile", "target", "profiles_dir"}, f"{where}.connection")
    connection = ConnectionCfg(
        profile=str(_require(conn, "profile", f"{where}.connection")),
        target=str(_require(conn, "target", f"{where}.connection")),
        profiles_dir=str(_require(conn, "profiles_dir", f"{where}.connection")),
    )

    br = _require(raw, "bronze", where)
    _reject_unknown(br, {"database", "schema"}, f"{where}.bronze")
    bronze = BronzeCfg(
        database=str(_require(br, "database", f"{where}.bronze")),
        schema=str(_require(br, "schema", f"{where}.bronze")),
    )

    dfl = _require(raw, "defaults", where)
    _reject_unknown(dfl, {"retry", "timeouts_seconds", "batching", "rate_limit"}, f"{where}.defaults")

    rt = _require(dfl, "retry", f"{where}.defaults")
    _reject_unknown(rt, {"max_retries", "delay_seconds", "backoff", "jitter"}, f"{where}.defaults.retry")
    retry = RetryCfg(
        max_retries=_as_int(_require(rt, "max_retries", f"{where}.defaults.retry"), f"{where}.defaults.retry.max_retries"),
        delay_seconds=_as_int(_require(rt, "delay_seconds", f"{where}.defaults.retry"), f"{where}.defaults.retry.delay_seconds"),
        backoff=str(rt.get("backoff", "exponential")),
        jitter=str(rt.get("jitter", "plus_minus")),
    )

    to = _require(dfl, "timeouts_seconds", f"{where}.defaults")
    if "default" not in to:
        raise ConfigError(f"{where}.defaults.timeouts_seconds: missing required key 'default'.")
    timeouts = TimeoutsCfg(
        default=_as_int(to["default"], f"{where}.defaults.timeouts_seconds.default"),
        by_kind={k: _as_int(v, f"{where}.defaults.timeouts_seconds.{k}") for k, v in to.items() if k != "default"},
    )

    bt = _require(dfl, "batching", f"{where}.defaults")
    _reject_unknown(bt, {"size", "max_batches"}, f"{where}.defaults.batching")
    batching = BatchingCfg(
        size=_as_int(_require(bt, "size", f"{where}.defaults.batching"), f"{where}.defaults.batching.size"),
        max_batches=_as_int(_require(bt, "max_batches", f"{where}.defaults.batching"), f"{where}.defaults.batching.max_batches"),
    )

    rl = _require(dfl, "rate_limit", f"{where}.defaults")
    _reject_unknown(rl, {"rps_budget", "concurrency"}, f"{where}.defaults.rate_limit")
    rate_limit = RateLimitCfg(
        rps_budget=_as_float(_require(rl, "rps_budget", f"{where}.defaults.rate_limit"), f"{where}.defaults.rate_limit.rps_budget"),
        concurrency=_as_int(_require(rl, "concurrency", f"{where}.defaults.rate_limit"), f"{where}.defaults.rate_limit.concurrency"),
    )

    tg = _require(raw, "tags", where)
    _reject_unknown(tg, {"rate_limit_key", "max_runtime_key"}, f"{where}.tags")
    tags = TagsCfg(
        rate_limit_key=str(_require(tg, "rate_limit_key", f"{where}.tags")),
        max_runtime_key=str(_require(tg, "max_runtime_key", f"{where}.tags")),
    )

    fr = _require(raw, "freshness", where)
    _reject_unknown(fr, {"gold_marts", "gold_lag_hours"}, f"{where}.freshness")
    gold_marts = fr.get("gold_marts", []) or []
    if not isinstance(gold_marts, list):
        raise ConfigError(f"{where}.freshness.gold_marts: expected a list (or omit to auto-derive).")
    freshness = FreshnessCfg(
        gold_marts=[str(m) for m in gold_marts],
        gold_lag_hours=_as_float(fr.get("gold_lag_hours", 30), f"{where}.freshness.gold_lag_hours"),
    )

    return FrameworkConfig(
        connection=connection,
        bronze=bronze,
        defaults=DefaultsCfg(retry=retry, timeouts=timeouts, batching=batching, rate_limit=rate_limit),
        tags=tags,
        freshness=freshness,
    )


def reset_framework_cache() -> None:
    """Clear the :func:`load_framework_config` cache.

    ``load_framework_config`` is memoized (one framework.yaml per process), which is
    correct at runtime but awkward in tests that load alternate fixture configs. Call
    this in a fixture/teardown to force a fresh parse.
    """
    load_framework_config.cache_clear()


# ===========================================================================
# Layer B -- sources/<key>.yaml
# ===========================================================================
_EXPECT_OPS = {
    "==": lambda n, k: n == k,
    "!=": lambda n, k: n != k,
    ">=": lambda n, k: n >= k,
    "<=": lambda n, k: n <= k,
    ">": lambda n, k: n > k,
    "<": lambda n, k: n < k,
}
_EXPECT_RE = re.compile(r"^\s*(==|!=|>=|<=|>|<)\s*(-?\d+)\s*$")

_STEP_KEYS = {
    "name", "run", "kind", "timeout_seconds", "mode", "rate_limited", "api_bound",
    "static_args", "partition_by", "produces", "metadata_sql",
}
_PRODUCE_KEYS = {
    "table", "dbt_source", "internal", "physical", "check_nonempty", "severity", "fresh_within_days",
}
_CHECK_KEYS = {"name", "attach_table", "sql", "expect", "severity", "description"}
_SOURCE_KEYS = {"source", "cli_module", "rps_env_var", "rate_limit_value", "steps", "checks"}


def _compile_expect(expr: str, where: str):
    m = _EXPECT_RE.match(str(expr))
    if not m:
        raise ConfigError(
            f"{where}: invalid expect {expr!r}. Use a comparator and integer, "
            "e.g. \"== 0\", \"> 0\", \">= 100\"."
        )
    op, operand = m.group(1), int(m.group(2))
    fn = _EXPECT_OPS[op]
    return lambda n: fn(n, operand)


def _parse_produce(raw: Any, where: str) -> Produces:
    if isinstance(raw, str):
        # Shorthand: a bare table name is a dbt-source terminal.
        return Produces(table=raw, dbt_source=True)
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{where}: each 'produces' entry must be a table name or a mapping.")
    _reject_unknown(raw, _PRODUCE_KEYS, where)
    table = str(_require(raw, "table", where))
    internal = bool(raw.get("internal", False))
    # dbt_source defaults True (the common case) unless the table is marked internal.
    dbt_source = bool(raw.get("dbt_source", not internal))
    if internal and raw.get("dbt_source", False):
        raise ConfigError(f"{where}: a table cannot be both 'internal: true' and 'dbt_source: true'.")
    severity = str(raw.get("severity", "ERROR")).upper()
    if severity not in ("ERROR", "WARN"):
        raise ConfigError(f"{where}.severity: must be ERROR or WARN, got {severity!r}.")
    fresh = raw.get("fresh_within_days")
    return Produces(
        table=table,
        dbt_source=dbt_source,
        physical=(str(raw["physical"]) if raw.get("physical") else None),
        nonempty=bool(raw.get("check_nonempty", False)),
        nonempty_severity=severity,
        freshness_days=(_as_float(fresh, f"{where}.fresh_within_days") if fresh is not None else None),
    )


def _parse_partition(raw: Any, where: str) -> PartitionDim:
    _reject_unknown(raw, {"name", "cli_flag", "values"}, where)
    values = _require(raw, "values", where)
    if not isinstance(values, Mapping) or not values:
        raise ConfigError(f"{where}.values: expected a non-empty map of slug -> real value.")
    return PartitionDim(
        name=str(_require(raw, "name", where)),
        cli_flag=str(_require(raw, "cli_flag", where)),
        values={str(k): str(v) for k, v in values.items()},
    )


def _parse_step(raw: Mapping, timeouts: TimeoutsCfg, where: str) -> ExtractionStep:
    _reject_unknown(raw, _STEP_KEYS, where)
    name = str(_require(raw, "name", where))
    produces_raw = _require(raw, "produces", where)
    if not isinstance(produces_raw, list) or not produces_raw:
        raise ConfigError(f"{where}.produces: expected a non-empty list.")
    produces = tuple(_parse_produce(p, f"{where}.produces[{i}]") for i, p in enumerate(produces_raw))

    kind = str(raw.get("kind", "snapshot"))
    timeout_s = _as_int(raw["timeout_seconds"], f"{where}.timeout_seconds") if "timeout_seconds" in raw else timeouts.for_kind(kind)
    mode = str(raw.get("mode", "simple"))
    if mode not in ("simple", "batched"):
        raise ConfigError(f"{where}.mode: must be 'simple' or 'batched', got {mode!r}.")
    partition = _parse_partition(raw["partition_by"], f"{where}.partition_by") if raw.get("partition_by") else None
    static_args = tuple(str(a) for a in raw.get("static_args", ()))
    md = raw.get("metadata_sql", {}) or {}
    if not isinstance(md, Mapping):
        raise ConfigError(f"{where}.metadata_sql: expected a map of label -> SQL.")

    return ExtractionStep(
        name=name,
        produces=produces,
        subcommand=(str(raw["run"]) if raw.get("run") is not None else None),
        static_args=static_args,
        partition=partition,
        uses_batch_flags=(mode == "batched"),
        rate_limited=bool(raw.get("rate_limited", False)),
        api_bound=bool(raw.get("api_bound", True)),
        timeout_s=timeout_s,
        extra_metadata_sql={str(k): str(v) for k, v in md.items()},
    )


def _parse_check(raw: Mapping, where: str) -> HealthCheck:
    _reject_unknown(raw, _CHECK_KEYS, where)
    return HealthCheck(
        name=str(_require(raw, "name", where)),
        attach_table=str(_require(raw, "attach_table", where)),
        sql=str(_require(raw, "sql", where)),
        passes=_compile_expect(_require(raw, "expect", where), f"{where}.expect"),
        severity=str(raw.get("severity", "WARN")).upper(),
        description=str(raw.get("description", "")),
    )


def _parse_source(raw: Mapping, framework: FrameworkConfig, where: str) -> SourceSpec:
    _reject_unknown(raw, _SOURCE_KEYS, where)
    key = str(_require(raw, "source", where))
    steps_raw = _require(raw, "steps", where)
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ConfigError(f"{where}.steps: expected a non-empty list.")
    steps = tuple(_parse_step(s, framework.defaults.timeouts, f"{where}.steps[{i}] ({s.get('name', '?')})")
                  for i, s in enumerate(steps_raw))

    checks_raw = raw.get("checks", []) or []
    checks = tuple(_parse_check(c, f"{where}.checks[{i}]") for i, c in enumerate(checks_raw))

    spec = SourceSpec(
        key=key,
        cli_module=str(_require(raw, "cli_module", where)),
        steps=steps,
        checks=checks,
        rate_limit_value=(str(raw["rate_limit_value"]) if raw.get("rate_limit_value") else None),
        rps_env_var=str(raw.get("rps_env_var", "API_RPS")),
    )

    # --- Semantic validation (beyond structure) -------------------------------
    if not any(p.dbt_source for _s, p in spec.iter_produces()):
        raise ConfigError(
            f"{where}: source '{key}' has no dbt-source terminal table. At least one "
            "'produces' entry must be a dbt source (a bare table name, or dbt_source: true) "
            "so downstream dbt models keep their lineage."
        )
    for hc in spec.checks:
        if spec.find_produce(hc.attach_table) is None:
            raise ConfigError(
                f"{where}: check {hc.name!r} attaches to unknown table {hc.attach_table!r} "
                "(no step 'produces' it)."
            )
    return spec


def load_source_specs(sources_dir: Optional[str] = None) -> List[SourceSpec]:
    """Scan ``sources/*.yaml`` and build the registry, deterministically sorted by key.

    This IS the registry: there is no hardcoded list of sources anywhere in Python.
    """
    d = Path(sources_dir) if sources_dir else SOURCES_DIR
    framework = load_framework_config()
    files = sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml"))
    specs: Dict[str, Tuple[SourceSpec, Path]] = {}
    for f in files:
        raw = _read_yaml(f)
        _jsonschema_validate(raw, "source.schema.json", f.name)
        spec = _parse_source(raw, framework, f.name)
        if spec.key in specs:
            other = specs[spec.key][1].name
            raise ConfigError(f"duplicate source key {spec.key!r} in {f.name} and {other}.")
        specs[spec.key] = (spec, f)
    return [specs[k][0] for k in sorted(specs)]
