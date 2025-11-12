from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Iterable

from ...config import settings
from ...models import PatternCache, Step
from .extractors import BasePatternExtractor, CodeExtractor, get_extractor


@dataclass
class PatternStep:
    instruction: str
    intent: dict[str, Any] | None = None


@dataclass
class Pattern:
    id: str
    source_run_id: str
    name: str
    summary: str
    steps: list[PatternStep]
    variables: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_run_id": self.source_run_id,
            "name": self.name,
            "summary": self.summary,
            "steps": [step.__dict__ for step in self.steps],
            "variables": self.variables,
        }


def extract_pattern_from_steps(
    run_id: str, steps: Iterable[Step], extractor: BasePatternExtractor | None = None
) -> Pattern:
    """
    Extract a pattern from a sequence of steps.

    Args:
        run_id: The run ID to extract pattern from
        steps: The steps to analyze
        extractor: Optional domain-specific extractor. Defaults to CodeExtractor.

    Returns:
        Extracted Pattern object
    """
    if extractor is None:
        extractor = CodeExtractor()
    usable_steps: list[PatternStep] = []
    variables: dict[str, Any] = {}
    instructions: list[str] = []

    for step in steps:
        if not extractor.should_include_step(step):
            continue
        normalized = extractor.normalize_instruction(step.content or "")
        if not normalized:
            continue
        extractor.discover_variables(normalized, variables)
        usable_steps.append(PatternStep(instruction=normalized))
        instructions.append(normalized)

    usable_steps = usable_steps[: settings.max_pattern_steps]
    instructions = instructions[: settings.max_pattern_steps]

    summary = extractor.extract_summary(instructions)
    summary = summary[: settings.pattern_summary_chars]

    pattern = Pattern(
        id=f"pat-{run_id}",
        source_run_id=run_id,
        name=f"Pattern from {run_id}",
        summary=summary,
        steps=usable_steps,
        variables=variables,
    )

    _clamp_pattern_tokens(pattern)
    return pattern


def _clamp_pattern_tokens(pattern: Pattern) -> None:
    def estimate_tokens(text: str) -> int:
        return math.ceil(len(text.split()))

    while pattern.steps:
        block = render_pattern_block(pattern)
        if estimate_tokens(block) <= settings.max_pattern_tokens:
            break
        pattern.steps.pop()


def render_pattern_block(pattern: Pattern) -> str:
    lines = [f'<reference_workflow id="{pattern.id}">']
    summary = pattern.summary or "Follow the proven approach from the reference run."
    lines.append(f"What worked before: {summary}")
    lines.append("")
    lines.append("Sequence:")
    if pattern.steps:
        for idx, step in enumerate(pattern.steps, start=1):
            lines.append(f"{idx}. {step.instruction}")
    else:
        lines.append("No reusable steps captured.")
    lines.append("")
    lines.append("Variables:")
    if pattern.variables:
        for key, payload in pattern.variables.items():
            lines.append(f"- {key}: {payload.get('type','text')} (ex: {payload.get('example','?')})")
    else:
        lines.append("- none discovered")
    lines.append("")
    lines.append(
        "Apply the same sequence when it fits. If critical context is missing, ask once, "
        "then continue with the user's goal."
    )
    lines.append("</reference_workflow>")
    return "\n".join(lines)


def pattern_to_cache_payload(pattern: Pattern) -> dict[str, str]:
    return {
        "id": pattern.id,
        "source_run_id": pattern.source_run_id,
        "name": pattern.name,
        "summary": pattern.summary,
        "steps_json": json.dumps([step.__dict__ for step in pattern.steps]),
        "variables_json": json.dumps(pattern.variables),
    }


def pattern_from_cache(cache: PatternCache) -> Pattern:
    steps_payload = json.loads(cache.steps_json)
    steps = [PatternStep(**step_dict) for step_dict in steps_payload]
    variables = json.loads(cache.variables_json)
    return Pattern(
        id=cache.id,
        source_run_id=cache.source_run_id,
        name=cache.name,
        summary=cache.summary,
        steps=steps,
        variables=variables,
    )
