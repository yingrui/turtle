import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

LOCAL_JWT_ALG = "HS256"
LOCAL_JWT_ISS = "stock-local"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def mint_local_user_jwt(user: User) -> str:
    now = int(time.time())
    exp = now + int(settings.stock_local_jwt_exp_hours * 3600)
    payload = {
        "sub": user.id,
        "login": user.login,
        "is_admin": user.is_admin,
        "iss": LOCAL_JWT_ISS,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.stock_secret_key, algorithm=LOCAL_JWT_ALG)


def verify_local_jwt(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.stock_secret_key,
            algorithms=[LOCAL_JWT_ALG],
            issuer=LOCAL_JWT_ISS,
            options={"verify_aud": False},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("stock_token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_local_jwt(token)
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


