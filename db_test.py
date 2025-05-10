#!/usr/bin/env python3
"""
Simple script to test database connection and pgvector functionality directly.
This script is meant to be run directly, not through pytest, to avoid event loop issues.
"""
import asyncio
import json
import os
import logging
from sqlalchemy import text
from dotenv import load_dotenv

# Setup logging and environment variables before importing microservices
logging.basicConfig(level=logging.INFO)
os.environ.setdefault("LOG_LEVEL", "INFO")  # Set log level to uppercase

# Load environment variables
load_dotenv()

# Import the AsyncSessionLocal from our project
from microservices.base_microservice import AsyncSessionLocal

async def setup_database():
    """Set up the database tables and pgvector extension."""
    print("Setting up database...")
    async with AsyncSessionLocal() as session:
        try:
            # Create pgvector extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            print("pgvector extension created or already exists")
            
            # Create tables
            await session.execute(text("""
            CREATE TABLE IF NOT EXISTS lookup_tables (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                values JSONB NOT NULL
            );
            """))
            print("lookup_tables table created or already exists")
            
            await session.execute(text("""
            CREATE TABLE IF NOT EXISTS metadata_store (
                id SERIAL PRIMARY KEY,
                entity_type VARCHAR(255) NOT NULL,
                entity_id VARCHAR(255) NOT NULL,
                metadata JSONB NOT NULL,
                UNIQUE(entity_type, entity_id)
            );
            """))
            print("metadata_store table created or already exists")
            
            await session.execute(text("""
            CREATE TABLE IF NOT EXISTS vectors (
                id SERIAL PRIMARY KEY,
                content_id VARCHAR(255) NOT NULL,
                content_type VARCHAR(255) NOT NULL,
                embedding vector(1536),
                metadata JSONB
            );
            """))
            print("vectors table created or already exists")
            
            # Create indices
            await session.execute(text("CREATE INDEX IF NOT EXISTS idx_vectors_content ON vectors(content_type, content_id);"))
            await session.execute(text("CREATE INDEX IF NOT EXISTS idx_metadata_entity ON metadata_store(entity_type, entity_id);"))
            
            await session.commit()
            print("All database tables and indices created successfully!\n")
            return True
        except Exception as e:
            print(f"Error setting up database: {e}")
            return False

async def test_lookup_table_crud():
    """Test lookup table CRUD operations."""
    print("Testing lookup table CRUD operations...")
    async with AsyncSessionLocal() as session:
        try:
            # Create lookup table
            test_table = {
                "name": "test_priorities",
                "description": "Test priority levels",
                "values": [
                    {"id": 1, "name": "High", "color": "#ff0000"},
                    {"id": 2, "name": "Medium", "color": "#ffff00"},
                    {"id": 3, "name": "Low", "color": "#00ff00"}
                ]
            }
            
            # Check if table already exists
            query = text("SELECT * FROM lookup_tables WHERE name = :name")
            result = await session.execute(query, {"name": test_table["name"]})
            existing = result.fetchone()
            
            if existing:
                # Delete existing table for clean test
                delete_query = text("DELETE FROM lookup_tables WHERE name = :name")
                await session.execute(delete_query, {"name": test_table["name"]})
                await session.commit()
                print(f"Deleted existing lookup table '{test_table['name']}' for clean test")
            
            # Insert new table
            insert_query = text("""
                INSERT INTO lookup_tables (name, description, values) 
                VALUES (:name, :description, :values)
                RETURNING id, name, description, values
            """)
            
            # Make sure to convert Python objects to JSON strings for PostgreSQL
            values_json = json.dumps(test_table["values"])
            
            result = await session.execute(
                insert_query, 
                {
                    "name": test_table["name"], 
                    "description": test_table["description"], 
                    "values": values_json
                }
            )
            await session.commit()
            
            created = result.fetchone()
            assert created is not None, "Failed to create lookup table"
            assert created.name == test_table["name"], "Created table name doesn't match"
            print(f"Created lookup table '{created.name}' with ID {created.id}")
            
            # Get the table
            query = text("SELECT * FROM lookup_tables WHERE name = :name")
            result = await session.execute(query, {"name": test_table["name"]})
            fetched = result.fetchone()
            
            assert fetched is not None, "Failed to fetch lookup table"
            assert fetched.name == test_table["name"], "Fetched table name doesn't match"
            
            # Parse the JSONB column back to Python object
            fetched_values = json.loads(fetched.values) if isinstance(fetched.values, str) else fetched.values
            print(f"Retrieved lookup table '{fetched.name}' with {len(fetched_values)} values")
            
            # Update table
            update_data = {
                "description": "Updated description",
                "values": [
                    {"id": 1, "name": "Highest", "color": "#ff0000"},
                    {"id": 2, "name": "High", "color": "#ff8800"},
                    {"id": 3, "name": "Medium", "color": "#ffff00"},
                    {"id": 4, "name": "Low", "color": "#00ff00"}
                ]
            }
            
            update_query = text("""
                UPDATE lookup_tables 
                SET description = :description, values = :values
                WHERE name = :name
                RETURNING id, name, description, values
            """)
            
            # Convert values to JSON string
            values_json = json.dumps(update_data["values"])
            
            result = await session.execute(
                update_query,
                {
                    "name": test_table["name"],
                    "description": update_data["description"],
                    "values": values_json
                }
            )
            await session.commit()
            
            updated = result.fetchone()
            assert updated is not None, "Failed to update lookup table"
            assert updated.description == update_data["description"], "Updated description doesn't match"
            
            # Parse the JSONB column back to Python object
            updated_values = json.loads(updated.values) if isinstance(updated.values, str) else updated.values
            print(f"Updated lookup table with new description: '{updated.description}' and {len(updated_values)} values")
            
            # Get all tables
            query = text("SELECT * FROM lookup_tables")
            result = await session.execute(query)
            all_tables = result.fetchall()
            print(f"Retrieved {len(all_tables)} lookup tables in total")
            
            # Delete table
            delete_query = text("DELETE FROM lookup_tables WHERE name = :name")
            await session.execute(delete_query, {"name": test_table["name"]})
            await session.commit()
            
            # Verify deletion
            query = text("SELECT * FROM lookup_tables WHERE name = :name")
            result = await session.execute(query, {"name": test_table["name"]})
            deleted = result.fetchone()
            assert deleted is None, "Lookup table was not deleted"
            print(f"Successfully deleted lookup table '{test_table['name']}'\n")
            
            return True
        except Exception as e:
            print(f"Error in lookup table CRUD test: {e}")
            return False

async def test_metadata_storage():
    """Test metadata storage and retrieval."""
    print("Testing metadata storage...")
    async with AsyncSessionLocal() as session:
        try:
            # Define test data
            entity_type = "test_entity"
            entity_id = "test123"
            metadata = {
                "key1": "value1",
                "key2": 42,
                "nested": {
                    "field1": "nested value",
                    "field2": [1, 2, 3]
                }
            }
            
            # Check if metadata already exists
            query = text("""
                SELECT * FROM metadata_store 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """)
            result = await session.execute(
                query, 
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            existing = result.fetchone()
            
            if existing:
                # Delete existing metadata for clean test
                delete_query = text("""
                    DELETE FROM metadata_store 
                    WHERE entity_type = :entity_type AND entity_id = :entity_id
                """)
                await session.execute(
                    delete_query, 
                    {"entity_type": entity_type, "entity_id": entity_id}
                )
                await session.commit()
                print(f"Deleted existing metadata for '{entity_type}/{entity_id}' for clean test")
            
            # Insert metadata
            insert_query = text("""
                INSERT INTO metadata_store (entity_type, entity_id, metadata)
                VALUES (:entity_type, :entity_id, :metadata)
                RETURNING id, entity_type, entity_id, metadata
            """)
            
            # Convert metadata to JSON string
            metadata_json = json.dumps(metadata)
            
            result = await session.execute(
                insert_query,
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "metadata": metadata_json
                }
            )
            await session.commit()
            
            created = result.fetchone()
            assert created is not None, "Failed to create metadata"
            assert created.entity_type == entity_type, "Created metadata entity_type doesn't match"
            print(f"Created metadata for '{created.entity_type}/{created.entity_id}' with ID {created.id}")
            
            # Get metadata
            query = text("""
                SELECT * FROM metadata_store 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """)
            result = await session.execute(
                query, 
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            fetched = result.fetchone()
            
            assert fetched is not None, "Failed to fetch metadata"
            assert fetched.entity_type == entity_type, "Fetched metadata entity_type doesn't match"
            
            # Parse the JSONB column back to Python object
            fetched_metadata = json.loads(fetched.metadata) if isinstance(fetched.metadata, str) else fetched.metadata
            assert fetched_metadata["key1"] == metadata["key1"], "Fetched metadata key1 doesn't match"
            print(f"Retrieved metadata with keys: {', '.join(fetched_metadata.keys())}")
            
            # Update metadata
            updated_metadata = {
                "key1": "updated value",
                "key3": "new value"
            }
            
            update_query = text("""
                UPDATE metadata_store
                SET metadata = :metadata
                WHERE entity_type = :entity_type AND entity_id = :entity_id
                RETURNING id, entity_type, entity_id, metadata
            """)
            
            # Convert updated metadata to JSON string
            updated_metadata_json = json.dumps(updated_metadata)
            
            result = await session.execute(
                update_query,
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "metadata": updated_metadata_json
                }
            )
            await session.commit()
            
            updated = result.fetchone()
            assert updated is not None, "Failed to update metadata"
            
            # Parse the JSONB column back to Python object
            updated_metadata_obj = json.loads(updated.metadata) if isinstance(updated.metadata, str) else updated.metadata
            print(f"Updated metadata with new keys: {', '.join(updated_metadata_obj.keys())}")
            
            # Clean up
            delete_query = text("""
                DELETE FROM metadata_store 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """)
            await session.execute(
                delete_query, 
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            await session.commit()
            print(f"Successfully deleted metadata for '{entity_type}/{entity_id}'\n")
            
            return True
        except Exception as e:
            print(f"Error in metadata storage test: {e}")
            return False

async def test_vector_operations():
    """Test pgvector operations with basic vectors."""
    print("Testing pgvector operations...")
    async with AsyncSessionLocal() as session:
        try:
            # Create a test vector (16-dimensional for simplicity)
            vector_dim = 16
            test_vector = [float(i) / vector_dim for i in range(vector_dim)]
            content_id = "test_vector_1"
            content_type = "test_vectors"
            
            # Clean up any existing test vectors
            delete_query = text("""
                DELETE FROM vectors 
                WHERE content_id = :content_id AND content_type = :content_type
            """)
            await session.execute(
                delete_query, 
                {"content_id": content_id, "content_type": content_type}
            )
            await session.commit()
            
            # Create a temporary table for this test with smaller vector dimension
            await session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS test_vectors (
                id SERIAL PRIMARY KEY,
                content_id VARCHAR(255) NOT NULL,
                content_type VARCHAR(255) NOT NULL,
                embedding vector({vector_dim}),
                metadata JSONB
            );
            """))
            print(f"Created test_vectors table with {vector_dim}-dimensional vectors")
            
            # Insert vector
            insert_query = text(f"""
                INSERT INTO test_vectors (content_id, content_type, embedding, metadata)
                VALUES (:content_id, :content_type, :embedding, :metadata)
                RETURNING id, content_id, content_type
            """)
            
            # Convert metadata to JSON string
            vector_metadata = {"name": "Test Vector", "description": "Vector for testing"}
            metadata_json = json.dumps(vector_metadata)
            
            result = await session.execute(
                insert_query,
                {
                    "content_id": content_id,
                    "content_type": content_type,
                    "embedding": str(test_vector),  # Convert to string for pgvector
                    "metadata": metadata_json
                }
            )
            await session.commit()
            
            created = result.fetchone()
            assert created is not None, "Failed to create vector"
            print(f"Created vector '{created.content_id}' with ID {created.id}")
            
            # Verify we can query the vector
            query = text("""
                SELECT * FROM test_vectors
                WHERE content_id = :content_id AND content_type = :content_type
            """)
            result = await session.execute(
                query, 
                {"content_id": content_id, "content_type": content_type}
            )
            fetched = result.fetchone()
            
            assert fetched is not None, "Failed to fetch vector"
            print(f"Retrieved vector with ID {fetched.id}")
            
            # Clean up the test table
            await session.execute(text("DROP TABLE test_vectors;"))
            await session.commit()
            print("Successfully cleaned up test vectors table\n")
            
            return True
        except Exception as e:
            print(f"Error in vector operations test: {e}")
            return False

async def main():
    """Run all database tests."""
    print("Running database tests...")
    
    # Setup the database
    setup_success = await setup_database()
    if not setup_success:
        print("Database setup failed. Exiting.")
        return
    
    # Run tests
    lookup_success = await test_lookup_table_crud()
    metadata_success = await test_metadata_storage()
    vector_success = await test_vector_operations()
    
    # Print summary
    print("\n=== Database Test Summary ===")
    print(f"Lookup Tables Test: {'✅ PASSED' if lookup_success else '❌ FAILED'}")
    print(f"Metadata Storage Test: {'✅ PASSED' if metadata_success else '❌ FAILED'}")
    print(f"Vector Operations Test: {'✅ PASSED' if vector_success else '❌ FAILED'}")
    print(f"Overall: {'✅ PASSED' if all([lookup_success, metadata_success, vector_success]) else '❌ FAILED'}")
    print("============================\n")

if __name__ == "__main__":
    asyncio.run(main()) 