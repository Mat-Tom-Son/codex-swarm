"""
Example: Using Codex-Swarm as a DraftPunk backend

This demonstrates the DraftPunk client library for document workflows.
"""

import sys
import time
from pathlib import Path

# Add src to path so we can import draftpunk_client
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from draftpunk_client import CodexSwarmClient


def main():
    print("🔌 DraftPunk Client Example")
    print("=" * 50)

    # Initialize client
    client = CodexSwarmClient(base_url="http://localhost:5050")

    # Start a simple document writing task
    print("\n📝 Starting document writing task...")
    run = client.start_run(
        project_id="draftpunk-demo",
        instructions="Create a simple markdown file called hello.md with a greeting",
        task_type="document_writing",
        name="Hello World Document",
    )

    print(f"✓ Run created: {run.run_id}")
    print(f"  Project: {run.project_id}")
    print(f"  Task Type: {run.task_type}")
    print(f"  Status: {run.status}")
    print(f"  Progress: {run.progress}%")

    # Poll for completion
    print("\n⏳ Waiting for completion...")
    max_wait = 60  # seconds
    start_time = time.time()

    while run.status in ("queued", "running"):
        if time.time() - start_time > max_wait:
            print("⚠️  Timeout waiting for run to complete")
            client.cancel_run(run.run_id)
            return

        time.sleep(2)
        run = client.get_run(run.run_id)
        print(f"  [{run.progress:3d}%] {run.status}")

    # Check results
    print(f"\n✅ Run completed with status: {run.status}")

    if run.had_errors:
        print("\n❌ Errors occurred:")
        for error in run.errors:
            print(f"  • {error.error_type}: {error.message}")
            print(f"    Step: {error.step}, Tool: {error.tool}")
    else:
        print("✓ No errors")

    # Display machine summary
    if run.machine_summary:
        summary = run.machine_summary
        print("\n📊 Machine Summary:")
        print(f"  Goal: {summary.goal}")
        print(f"  Execution attempted: {summary.execution_attempted}")
        print(f"  Execution succeeded: {summary.execution_succeeded}")
        print(f"  Primary artifact: {summary.primary_artifact}")
        if summary.secondary_artifacts:
            print(f"  Secondary artifacts: {', '.join(summary.secondary_artifacts)}")
        if summary.notes:
            print(f"  Notes: {summary.notes}")

    # List workspace files
    print("\n📁 Workspace Files:")
    files = client.list_files(run.run_id)
    print(f"  Total: {files.total_files} files")
    for file in files.files[:10]:  # Show first 10
        size_kb = file.size_bytes / 1024
        print(f"  • {file.path} ({size_kb:.1f}KB, {file.type})")

    # Download a file if available
    if run.machine_summary and run.machine_summary.primary_artifact:
        artifact_path = run.machine_summary.primary_artifact
        print(f"\n📄 Downloading {artifact_path}...")
        try:
            content = client.get_file_text(run.run_id, artifact_path)
            print("─" * 50)
            print(content[:500])  # Show first 500 chars
            if len(content) > 500:
                print("...")
            print("─" * 50)
        except Exception as e:
            print(f"  ⚠️  Could not download: {e}")

    print("\n✨ Example complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
