# Authentication System in CG-Core

This document outlines the authentication system implemented in CG-Core, including JWT token-based authentication, API key management, and Role-Based Access Control (RBAC).

## Features

- User registration and login
- JWT token-based authentication with refresh tokens
- API key management for N8N and external integrations
- Role-Based Access Control (RBAC) with permissions
- Middleware for securing endpoints

## Authentication Flow

### User Registration and Login

1. User registers with username, email and password
2. System validates input and creates a new user with hashed password
3. User logs in with username/password to receive JWT tokens
4. Access token is used for authentication, refresh token for obtaining new access tokens

### JWT Token Flow

The system uses two types of tokens:

- **Access Token**: Short-lived token for API access (default: 30 minutes)
- **Refresh Token**: Longer-lived token for obtaining new access tokens (default: 7 days)

When the access token expires, the client can use the refresh token to get a new access token without requiring the user to log in again.

## API Keys for N8N Integration

For integrating with N8N or other services, the system provides API key management:

- Generate API keys with optional expiration
- List active API keys
- Revoke API keys

API keys are tied to a user account and inherit the user's permissions. When using an API key for authentication, include it in the `X-API-Key` header.

## Role-Based Access Control (RBAC)

The system implements a comprehensive RBAC system:

- Users can have multiple roles
- Roles contain multiple permissions
- Permissions define what actions a user can perform
- Middleware enforces access control based on roles and permissions

The system comes with predefined roles:

- **admin**: Full access to all features
- **user**: Basic user access with limited permissions
- **n8n**: Role specifically for N8N integration with API access

## API Endpoints

### Authentication

- `POST /auth/register`: Register a new user
- `POST /auth/token`: Login to get access and refresh tokens
- `POST /auth/refresh`: Refresh an access token
- `GET /auth/me`: Get current user information
- `PUT /auth/me`: Update current user information

### API Key Management

- `POST /auth/api-keys`: Create a new API key
- `GET /auth/api-keys`: List API keys
- `DELETE /auth/api-keys/{key_id}`: Revoke an API key

### Role Management

- `GET /auth/roles`: List all roles
- `GET /auth/permissions`: List all permissions
- `POST /auth/roles`: Create a new role
- `POST /auth/users/{user_id}/roles/{role_name}`: Add a role to a user
- `DELETE /auth/users/{user_id}/roles/{role_name}`: Remove a role from a user

## Securing Routes

### Using JWT Authentication

Routes can be secured using FastAPI dependencies:

```python
from microservices.auth.jwt import get_current_user, TokenData

@router.get("/protected")
async def protected_route(token_data: TokenData = Depends(get_current_user)):
    return {"message": f"Hello, {token_data.username}!"}
```

### Using Role-Based Protection

To restrict routes to users with specific roles:

```python
from microservices.auth.middleware import RBACMiddleware

@router.get("/admin-only")
async def admin_only_route(
    token_data: TokenData = Depends(RBACMiddleware.has_roles(["admin"]))
):
    return {"message": "Admin access granted"}
```

### Using Permission-Based Protection

To restrict routes to users with specific permissions:

```python
from microservices.auth.middleware import RBACMiddleware

@router.get("/database-access")
async def database_access_route(
    token_data: TokenData = Depends(RBACMiddleware.has_permissions(["database:read"]))
):
    return {"message": "Database access granted"}
```

### Flexible Authentication (JWT or API Key)

To allow either JWT or API Key authentication:

```python
from microservices.auth.middleware import detect_auth_method

@router.get("/flexible-auth")
async def flexible_auth_route(auth_info = Depends(detect_auth_method)):
    return {"message": "Authentication successful", "auth_info": auth_info}
```

## Environment Configuration

The authentication system is configured via environment variables:

```
# Authentication Settings
JWT_SECRET_KEY=your-secure-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Security Best Practices

- JWT tokens are stateless, allowing for scalable authentication
- Passwords are hashed using bcrypt
- API keys have configurable expiration dates
- Role-based access control limits user actions
- JWT tokens include minimal user information

## Testing Authentication

To test the authentication system, use the provided tests:

```bash
# Run auth tests
python -m pytest microservices/tests/test_auth.py
``` 