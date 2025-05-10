#!/usr/bin/env python3
"""
Minimal server for testing the microservices.main app.
"""
import uvicorn
import os
import sys

if __name__ == "__main__":
    print("Starting minimal CG-Core server...")
    print("Setting PYTHONPATH to current directory...")
    sys.path.insert(0, os.getcwd())
    
    # Import the app
    from microservices.main import app
    
    # Print app info for debugging
    print(f"App title: {app.title}")
    print(f"App description: {app.description}")
    print("App routes:")
    for route in app.routes:
        print(f"  {route.path} [{','.join(route.methods) if hasattr(route, 'methods') else 'WebSocket'}]")
    
    # Run the server with explicit parameters and debug
    print("Starting server on http://localhost:8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="debug") 