from fastapi import APIRouter

from . import projects, runs, patterns, ui

router = APIRouter()
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(patterns.router, prefix="/patterns", tags=["patterns"])
router.include_router(ui.router, prefix="/ui", tags=["ui"])
