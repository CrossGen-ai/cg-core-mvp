# CG-Core: Modular Backend System

A modern, modular backend system built with FastAPI that uses the concept of microservices as routers within a single application.

## Architecture

CG-Core uses a "modular monolith" approach - rather than running each microservice as a separate server with its own port, all functionality is organized into modules (routers) within a single FastAPI application. This provides:

- **Simplified deployment**: Only one application to deploy and monitor
- **Reduced overhead**: No inter-service HTTP communication overhead
- **Conceptual separation**: Code is still organized as distinct "microservices"
- **Feature flags**: Enable/disable functionality without changing deployment

### Key Components

1. **Base Microservice**: A shared class that provides common functionality (auth, logging, event handling)
2. **Event System**: Central event handling for pub/sub across the application
3. **Database Service**: PostgreSQL with pgvector for embeddings and Qdrant integration
4. **Feature Flags**: Runtime toggles for functionality

## Project Structure

```
cg-core/
├── microservices/              # Original implementation (for reference)
├── server.py                   # Main FastAPI application that mounts all routers
├── base.py                     # Base service with common utilities
└── README.md                   # This file
```

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL with pgvector extension
- (Optional) Qdrant vector database

### Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the server:
   ```
   python server.py
   ```
   
The server will be available at http://localhost:8000

## API Documentation

Once running, the API documentation is available at:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## Current Endpoints

### Root
- GET `/` - API information
- GET `/health` - Overall system health check

### Event System (Prefix: `/events`)
- GET `/events/ping` - Simple health check for the events service

### Database Service (Prefix: `/database`)
- GET `/database/ping` - Simple health check for the database service

## Feature Flags

Feature flags are controlled through environment variables:
- `FEATURE_FLAG_QDRANT_ENABLED` - Enable Qdrant integration
- `FEATURE_FLAG_OPENAI_ENABLED` - Enable OpenAI embeddings generation

## License

MIT
