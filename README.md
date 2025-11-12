# Cross-Run Context Injection (Swarm + Codex)

Exploratory backend that learns lightweight workflow patterns from successful Codex runs, injects them into subsequent Swarm executions, and exposes a tiny HTTP API for your React UI.

## Why it’s fun already

- **Pattern memory** – Every successful run gets distilled into a `<reference_workflow>` block (max 12 steps + variables) that can be injected into the next Swarm task automatically.
- **One agent, one tool** – Swarm runner wraps a single `codex_exec` tool, so every action produces JSONL events, touched files, and artifacts you can replay in the UI.
- **Live telemetry** – Subscribe to `/runs/{id}/stream` (Server-Sent Events) for status, assistant/tool turns, artifact registrations, and git diff summaries.
- **CLI ergonomics** – `./run.sh crossrun …` handles install/migrate/launch/run/watch/ui without typing `python` or remembering curl payloads.
- **Offline & demo modes** – Toggle `CROSS_RUN_FAKE_CODEX` (skip CLI) and/or `CROSS_RUN_FAKE_SWARM` (skip OpenAI API) for fully local smoke tests; flip them off when you want real executions.
- **Diff artifacts** – If the workspace is a git repo, every run produces a structured `diff-summary` artifact (branch + files + shortstat + `git diff --stat`) the UI can render instantly.

## Repo layout

```
docs/                # context + architecture notes
scripts/             # helper scripts (dev servers, smoke tests)
src/app/             # Python source (API service + Swarm runner + shared logic)
workspaces/          # local run directories (git repos recommended)
```

## Architecture at a glance

1. **FastAPI API service** – CRUD for projects/runs, orchestrates pattern extraction and run lifecycle, persists steps/artifacts in SQLite.
2. **Swarm Runner** – Tiny FastAPI app that hosts a single Swarm agent wired to `codex_exec`. Callable instructions merge the stored pattern block + base prompt on each run.
3. **Codex CLI** – Invoked headlessly with `--json` + guardrail flags; JSONL stream is captured as artifacts so your UI can replay commands/diffs/output.
4. **SQLite** – Flat schema (`runs`, `steps`, `patterns`, `artifacts`) keeps metadata portable. Patterns are derived from steps and cached for quick previews.
5. **Workspaces** – Each run gets its own working directory (preferably a git repo). Codex processes operate inside that directory via `--cd`, and you can seed a new run by cloning a previous workspace (`from_run_id`) before Codex ever wakes up.
6. **Event broker** – Simple in-memory pub/sub publishes status, steps, artifacts, and diff summaries to `/runs/{id}/stream` so the frontend feels “alive.”

For a deeper dive, see `docs/architecture.md` and `docs/ux.md`.

## Quick start (friendly CLI — no `python` typing)

```bash
# 1) Install deps (Python 3.11+, via helper script)
./run.sh crossrun install   # set PYTHON_BIN=python3.12 if needed

# 2) Create the SQLite schema
./run.sh crossrun migrate

# 3) (optional) fake Codex CLI for demos
export CROSS_RUN_FAKE_CODEX=1

# 3b) (optional) run Swarm offline (no OpenAI key needed)
export CROSS_RUN_FAKE_SWARM=1      # or set OPENAI_API_KEY=<your key> for full Swarm runs

# 4) Launch API + runner (keep this terminal open)
./run.sh crossrun services        # uses $PYTHON_BIN -m uvicorn behind the scenes

# 5) New terminal: launch a run + auto-watch
./run.sh crossrun run "touch hello.txt"

# Need to reuse a workspace snapshot?
# ./run.sh crossrun run --from-run-id <previous_run_id> "touch hello.txt && ls"

# Bonus helpers (attaching later)
./run.sh crossrun watch <run_id>
./run.sh crossrun ui <run_id>      # opens the browser console

> If `OPENAI_API_KEY` isn’t set, the runner automatically switches to “offline” mode (`CROSS_RUN_FAKE_SWARM`) and calls `codex_exec` directly—perfect for local demos. Set a real key whenever you want Swarm to plan via OpenAI.
```

Prefer raw commands? See `scripts/devservers.sh` and the curl examples below.

### Environment setup

Create a `.env` in the repo root (already gitignored) with at least:

```dotenv
OPENAI_API_KEY=sk-...
# Optional toggles:
# CROSS_RUN_FAKE_CODEX=1   # stub Codex CLI
# CROSS_RUN_FAKE_SWARM=1   # skip Swarm/OpenAI planner
# CROSS_RUN_REQUIRE_GIT_REPO=1  # enforce git repo presence (default skips check)
```

The services automatically:
- Mirror `OPENAI_API_KEY` into both Swarm + Codex CLI subprocesses
- Auto-run `codex login --with-api-key ...` if the CLI hasn’t been authenticated yet (no more hanging login prompts)
- Fall back to fake modes when the key is missing

### Manual smoke test

```bash
# Create / update a project
curl -X PUT http://localhost:5050/projects/demo \
  -H "Content-Type: application/json" \
  -d '{"id":"demo","name":"Demo Project"}'

# Kick off a run (fake Codex will just log a stub)
curl -X POST http://localhost:5050/projects/demo/runs \
  -H "Content-Type: application/json" \
  -d '{"project_id":"demo","name":"Initial run","instructions":"touch hello.txt"}'

# Inspect derived pattern
curl http://localhost:5050/patterns/<run_id>

# Stream run events (status, steps, artifacts, diff hit)
curl -N http://localhost:5050/runs/<run_id>/stream

# Fetch git diff summary (if workspace is a repo)
curl http://localhost:5050/runs/<run_id>/diff

# Minimal SSE console (in browser)
open http://localhost:5050/ui/runs/<run_id>
```

See `docs/architecture.md`+`docs/ux.md` for flow details, API cadence, and judge-friendly UX notes.

### Automated tests (live API)

We ship an async pytest that boots both FastAPI services (in fake Codex/Swarm mode), launches two runs, and confirms that artifacts/steps are persisted plus the second run’s workspace inherits files from `from_run_id`. Run it with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3.11 -m pytest -p pytest_asyncio.plugin tests/test_live_api.py
```

The fixture picks random localhost ports, runs migrations against a temp SQLite file, and tears down both uvicorn processes automatically, so it’s safe to run alongside your real services.

## Feature set in more detail

| Capability                 | What you get                                                                   |
|---------------------------|---------------------------------------------------------------------------------|
| Pattern extraction        | Trims assistant/tool steps, finds variables via regex, clamps to 12 steps, renders `<reference_workflow>` XML |
| Pattern injection         | Stored block + base prompt automatically become the Swarm system message        |
| Event streaming           | `/runs/{id}/stream` emits `status`, `step`, `artifact`, and `diff` events       |
| Diff summaries            | Git branch/shortstat/file list + `--stat` output saved as JSON + artifact       |
| Workspace cloning         | Provide `from_run_id` to copy the previous workspace (files + `.git`) and emit provenance `workspace` events before Codex runs |
| Fake modes                | `CROSS_RUN_FAKE_CODEX=1` bypasses Codex CLI; `CROSS_RUN_FAKE_SWARM=1` bypasses Swarm API key |
| Self-healing Codex auth   | Automatically runs `codex login --with-api-key` using values from `.env`, retries commands when the CLI needs credentials |
| Telemetry UI              | `/ui/runs/{id}` is a zero-dependency HTML console you can use as a reference    |
| CLI helper                | Install/migrate/run/watch/ui commands with sensible defaults + env overrides    |

## API + CLI cheat sheet

| Action                                  | HTTP endpoint / CLI command                                                                 |
|-----------------------------------------|---------------------------------------------------------------------------------------------|
| Create project                          | `PUT /projects/{id}`                                                                        |
| Launch run                              | `POST /projects/{id}/runs` (supports `reference_run_id` + `from_run_id`) or `./run.sh crossrun run "..."` |
| Fetch run/pattern/steps/artifacts       | `GET /runs/{id}`, `/patterns/{id}`, `/runs/{id}/steps`, `/runs/{id}/artifacts`              |
| Stream live events                      | `GET /runs/{id}/stream` (SSE)                                                               |
| Diff summary                            | `GET /runs/{id}/diff`                                                                       |
| Run console                             | `http://localhost:5050/ui/runs/{id}` or `./run.sh crossrun ui <id>`                         |
| Launch services                         | `./run.sh crossrun services` (uses `$PYTHON_BIN -m uvicorn`)                                |

## Example run transcript (fake mode)

```
./run.sh crossrun run "touch hello.txt"
→ status: running
→ step(user): touch hello.txt
→ step(assistant): codex_exec(fake)
→ step(tool): codex_exec result (notes=["fake-codex-mode"])
→ artifact: artifacts/run-...-codex-....jsonl (72 bytes)
→ status: succeeded
```

With real Codex + git repo workspace you’ll also see:

```
→ step(tool): files=["hello.txt"], notes=["cmd:['touch hello.txt'] exit:0"]
→ diff: { "branch": "main", "files": [{"path": "hello.txt", "status": "??"}], "shortstat": "1 file changed..." }
```

## Environment knobs

| Variable              | Effect                                                                 |
|-----------------------|------------------------------------------------------------------------|
| `OPENAI_API_KEY`      | Enables Swarm planning + Codex CLI requests (production mode)          |
| `CROSS_RUN_FAKE_CODEX`| Forces `codex_exec` to stub responses (no CLI invocation)              |
| `CROSS_RUN_FAKE_SWARM`| Forces Swarm runner to skip OpenAI calls and synthesize a reply        |
| `CROSS_RUN_REQUIRE_GIT_REPO` | Set to `1` if you want Codex to refuse runs outside git repos (default = auto-skip check) |
| `CROSS_RUN_RUNNER_URL` | Override the Swarm runner base URL (tests use this to point at random ports) |
| `PYTHON_BIN`          | Interpreter used by `run.sh` + `scripts/devservers.sh`                 |

Mix and match: keep everything offline for local demos, then flip the switches when you want genuine Codex + Swarm automation.

## Roadmap ideas (PRs welcome)

1. Workspace snapshot dedupe/compression so repeated clones stay lightweight.
2. Step intent inference (populate `intent_kind/intent_target` to enrich patterns).
3. Websocket-based event streaming for richer UI interactions.
4. “Reproduce in Codex CLI” button that prints the exact `codex exec` command for manual triage.
5. CI profile: headless runner + database seeded via GitHub Actions for quick regression checks.
