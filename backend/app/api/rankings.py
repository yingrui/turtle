"""Ranking sources: the only thing a simulation may rank by."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.ranking import RankingSource
from app.models.user import User
from app.services.analysis_service import RankingSourceService

router = APIRouter(prefix="/api/rankings", tags=["rankings"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_sources(
    include_deprecated: bool = False,
    include_controls: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {
        "sources": RankingSourceService().list_sources(db, include_deprecated, include_controls)
    }


@router.post("")
def create_source(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """创建一个评分模型 = 用某个算法跑一次，产物登记成一个新的来源。

    REST 上"被创建的东西"是模型，不是运行；运行只是过程，所以返回运行号，前端轮询它的状态。
    """
    from app.analysis import methods, registry  # noqa: F401
    from app.api.analyses import _execute_in_background
    from app.models.run import Run

    method = body.get("method")
    try:
        spec = registry.get(method)
    except (KeyError, TypeError):
        raise HTTPException(status_code=422, detail=f"unknown method: {method}") from None
    if spec.output_kind not in ("score_table", "model"):
        # 评分模型的两种形态：打分表（规则加分）与训练出来的模型。导出训练集不是模型，走 /api/datasets/build。
        raise HTTPException(
            status_code=422, detail="这个入口只创建评分模型；导出训练集请用 POST /api/datasets/build"
        )
    try:
        parsed = spec.params_model(**(body.get("params") or {}))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from None

    run = Run(
        id=__import__("uuid").uuid4().hex,
        kind=method,
        title=spec.display_name,
        params=parsed.model_dump(mode="json"),
        status="pending",
        created_by=getattr(user, "login", None),
    )
    db.add(run)
    db.commit()
    _execute_in_background(
        run.id, method, parsed.model_dump(mode="json"), body.get("dataset") or {},
        body.get("source_id"), body.get("display_name"), getattr(user, "login", None),
    )
    return {"run_id": run.id, "method": method}


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        source = RankingSourceService().get(db, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None
    return {
        "id": source.id,
        "kind": source.kind,
        "display_name": source.display_name,
        "description": source.description,
        "method": source.method,
        "params": source.params or {},
        "row_count": source.row_count,
        "date_from": source.date_from,
        "date_to": source.date_to,
        "dataset": {
            "name": source.dataset_name,
            "version": source.dataset_version,
            "manifest_sha256": source.dataset_sha256,
        },
        "label": source.label or {},
        "status": source.status,
        "validation": source.validation or {},
        "artifact_sha256": source.artifact_sha256,
    }


@router.get("/{source_id}/factors")
def source_factors(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """这个模型用了哪些因子，以及库里还认不认识它们。

    模型里存的是因子代号和系数。因子库以后会加新因子，这不影响已有模型；但如果某个因子被改名、删掉，
    或者公式版本变了，这个模型算出来的分数就不再是当初那个意思 —— 这里就是把这件事显示出来。
    """
    import json
    from pathlib import Path

    from sqlalchemy import text

    from app.models.ranking import RankingSource

    source = db.get(RankingSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Ranking source not found")

    codes: list[str] = []
    dropped: list[dict] = []
    trained: dict = {}
    if source.kind == "model":
        directory = Path(source.artifact_key)
        periods = sorted((source.params or {}).get("periods") or [])
        target = directory / f"{periods[-1]}.json" if periods else None
        if target and target.exists():
            payload = json.loads(target.read_text())
            codes = [factor["code"] for factor in payload.get("factors", [])]
            dropped = payload.get("dropped_factors") or []
            # 训练用的是库里哪一段数据、多少行 —— 自动记下来的，不需要人去选"哪份数据集"。
            trained = {
                "window": payload.get("train_window"),
                "rows": (payload.get("metrics") or {}).get("n_train"),
            }
    else:
        codes = list((source.params or {}).get("factors") or [])

    if not codes:
        return {"source_id": source_id, "factors": []}

    rows = db.execute(
        text(
            "SELECT code, name, category, direction FROM factor_definitions WHERE code = ANY(:codes)"
        ),
        {"codes": codes},
    ).all()
    known = {code: {"name": name, "category": category, "direction": direction} for code, name, category, direction in rows}

    return {
        "source_id": source_id,
        "trained": trained,
        "dropped": dropped,
        "factors": [
            {
                "code": code,
                "name": known.get(code, {}).get("name"),
                "category": known.get(code, {}).get("category"),
                "direction": known.get(code, {}).get("direction"),
                # 因子库里找不到 = 这个模型以后算不准了
                "missing": code not in known,
            }
            for code in codes
        ],
    }


@router.get("/{source_id}/preview")
def preview(
    source_id: str,
    day: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return {"rows": RankingSourceService().preview(db, source_id, day or date.today(), limit)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None


@router.delete("/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """删掉一个评分模型。

    被回测用过也允许删除：删掉之后那些回测的分数无法再复现，但回测本身的成交与净值还在。这是拿"可复现"
    换"能清理"，等存储与算力更宽裕时可以再讨论保留策略。
    """
    from app.models.simulation import SimulationRun

    source = db.get(RankingSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Ranking source not found")
    used = db.query(SimulationRun).filter(SimulationRun.ranking_source_id == source_id).count()
    db.delete(source)
    db.commit()
    return {"id": source_id, "deleted": True, "used_by_runs": used}


@router.get("/{source_id}/explain")
def explain(
    source_id: str,
    day: date = Query(..., description="交易日"),
    ts_code: str = Query(..., description="股票代码"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """这只股票那天为什么排在这里：每个因子的取值、截面分位，以及它对总分的贡献。

    排名本身只是一个数字，没有分解就无法判断"它是不是靠某一项极端值顶上去的"。
    """
    import json
    from pathlib import Path

    from sqlalchemy import text

    from app.models.ranking import RankingSource

    source = db.get(RankingSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Ranking source not found")

    codes: list[str] = []
    model: dict | None = None
    if source.kind == "model":
        directory = Path(source.artifact_key)
        target = directory / f"{day.year}-{day.month:02d}.json"
        if not target.exists():
            candidates = sorted(p.stem for p in directory.glob("*.json") if p.stem <= f"{day.year}-{day.month:02d}")
            if not candidates:
                raise HTTPException(status_code=404, detail="No model covers that date")
            target = directory / f"{candidates[-1]}.json"
        model = json.loads(target.read_text())
        codes = [factor["code"] for factor in model.get("factors", [])]
    else:
        codes = list((source.params or {}).get("factors") or [])

    if not codes:
        return {"source_id": source_id, "day": day.isoformat(), "ts_code": ts_code, "factors": []}

    rows = db.execute(
        text(
            "SELECT d.code, v.value FROM factor_values v "
            "JOIN factor_definitions d ON d.id = v.factor_id "
            "WHERE v.trade_date = :day AND v.ts_code = :code AND d.code = ANY(:codes)"
        ),
        {"day": day, "code": ts_code, "codes": codes},
    ).all()
    values = {code: float(value) for code, value in rows if value is not None}

    # 同日全市场分位，用来判断"这个数是高还是低"
    percentile_rows = db.execute(
        text(
            "SELECT d.code, v.value FROM factor_values v "
            "JOIN factor_definitions d ON d.id = v.factor_id "
            "WHERE v.trade_date = :day AND d.code = ANY(:codes)"
        ),
        {"day": day, "codes": codes},
    ).all()
    by_factor: dict[str, list[float]] = {}
    for code, value in percentile_rows:
        if value is not None:
            by_factor.setdefault(code, []).append(float(value))

    factors = []
    for code in codes:
        value = values.get(code)
        peers = by_factor.get(code) or []
        percentile = None
        if value is not None and peers:
            below = sum(1 for peer in peers if peer < value)
            percentile = round(below / len(peers) * 100, 1)
        contribution = None
        if model is not None and percentile is not None:
            spec = next((f for f in model.get("factors", []) if f["code"] == code), None)
            if spec and spec.get("woe"):
                contribution = round(_contribution(spec, percentile), 4)
        factors.append(
            {"code": code, "value": value, "percentile": percentile, "contribution": contribution}
        )

    return {
        "source_id": source_id,
        "day": day.isoformat(),
        "ts_code": ts_code,
        "kind": source.kind,
        "intercept": None if model is None else model.get("intercept"),
        "factors": factors,
    }


def _contribution(spec: dict, percentile: float) -> float:
    """某一项对总分的贡献。

    评分卡不是按原始值分箱，而是按**当日截面分位**分成若干档（模型里只存了每档的 WOE，没有存边界）。
    所以要先把分位落到档位，再乘系数。
    """
    woe = spec["woe"]
    index = min(int(percentile / 100 * len(woe)), len(woe) - 1)
    return float(spec.get("coef", 0.0)) * float(woe[index])


@router.get("/{source_id}/months")
def list_months(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """这套评分模型包含哪些月份，以及库里还有哪些训好的月份可以加进来。"""
    from app.models.model_artifact import ModelArtifact

    source = db.get(RankingSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Ranking source not found")
    if source.kind != "model":
        return {"source_id": source_id, "months": [], "available": []}

    periods = (source.params or {}).get("periods") or []
    artifacts = {row.period: row for row in db.query(ModelArtifact).all()}
    return {
        "source_id": source_id,
        "months": [
            {
                "period": period,
                "trained": period in artifacts,
                "mlflow_run_id": artifacts[period].mlflow_run_id if period in artifacts else None,
                "mlflow_model_version": artifacts[period].mlflow_model_version if period in artifacts else None,
                "train_auc": (artifacts[period].metrics or {}).get("train_auc") if period in artifacts else None,
            }
            for period in periods
        ],
        # 可以加进来的：训练好但还不在这一套里的期次
        "available": sorted(period for period in artifacts if period not in periods),
    }


@router.post("/{source_id}/months")
def add_month(source_id: str, body: dict, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """把某个月训练好的模型加进这套评分模型。"""
    import shutil
    from pathlib import Path

    from app.models.model_artifact import ModelArtifact

    source = db.get(RankingSource, source_id)
    if not source or source.kind != "model":
        raise HTTPException(status_code=404, detail="评分模型不存在")
    period = str(body.get("period") or "").strip()
    artifact = db.query(ModelArtifact).filter(ModelArtifact.period == period).first()
    if not artifact:
        raise HTTPException(status_code=404, detail=f"没有 {period} 的训练产物")

    directory = Path(source.artifact_key)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{period}.json"
    # 模型产物可能本来就在这个目录里（导入的模型如此），同文件不必复制。
    if Path(artifact.artifact_key).resolve() != target.resolve():
        shutil.copyfile(artifact.artifact_key, target)

    params = dict(source.params or {})
    periods = sorted({*(params.get("periods") or []), period})
    params["periods"] = periods
    source.params = params
    source.date_from = min(filter(None, [source.date_from, f"{periods[0]}-01"]))
    db.commit()
    return {"source_id": source_id, "periods": periods}


@router.delete("/{source_id}/months/{period}")
def remove_month(source_id: str, period: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """从这套评分模型里去掉某个月（模型文件仍在模型产物里，随时可以再加回来）。"""
    from pathlib import Path

    source = db.get(RankingSource, source_id)
    if not source or source.kind != "model":
        raise HTTPException(status_code=404, detail="评分模型不存在")
    params = dict(source.params or {})
    periods = [item for item in (params.get("periods") or []) if item != period]
    params["periods"] = periods
    source.params = params
    target = Path(source.artifact_key) / f"{period}.json"
    if target.exists():
        target.unlink()
    db.commit()
    return {"source_id": source_id, "periods": periods}


@router.post("/{source_id}/deprecate")
def deprecate(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import datetime

    try:
        source = RankingSourceService().get(db, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None
    source.status = "deprecated"
    source.deprecated_at = datetime.utcnow()
    db.commit()
    return {"id": source.id, "status": source.status}
