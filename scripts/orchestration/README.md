# `scripts/orchestration/`

Launch and health-check scripts for the local Dagster control plane that orchestrates
the artwork-db data lifecycle (extraction assets + dbt transforms).

All scripts are Bash, macOS-friendly, and share one environment contract:

- **Repo root** is resolved from the script location (`scripts/orchestration/../..`).
- **Venv** is expected at `<repo>/.venv` (created by `bootstrap_dagster.sh`).
- **`DAGSTER_HOME`** defaults to `<repo>/orchestration/dagster_home` and holds the SQLite
  run storage, run queue, `dagster.yaml`, and `workspace.yaml`.
- **`.env`** at the repo root is sourced (Snowflake key-pair / dbt vars) before launch.
- The dbt **manifest** (`artwork_pipeline/target/manifest.json`) is built with `dbt parse`
  once in the parent process before Dagster loads the code location — this avoids the
  dbt-fusion `dbt deps` race documented in `orchestration/artwork_orchestration/resources.py`.

---

## Quick start

```bash
# 1. One-time setup: venv, deps, dbt deps.
bash scripts/orchestration/bootstrap_dagster.sh

# 2a. Single-machine dev (UI + daemon on localhost only):
bash scripts/orchestration/run_dagster_dev.sh          # http://localhost:3000

# 2b. OR expose the UI to the LAN (webserver + daemon, split):
bash scripts/orchestration/run_dagster_stack.sh        # background both, prints LAN URL

# 3. Anytime: verify the setup is healthy.
bash scripts/orchestration/doctor_orchestration.sh
```

> The sandbox/workspace mount may strip the executable bit. If `./script.sh` fails with
> "permission denied", either `chmod +x scripts/orchestration/*.sh` locally or invoke via
> `bash <script>` as shown above.

---

## Which script do I run?

| Goal | Script | Processes | Bind | Terminals |
|------|--------|-----------|------|-----------|
| Local dev, one machine | `run_dagster_dev.sh` | UI + daemon (`dagster dev`) | localhost | 1 (foreground) |
| Dashboard reachable from other machines, hands-off | `run_dagster_stack.sh` | webserver + daemon (background) | `0.0.0.0` | 1 (returns prompt) |
| Same, but want each process in its own tab | `run_dagster_webserver.sh` + `run_dagster_daemon.sh` | webserver, daemon (foreground) | `0.0.0.0` | 2 |
| One-time install | `bootstrap_dagster.sh` | — | — | — |
| Health check | `doctor_orchestration.sh` | — | — | — |

**Why the split?** `dagster.yaml` uses the `QueuedRunCoordinator`: the **webserver only
enqueues** runs; the **daemon dequeues and launches** them (and ticks schedules/sensors).
So whenever you run the webserver, a daemon must also be running or nothing executes.
Run only **one daemon** per deployment (multiple webservers are fine).

---

## Scripts

### `bootstrap_dagster.sh`
One-time setup. Creates `.venv`, upgrades pip, installs `requirements.txt` + the editable
`orchestration` package (Dagster + dagster-dbt), and runs `dbt deps`.

### `doctor_orchestration.sh`
Non-destructive sanity check: venv active, `dbt`/`dagster` present, manifest present,
`dbt debug` connects on the `dev` target, and `artwork_orchestration.definitions` imports
cleanly (prints asset/job/check counts). Exits non-zero on failure.

### `run_dagster_dev.sh`
The single-machine all-in-one (`dagster dev -m artwork_orchestration.definitions`): UI +
daemon on `localhost:3000`. Unchanged reference launcher — no LAN exposure.

### `run_dagster_webserver.sh`
Runs **only** `dagster-webserver`, bound to `0.0.0.0` (LAN-accessible), loading the code
location from `$DAGSTER_HOME/workspace.yaml`. Authoritative manifest builder (always
`dbt parse`). Prints the LAN URL and candidate interface IPs.

```bash
bash scripts/orchestration/run_dagster_webserver.sh
# overrides:
DAGSTER_WEBSERVER_HOST=0.0.0.0 DAGSTER_WEBSERVER_PORT=3000 \
DAGSTER_ADVERTISE_IP=192.168.1.50 \
  bash scripts/orchestration/run_dagster_webserver.sh
```

### `run_dagster_daemon.sh`
Runs **only** `dagster-daemon run` (run queue + schedules + sensors), loading
`$DAGSTER_HOME/workspace.yaml`. Parses the dbt manifest **only if missing** so it never
races the webserver's parse. Start one per deployment.

### `run_dagster_stack.sh`
Convenience launcher: builds the manifest once, then starts the **daemon + webserver as
background processes**, writes logs and PID files under `$DAGSTER_HOME/logs/`, and returns
your prompt (close the terminal, it keeps running). Refuses to double-start. Prints the
exact `http://<LAN-IP>:<port>` to open from another machine.

```bash
bash scripts/orchestration/run_dagster_stack.sh
tail -f orchestration/dagster_home/logs/webserver.log orchestration/dagster_home/logs/daemon.log
```

### `run_dagster_stack_stop.sh`
Stops the background stack started by `run_dagster_stack.sh`: reads the PID files
(SIGTERM, then SIGKILL if a process lingers) and cleans them up.

### `_dagster_env.sh` (sourced helper — not executed)
Shared setup used by the webserver, daemon, and stack launchers so `DAGSTER_HOME`
resolution, `dagster.yaml`/`workspace.yaml` seeding, `.env` sourcing, and venv activation
stay identical across processes. Provides `dagster_env_setup`, `dagster_dbt_parse`,
`detect_lan_ip`, and `list_lan_ip_candidates`.

---

## Environment variables

| Variable | Default | Used by | Purpose |
|----------|---------|---------|---------|
| `DAGSTER_HOME` | `<repo>/orchestration/dagster_home` | all | Instance home (storage, run queue, config). |
| `DAGSTER_WEBSERVER_HOST` | `0.0.0.0` | webserver, stack | Bind address for the UI. |
| `DAGSTER_WEBSERVER_PORT` | `3000` | webserver, stack | UI port. |
| `DAGSTER_ADVERTISE_IP` | (auto-detected) | webserver, stack | Pin the IP printed in the "open from another Mac" URL when auto-detect picks the wrong interface (VPN, Wi-Fi on `en1`). |
| `SNOWFLAKE_*`, `DBT_*` | (from `.env`) | all | Snowflake key-pair / dbt auth for the `dev` target. |

---

## Security

Binding `0.0.0.0` exposes an **unauthenticated** Dagster UI to everything on your local
network. Only use the LAN launchers on a trusted network. Dagster OSS has no built-in
auth; put it behind a reverse proxy / VPN if you need access control.

---

## Troubleshooting

- **UI loads but runs stay "Queued"** — the daemon isn't running. Start
  `run_dagster_daemon.sh` (or use `run_dagster_stack.sh`).
- **"Open from another Mac" URL is blank/wrong** — set `DAGSTER_ADVERTISE_IP` to the right
  interface IP (the launcher prints candidates).
- **Can't reach the UI from another machine** — confirm both are on the same LAN, the
  macOS firewall allows inbound on the port, and you used the LAN IP (not `0.0.0.0`).
- **`dbt parse` warnings on launch** — check `.env` has the `SNOWFLAKE_*` key-pair vars;
  run `doctor_orchestration.sh` to confirm `dbt debug` connects.
- **Manifest / code location won't load** — `doctor_orchestration.sh` isolates whether the
  problem is dbt connectivity, a missing manifest, or a Python import error.
