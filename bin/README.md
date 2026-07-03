# bin/

The classic **branch-protection governance** that used to live here (the
`apply` / `export` / `rollback` shell scripts and the `policy.*.json` bodies) has
been ported into the standalone `ghclient` package and **deleted** from `bin/`.

- Use it via `ghclient branch-protection apply|export|rollback` (dry-run by
  default; `--apply` to mutate) or the thin wrappers in
  `tools/github/wrappers/`.
- The desired-state policy is now `tools/github/policies/policy.main.json`
  (Model A: `main` only).
- Full move/removal record: `tools/github/CHANGELOG.md`.

## What remains here

- `check_no_attribution.sh` -- the authorship guard. Left in place intentionally;
  its hardening and relocation to `scripts/` are tracked under Area C (H7) and are
  out of scope for the branch-protection port.
