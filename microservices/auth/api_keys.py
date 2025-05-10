"""
API Key management for N8N integration.

This module provides functionality for:
- Creating API keys for N8N integration
- Validating API keys
- Revoking API keys
"""
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import APIKeyHeader
from microservices.base_microservice import AsyncSessionLocal
from microservices.auth.models import APIKey, User

# API Key header scheme
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_db_session():
    """Dependency for getting a database session."""
    async with AsyncSessionLocal() as session:
        yield session

class APIKeyManager:
    """
    Manages API keys for N8N and other external integrations.
    """
    @staticmethod
    async def create_api_key(
        user_id: int,
        name: str,
        expires_in_days: Optional[int] = 365,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Create a new API key for a user.
        
        Args:
            user_id: ID of the user who owns this key
            name: Name/description of the key's purpose
            expires_in_days: Days until the key expires (None for no expiration)
            db: Database session
            
        Returns:
            Dict with API key information
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Generate a new API key
            api_key = APIKey(
                key=APIKey.generate_key(),
                name=name,
                user_id=user_id,
                expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
                is_active=True
            )
            
            # Add to database
            db.add(api_key)
            await db.commit()
            await db.refresh(api_key)
            
            # Return a dictionary with the key information
            return {
                "key": api_key.key,  # Only time the full key is returned
                "id": api_key.id,
                "name": api_key.name,
                "created_at": api_key.created_at,
                "expires_at": api_key.expires_at,
                "is_active": api_key.is_active
            }
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def get_api_keys(
        user_id: int,
        include_inactive: bool = False,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: ID of the user
            include_inactive: Whether to include inactive keys
            db: Database session
            
        Returns:
            List of API key information dicts (without the actual keys)
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Query to get API keys
            query = select(APIKey).where(APIKey.user_id == user_id)
            if not include_inactive:
                query = query.where(APIKey.is_active == True)
                
            # Execute query
            result = await db.execute(query)
            api_keys = result.scalars().all()
            
            # Return list of dictionaries with key information (without actual key)
            return [
                {
                    "id": key.id,
                    "name": key.name,
                    "created_at": key.created_at,
                    "expires_at": key.expires_at,
                    "is_active": key.is_active,
                    # Only return first/last few chars of the key
                    "key_preview": f"{key.key[:5]}...{key.key[-5:]}"
                }
                for key in api_keys
            ]
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def revoke_api_key(
        key_id: int,
        user_id: int,
        db: AsyncSession = None
    ) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: ID of the API key to revoke
            user_id: ID of the user (for ownership verification)
            db: Database session
            
        Returns:
            True if revoked successfully, False otherwise
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Get the API key
            result = await db.execute(
                select(APIKey).where(
                    APIKey.id == key_id, 
                    APIKey.user_id == user_id
                )
            )
            api_key = result.scalar_one_or_none()
            
            # If not found, return False
            if api_key is None:
                return False
                
            # Revoke the key
            api_key.is_active = False
            await db.commit()
            
            return True
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def validate_api_key(
        api_key: str,
        db: AsyncSession = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return user information.
        
        Args:
            api_key: The API key to validate
            db: Database session
            
        Returns:
            Dict with user information if key is valid, None otherwise
        """
        if not api_key:
            return None
            
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Get the API key
            result = await db.execute(
                select(APIKey).where(APIKey.key == api_key)
            )
            api_key_obj = result.scalar_one_or_none()
            
            # If not found or not valid, return None
            if api_key_obj is None or not api_key_obj.is_valid():
                return None
                
            # Get the user
            result = await db.execute(
                select(User).where(User.id == api_key_obj.user_id)
            )
            user = result.scalar_one_or_none()
            
            # If user not found or not active, return None
            if user is None or not user.is_active:
                return None
                
            # Return user information
            return {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_superuser": user.is_superuser,
                "api_key_id": api_key_obj.id,
                "api_key_name": api_key_obj.name
            }
        finally:
            if close_db:
                await db.close()

async def get_api_key_user(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the user from an API key.
    
    Args:
        api_key: API key from header
        db: Database session
        
    Returns:
        User information dict
        
    Raises:
        HTTPException: If API key is invalid
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "APIKey"},
        )
        
    user_info = await APIKeyManager.validate_api_key(api_key, db)
    
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
        
    return user_info

def require_api_key(request: Request):
    """
    Middleware function to check for API key in headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if valid, raises HTTPException otherwise
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "APIKey"},
        )
    return True 