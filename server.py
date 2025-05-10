#!/usr/bin/env python3
"""
Clean architecture server for CG-Core.
This server directly imports and uses the necessary components.
"""
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from base import base_service, FEATURE_FLAGS
import uvicorn
import os

# Create the FastAPI app
app = FastAPI(title="CG-Core API", description="Modular backend system")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create routers
events_router = APIRouter(prefix="/events", tags=["events"])
database_router = APIRouter(prefix="/database", tags=["database"])

# Add event endpoints
@events_router.get("/ping")
async def events_ping():
    return base_service.mcp_response(message="Events service is alive")

# Add database endpoints
@database_router.get("/ping")
async def database_ping():
    return base_service.mcp_response(message="Database service is alive")

# Root endpoint
@app.get("/")
async def root():
    return base_service.mcp_response(
        message="CG-Core API",
        data={
            "name": "CG-Core API",
            "version": "0.1.0",
            "services": ["events", "database"],
            "feature_flags": FEATURE_FLAGS
        }
    )

# Health check endpoint
@app.get("/health")
async def health():
    # Log the health check
    base_service.log_event("health.check", {"source": "api"})
    
    return base_service.mcp_response(
        message="System health",
        data={
            "status": "ok",
            "services": {
                "events": "online",
                "database": "online"
            },
            "feature_flags": FEATURE_FLAGS
        }
    )

# Include routers
app.include_router(events_router)
app.include_router(database_router)

# Startup event
@app.on_event("startup")
async def startup_event():
    # Log startup
    base_service.log_event("service.startup", {"service": "main"})

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    # Log shutdown
    base_service.log_event("service.shutdown", {"service": "main"})

if __name__ == "__main__":
    # Run the server
    print("Starting CG-Core API server on http://localhost:8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 