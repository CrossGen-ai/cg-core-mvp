# Database Microservice

A central microservice that provides access to PostgreSQL with pgvector support, Qdrant vector database, OpenAI embeddings generation, lookup tables, and rich metadata storage.

## Features

- **PostgreSQL with pgvector**: Store and query vector embeddings directly in PostgreSQL
- **Qdrant Integration**: Optional vector storage in Qdrant for advanced similarity search
- **OpenAI Embeddings**: Generate embeddings from text content using OpenAI's API
- **Lookup Tables**: Manage shared lookup values across the application
- **Rich Metadata**: Store and retrieve arbitrary metadata for any entity
- **Similarity Search**: Find similar content based on vector similarity in PostgreSQL or Qdrant

## Setup

### Prerequisites

- PostgreSQL database with pgvector extension
- Qdrant server (optional)
- OpenAI API key (for embeddings generation)

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`)
- `QDRANT_URL`: Qdrant server URL (default: `http://localhost:6333`)
- `OPENAI_API_KEY`: Your OpenAI API key
- `EMBEDDING_MODEL`: OpenAI embedding model to use (default: `text-embedding-ada-002`)
- `EMBEDDING_DIMENSION`: Dimension of embeddings (default: `1536`)

### Database Migrations

The microservice includes a migration endpoint to set up the required database schema:

```
POST /migrations/pgvector
```

Alternatively, you can run the SQL migrations directly:

1. For the event logging system: `events_migration.sql`
2. For pgvector and metadata tables: `pgvector_migration.sql`

## API Endpoints

### Health Check

```
GET /health
```

Returns the status of the database connections and configured services.

### Lookup Table Management

#### Get All Lookup Tables

```
GET /lookup-tables
```

Returns a list of all lookup tables.

#### Get Lookup Table by Name

```
GET /lookup-tables/{name}
```

Returns a specific lookup table by name.

#### Create Lookup Table

```
POST /lookup-tables
```

**Request Body**:
```json
{
  "name": "priorities",
  "description": "Task priority levels",
  "values": [
    {"id": 1, "name": "High", "color": "#ff0000"},
    {"id": 2, "name": "Medium", "color": "#ffff00"},
    {"id": 3, "name": "Low", "color": "#00ff00"}
  ]
}
```

#### Update Lookup Table

```
PUT /lookup-tables/{name}
```

**Request Body** (all fields optional):
```json
{
  "description": "Updated description",
  "values": [
    {"id": 1, "name": "Critical", "color": "#ff0000"},
    {"id": 2, "name": "High", "color": "#ff8800"},
    {"id": 3, "name": "Medium", "color": "#ffff00"},
    {"id": 4, "name": "Low", "color": "#00ff00"}
  ]
}
```

#### Delete Lookup Table

```
DELETE /lookup-tables/{name}
```

### Metadata Storage

#### Store Metadata

```
POST /metadata
```

**Request Body**:
```json
{
  "entity_type": "user",
  "entity_id": "123",
  "metadata": {
    "preferences": {
      "theme": "dark",
      "notifications": true
    },
    "last_active": "2023-08-01T12:00:00Z"
  }
}
```

#### Get Metadata

```
GET /metadata/{entity_type}/{entity_id}
```

Returns the metadata for the specified entity.

### Vector Embeddings

#### Create Embedding

```
POST /embeddings
```

**Request Body**:
```json
{
  "content_id": "document-123",
  "content_type": "document",
  "text": "This is the text content to generate an embedding for.",
  "metadata": {
    "title": "Sample Document",
    "author": "John Doe"
  },
  "store_in_qdrant": true,
  "collection_name": "documents"
}
```

#### Get Embedding

```
GET /embeddings/{content_type}/{content_id}
```

Returns the stored embedding for the specified content.

#### Search Similar Content

```
POST /search/similar
```

**Request Body**:
```json
{
  "text": "Search query text",
  "content_type": "document",
  "limit": 10,
  "use_qdrant": false
}
```

Returns the most similar content items to the provided text, based on vector similarity.

## Usage Examples

### Managing Lookup Tables

```python
import httpx

async def create_task_priorities():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://database-service/lookup-tables",
            json={
                "name": "task_priorities",
                "description": "Task priority levels",
                "values": [
                    {"id": 1, "name": "High", "color": "#ff0000"},
                    {"id": 2, "name": "Medium", "color": "#ffff00"},
                    {"id": 3, "name": "Low", "color": "#00ff00"}
                ]
            }
        )
        return response.json()
```

### Storing and Retrieving Metadata

```python
import httpx

async def store_user_preferences(user_id, preferences):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://database-service/metadata",
            json={
                "entity_type": "user",
                "entity_id": user_id,
                "metadata": {
                    "preferences": preferences,
                    "last_updated": "2023-08-01T12:00:00Z"
                }
            }
        )
        return response.json()

async def get_user_preferences(user_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://database-service/metadata/user/{user_id}"
        )
        return response.json()
```

### Working with Embeddings

```python
import httpx

async def index_document(doc_id, title, content):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://database-service/embeddings",
            json={
                "content_id": doc_id,
                "content_type": "document",
                "text": content,
                "metadata": {
                    "title": title
                },
                "store_in_qdrant": True
            }
        )
        return response.json()

async def find_similar_documents(query):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://database-service/search/similar",
            json={
                "text": query,
                "content_type": "document",
                "limit": 5
            }
        )
        return response.json()
```

## Integration with Base Microservice

This service inherits from the BaseMicroservice class, utilizing its:

- MCP protocol for standard API responses
- Event logging and emission capabilities
- Error handling and logging
- Feature flag support

## Event Table Migration

To create the persistent event log table for the async event system, run this SQL in your Postgres database:

```sql
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(255) DEFAULT 'system',
    status VARCHAR(32) DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS idx_events_event_name ON events(event_name);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
```

