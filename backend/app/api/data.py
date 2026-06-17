from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.user import User
from app.core.dataset.Dataset import Dataset

router = APIRouter(prefix="/api/data", tags=["data"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def data_status(_: User = Depends(get_current_user)):
    return Dataset().get_data_status()


@router.get("/latest-date")
def latest_date(_: User = Depends(get_current_user)):
    latest = Dataset().get_latest_date()
    return {"latest_date": latest}
