#!/usr/bin/env python3
"""Create local Snowflake CLI profiles used by ghclient secrets publish.

Dry-run by default. With --apply, this script:
  * copies the transformer private key to staging/prod CI key paths, chmod 600;
  * backs up ~/.snowflake/connections.toml;
  * upserts [artwork_ci_staging] and [artwork_ci_prod] profiles.

It never prints key contents.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class CiProfile:
    name: str
    key_path: Path
    warehouse: str


def expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()


def quote_toml(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def profile_block(name: str, fields: Mapping[str, str]) -> str:
    lines = [f"[{name}]"]
    for key, value in fields.items():
        lines.append(f"{key} = {quote_toml(value)}")
    return "\n".join(lines) + "\n"


def upsert_profile(text: str, name: str, fields: Mapping[str, str]) -> str:
    block = profile_block(name, fields)
    pattern = re.compile(rf"(?ms)^\[{re.escape(name)}\]\n.*?(?=^\[|\Z)")
    if pattern.search(text):
        return pattern.sub(block + "\n", text).rstrip() + "\n"
    return text.rstrip() + "\n\n" + block


def install_key(source: Path, target: Path, *, apply: bool) -> None:
    if not source.is_file():
        raise SystemExit(f"source transformer key does not exist: {source}")
    print(f"{'copy' if apply else 'would copy'} {source} -> {target}")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)


def run_test(profile: str) -> int:
    print(f"testing snow connection: {profile}")
    return subprocess.call(["snow", "connection", "test", "--connection", profile])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write files; default is dry-run")
    parser.add_argument("--test", action="store_true", help="run snow connection test after apply")
    parser.add_argument("--connections", default="~/.snowflake/connections.toml")
    parser.add_argument("--profile", default="kw94245", help="base local profile label")
    parser.add_argument("--account", default="DSHXYWJ-KW94245")
    parser.add_argument("--database", default="ARTWORK_DB")
    parser.add_argument("--user", default="ARTWORK_TRANSFORMER_SVC")
    parser.add_argument("--role", default="ARTWORK_TRANSFORMER")
    parser.add_argument("--source-key", default="~/.snowflake/keys/kw94245_transformer_rsa_key.p8")
    parser.add_argument("--staging-profile", default="artwork_ci_staging")
    parser.add_argument("--prod-profile", default="artwork_ci_prod")
    parser.add_argument("--staging-key", default="~/.snowflake/keys/staging_ci.p8")
    parser.add_argument("--prod-key", default="~/.snowflake/keys/prod_ci.p8")
    parser.add_argument("--staging-warehouse", default="ARTWORK_WH_STAGING")
    parser.add_argument("--prod-warehouse", default="ARTWORK_WH_PROD")
    args = parser.parse_args(argv)

    connections = expand(args.connections)
    source_key = expand(args.source_key.replace("kw94245", args.profile)) if args.source_key == "~/.snowflake/keys/kw94245_transformer_rsa_key.p8" else expand(args.source_key)
    profiles = [
        CiProfile(args.staging_profile, expand(args.staging_key), args.staging_warehouse),
        CiProfile(args.prod_profile, expand(args.prod_key), args.prod_warehouse),
    ]

    print("Snowflake CI profile plan")
    print(f"  connections.toml: {connections}")
    print(f"  account:          {args.account}")
    print(f"  user/role:        {args.user} / {args.role}")
    print(f"  database:         {args.database}")
    print(f"  source key:       {source_key}")
    print(f"  mode:             {'APPLY' if args.apply else 'DRY-RUN'}")

    for profile in profiles:
        install_key(source_key, profile.key_path, apply=args.apply)

    text = connections.read_text() if connections.exists() else ""
    for profile in profiles:
        fields = {
            "account": args.account,
            "user": args.user,
            "role": args.role,
            "warehouse": profile.warehouse,
            "database": args.database,
            "authenticator": "SNOWFLAKE_JWT",
            "private_key_path": str(profile.key_path),
        }
        print(f"{'upsert' if args.apply else 'would upsert'} [{profile.name}] warehouse={profile.warehouse}")
        text = upsert_profile(text, profile.name, fields)

    if not args.apply:
        print("dry-run: nothing changed; re-run with --apply to write profiles")
        return 0

    connections.parent.mkdir(parents=True, exist_ok=True)
    if connections.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = connections.with_name(connections.name + f".bak.{stamp}")
        shutil.copy2(connections, backup)
        print(f"backup: {backup}")
    connections.write_text(text.lstrip())
    connections.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"wrote {connections}")

    if args.test:
        failures = sum(run_test(profile.name) != 0 for profile in profiles)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
