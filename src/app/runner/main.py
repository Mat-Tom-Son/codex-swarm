import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from swarm import Agent, Swarm

from ..config import settings
from ..domains import get_domain_config
from .codex_tool import codex_exec

app = FastAPI(title="Swarm Runner", version="0.1.0")
OPENAI_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
if OPENAI_KEY and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = OPENAI_KEY
USE_FAKE_SWARM = not OPENAI_KEY or os.getenv("CROSS_RUN_FAKE_SWARM") == "1"
client = None if USE_FAKE_SWARM else Swarm()


def _load_domain_instructions(task_type: str) -> str:
    """Load domain-specific instruction template from file."""
    domain_config = get_domain_config(task_type)
    instructions_path = (
        Path(__file__).parent.parent / "domains" / "instructions" / domain_config.instruction_template
    )

    if instructions_path.exists():
        return instructions_path.read_text().strip()

    # Fallback to basic code instructions
    return "You are a precise code agent. Keep changes minimal."


def build_instructions(context_variables: Dict[str, Any]) -> str:
    """
    Build complete system instructions from:
    1. Pattern block (from reference run)
    2. Domain-specific instructions (based on task_type)
    3. Tool usage guidelines
    """
    pattern_block = context_variables.get("pattern_block", "").strip()
    task_type = context_variables.get("task_type", "code")

    # Load domain-specific base instructions
    domain_instructions = _load_domain_instructions(task_type)

    tool_usage = """
Tooling contract:
- When the user asks for workspace changes or commands (edit files, run tests, inspect git, process documents, run scripts), ALWAYS call `codex_exec(prompt=...)`.
- Put the exact shell/script steps you need in the tool prompt (e.g., "touch hello.txt && git status" or "python analyze.py").
- Codex can execute Python scripts, run shell commands, edit files, and perform file operations.
- Only return a natural-language summary after at least one successful tool invocation, including key outcomes (files touched, command results).
- If the user request truly requires no changes (e.g., a conceptual answer), you may respond normally, but prefer the tool when unsure.
""".strip()

    parts = [part for part in (pattern_block, domain_instructions, tool_usage) if part]
    return "\n\n".join(parts)


builder = Agent(
    name="Builder",
    instructions=build_instructions,
    functions=[codex_exec],
)


class RunRequest(BaseModel):
    messages: List[Dict[str, Any]]
    context_variables: Dict[str, Any]
    max_turns: Optional[int] = 10


class RunResponse(BaseModel):
    messages: List[Dict[str, Any]]
    agent: Dict[str, Any]
    context_variables: Dict[str, Any]


@app.get("/healthz", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _fake_swarm_run(req: RunRequest) -> RunResponse:
    messages = list(req.messages)
    user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_prompt = msg.get("content", "")
            break
    summary = codex_exec(req.context_variables, user_prompt, req.context_variables.get("profile"))
    assistant_message = {"role": "assistant", "content": summary}
    messages.append(assistant_message)
    return RunResponse(
        messages=messages,
        agent={"name": "OfflineBuilder"},
        context_variables=req.context_variables,
    )


@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest) -> RunResponse:
    if client is None:
        return _fake_swarm_run(req)

    resp = client.run(
        agent=builder,
        messages=req.messages,
        context_variables=req.context_variables,
        max_turns=req.max_turns,
    )
    return RunResponse(
        messages=resp.messages,
        agent={"name": resp.agent.name},
        context_variables=resp.context_variables,
    )
