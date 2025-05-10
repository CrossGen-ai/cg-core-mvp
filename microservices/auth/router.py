"""
Authentication router.

This module provides FastAPI router for authentication endpoints:
- User registration and login
- User profile management
- API key management
- Role management
- Password reset
"""
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from microservices.base_microservice import BaseMicroservice, AsyncSessionLocal
from microservices.auth.users import (
    UserService, UserCreate, UserLogin, UserUpdate, UserOut,
    PasswordReset, PasswordResetConfirm, get_db_session
)
from microservices.auth.api_keys import APIKeyManager
from microservices.auth.jwt import (
    Token, TokenData, create_tokens, verify_token, refresh_access_token,
    get_current_user
)
from microservices.auth.middleware import RBACMiddleware
from microservices.auth.models import User
from microservices.auth.users import init_roles_and_permissions

# Create router
router = APIRouter(tags=["auth"])

# Create service instance
base_service = BaseMicroservice()

# Initialize default roles and permissions on startup
async def start_auth_service():
    """Initialize the auth service."""
    base_service.log_event("service.startup", {"service": "auth"})
    
    # Initialize database tables if needed
    async with AsyncSessionLocal() as session:
        try:
            # Create tables
            from microservices.auth.models import Base
            from sqlalchemy.schema import CreateTable
            from sqlalchemy import inspect
            
            inspector = inspect(session.bind)
            existing_tables = inspector.get_table_names()
            
            # Create missing tables
            models = [
                User,
                User.__table__.metadata.tables["roles"],
                User.__table__.metadata.tables["permissions"],
                User.__table__.metadata.tables["user_roles"],
                User.__table__.metadata.tables["role_permissions"],
                User.__table__.metadata.tables["api_keys"]
            ]
            
            for model in models:
                if model.__tablename__ not in existing_tables:
                    # Create the table
                    query = CreateTable(model.__table__)
                    await session.execute(query)
                    base_service.logger.info(f"Created table: {model.__tablename__}")
            
            await session.commit()
            
            # Initialize roles and permissions
            await init_roles_and_permissions()
            base_service.logger.info("Initialized roles and permissions")
            
        except Exception as e:
            base_service.log_error(e, context="Auth service startup")
            raise

# --- Basic Auth Endpoints ---

@router.post("/register", response_model=Dict[str, Any])
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Register a new user.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Dict with user information and token
    """
    try:
        user_info, tokens = await UserService.register_user(user_data, db)
        
        # Log event
        base_service.log_event("user.registered", {
            "username": user_info.username,
            "email": user_info.email
        })
        
        return {
            "status": "ok",
            "message": "User registered successfully",
            "data": {
                "user": user_info,
                "token": tokens
            }
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="User registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed: " + str(e)
        )

@router.post("/token", response_model=Dict[str, Any])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Authenticate a user and return a token.
    
    Args:
        form_data: OAuth2 form with username and password
        db: Database session
        
    Returns:
        Dict with token information
    """
    try:
        login_data = UserLogin(
            username=form_data.username,
            password=form_data.password
        )
        
        user_info, tokens = await UserService.authenticate_user(login_data, db)
        
        # Log event
        base_service.log_event("user.login", {
            "username": user_info.username,
            "id": user_info.id
        })
        
        return {
            "status": "ok",
            "message": "Login successful",
            "data": {
                "user": user_info,
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "token_type": tokens.token_type,
                "expires_at": tokens.expires_at
            }
        }
    except HTTPException as e:
        # Log failed login attempt
        base_service.log_event("user.login.failed", {
            "username": form_data.username,
            "reason": str(e.detail)
        })
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="User login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed: " + str(e)
        )

@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(refresh_token: str):
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        Dict with new token information
    """
    try:
        new_tokens = refresh_access_token(refresh_token)
        
        if new_tokens is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return {
            "status": "ok",
            "message": "Token refreshed successfully",
            "data": {
                "access_token": new_tokens.access_token,
                "refresh_token": new_tokens.refresh_token,
                "token_type": new_tokens.token_type,
                "expires_at": new_tokens.expires_at
            }
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Token refresh")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed: " + str(e)
        )

@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    token_data: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get information about the current authenticated user.
    
    Args:
        token_data: Token data from authentication
        db: Database session
        
    Returns:
        Dict with user information
    """
    try:
        user_info = await UserService.get_user_by_id(token_data.user_id, db)
        
        if user_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        return {
            "status": "ok",
            "message": "User information retrieved successfully",
            "data": user_info
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Get current user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information: " + str(e)
        )

@router.put("/me", response_model=Dict[str, Any])
async def update_current_user(
    update_data: UserUpdate,
    token_data: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update information for the current authenticated user.
    
    Args:
        update_data: Data to update
        token_data: Token data from authentication
        db: Database session
        
    Returns:
        Dict with updated user information
    """
    try:
        updated_user = await UserService.update_user(token_data.user_id, update_data, db)
        
        if updated_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Log event
        base_service.log_event("user.updated", {
            "id": token_data.user_id,
            "fields_updated": list(update_data.dict(exclude_unset=True).keys())
        })
        
        return {
            "status": "ok",
            "message": "User updated successfully",
            "data": updated_user
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Update current user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user: " + str(e)
        )

# --- API Key Management ---

@router.post("/api-keys", response_model=Dict[str, Any])
async def create_api_key(
    name: str,
    expires_in_days: Optional[int] = 365,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["api_keys:create"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new API key for the current user.
    
    Args:
        name: Name/description of the key's purpose
        expires_in_days: Days until the key expires (None for no expiration)
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with API key information
    """
    try:
        api_key = await APIKeyManager.create_api_key(
            user_id=token_data.user_id,
            name=name,
            expires_in_days=expires_in_days,
            db=db
        )
        
        # Log event
        base_service.log_event("api_key.created", {
            "user_id": token_data.user_id,
            "name": name,
            "expires_in_days": expires_in_days
        })
        
        return {
            "status": "ok",
            "message": "API key created successfully",
            "data": api_key
        }
    except Exception as e:
        base_service.log_error(e, context="Create API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key: " + str(e)
        )

@router.get("/api-keys", response_model=Dict[str, Any])
async def get_api_keys(
    include_inactive: bool = False,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["api_keys:read"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all API keys for the current user.
    
    Args:
        include_inactive: Whether to include inactive keys
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with list of API key information
    """
    try:
        api_keys = await APIKeyManager.get_api_keys(
            user_id=token_data.user_id,
            include_inactive=include_inactive,
            db=db
        )
        
        return {
            "status": "ok",
            "message": "API keys retrieved successfully",
            "data": api_keys
        }
    except Exception as e:
        base_service.log_error(e, context="Get API keys")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys: " + str(e)
        )

@router.delete("/api-keys/{key_id}", response_model=Dict[str, Any])
async def revoke_api_key(
    key_id: int,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["api_keys:delete"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Revoke an API key.
    
    Args:
        key_id: ID of the API key to revoke
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with status information
    """
    try:
        success = await APIKeyManager.revoke_api_key(
            key_id=key_id,
            user_id=token_data.user_id,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found or not owned by you"
            )
            
        # Log event
        base_service.log_event("api_key.revoked", {
            "user_id": token_data.user_id,
            "key_id": key_id
        })
        
        return {
            "status": "ok",
            "message": "API key revoked successfully",
            "data": {"key_id": key_id}
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Revoke API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key: " + str(e)
        )

# --- Role Management ---

@router.get("/roles", response_model=Dict[str, Any])
async def get_roles(
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["roles:read"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all roles.
    
    Args:
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with list of roles
    """
    try:
        roles = await UserService.get_roles(db)
        
        return {
            "status": "ok",
            "message": "Roles retrieved successfully",
            "data": roles
        }
    except Exception as e:
        base_service.log_error(e, context="Get roles")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve roles: " + str(e)
        )

@router.get("/permissions", response_model=Dict[str, Any])
async def get_permissions(
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["roles:read"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all permissions.
    
    Args:
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with list of permissions
    """
    try:
        permissions = await UserService.get_permissions(db)
        
        return {
            "status": "ok",
            "message": "Permissions retrieved successfully",
            "data": permissions
        }
    except Exception as e:
        base_service.log_error(e, context="Get permissions")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permissions: " + str(e)
        )

@router.post("/roles", response_model=Dict[str, Any])
async def create_role(
    name: str,
    description: str,
    permissions: Optional[List[str]] = None,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["roles:create"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new role.
    
    Args:
        name: Role name
        description: Role description
        permissions: List of permission names to add to role
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with role information
    """
    try:
        role = await UserService.create_role(
            name=name,
            description=description,
            permissions=permissions,
            db=db
        )
        
        # Log event
        base_service.log_event("role.created", {
            "user_id": token_data.user_id,
            "role_name": name,
            "permissions": permissions
        })
        
        return {
            "status": "ok",
            "message": "Role created successfully",
            "data": role
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Create role")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role: " + str(e)
        )

@router.post("/users/{user_id}/roles/{role_name}", response_model=Dict[str, Any])
async def add_role_to_user(
    user_id: int,
    role_name: str,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["roles:update", "users:update"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Add a role to a user.
    
    Args:
        user_id: User ID
        role_name: Name of the role to add
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with status information
    """
    try:
        success = await UserService.add_user_role(
            user_id=user_id,
            role_name=role_name,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or role not found"
            )
            
        # Log event
        base_service.log_event("user.role.added", {
            "admin_id": token_data.user_id,
            "user_id": user_id,
            "role_name": role_name
        })
        
        return {
            "status": "ok",
            "message": f"Role '{role_name}' added to user successfully",
            "data": {"user_id": user_id, "role_name": role_name}
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Add role to user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add role to user: " + str(e)
        )

@router.delete("/users/{user_id}/roles/{role_name}", response_model=Dict[str, Any])
async def remove_role_from_user(
    user_id: int,
    role_name: str,
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["roles:update", "users:update"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Remove a role from a user.
    
    Args:
        user_id: User ID
        role_name: Name of the role to remove
        token_data: Token data from authentication with permission check
        db: Database session
        
    Returns:
        Dict with status information
    """
    try:
        success = await UserService.remove_user_role(
            user_id=user_id,
            role_name=role_name,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or role not found"
            )
            
        # Log event
        base_service.log_event("user.role.removed", {
            "admin_id": token_data.user_id,
            "user_id": user_id,
            "role_name": role_name
        })
        
        return {
            "status": "ok",
            "message": f"Role '{role_name}' removed from user successfully",
            "data": {"user_id": user_id, "role_name": role_name}
        }
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        base_service.log_error(e, context="Remove role from user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove role from user: " + str(e)
        )

# --- Health Check ---

@router.get("/ping", response_model=Dict[str, Any])
async def ping():
    """
    Health check endpoint for the auth service.
    
    Returns:
        Dict with status information
    """
    return base_service.mcp_response(
        message="Auth service is alive",
        data={"timestamp": datetime.utcnow().isoformat()}
    ) 