import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, mint_local_user_jwt, verify_password
from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login: str
    password: str


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class AuthModeResponse(BaseModel):
    mode: str
    allow_signup: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    login: str
    is_admin: bool
    name: str | None = None
    email: str | None = None


@router.get("/mode", response_model=AuthModeResponse)
def auth_mode():
    local = settings.stock_auth_mode == "local"
    return AuthModeResponse(
        mode=settings.stock_auth_mode,
        allow_signup=local and settings.stock_allow_signup,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if settings.stock_auth_mode != "local":
        raise HTTPException(status_code=400, detail="Local login is disabled")
    user = db.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid login or password")
    return TokenResponse(access_token=mint_local_user_jwt(user))


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if settings.stock_auth_mode != "local":
        raise HTTPException(status_code=400, detail="Local signup is disabled")
    if not settings.stock_allow_signup:
        raise HTTPException(status_code=403, detail="Signup is disabled")
    existing = db.scalar(select(User).where(User.login == body.login))
    if existing:
        raise HTTPException(status_code=409, detail="Login already exists")
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    user = User(
        id=str(uuid.uuid4()),
        login=body.login,
        password_hash=hash_password(body.password),
        is_admin=user_count == 0,
    )
    db.add(user)
    db.commit()
    return TokenResponse(access_token=mint_local_user_jwt(user))


@router.get("/me", response_model=MeResponse)
def me(request: Request, user: User = Depends(get_current_user)):
    claims = getattr(request.state, "openkms", None)
    if claims:
        return MeResponse(
            id=user.id,
            login=user.login,
            is_admin=user.is_admin,
            name=claims.get("name"),
            email=claims.get("email"),
        )
    return MeResponse(id=user.id, login=user.login, is_admin=user.is_admin, name=user.login)
