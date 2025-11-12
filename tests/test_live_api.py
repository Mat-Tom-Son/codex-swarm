from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest


async def _wait_for_run(client: httpx.AsyncClient, run_id: str) -> dict:
    for _ in range(120):
        resp = await client.get(f"/runs/{run_id}")
        resp.raise_for_status()
        body = resp.json()
        if body["status"] in {"succeeded", "failed"}:
            return body
        await asyncio.sleep(0.25)
    raise AssertionError(f"Run {run_id} did not finish in time")


def _workspace_path(workspace_root: Path, project_id: str, run_id: str) -> Path:
    return workspace_root / project_id / run_id


@pytest.mark.asyncio
async def test_run_lifecycle_and_workspace_clone(live_services: dict[str, Path]) -> None:
    project_id = "demo"
    async with httpx.AsyncClient(base_url=live_services["api_base"], timeout=30) as client:
        # Upsert project.
        resp = await client.put(
            f"/projects/{project_id}",
            json={"id": project_id, "name": "Demo Project"},
        )
        resp.raise_for_status()

        # Launch initial run.
        resp = await client.post(
            f"/projects/{project_id}/runs",
            json={
                "project_id": project_id,
                "name": "Baseline",
                "instructions": "touch hello.txt",
            },
        )
        resp.raise_for_status()
        baseline_run = resp.json()
        baseline_run = await _wait_for_run(client, baseline_run["id"])
        assert baseline_run["status"] == "succeeded"
        assert baseline_run["workspace_from_run_id"] is None

        # Tool step and artifact should exist for baseline run.
        steps_resp = await client.get(f"/runs/{baseline_run['id']}/steps")
        steps_resp.raise_for_status()
        step_roles = {step["role"] for step in steps_resp.json()}
        assert "tool" in step_roles

        artifacts_resp = await client.get(f"/runs/{baseline_run['id']}/artifacts")
        artifacts_resp.raise_for_status()
        artifacts = artifacts_resp.json()
        assert artifacts, "Expected Codex JSONL artifact to be registered"

        # Populate the workspace with a sentinel file to verify cloning later.
        workspace_root = live_services["workspace_root"]
        baseline_workspace = _workspace_path(workspace_root, project_id, baseline_run["id"])
        sentinel = baseline_workspace / "sentinel.txt"
        sentinel.write_text("baseline-state", encoding="utf-8")
        git_dir = baseline_workspace / ".git"
        baseline_git_exists = git_dir.exists()

        # Launch second run that clones from the first workspace.
        resp = await client.post(
            f"/projects/{project_id}/runs",
            json={
                "project_id": project_id,
                "name": "Clone",
                "instructions": "ls",
                "from_run_id": baseline_run["id"],
            },
        )
        resp.raise_for_status()
        clone_run = await _wait_for_run(client, resp.json()["id"])
        assert clone_run["status"] == "succeeded"
        assert clone_run["workspace_from_run_id"] == baseline_run["id"]

        clone_workspace = _workspace_path(workspace_root, project_id, clone_run["id"])
        clone_sentinel = clone_workspace / "sentinel.txt"
        assert clone_sentinel.exists(), "Clone should copy workspace files"
        assert clone_sentinel.read_text(encoding="utf-8") == "baseline-state"
        if baseline_git_exists:
            assert (clone_workspace / ".git").exists(), ".git should be carried over during cloning"

        # Ensure artifacts are still persisted for cloned run.
        clone_artifacts = await client.get(f"/runs/{clone_run['id']}/artifacts")
        clone_artifacts.raise_for_status()
        assert clone_artifacts.json(), "Clone run should still emit Codex JSONL artifacts"
