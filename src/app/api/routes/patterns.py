from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ... import repositories
from ...schemas import PatternRead
from ...services import run_service
from ..deps import db_session

router = APIRouter()


@router.get("/{run_id}", response_model=PatternRead)
async def get_pattern(
    run_id: str,
    session: AsyncSession = Depends(db_session),
) -> PatternRead:
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    pattern = await run_service.fetch_pattern(session, run_id)
    if not pattern:
        return PatternRead(
            id=f"pat-{run_id}",
            source_run_id=run_id,
            name=f"Pattern from {run_id}",
            summary="",
            steps=[],
            variables={},
        )
    payload = pattern.to_dict()
    return PatternRead(
        id=payload["id"],
        source_run_id=payload["source_run_id"],
        name=payload["name"],
        summary=payload["summary"],
        steps=payload["steps"],
        variables=payload["variables"],
    )
