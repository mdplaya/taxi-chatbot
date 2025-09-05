"""
Simple Progress Manager
Basic progress tracking without SSE complexity
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Simple progress update"""
    stage: str
    message: str
    percentage: int
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "stage": self.stage,
            "message": self.message,
            "percentage": self.percentage,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {}
        }


class SimpleProgressManager:
    """
    Basic progress tracking
    Simplified without SSE streaming
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.progress_history: Dict[str, List[ProgressUpdate]] = {}
    
    async def start_session(self, session_id: str) -> None:
        """Start tracking progress for a session"""
        
        self.active_sessions[session_id] = {
            "started_at": datetime.now(),
            "last_update": datetime.now(),
            "current_stage": "initialized",
            "percentage": 0
        }
        self.progress_history[session_id] = []
        logger.debug(f"Started progress tracking for session {session_id}")
    
    async def update_progress(
        self,
        session_id: str,
        stage: str,
        message: str,
        percentage: int,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Update progress for a session"""
        if session_id not in self.active_sessions:
            await self.start_session(session_id)
        
        # Create update
        update = ProgressUpdate(
            stage=stage,
            message=message,
            percentage=min(100, max(0, percentage)),  # Clamp to 0-100
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        # Update session
        self.active_sessions[session_id].update({
            "last_update": update.timestamp,
            "current_stage": stage,
            "percentage": update.percentage
        })
        
        # Add to history
        self.progress_history[session_id].append(update)
        
        # Keep only last 100 updates per session
        self.progress_history[session_id] = self.progress_history[session_id][-100:]
        
        logger.debug(f"Progress update for {session_id}: {stage} - {percentage}%")
    
    async def get_session_progress(self, session_id: str) -> Dict[str, Any]:
        """Get current progress for a session"""
        if session_id not in self.active_sessions:
            return {
                "status": "not_found",
                "percentage": 0
            }
        
        session = self.active_sessions[session_id]
        history = self.progress_history.get(session_id, [])
        
        return {
            "status": "active",
            "current_stage": session["current_stage"],
            "percentage": session["percentage"],
            "started_at": session["started_at"].isoformat(),
            "last_update": session["last_update"].isoformat(),
            "recent_updates": [u.to_dict() for u in history[-5:]]  # Last 5 updates
        }
    
    async def complete_session(self, session_id: str) -> None:
        """Mark session as complete"""
        if session_id in self.active_sessions:
            await self.update_progress(
                session_id,
                "completed",
                "Processing complete",
                100
            )
            # Remove from active sessions after a delay
            await asyncio.sleep(5)
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        """Clean up old inactive sessions"""
        now = datetime.now()
        to_remove = []
        
        for session_id, session in self.active_sessions.items():
            age = (now - session["last_update"]).total_seconds()
            if age > max_age_seconds:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self.active_sessions[session_id]
            if session_id in self.progress_history:
                del self.progress_history[session_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "active_sessions": len(self.active_sessions),
            "total_updates": sum(len(h) for h in self.progress_history.values())
        }


# Global instance for backward compatibility
_progress_manager = None

def get_progress_manager() -> SimpleProgressManager:
    """Get or create progress manager instance"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = SimpleProgressManager()
    return _progress_manager