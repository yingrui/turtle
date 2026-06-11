from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, data, jobs, portfolios, screening, simulations, stocks
from app.config import settings
from app.database import Base, engine


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


@app.get("/health")
def health():
    return {"status": "ok"}
