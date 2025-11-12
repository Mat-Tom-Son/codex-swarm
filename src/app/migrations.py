from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from .config import settings
from .database import Base
from . import models  # noqa: F401  # ensures models register with Base


def init_db(path: Path | None = None) -> None:
    """Create all tables defined in the ORM metadata."""
    db_path = path or settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # Migration: Add workspace_from_run_id to runs table
        columns = {col["name"] for col in inspect(conn).get_columns("runs")}
        if "workspace_from_run_id" not in columns:
            conn.execute(text("ALTER TABLE runs ADD COLUMN workspace_from_run_id VARCHAR"))

        # Migration: Ensure task_type/domain_config exist on projects table
        inspector = inspect(conn)
        project_columns = {col["name"] for col in inspector.get_columns("projects")}
        if "task_type" not in project_columns:
            if "project_type" in project_columns:
                conn.execute(text("ALTER TABLE projects RENAME COLUMN project_type TO task_type"))
            else:
                conn.execute(text("ALTER TABLE projects ADD COLUMN task_type VARCHAR NOT NULL DEFAULT 'code'"))
            project_columns = {col["name"] for col in inspector.get_columns("projects")}
        if "domain_config" not in project_columns:
            conn.execute(text("ALTER TABLE projects ADD COLUMN domain_config JSON"))


if __name__ == "__main__":
    init_db()
