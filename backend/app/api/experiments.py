"""Experiments: define, expand into runs, inspect the matrix, conclude."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.experiment import Experiment
from app.models.user import User
from app.services.experiment_service import ExperimentService

router = APIRouter(prefix="/api/experiments", tags=["experiments"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_experiments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    return {
        "experiments": [
            {
                "id": row.id,
                "question": row.question,
                "status": row.status,
                "strategy": row.strategy,
                "window": [row.window_start, row.window_end],
                "variants": len(row.variants or []),
                "controls": len(row.controls or []),
                "verdict": (row.conclusion or {}).get("verdict"),
            }
            for row in rows
        ]
    }


@router.post("")
def create_experiment(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        experiment = ExperimentService().create(db, body, created_by=getattr(user, "login", None))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"id": experiment.id, "status": experiment.status}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    service = ExperimentService()
    return {
        **service.summary(db, experiment),
        "variants": experiment.variants or [],
        "controls_spec": experiment.controls or [],
    }


@router.post("/{experiment_id}/conclude")
def conclude(experiment_id: str, body: dict, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    try:
        ExperimentService().conclude(db, experiment, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"id": experiment.id, "status": experiment.status}


@router.post("/{experiment_id}/cells/{variant}")
def attach_cell(
    experiment_id: str, variant: str, body: dict, db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Record which job/run filled a matrix cell — the link between the plan and the books."""
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    cell = ExperimentService().attach(
        db, experiment_id, variant, job_id=body.get("job_id"), run_id=body.get("run_id"),
        is_control=bool(body.get("is_control")),
    )
    return {"experiment_id": cell.experiment_id, "variant": cell.variant, "run_id": cell.run_id}
