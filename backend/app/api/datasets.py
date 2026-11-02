"""数据集：看一眼训练集有哪些版本。

数据集本身放在 openKMS，turtle 只做转发 —— 直连它的数据库会把两边的表结构绑在一起。
训练并不读这些文件（评分卡读的是库里的行情与因子表），这里的用途是"这批数据的版本是什么、
导出到哪一天、有多少行"，写报告和追溯时要用。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from sqlalchemy.orm import Session

from app.models.user import User

router = APIRouter(prefix="/api/datasets", tags=["datasets"], dependencies=[Depends(get_current_user)])


def _openkms(path: str) -> dict:
    base = (getattr(settings, "stock_openkms_base_url", "") or "").rstrip("/")
    key = getattr(settings, "stock_openkms_api_key", "") or ""
    if not base or not key:
        raise HTTPException(status_code=503, detail="openKMS 未配置（缺少地址或密钥）")
    request = urllib.request.Request(
        f"{base}/api{path}", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail=exc.read().decode()[:200]) from None
    except Exception as exc:  # noqa: BLE001 — 网络问题要让前端看得见
        raise HTTPException(status_code=502, detail=f"读取 openKMS 失败：{exc}") from None


@router.get("")
def list_datasets(kind: str = Query("file"), _: User = Depends(get_current_user)):
    payload = _openkms(f"/datasets?kind={kind}")
    items = payload.get("items") or []
    return {
        "datasets": [
            {
                "id": item.get("id"),
                "name": item.get("display_name") or item.get("name"),
                "kind": item.get("kind"),
                "description": item.get("description"),
            }
            for item in items
        ]
    }


@router.post("/build")
def build(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """导出训练集：创建一个构建任务，后台跑，产物写进 openKMS。"""
    from app.analysis import methods, registry  # noqa: F401
    from app.api.analyses import _execute_in_background
    from app.models.ranking import AnalysisRun

    try:
        spec = registry.get("dataset_build")
        parsed = spec.params_model(**(body.get("params") or {}))  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from None

    run = AnalysisRun(
        id=__import__("uuid").uuid4().hex,
        method="dataset_build",
        params=parsed.model_dump(mode="json"),
        status="pending",
        created_by=getattr(user, "login", None),
    )
    db.add(run)
    db.commit()
    _execute_in_background(run.id, "dataset_build", parsed.model_dump(mode="json"), {},
                           None, None, getattr(user, "login", None))
    return {"run_id": run.id}


@router.get("/{dataset_id}/versions/{version}/files")
def version_files(dataset_id: str, version: int, _: User = Depends(get_current_user)):
    """某个版本里到底有哪些文件 —— 知道版本号之后，下一步就是看它包含什么。"""
    manifest = _openkms(f"/dataset-versions/{dataset_id}/{version}/manifest")
    files = manifest.get("files") or []
    return {
        "dataset_id": dataset_id,
        "version": version,
        "files": [
            {
                "name": item.get("name"),
                "rows": item.get("rows") or item.get("row_count"),
                "description": item.get("description"),
                "sha256": item.get("sha256"),
                "bytes": item.get("bytes") or item.get("size"),
            }
            for item in files
        ],
    }


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, _: User = Depends(get_current_user)):
    versions = _openkms(f"/dataset-versions/{dataset_id}")
    listing = _openkms("/datasets?kind=file")
    name = next(
        (
            item.get("display_name") or item.get("name")
            for item in (listing.get("items") or [])
            if item.get("id") == dataset_id
        ),
        None,
    )
    return {
        "id": dataset_id,
        "name": name,
        "versions": [
            {
                "version": version.get("version"),
                "status": version.get("status"),
                "files": version.get("file_count"),
                "rows": version.get("row_count"),
                "date_from": version.get("date_from"),
                "date_to": version.get("date_to"),
                "published_at": version.get("published_at"),
                "manifest_sha256": (version.get("manifest_key") or "").split("/")[-1] or None,
            }
            for version in (versions if isinstance(versions, list) else [])
        ],
    }
