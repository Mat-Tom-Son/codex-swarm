# Codex-Swarm Application Audit Report

**Date:** 2025-11-12
**Auditor:** Claude (Sonnet 4.5)
**Scope:** Security Hardening & User Experience Improvements

---

## Executive Summary

Codex-Swarm is a well-architected automation system that combines OpenAI Swarm and Anthropic Codex with pattern learning capabilities. The codebase demonstrates solid engineering practices with path traversal protection, workspace isolation, and comprehensive test coverage. However, there are opportunities to enhance security posture and significantly improve user experience.

**Key Findings:**
- ✅ Good workspace isolation with path traversal prevention
- ⚠️ No authentication/authorization on API endpoints
- ⚠️ Limited input validation and rate limiting
- ⚠️ Sensitive data exposure risks (API keys, workspace contents)
- 💡 UX can be significantly enhanced with better error handling and feedback
- 💡 Pattern extraction and observability can be improved

---

## 🔒 Security Findings & Recommendations

### CRITICAL Priority

#### 1. API Authentication & Authorization
**Current State:** No authentication on any API endpoints (ports 5050, 5055)

**Risk:**
- Anyone with network access can create/delete projects and runs
- Potential for resource exhaustion attacks
- Unauthorized access to workspace contents and artifacts
- Exposure of execution logs and git diffs

**Recommendations:**

**Quick Win - API Key Authentication:**
```python
# src/app/api/deps.py
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from ..config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not settings.api_key:
        # Authentication disabled if no key configured
        return

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
```

Add to config.py:
```python
api_key: str | None = Field(default=None, alias="API_KEY")
require_auth: bool = Field(default=False, alias="REQUIRE_AUTH")
```

Apply to routes:
```python
# src/app/api/routes/*.py
@router.post("/projects/{project_id}/runs", dependencies=[Depends(verify_api_key)])
```

**Long-term - OAuth2/JWT:**
- Implement user-based authentication
- Role-based access control (RBAC)
- Per-project permissions
- Audit logging of all API access

---

#### 2. Input Validation & Sanitization
**Current State:** Limited validation on user inputs

**Risk:**
- SQL injection potential (mitigated by SQLAlchemy, but not eliminated)
- Command injection through workspace operations
- Path traversal through project_id/run_id manipulation
- XSS in UI console

**Recommendations:**

```python
# src/app/schemas.py
from pydantic import BaseModel, Field, validator
import re

class ProjectCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, regex=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(..., min_length=1, max_length=200)
    task_type: str = Field(default="code", regex=r'^(code|research|writing|data_analysis|document_processing)$')

    @validator('id')
    def validate_id(cls, v):
        if v in ['..', '.', 'admin', 'root']:
            raise ValueError('Reserved identifier')
        return v

class RunCreate(BaseModel):
    instructions: str = Field(..., min_length=1, max_length=10000)

    @validator('instructions')
    def sanitize_instructions(cls, v):
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'rm\s+-rf\s+/',
            r'mkfs\.',
            r'dd\s+if=/dev/zero',
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Instructions contain potentially dangerous commands')
        return v
```

**XSS Protection for UI:**
```python
# src/app/api/routes/ui.py
import html

def escape_html(text: str) -> str:
    return html.escape(text)

@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_console(run_id: str) -> HTMLResponse:
    # Validate and escape run_id
    safe_run_id = escape_html(run_id)
    if not re.match(r'^run-[a-z0-9]+$', run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    # ... rest of function
```

---

#### 3. Secrets Management
**Current State:** API keys stored in environment variables and passed through subprocess environments

**Risk:**
- Secrets exposed in logs
- Secrets leaked through error messages
- Secrets visible in process listings

**Recommendations:**

```python
# src/app/config.py
from pathlib import Path
import os

class Settings(BaseSettings):
    # Support for secrets files (Docker/Kubernetes style)
    openai_api_key: str | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Try to load from secrets file if not set
        if not self.openai_api_key:
            secret_file = Path("/run/secrets/openai_api_key")
            if secret_file.exists():
                self.openai_api_key = secret_file.read_text().strip()

# src/app/runner/codex_tool.py
def _build_codex_env() -> dict[str, str]:
    env = os.environ.copy()
    key = settings.openai_api_key
    if key:
        env["OPENAI_API_KEY"] = key
    # Sanitize environment - remove other sensitive vars
    sensitive_keys = [k for k in env.keys() if 'SECRET' in k or 'PASSWORD' in k or 'TOKEN' in k]
    for k in sensitive_keys:
        if k != "OPENAI_API_KEY":
            env.pop(k, None)
    return env
```

**Use a proper secrets manager:**
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Kubernetes Secrets

---

#### 4. Rate Limiting & Resource Protection
**Current State:** No rate limiting or resource quotas

**Risk:**
- Denial of service through excessive run creation
- Disk space exhaustion from workspace/artifact creation
- API flooding

**Recommendations:**

```python
# src/app/middleware/rate_limit.py
from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, identifier: str, max_requests: int = 60, window: int = 60):
        """Allow max_requests per window seconds"""
        async with self._lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window)

            # Clean old requests
            self._requests[identifier] = [
                req_time for req_time in self._requests[identifier]
                if req_time > cutoff
            ]

            if len(self._requests[identifier]) >= max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_requests} requests per {window}s"
                )

            self._requests[identifier].append(now)

rate_limiter = RateLimiter()

# src/app/api/main.py
from fastapi import Request

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Use IP address as identifier (or API key if authenticated)
    identifier = request.client.host if request.client else "unknown"

    # Different limits for different endpoints
    if request.url.path.startswith("/projects/") and request.method == "POST":
        await rate_limiter.check_rate_limit(identifier, max_requests=10, window=60)

    response = await call_next(request)
    return response
```

**Workspace Quota Management:**
```python
# src/app/config.py
max_workspace_size_mb: int = 1000  # 1GB per workspace
max_total_workspaces: int = 100
max_artifact_size_mb: int = 100

# src/app/services/run_service.py
def _check_workspace_quota(project_id: str) -> None:
    """Enforce workspace quotas"""
    workspace_root = settings.workspace_root.resolve()

    # Check total workspace count
    workspace_count = sum(1 for _ in workspace_root.rglob("*") if _.is_dir())
    if workspace_count >= settings.max_total_workspaces:
        raise ValueError(f"Workspace limit reached ({settings.max_total_workspaces})")

    # Check disk usage
    total_size = sum(f.stat().st_size for f in workspace_root.rglob("*") if f.is_file())
    total_size_mb = total_size / (1024 * 1024)
    if total_size_mb > (settings.max_total_workspaces * settings.max_workspace_size_mb):
        raise ValueError("Disk quota exceeded")
```

---

### HIGH Priority

#### 5. Workspace Isolation Enhancements
**Current State:** Good path traversal protection, but workspace processes share system resources

**Risk:**
- Resource exhaustion from runaway processes
- Potential for workspace-to-workspace interference
- No memory/CPU limits

**Recommendations:**

```python
# src/app/runner/codex_tool.py
import resource

def _set_resource_limits():
    """Set resource limits for subprocess execution"""
    try:
        # Limit CPU time to 30 minutes
        resource.setrlimit(resource.RLIMIT_CPU, (1800, 1800))

        # Limit memory to 2GB
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024))

        # Limit file size to 500MB
        resource.setrlimit(resource.RLIMIT_FSIZE, (500 * 1024 * 1024, 500 * 1024 * 1024))

        # Limit number of open files
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))
    except Exception:
        pass  # May fail on some systems

def codex_exec(...):
    # ... existing code ...
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
        preexec_fn=_set_resource_limits,  # Add resource limits
    )
```

**Docker/Container Isolation (Recommended):**
```python
# Use Docker for true isolation
def codex_exec_containerized(context_variables, prompt, profile=None):
    """Execute codex in isolated container"""
    workspace = context_variables["workspace"]

    cmd = [
        "docker", "run",
        "--rm",
        "--network", "none",  # No network access
        "--memory", "2g",     # Memory limit
        "--cpus", "2",        # CPU limit
        "--read-only",        # Read-only filesystem except volumes
        "-v", f"{workspace}:/workspace",
        "-w", "/workspace",
        "codex-runner:latest",
        "codex", "exec", "--json", prompt
    ]
    # ... rest of implementation
```

---

#### 6. Artifact Security & Access Control
**Current State:** Artifacts stored on filesystem with no access control beyond file system permissions

**Risk:**
- Unauthorized access to execution logs
- Exposure of sensitive data in git diffs
- No encryption at rest

**Recommendations:**

```python
# src/app/api/routes/runs.py
from ..deps import verify_api_key

@router.get("/{run_id}/artifacts/{artifact_id}/download", dependencies=[Depends(verify_api_key)])
async def download_artifact(
    run_id: str,
    artifact_id: str,
    session: AsyncSession = Depends(db_session),
):
    # Add artifact access logging
    logger.info(f"Artifact download: run={run_id}, artifact={artifact_id}")

    # Validate artifact contains no secrets before serving
    artifact_path = Path(artifact.path)
    content = artifact_path.read_text()

    # Check for potential secrets
    if _contains_secrets(content):
        logger.warning(f"Artifact contains potential secrets: {artifact_id}")
        # Optionally redact or deny access

    return FileResponse(...)

def _contains_secrets(content: str) -> bool:
    """Check for common secret patterns"""
    patterns = [
        r'sk-[a-zA-Z0-9]{32,}',  # OpenAI keys
        r'AKIA[0-9A-Z]{16}',      # AWS keys
        r'-----BEGIN PRIVATE KEY-----',
    ]
    return any(re.search(p, content) for p in patterns)
```

**Encryption at rest:**
```python
# src/app/services/artifact_encryption.py
from cryptography.fernet import Fernet
from pathlib import Path

class ArtifactEncryption:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)

    def encrypt_file(self, path: Path) -> Path:
        """Encrypt artifact file"""
        content = path.read_bytes()
        encrypted = self.cipher.encrypt(content)
        encrypted_path = path.with_suffix(path.suffix + '.enc')
        encrypted_path.write_bytes(encrypted)
        path.unlink()  # Remove unencrypted file
        return encrypted_path

    def decrypt_file(self, path: Path) -> bytes:
        """Decrypt artifact for serving"""
        encrypted = path.read_bytes()
        return self.cipher.decrypt(encrypted)
```

---

#### 7. SQL Injection Prevention (Defense in Depth)
**Current State:** Using SQLAlchemy ORM provides good protection, but raw queries could be risky

**Risk:** Low (using ORM), but defense in depth is important

**Recommendations:**

```python
# Ensure parameterized queries everywhere
# Good example from codebase:
run = await repositories.runs.get_run(session, run_id)  # ✓ Safe

# If you ever need raw SQL:
from sqlalchemy import text

# Bad:
query = f"SELECT * FROM runs WHERE id = '{run_id}'"  # ✗ Vulnerable

# Good:
query = text("SELECT * FROM runs WHERE id = :run_id")
result = await session.execute(query, {"run_id": run_id})  # ✓ Safe
```

**Enable SQL query logging in dev:**
```python
# src/app/database.py
import os

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG") == "1",  # Enable query logging
    future=True,
)
```

---

### MEDIUM Priority

#### 8. CORS Configuration
**Current State:** No CORS configuration visible

**Risk:** If API is accessed from browser, need proper CORS

**Recommendations:**

```python
# src/app/api/main.py
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Cross-Run Context API", version="0.1.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend dev server
        "https://yourdomain.com",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight requests
)
```

---

#### 9. Error Information Disclosure
**Current State:** Detailed errors may leak system information

**Risk:** Stack traces and system paths exposed to clients

**Recommendations:**

```python
# src/app/api/main.py
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions"""
    # Log full error server-side
    logger.exception(f"Unhandled exception: {exc}")

    # Return sanitized error to client
    if settings.debug:
        # In development, return full error
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    else:
        # In production, return generic error
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": str(uuid4())}
        )

# Add to config
debug: bool = Field(default=False, alias="DEBUG")
```

---

## 💡 User Experience Improvements

### HIGH Priority UX Enhancements

#### 1. Enhanced Error Messages & Recovery
**Current State:** Basic error handling, limited user guidance

**Improvements:**

```python
# src/app/services/run_service.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class RunError:
    code: str
    message: str
    recovery_suggestion: str
    docs_link: Optional[str] = None

ERROR_CATALOG = {
    "codex-cli-not-found": RunError(
        code="CODEX_NOT_INSTALLED",
        message="Codex CLI is not installed or not in PATH",
        recovery_suggestion="Install Codex CLI: https://docs.claude.com/claude-code",
        docs_link="https://docs.claude.com/claude-code/installation"
    ),
    "codex-login-required": RunError(
        code="CODEX_AUTH_REQUIRED",
        message="Codex CLI is not authenticated",
        recovery_suggestion="Set OPENAI_API_KEY environment variable or run 'codex login'",
        docs_link="https://docs.claude.com/claude-code/authentication"
    ),
    "workspace-quota-exceeded": RunError(
        code="QUOTA_EXCEEDED",
        message="Workspace quota exceeded",
        recovery_suggestion="Clean up old workspaces or increase quota in settings",
    ),
}

async def launch_run(...):
    try:
        # ... existing code ...
    except Exception as exc:
        error_key = _extract_error_key(exc)
        if error_key in ERROR_CATALOG:
            error_info = ERROR_CATALOG[error_key]
            await run_events.publish(run.id, {
                "type": "error",
                "error": {
                    "code": error_info.code,
                    "message": error_info.message,
                    "recovery": error_info.recovery_suggestion,
                    "docs": error_info.docs_link,
                }
            })
        raise
```

---

#### 2. Progress Indicators & ETA
**Current State:** Event streaming exists but limited progress indication

**Improvements:**

```python
# src/app/services/run_service.py
import time

async def launch_run(...):
    start_time = time.time()

    # Publish progress events
    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "initializing",
        "percent": 0,
        "message": "Preparing workspace..."
    })

    workspace, cloned_entries, source_found = _prepare_workspace(...)

    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "workspace_ready",
        "percent": 20,
        "message": "Workspace prepared",
        "elapsed": time.time() - start_time
    })

    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "executing",
        "percent": 40,
        "message": "Running Codex agent..."
    })

    runner_response = await runner_client.invoke_run(...)

    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "extracting_patterns",
        "percent": 80,
        "message": "Extracting patterns..."
    })

    await pattern_agent.fetch_pattern(session, run.id)

    await run_events.publish(run.id, {
        "type": "progress",
        "stage": "complete",
        "percent": 100,
        "message": "Run completed",
        "elapsed": time.time() - start_time
    })
```

**Enhanced UI Console:**
```html
<!-- src/app/api/routes/ui.py -->
<div id='progress-bar' style='width:100%; height:4px; background:#1f2937; margin:16px 0;'>
  <div id='progress-fill' style='width:0%; height:100%; background:#10b981; transition:width 0.3s;'></div>
</div>
<div id='status-message' style='margin:8px 0; color:#9ca3af;'></div>

<script>
source.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);

  if (payload.type === 'progress') {
    const fill = document.getElementById('progress-fill');
    const msg = document.getElementById('status-message');
    fill.style.width = payload.percent + '%';
    msg.textContent = payload.message;

    if (payload.elapsed) {
      msg.textContent += ` (${payload.elapsed.toFixed(1)}s)`;
    }
  }

  // ... rest of handler
});
</script>
```

---

#### 3. Run Cancellation & Control
**Current State:** No way to cancel a running execution

**Improvements:**

```python
# src/app/models.py
# Add cancellation flag to Run model
class Run(Base):
    # ... existing fields ...
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[str | None] = mapped_column(String, nullable=True)

# src/app/api/routes/runs.py
@router.post("/{run_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    """Request cancellation of a running execution"""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail="Run is not active")

    # Set cancellation flag
    run.cancellation_requested = True
    run.cancelled_at = datetime.utcnow().isoformat() + "Z"
    await session.commit()

    await run_events.publish(run_id, {
        "type": "cancellation_requested",
        "run_id": run_id,
    })

    return {"status": "cancellation_requested"}

# src/app/runner/codex_tool.py
def codex_exec(...):
    # Store process handle for cancellation
    run_id = context_variables["run_id"]
    _active_processes[run_id] = proc

    try:
        for line in proc.stdout:
            # Check for cancellation
            if _should_cancel(run_id):
                proc.terminate()
                return "codex_exec(cancelled)"
            # ... rest of processing
    finally:
        _active_processes.pop(run_id, None)
```

---

#### 4. Workspace Management UI
**Current State:** Workspaces are filesystem directories with no UI

**Improvements:**

```python
# src/app/api/routes/runs.py
@router.get("/{run_id}/workspace/files")
async def list_workspace_files(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    """List files in run workspace"""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    workspace = run_service._workspace_path(run.project_id, run.id)

    if not workspace.exists():
        return {"files": []}

    files = []
    for path in workspace.rglob("*"):
        if path.is_file():
            rel_path = path.relative_to(workspace)
            files.append({
                "path": str(rel_path),
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
                "is_git": str(rel_path).startswith(".git/")
            })

    return {"files": sorted(files, key=lambda f: f["path"])}

@router.get("/{run_id}/workspace/files/{file_path:path}")
async def download_workspace_file(
    run_id: str,
    file_path: str,
    session: AsyncSession = Depends(db_session),
):
    """Download a specific file from workspace"""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    workspace = run_service._workspace_path(run.project_id, run.id)
    full_path = (workspace / file_path).resolve()

    # Security check
    if not full_path.is_relative_to(workspace):
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)
```

---

#### 5. Pattern Visualization & Editing
**Current State:** Patterns are extracted automatically but not easily visible or editable

**Improvements:**

```python
# src/app/api/routes/patterns.py
@router.get("/{pattern_id}/preview")
async def preview_pattern(
    pattern_id: str,
    session: AsyncSession = Depends(db_session),
):
    """Get human-readable pattern preview"""
    cache = await repositories.patterns.get_cached_pattern(session, pattern_id)
    if not cache:
        raise HTTPException(status_code=404, detail="Pattern not found")

    pattern = pattern_service.pattern_from_cache(cache)

    return {
        "id": pattern.id,
        "name": pattern.name,
        "summary": pattern.summary,
        "steps": [
            {
                "order": i + 1,
                "description": step["description"],
                "action_type": step.get("action_type", "unknown")
            }
            for i, step in enumerate(pattern.steps)
        ],
        "variables": [
            {
                "name": key,
                "type": var.get("type", "string"),
                "example": var.get("example", ""),
                "description": var.get("description", "")
            }
            for key, var in pattern.variables.items()
        ],
        "usage_count": 0,  # TODO: Track pattern usage
        "success_rate": 0.0,  # TODO: Track pattern success
    }

@router.put("/{pattern_id}")
async def update_pattern(
    pattern_id: str,
    updates: PatternUpdate,
    session: AsyncSession = Depends(db_session),
):
    """Allow manual pattern refinement"""
    cache = await repositories.patterns.get_cached_pattern(session, pattern_id)
    if not cache:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Update pattern fields
    if updates.name:
        cache.name = updates.name
    if updates.summary:
        cache.summary = updates.summary
    # ... update other fields

    await session.commit()
    return {"status": "updated"}
```

---

#### 6. Better CLI Experience
**Current State:** Good CLI but could be more user-friendly

**Improvements:**

```python
# scripts/crossrun.py
import rich
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def run_command(args: argparse.Namespace) -> None:
    # Show a nice spinner while creating run
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating run...", total=None)

        # Create run
        resp = client.post(f"/projects/{args.project_id}/runs", json=payload)
        resp.raise_for_status()
        run = resp.json()

        progress.update(task, description="✓ Run created")

    # Show run info in a nice table
    table = Table(title=f"Run {run['id']}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("ID", run["id"])
    table.add_row("Project", args.project_id)
    table.add_row("Status", run["status"])
    table.add_row("Workspace", f"workspaces/{safe_project}/{safe_run}")

    console.print(table)

    if args.watch:
        console.print("\n[yellow]Streaming events (Ctrl+C to stop)...[/yellow]\n")
        watch(args=argparse.Namespace(run_id=run_id, api_url=args.api_url))

def watch(args: argparse.Namespace) -> None:
    """Enhanced event watching with rich formatting"""
    url = f"{args.api_url}/runs/{args.run_id}/stream"

    with httpx.Client(timeout=None) as client:
        with client.stream("GET", url) as response:
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = json.loads(line.removeprefix("data:").strip())
                event_type = data.get('type', 'event')

                # Format events nicely
                if event_type == "status":
                    status = data.get("status", "unknown")
                    color = "green" if status == "succeeded" else "red" if status == "failed" else "yellow"
                    console.print(f"[{color}]● Status: {status}[/{color}]")

                elif event_type == "step":
                    role = data.get("role", "")
                    content = data.get("content", "")[:100]
                    console.print(f"[blue]→ {role}:[/blue] {content}...")

                elif event_type == "artifact":
                    path = data.get("path", "")
                    console.print(f"[green]📄 Artifact saved:[/green] {path}")

                else:
                    console.print(f"[dim]• {event_type}[/dim]")
```

---

#### 7. Dashboard & Analytics
**Current State:** No overview of runs, projects, or system health

**Improvements:**

```python
# src/app/api/routes/dashboard.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(
    session: AsyncSession = Depends(db_session),
):
    """Get system-wide statistics"""

    # Count runs by status
    from sqlalchemy import func, select

    run_counts = await session.execute(
        select(Run.status, func.count(Run.id))
        .group_by(Run.status)
    )

    # Recent runs
    recent_runs = await repositories.runs.list_runs(session, limit=10)

    # Workspace usage
    workspace_root = settings.workspace_root
    total_size = sum(f.stat().st_size for f in workspace_root.rglob("*") if f.is_file())

    # Pattern library size
    patterns_count = await session.execute(select(func.count(PatternCache.id)))

    return {
        "runs": {
            "total": sum(count for _, count in run_counts),
            "by_status": {status: count for status, count in run_counts},
            "recent": [_run_to_read(r) for r in recent_runs],
        },
        "storage": {
            "workspace_bytes": total_size,
            "workspace_mb": total_size / (1024 * 1024),
        },
        "patterns": {
            "count": patterns_count.scalar(),
        },
    }
```

**Simple dashboard UI:**
```html
<!-- Add to src/app/api/routes/ui.py -->
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    # Serve a simple dashboard showing system stats
    # ... implementation
```

---

### MEDIUM Priority UX Enhancements

#### 8. Run Templates & Presets
**Current State:** Users must write instructions from scratch

**Improvements:**

```python
# Add template system
TEMPLATES = {
    "test": "Run the test suite and report any failures",
    "lint": "Run code linting and fix any issues",
    "doc": "Generate documentation for the codebase",
    "analyze": "Analyze the code for potential issues and suggest improvements",
    "refactor": "Refactor the code to improve maintainability",
}

# CLI support
run_p.add_argument("--template", choices=TEMPLATES.keys(), help="Use a predefined template")

def run_command(args):
    instructions = args.instructions
    if args.template:
        instructions = TEMPLATES[args.template]
    # ... rest
```

---

#### 9. Workspace Cleanup Tools
**Current State:** Workspaces accumulate forever

**Improvements:**

```python
# scripts/crossrun.py
cleanup_p = sub.add_parser("cleanup", help="Clean up old workspaces")
cleanup_p.add_argument("--older-than", type=int, default=7, help="Days")
cleanup_p.add_argument("--failed-only", action="store_true")
cleanup_p.add_argument("--dry-run", action="store_true")
cleanup_p.set_defaults(func=cleanup_workspaces)

def cleanup_workspaces(args):
    """Clean up old workspaces"""
    workspace_root = Path("workspaces")
    cutoff = datetime.now() - timedelta(days=args.older_than)

    # Find old workspaces
    for workspace in workspace_root.rglob("run-*"):
        if not workspace.is_dir():
            continue

        mtime = datetime.fromtimestamp(workspace.stat().st_mtime)
        if mtime > cutoff:
            continue

        # Check if run failed (if --failed-only)
        if args.failed_only:
            # Query API for run status
            pass

        if args.dry_run:
            print(f"Would delete: {workspace}")
        else:
            shutil.rmtree(workspace)
            print(f"Deleted: {workspace}")
```

---

#### 10. Notification System
**Current State:** Must actively monitor runs

**Improvements:**

```python
# Add webhook notifications
class Settings(BaseSettings):
    # ... existing fields ...
    webhook_url: str | None = None
    slack_webhook_url: str | None = None

async def _update_status(session: AsyncSession, run_id: str, status: str) -> None:
    # ... existing code ...

    # Send notifications
    if status in ["succeeded", "failed"] and settings.webhook_url:
        await _send_webhook_notification(run_id, status)

async def _send_webhook_notification(run_id: str, status: str):
    """Send webhook when run completes"""
    if not settings.webhook_url:
        return

    payload = {
        "run_id": run_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "url": f"{settings.api_url}/runs/{run_id}",
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.webhook_url, json=payload, timeout=5.0)
    except Exception:
        logger.exception("Failed to send webhook")
```

---

## 📊 Implementation Priority Matrix

### Quick Wins (High Impact, Low Effort)
1. ✅ Add API key authentication (1-2 hours)
2. ✅ Add input validation with Pydantic (2-3 hours)
3. ✅ Add rate limiting middleware (2-3 hours)
4. ✅ Enhanced error messages (2-3 hours)
5. ✅ Progress indicators (2-3 hours)
6. ✅ CLI improvements with rich (1-2 hours)

**Total: ~1-2 days of work**

### High Value (High Impact, Medium Effort)
1. Run cancellation (4-6 hours)
2. Workspace file browser API (4-6 hours)
3. Resource limits on subprocesses (3-4 hours)
4. CORS configuration (1 hour)
5. Dashboard stats endpoint (4-6 hours)
6. Cleanup tools (3-4 hours)

**Total: ~3-4 days of work**

### Long-term (High Impact, High Effort)
1. Full OAuth2/JWT authentication (1-2 weeks)
2. Docker-based workspace isolation (1-2 weeks)
3. Artifact encryption (3-5 days)
4. Pattern visualization UI (1-2 weeks)
5. Comprehensive monitoring/observability (1-2 weeks)
6. Role-based access control (1-2 weeks)

**Total: ~8-12 weeks of work**

---

## 🚀 Recommended Implementation Roadmap

### Phase 1: Security Fundamentals (Week 1-2)
- [ ] API key authentication
- [ ] Input validation
- [ ] Rate limiting
- [ ] Error handling improvements
- [ ] Secrets management review

### Phase 2: UX Essentials (Week 3-4)
- [ ] Progress indicators
- [ ] Enhanced CLI with rich
- [ ] Run cancellation
- [ ] Better error messages
- [ ] Cleanup tools

### Phase 3: Advanced Features (Week 5-8)
- [ ] Workspace file browser
- [ ] Dashboard & analytics
- [ ] Pattern visualization
- [ ] Resource limits
- [ ] Notification webhooks

### Phase 4: Production Hardening (Week 9-12)
- [ ] Docker isolation
- [ ] Comprehensive monitoring
- [ ] Artifact encryption
- [ ] Full audit logging
- [ ] Load testing & optimization

---

## 📝 Configuration Checklist for Production

### Before deploying to production:

```bash
# .env.production
CROSS_RUN_REQUIRE_AUTH=true
API_KEY=<generate-strong-random-key>
OPENAI_API_KEY=<your-key>

# Security
CROSS_RUN_DEBUG=false
CROSS_RUN_REQUIRE_GIT_REPO=true

# Resource limits
CROSS_RUN_MAX_WORKSPACE_SIZE_MB=1000
CROSS_RUN_MAX_TOTAL_WORKSPACES=100
CROSS_RUN_MAX_ARTIFACT_SIZE_MB=100

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_RUNS_PER_HOUR=10

# Database
CROSS_RUN_DATABASE_PATH=/var/lib/codex-swarm/production.db

# Workspaces & Artifacts
CROSS_RUN_WORKSPACE_ROOT=/var/lib/codex-swarm/workspaces
CROSS_RUN_ARTIFACTS_ROOT=/var/lib/codex-swarm/artifacts

# Notifications (optional)
WEBHOOK_URL=https://your-webhook-endpoint.com/notify
```

### Security checklist:
- [ ] API authentication enabled
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Debug mode disabled
- [ ] Secrets stored securely (not in .env)
- [ ] Database backups configured
- [ ] Workspace quotas enforced
- [ ] Artifact encryption enabled
- [ ] All endpoints behind auth
- [ ] HTTPS/TLS enabled
- [ ] Firewall rules configured
- [ ] Audit logging enabled

---

## 🎯 Summary

**Current State:**
Codex-Swarm is a well-designed system with solid fundamentals. The architecture is clean, workspace isolation is implemented, and the pattern learning concept is innovative.

**Security Posture:**
- ⚠️ Currently suitable for **trusted, internal use only**
- ⚠️ **NOT production-ready** for public/untrusted environments
- ⚠️ Missing authentication, authorization, and many security controls

**User Experience:**
- ✅ Good foundation with CLI and API
- ⚠️ Limited visibility into run progress
- ⚠️ No workspace management UI
- ⚠️ Error messages could be more helpful

**Priority Actions:**
1. **Immediate**: Add API authentication (< 1 day)
2. **Short-term**: Input validation + rate limiting (< 1 week)
3. **Medium-term**: UX improvements + run control (2-4 weeks)
4. **Long-term**: Full production hardening (8-12 weeks)

With the recommended security improvements, Codex-Swarm can safely move to production environments. The UX improvements will make it significantly more user-friendly and valuable for teams.

---

**Questions or need clarification on any recommendations? Let me know!**
