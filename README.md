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
2. **Event Handler**: Processes asynchronous events between services
3. **Database Service**: Manages interactions with PostgreSQL and pgvector
4. **Authentication System**: Handles user management, JWT tokens, and API keys

## Project Structure

```
cg-core/
├── server.py                # Main server entry point
├── base.py                  # Base utilities
├── env.example              # Example environment config
├── microservices/
│   ├── __init__.py
│   ├── main.py              # Main FastAPI application
│   ├── base_microservice.py # Base microservice class
│   ├── auth/                # Authentication microservice
│   │   ├── __init__.py
│   │   ├── models.py        # User and role models
│   │   ├── router.py        # Auth endpoints
│   │   ├── jwt.py           # JWT token handling
│   │   ├── api_keys.py      # API key management
│   │   ├── users.py         # User service
│   │   └── middleware.py    # Auth middleware
│   ├── database/            # Database microservice
│   │   ├── __init__.py
│   │   └── router.py        # Database endpoints
│   ├── event_handler/       # Event handler microservice
│   │   ├── __init__.py
│   │   └── router.py        # Event endpoints
│   └── tests/               # Microservice tests
├── docs/                    # Documentation
│   ├── DATABASE.md          # Database service documentation
│   └── AUTHENTICATION.md    # Authentication system documentation
└── tests/                   # Standalone test scripts
```

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL with pgvector extension
- Docker (optional, for containerized development)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cg-core.git
   cd cg-core
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create an `.env` file based on the example:
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. Start the server:
   ```bash
   python server.py
   ```

The API will be available at http://localhost:8000 with API documentation at http://localhost:8000/docs.

## API Documentation

Once the server is running, access the Swagger UI at http://localhost:8000/docs or ReDoc at http://localhost:8000/redoc.

## Key Features

### Authentication

The authentication system provides:

- User registration and login with JWT tokens
- Role-Based Access Control (RBAC)
- API key management for N8N integration
- Secure middleware for protecting endpoints

See [Authentication Documentation](docs/AUTHENTICATION.md) for details.

### Database Service

The database service provides:

- PostgreSQL integration with SQLAlchemy
- pgvector support for vector embeddings
- General-purpose lookup tables
- Metadata storage (JSON)

See [Database Documentation](docs/DATABASE.md) for details.

### Event System

The event system provides:

- Persistent event storage
- Event subscription and publishing
- Async event processing
- Cross-service communication

## Feature Flags

Feature flags are controlled through environment variables:
- `FEATURE_FLAG_QDRANT_ENABLED` - Enable Qdrant integration
- `FEATURE_FLAG_OPENAI_ENABLED` - Enable OpenAI embeddings generation

## License

MIT
