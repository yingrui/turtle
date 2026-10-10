from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, data, jobs, portfolios, screening, simulations, stock_pick, stocks
from app.config import settings
from app.database import Base, engine

# Touched by POST /-/reload so uvicorn --reload (backend-dev) restarts workers after openKMS dev-sync.
_RELOAD_SENTINEL = Path(__file__).resolve().parent / ".reload"


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/-/reload")
def hot_reload():
    """openKMS kubernetes --reload webhook; no-op useful without uvicorn --reload."""
    _RELOAD_SENTINEL.touch()
    return {"ok": True}

