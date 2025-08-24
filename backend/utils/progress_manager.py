"""
Progress Manager Module
Handles progress tracking and SSE event generation for real-time updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    """Individual progress event"""
    timestamp: datetime
    session_id: str
    agent: str
    step: str
    message: str
    percentage: Optional[int] = None
    status: str = "in_progress"
    metadata: Dict[str, Any] = None
    
    def to_sse_format(self) -> str:
        """Convert to SSE event format"""
        data = {
            "type": "progress",
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "step": self.step,
            "message": self.message,
            "percentage": self.percentage,
            "status": self.status,
            "metadata": self.metadata or {}
        }
        return f"data: {json.dumps(data)}\n\n"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "agent": self.agent,
            "step": self.step,
            "message": self.message,
            "percentage": self.percentage,
            "status": self.status,
            "metadata": self.metadata or {}
        }


class ProgressManager:
    """Manages progress events and SSE streaming"""
    
    def __init__(self):
        """Initialize the Progress Manager"""
        # Store progress events by session
        self.progress_events: Dict[str, List[ProgressEvent]] = defaultdict(list)
        
        # Active SSE connections by session
        self.active_connections: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        
        # Configuration
        self.max_events_per_session = int(os.getenv("MAX_PROGRESS_EVENTS", "100"))
        self.event_ttl = int(os.getenv("PROGRESS_EVENT_TTL", "3600"))  # 1 hour
        
        # Background cleanup task
        self.cleanup_task = None
        
    async def add_progress(self, session_id: str, agent: str, step: str, 
                          message: str, percentage: Optional[int] = None,
                          status: str = "in_progress", metadata: Dict[str, Any] = None):
        """
        Add a progress event for a session
        
        Args:
            session_id: Session identifier
            agent: Name of the agent generating the progress
            step: Current step being performed
            message: User-friendly message
            percentage: Optional progress percentage (0-100)
            status: Status of the step (started, in_progress, completed, failed)
            metadata: Optional additional data
        """
        event = ProgressEvent(
            timestamp=datetime.now(),
            session_id=session_id,
            agent=agent,
            step=step,
            message=message,
            percentage=percentage,
            status=status,
            metadata=metadata
        )
        
        # Store event
        self.progress_events[session_id].append(event)
        
        # Trim events if exceeding limit
        if len(self.progress_events[session_id]) > self.max_events_per_session:
            self.progress_events[session_id] = \
                self.progress_events[session_id][-self.max_events_per_session:]
        
        # Send to active SSE connections
        await self._broadcast_to_session(session_id, event)
        
        logger.info(f"Progress event added for session {session_id}: {agent} - {step}")
        
    async def _broadcast_to_session(self, session_id: str, event: ProgressEvent):
        """Broadcast event to all active connections for a session"""
        connections = self.active_connections.get(session_id, [])
        
        # Remove closed connections
        active = []
        for queue in connections:
            try:
                # Try to put event in queue (non-blocking)
                queue.put_nowait(event)
                active.append(queue)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for session {session_id}, dropping old events")
                # Clear old events and add new one
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                queue.put_nowait(event)
                active.append(queue)
            except Exception as e:
                logger.error(f"Error broadcasting to session {session_id}: {e}")
                # Don't add to active list (connection is dead)
        
        self.active_connections[session_id] = active
    
    async def create_sse_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Create an SSE stream for a session
        
        Yields SSE-formatted progress events
        """
        # Create a queue for this connection
        queue = asyncio.Queue(maxsize=50)
        self.active_connections[session_id].append(queue)
        
        try:
            # Send initial connection event
            yield "data: {\"type\": \"connected\", \"session_id\": \"" + session_id + "\"}\n\n"
            
            # Send any existing events for this session
            existing_events = self.get_recent_progress(session_id, limit=10)
            for event_dict in existing_events:
                event = ProgressEvent(
                    timestamp=datetime.fromisoformat(event_dict["timestamp"]),
                    session_id=session_id,
                    agent=event_dict["agent"],
                    step=event_dict["step"],
                    message=event_dict["message"],
                    percentage=event_dict.get("percentage"),
                    status=event_dict.get("status", "in_progress"),
                    metadata=event_dict.get("metadata")
                )
                yield event.to_sse_format()
            
            # Stream new events as they arrive
            while True:
                try:
                    # Wait for new events with timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE stream for session {session_id}: {e}")
                    break
                    
        finally:
            # Remove this connection from active list
            try:
                self.active_connections[session_id].remove(queue)
            except (ValueError, KeyError):
                pass
    
    def get_recent_progress(self, session_id: str, limit: int = 10,
                           since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get recent progress events for a session
        
        Args:
            session_id: Session identifier
            limit: Maximum number of events to return
            since_timestamp: Only return events after this timestamp
            
        Returns:
            List of progress events as dictionaries
        """
        events = self.progress_events.get(session_id, [])
        
        # Filter by timestamp if provided
        if since_timestamp:
            events = [e for e in events if e.timestamp > since_timestamp]
        
        # Return most recent events up to limit
        return [e.to_dict() for e in events[-limit:]]
    
    def get_session_progress_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of progress for a session
        
        Returns:
            Summary including current step, overall percentage, etc.
        """
        events = self.progress_events.get(session_id, [])
        
        if not events:
            return {
                "session_id": session_id,
                "status": "not_started",
                "current_agent": None,
                "current_step": None,
                "overall_percentage": 0,
                "event_count": 0
            }
        
        latest_event = events[-1]
        
        # Calculate overall percentage based on completed steps
        completed_steps = sum(1 for e in events if e.status == "completed")
        total_steps = len(set((e.agent, e.step) for e in events))
        overall_percentage = int((completed_steps / max(total_steps, 1)) * 100)
        
        return {
            "session_id": session_id,
            "status": latest_event.status,
            "current_agent": latest_event.agent,
            "current_step": latest_event.step,
            "current_message": latest_event.message,
            "overall_percentage": overall_percentage,
            "event_count": len(events),
            "last_update": latest_event.timestamp.isoformat()
        }
    
    async def cleanup_old_sessions(self):
        """Remove old progress events to prevent memory leak"""
        current_time = datetime.now()
        sessions_to_remove = []
        
        for session_id, events in self.progress_events.items():
            if events:
                # Check if session is old
                latest_event = events[-1]
                age_seconds = (current_time - latest_event.timestamp).total_seconds()
                
                if age_seconds > self.event_ttl:
                    sessions_to_remove.append(session_id)
        
        # Remove old sessions
        for session_id in sessions_to_remove:
            del self.progress_events[session_id]
            # Also remove any active connections
            if session_id in self.active_connections:
                del self.active_connections[session_id]
            logger.info(f"Cleaned up old progress events for session {session_id}")
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # Run every 5 minutes
                    await self.cleanup_old_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
    
    def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()


# Global instance
progress_manager = ProgressManager()