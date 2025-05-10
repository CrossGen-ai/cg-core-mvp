# Tests Directory

This directory contains standalone test scripts that verify functionality outside the normal pytest framework.

## Available Tests

### Database Tests

- **db_test.py**: Standalone script to test the PostgreSQL database with pgvector extension
  - Tests database connectivity
  - Verifies pgvector extension is working
  - Tests CRUD operations for lookup tables
  - Tests metadata storage
  - Tests vector embedding operations

## Running Tests

To run the database test:

```bash
# Make sure you are in the root directory
cd /path/to/project

# Activate virtual environment if needed
source venv/bin/activate

# Run the database test script
python tests/db_test.py
```

## Test Structure

Each standalone test script should:

1. Be executable directly (not just through pytest)
2. Include proper logging of test results
3. Provide a clear summary of what passed/failed
4. Clean up any test data it creates

## Integration with Pytest

Many of these standalone tests verify functionality that's also covered by pytest tests.
In those cases, the pytest tests are often marked with @pytest.mark.skip to avoid
duplicating the same tests.

For example, the database tests in `microservices/tests/test_database.py` are skipped
with the reason "Database functionality verified with db_test.py script". 