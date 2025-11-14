# DraftPunk Integration Guide

This document describes how to use Codex-Swarm as a backend service for DraftPunk.

## Overview

Codex-Swarm provides a **clean, minimal, non-interactive API** for DraftPunk to use as a local automation and workflow service. DraftPunk treats Codex-Swarm as a stable backend engine that executes document workflows and code tasks.

## Architecture

```
DraftPunk (Chat Client)
    ↓ HTTP API calls
Codex-Swarm Backend
    ├── FastAPI (port 5050) - API endpoints
    ├── Swarm Runner (port 5055) - Execution engine
    ├── SQLite Database - Run persistence
    └── Workspaces - Isolated file environments
```

## Quick Start

### 1. Install Dependencies

```bash
./run.sh crossrun install
```

### 2. Run Database Migration

```bash
./run.sh crossrun migrate
```

### 3. Set Up Authentication

Codex-Swarm requires OpenAI API access. Set one of:

```bash
export OPENAI_API_KEY="sk-..."
# OR
export CROSS_RUN_OPENAI_API_KEY="sk-..."
```

For testing without OpenAI:

```bash
export CROSS_RUN_FAKE_SWARM=1
export CROSS_RUN_FAKE_CODEX=1
```

### 4. Start Services

```bash
./run.sh crossrun services
```

This starts both:
- **API Service** at `http://localhost:5050`
- **Runner Service** at `http://localhost:5055`

## Using the DraftPunk Client

### Python Client Library

Codex-Swarm includes a typed Python client at `src/draftpunk_client.py`:

```python
from draftpunk_client import CodexSwarmClient

# Initialize client
client = CodexSwarmClient(base_url="http://localhost:5050")

# Start a document writing run
run = client.start_run(
    project_id="my-workspace",
    instructions="Write a technical report on API design patterns",
    task_type="document_writing"
)

print(f"Started run: {run.run_id}")
print(f"Status: {run.status}")
print(f"Progress: {run.progress}%")

# Poll for completion
import time
while run.status in ("queued", "running"):
    time.sleep(2)
    run = client.get_run(run.run_id)
    print(f"Progress: {run.progress}%")

# Check results
if run.had_errors:
    for error in run.errors:
        print(f"Error: {error.message}")
else:
    summary = run.machine_summary
    print(f"✓ Complete!")
    print(f"  Goal: {summary.goal}")
    print(f"  Primary output: {summary.primary_artifact}")

    # Download the output file
    if summary.primary_artifact:
        content = client.get_file_text(run.run_id, summary.primary_artifact)
        print(content)
```

### Available Task Types

Codex-Swarm supports the following task types for DraftPunk workflows:

- **`code`** - Software development, scripting, coding tasks
- **`research`** - Literature review, web research, synthesis
- **`writing`** - Long-form content, articles, reports
- **`data_analysis`** - Python analysis, visualization, statistics
- **`document_processing`** - Batch conversion, formatting, transformation
- **`document_writing`** - Creating structured documents (DraftPunk primary use)
- **`document_analysis`** - Analyzing, extracting insights from documents

## API Endpoints

### Start a Run

**`POST /projects/{project_id}/runs`**

Create and queue a new run for execution.

**Request:**
```json
{
  "project_id": "my-workspace",
  "name": "Document generation run",
  "instructions": "Write a technical report on API design",
  "task_type": "document_writing",
  "reference_run_id": null,
  "from_run_id": null
}
```

**Response:**
```json
{
  "run_id": "run-abc123",
  "project_id": "my-workspace",
  "task_type": "document_writing",
  "status": "queued",
  "progress": 0,
  "had_errors": false,
  "errors": [],
  "artifacts": [],
  "machine_summary": null,
  "created_at": "2025-01-13T10:30:00Z"
}
```

### Get Run Status

**`GET /runs/{run_id}`**

Fetch complete run information including results.

**Response:**
```json
{
  "run_id": "run-abc123",
  "project_id": "my-workspace",
  "task_type": "document_writing",
  "status": "succeeded",
  "progress": 100,
  "had_errors": false,
  "errors": [],
  "artifacts": [
    {
      "id": "art-xyz",
      "run_id": "run-abc123",
      "kind": "markdown",
      "path": "/path/to/output.md",
      "bytes": 15234,
      "created_at": "2025-01-13T10:32:00Z"
    }
  ],
  "machine_summary": {
    "goal": "Write a technical report on API design",
    "primary_artifact": "report.md",
    "secondary_artifacts": ["diagrams.png"],
    "execution_attempted": true,
    "execution_succeeded": true,
    "reason_for_failure": null,
    "notes": null
  },
  "created_at": "2025-01-13T10:30:00Z"
}
```

### List Workspace Files

**`GET /runs/{run_id}/workspace/files`**

List all files in the run's workspace.

**Response:**
```json
{
  "run_id": "run-abc123",
  "total_files": 3,
  "files": [
    {
      "path": "report.md",
      "size_bytes": 15234,
      "type": "markdown"
    },
    {
      "path": "diagrams.png",
      "size_bytes": 45123,
      "type": "image"
    },
    {
      "path": "notes.txt",
      "size_bytes": 1024,
      "type": "text"
    }
  ]
}
```

### Download File

**`GET /runs/{run_id}/workspace/files/{path}`**

Download a specific file from the workspace.

**Example:**
```bash
curl http://localhost:5050/runs/run-abc123/workspace/files/report.md
```

Returns raw file contents with appropriate `Content-Type`.

## Machine Summary

The `machine_summary` field provides structured, LLM-friendly information about run outcomes:

```python
{
  "goal": "User's original task description",
  "primary_artifact": "main_output.md",          # Most important output file
  "secondary_artifacts": ["extra.txt", ...],     # Additional outputs
  "execution_attempted": true,                   # Whether execution ran
  "execution_succeeded": true,                   # Whether it completed successfully
  "reason_for_failure": null,                    # Error classification if failed
  "notes": null                                  # Additional context
}
```

### Error Classifications

When `execution_succeeded` is `false`, `reason_for_failure` will be one of:

- `permission_error` - File/system permission denied
- `missing_dependency` - Required tool or file not found
- `timeout` - Operation exceeded time limit
- `tool_failure` - Tool execution failed
- `runtime_error` - General execution error
- `cancelled` - User cancelled the run

## Project ID Semantics

**IMPORTANT**: `project_id` is the stable identifier for a DraftPunk workspace.

### Rules

1. **Non-empty** - `project_id` cannot be empty or whitespace
2. **Stable** - Use the same `project_id` for all runs in a workspace
3. **Pattern learning** - Patterns are stored per-project for reuse
4. **Workspace organization** - Files are organized under `workspaces/{project_id}/`

### Example

```python
# Good: Stable project_id across runs
client.start_run(project_id="api-docs", instructions="Write intro")
client.start_run(project_id="api-docs", instructions="Add examples")
client.start_run(project_id="api-docs", instructions="Review and polish")

# Bad: Different project_id loses context
client.start_run(project_id="task-1", instructions="Write intro")
client.start_run(project_id="task-2", instructions="Add examples")  # No pattern reuse!
```

## Service Mode (Non-Interactive)

When running as a background service for DraftPunk:

### No Interactive Prompts

Services will **never** block waiting for user input. All configuration must be via environment variables or config files.

### Fail-Fast on Misconfiguration

If critical configuration is missing (e.g., `OPENAI_API_KEY` when not in fake mode), services will:

1. Log a clear error message
2. Exit immediately with non-zero code
3. **Not** hang or prompt for input

Example:
```
FATAL: Running in service mode without OPENAI_API_KEY.
Set OPENAI_API_KEY environment variable or CROSS_RUN_OPENAI_API_KEY config.
Alternatively, set CROSS_RUN_FAKE_SWARM=1 for testing without OpenAI.
```

### TTY Detection

Services detect non-TTY environments and disable Rich formatting automatically.

## Error Handling

### Structured Errors

All errors are captured in the `errors` array:

```json
{
  "errors": [
    {
      "step": "execution",
      "tool": "codex_exec",
      "error_type": "permission_error",
      "message": "Cannot execute Python script: Permission denied"
    }
  ]
}
```

### Error Recovery

DraftPunk can inspect errors and decide whether to:
- Retry with different parameters
- Inform the user
- Fall back to alternative workflow

## Pattern Reuse

Codex-Swarm learns from successful runs and can reuse patterns.

### Using a Reference Run

```python
# First run - establishes pattern
run1 = client.start_run(
    project_id="reports",
    instructions="Write Q1 sales report",
    task_type="document_writing"
)

# Later run - reuses pattern
run2 = client.start_run(
    project_id="reports",
    instructions="Write Q2 sales report",
    task_type="document_writing",
    reference_run_id=run1.run_id  # Reuse workflow pattern
)
```

### Workspace Cloning

Clone files from a previous run:

```python
run2 = client.start_run(
    project_id="reports",
    instructions="Update the report with new data",
    task_type="document_writing",
    from_run_id=run1.run_id  # Clone workspace files
)
```

## Environment Variables

### Required

- `OPENAI_API_KEY` - OpenAI API key (or set fake mode)

### Optional

- `CROSS_RUN_DATABASE_PATH` - SQLite database path (default: `data/dev.db`)
- `CROSS_RUN_WORKSPACE_ROOT` - Workspace directory (default: `workspaces`)
- `CROSS_RUN_ARTIFACTS_ROOT` - Artifacts directory (default: `artifacts`)
- `CROSS_RUN_RUNNER_URL` - Runner service URL (default: `http://localhost:5055`)
- `CROSS_RUN_CODEX_PROFILE` - Codex CLI profile (default: `batch`)
- `CROSS_RUN_CODEX_FULL_AUTO` - Enable full automation (default: `true`)
- `CROSS_RUN_REQUIRE_GIT_REPO` - Require git repos (default: `false`)

### Testing/Development

- `CROSS_RUN_FAKE_SWARM=1` - Skip OpenAI Swarm calls
- `CROSS_RUN_FAKE_CODEX=1` - Skip Codex CLI execution

## Troubleshooting

### "Project not found"

Create project first:
```python
client.client.put(
    f"/projects/{project_id}",
    json={
        "id": project_id,
        "name": project_id,
        "task_type": "document_writing"
    }
)
```

Or use `start_run()` which auto-creates projects.

### "Run stuck in queued status"

Check that both services are running:
```bash
curl http://localhost:5050/healthz
curl http://localhost:5055/healthz
```

### "Permission errors during execution"

Codex CLI needs write access to workspace. Check:
```bash
ls -la workspaces/
```

### "OPENAI_API_KEY not set"

In service mode, set the environment variable before starting:
```bash
export OPENAI_API_KEY="sk-..."
./run.sh crossrun services
```

## Next Steps

1. **MCP Integration** - Add MCP server on top of HTTP API
2. **Stencila Workflows** - Use Stencila for `document_*` task types
3. **Streaming Results** - Use SSE endpoint for real-time updates
4. **Artifact Management** - Download and cache artifacts in DraftPunk

## API Reference Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/projects/{id}` | PUT | Create/update project |
| `/projects/{id}/runs` | POST | Start new run |
| `/runs` | GET | List all runs |
| `/runs/{id}` | GET | Get run details |
| `/runs/{id}/workspace/files` | GET | List workspace files |
| `/runs/{id}/workspace/files/{path}` | GET | Download file |
| `/runs/{id}/cancel` | POST | Cancel running execution |
| `/runs/{id}/stream` | GET | SSE event stream |

## Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad request (validation error)
- `404` - Not found
- `500` - Server error

All errors return JSON:
```json
{
  "detail": "Error message here"
}
```
