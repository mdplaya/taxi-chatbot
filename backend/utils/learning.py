"""
Advanced Learning Module for TAXI Chatbot
Centralized learning coordinator for pattern recognition and adaptation
All learning is LLM-powered with NO hardcoded rules
"""

import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import os
from openai import OpenAI
from enum import Enum

from utils.valkey_manager import ValkeyManager

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of patterns the system can learn"""
    SEQUENCE = "sequence"  # User action sequences
    PREFERENCE = "preference"  # User preferences
    ERROR = "error"  # Common error patterns
    SUCCESS = "success"  # Success patterns
    OPTIMIZATION = "optimization"  # Performance optimizations


class Pattern(BaseModel):
    """Represents a learned pattern"""
    type: PatternType
    description: str
    occurrences: int = 1
    confidence: float = Field(ge=0.0, le=1.0)
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserPreferences(BaseModel):
    """User preference model"""
    user_id: str
    cloud_provider: Optional[str] = None
    machine_types: List[str] = Field(default_factory=list)
    operating_system: Optional[str] = None
    regions: List[str] = Field(default_factory=list)
    communication_style: Optional[str] = None
    custom_preferences: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)


class AgentMemory(BaseModel):
    """Agent memory snapshot for coordination"""
    agent_name: str
    learned_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    last_reflection: Optional[datetime] = None


class ImprovementSuggestion(BaseModel):
    """Improvement suggestion for agents"""
    suggestion: str
    impact: str  # high, medium, low
    confidence: float = Field(ge=0.0, le=1.0)
    implementation: str
    estimated_benefit: Optional[str] = None


class LearningEngine:
    """
    Centralized learning coordinator for pattern recognition and adaptation.
    All decisions made through LLM reasoning - NO hardcoded patterns.
    """
    
    def __init__(self, valkey_manager: ValkeyManager):
        """Initialize learning engine with Valkey for persistence"""
        self.valkey_manager = valkey_manager
        self.model = os.getenv("OUTCOME_EVALUATION_MODEL", "gpt-5-mini")
        self.temperature = 1.0  # gpt-5-mini only supports 1.0
        
        # Learning configuration
        self.pattern_min_occurrences = int(os.getenv("LEARNING_PATTERN_MIN_OCCURRENCES", "3"))
        self.confidence_threshold = float(os.getenv("LEARNING_CONFIDENCE_THRESHOLD", "0.75"))
        self.pattern_ttl = int(os.getenv("LEARNING_PATTERN_TTL", "604800"))  # 7 days
        self.coordination_enabled = os.getenv("LEARNING_COORDINATION_ENABLED", "true").lower() == "true"
        self.improvement_threshold = float(os.getenv("LEARNING_IMPROVEMENT_THRESHOLD", "0.8"))
        
        # Pattern recognition config
        self.pattern_recognition_enabled = os.getenv("PATTERN_RECOGNITION_ENABLED", "true").lower() == "true"
        self.pattern_min_confidence = float(os.getenv("PATTERN_MIN_CONFIDENCE", "0.6"))
        self.pattern_max_age_days = int(os.getenv("PATTERN_MAX_AGE_DAYS", "30"))
        self.success_pattern_weight = float(os.getenv("SUCCESS_PATTERN_WEIGHT", "1.5"))
        self.error_pattern_weight = float(os.getenv("ERROR_PATTERN_WEIGHT", "2.0"))
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.llm = OpenAI(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.llm = None
        else:
            logger.warning("No OpenAI API key configured for LearningEngine")
            self.llm = None
    
    async def identify_success_patterns(self, 
                                       session_history: List[Dict],
                                       outcome: str) -> List[Pattern]:
        """
        Analyze successful interactions to identify patterns.
        Uses LLM to detect patterns - no hardcoded rules.
        """
        if not self.pattern_recognition_enabled or not self.llm:
            return []
        
        prompt = f"""
        Analyze this session history to identify patterns.
        Session outcome: {outcome}
        Session history: {json.dumps(session_history, default=str)}
        
        Identify patterns in:
        1. User action sequences (what order things happen)
        2. User preferences (repeated choices)
        3. Success indicators (what led to success)
        4. Error patterns (if outcome was error/failure)
        
        Focus on patterns that appear multiple times or show clear preferences.
        
        Return JSON with this structure:
        {{
            "patterns": [
                {{
                    "type": "sequence|preference|error|success",
                    "description": "Clear description of the pattern",
                    "occurrences": number of times observed,
                    "confidence": 0.0-1.0 confidence score,
                    "metadata": {{}} // any additional context
                }}
            ]
        }}
        """
        
        analysis = await self._llm_analyze(prompt)
        
        patterns = []
        for pattern_data in analysis.get("patterns", []):
            # Only include patterns meeting minimum criteria
            if pattern_data.get("occurrences", 0) >= self.pattern_min_occurrences:
                if pattern_data.get("confidence", 0) >= self.pattern_min_confidence:
                    pattern = Pattern(
                        type=PatternType(pattern_data.get("type", "sequence")),
                        description=pattern_data.get("description", ""),
                        occurrences=pattern_data.get("occurrences", 1),
                        confidence=pattern_data.get("confidence", 0.5),
                        metadata=pattern_data.get("metadata", {})
                    )
                    patterns.append(pattern)
        
        # Apply outcome weighting
        if outcome == "success":
            for pattern in patterns:
                if pattern.type == PatternType.SUCCESS:
                    pattern.confidence = min(1.0, pattern.confidence * self.success_pattern_weight)
        elif outcome in ["error", "failure"]:
            for pattern in patterns:
                if pattern.type == PatternType.ERROR:
                    pattern.confidence = min(1.0, pattern.confidence * self.error_pattern_weight)
        
        return patterns
    
    async def learn_user_preferences(self,
                                    user_id: str,
                                    interactions: List[Dict]) -> UserPreferences:
        """
        Infer user preferences from interaction history.
        All inference done through LLM analysis.
        """
        if not self.llm:
            return UserPreferences(user_id=user_id)
        
        prompt = f"""
        Analyze these user interactions to learn preferences.
        User ID: {user_id}
        Interactions: {json.dumps(interactions, default=str)}
        
        Identify preferences for:
        1. Cloud provider (GCP, AWS, Azure)
        2. Machine types frequently requested
        3. Operating systems preferred
        4. Regions/zones commonly used
        5. Communication style (technical, casual, brief, detailed)
        6. Any other patterns in their requests
        
        Return JSON with:
        {{
            "preferences": {{
                "cloud_provider": "provider or null",
                "machine_types": ["list of types"],
                "operating_system": "OS or null",
                "regions": ["list of regions"],
                "communication_style": "style or null",
                "custom": {{}} // any other observed preferences
            }},
            "confidence_scores": {{
                "cloud_provider": 0.0-1.0,
                "machine_types": 0.0-1.0,
                "operating_system": 0.0-1.0,
                "regions": 0.0-1.0,
                "communication_style": 0.0-1.0
            }}
        }}
        """
        
        analysis = await self._llm_analyze(prompt)
        
        prefs = analysis.get("preferences", {})
        scores = analysis.get("confidence_scores", {})
        
        preferences = UserPreferences(
            user_id=user_id,
            cloud_provider=prefs.get("cloud_provider"),
            machine_types=prefs.get("machine_types", []),
            operating_system=prefs.get("operating_system"),
            regions=prefs.get("regions", []),
            communication_style=prefs.get("communication_style"),
            custom_preferences=prefs.get("custom", {}),
            confidence_scores=scores
        )
        
        # Persist high-confidence preferences
        if any(score >= self.confidence_threshold for score in scores.values()):
            await self.save_user_preferences(preferences)
        
        return preferences
    
    async def coordinate_agent_learning(self,
                                       agent_memories: Dict[str, AgentMemory],
                                       session_outcome: str) -> Dict[str, Any]:
        """
        Coordinate learning across multiple agents.
        Identifies shared patterns and resolves conflicts.
        """
        if not self.coordination_enabled or not self.llm:
            return {"coordination_skipped": True}
        
        # Serialize agent memories for analysis
        memories_data = {
            name: {
                "patterns": memory.learned_patterns,
                "corrections": memory.corrections,
                "metrics": memory.performance_metrics
            }
            for name, memory in agent_memories.items()
        }
        
        prompt = f"""
        Coordinate learning across these agents.
        Session outcome: {session_outcome}
        Agent memories: {json.dumps(memories_data, default=str)}
        
        Analyze for:
        1. Shared patterns that multiple agents should know
        2. Conflicting patterns that need resolution
        3. Opportunities for agents to learn from each other
        4. Coordination improvements
        
        Return JSON with:
        {{
            "shared_patterns": [
                {{
                    "pattern": "description",
                    "agents_affected": ["agent names"],
                    "action": "what to do with this pattern",
                    "confidence": 0.0-1.0
                }}
            ],
            "conflicts": [
                {{
                    "description": "conflict description",
                    "agents": ["involved agents"],
                    "resolution": "how to resolve"
                }}
            ],
            "coordination_actions": ["list of coordination improvements"]
        }}
        """
        
        analysis = await self._llm_analyze(prompt)
        
        # Save shared patterns for cross-agent use
        for shared_pattern in analysis.get("shared_patterns", []):
            if shared_pattern.get("confidence", 0) >= self.confidence_threshold:
                pattern_data = {
                    "pattern": shared_pattern["pattern"],
                    "agents": shared_pattern["agents_affected"],
                    "action": shared_pattern["action"]
                }
                
                for agent in shared_pattern["agents_affected"]:
                    await self.valkey_manager.save_learned_pattern(
                        agent_name=agent,
                        pattern_type="shared",
                        pattern_data=pattern_data,
                        confidence=shared_pattern.get("confidence", 0.5)
                    )
        
        return analysis
    
    async def suggest_improvements(self,
                                  agent_name: str,
                                  recent_performance: List[Dict]) -> List[ImprovementSuggestion]:
        """
        Generate improvement suggestions for specific agents.
        All suggestions generated through LLM analysis.
        """
        if not self.llm:
            return []
        
        prompt = f"""
        Analyze performance and suggest improvements for {agent_name} agent.
        Recent performance: {json.dumps(recent_performance, default=str)}
        
        Consider:
        1. Error patterns and how to avoid them
        2. Performance bottlenecks
        3. Accuracy improvements
        4. Process optimizations
        5. Better error handling
        
        Generate 3-5 specific, actionable improvements.
        
        Return JSON with:
        {{
            "improvements": [
                {{
                    "suggestion": "specific suggestion",
                    "impact": "high|medium|low",
                    "confidence": 0.0-1.0,
                    "implementation": "how to implement",
                    "estimated_benefit": "expected improvement"
                }}
            ]
        }}
        """
        
        analysis = await self._llm_analyze(prompt)
        
        suggestions = []
        for imp in analysis.get("improvements", []):
            if imp.get("confidence", 0) >= self.improvement_threshold:
                suggestion = ImprovementSuggestion(
                    suggestion=imp.get("suggestion", ""),
                    impact=imp.get("impact", "medium"),
                    confidence=imp.get("confidence", 0.5),
                    implementation=imp.get("implementation", ""),
                    estimated_benefit=imp.get("estimated_benefit")
                )
                suggestions.append(suggestion)
        
        return suggestions
    
    async def calculate_pattern_confidence(self,
                                          pattern: Pattern,
                                          historical_outcomes: List[str]) -> float:
        """
        Calculate confidence score for learned patterns.
        Considers historical success rate and time decay.
        """
        if not historical_outcomes:
            return pattern.confidence
        
        # Calculate success rate
        success_count = sum(1 for outcome in historical_outcomes if outcome == "success")
        success_rate = success_count / len(historical_outcomes)
        
        # Calculate time decay factor
        days_old = (datetime.now() - pattern.last_seen).days
        time_decay = max(0.5, 1.0 - (days_old / self.pattern_max_age_days))
        
        # Weight factors: success rate (40%), original confidence (40%), time decay (20%)
        new_confidence = (
            success_rate * 0.4 +
            pattern.confidence * 0.4 +
            time_decay * 0.2
        )
        
        # Apply pattern type weighting
        if pattern.type == PatternType.SUCCESS:
            new_confidence *= self.success_pattern_weight
        elif pattern.type == PatternType.ERROR:
            new_confidence *= self.error_pattern_weight
        
        return min(1.0, max(0.0, new_confidence))
    
    async def prune_patterns(self, patterns: List[Pattern]) -> List[Pattern]:
        """
        Remove old or low-confidence patterns for memory optimization.
        """
        pruned = []
        cutoff_date = datetime.now() - timedelta(days=self.pattern_max_age_days)
        
        for pattern in patterns:
            # Keep if: recent AND high confidence AND sufficient occurrences
            if (pattern.last_seen > cutoff_date and
                pattern.confidence >= self.pattern_min_confidence and
                pattern.occurrences >= self.pattern_min_occurrences):
                pruned.append(pattern)
        
        # Sort by confidence and keep top 100
        pruned.sort(key=lambda p: p.confidence, reverse=True)
        return pruned[:100]
    
    async def save_cross_session_pattern(self, user_id: str, pattern: Pattern) -> bool:
        """
        Save pattern for cross-session learning.
        """
        if pattern.confidence < self.confidence_threshold:
            return False
        
        pattern_data = {
            "description": pattern.description,
            "type": pattern.type.value,
            "occurrences": pattern.occurrences,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        return await self.valkey_manager.save_learned_pattern(
            agent_name=f"user_{user_id}",
            pattern_type=pattern.type.value,
            pattern_data=pattern_data,
            confidence=pattern.confidence
        )
    
    async def save_user_preferences(self, preferences: UserPreferences) -> bool:
        """
        Persist user preferences to Valkey.
        """
        pref_data = preferences.dict()
        
        return await self.valkey_manager.save_agent_memory(
            agent_name=f"user_{preferences.user_id}",
            session_id="preferences",
            memory_type="preferences",
            data=pref_data,
            ttl=self.pattern_ttl
        )
    
    async def filter_active_patterns(self, patterns: List[Pattern]) -> List[Pattern]:
        """
        Filter patterns to only include active ones based on TTL.
        """
        cutoff_date = datetime.now() - timedelta(days=self.pattern_max_age_days)
        return [p for p in patterns if p.last_seen > cutoff_date]
    
    async def enforce_memory_limits(self, patterns: List[Pattern], limit: int = 100) -> List[Pattern]:
        """
        Enforce memory limits by keeping only top patterns.
        """
        # Sort by confidence descending
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns[:limit]
    
    async def _llm_analyze(self, prompt: str) -> Dict[str, Any]:
        """
        Core LLM analysis - all learning decisions go through here.
        NO hardcoded logic allowed.
        """
        if not self.llm:
            logger.warning("No LLM available for learning analysis")
            return {}
        
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a learning system that identifies patterns and preferences. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {}
                
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return {}