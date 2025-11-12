from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global configuration shared by API + runner services."""

    database_path: Path = Path("data/dev.db")
    workspace_root: Path = Path("workspaces")
    artifacts_root: Path = Path("artifacts")
    runner_url: str = "http://localhost:5055"
    codex_profile: str = "batch"
    codex_full_auto: bool = True
    base_prompt: str = "You are a precise code agent. Keep changes minimal."
    max_pattern_steps: int = 12
    max_pattern_tokens: int = 600
    pattern_summary_chars: int = 250
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    require_git_repo: bool = False

    class Config:
        env_prefix = "CROSS_RUN_"
        env_file = ".env"
        extra = "ignore"


settings = Settings()
