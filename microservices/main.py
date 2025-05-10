from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import importlib.util
import sys
import asyncio
from contextlib import asynccontextmanager

from microservices.base_microservice import BaseMicroservice
from microservices.event_handler.router import router as event_router, start_event_handler
from microservices.database.router import router as database_router, start_database_service
from microservices.auth.router import router as auth_router, start_auth_service

# Create shared base microservice instance
base_service = BaseMicroservice()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    try:
        print("Starting lifespan context manager...")
        # Startup: Initialize services
        print("Logging startup event...")
        base_service.log_event("service.startup", {"service": "main"})
        
        print("Starting event dispatcher...")
        # Start event dispatcher background task
        loop = asyncio.get_event_loop()
        loop.create_task(base_service.start_event_dispatcher())
        
        # Initialize microservices
        print("Initializing event handler...")
        await start_event_handler()
        print("Initializing database service...")
        await start_database_service()
        print("Initializing authentication service...")
        await start_auth_service()
        print("All services initialized successfully")
    
        print("Ready to yield control back to FastAPI")
        yield
        print("Shutting down...")
        
        # Shutdown: Cleanup resources
        base_service.log_event("service.shutdown", {"service": "main"})
    except Exception as e:
        print(f"ERROR in lifespan: {e}")
        import traceback
        traceback.print_exc()
        # Still need to yield to prevent hanging
        yield
        print("Shutting down after error...")

# Create main FastAPI app with lifespan
app = FastAPI(
    title="CG-Core API", 
    description="Modular microservices system with a single entry point",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Feature flags
FEATURE_FLAGS = {
    "qdrant_enabled": os.getenv("FEATURE_FLAG_QDRANT_ENABLED", "true").lower() == "true",
    "openai_enabled": os.getenv("FEATURE_FLAG_OPENAI_ENABLED", "true").lower() == "true",
}

# Include routers with prefixes
app.include_router(event_router, prefix="/events", tags=["events"])
app.include_router(database_router, prefix="/database", tags=["database"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/", tags=["root"])
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "CG-Core API",
        "version": "0.1.0",
        "services": ["events", "database", "auth"],
        "feature_flags": FEATURE_FLAGS
    }

@app.get("/health", tags=["health"])
async def health_check():
    """Overall system health check."""
    return {
        "status": "ok",
        "services": {
            "events": "online",
            "database": "online",
            "auth": "online"
        }
    }

# For running directly with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("microservices.main:app", host="0.0.0.0", port=8000, reload=True) 