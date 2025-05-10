from fastapi import APIRouter, WebSocket, Request, Depends, WebSocketDisconnect, Query
from microservices.base_microservice import BaseMicroservice, Event, AsyncSessionLocal
from typing import List, Dict, Set
import asyncio
import json
from sqlalchemy import select

# Initialize router
router = APIRouter()
event_handler = BaseMicroservice()

# In-memory subscription registry: event_name -> set of websockets
subscriptions: Dict[str, Set[WebSocket]] = {}

@router.post("/publish")
async def publish_event(request: Request):
    """
    Publish an event to the system. Expects JSON: {"event_name": str, "payload": dict}
    """
    data = await request.json()
    event_name = data.get("event_name")
    payload = data.get("payload", {})
    if not event_name:
        return event_handler.mcp_response(message="Missing event_name", status="error")
    # Persist and log event
    await event_handler.emit_event(event_name, payload, source="api")
    # Notify WebSocket subscribers
    for ws in subscriptions.get(event_name, set()).copy():
        try:
            await ws.send_text(json.dumps({"event_name": event_name, "payload": payload}))
        except Exception:
            subscriptions[event_name].discard(ws)
    return event_handler.mcp_response(message=f"Event '{event_name}' published.")

@router.post("/subscribe")
async def subscribe(request: Request):
    """
    Register interest in an event type. Expects JSON: {"event_name": str}
    (For HTTP clients, this is a no-op; for WebSocket, handled in /ws)
    """
    return event_handler.mcp_response(message="Use WebSocket for real-time subscriptions.")

@router.post("/unsubscribe")
async def unsubscribe(request: Request):
    """
    Unregister interest in an event type. Expects JSON: {"event_name": str}
    (For HTTP clients, this is a no-op; for WebSocket, handled in /ws)
    """
    return event_handler.mcp_response(message="Use WebSocket for real-time subscriptions.")

@router.get("/events")
async def get_events(event_name: str = Query(None)):
    """
    Retrieve persisted events (optionally filter by event_name)
    """
    async with AsyncSessionLocal() as session:
        # Use SQLAlchemy 2.0 style with select()
        if event_name:
            stmt = select(Event).where(Event.event_name == event_name)
        else:
            stmt = select(Event)
        
        result = await session.execute(stmt)
        events = result.scalars().all()
        return event_handler.mcp_response(data=[{
            "id": e.id,
            "event_name": e.event_name,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
            "source": e.source,
            "status": e.status
        } for e in events])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event streaming.
    Client must send {"action": "subscribe", "event_name": str} or {"action": "unsubscribe", ...}
    """
    await websocket.accept()
    client_subs = set()
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
            except Exception:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue
            action = data.get("action")
            event_name = data.get("event_name")
            if action == "subscribe" and event_name:
                subscriptions.setdefault(event_name, set()).add(websocket)
                client_subs.add(event_name)
                await websocket.send_text(json.dumps({"subscribed": event_name}))
            elif action == "unsubscribe" and event_name:
                subscriptions.get(event_name, set()).discard(websocket)
                client_subs.discard(event_name)
                await websocket.send_text(json.dumps({"unsubscribed": event_name}))
            else:
                await websocket.send_text(json.dumps({"error": "Invalid action or missing event_name"}))
    except WebSocketDisconnect:
        # Cleanup on disconnect
        for event_name in client_subs:
            subscriptions.get(event_name, set()).discard(websocket)

# Initialize router functionality
async def start_event_handler():
    """
    Start the event handler service functionality.
    This is called from the main app startup.
    """
    await event_handler.start_event_dispatcher()
    event_handler.log_event("service.startup", {"service": "event_handler"}) 