"""
Authentication utilities using pbkdf2_sha256 (no bcrypt limitations)
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256
from sqlalchemy.orm import Session

from database import get_db
import models

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "a0cfa6b4a0350e92f78c4588d7b098f35cc73ecb1d451175d9d3edabacf58477")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash.
    
    Args:
        plain_password: The password to verify
        hashed_password: The stored hash to check against
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password for storage.
    
    Args:
        password: Plain text password
    
    Returns:
        Secure hash string suitable for database storage
    """
    try:
        return pbkdf2_sha256.hash(password)
    except Exception as e:
        print(f"Password hashing error: {e}")
        # Fallback - should not happen with pbkdf2_sha256
        return pbkdf2_sha256.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token (e.g., {"sub": "user@example.com"})
        expires_delta: Custom expiration time (optional)
    
    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_token(token: str) -> Optional[str]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT string to decode
    
    Returns:
        The email (subject) from the token, or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        return email
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency to get the current authenticated user.
    
    This dependency:
    1. Extracts the JWT from the Authorization header
    2. Decodes and validates the token
    3. Looks up the user in the database
    4. Returns the user object or raises 401 Unauthorized
    
    Usage:
        @app.get("/protected")
        def protected_route(user: models.User = Depends(get_current_user)):
            return {"message": f"Hello, {user.email}"}
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode the token
    email = decode_token(token)
    if email is None:
        raise credentials_exception
    
    # Look up user in database
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Dependency that also checks if the user is active.
    
    Builds on get_current_user to add an additional check.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user