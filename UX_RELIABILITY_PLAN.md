# Codex-Swarm: Reliability & UX Improvements
**Focus: Making the prototype more reliable and easier to use**

---

## 🎯 Top Priority Improvements

### 1. Better Error Handling & Recovery ⭐⭐⭐
**Problem:** When things fail, users don't know what went wrong or how to fix it.

**Quick Wins:**
- Add helpful error messages with recovery suggestions
- Gracefully handle missing Codex CLI
- Better handling when OpenAI API is unavailable
- Validate inputs before starting runs

**Impact:** Reduces frustration, makes debugging easier
**Effort:** 3-4 hours

---

### 2. Progress Visibility ⭐⭐⭐
**Problem:** Users don't know what's happening during a run. Is it stuck? Making progress?

**Quick Wins:**
- Add progress indicators to event stream
- Show "currently doing X..." messages
- Display elapsed time
- Better status transitions in UI

**Impact:** Builds confidence, helps identify hangs
**Effort:** 3-4 hours

---

### 3. Run Control (Cancellation) ⭐⭐
**Problem:** If a run goes wrong, there's no way to stop it.

**Quick Wins:**
- Add cancel endpoint
- Store subprocess handles
- Graceful shutdown of Codex processes
- Update status to "cancelled"

**Impact:** Prevents wasted time, saves resources
**Effort:** 4-5 hours

---

### 4. Better CLI Experience ⭐⭐⭐
**Problem:** Plain text output is hard to read and follow.

**Quick Wins:**
- Use `rich` library for formatted output
- Color-coded status messages
- Tables for run information
- Better event formatting in watch mode

**Impact:** Makes CLI much more pleasant to use
**Effort:** 2-3 hours

---

### 5. Workspace Management ⭐
**Problem:** Hard to see what files were created/modified without going to filesystem.

**Quick Wins:**
- API endpoint to list workspace files
- Download specific files from workspace
- Show file tree in events
- Summary of changes after run completes

**Impact:** Easier to see results
**Effort:** 4-5 hours

---

### 6. Cleanup Tools ⭐⭐
**Problem:** Workspaces and artifacts accumulate indefinitely.

**Quick Wins:**
- `./run.sh crossrun cleanup` command
- Delete old/failed runs
- Show disk usage
- Dry-run mode

**Impact:** Prevents disk filling up
**Effort:** 2-3 hours

---

### 7. Run Templates ⭐
**Problem:** Users write the same types of instructions repeatedly.

**Quick Wins:**
- Predefined templates for common tasks
- `--template test` or `--template lint`
- Easy to add custom templates

**Impact:** Faster to start runs
**Effort:** 1-2 hours

---

### 8. Retry & Resume Failed Runs ⭐
**Problem:** If a run fails midway, you have to start over.

**Quick Wins:**
- Store run state checkpoints
- `retry` command to restart failed runs
- Continue from last successful step
- Preserve workspace on failure

**Impact:** Saves time on transient failures
**Effort:** 6-8 hours

---

## 🚀 Recommended Implementation Order

### Phase 1: Core UX (1-2 days)
1. ✅ Better error messages with recovery hints
2. ✅ Rich CLI with colors and formatting
3. ✅ Progress indicators in event stream
4. ✅ Enhanced UI console with progress bars

**Result:** Much more pleasant to use, clearer feedback

---

### Phase 2: Control & Visibility (2-3 days)
1. ✅ Run cancellation
2. ✅ Workspace file listing API
3. ✅ File tree in events
4. ✅ Summary of changes after runs

**Result:** More control, easier to inspect results

---

### Phase 3: Maintenance (1 day)
1. ✅ Cleanup command
2. ✅ Disk usage stats
3. ✅ Run templates

**Result:** Easier to maintain, faster workflows

---

### Phase 4: Advanced (2-3 days)
1. ✅ Retry failed runs
2. ✅ Better pattern visualization
3. ✅ Notification webhooks

**Result:** More robust, better for longer workflows

---

## 📝 Specific Implementation Details

### Better Error Messages

```python
# src/app/services/errors.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserError(Exception):
    """User-facing error with recovery suggestion"""
    message: str
    recovery: str
    code: str
    docs_url: Optional[str] = None

    def to_dict(self):
        return {
            "error": self.message,
            "suggestion": self.recovery,
            "code": self.code,
            "docs": self.docs_url
        }

# Common errors
CODEX_NOT_FOUND = UserError(
    message="Codex CLI is not installed or not in your PATH",
    recovery="Install it with: npm install -g @anthropic-ai/claude-code",
    code="CODEX_CLI_MISSING",
    docs_url="https://docs.claude.com/claude-code"
)

CODEX_AUTH_FAILED = UserError(
    message="Codex CLI authentication failed",
    recovery="Run 'codex login' or set OPENAI_API_KEY environment variable",
    code="CODEX_AUTH_REQUIRED"
)

WORKSPACE_NOT_FOUND = UserError(
    message="Source workspace not found for cloning",
    recovery="Check that the source run ID is correct, or start without --from-run-id",
    code="WORKSPACE_MISSING"
)
```

### Progress Indicators

```python
# src/app/services/run_service.py
import time

async def launch_run(...):
    start_time = time.time()

    # Stage 1: Workspace preparation
    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "workspace_prep",
        "message": "Preparing workspace...",
        "percent": 0
    })

    workspace, cloned_entries, source_found = _prepare_workspace(...)

    if cloned_entries:
        await run_events.publish(run.id, {
            "type": "progress",
            "stage": "workspace_cloned",
            "message": f"Cloned {len(cloned_entries)} items from previous run",
            "percent": 20,
            "details": {"files": cloned_entries[:10]}  # First 10
        })

    # Stage 2: Running
    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "executing",
        "message": "Codex is working on your task...",
        "percent": 30
    })

    runner_response = await runner_client.invoke_run(...)

    # Stage 3: Pattern extraction
    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "extracting_patterns",
        "message": "Learning from this run...",
        "percent": 80
    })

    await pattern_agent.fetch_pattern(session, run.id)

    # Complete
    elapsed = time.time() - start_time
    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "complete",
        "message": f"Run completed in {elapsed:.1f}s",
        "percent": 100,
        "elapsed": elapsed
    })
```

### Rich CLI

```python
# Add to pyproject.toml dependencies:
# "rich>=13.0.0,<14.0.0"

# scripts/crossrun.py
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

def run_command(args: argparse.Namespace) -> None:
    # Show creation progress
    with console.status("[bold green]Creating run...") as status:
        # Create project
        client.put(f"/projects/{args.project_id}", json={...})

        # Create run
        resp = client.post(f"/projects/{args.project_id}/runs", json=payload)
        run = resp.json()
        run_id = run["id"]

    # Show run info in nice table
    table = Table(title="🚀 Run Created", show_header=False, box=None)
    table.add_column("Key", style="cyan bold")
    table.add_column("Value", style="green")

    table.add_row("Run ID", run_id)
    table.add_row("Project", args.project_id)
    table.add_row("Status", f"[yellow]{run['status']}[/yellow]")
    table.add_row("Task Type", task_type)
    table.add_row("Workspace", f"workspaces/{safe_project}/{safe_run}")

    console.print()
    console.print(table)
    console.print()

    if args.watch:
        watch_with_rich(run_id, args.api_url)

def watch_with_rich(run_id: str, api_url: str):
    """Watch run with rich formatting"""
    console.print(Panel.fit(
        f"Streaming events for run [bold cyan]{run_id}[/bold cyan]",
        title="Live Monitor",
        border_style="blue"
    ))
    console.print()

    with httpx.Client(timeout=None) as client:
        with client.stream("GET", f"{api_url}/runs/{run_id}/stream") as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = json.loads(line.removeprefix("data:").strip())
                event_type = data.get('type', 'event')

                # Format different event types
                if event_type == "status":
                    status = data.get("status", "")
                    if status == "running":
                        console.print("▶️  [yellow]Status: Running[/yellow]")
                    elif status == "succeeded":
                        console.print("✅ [bold green]Status: Succeeded[/bold green]")
                    elif status == "failed":
                        console.print("❌ [bold red]Status: Failed[/bold red]")

                elif event_type == "progress":
                    msg = data.get("message", "")
                    percent = data.get("percent", 0)
                    console.print(f"⏳ [{percent:3d}%] {msg}")

                elif event_type == "step":
                    role = data.get("role", "")
                    content = data.get("content", "")[:200]
                    if role == "assistant":
                        console.print(f"🤖 [blue]{content}[/blue]")
                    elif role == "tool":
                        console.print(f"🔧 [magenta]{content}[/magenta]")

                elif event_type == "artifact":
                    path = data.get("path", "")
                    console.print(f"📄 [green]Saved artifact: {path}[/green]")

                elif event_type == "error":
                    error = data.get("error", {})
                    console.print()
                    console.print(Panel(
                        f"[bold red]{error.get('message')}[/bold red]\n\n"
                        f"💡 [yellow]Suggestion:[/yellow] {error.get('suggestion', 'Check logs')}",
                        title="⚠️  Error",
                        border_style="red"
                    ))
                    console.print()
```

### Run Cancellation

```python
# src/app/runner/codex_tool.py
import threading
import signal

# Global registry of active processes
_active_processes: dict[str, subprocess.Popen] = {}
_process_lock = threading.Lock()

def codex_exec(...):
    run_id = context_variables.get("run_id", "run-unknown")

    # ... existing setup ...

    proc = subprocess.Popen(...)

    # Register process
    with _process_lock:
        _active_processes[run_id] = proc

    try:
        for line in proc.stdout:
            # Check if cancellation requested
            if _is_cancelled(run_id):
                console.print("[yellow]Cancellation requested, terminating...[/yellow]")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return "codex_exec(cancelled)"

            # ... rest of processing ...
    finally:
        # Unregister process
        with _process_lock:
            _active_processes.pop(run_id, None)

def _is_cancelled(run_id: str) -> bool:
    """Check if run cancellation has been requested"""
    # This would check database or a shared flag
    # For now, simplified version:
    cancel_file = Path(f"/tmp/cancel-{run_id}")
    return cancel_file.exists()

def cancel_run(run_id: str):
    """Cancel a running execution"""
    with _process_lock:
        proc = _active_processes.get(run_id)
        if proc and proc.poll() is None:
            proc.terminate()
            return True
    return False

# src/app/api/routes/runs.py
@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    """Cancel a running execution"""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ["queued", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status: {run.status}"
        )

    # Set cancellation flag
    cancel_file = Path(f"/tmp/cancel-{run_id}")
    cancel_file.touch()

    # Try to kill process directly
    from ..runner.codex_tool import cancel_run as kill_process
    killed = kill_process(run_id)

    await run_events.publish(run_id, {
        "type": "cancellation_requested",
        "run_id": run_id,
        "killed": killed
    })

    return {"status": "cancellation_requested", "process_killed": killed}
```

### Cleanup Command

```python
# scripts/crossrun.py
def cleanup(args: argparse.Namespace) -> None:
    """Clean up old workspaces and artifacts"""
    from datetime import datetime, timedelta
    import shutil

    workspace_root = REPO_ROOT / "workspaces"
    artifacts_root = REPO_ROOT / "artifacts"

    cutoff = datetime.now() - timedelta(days=args.older_than)

    console.print(f"[yellow]Finding workspaces older than {args.older_than} days...[/yellow]")

    # Find candidates
    to_delete = []
    total_size = 0

    for workspace_dir in workspace_root.rglob("run-*"):
        if not workspace_dir.is_dir():
            continue

        mtime = datetime.fromtimestamp(workspace_dir.stat().st_mtime)
        if mtime > cutoff:
            continue

        # Calculate size
        size = sum(f.stat().st_size for f in workspace_dir.rglob("*") if f.is_file())
        total_size += size
        to_delete.append((workspace_dir, size, mtime))

    if not to_delete:
        console.print("[green]No workspaces to clean up![/green]")
        return

    # Show what will be deleted
    table = Table(title=f"Workspaces to Delete ({len(to_delete)})")
    table.add_column("Path", style="cyan")
    table.add_column("Size", style="yellow")
    table.add_column("Age", style="dim")

    for path, size, mtime in sorted(to_delete, key=lambda x: x[1], reverse=True)[:20]:
        age = datetime.now() - mtime
        table.add_row(
            str(path.relative_to(workspace_root)),
            f"{size / 1024 / 1024:.1f} MB",
            f"{age.days} days"
        )

    console.print(table)
    console.print(f"\n[bold]Total: {total_size / 1024 / 1024:.1f} MB[/bold]")

    if args.dry_run:
        console.print("\n[yellow]Dry run - no files deleted[/yellow]")
        return

    # Confirm
    if not args.force:
        response = input("\nProceed with deletion? [y/N]: ")
        if response.lower() != 'y':
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Delete
    with Progress() as progress:
        task = progress.add_task("Deleting...", total=len(to_delete))
        for path, _, _ in to_delete:
            shutil.rmtree(path)
            progress.advance(task)

    console.print(f"\n[green]✓ Deleted {len(to_delete)} workspaces ({total_size / 1024 / 1024:.1f} MB freed)[/green]")

# Add to parser
cleanup_p = sub.add_parser("cleanup", help="Clean up old workspaces")
cleanup_p.add_argument("--older-than", type=int, default=7, help="Delete workspaces older than N days")
cleanup_p.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
cleanup_p.add_argument("--force", action="store_true", help="Skip confirmation")
cleanup_p.set_defaults(func=cleanup)
```

---

## 🎯 Quick Start: What Should We Implement First?

Based on impact and effort, I recommend starting with:

### Option A: "Better Feedback" Package (4-5 hours)
- Better error messages
- Progress indicators
- Rich CLI formatting

**Result:** Immediately more pleasant to use

### Option B: "Control & Visibility" Package (5-6 hours)
- Run cancellation
- Workspace file listing
- Enhanced UI console

**Result:** More control over runs, easier to debug

### Option C: "Maintenance" Package (3-4 hours)
- Cleanup command
- Run templates
- Disk usage tools

**Result:** Easier day-to-day usage

---

## 🤔 Which Should We Build First?

Let me know which area you'd like to focus on, and I can start implementing right away!
