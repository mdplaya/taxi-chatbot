"""
Agent Session Model for Conversational State Management
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class ConversationState(str, Enum):
    """Conversation state enum"""
    INITIAL = "initial"
    GATHERING_INFO = "gathering_info"
    CONFIRMING = "confirming"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Message(BaseModel):
    """Single message in conversation"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}

class AgentMemorySnapshot(BaseModel):
    """Snapshot of agent memory at a point in time"""
    agent_name: str
    short_term: Dict[str, Any] = {}
    long_term: Dict[str, Any] = {}
    corrections: List[Dict[str, Any]] = []
    learned_patterns: Dict[str, List[Dict[str, Any]]] = {}
    confidence_scores: Dict[str, float] = {}
    timestamp: datetime = Field(default_factory=datetime.now)

class AgentSession(BaseModel):
    """Enhanced session model with agent memory tracking"""
    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Conversation state
    state: ConversationState = ConversationState.INITIAL
    conversation_history: List[Message] = []
    
    # Current context
    current_intent: Optional[str] = None
    current_agent: Optional[str] = None
    current_vm_request: Optional[Dict[str, Any]] = None
    
    # Agent memories
    agent_memories: Dict[str, AgentMemorySnapshot] = {}
    
    # User preferences learned
    user_preferences: Dict[str, Any] = {}
    
    # Corrections made
    corrections_history: List[Dict[str, Any]] = []
    
    # Final outputs
    final_payload: Optional[Dict[str, Any]] = None
    provision_result: Optional[Dict[str, Any]] = None
    
    # Metadata
    metadata: Dict[str, Any] = {}
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add message to conversation history"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.conversation_history.append(message)
        self.updated_at = datetime.now()
    
    def save_agent_memory(self, agent_name: str, memory_snapshot: AgentMemorySnapshot):
        """Save agent memory snapshot"""
        self.agent_memories[agent_name] = memory_snapshot
        self.updated_at = datetime.now()
    
    def add_correction(self, field: str, old_value: Any, new_value: Any, corrected_by: str):
        """Track correction made"""
        correction = {
            'field': field,
            'old_value': old_value,
            'new_value': new_value,
            'corrected_by': corrected_by,
            'timestamp': datetime.now().isoformat()
        }
        self.corrections_history.append(correction)
        self.updated_at = datetime.now()
    
    def update_state(self, new_state: ConversationState):
        """Update conversation state"""
        self.state = new_state
        self.updated_at = datetime.now()
    
    def get_recent_context(self, message_count: int = 5) -> List[Message]:
        """Get recent conversation context"""
        return self.conversation_history[-message_count:] if self.conversation_history else []
    
    def to_valkey_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Valkey storage"""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'state': self.state,
            'conversation_history': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'metadata': msg.metadata
                }
                for msg in self.conversation_history
            ],
            'current_intent': self.current_intent,
            'current_agent': self.current_agent,
            'current_vm_request': self.current_vm_request,
            'agent_memories': {
                name: {
                    'agent_name': mem.agent_name,
                    'short_term': mem.short_term,
                    'long_term': mem.long_term,
                    'corrections': mem.corrections,
                    'learned_patterns': mem.learned_patterns,
                    'confidence_scores': mem.confidence_scores,
                    'timestamp': mem.timestamp.isoformat()
                }
                for name, mem in self.agent_memories.items()
            },
            'user_preferences': self.user_preferences,
            'corrections_history': self.corrections_history,
            'final_payload': self.final_payload,
            'provision_result': self.provision_result,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_valkey_dict(cls, data: Dict[str, Any]) -> 'AgentSession':
        """Create instance from Valkey stored dictionary"""
        session = cls(
            session_id=data['session_id'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            state=data['state'],
            current_intent=data.get('current_intent'),
            current_agent=data.get('current_agent'),
            current_vm_request=data.get('current_vm_request'),
            user_preferences=data.get('user_preferences', {}),
            corrections_history=data.get('corrections_history', []),
            final_payload=data.get('final_payload'),
            provision_result=data.get('provision_result'),
            metadata=data.get('metadata', {})
        )
        
        # Reconstruct conversation history
        for msg_data in data.get('conversation_history', []):
            message = Message(
                role=msg_data['role'],
                content=msg_data['content'],
                timestamp=datetime.fromisoformat(msg_data['timestamp']),
                metadata=msg_data.get('metadata', {})
            )
            session.conversation_history.append(message)
        
        # Reconstruct agent memories
        for name, mem_data in data.get('agent_memories', {}).items():
            memory = AgentMemorySnapshot(
                agent_name=mem_data['agent_name'],
                short_term=mem_data['short_term'],
                long_term=mem_data['long_term'],
                corrections=mem_data['corrections'],
                learned_patterns=mem_data['learned_patterns'],
                confidence_scores=mem_data['confidence_scores'],
                timestamp=datetime.fromisoformat(mem_data['timestamp'])
            )
            session.agent_memories[name] = memory
        
        return session