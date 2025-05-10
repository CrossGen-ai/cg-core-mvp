#!/usr/bin/env python3
"""
Basic FastAPI server.
"""
from fastapi import FastAPI
import uvicorn

# Create a basic FastAPI app
app = FastAPI(title="Basic Server")

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}

if __name__ == "__main__":
    # Run the server directly
    print("Starting basic server on http://localhost:8002...")
    uvicorn.run(app, host="127.0.0.1", port=8002) 