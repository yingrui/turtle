from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    data,
    jobs,
    portfolios,
    screening,
    simulations,
    stock_pick,
    stocks,
    webhooks,
)
from app.config import settings
from app.database import Base, engine

# Written by POST /-/reload so uvicorn --reload restarts the worker after openKMS dev-sync.
# Use a non-dotfile name: watchfiles ignores hidden paths by default.
_RELOAD_SENTINEL = Path(__file__).resolve().parent / "_reload_trigger.py"
_STARTED_AT = datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Stock Trading API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.stock_frontend_url, "http://localhost:3200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(data.router)
app.include_router(portfolios.router)
app.include_router(screening.router)
app.include_router(jobs.router)
app.include_router(simulations.router)
app.include_router(stocks.router)
app.include_router(stock_pick.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok", "started_at": _STARTED_AT}


@app.post("/-/reload")
def hot_reload():
    """openKMS kubernetes --reload webhook: bump sentinel so uvicorn --reload restarts."""
    stamp = datetime.now(timezone.utc).isoformat()
    _RELOAD_SENTINEL.write_text(f"{stamp}\n", encoding="utf-8")
    return {"ok": True, "sentinel": stamp}

