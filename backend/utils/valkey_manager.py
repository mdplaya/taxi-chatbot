"""
Valkey Manager for Agent Memory Persistence
Handles all Valkey operations for the agentic system
"""

import json
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import valkey
from valkey.asyncio import Valkey as AsyncValkey
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class ValkeyManager:
    """
    Manages Valkey connections and operations for agent memory persistence
    """
    
    def __init__(self):
        self.host = os.getenv('VALKEY_HOST', 'localhost')
        self.port = int(os.getenv('VALKEY_PORT', 6379))
        self.db = int(os.getenv('VALKEY_AGENT_DB', 1))
        # Treat empty string as None for password
        password_env = os.getenv('VALKEY_PASSWORD')
        self.password = password_env if password_env and password_env.strip() else None
        self.pool_size = int(os.getenv('VALKEY_CONNECTION_POOL_SIZE', 10))
        
        # TTL configurations
        self.agent_memory_ttl = int(os.getenv('AGENT_MEMORY_TTL', 86400))
        self.short_term_ttl = int(os.getenv('SHORT_TERM_MEMORY_TTL', 3600))
        self.long_term_ttl = int(os.getenv('LONG_TERM_MEMORY_TTL', 604800))
        self.correction_ttl = int(os.getenv('CORRECTION_MEMORY_TTL', 2592000))
        
        # Initialize connection pools
        self._init_connection_pools()
    
    def _init_connection_pools(self):
        """Initialize sync and async connection pools"""
        # Build connection kwargs
        async_conn_kwargs = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'max_connections': self.pool_size,
            'decode_responses': True
        }
        
        sync_conn_kwargs = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'max_connections': self.pool_size,
            'decode_responses': True
        }
        
        # Only add password if it's actually set (now None if empty)
        if self.password:
            async_conn_kwargs['password'] = self.password
            sync_conn_kwargs['password'] = self.password
        
        # Async pool for agent operations
        self.async_pool = valkey.asyncio.ConnectionPool(**async_conn_kwargs)
        
        # Sync pool for initialization and cleanup
        self.sync_pool = valkey.ConnectionPool(**sync_conn_kwargs)
    
    async def get_async_client(self) -> AsyncValkey:
        """Get async Valkey client from pool"""
        return AsyncValkey(connection_pool=self.async_pool)
    
    def get_sync_client(self) -> valkey.Valkey:
        """Get sync Valkey client from pool"""
        return valkey.Valkey(connection_pool=self.sync_pool)
    
    # Agent Memory Operations
    async def save_agent_memory(
        self, 
        agent_name: str, 
        session_id: str, 
        memory_type: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Save agent memory to Valkey"""
        try:
            client = await self.get_async_client()
            key = f"agents:{agent_name}:session:{session_id}:{memory_type}"
            
            # Serialize data
            serialized = json.dumps(data, default=str)
            
            # Set with TTL
            ttl = ttl or self.agent_memory_ttl
            await client.setex(key, ttl, serialized)
            
            # Add to session index
            index_key = f"sessions:{session_id}:agents"
            await client.sadd(index_key, agent_name)
            await client.expire(index_key, ttl)
            
            logger.info(f"Saved {memory_type} memory for {agent_name}:{session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving agent memory: {e}")
            return False
        finally:
            await client.aclose()
    
    async def load_agent_memory(
        self,
        agent_name: str,
        session_id: str,
        memory_type: str
    ) -> Optional[Dict[str, Any]]:
        """Load agent memory from Valkey"""
        try:
            client = await self.get_async_client()
            key = f"agents:{agent_name}:session:{session_id}:{memory_type}"
            
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Error loading agent memory: {e}")
            return None
        finally:
            await client.aclose()
    
    # Cross-Session Learning
    async def save_learned_pattern(
        self,
        agent_name: str,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        confidence: float
    ) -> bool:
        """Save learned pattern for cross-session use"""
        try:
            client = await self.get_async_client()
            
            # Only save high-confidence patterns
            threshold = float(os.getenv('PATTERN_CONFIDENCE_THRESHOLD', 0.7))
            if confidence < threshold:
                return False
            
            key = f"agents:{agent_name}:patterns:{pattern_type}"
            pattern_id = f"{datetime.now().isoformat()}_{confidence}"
            
            # Store as sorted set with confidence as score
            await client.zadd(
                key,
                {json.dumps(pattern_data): confidence}
            )
            
            # Keep only top 100 patterns
            await client.zremrangebyrank(key, 0, -101)
            
            # Set TTL
            await client.expire(key, self.correction_ttl)
            
            logger.info(f"Saved learned pattern for {agent_name}:{pattern_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving learned pattern: {e}")
            return False
        finally:
            await client.aclose()
    
    async def get_learned_patterns(
        self,
        agent_name: str,
        pattern_type: str,
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Get learned patterns above confidence threshold"""
        try:
            client = await self.get_async_client()
            key = f"agents:{agent_name}:patterns:{pattern_type}"
            
            # Get patterns with score >= min_confidence
            patterns = await client.zrangebyscore(
                key,
                min_confidence,
                1.0,
                withscores=True
            )
            
            result = []
            for pattern_json, confidence in patterns:
                pattern_data = json.loads(pattern_json)
                pattern_data['confidence'] = confidence
                result.append(pattern_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting learned patterns: {e}")
            return []
        finally:
            await client.aclose()
    
    # Session Management
    async def save_session(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Save session data"""
        try:
            client = await self.get_async_client()
            key = f"sessions:{session_id}:data"
            
            serialized = json.dumps(session_data, default=str)
            ttl = ttl or self.agent_memory_ttl
            
            await client.setex(key, ttl, serialized)
            
            # Add to active sessions set
            await client.sadd("active_sessions", session_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False
        finally:
            await client.aclose()
    
    async def load_session(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load session data"""
        try:
            client = await self.get_async_client()
            key = f"sessions:{session_id}:data"
            
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None
        finally:
            await client.aclose()
    
    # Conversation History
    async def append_conversation(
        self,
        session_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """Append message to conversation history"""
        try:
            client = await self.get_async_client()
            key = f"sessions:{session_id}:conversation"
            
            # Add to list
            await client.rpush(key, json.dumps(message, default=str))
            
            # Trim to last 100 messages
            await client.ltrim(key, -100, -1)
            
            # Set TTL
            await client.expire(key, self.agent_memory_ttl)
            
            return True
            
        except Exception as e:
            logger.error(f"Error appending conversation: {e}")
            return False
        finally:
            await client.aclose()
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        try:
            client = await self.get_async_client()
            key = f"sessions:{session_id}:conversation"
            
            # Get last N messages
            messages = await client.lrange(key, -limit, -1)
            
            return [json.loads(msg) for msg in messages]
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
        finally:
            await client.aclose()
    
    # Health Check
    async def health_check(self) -> bool:
        """Check Valkey connection health"""
        try:
            client = await self.get_async_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error(f"Valkey health check failed: {e}")
            return False
        finally:
            await client.aclose()
    
    # Cleanup
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            client = await self.get_async_client()
            
            # Get all active sessions
            sessions = await client.smembers("active_sessions")
            
            expired_count = 0
            for session_id in sessions:
                # Check if session data exists
                key = f"sessions:{session_id}:data"
                if not await client.exists(key):
                    await client.srem("active_sessions", session_id)
                    expired_count += 1
            
            logger.info(f"Cleaned up {expired_count} expired sessions")
            return expired_count
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0
        finally:
            await client.aclose()

# Singleton instance
valkey_manager = ValkeyManager()