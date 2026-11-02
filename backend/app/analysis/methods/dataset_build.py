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
    dataset: str = Field(DEFAULT_DATASET, title="目标数据集", description="导出到哪个数据集（不存在会新建）")
    version: int = Field(1, ge=1, title="写入哪一版", description="往这个版本的草稿里加文件；发布由人决定")
    start: date = Field(..., title="起始交易日")
    end: date = Field(..., title="结束交易日")
    label: str = Field("benchmark", title="标签", description="benchmark 跑赢基准 / relative 相对排名 / absolute 绝对上涨")
    horizon: int = Field(20, ge=1, le=60, title="持有期（交易日）")
    benchmark: str = Field("000300.SH", title="基准指数")
    publish: bool = Field(False, title="导出后立即发布", description="发布后这一版不可再改，谨慎勾选")


def run(db: Session, params: DatasetBuildParams, dataset: dict | None = None) -> dict:
    """导出一段区间，追加到 openKMS 数据集版本的草稿里。"""
    from scripts.export_training_set import _request, build_slice, find_or_create_dataset, upload_slice

    frame = build_slice(
        db,
        start=params.start,
        end=params.end,
        horizon=params.horizon,
        label=params.label,
        benchmark=params.benchmark,
    )
    target = find_or_create_dataset(params.dataset)
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    filename = f"{params.start.isoformat()}_{params.end.isoformat()}.parquet"
    upload_slice(target["id"], params.version, filename, buffer.getvalue())
    if params.publish:
        _request("POST", f"/dataset-versions/{target['id']}/{params.version}/publish")

    return {
        "dataset_id": target["id"],
        "dataset_name": params.dataset,
        "version": params.version,
        "file": filename,
        "rows": int(len(frame)),
        "date_from": params.start.isoformat(),
        "date_to": params.end.isoformat(),
        "columns": sorted(frame.columns.tolist()),
        "files_hint": "可在 数据集 → 该数据集 → 该版本 看到这个文件",
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
