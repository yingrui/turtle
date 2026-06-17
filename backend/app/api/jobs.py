from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


class CreateJobRequest(BaseModel):
    type: str
    portfolio: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    policy_ids: list[int] | None = None
    ts_codes: list[str] | None = None
    as_of_date: str | None = None
    ignore_st: bool | None = None
    trend_filter: str | None = None


def _job_to_dict(job) -> dict:
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "log": job.log,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("")
def list_jobs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models.job import Job

    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
    return {"jobs": [_job_to_dict(j) for j in jobs]}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models.job import Job

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.post("", status_code=201)
def create_job(body: CreateJobRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True)
    job_type = payload.pop("type")
    if job_type in ("data_sync", "calendar_sync"):
        raise HTTPException(
            status_code=400,
            detail="Data sync is handled by an external ETL; not supported in this application.",
        )
    svc = JobService()
    job = svc.create_job(db, job_type, payload)
    return _job_to_dict(job)
