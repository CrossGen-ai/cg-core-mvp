"""
Authentication middleware.

This module provides middleware for:
- User validation from JWT tokens
- Role-based access control
- API key validation
"""
from typing import List, Callable, Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from microservices.auth.jwt import get_current_user, TokenData
from microservices.auth.api_keys import get_api_key_user
from microservices.auth.users import get_db_session
from microservices.auth.models import User, Role
from sqlalchemy.future import select

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

class RBACMiddleware:
    """
    Role-Based Access Control middleware.
    
    Creates FastAPI dependencies for protecting routes based on:
    - User authentication
    - Role requirements
    - Permission requirements
    """
    
    @staticmethod
    def has_roles(roles: List[str]):
        """
        Dependency to check if the user has any of the specified roles.
        
        Args:
            roles: List of required role names (any match is sufficient)
            
        Returns:
            Dependency function
        """
        async def verify_roles(
            token_data: TokenData = Depends(get_current_user), 
            db: AsyncSession = Depends(get_db_session)
        ):
            # Get user from database to check current roles
            # (in case they changed since token was issued)
            result = await db.execute(
                select(User).where(User.id == token_data.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            # Superusers bypass role checks
            if user.is_superuser:
                return token_data
                
            # Check if user has any of the required roles
            user_roles = [r.name for r in user.roles]
            if not any(role in user_roles for role in roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {', '.join(roles)}",
                )
                
            return token_data
            
        return verify_roles
    
    @staticmethod
    def has_permissions(permissions: List[str]):
        """
        Dependency to check if the user has all of the specified permissions.
        
        Args:
            permissions: List of required permission names (all must match)
            
        Returns:
            Dependency function
        """
        async def verify_permissions(
            token_data: TokenData = Depends(get_current_user), 
            db: AsyncSession = Depends(get_db_session)
        ):
            # Get user with roles from database
            result = await db.execute(
                select(User).where(User.id == token_data.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            # Superusers bypass permission checks
            if user.is_superuser:
                return token_data
                
            # Check if user has all required permissions through their roles
            for permission in permissions:
                if not user.has_permission(permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {permission}",
                    )
                    
            return token_data
            
        return verify_permissions
    
    @staticmethod
    def is_active_user():
        """
        Dependency to check if a user is active.
        
        Returns:
            Dependency function
        """
        async def verify_active(
            token_data: TokenData = Depends(get_current_user), 
            db: AsyncSession = Depends(get_db_session)
        ):
            # Get user from database
            result = await db.execute(
                select(User).where(User.id == token_data.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Inactive user",
                )
                
            return token_data
            
        return verify_active
    
    @staticmethod
    def is_self_or_admin(user_id_param: str = "user_id"):
        """
        Dependency to check if request is for the authenticated user or from an admin.
        
        Args:
            user_id_param: Name of the path parameter containing the user ID
            
        Returns:
            Dependency function
        """
        async def verify_self_or_admin(
            request: Request,
            token_data: TokenData = Depends(get_current_user), 
            db: AsyncSession = Depends(get_db_session)
        ):
            # Get target user ID from path parameter
            target_user_id = request.path_params.get(user_id_param)
            if target_user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing user ID parameter: {user_id_param}",
                )
                
            # Check if user is self or admin
            result = await db.execute(
                select(User).where(User.id == token_data.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            # Allow if user is target or is admin/superuser
            if str(token_data.user_id) != str(target_user_id) and not user.is_superuser and not user.has_role("admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied: can only modify own resource",
                )
                
            return token_data
            
        return verify_self_or_admin

# Middleware for detecting and validating auth method (JWT or API Key)
async def detect_auth_method(
    request: Request, 
    db: AsyncSession = Depends(get_db_session)
):
    """
    Middleware to detect and validate the authentication method (JWT or API Key).
    
    Args:
        request: FastAPI request
        db: Database session
        
    Returns:
        Dict with user information
        
    Raises:
        HTTPException: If authentication fails
    """
    # Check for Bearer token in header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Use JWT authentication
        token = auth_header.replace("Bearer ", "")
        token_data = get_current_user(token)
        return token_data
        
    # Check for API Key in header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use API Key authentication
        user_info = get_api_key_user(api_key, db)
        return user_info
        
    # No authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer or APIKey"},
    ) 