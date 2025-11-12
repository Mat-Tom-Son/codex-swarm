from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import httpx

from ..config import settings


async def invoke_run(
    run_id: str,
    project_id: str,
    user_prompt: str,
    pattern_block: str,
    workspace: Path,
    task_type: str = "code",
    profile: str | None = None,
) -> Dict[str, Any]:
    payload = {
        "messages": [{"role": "user", "content": user_prompt}],
        "context_variables": {
            "workspace": str(workspace),
            "pattern_block": pattern_block,
            "base_prompt": settings.base_prompt,
            "profile": profile or settings.codex_profile,
            "run_id": run_id,
            "project_id": project_id,
            "task_type": task_type,  # Pass task type to runner
        },
    }
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.post(f"{settings.runner_url}/run", json=payload)
        resp.raise_for_status()
        return resp.json()
