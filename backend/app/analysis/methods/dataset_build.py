"""把"导出训练集"变成一件可以在系统里运行、并且留下记录的操作。

原来只有一条命令 `python -m scripts.export_training_set --month 2026-09`：谁跑的、用的哪段数据、
多少行、对应 openKMS 的哪个版本，全都只留在那个人的终端里。现在它有两个身份：

- 参数（因子、标签、区间、目标数据集与版本）由契约描述，界面照它生成表单；
- 运行结果写进 analysis_runs，并返回一个描述文件（产物的名称、行数、覆盖区间、openKMS 版本）。

产物本身在 openKMS（parquet 文件 + 数据集版本），turtle 只保存"我导出了什么"的描述。
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis.registry import MethodSpec, register

DEFAULT_DATASET = "scorecard-training-20d-bench"


class DatasetBuildParams(BaseModel):
    dataset: str = Field(DEFAULT_DATASET, title="目标数据集")
    version: int = Field(1, ge=1, title="目标版本")
    start: date = Field(..., title="起始交易日")
    end: date = Field(..., title="结束交易日")
    label: str = Field("benchmark", title="标签", description="benchmark 跑赢基准 / relative 相对排名 / absolute 绝对上涨")
    horizon: int = Field(20, ge=1, le=60, title="持有期（交易日）")
    benchmark: str = Field("000300.SH", title="基准指数")
    granularity: str = Field(
        "month",
        title="分块粒度",
        description="按月导出时每月一个文件，按周则为每周一个文件；分块越小，内存占用越低，文件数越多",
    )
    publish: bool = Field(False, title="导出后立即发布")


def _version_status(dataset_id: str) -> dict[int, str]:
    """各版本的状态：已发布的版本不能再写。"""
    from scripts.export_training_set import _request

    versions = _request("GET", f"/dataset-versions/{dataset_id}")
    items = versions if isinstance(versions, list) else []
    return {int(item["version"]): item["status"] for item in items if item.get("version")}


def _factor_versions(db: Session, columns: list[str]) -> dict[str, int]:
    """导出的列里哪些是因子，以及它们当时的版本。因子公式一改，导出的含义就变了。"""
    from sqlalchemy import text

    from app.core.tushare_schema import tushare_table  # noqa: F401  (kept for parity)

    rows = db.execute(
        text(
            "SELECT d.code, COALESCE(s.version, 1) FROM factor_definitions d "
            "LEFT JOIN factor_specs s ON s.code = d.code WHERE d.code = ANY(:codes)"
        ),
        {"codes": columns},
    ).all()
    return {code: int(version) for code, version in rows}


def _windows(start: date, end: date, granularity: str) -> list[tuple[date, date]]:
    """把区间切成小块：一次只构造一块，内存占用与块大小成正比。"""
    from datetime import timedelta

    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        if granularity == "day":
            last = cursor
        elif granularity == "week":
            last = min(cursor + timedelta(days=6), end)
        else:
            last = min(
                (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), end
            )
        windows.append((cursor, last))
        cursor = last + timedelta(days=1)
    return windows


def run(db: Session, params: DatasetBuildParams, dataset: dict | None = None) -> dict:
    """按分块粒度逐块导出，追加到 openKMS 数据集版本的草稿里。

    一块只构造一次，内存占用与块大小成正比 —— 一次性拼两年半的截面会把进程撑爆。
    """
    from scripts.export_training_set import (
        _request,
        build_slice,
        find_or_create_dataset,
        upload_slice,
    )

    target = find_or_create_dataset(params.dataset)
    version = params.version
    status = _version_status(target["id"])
    note = None
    if status.get(version) == "published":
        version = max(status) + 1 if status else version + 1
        _request("POST", f"/dataset-versions/{target['id']}", b"{}")
        note = f"v{params.version} 已发布，改为写入新版本 v{version}"

    files: list[str] = []
    total_rows = 0
    columns: list[str] = []
    for window_start, window_end in _windows(params.start, params.end, params.granularity):
        frame = build_slice(
            db,
            start=window_start,
            end=window_end,
            horizon=params.horizon,
            label=params.label,
            benchmark=params.benchmark,
        )
        if frame.empty:
            continue
        columns = sorted(frame.columns.tolist())
        total_rows += len(frame)
        filename = f"{window_start.isoformat()}_{window_end.isoformat()}.parquet"
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        upload_slice(target["id"], version, filename, buffer.getvalue())
        files.append(filename)
        del frame, buffer

    if not files:
        raise ValueError("该区间没有可导出的数据（标签需要未来收益，区间末尾可能不足一个持有期）")

    if params.publish:
        _request("POST", f"/dataset-versions/{target['id']}/{version}/publish")

    from app.services.analysis_service import code_revision

    return {
        "code_revision": code_revision(),
        "factors": _factor_versions(db, columns),
        "dataset_id": target["id"],
        "dataset_name": params.dataset,
        "version": version,
        "requested_version": params.version,
        "note": note,
        "files": files,
        "file_count": len(files),
        "rows": total_rows,
        "date_from": params.start.isoformat(),
        "date_to": params.end.isoformat(),
        "granularity": params.granularity,
        "columns": columns,
    }


METHOD = register(
    MethodSpec(
        name="dataset_build",
        display_name="导出训练集",
        description=(
            "把一段区间的因子、未来收益和标签拼成一张表，导出成文件写进 openKMS 数据集的一个版本。"
            "同一段区间重复导出会覆盖同名文件，不会多出一份。"
        ),
        params_model=DatasetBuildParams,
        output_kind="dataset",
        run=run,
    )
)
