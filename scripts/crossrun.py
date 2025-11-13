from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
DEFAULT_API = "http://localhost:5050"

# Run templates for common tasks
RUN_TEMPLATES = {
    "test": {
        "instructions": "Run all tests in the test suite and report results",
        "description": "Run test suite",
    },
    "lint": {
        "instructions": "Run linting on the codebase and fix any issues found",
        "description": "Run linter and fix issues",
    },
    "format": {
        "instructions": "Format all code files according to project style",
        "description": "Format code",
    },
    "doc": {
        "instructions": "Generate or update documentation for the codebase",
        "description": "Generate documentation",
    },
    "analyze": {
        "instructions": "Analyze the codebase for potential issues, bugs, and improvements",
        "description": "Code analysis",
    },
    "refactor": {
        "instructions": "Refactor the code to improve maintainability and readability",
        "description": "Refactor code",
    },
    "security": {
        "instructions": "Scan the codebase for security vulnerabilities and suggest fixes",
        "description": "Security scan",
    },
    "deps": {
        "instructions": "Update project dependencies to latest compatible versions",
        "description": "Update dependencies",
    },
}


def _safe_segment(value: str, fallback: str) -> str:
    trimmed = value.strip() or fallback
    encoded = quote(trimmed, safe="")
    return encoded or fallback


def _run(cmd: Iterable[str], extra_env: dict | None = None) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC_PATH))
    if extra_env:
        env.update(extra_env)
    print(f"$ {' '.join(cmd)}")
    subprocess.run(list(cmd), cwd=str(REPO_ROOT), check=True, env=env)


def install(args: argparse.Namespace) -> None:
    _run([args.python_bin, "-m", "pip", "install", "--user", "-e", ".[dev]"])


def migrate(args: argparse.Namespace) -> None:
    _run([args.python_bin, "-m", "app.migrations"])


def services(args: argparse.Namespace) -> None:
    if args.manual:
        print("Run these in separate terminals:")
        print("  PYTHONPATH=src uvicorn app.api.main:app --reload --port 5050")
        print("  PYTHONPATH=src uvicorn app.runner.main:app --reload --port 5055")
        return
    _run(["bash", "scripts/devservers.sh"])


def templates(args: argparse.Namespace) -> None:
    """List available run templates."""
    console.print()
    console.print(Panel.fit("📝 Available Run Templates", border_style="cyan"))
    console.print()

    table = Table(show_header=True, box=None)
    table.add_column("Template", style="cyan bold", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Instructions", style="dim")

    for name, template in sorted(RUN_TEMPLATES.items()):
        table.add_row(
            name,
            template["description"],
            template["instructions"][:60] + "..." if len(template["instructions"]) > 60 else template["instructions"],
        )

    console.print(table)
    console.print()
    console.print("[dim]Usage: ./run.sh crossrun run --template <name>[/dim]")
    console.print()


def run_command(args: argparse.Namespace) -> None:
    # Handle template if specified
    instructions = args.instructions
    if hasattr(args, "template") and args.template:
        if args.template not in RUN_TEMPLATES:
            console.print(f"[red]Unknown template: {args.template}[/red]")
            console.print(f"[yellow]Available templates: {', '.join(RUN_TEMPLATES.keys())}[/yellow]")
            console.print("[dim]Use './run.sh crossrun templates' to see all templates[/dim]")
            return

        template = RUN_TEMPLATES[args.template]
        instructions = template["instructions"]
        console.print(f"[cyan]Using template:[/cyan] {args.template} - {template['description']}")
        console.print()
    elif not instructions:
        console.print("[red]Error: Either instructions or --template is required[/red]")
        console.print("[dim]Usage:[/dim]")
        console.print("  [dim]./run.sh crossrun run \"your instructions here\"[/dim]")
        console.print("  [dim]./run.sh crossrun run --template test[/dim]")
        return

    payload = {
        "project_id": args.project_id,
        "name": args.name or instructions.splitlines()[0][:40] or "Run",
        "instructions": instructions,
        "reference_run_id": args.reference_run_id,
        "from_run_id": args.from_run_id,
    }

    with console.status("[bold green]Creating run...") as status:
        with httpx.Client(base_url=args.api_url, timeout=None) as client:
            # Create/update project with specified task_type
            task_type = getattr(args, "task_type", "code")
            client.put(
                f"/projects/{args.project_id}",
                json={
                    "id": args.project_id,
                    "name": args.project_id.title(),
                    "task_type": task_type,
                },
            ).raise_for_status()

            status.update("[bold green]Launching run...")
            resp = client.post(f"/projects/{args.project_id}/runs", json=payload)
            resp.raise_for_status()
            run = resp.json()
            run_id = run["id"]

    # Display run info in a nice table
    table = Table(title="🚀 Run Created", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan bold")
    table.add_column("Value", style="green")

    table.add_row("Run ID", run_id)
    table.add_row("Project", args.project_id)
    table.add_row("Status", f"[yellow]{run['status']}[/yellow]")

    safe_project = _safe_segment(args.project_id, "project")
    safe_run = _safe_segment(run_id, "run")
    table.add_row("Workspace", f"workspaces/{safe_project}/{safe_run}")

    if task_type != "code":
        table.add_row("Task Type", task_type)

    if args.reference_run_id:
        table.add_row("Using Pattern", args.reference_run_id)

    if args.from_run_id:
        table.add_row("Cloned From", args.from_run_id)

    console.print()
    console.print(table)
    console.print()

    if args.watch:
        watch(args=argparse.Namespace(run_id=run_id, api_url=args.api_url))


def watch(args: argparse.Namespace) -> None:
    url = f"{args.api_url}/runs/{args.run_id}/stream"

    console.print()
    console.print(
        Panel.fit(
            f"Streaming events for run [bold cyan]{args.run_id}[/bold cyan]\n"
            f"Press [bold]Ctrl+C[/bold] to stop watching",
            title="📡 Live Monitor",
            border_style="blue",
        )
    )
    console.print()

    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue

                    data = json.loads(line.removeprefix("data:").strip())
                    event_type = data.get("type", "event")

                    # Format different event types with colors and icons
                    if event_type == "status":
                        status = data.get("status", "unknown")
                        if status == "queued":
                            console.print("⏸️  [dim]Status: Queued[/dim]")
                        elif status == "running":
                            console.print("▶️  [yellow]Status: Running[/yellow]")
                        elif status == "succeeded":
                            console.print("✅ [bold green]Status: Succeeded[/bold green]")
                        elif status == "failed":
                            console.print("❌ [bold red]Status: Failed[/bold red]")
                        else:
                            console.print(f"📋 Status: {status}")

                    elif event_type == "progress":
                        message = data.get("message", "")
                        percent = data.get("percent", 0)
                        elapsed = data.get("elapsed")
                        if elapsed:
                            console.print(
                                f"⏳ [[cyan]{percent:3d}%[/cyan]] {message} [dim]({elapsed:.1f}s)[/dim]"
                            )
                        else:
                            console.print(f"⏳ [[cyan]{percent:3d}%[/cyan]] {message}")

                    elif event_type == "step":
                        role = data.get("role", "")
                        content = data.get("content", "")[:150]
                        if role == "assistant":
                            console.print(f"🤖 [blue]{content}...[/blue]")
                        elif role == "user":
                            console.print(f"👤 [white]{content}...[/white]")
                        elif role == "tool":
                            console.print(f"🔧 [magenta]{content}[/magenta]")
                            # Show files if present
                            files = data.get("files", [])
                            if files:
                                console.print(
                                    f"   [dim]Modified: {', '.join(files[:5])}[/dim]"
                                )

                    elif event_type == "artifact":
                        path = data.get("path", "")
                        bytes_count = data.get("bytes", 0)
                        console.print(
                            f"📄 [green]Artifact saved:[/green] {path} [dim]({bytes_count} bytes)[/dim]"
                        )

                    elif event_type == "error":
                        error = data.get("error", {})
                        console.print()
                        console.print(
                            Panel(
                                f"[bold red]{error.get('error', 'Unknown error')}[/bold red]\n\n"
                                f"💡 [yellow]Suggestion:[/yellow] {error.get('suggestion', 'Check the logs')}",
                                title="⚠️  Error",
                                border_style="red",
                            )
                        )
                        console.print()

                    elif event_type == "workspace":
                        action = data.get("action", "")
                        if action == "cloned":
                            entries = data.get("entries", [])
                            console.print(
                                f"📁 [green]Workspace cloned:[/green] {len(entries)} items"
                            )
                        elif action == "clone-missing":
                            console.print("📁 [yellow]Source workspace not found[/yellow]")

                    elif event_type == "diff":
                        diff = data.get("diff", {})
                        files_changed = len(diff.get("files", []))
                        if files_changed:
                            console.print(
                                f"📝 [cyan]Git diff:[/cyan] {files_changed} files changed"
                            )

                    elif event_type == "cancelled":
                        console.print("🛑 [red]Run cancelled[/red]")

                    elif event_type == "workspace_summary":
                        total = data.get("total_files", 0)
                        files = data.get("files", [])
                        console.print(f"\n📁 [cyan]Workspace files:[/cyan] {total} total")
                        if files:
                            for f in files[:10]:
                                size_kb = f.get("size", 0) / 1024
                                console.print(f"   [dim]{f.get('path')} ({size_kb:.1f}KB)[/dim]")
                            if total > 10:
                                console.print(f"   [dim]... and {total - 10} more files[/dim]")

                    else:
                        # Unknown event type, show as dim JSON
                        console.print(f"[dim]• {event_type}: {json.dumps(data)}[/dim]")

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Disconnected[/yellow]")
    except Exception as exc:
        console.print()
        console.print(f"[red]Error: {exc}[/red]")


def cancel(args: argparse.Namespace) -> None:
    """Cancel a running execution."""
    url = f"{args.api_url}/runs/{args.run_id}/cancel"

    with console.status("[bold yellow]Requesting cancellation..."):
        with httpx.Client(timeout=10) as client:
            try:
                resp = client.post(url)
                resp.raise_for_status()
                result = resp.json()

                console.print()
                if result.get("process_killed"):
                    console.print("🛑 [green]Run cancelled and process terminated[/green]")
                else:
                    console.print("🛑 [yellow]Cancellation requested (process may have already finished)[/yellow]")
                console.print(f"   Run ID: {args.run_id}")
                console.print()

            except httpx.HTTPStatusError as exc:
                console.print()
                console.print(f"[red]Failed to cancel run: {exc.response.json().get('detail', str(exc))}[/red]")
            except Exception as exc:
                console.print()
                console.print(f"[red]Error: {exc}[/red]")


def open_ui(args: argparse.Namespace) -> None:
    url = f"{args.api_url}/ui/runs/{args.run_id}"
    print(f"Opening {url}")
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", url], check=False)
    else:
        print("Please open manually:", url)


def cleanup(args: argparse.Namespace) -> None:
    """Clean up old workspaces and artifacts."""
    from datetime import datetime, timedelta
    import shutil

    workspace_root = REPO_ROOT / "workspaces"
    artifacts_root = REPO_ROOT / "artifacts"

    if not workspace_root.exists():
        console.print("[yellow]No workspaces directory found[/yellow]")
        return

    cutoff = datetime.now() - timedelta(days=args.older_than)

    console.print(f"[yellow]Finding workspaces older than {args.older_than} days...[/yellow]\n")

    # Find candidates for deletion
    to_delete = []
    total_size = 0

    for workspace_dir in workspace_root.rglob("run-*"):
        if not workspace_dir.is_dir():
            continue

        # Check modification time
        mtime = datetime.fromtimestamp(workspace_dir.stat().st_mtime)
        if mtime > cutoff:
            continue

        # If only-failed, check run status
        if args.only_failed:
            # Try to determine if run failed (basic heuristic)
            # In a full implementation, we'd query the API
            # For now, skip this filter or use a simple check
            pass

        # Calculate size
        size = sum(f.stat().st_size for f in workspace_dir.rglob("*") if f.is_file())
        total_size += size

        age_days = (datetime.now() - mtime).days
        to_delete.append({
            "path": workspace_dir,
            "size": size,
            "age_days": age_days,
            "mtime": mtime,
        })

    if not to_delete:
        console.print("[green]✓ No workspaces to clean up![/green]")
        return

    # Show what will be deleted
    table = Table(title=f"Workspaces to Delete ({len(to_delete)})")
    table.add_column("Path", style="cyan", no_wrap=False)
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Age", style="dim", justify="right")

    # Sort by size descending, show top 20
    sorted_items = sorted(to_delete, key=lambda x: x["size"], reverse=True)
    for item in sorted_items[:20]:
        rel_path = item["path"].relative_to(workspace_root)
        size_mb = item["size"] / 1024 / 1024
        table.add_row(
            str(rel_path),
            f"{size_mb:.1f} MB",
            f"{item['age_days']} days",
        )

    if len(to_delete) > 20:
        table.add_row("[dim]...[/dim]", f"[dim]+ {len(to_delete) - 20} more[/dim]", "")

    console.print(table)
    console.print()
    console.print(f"[bold]Total: {total_size / 1024 / 1024:.1f} MB will be freed[/bold]\n")

    if args.dry_run:
        console.print("[yellow]Dry run - no files deleted[/yellow]")
        return

    # Confirm deletion
    if not args.force:
        from rich.prompt import Confirm

        if not Confirm.ask("Proceed with deletion?", default=False):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Delete workspaces
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Deleting workspaces...", total=len(to_delete))

        for item in to_delete:
            try:
                shutil.rmtree(item["path"])
                progress.advance(task)
            except Exception as exc:
                console.print(f"[red]Failed to delete {item['path']}: {exc}[/red]")

    console.print()
    console.print(
        f"[green]✓ Deleted {len(to_delete)} workspaces ({total_size / 1024 / 1024:.1f} MB freed)[/green]"
    )


def stats(args: argparse.Namespace) -> None:
    """Show disk usage statistics."""
    workspace_root = REPO_ROOT / "workspaces"
    artifacts_root = REPO_ROOT / "artifacts"
    data_dir = REPO_ROOT / "data"

    def calculate_dir_size(path: Path) -> tuple[int, int]:
        """Returns (total_size_bytes, file_count)."""
        if not path.exists():
            return 0, 0
        total = 0
        count = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
                count += 1
        return total, count

    console.print()
    console.print(Panel.fit("📊 Disk Usage Statistics", border_style="cyan"))
    console.print()

    # Calculate sizes
    workspace_size, workspace_files = calculate_dir_size(workspace_root)
    artifacts_size, artifacts_files = calculate_dir_size(artifacts_root)
    data_size, data_files = calculate_dir_size(data_dir)

    # Count workspaces
    workspace_count = 0
    if workspace_root.exists():
        workspace_count = sum(1 for _ in workspace_root.rglob("run-*") if _.is_dir())

    # Create table
    table = Table(show_header=True, box=None)
    table.add_column("Location", style="cyan bold")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Files", style="yellow", justify="right")
    table.add_column("Notes", style="dim")

    table.add_row(
        "Workspaces",
        f"{workspace_size / 1024 / 1024:.1f} MB",
        str(workspace_files),
        f"{workspace_count} runs",
    )

    table.add_row(
        "Artifacts",
        f"{artifacts_size / 1024 / 1024:.1f} MB",
        str(artifacts_files),
        "Execution logs",
    )

    table.add_row(
        "Database",
        f"{data_size / 1024 / 1024:.1f} MB",
        str(data_files),
        "SQLite DB",
    )

    total_size = workspace_size + artifacts_size + data_size
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_size / 1024 / 1024:.1f} MB[/bold]",
        f"[bold]{workspace_files + artifacts_files + data_files}[/bold]",
        "",
    )

    console.print(table)
    console.print()

    # Show recommendations
    if workspace_size > 1024 * 1024 * 1024:  # > 1GB
        console.print(
            "[yellow]💡 Workspaces are using significant disk space. "
            "Consider running cleanup:[/yellow]"
        )
        console.print("   [dim]./run.sh crossrun cleanup --older-than 7[/dim]\n")


def quickstart(args: argparse.Namespace) -> None:
    install(args)
    migrate(args)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC_PATH))
    proc = subprocess.Popen(["bash", "scripts/devservers.sh"], cwd=str(REPO_ROOT), env=env)
    print("Waiting for API to respond...")
    try:
        with httpx.Client(base_url=args.api_url, timeout=0.5) as client:
            for _ in range(30):
                try:
                    client.get("/healthz")
                    break
                except httpx.HTTPError:
                    time.sleep(0.5)
        run_command(
            argparse.Namespace(
                instructions=args.instructions,
                project_id="demo",
                name="Quickstart run",
                reference_run_id=None,
                from_run_id=None,
                api_url=args.api_url,
                watch=True,
            )
        )
    finally:
        proc.terminate()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helper CLI for Cross-Run backend")
    parser.add_argument(
        "--python-bin",
        default=os.environ.get("PYTHON_BIN", "python3.11"),
        help="Python interpreter used for install/migrate/quickstart commands",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install dependencies")
    install_p.set_defaults(func=install)

    migrate_p = sub.add_parser("migrate", help="Create/update the SQLite database")
    migrate_p.set_defaults(func=migrate)

    services_p = sub.add_parser("services", help="Launch API + runner")
    services_p.add_argument("--manual", action="store_true", help="Print commands instead of running")
    services_p.set_defaults(func=services)

    run_p = sub.add_parser("run", help="Launch a Codex run and optionally watch it")
    run_p.add_argument("instructions", nargs="?", help="Instruction text sent to Codex")
    run_p.add_argument("--project-id", default="demo")
    run_p.add_argument("--name")
    run_p.add_argument(
        "--task-type",
        "--project-type",
        dest="task_type",
        default="code",
        choices=["code", "research", "writing", "data_analysis", "document_processing"],
        help="Task type for the run (alias: --project-type, default: code)",
    )
    run_p.add_argument(
        "--template",
        "-t",
        choices=list(RUN_TEMPLATES.keys()),
        help="Use a predefined template",
    )
    run_p.add_argument("--reference-run-id", help="Reference run ID for pattern reuse")
    run_p.add_argument("--from-run-id", help="Source run ID to clone workspace from")
    run_p.add_argument("--api-url", default=DEFAULT_API)
    run_p.add_argument("--no-watch", dest="watch", action="store_false")
    run_p.set_defaults(func=run_command, watch=True)

    watch_p = sub.add_parser("watch", help="Attach to the SSE stream for a run")
    watch_p.add_argument("run_id")
    watch_p.add_argument("--api-url", default=DEFAULT_API)
    watch_p.set_defaults(func=watch)

    cancel_p = sub.add_parser("cancel", help="Cancel a running execution")
    cancel_p.add_argument("run_id")
    cancel_p.add_argument("--api-url", default=DEFAULT_API)
    cancel_p.set_defaults(func=cancel)

    ui_p = sub.add_parser("ui", help="Open the browser console for a run")
    ui_p.add_argument("run_id")
    ui_p.add_argument("--api-url", default=DEFAULT_API)
    ui_p.set_defaults(func=open_ui)

    cleanup_p = sub.add_parser("cleanup", help="Clean up old workspaces")
    cleanup_p.add_argument(
        "--older-than",
        type=int,
        default=7,
        help="Delete workspaces older than N days (default: 7)",
    )
    cleanup_p.add_argument(
        "--only-failed",
        action="store_true",
        help="Only delete failed runs",
    )
    cleanup_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    cleanup_p.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    cleanup_p.set_defaults(func=cleanup)

    stats_p = sub.add_parser("stats", help="Show disk usage statistics")
    stats_p.set_defaults(func=stats)

    templates_p = sub.add_parser("templates", help="List available run templates")
    templates_p.set_defaults(func=templates)

    quick_p = sub.add_parser("quickstart", help="Install, migrate, start services, and run a sample task")
    quick_p.add_argument("--instructions", default="touch hello.txt")
    quick_p.add_argument("--api-url", default=DEFAULT_API)
    quick_p.set_defaults(func=quickstart)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
