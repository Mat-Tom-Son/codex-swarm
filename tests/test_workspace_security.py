from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services import run_service


def test_workspace_path_sanitizes_identifiers(tmp_path: Path) -> None:
    original_root = settings.workspace_root
    try:
        settings.workspace_root = tmp_path
        path = run_service._workspace_path("../evil..", "run/../../escape")
        assert path.is_relative_to(tmp_path)
        relative = path.relative_to(tmp_path)
        assert len(relative.parts) == 2
        assert ".." not in relative.parts
        assert "%2F" in relative.parts[0]
    finally:
        settings.workspace_root = original_root
