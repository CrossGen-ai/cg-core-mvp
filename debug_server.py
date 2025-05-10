#!/usr/bin/env python3
"""
Debug server for diagnosing issues with the CG-Core system.
"""
import uvicorn
import os
import sys
import traceback

if __name__ == "__main__":
    try:
        print("="*80)
        print("Starting debug server...")
        print("Setting PYTHONPATH to current directory...")
        sys.path.insert(0, os.getcwd())
        
        print("Importing app from microservices.main...")
        from microservices.main import app
        
        print("App imported successfully.")
        print(f"App title: {app.title}")
        print(f"App description: {app.description}")
        
        print("App routes:")
        for route in app.routes:
            print(f"  {route.path} [{','.join(route.methods) if hasattr(route, 'methods') and route.methods else 'WebSocket'}]")
        
        print("="*80)
        print("Starting server on http://127.0.0.1:8080...")
        uvicorn.run(app, host="127.0.0.1", port=8080, log_level="debug")
    except Exception as e:
        print(f"ERROR starting server: {e}")
        traceback.print_exc()
        sys.exit(1) 