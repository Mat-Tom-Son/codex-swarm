from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(
        String, nullable=False, default="code"
    )  # code, research, writing, data_analysis, document_processing
    domain_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)

    runs: Mapped[list["Run"]] = relationship(back_populates="project")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="queued",
    )
    reference_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    workspace_from_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    system_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    codex_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="runs")
    steps: Mapped[list["Step"]] = relationship(back_populates="run")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    t: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    intent_target: Mapped[str | None] = mapped_column(String, nullable=True)
    intent_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_notes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tool_args_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["Run"] = relationship(back_populates="steps")


class PatternCache(Base):
    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_run_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
