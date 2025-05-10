"""
User management service.

This module provides functionality for:
- User registration
- User authentication
- User profile management
- Role and permission management
"""
import os
from typing import Optional, List, Dict, Any, Tuple
import re
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from fastapi import HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field, validator
from microservices.base_microservice import AsyncSessionLocal
from microservices.auth.models import User, Role, Permission
from microservices.auth.jwt import create_tokens, Token

# Regex patterns for validation
USERNAME_PATTERN = r"^[a-zA-Z0-9_-]{3,20}$"
PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$"

# Pydantic models for request validation
class UserCreate(BaseModel):
    """Model for user registration."""
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=8)
    
    @validator('username')
    def username_must_be_valid(cls, v):
        if not re.match(USERNAME_PATTERN, v):
            raise ValueError('Username must be 3-20 characters and contain only letters, numbers, underscores, or hyphens')
        return v
        
    @validator('password')
    def password_must_be_strong(cls, v):
        if not re.match(PASSWORD_PATTERN, v):
            raise ValueError('Password must be at least 8 characters and include uppercase, lowercase, and numbers')
        return v

class UserLogin(BaseModel):
    """Model for user login."""
    username: str
    password: str

class UserUpdate(BaseModel):
    """Model for updating user profile."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    
    @validator('password')
    def password_must_be_strong(cls, v):
        if v is not None and not re.match(PASSWORD_PATTERN, v):
            raise ValueError('Password must be at least 8 characters and include uppercase, lowercase, and numbers')
        return v

class UserOut(BaseModel):
    """Model for user information returned to clients."""
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    roles: List[str] = []
    
    class Config:
        orm_mode = True

class PasswordReset(BaseModel):
    """Model for password reset request."""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Model for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_must_be_strong(cls, v):
        if not re.match(PASSWORD_PATTERN, v):
            raise ValueError('Password must be at least 8 characters and include uppercase, lowercase, and numbers')
        return v

async def get_db_session():
    """Dependency for getting a database session."""
    async with AsyncSessionLocal() as session:
        yield session

class UserService:
    """
    Service for user management operations.
    """
    @staticmethod
    async def register_user(
        user_data: UserCreate,
        db: AsyncSession = None
    ) -> Tuple[UserOut, Token]:
        """
        Register a new user.
        
        Args:
            user_data: User registration data
            db: Database session
            
        Returns:
            Tuple of user information and token
            
        Raises:
            HTTPException: If username or email already exists
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Check if username or email already exists
            result = await db.execute(
                select(User).where(
                    or_(
                        User.username == user_data.username,
                        User.email == user_data.email
                    )
                )
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                if existing_user.username == user_data.username:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already registered"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
            
            # Create new user
            hashed_password = User.get_password_hash(user_data.password)
            new_user = User(
                username=user_data.username,
                email=user_data.email,
                hashed_password=hashed_password
            )
            
            # Find default user role
            result = await db.execute(
                select(Role).where(Role.name == "user")
            )
            default_role = result.scalar_one_or_none()
            
            # If default role doesn't exist, create it
            if default_role is None:
                default_role = Role(
                    name="user",
                    description="Default user role with basic permissions"
                )
                db.add(default_role)
                await db.flush()
            
            # Add role to user
            new_user.roles.append(default_role)
            
            # Save to database
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            # Create tokens
            tokens = create_tokens(
                user_id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                scopes=[r.name for r in new_user.roles]
            )
            
            # Format user information for return
            user_info = UserOut(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                is_active=new_user.is_active,
                is_superuser=new_user.is_superuser,
                created_at=new_user.created_at,
                last_login=new_user.last_login,
                roles=[r.name for r in new_user.roles]
            )
            
            return user_info, tokens
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def authenticate_user(
        login_data: UserLogin,
        db: AsyncSession = None
    ) -> Tuple[UserOut, Token]:
        """
        Authenticate a user and return tokens.
        
        Args:
            login_data: Login credentials
            db: Database session
            
        Returns:
            Tuple of user information and token
            
        Raises:
            HTTPException: If authentication fails
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Find user by username
            result = await db.execute(
                select(User).where(User.username == login_data.username)
            )
            user = result.scalar_one_or_none()
            
            # Check if user exists and password is correct
            if user is None or not user.verify_password(login_data.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is disabled",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Update last login time
            user.last_login = datetime.utcnow()
            await db.commit()
            
            # Create tokens
            tokens = create_tokens(
                user_id=user.id,
                username=user.username,
                email=user.email,
                scopes=[r.name for r in user.roles]
            )
            
            # Format user information for return
            user_info = UserOut(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                last_login=user.last_login,
                roles=[r.name for r in user.roles]
            )
            
            return user_info, tokens
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def get_user_by_id(
        user_id: int,
        db: AsyncSession = None
    ) -> Optional[UserOut]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            User information or None if not found
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return None
                
            return UserOut(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                last_login=user.last_login,
                roles=[r.name for r in user.roles]
            )
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def update_user(
        user_id: int,
        update_data: UserUpdate,
        db: AsyncSession = None
    ) -> Optional[UserOut]:
        """
        Update user information.
        
        Args:
            user_id: User ID
            update_data: Data to update
            db: Database session
            
        Returns:
            Updated user information or None if not found
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return None
                
            # Update email if provided
            if update_data.email is not None:
                # Check if email is already taken
                result = await db.execute(
                    select(User).where(
                        User.email == update_data.email,
                        User.id != user_id
                    )
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
                    
                user.email = update_data.email
                
            # Update password if provided
            if update_data.password is not None:
                user.hashed_password = User.get_password_hash(update_data.password)
                
            await db.commit()
            await db.refresh(user)
            
            return UserOut(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                last_login=user.last_login,
                roles=[r.name for r in user.roles]
            )
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def add_user_role(
        user_id: int,
        role_name: str,
        db: AsyncSession = None
    ) -> bool:
        """
        Add a role to a user.
        
        Args:
            user_id: User ID
            role_name: Name of the role to add
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Get user
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return False
                
            # Get role
            result = await db.execute(
                select(Role).where(Role.name == role_name)
            )
            role = result.scalar_one_or_none()
            
            if role is None:
                return False
                
            # Add role if user doesn't already have it
            if not user.has_role(role_name):
                user.roles.append(role)
                await db.commit()
                
            return True
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def remove_user_role(
        user_id: int,
        role_name: str,
        db: AsyncSession = None
    ) -> bool:
        """
        Remove a role from a user.
        
        Args:
            user_id: User ID
            role_name: Name of the role to remove
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Get user
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return False
                
            # Get role
            result = await db.execute(
                select(Role).where(Role.name == role_name)
            )
            role = result.scalar_one_or_none()
            
            if role is None:
                return False
                
            # Remove role if user has it
            if user.has_role(role_name):
                user.roles.remove(role)
                await db.commit()
                
            return True
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def create_role(
        name: str,
        description: str,
        permissions: List[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Create a new role.
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permission names to add to role
            db: Database session
            
        Returns:
            Role information
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            # Check if role already exists
            result = await db.execute(
                select(Role).where(Role.name == name)
            )
            existing_role = result.scalar_one_or_none()
            
            if existing_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role '{name}' already exists"
                )
                
            # Create role
            role = Role(
                name=name,
                description=description
            )
            
            # Add permissions if provided
            if permissions:
                for perm_name in permissions:
                    # Check if permission exists
                    result = await db.execute(
                        select(Permission).where(Permission.name == perm_name)
                    )
                    perm = result.scalar_one_or_none()
                    
                    # Create permission if it doesn't exist
                    if perm is None:
                        perm = Permission(
                            name=perm_name,
                            description=f"Auto-created permission for {perm_name}"
                        )
                        db.add(perm)
                        await db.flush()
                        
                    role.permissions.append(perm)
            
            db.add(role)
            await db.commit()
            await db.refresh(role)
            
            return {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": [p.name for p in role.permissions]
            }
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def get_roles(
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get all roles.
        
        Args:
            db: Database session
            
        Returns:
            List of role information
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            result = await db.execute(select(Role))
            roles = result.scalars().all()
            
            return [
                {
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "permissions": [p.name for p in role.permissions]
                }
                for role in roles
            ]
        finally:
            if close_db:
                await db.close()
                
    @staticmethod
    async def get_permissions(
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get all permissions.
        
        Args:
            db: Database session
            
        Returns:
            List of permission information
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
            
        try:
            result = await db.execute(select(Permission))
            permissions = result.scalars().all()
            
            return [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "description": perm.description
                }
                for perm in permissions
            ]
        finally:
            if close_db:
                await db.close()

# Initialize basic roles and permissions on startup
async def init_roles_and_permissions():
    """Initialize default roles and permissions."""
    async with AsyncSessionLocal() as db:
        # Create admin role if it doesn't exist
        result = await db.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        
        if admin_role is None:
            admin_role = Role(
                name="admin",
                description="Administrator with full access to all features"
            )
            db.add(admin_role)
            
        # Create user role if it doesn't exist
        result = await db.execute(select(Role).where(Role.name == "user"))
        user_role = result.scalar_one_or_none()
        
        if user_role is None:
            user_role = Role(
                name="user",
                description="Regular user with basic access"
            )
            db.add(user_role)
            
        # Create n8n role if it doesn't exist
        result = await db.execute(select(Role).where(Role.name == "n8n"))
        n8n_role = result.scalar_one_or_none()
        
        if n8n_role is None:
            n8n_role = Role(
                name="n8n",
                description="Role for N8N integration with API access"
            )
            db.add(n8n_role)
        
        # Create basic permissions
        basic_permissions = {
            "users:read": "Read user information",
            "users:create": "Create users",
            "users:update": "Update user information",
            "users:delete": "Delete users",
            "roles:read": "Read role information",
            "roles:create": "Create roles",
            "roles:update": "Update role information",
            "roles:delete": "Delete roles",
            "api_keys:read": "Read API keys",
            "api_keys:create": "Create API keys",
            "api_keys:update": "Update API keys",
            "api_keys:delete": "Delete API keys",
            "events:read": "Read events",
            "events:create": "Create events",
            "database:read": "Read database",
            "database:write": "Write to database",
            "n8n:access": "Access N8N integration endpoints"
        }
        
        for perm_name, perm_desc in basic_permissions.items():
            result = await db.execute(
                select(Permission).where(Permission.name == perm_name)
            )
            perm = result.scalar_one_or_none()
            
            if perm is None:
                perm = Permission(
                    name=perm_name,
                    description=perm_desc
                )
                db.add(perm)
                
                # Add to appropriate roles
                if perm_name.startswith("users:") or perm_name.startswith("roles:"):
                    admin_role.permissions.append(perm)
                elif perm_name == "users:read" or perm_name == "roles:read":
                    user_role.permissions.append(perm)
                elif perm_name.startswith("api_keys:"):
                    admin_role.permissions.append(perm)
                    if perm_name == "api_keys:read":
                        user_role.permissions.append(perm)
                elif perm_name.startswith("events:"):
                    admin_role.permissions.append(perm)
                    n8n_role.permissions.append(perm)
                elif perm_name.startswith("database:"):
                    admin_role.permissions.append(perm)
                    n8n_role.permissions.append(perm)
                elif perm_name == "n8n:access":
                    admin_role.permissions.append(perm)
                    n8n_role.permissions.append(perm)
                    
        await db.commit() 