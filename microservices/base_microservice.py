import os
import logging
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Any, Dict, Callable, Awaitable, List
from functools import wraps
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, JSON, select
from datetime import datetime
import json

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("microservice")

# SQLAlchemy async setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String, index=True)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="system")
    status = Column(String, default="new")

# Feature flags and plugin registry (simple config-based)
FEATURE_FLAGS = {}
PLUGINS = {}

# In-memory event subscribers: {event_name: [callback, ...]}
EVENT_SUBSCRIBERS: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}

# --- Feature flag and plugin loading ---
def load_feature_flags():
    for key, value in os.environ.items():
        if key.startswith("FEATURE_"):
            FEATURE_FLAGS[key[8:].lower()] = value.lower() == "true"

def load_plugins():
    pass

class MCPResponse(JSONResponse):
    """
    Standard MCP protocol response for all API endpoints.
    """
    def __init__(self, data: Any = None, message: str = "success", status: str = "ok", **kwargs):
        content = {
            "status": status,
            "message": message,
            "data": data,
        }
        super().__init__(content=content, **kwargs)

class BaseMicroservice:
    """
    Base class for all microservices. Provides:
    - User validation
    - Error/event logging
    - MCP protocol response
    - Plugin/feature flag support
    - Config from environment variables
    - Persistent async event handling (SQLAlchemy)
    """
    def __init__(self):
        load_feature_flags()
        load_plugins()
        self.logger = logger
        self.feature_flags = FEATURE_FLAGS
        self.plugins = PLUGINS
        self.event_subscribers = EVENT_SUBSCRIBERS
        self._event_dispatcher_started = False

    async def user_validation(self, request: Request):
        """
        Dependency for user validation. Checks for a valid user token in headers.
        """
        user_token = request.headers.get("Authorization")
        if not user_token or not self._is_valid_user(user_token):
            self.logger.warning("Unauthorized access attempt.")
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user_token

    def _is_valid_user(self, token: str) -> bool:
        # Placeholder: implement real validation (e.g., JWT, DB lookup)
        return token == os.getenv("SECRET_KEY", "your-secret-key")

    def mcp_response(self, data: Any = None, message: str = "success", status: str = "ok"):
        """
        Return a standard MCP protocol response.
        """
        return MCPResponse(data=data, message=message, status=status)

    def log_event(self, event: str, details: Dict[str, Any] = None):
        self.logger.info(f"EVENT: {event} | Details: {details}")

    def log_error(self, error: Exception, context: str = ""):
        self.logger.error(f"ERROR: {str(error)} | Context: {context}")

    def feature_enabled(self, feature: str) -> bool:
        return self.feature_flags.get(feature, False)

    def use_plugin(self, name: str, *args, **kwargs):
        plugin = self.plugins.get(name)
        if plugin:
            return plugin(*args, **kwargs)
        raise NotImplementedError(f"Plugin '{name}' not found.")

    # --- Persistent Async Event System ---
    async def emit_event(self, event_name: str, payload: dict, source: str = "system"):
        """
        Emit (persist) an event to the database and notify subscribers asynchronously.
        """
        async with AsyncSessionLocal() as session:
            event = Event(event_name=event_name, payload=payload, source=source)
            session.add(event)
            await session.commit()
            await session.refresh(event)
        self.log_event(event_name, payload)
        # Notify in-memory subscribers
        await self._notify_subscribers(event)

    def subscribe(self, event_name: str, callback: Callable[[Event], Awaitable[None]]):
        """
        Register a coroutine callback for a given event name.
        """
        if event_name not in self.event_subscribers:
            self.event_subscribers[event_name] = []
        self.event_subscribers[event_name].append(callback)

    async def _notify_subscribers(self, event: Event):
        """
        Call all registered callbacks for the event_name.
        """
        callbacks = self.event_subscribers.get(event.event_name, [])
        for cb in callbacks:
            await cb(event)

    async def start_event_dispatcher(self, poll_interval: float = 2.0):
        """
        Background task: poll the DB for new events and dispatch to subscribers.
        Should be started once at app startup.
        """
        if self._event_dispatcher_started:
            return
        self._event_dispatcher_started = True
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Event).where(Event.status == "new"))
                    new_events = result.scalars().all()
                    for event in new_events:
                        await self._notify_subscribers(event)
                        event.status = "processed"
                        session.add(event)
                    await session.commit()
            except Exception as e:
                self.log_error(e, context="Event dispatcher loop")
            await asyncio.sleep(poll_interval) 