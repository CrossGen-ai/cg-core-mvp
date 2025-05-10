"""
Test cases for the authentication microservice.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from microservices.main import app
import asyncio
import jwt
from datetime import datetime, timedelta
from sqlalchemy import text, select, insert, update, delete
from microservices.base_microservice import AsyncSessionLocal
from microservices.auth.models import User, Role, Permission
from microservices.auth.jwt import verify_token

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_auth_ping():
    """Test that the auth service is responding."""
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        response = await ac.get("/auth/ping")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["message"] == "Auth service is alive"
        assert "timestamp" in response.json()["data"]

@pytest.mark.asyncio
async def test_auth_register_user():
    """Test user registration process."""
    # Generate unique username to avoid conflicts
    unique_username = f"testuser_{datetime.utcnow().timestamp()}"
    
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        # Register a new user
        response = await ac.post("/auth/register", json={
            "username": unique_username,
            "email": f"{unique_username}@example.com",
            "password": "TestPassword123"
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["message"] == "User registered successfully"
        
        # Check returned data structure
        data = response.json()["data"]
        assert "user" in data
        assert "token" in data
        
        # Check user data
        user = data["user"]
        assert user["username"] == unique_username
        assert user["email"] == f"{unique_username}@example.com"
        assert user["is_active"] is True
        assert "roles" in user
        
        # Check token
        token = data["token"]
        assert "access_token" in token
        assert "refresh_token" in token
        assert token["token_type"] == "bearer"
        assert "expires_at" in token
        
        # Verify access token
        token_data = verify_token(token["access_token"])
        assert token_data is not None
        assert token_data.username == unique_username
        
        # Clean up - delete test user
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(User).where(User.username == unique_username)
            )
            await session.commit()

@pytest.mark.asyncio
async def test_login_and_me_endpoint():
    """Test user login and profile retrieval."""
    # Create test user
    unique_username = f"logintest_{datetime.utcnow().timestamp()}"
    password = "TestPassword123"
    
    async with AsyncSessionLocal() as session:
        # Create user with hashed password
        hashed_password = User.get_password_hash(password)
        test_user = User(
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password=hashed_password,
            is_active=True
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)
        user_id = test_user.id
    
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        # Login with created user
        response = await ac.post("/auth/token", data={
            "username": unique_username,
            "password": password,
            "grant_type": "password"  # Required by OAuth2PasswordRequestForm
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        
        # Get token
        token = response.json()["data"]["access_token"]
        
        # Use token to access me endpoint
        me_response = await ac.get(
            "/auth/me", 
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert me_response.status_code == 200
        assert me_response.json()["status"] == "ok"
        assert me_response.json()["data"]["username"] == unique_username
        assert me_response.json()["data"]["id"] == user_id
    
    # Clean up - delete test user
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(User).where(User.username == unique_username)
        )
        await session.commit()

@pytest.mark.asyncio
async def test_invalid_login():
    """Test login with invalid credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        # Try login with non-existent user
        response = await ac.post("/auth/token", data={
            "username": "nonexistent_user",
            "password": "WrongPassword123",
            "grant_type": "password"
        })
        
        assert response.status_code == 401  # Unauthorized
        assert "access_token" not in response.json()

@pytest.mark.asyncio
async def test_token_refresh():
    """Test token refresh flow."""
    # Create test user
    unique_username = f"refreshtest_{datetime.utcnow().timestamp()}"
    password = "TestPassword123"
    
    async with AsyncSessionLocal() as session:
        # Create user with hashed password
        hashed_password = User.get_password_hash(password)
        test_user = User(
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password=hashed_password,
            is_active=True
        )
        session.add(test_user)
        await session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        # Login to get tokens
        response = await ac.post("/auth/token", data={
            "username": unique_username,
            "password": password,
            "grant_type": "password"
        })
        
        refresh_token = response.json()["data"]["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_response = await ac.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()["data"]
        assert "refresh_token" in refresh_response.json()["data"]
    
    # Clean up - delete test user
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(User).where(User.username == unique_username)
        )
        await session.commit()

@pytest.mark.asyncio
async def test_protected_endpoints_unauthorized():
    """Test that protected endpoints reject unauthorized access."""
    transport = ASGITransport(app=app)
    async with AsyncClient(base_url="http://test", transport=transport) as ac:
        # Try to access a protected endpoint without token
        response = await ac.get("/auth/me")
        assert response.status_code == 401
        
        # Try with invalid token
        response = await ac.get(
            "/auth/me", 
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

@pytest.mark.skipif(True, reason="API key tests require valid user with permissions")
@pytest.mark.asyncio
async def test_api_key_lifecycle():
    """
    Test API key creation, listing, and revocation.
    Requires a valid user with api_keys:* permissions.
    """
    # Create test admin user with required permissions
    unique_username = f"apikeytest_{datetime.utcnow().timestamp()}"
    password = "TestPassword123"
    
    # This test is complex and requires setting up roles and permissions
    # It's marked as skipped for now as it requires more setup
    # The implementation would follow this outline:
    # 1. Create admin user with appropriate roles/permissions
    # 2. Login and get token
    # 3. Create API key 
    # 4. List API keys and verify
    # 5. Revoke API key
    # 6. Check it's been revoked
    # 7. Clean up (delete user)
    assert True

@pytest.mark.skipif(True, reason="Role tests require admin permissions")
@pytest.mark.asyncio
async def test_role_management():
    """
    Test role creation and assignment.
    Requires admin permissions.
    """
    # Similar to API key test, this is complex and requires setup
    # It's marked as skipped for now
    assert True 