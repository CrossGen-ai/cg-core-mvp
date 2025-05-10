"""
Base utilities for CG-Core services.

This module provides common functionality for all services:
- Logging
- Feature flags
- MCP response formatting 
- Database connections (if needed)
"""

import os
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Feature flags (can be expanded as needed)
FEATURE_FLAGS = {
    "qdrant_enabled": os.getenv("FEATURE_FLAG_QDRANT_ENABLED", "true").lower() == "true",
    "openai_enabled": os.getenv("FEATURE_FLAG_OPENAI_ENABLED", "true").lower() == "true",
}

class BaseService:
    """Base service with common functionality."""
    
    def __init__(self, service_name: str = "core"):
        """Initialize base service."""
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
    
    def log_event(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Log an event."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "event": event_name,
            "data": data or {},
        }
        self.logger.info(f"EVENT: {json.dumps(log_data)}")
        return log_data
    
    def log_error(self, error: Exception, context: Optional[str] = None) -> None:
        """Log an error with optional context."""
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "context": context or "unknown",
        }
        self.logger.error(f"ERROR: {json.dumps(error_data)}")
        return error_data
    
    def mcp_response(
        self, 
        message: str = "ok", 
        status: str = "ok", 
        data: Optional[Union[Dict, List, str, int, bool]] = None
    ) -> Dict[str, Any]:
        """Format a standard MCP response."""
        response = {
            "message": message,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if data is not None:
            response["data"] = data
            
        return response
    
    def get_feature_flag(self, flag_name: str) -> bool:
        """Get the status of a feature flag."""
        return FEATURE_FLAGS.get(flag_name, False)

# Create a shared base service instance for use throughout the app
base_service = BaseService() 