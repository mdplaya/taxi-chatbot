"""
Simple Learning System
Basic session-based preference tracking
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    USER_PREFERENCE = "user_preference"
    ERROR_CORRECTION = "error_correction"
    ROUTING_SUCCESS = "routing_success"
    ROUTING_FAILURE = "routing_failure"


@dataclass
class Pattern:
    """Simple pattern for tracking"""
    type: PatternType
    pattern: Dict[str, Any]
    confidence: float
    frequency: int
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SimpleLearningEngine:
    """
    Basic learning engine for session preferences
    Tracks only current session data
    """
    
    def __init__(self):
        # Session-based storage only
        self.session_patterns: Dict[str, List[Pattern]] = {}
        self.session_preferences: Dict[str, Dict[str, Any]] = {}
    
    async def learn(self, pattern: Pattern, session_id: str = None) -> bool:
        """
        Store pattern for current session
        """
        if not session_id:
            return False
        
        # Initialize session if needed
        if session_id not in self.session_patterns:
            self.session_patterns[session_id] = []
            self.session_preferences[session_id] = {}
        
        # Add pattern to session
        self.session_patterns[session_id].append(pattern)
        
        # Update preferences based on pattern type
        if pattern.type == PatternType.USER_PREFERENCE:
            self._update_preferences(session_id, pattern)
        
        # Keep only last 50 patterns per session
        self.session_patterns[session_id] = self.session_patterns[session_id][-50:]
        
        logger.debug(f"Learned pattern for session {session_id}: {pattern.type}")
        return True
    
    def _update_preferences(self, session_id: str, pattern: Pattern):
        """Update session preferences"""
        prefs = self.session_preferences[session_id]
        
        # Extract preference data
        if "preference" in pattern.pattern:
            pref_key = pattern.pattern.get("preference")
            pref_value = pattern.pattern.get("value")
            if pref_key and pref_value:
                prefs[pref_key] = pref_value
    
    async def get_session_preferences(self, session_id: str) -> Dict[str, Any]:
        """Get preferences for current session"""
        return self.session_preferences.get(session_id, {})
    
    async def get_session_patterns(self, session_id: str, pattern_type: PatternType = None) -> List[Pattern]:
        """Get patterns for current session"""
        patterns = self.session_patterns.get(session_id, [])
        
        if pattern_type:
            patterns = [p for p in patterns if p.type == pattern_type]
        
        return patterns
    
    async def track_correction(self, original: str, corrected: str, session_id: str = None):
        """Track a correction made during session"""
        if not session_id:
            return
        
        pattern = Pattern(
            type=PatternType.ERROR_CORRECTION,
            pattern={"original": original, "corrected": corrected},
            confidence=0.8,
            frequency=1
        )
        await self.learn(pattern, session_id)
    
    def clear_session(self, session_id: str):
        """Clear data for a session"""
        if session_id in self.session_patterns:
            del self.session_patterns[session_id]
        if session_id in self.session_preferences:
            del self.session_preferences[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get basic stats"""
        return {
            "active_sessions": len(self.session_patterns),
            "total_patterns": sum(len(p) for p in self.session_patterns.values())
        }