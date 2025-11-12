# UX Playbook — “Juiced” Edition

## Create Run flow
- **Context chips**: show the selected reference run and a live preview badge (“Pattern: 6 steps, 3 vars”).
- **Editor assist**: split instructions editor view into “Goal” + “Guardrails” tabs so judges see intent + safety cues.
- **Call-to-action**: “Run with Guidance” primary button, secondary “Dry run” (skips reference block) for comparisons.

## Run detail screen
- **Transcript rail** (left): badges for `user`, `assistant`, `tool`; tool entries expand inline to show touched files + notes.
- **Diff & artifacts rail** (right): per-file cards with LoC +/- micro-bars, “Download Codex JSONL” button, rerun shortcut.
- **Live pulse**: subscribe to `/runs/{id}/stream` (SSE) to animate status + transcript updates in real time, no manual refresh.
- **Pattern preview drawer**: sticky card summarizing `<reference_workflow>` currently in play; highlight missing variables.
- **Git diff card**: call `/runs/{id}/diff` (or listen for `diff` SSE events) to show changed files + shortstat/branch info without re-reading the workspace.

## Run list
- Columns: Name, Date, Status, Pattern badge (with tooltip summary), Workspace path (tap-to-copy).
- Provide quick filters for “Has Pattern”, “Failed”, “Needs Approval”.

## Delight tweaks
- Use shadcn toast to celebrate when a new pattern is derived (“Saved 6-step workflow from Run 5”).
- Inline guidance when Codex fails: show the captured notes (stderr, exit codes) in a friendly card instead of dumping logs.
- Offer “Load workspace diff” button that opens a modal with `git status` summary for run directories.
