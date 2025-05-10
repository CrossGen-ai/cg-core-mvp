"""
JWT token handling for authentication.

This module provides functionality for:
- Creating JWT tokens
- Validating JWT tokens
- Refreshing JWT tokens
"""
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import jwt
from jwt.exceptions import PyJWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "highly_secure_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Authentication scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: int  # Unix timestamp

class TokenData(BaseModel):
    """Token payload model."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    scopes: list[str] = []
    exp: Optional[int] = None  # Expiration time

def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to include in the token
        expires_delta: Custom expiration time, defaults to ACCESS_TOKEN_EXPIRE_MINUTES
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expires = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    data: Dict[str, Any]
) -> str:
    """
    Create a JWT refresh token with longer expiration.
    
    Args:
        data: Payload data to include in the token
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_tokens(user_id: int, username: str, email: str, scopes: list[str] = None) -> Token:
    """
    Create both access and refresh tokens for a user.
    
    Args:
        user_id: User's ID
        username: User's username
        email: User's email
        scopes: List of permission scopes
        
    Returns:
        Token object with access_token, refresh_token and metadata
    """
    if scopes is None:
        scopes = []
        
    # Prepare token data
    token_data = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "scopes": scopes,
    }
    
    # Create tokens
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Calculate expiration timestamp for client
    expires_at = int(time.time()) + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_at=expires_at
    )

def verify_token(token: str) -> Optional[TokenData]:
    """
    Verify a JWT token and return its data.
    
    Args:
        token: JWT token string
    
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        username = payload.get("username")
        email = payload.get("email")
        scopes = payload.get("scopes", [])
        exp = payload.get("exp")
        
        return TokenData(
            user_id=user_id,
            username=username,
            email=email,
            scopes=scopes,
            exp=exp
        )
    except PyJWTError:
        return None
    except (ValueError, TypeError):
        # Handle case when sub is not a valid integer
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    FastAPI dependency to get the current authenticated user from token.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        TokenData object for the authenticated user
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception
    
    # Check token expiration - JWT library should handle this,
    # but adding an extra check for clarity
    if token_data.exp and datetime.fromtimestamp(token_data.exp) < datetime.utcnow():
        raise credentials_exception
        
    return token_data

def refresh_access_token(refresh_token: str) -> Optional[Token]:
    """
    Generate a new access token using a refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        New Token object with fresh access_token, or None if refresh_token is invalid
    """
    token_data = verify_token(refresh_token)
    if token_data is None:
        return None
    
    # Create new tokens
    return create_tokens(
        user_id=token_data.user_id,
        username=token_data.username,
        email=token_data.email,
        scopes=token_data.scopes
    ) 