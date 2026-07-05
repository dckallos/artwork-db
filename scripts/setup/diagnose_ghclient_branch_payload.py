#!/usr/bin/env python3
"""
Read-only ghclient branch-protection payload diagnosis.

This script imports the local ghclient package, computes the branch-protection
payload that ghclient would send for a full PUT, and prints deterministic payload
variants. It performs no network calls and cannot apply GitHub changes.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gh[oprsu]_[A-Za-z0-9_]+"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
)


def redact(text: str) -> str:
    out = text
    for pat in TOKEN_PATTERNS:
        out = pat.sub("<REDACTED_TOKEN>", out)
    out = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "-----PRIVATE KEY REDACTED-----",
        out,
        flags=re.DOTALL,
    )
    return out


def eprint(msg: str = "") -> None:
    print(redact(msg), file=sys.stderr)


def print_json(label: str, obj: Any) -> None:
    print(f"\n== {label} ==")
    print(redact(json.dumps(obj, indent=2, sort_keys=True)))


def run_git_root(start: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).resolve()
    return None


def infer_repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    cwd = Path.cwd().resolve()
    git_root = run_git_root(cwd)
    if git_root is not None:
        return git_root
    # Fallback for running the script from scripts/setup in an extracted zip.
    return Path(__file__).resolve().parents[2]


def contexts_from_rsc(rsc: Any) -> list[str]:
    contexts: list[str] = []
    if not isinstance(rsc, dict):
        return contexts
    for ctx in rsc.get("contexts") or []:
        if isinstance(ctx, str):
            contexts.append(ctx)
    for chk in rsc.get("checks") or []:
        if isinstance(chk, dict) and isinstance(chk.get("context"), str):
            contexts.append(chk["context"])
    return list(dict.fromkeys(contexts))


def checks_from_rsc(rsc: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if isinstance(rsc, dict):
        for chk in rsc.get("checks") or []:
            if isinstance(chk, dict) and isinstance(chk.get("context"), str):
                item: dict[str, Any] = {"context": chk["context"]}
                if isinstance(chk.get("app_id"), int):
                    item["app_id"] = chk["app_id"]
                else:
                    item["app_id"] = -1
                checks.append(item)
        if checks:
            return checks
    return [{"context": ctx, "app_id": -1} for ctx in contexts_from_rsc(rsc)]


def rsc_strict(rsc: Any) -> bool:
    return bool(rsc.get("strict", True)) if isinstance(rsc, dict) else True


def variant_contexts_only(body: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(body)
    rsc = out.get("required_status_checks")
    if isinstance(rsc, dict):
        out["required_status_checks"] = {
            "strict": rsc_strict(rsc),
            "contexts": contexts_from_rsc(rsc),
        }
    return out


def variant_checks_only(body: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(body)
    rsc = out.get("required_status_checks")
    if isinstance(rsc, dict):
        out["required_status_checks"] = {
            "strict": rsc_strict(rsc),
            "checks": checks_from_rsc(rsc),
        }
    return out


def variant_status_checks_patch(body: dict[str, Any]) -> dict[str, Any]:
    rsc = body.get("required_status_checks")
    if not isinstance(rsc, dict):
        return {"strict": True, "contexts": []}
    return {
        "strict": rsc_strict(rsc),
        "checks": checks_from_rsc(rsc),
        "contexts": [],
    }


def variant_rsc_null(body: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(body)
    out["required_status_checks"] = None
    return out


def full_put_shape_findings(payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    required_top = [
        "required_status_checks",
        "enforce_admins",
        "required_pull_request_reviews",
        "restrictions",
    ]
    missing = [key for key in required_top if key not in payload]
    if missing:
        findings.append(f"ERROR: full PUT payload missing required top-level key(s): {missing}")
    rsc = payload.get("required_status_checks")
    if rsc is None:
        findings.append("INFO: required_status_checks=null disables required checks.")
    elif not isinstance(rsc, dict):
        findings.append("ERROR: required_status_checks must be an object or null.")
    else:
        has_contexts_key = "contexts" in rsc
        has_checks_key = "checks" in rsc
        if has_contexts_key and has_checks_key:
            findings.append(
                "LIKELY_INVALID_FULL_PUT: required_status_checks contains both contexts and checks; "
                "the captured GitHub 422 reported a oneOf/anyOf schema conflict for exactly this shape."
            )
        if not has_contexts_key and not has_checks_key:
            findings.append("ERROR: required_status_checks has neither contexts nor checks.")
        if has_contexts_key and not isinstance(rsc.get("contexts"), list):
            findings.append("ERROR: contexts must be an array when present.")
        if has_checks_key and not isinstance(rsc.get("checks"), list):
            findings.append("ERROR: checks must be an array when present.")
        if has_checks_key and not has_contexts_key:
            findings.append(
                "AMBIGUOUS_FULL_PUT: checks-only preserves app_id, but current docs still describe contexts as required; "
                "verify empirically before using for full PUT."
            )
        if has_contexts_key and not has_checks_key:
            findings.append("LIKELY_SAFE_FULL_PUT: contexts-only is the conservative full branch-protection PUT shape.")
    return findings



def status_checks_patch_findings(payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if "strict" in payload and not isinstance(payload.get("strict"), bool):
        findings.append("ERROR: strict must be boolean when present.")
    has_contexts_key = "contexts" in payload
    has_checks_key = "checks" in payload
    if not has_contexts_key and not has_checks_key:
        findings.append("ERROR: status-checks PATCH has neither contexts nor checks.")
    if has_contexts_key and not isinstance(payload.get("contexts"), list):
        findings.append("ERROR: contexts must be an array when present.")
    if has_checks_key:
        checks = payload.get("checks")
        if not isinstance(checks, list):
            findings.append("ERROR: checks must be an array when present.")
        else:
            for check in checks:
                if not isinstance(check, dict) or not isinstance(check.get("context"), str):
                    findings.append("ERROR: every check must be an object with a string context.")
                    break
        findings.append("LIKELY_SAFE_PATCH: required-status-checks PATCH documents checks[].app_id, including app_id=-1.")
    elif has_contexts_key:
        findings.append("LIKELY_SAFE_PATCH: contexts-only PATCH is the legacy documented shape.")
    return findings

def write_variants(out_dir: Path, variants: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in variants.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path}")


def load_current_body(repo_root: Path, branch: str) -> tuple[dict[str, Any], str, Path]:
    sys.path.insert(0, str(repo_root / "tools" / "github"))
    from ghclient import branch_protection as bp  # type: ignore
    from ghclient.config import default_config_path, load_config  # type: ignore

    config_path = default_config_path()
    cfg = load_config(config_path)
    policy = cfg.branch_protection.get(branch)
    body = bp.policy_body_for_apply(cfg, policy)
    return body, cfg.repo, config_path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", help="Path to artwork-db checkout; defaults to git root/current script root.")
    parser.add_argument("--branch", default="main", help="Protected branch configured in ghclient; default: main.")
    parser.add_argument("--out-dir", help="Optional local directory for JSON variant files. No network calls are made.")
    parser.add_argument("--quiet-json", action="store_true", help="Print only the final machine-readable summary JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = infer_repo_root(args.repo_root)
    result: dict[str, Any] = {
        "script": Path(__file__).name,
        "repo_root": str(repo_root),
        "branch": args.branch,
        "network": "none",
        "mutates_github": False,
    }

    try:
        current_body, repo_slug, config_path = load_current_body(repo_root, args.branch)
    except Exception as exc:  # noqa: BLE001 - diagnostic script must render actionable errors.
        result["ok"] = False
        result["error"] = redact(f"{type(exc).__name__}: {exc}")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    variants = {
        "ghclient-current-full-put": current_body,
        "candidate-full-put-contexts-only": variant_contexts_only(current_body),
        "candidate-full-put-checks-only": variant_checks_only(current_body),
        "candidate-status-checks-patch": variant_status_checks_patch(current_body),
        "diagnostic-full-put-required-status-checks-null": variant_rsc_null(current_body),
    }
    findings = {}
    for name, obj in variants.items():
        if name == "candidate-status-checks-patch" and isinstance(obj, dict):
            findings[name] = status_checks_patch_findings(obj)
        elif isinstance(obj, dict):
            findings[name] = full_put_shape_findings(obj)
        else:
            findings[name] = []
    likely_invalid_current = any("LIKELY_INVALID_FULL_PUT" in item for item in findings["ghclient-current-full-put"])

    result.update(
        {
            "ok": True,
            "repo": repo_slug,
            "config_path": str(config_path),
            "likely_invalid_current_full_put": likely_invalid_current,
            "variants": variants,
            "findings": findings,
        }
    )

    if args.out_dir:
        write_variants(Path(args.out_dir).expanduser().resolve(), variants)

    if args.quiet_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("ghclient branch-protection payload diagnosis")
        print(f"  repo_root: {repo_root}")
        print(f"  config:    {config_path}")
        print(f"  repo:      {repo_slug}")
        print(f"  branch:    {args.branch}")
        print("  network:   none")
        print("  mutation:  none")
        for name, obj in variants.items():
            print_json(name, obj)
            for finding in findings[name]:
                print(f"  - {finding}")
        print("\nSummary:")
        if likely_invalid_current:
            print("  CURRENT_FULL_PUT_LIKELY_INVALID: yes")
            print("  recommended next code change: separate full PUT payloads from status-check PATCH payloads")
        else:
            print("  CURRENT_FULL_PUT_LIKELY_INVALID: no")

    return 10 if likely_invalid_current else 0


if __name__ == "__main__":
    raise SystemExit(main())
