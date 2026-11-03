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
    # A simulation can be driven by the trade policies ("signal", default) or by a scorecard's daily
    # ranking ("model"). These carry the model-run parameters.
    mode: str | None = None
    model_policy: str | None = None
    top_n: int | None = None
    sell_rank_limit: int | None = None
    max_holding_days: int | None = None
    cash_buffer: float | None = None
    initial_cash: float | None = None
    #: A run's name and description — an experiment report points at these.
    name: str | None = None
    description: str | None = None
    #: Provenance of the experiment: which dataset version, which label, which benchmark.
    dataset: str | None = None
    dataset_version: int | None = None
    dataset_sha256: str | None = None
    label: str | None = None
    horizon: int | None = None
    benchmark: str | None = None
    #: `ic_weights` swaps the scorecard for an IC-weight table (no training involved).
    ranking_source: str | None = None
    ranking_weights: str | None = None
    #: The online path: a registered `ranking_sources.id`. Replaces `ranking_weights`' free-text path.
    ranking_source_id: str | None = None
    #: `policy` = pool → policy → trades (the strategy); omitted = the mechanical ranking diagnostic.
    buy_rule: str | None = None
    #: `monthly` / `weekly` / `none` — whether a model-driven run may train what it is missing.
    retrain: str | None = None


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
    """单个任务的查询。

    读 runs（统一表）；若那里没有（回填之前的极老记录），回落到 jobs。返回值形状保持不变 ——
    openKMS 的 Action 回调仍在读这个接口。
    """
    from app.models.job import Job
    from app.models.run import Run

    run = db.get(Run, job_id)
    if run is not None:
        return {
            "id": run.id,
            "type": run.kind,
            "status": run.status,
            "progress": "",
            "payload": run.params,
            "result": None if not run.result else __import__("json").dumps(run.result),
            "error": run.error,
            "log": "",
            "created_at": run.started_at.isoformat() if run.started_at else None,
            "updated_at": run.finished_at.isoformat() if run.finished_at else None,
        }

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
