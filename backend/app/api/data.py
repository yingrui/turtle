from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.user import User
from app.core.dataset.Dataset import Dataset

router = APIRouter(prefix="/api/data", tags=["data"], dependencies=[Depends(get_current_user)])


@router.get("/latest-date")
def latest_date(_: User = Depends(get_current_user)):
    ds = Dataset()
    latest = ds.get_latest_date()
    if latest is None:
        return {"latest_date": None}
    if hasattr(latest, "isoformat"):
        return {"latest_date": latest.isoformat()}
    return {"latest_date": str(latest)}
