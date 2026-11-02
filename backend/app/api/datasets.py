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
