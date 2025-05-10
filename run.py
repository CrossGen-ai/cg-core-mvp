#!/usr/bin/env python3
"""
Run script for the CG-Core API.
This script launches the single FastAPI server with all microservices mounted as routers.
"""
import uvicorn
import sys
import traceback

if __name__ == "__main__":
    try:
        # Print information about the server
        print("Starting CG-Core API server...")
        print("Access the API at http://localhost:8000")
        print("API documentation at http://localhost:8000/docs")
        
        # Run the server
        uvicorn.run(
            "microservices.main:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="info"
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        traceback.print_exc()
        sys.exit(1) 