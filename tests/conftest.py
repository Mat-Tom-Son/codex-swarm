from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wait_for_health(url: str, timeout: float = 30.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
            continue
        time.sleep(0.2)
    raise RuntimeError(f"Service at {url} did not become healthy in time")


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _python_bin() -> str:
    env_bin = os.environ.get("PYTHON_BIN")
    if env_bin and shutil.which(env_bin):
        return env_bin
    for candidate in ("python3.11", "python3.12", "python3"):
        path = shutil.which(candidate)
        if path:
            return path
    return sys.executable


def _run_migrations(python_bin: str, env: dict[str, str]) -> None:
    subprocess.run(
        [python_bin, "-m", "app.migrations"],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_services(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    runtime_root = tmp_path_factory.mktemp("runtime")
    workspace_root = runtime_root / "workspaces"
    artifacts_root = runtime_root / "artifacts"
    workspace_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    api_port = _find_free_port()
    runner_port = _find_free_port()

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": f"src:{env.get('PYTHONPATH', '')}",
            "CROSS_RUN_DATABASE_PATH": str(runtime_root / "test.db"),
            "CROSS_RUN_WORKSPACE_ROOT": str(workspace_root),
            "CROSS_RUN_ARTIFACTS_ROOT": str(artifacts_root),
            "CROSS_RUN_FAKE_CODEX": "1",
            "CROSS_RUN_FAKE_SWARM": "1",
            # Force runner to skip git enforcement in case git is absent in CI.
            "CROSS_RUN_REQUIRE_GIT_REPO": "0",
            "OPENAI_API_KEY": "",
            "CROSS_RUN_RUNNER_URL": f"http://127.0.0.1:{runner_port}",
        }
    )

    processes: list[subprocess.Popen] = []
    try:
        python_bin = _python_bin()
        _run_migrations(python_bin, env)
        for port, target in (
            (api_port, "app.api.main:app"),
            (runner_port, "app.runner.main:app"),
        ):
            proc = subprocess.Popen(
                [
                    python_bin,
                    "-m",
                    "uvicorn",
                    target,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--app-dir",
                    "src",
                ],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(proc)

        _wait_for_health(f"http://127.0.0.1:{api_port}/healthz")
        _wait_for_health(f"http://127.0.0.1:{runner_port}/healthz")

        yield {
            "workspace_root": workspace_root,
            "artifacts_root": artifacts_root,
            "api_base": f"http://127.0.0.1:{api_port}",
            "runner_base": f"http://127.0.0.1:{runner_port}",
        }
    finally:
        for proc in processes:
            _terminate_process(proc)
