"""
Security utilities for authentication.
Includes password hashing, JWT token creation and verification.
"""
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db, get_user_by_username

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


class TokenData(BaseModel):
    username: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary containing claims (e.g., {"sub": username})
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[str]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Username if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency to get current user from JWT token.
    
    If no token is provided, returns a default user ID for demo purposes.
    """
    # 如果没有token，返回默认用户ID（演示模式）
    if token is None:
        return "1"
    
    username = decode_token(token)
    if username is None:
        # 解析失败也返回默认用户ID
        return "1"

    return username


# Optional: Current user dependency that returns None if not authenticated
async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """Get current user if authenticated, None otherwise."""
    if not token:
        return None
    return decode_token(token)


# Admin user check（以 users.is_superuser 为准，查库校验）
def get_current_admin_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """获取当前管理员用户；需在库内将该用户 is_superuser=True。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证或令牌无效",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    username = decode_token(token)
    if not username:
        raise credentials_exception
    user = get_user_by_username(db, username=username)
    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限（is_superuser）",
        )
    return {"username": username, "role": "admin"}
