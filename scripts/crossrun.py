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


def run_command(args: argparse.Namespace) -> None:
    payload = {
        "project_id": args.project_id,
        "name": args.name or args.instructions.splitlines()[0][:40] or "Run",
        "instructions": args.instructions,
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

                    else:
                        # Unknown event type, show as dim JSON
                        console.print(f"[dim]• {event_type}: {json.dumps(data)}[/dim]")

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Disconnected[/yellow]")
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
    run_p.add_argument("instructions", help="Instruction text sent to Codex")
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
    run_p.add_argument("--reference-run-id", help="Reference run ID for pattern reuse")
    run_p.add_argument("--from-run-id", help="Source run ID to clone workspace from")
    run_p.add_argument("--api-url", default=DEFAULT_API)
    run_p.add_argument("--no-watch", dest="watch", action="store_false")
    run_p.set_defaults(func=run_command, watch=True)

    watch_p = sub.add_parser("watch", help="Attach to the SSE stream for a run")
    watch_p.add_argument("run_id")
    watch_p.add_argument("--api-url", default=DEFAULT_API)
    watch_p.set_defaults(func=watch)

    ui_p = sub.add_parser("ui", help="Open the browser console for a run")
    ui_p.add_argument("run_id")
    ui_p.add_argument("--api-url", default=DEFAULT_API)
    ui_p.set_defaults(func=open_ui)

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
