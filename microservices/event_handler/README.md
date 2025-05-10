# Event Handler Microservice

A central microservice that manages event publishing, subscription, and logging across all microservices in the system.

## Features

- **Event Publishing**: Publish events with any payload to notify other services
- **Event Persistence**: Store events in the database for future retrieval and analysis 
- **WebSocket Support**: Real-time event streaming via WebSocket
- **Subscription Management**: Register interest in specific event types
- **Event Retrieval API**: Query historical events with optional filtering
- **Logging**: Comprehensive logging of all event activities

## API Endpoints

### Publishing Events

```
POST /publish
```

**Request Body**:
```json
{
  "event_name": "user.created",
  "payload": {
    "user_id": "123",
    "email": "user@example.com",
    "created_at": "2023-08-01T12:00:00Z"
  }
}
```

**Response**:
```json
{
  "status": "ok",
  "message": "Event 'user.created' published.",
  "data": null
}
```

### Retrieving Events

```
GET /events
```

Optional query parameter: `event_name` to filter events.

**Response**:
```json
{
  "status": "ok",
  "message": "success",
  "data": [
    {
      "id": 1,
      "event_name": "user.created",
      "payload": {
        "user_id": "123",
        "email": "user@example.com"
      },
      "created_at": "2023-08-01T12:00:00Z",
      "source": "api",
      "status": "processed"
    }
  ]
}
```

### WebSocket Connection

```
WebSocket /ws
```

After connecting, send JSON messages to subscribe/unsubscribe to events:

**Subscribe to an event**:
```json
{
  "action": "subscribe",
  "event_name": "user.created"
}
```

**Unsubscribe from an event**:
```json
{
  "action": "unsubscribe",
  "event_name": "user.created"
}
```

**Events are received as**:
```json
{
  "event_name": "user.created",
  "payload": {
    "user_id": "123",
    "email": "user@example.com"
  }
}
```

## Usage Examples

### Publishing an Event

```python
import httpx

async def publish_event():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://event-handler-service/publish",
            json={
                "event_name": "user.created",
                "payload": {"user_id": "123"}
            }
        )
        return response.json()
```

### Subscribing to Events via WebSocket

```python
import asyncio
import websockets
import json

async def subscribe_to_events():
    async with websockets.connect("ws://event-handler-service/ws") as websocket:
        # Subscribe to an event type
        await websocket.send(json.dumps({
            "action": "subscribe",
            "event_name": "user.created"
        }))
        
        # Listen for events
        while True:
            event = await websocket.recv()
            event_data = json.loads(event)
            print(f"Received event: {event_data}")
```

## Integration with Base Microservice

The Event Handler builds on the BaseMicroservice class, using its event emission and logging capabilities. All events are persisted to the database using the shared Event model.

## Deployment

The Event Handler should be deployed as a central service that all other microservices can access. It requires:

- PostgreSQL database (for event persistence)
- Environment variables as defined in your `.env` file, including DATABASE_URL
