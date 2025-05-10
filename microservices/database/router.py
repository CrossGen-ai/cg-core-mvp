from fastapi import APIRouter, Query, Depends, HTTPException, Body
from microservices.base_microservice import BaseMicroservice
from typing import Dict, List, Optional, Any, Union
import os
import json
import asyncio
from sqlalchemy import create_engine, Column, Integer, String, JSON, MetaData, Table, select, insert, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector
import numpy as np
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# Initialize router
router = APIRouter()
db_service = BaseMicroservice()

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))  # Default for text-embedding-ada-002

# Initialize SQLAlchemy async engine and session factory
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Initialize OpenAI client (lazy initialization to handle missing API key)
openai_client = None

# Initialize Qdrant client
qdrant_client = QdrantClient(url=QDRANT_URL)

# Dependency to get DB session
async def get_db():
    async with async_session() as session:
        yield session

# Metadata object for database tables
metadata = MetaData()

# Define tables
lookup_tables = Table(
    'lookup_tables', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False, unique=True),
    Column('description', String),
    Column('values', JSON, nullable=False),  # JSON array of key-value pairs
)

metadata_store = Table(
    'metadata_store', metadata,
    Column('id', Integer, primary_key=True),
    Column('entity_type', String, nullable=False),  # What kind of entity this metadata belongs to
    Column('entity_id', String, nullable=False),    # ID of the entity
    Column('metadata', JSON, nullable=False),       # Arbitrary JSON metadata
)

vectors = Table(
    'vectors', metadata,
    Column('id', Integer, primary_key=True),
    Column('content_id', String, nullable=False),   # ID of the content this vector represents
    Column('content_type', String, nullable=False), # Type of content (document, page, etc.)
    Column('embedding', Vector(EMBEDDING_DIMENSION)), # pgvector column
    Column('metadata', JSON),                       # Additional metadata
)

# Helper functions
async def get_openai_client():
    """Get an initialized OpenAI client, creating it if needed."""
    global openai_client
    if openai_client is None:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return openai_client

async def generate_embedding(text: str) -> List[float]:
    """Generate an embedding for the given text using OpenAI's API."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        client = await get_openai_client()
        response = await client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        embedding = response.data[0].embedding
        return embedding
    except Exception as e:
        db_service.log_error(e, context=f"Failed to generate embedding for text: {text[:50]}...")
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {str(e)}")

async def ensure_qdrant_collection(collection_name: str):
    """Ensure that a collection exists in Qdrant."""
    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE)
            )
            db_service.log_event(f"Created Qdrant collection: {collection_name}")
    except Exception as e:
        db_service.log_error(e, context=f"Failed to ensure Qdrant collection: {collection_name}")
        raise HTTPException(status_code=500, detail=f"Qdrant operation failed: {str(e)}")

# API Endpoints

# Lookup table management
@router.get("/lookup-tables")
async def get_lookup_tables(db: AsyncSession = Depends(get_db)):
    """Get all lookup tables."""
    try:
        query = select(lookup_tables)
        result = await db.execute(query)
        tables = result.fetchall()
        return db_service.mcp_response(data=[dict(table) for table in tables])
    except Exception as e:
        db_service.log_error(e, context="Failed to get lookup tables")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.get("/lookup-tables/{name}")
async def get_lookup_table(name: str, db: AsyncSession = Depends(get_db)):
    """Get a specific lookup table by name."""
    try:
        query = select(lookup_tables).where(lookup_tables.c.name == name)
        result = await db.execute(query)
        table = result.fetchone()
        
        if not table:
            raise HTTPException(status_code=404, detail=f"Lookup table '{name}' not found")
            
        return db_service.mcp_response(data=dict(table))
    except HTTPException:
        raise
    except Exception as e:
        db_service.log_error(e, context=f"Failed to get lookup table: {name}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.post("/lookup-tables")
async def create_lookup_table(
    name: str = Body(...),
    description: str = Body(None),
    values: List[Dict[str, Any]] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a new lookup table."""
    try:
        # Check if table already exists
        query = select(lookup_tables).where(lookup_tables.c.name == name)
        result = await db.execute(query)
        existing = result.fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Lookup table '{name}' already exists")
            
        # Insert new table
        stmt = insert(lookup_tables).values(
            name=name,
            description=description,
            values=values
        )
        await db.execute(stmt)
        await db.commit()
        
        # Log the event
        await db_service.emit_event("lookup_table.created", {"name": name})
        
        return db_service.mcp_response(
            message=f"Lookup table '{name}' created successfully",
            data={"name": name, "description": description, "values": values}
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        db_service.log_error(e, context=f"Failed to create lookup table: {name}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.put("/lookup-tables/{name}")
async def update_lookup_table(
    name: str,
    description: Optional[str] = Body(None),
    values: Optional[List[Dict[str, Any]]] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing lookup table."""
    try:
        # Check if table exists
        query = select(lookup_tables).where(lookup_tables.c.name == name)
        result = await db.execute(query)
        existing = result.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail=f"Lookup table '{name}' not found")
            
        # Prepare update values
        update_values = {}
        if description is not None:
            update_values["description"] = description
        if values is not None:
            update_values["values"] = values
            
        if not update_values:
            return db_service.mcp_response(
                message="No updates provided",
                data=dict(existing)
            )
            
        # Update table
        stmt = update(lookup_tables).where(lookup_tables.c.name == name).values(**update_values)
        await db.execute(stmt)
        await db.commit()
        
        # Get updated table
        query = select(lookup_tables).where(lookup_tables.c.name == name)
        result = await db.execute(query)
        updated = result.fetchone()
        
        # Log the event
        await db_service.emit_event("lookup_table.updated", {"name": name})
        
        return db_service.mcp_response(
            message=f"Lookup table '{name}' updated successfully",
            data=dict(updated)
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        db_service.log_error(e, context=f"Failed to update lookup table: {name}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.delete("/lookup-tables/{name}")
async def delete_lookup_table(name: str, db: AsyncSession = Depends(get_db)):
    """Delete a lookup table."""
    try:
        # Check if table exists
        query = select(lookup_tables).where(lookup_tables.c.name == name)
        result = await db.execute(query)
        existing = result.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail=f"Lookup table '{name}' not found")
            
        # Delete table
        stmt = delete(lookup_tables).where(lookup_tables.c.name == name)
        await db.execute(stmt)
        await db.commit()
        
        # Log the event
        await db_service.emit_event("lookup_table.deleted", {"name": name})
        
        return db_service.mcp_response(
            message=f"Lookup table '{name}' deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        db_service.log_error(e, context=f"Failed to delete lookup table: {name}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

# Metadata storage and retrieval
@router.post("/metadata")
async def store_metadata(
    entity_type: str = Body(...),
    entity_id: str = Body(...),
    metadata: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Store metadata for an entity."""
    try:
        # Check if metadata already exists for this entity
        query = select(metadata_store).where(
            (metadata_store.c.entity_type == entity_type) & 
            (metadata_store.c.entity_id == entity_id)
        )
        result = await db.execute(query)
        existing = result.fetchone()
        
        if existing:
            # Update existing metadata
            stmt = update(metadata_store).where(
                (metadata_store.c.entity_type == entity_type) & 
                (metadata_store.c.entity_id == entity_id)
            ).values(metadata=metadata)
            await db.execute(stmt)
        else:
            # Insert new metadata
            stmt = insert(metadata_store).values(
                entity_type=entity_type,
                entity_id=entity_id,
                metadata=metadata
            )
            await db.execute(stmt)
            
        await db.commit()
        
        # Log the event
        await db_service.emit_event("metadata.stored", {
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        return db_service.mcp_response(
            message=f"Metadata stored for {entity_type}/{entity_id}",
            data={"entity_type": entity_type, "entity_id": entity_id, "metadata": metadata}
        )
    except Exception as e:
        await db.rollback()
        db_service.log_error(e, context=f"Failed to store metadata for {entity_type}/{entity_id}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.get("/metadata/{entity_type}/{entity_id}")
async def get_metadata(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get metadata for an entity."""
    try:
        query = select(metadata_store).where(
            (metadata_store.c.entity_type == entity_type) & 
            (metadata_store.c.entity_id == entity_id)
        )
        result = await db.execute(query)
        metadata_record = result.fetchone()
        
        if not metadata_record:
            raise HTTPException(status_code=404, detail=f"Metadata for {entity_type}/{entity_id} not found")
            
        return db_service.mcp_response(data=dict(metadata_record))
    except HTTPException:
        raise
    except Exception as e:
        db_service.log_error(e, context=f"Failed to get metadata for {entity_type}/{entity_id}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

# Vector embeddings operations
@router.post("/embeddings")
async def create_embedding(
    content_id: str = Body(...),
    content_type: str = Body(...),
    text: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    store_in_qdrant: bool = Body(False),
    collection_name: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate and store an embedding for the given text."""
    try:
        # Generate embedding
        embedding = await generate_embedding(text)
        
        # Store in PostgreSQL
        stmt = insert(vectors).values(
            content_id=content_id,
            content_type=content_type,
            embedding=embedding,
            metadata=metadata or {}
        )
        await db.execute(stmt)
        await db.commit()
        
        # Store in Qdrant if requested
        if store_in_qdrant:
            if not collection_name:
                collection_name = content_type  # Use content_type as default collection name
                
            # Ensure collection exists
            await ensure_qdrant_collection(collection_name)
            
            # Store vector in Qdrant
            qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=content_id,
                        vector=embedding,
                        payload=metadata or {}
                    )
                ]
            )
        
        # Log the event
        await db_service.emit_event("embedding.created", {
            "content_id": content_id,
            "content_type": content_type
        })
        
        return db_service.mcp_response(
            message=f"Embedding created for {content_type}/{content_id}",
            data={
                "content_id": content_id,
                "content_type": content_type,
                "vector_length": len(embedding),
                "stored_in_qdrant": store_in_qdrant
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        db_service.log_error(e, context=f"Failed to create embedding for {content_type}/{content_id}")
        raise HTTPException(status_code=500, detail=f"Embedding operation failed: {str(e)}")

@router.get("/embeddings/{content_type}/{content_id}")
async def get_embedding(content_type: str, content_id: str, db: AsyncSession = Depends(get_db)):
    """Get a stored embedding."""
    try:
        query = select(vectors).where(
            (vectors.c.content_type == content_type) & 
            (vectors.c.content_id == content_id)
        )
        result = await db.execute(query)
        vector_record = result.fetchone()
        
        if not vector_record:
            raise HTTPException(status_code=404, detail=f"Embedding for {content_type}/{content_id} not found")
            
        # Convert embedding to list for JSON serialization
        record_dict = dict(vector_record)
        record_dict["embedding"] = record_dict["embedding"].tolist() if hasattr(record_dict["embedding"], "tolist") else record_dict["embedding"]
            
        return db_service.mcp_response(data=record_dict)
    except HTTPException:
        raise
    except Exception as e:
        db_service.log_error(e, context=f"Failed to get embedding for {content_type}/{content_id}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@router.post("/search/similar")
async def search_similar(
    text: str = Body(...),
    content_type: Optional[str] = Body(None),
    limit: int = Body(10),
    use_qdrant: bool = Body(False),
    collection_name: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Search for similar content based on vector similarity."""
    try:
        # Generate embedding for the query text
        query_embedding = await generate_embedding(text)
        
        results = []
        
        if use_qdrant:
            if not collection_name and not content_type:
                raise HTTPException(status_code=400, detail="Either collection_name or content_type must be provided when using Qdrant")
                
            # Use content_type as collection name if not specified
            if not collection_name:
                collection_name = content_type
                
            # Search in Qdrant
            search_results = qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit
            )
            
            # Format results
            results = [{
                "content_id": str(result.id),
                "content_type": collection_name,
                "similarity": result.score,
                "metadata": result.payload
            } for result in search_results]
        else:
            # Search in PostgreSQL using pgvector
            where_clause = ""
            if content_type:
                where_clause = f"WHERE content_type = '{content_type}'"
                
            # Use raw SQL for vector similarity search with pgvector
            raw_query = f"""
            SELECT 
                content_id, 
                content_type, 
                1 - (embedding <=> :embedding) as similarity,
                metadata
            FROM vectors
            {where_clause}
            ORDER BY similarity DESC
            LIMIT :limit
            """
            
            # Execute raw SQL query
            result = await db.execute(
                raw_query,
                {"embedding": query_embedding, "limit": limit}
            )
            
            # Format results
            rows = result.fetchall()
            results = [{
                "content_id": row.content_id,
                "content_type": row.content_type,
                "similarity": float(row.similarity),
                "metadata": row.metadata
            } for row in rows]
        
        return db_service.mcp_response(
            message=f"Found {len(results)} similar items",
            data=results
        )
    except HTTPException:
        raise
    except Exception as e:
        db_service.log_error(e, context=f"Failed to search for similar content")
        raise HTTPException(status_code=500, detail=f"Search operation failed: {str(e)}")

# Database Migration API
@router.post("/migrations/pgvector")
async def apply_pgvector_migration():
    """Apply the pgvector extension to the database."""
    try:
        # Create an engine for running raw SQL
        sync_engine = create_engine(DATABASE_URL.replace("+asyncpg", ""))
        
        # Run migration
        with sync_engine.connect() as conn:
            # Enable pgvector extension
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create vectors table if it doesn't exist
            conn.execute(f"""
            CREATE TABLE IF NOT EXISTS vectors (
                id SERIAL PRIMARY KEY,
                content_id VARCHAR(255) NOT NULL,
                content_type VARCHAR(255) NOT NULL,
                embedding vector({EMBEDDING_DIMENSION}),
                metadata JSONB
            );
            """)
            
            # Create index on content ID and type
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vectors_content ON vectors(content_type, content_id);
            """)
            
            # Create lookup tables table if it doesn't exist
            conn.execute("""
            CREATE TABLE IF NOT EXISTS lookup_tables (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                values JSONB NOT NULL
            );
            """)
            
            # Create metadata store table if it doesn't exist
            conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata_store (
                id SERIAL PRIMARY KEY,
                entity_type VARCHAR(255) NOT NULL,
                entity_id VARCHAR(255) NOT NULL,
                metadata JSONB NOT NULL,
                UNIQUE(entity_type, entity_id)
            );
            """)
            
            # Create index on entity type and ID
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_entity ON metadata_store(entity_type, entity_id);
            """)
            
            conn.commit()
        
        return db_service.mcp_response(
            message="Successfully applied pgvector migration",
            data={
                "tables_created": ["vectors", "lookup_tables", "metadata_store"],
                "extensions_enabled": ["vector"]
            }
        )
    except Exception as e:
        db_service.log_error(e, context="Failed to apply pgvector migration")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

# Health check
@router.get("/health")
async def health_check():
    """Check the health of the database service."""
    try:
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute(select(1))
        
        # Check Qdrant connection
        collections = qdrant_client.get_collections()
        
        # Check OpenAI API key
        openai_status = "Configured" if OPENAI_API_KEY else "Not configured"
        
        return db_service.mcp_response(
            message="Database service is healthy",
            data={
                "postgresql": "Connected",
                "qdrant": "Connected",
                "openai": openai_status
            }
        )
    except Exception as e:
        db_service.log_error(e, context="Health check failed")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# Start database service functions
async def start_database_service():
    """
    Start the database service functionality. 
    This is called from the main app startup.
    """
    db_service.log_event("service.startup", {"service": "database"}) 