"""
Simple Valkey Manager
Basic session storage operations
"""

from typing import Dict, Any, Optional, List
import json
import logging
from datetime import datetime, timedelta
import redis
import os

logger = logging.getLogger(__name__)


class SimpleValkeyManager:
    """
    Basic Redis/Valkey session management
    Simplified to core key-value operations
    """
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.ttl = int(os.getenv("VALKEY_SESSION_TTL", "3600"))  # 1 hour default
        self._connect()
    
    def _connect(self):
        """Connect to Valkey/Redis"""
        try:
            host = os.getenv("VALKEY_HOST", "localhost")
            port = int(os.getenv("VALKEY_PORT", "6379"))
            db = int(os.getenv("VALKEY_DB", "0"))
            password = os.getenv("VALKEY_PASSWORD")
            
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            
            # Test connection
            self.client.ping()
            self.connected = True
            logger.info(f"Connected to Valkey at {host}:{port}")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Valkey: {e}. Using in-memory fallback.")
            self.connected = False
            self.memory_store = {}  # Fallback to in-memory
    
    async def store_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Store session data"""
        try:
            key = f"session:{session_id}"
            value = json.dumps(data, default=str)
            
            if self.connected:
                self.client.setex(key, self.ttl, value)
            else:
                # In-memory fallback
                self.memory_store[key] = {
                    "data": value,
                    "expires": datetime.now() + timedelta(seconds=self.ttl)
                }
            
            logger.debug(f"Stored session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store session {session_id}: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data"""
        try:
            key = f"session:{session_id}"
            
            if self.connected:
                value = self.client.get(key)
            else:
                # In-memory fallback
                if key in self.memory_store:
                    entry = self.memory_store[key]
                    if entry["expires"] > datetime.now():
                        value = entry["data"]
                    else:
                        del self.memory_store[key]
                        value = None
                else:
                    value = None
            
            if value:
                return json.loads(value)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing session data"""
        try:
            # Get current data
            current = await self.get_session(session_id)
            if not current:
                current = {}
            
            # Merge updates
            current.update(updates)
            
            # Store back
            return await self.store_session(session_id, current)
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session data"""
        try:
            key = f"session:{session_id}"
            
            if self.connected:
                self.client.delete(key)
            else:
                # In-memory fallback
                if key in self.memory_store:
                    del self.memory_store[key]
            
            logger.debug(f"Deleted session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        try:
            key = f"session:{session_id}"
            
            if self.connected:
                return bool(self.client.exists(key))
            else:
                # In-memory fallback
                if key in self.memory_store:
                    if self.memory_store[key]["expires"] > datetime.now():
                        return True
                    else:
                        del self.memory_store[key]
                return False
                
        except Exception as e:
            logger.error(f"Failed to check session {session_id}: {e}")
            return False
    
    async def list_sessions(self, pattern: str = "*") -> List[str]:
        """List session IDs matching pattern"""
        try:
            search_pattern = f"session:{pattern}"
            sessions = []
            
            if self.connected:
                keys = self.client.keys(search_pattern)
                sessions = [k.replace("session:", "") for k in keys]
            else:
                # In-memory fallback
                now = datetime.now()
                for key in list(self.memory_store.keys()):
                    if key.startswith("session:"):
                        if self.memory_store[key]["expires"] > now:
                            sessions.append(key.replace("session:", ""))
                        else:
                            del self.memory_store[key]
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def cleanup_expired(self):
        """Clean up expired sessions (in-memory only)"""
        if not self.connected and hasattr(self, 'memory_store'):
            now = datetime.now()
            expired = [k for k, v in self.memory_store.items() 
                      if v["expires"] <= now]
            for key in expired:
                del self.memory_store[key]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            if self.connected:
                info = self.client.info()
                return {
                    "connected": True,
                    "db_size": self.client.dbsize(),
                    "used_memory": info.get("used_memory_human", "unknown")
                }
            else:
                return {
                    "connected": False,
                    "sessions_in_memory": len([k for k in self.memory_store.keys() 
                                              if k.startswith("session:")])
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Global instance for backward compatibility
_valkey_manager = None

def get_valkey_manager() -> SimpleValkeyManager:
    """Get or create Valkey manager instance"""
    global _valkey_manager
    if _valkey_manager is None:
        _valkey_manager = SimpleValkeyManager()
    return _valkey_manager