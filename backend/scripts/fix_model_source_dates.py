"""把逐月模型来源的覆盖区间从 "2025-07" 改成真实日期。

Revision 无关：只是一条数据修正。python -m scripts.fix_model_source_dates
"""

from __future__ import annotations

import calendar

from app.database import SessionLocal
from app.models.ranking import RankingSource


def main() -> int:
    with SessionLocal() as db:
        for source in db.query(RankingSource).filter(RankingSource.kind == "model").all():
            periods = sorted((source.params or {}).get("periods") or [])
            if not periods:
                continue
            year, month = (int(part) for part in periods[-1].split("-")[:2])
            source.date_from = f"{periods[0]}-01"
            source.date_to = f"{periods[-1]}-{calendar.monthrange(year, month)[1]:02d}"
            print(f"{source.id}: {source.date_from} → {source.date_to}")
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
