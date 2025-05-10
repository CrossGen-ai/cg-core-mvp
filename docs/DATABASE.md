# PostgreSQL Database with pgvector

This document explains how to set up and test the PostgreSQL database with the pgvector extension for our application.

## Database Requirements

Our application uses:

1. PostgreSQL for relational data storage
2. pgvector extension for vector embeddings and similarity search
3. JSON/JSONB support for flexible metadata storage

## Docker Setup

We use a Docker container for PostgreSQL with pgvector:

```bash
# Check if the container is running
docker ps | grep postgres

# If not running, start it:
# docker run -d --name local-postgres -p 5432:5432 -e POSTGRES_PASSWORD=yourpassword postgres:latest
```

## Installing pgvector Extension

If you need to install the pgvector extension in your PostgreSQL container:

```bash
# Install required packages and pgvector inside the container
docker exec -it local-postgres bash -c "apt-get update && apt-get install -y postgresql-server-dev-17 make gcc git && git clone https://github.com/pgvector/pgvector.git && cd pgvector && make && make install"

# Create the extension in your database
docker exec -it local-postgres psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Database Schema

Our application uses the following tables:

1. **lookup_tables**: For application lookups and configurations
   ```sql
   CREATE TABLE IF NOT EXISTS lookup_tables (
       id SERIAL PRIMARY KEY,
       name VARCHAR(255) NOT NULL UNIQUE,
       description TEXT,
       values JSONB NOT NULL
   );
   ```

2. **metadata_store**: For flexible metadata storage
   ```sql
   CREATE TABLE IF NOT EXISTS metadata_store (
       id SERIAL PRIMARY KEY,
       entity_type VARCHAR(255) NOT NULL,
       entity_id VARCHAR(255) NOT NULL,
       metadata JSONB NOT NULL,
       UNIQUE(entity_type, entity_id)
   );
   ```

3. **vectors**: For vector embeddings using pgvector
   ```sql
   CREATE TABLE IF NOT EXISTS vectors (
       id SERIAL PRIMARY KEY,
       content_id VARCHAR(255) NOT NULL,
       content_type VARCHAR(255) NOT NULL,
       embedding vector(1536),
       metadata JSONB
   );
   ```

## Testing Database Connectivity

We provide a standalone script to test database connectivity and features:

```bash
# Install required dependencies
pip install -r requirements.txt
pip install python-dotenv  # If not already in requirements

# Run the database test script
./tests/db_test.py
```

The test script verifies:
- Connection to PostgreSQL
- pgvector extension functionality
- CRUD operations for lookup tables and metadata
- Vector operations with pgvector

## Environment Variables

Configure database connection in your `.env` file:

```ini
# PostgreSQL Connection
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/postgres
```

## Using in Development

When developing with this database:

1. Ensure your PostgreSQL Docker container is running
2. Make sure the pgvector extension is installed
3. Update your `.env` file with the correct connection string
4. All database operations are available through the `/database/` API endpoints

## Common Issues and Solutions

1. **Connection Refused**: Ensure the PostgreSQL Docker container is running and port 5432 is exposed
2. **Missing pgvector extension**: Follow the installation instructions above
3. **Authentication failed**: Check your database connection string in the `.env` file
4. **Cannot create extension**: Ensure you have admin privileges (use postgres user)

For more details on our API endpoints and functionality, see the API documentation. 