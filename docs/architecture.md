# Cross-Run Context Injection — Architecture Notes

## Goals
- Capture successful run signals and distill them into compact workflow patterns.
- Inject pattern guidance into subsequent runs through Swarm callable instructions.
- Execute work through Codex CLI in headless mode, persisting every step/artefact.
- Keep implementation lightweight: SQLite, FastAPI, and a minimal Swarm runner.

## Components
1. **API Service (FastAPI + SQLite)**
   - CRUD for projects/runs.
   - Pattern extraction + preview endpoints.
   - Orchestrates run lifecycle, persists steps, stores Codex JSONL artefacts.
2. **Swarm Runner (FastAPI)**
   - One Swarm agent with a single tool (`codex_exec`).
   - Builds system message from stored `pattern_block`, `base_prompt`, run prompt.
   - Streams Codex JSONL output, returns summary + files touched.
3. **Workspaces**
   - Each run executes in `/workspaces/<project>/<run>/`.
   - Git repos recommended; set `fromRunId` to copy the previous workspace (including `.git`) before the new run starts.
4. **SQLite Schema**
   - Tables from spec (`runs`, `steps`, `patterns`, `artifacts`).
   - Patterns are derived views; cache table optional for fast UI previews.

## Data Flow
1. Client hits `POST /projects/:id/runs`.
2. API optionally pulls reference run, runs extractor → `pattern_block`.
3. API stores run row (`queued`) + composed `system_instructions`.
4. API synchronously/asynchronously POSTs to Runner `/run`:
   ```json
   {
     "messages": [{"role":"user","content": "<run instructions>"}],
     "context_variables": {
       "workspace": "/workspaces/<project>/<run>",
       "pattern_block": "<reference_workflow>…</reference_workflow>",
       "base_prompt": "You are a precise code agent.",
       "profile": "batch"
     }
   }
   ```
5. Runner executes Codex, produces JSONL events → API logs `steps`, `tool_reports`, attaches artifact paths.
6. Client either polls (`GET /runs/:id`, `/runs/:id/steps`) or subscribes to `GET /runs/:id/stream` (Server-Sent Events) for live status/tool/diff events. An HTML demo lives at `/ui/runs/{id}` for quick validation.
7. Git diff summaries (when the workspace is a repo) are captured into `diff-summary` artifacts and exposed via `/runs/{id}/diff` + live events so the UI can highlight file changes instantly.

## Pattern Extraction Highlights
- Filter assistant/tool steps with `outcome_ok=1`.
- Normalize instructions (trim, collapse whitespace, 160-char max).
- Regex-based variable discovery (range, substitution, file references).
- Build XML `<reference_workflow>` block capped at 12 steps / ~600 tokens.

## UX Considerations
- **Run creation modal** with “Learn from” dropdown + pattern preview drawer.
- **Run detail screen** showcasing transcript, pattern summary, diff stats, artefact downloads.
- **Pattern badge** on run list to encourage reuse.
- Provide copy-friendly testing guide (Codex login, sample `curl` for `/run`).

## Next Steps
1. Scaffold FastAPI projects (`api/`, `runner/`) with shared settings module.
2. Implement SQLite access layer + migration CLI.
3. Build pattern extractor + REST endpoints.
4. Integrate Swarm runner, stub Codex exec for local dev, document tests.
