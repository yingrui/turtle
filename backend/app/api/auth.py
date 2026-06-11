import uuid

from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/mode", response_model=AuthModeResponse)
def auth_mode():
    return AuthModeResponse(mode=settings.stock_auth_mode, allow_signup=settings.stock_allow_signup)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if settings.stock_auth_mode != "local":
        raise HTTPException(status_code=400, detail="Only local auth is supported")
    user = db.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid login or password")
    return TokenResponse(access_token=mint_local_user_jwt(user))


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
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


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "login": user.login, "is_admin": user.is_admin}
