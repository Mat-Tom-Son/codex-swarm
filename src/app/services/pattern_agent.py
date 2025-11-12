from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .. import repositories
from ..domains import get_domain_config
from ..events import run_events
from ..models import PatternCache
from ..services import patterns as pattern_service
from ..services.patterns.extractors import get_extractor

logger = logging.getLogger(__name__)


async def fetch_pattern(session: AsyncSession, run_id: str) -> pattern_service.Pattern | None:
    """Ensure a pattern is cached for the given run and return it."""
    cache = await repositories.patterns.get_cached_pattern(session, run_id)
    if cache:
        return pattern_service.pattern_from_cache(cache)

    run = await repositories.runs.get_run(session, run_id)
    if not run:
        return None

    steps = await repositories.steps.list_steps_for_run(session, run_id)
    if not steps:
        return None

    project = run.project or await repositories.projects.get_project(session, run.project_id)
    if not project:
        return None

    domain_config = get_domain_config(project.task_type)
    extractor_class = get_extractor(domain_config.pattern_extractor)
    extractor = extractor_class()

    pattern = pattern_service.extract_pattern_from_steps(run_id, steps, extractor)
    payload = pattern_service.pattern_to_cache_payload(pattern)
    cache_model = PatternCache(**payload)
    await repositories.patterns.save_pattern_cache(session, cache_model)

    event_payload: dict[str, Any] = {
        "type": "pattern",
        "pattern_id": pattern.id,
        "run_id": run_id,
        "summary": pattern.summary,
        "steps": len(pattern.steps),
        "variables": list(pattern.variables.keys()),
    }
    await run_events.publish(run_id, event_payload)
    return pattern
