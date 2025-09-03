"""
Error Correction System
LLM-based error detection and correction - NO hardcoded rules
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from openai import OpenAI
import os
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CorrectionPattern:
    pattern_id: str
    original_type: str
    correction_type: str
    context: str
    examples: List[Dict[str, Any]]
    confidence: float
    success_rate: float
    timestamp: datetime


@dataclass
class CorrectionResult:
    original: Any
    corrected: Any
    confidence: float
    reasoning: str
    pattern_applied: Optional[str]
    requires_confirmation: bool


class ErrorCorrectionSystem:
    """
    Intelligent error correction using LLM reasoning
    Learns from corrections and improves over time
    NO pattern matching or hardcoded rules
    """
    
    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
        self.learned_patterns: Dict[str, CorrectionPattern] = {}
        self.correction_history: List[Dict[str, Any]] = []
        self.confidence_threshold = float(os.getenv("CORRECTION_LEARNING_THRESHOLD", "0.8"))
        
        # Initialize LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = OpenAI(api_key=api_key)
        else:
            logger.warning("No OpenAI API key - error correction will have limited capabilities")
            self.llm = None
    
    async def detect_and_correct(self, input_data: Any, context: Dict[str, Any]) -> CorrectionResult:
        """
        Detect potential errors and correct them using LLM reasoning
        """
        # First, check if we've seen similar inputs before
        similar_corrections = await self._find_similar_corrections(input_data, context)
        
        # Check if this is a VM request that should skip correction
        is_vm_request = context.get("agent") == "orchestrator" and \
                       isinstance(input_data, str) and \
                       any(kw in str(input_data).lower() for kw in ['vm', 'server', 'instance', 'compute'])
        
        detection_prompt = f"""
        Analyze this input for potential errors or improvements:
        
        Input: {json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)}
        Context: {json.dumps(context)}
        
        Previous similar corrections:
        {json.dumps(similar_corrections[:3]) if similar_corrections else "None"}
        
        Learned patterns that might apply:
        {self._get_relevant_patterns(input_data, context)}
        
        {"For VM/compute requests, apply these specific corrections:" if is_vm_request else ""}
        {"- 'red hat 8' or 'rhel 8' → 'RHEL8'" if is_vm_request else ""}
        {"- 'windows 2022' or 'win22' → 'Windows Server 2022'" if is_vm_request else ""}
        {"- Region without zone (e.g., 'us-east4') → Keep as-is, specialist will clarify" if is_vm_request else ""}
        {"- DO NOT expand simple VM requests with unnecessary fields" if is_vm_request else ""}
        
        Detect:
        1. Potential typos or misspellings
        2. Ambiguous references
        3. Missing information (but don't over-expand for VM requests)
        4. Inconsistencies
        5. Common variations that need normalization
        
        Respond in JSON:
        {{
            "has_errors": true/false,
            "error_types": [],
            "suggested_correction": "corrected version or null",
            "reasoning": "explanation",
            "confidence": 0.0-1.0,
            "requires_user_confirmation": true/false,
            "is_simple_request": {str(is_vm_request).lower()}
        }}
        """
        
        detection = await self._llm_reason(detection_prompt)
        
        if not detection.get("has_errors", False):
            return CorrectionResult(
                original=input_data,
                corrected=input_data,
                confidence=1.0,
                reasoning="No errors detected",
                pattern_applied=None,
                requires_confirmation=False
            )
        
        # Apply correction
        correction = await self._apply_correction(
            input_data,
            detection.get("suggested_correction"),
            detection.get("reasoning", ""),
            context
        )
        
        # Store for learning
        self._store_correction(input_data, correction, context)
        
        return correction
    
    async def _apply_correction(self, original: Any, suggested: Any, reasoning: str, context: Dict[str, Any]) -> CorrectionResult:
        """
        Apply correction with confidence scoring
        """
        correction_prompt = f"""
        Apply this correction intelligently:
        
        Original: {json.dumps(original) if isinstance(original, dict) else str(original)}
        Suggested: {json.dumps(suggested) if isinstance(suggested, dict) else str(suggested)}
        Reasoning: {reasoning}
        Context: {json.dumps(context)}
        
        Consider:
        1. Is the correction appropriate for the context?
        2. Does it preserve user intent?
        3. Are there multiple valid interpretations?
        4. Should the user confirm this correction?
        
        Respond in JSON:
        {{
            "final_correction": "the corrected version",
            "confidence": 0.0-1.0,
            "reasoning": "detailed explanation",
            "alternatives": [],
            "requires_confirmation": true/false,
            "correction_type": "typo|ambiguity|normalization|completion|other"
        }}
        """
        
        result = await self._llm_reason(correction_prompt)
        
        # Check if we should apply a learned pattern
        pattern_id = await self._match_pattern(original, result.get("correction_type", ""))
        
        return CorrectionResult(
            original=original,
            corrected=result.get("final_correction", suggested),
            confidence=result.get("confidence", 0.5),
            reasoning=result.get("reasoning", reasoning),
            pattern_applied=pattern_id,
            requires_confirmation=result.get("requires_confirmation", True)
        )
    
    async def learn_from_feedback(self, original: Any, correction: Any, was_accepted: bool, user_feedback: Optional[str] = None):
        """
        Learn from user feedback on corrections
        """
        learning_prompt = f"""
        Learn from this correction feedback:
        
        Original: {json.dumps(original) if isinstance(original, dict) else str(original)}
        Suggested correction: {json.dumps(correction) if isinstance(correction, dict) else str(correction)}
        Was accepted: {was_accepted}
        User feedback: {user_feedback or "None"}
        
        Extract learning:
        1. What pattern can be identified?
        2. When should this correction be applied?
        3. When should it NOT be applied?
        4. What context clues are important?
        
        Respond in JSON:
        {{
            "pattern_description": "description",
            "should_apply_when": [],
            "should_not_apply_when": [],
            "context_indicators": [],
            "confidence_adjustment": -0.2 to 0.2,
            "pattern_type": "typo|ambiguity|normalization|completion|other"
        }}
        """
        
        learning = await self._llm_reason(learning_prompt)
        
        if was_accepted and learning:
            # Create or update pattern
            pattern_id = self._generate_pattern_id(original, correction)
            
            if pattern_id in self.learned_patterns:
                # Update existing pattern
                pattern = self.learned_patterns[pattern_id]
                pattern.success_rate = (pattern.success_rate * len(pattern.examples) + 1.0) / (len(pattern.examples) + 1)
                pattern.examples.append({
                    "original": original,
                    "correction": correction,
                    "feedback": user_feedback
                })
                pattern.confidence = min(1.0, pattern.confidence + learning.get("confidence_adjustment", 0))
            else:
                # Create new pattern
                self.learned_patterns[pattern_id] = CorrectionPattern(
                    pattern_id=pattern_id,
                    original_type=str(type(original).__name__),
                    correction_type=learning.get("pattern_type", "other"),
                    context=learning.get("pattern_description", ""),
                    examples=[{
                        "original": original,
                        "correction": correction,
                        "feedback": user_feedback
                    }],
                    confidence=0.5 + learning.get("confidence_adjustment", 0),
                    success_rate=1.0 if was_accepted else 0.0,
                    timestamp=datetime.now()
                )
    
    async def validate_correction(self, original: Any, corrected: Any, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a correction before applying
        """
        validation_prompt = f"""
        Validate this correction:
        
        Original: {json.dumps(original) if isinstance(original, dict) else str(original)}
        Corrected: {json.dumps(corrected) if isinstance(corrected, dict) else str(corrected)}
        Context: {json.dumps(context)}
        
        Check:
        1. Does the correction maintain user intent?
        2. Is it contextually appropriate?
        3. Are there any risks or side effects?
        4. Is the correction an improvement?
        
        Respond in JSON:
        {{
            "is_valid": true/false,
            "validation_result": "explanation",
            "risks": [],
            "confidence": 0.0-1.0
        }}
        """
        
        validation = await self._llm_reason(validation_prompt)
        
        is_valid = validation.get("is_valid", False) and validation.get("confidence", 0) >= self.confidence_threshold
        reason = validation.get("validation_result", "Validation failed")
        
        if validation.get("risks"):
            reason += f" Risks: {', '.join(validation['risks'])}"
        
        return is_valid, reason
    
    async def _find_similar_corrections(self, input_data: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find similar corrections from history using LLM
        """
        if not self.correction_history:
            return []
        
        similarity_prompt = f"""
        Find similar corrections from history:
        
        Current input: {json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)}
        Current context: {json.dumps(context)}
        
        History (last 10):
        {json.dumps(self.correction_history[-10:], default=str)}
        
        Identify which historical corrections are similar and relevant.
        
        Respond in JSON:
        {{
            "similar_indices": [list of indices],
            "relevance_scores": [0.0-1.0 for each]
        }}
        """
        
        result = await self._llm_reason(similarity_prompt)
        
        similar = []
        for idx in result.get("similar_indices", []):
            if 0 <= idx < len(self.correction_history):
                similar.append(self.correction_history[idx])
        
        return similar
    
    def _get_relevant_patterns(self, input_data: Any, context: Dict[str, Any]) -> str:
        """
        Get relevant learned patterns for context
        """
        if not self.learned_patterns:
            return "No learned patterns yet"
        
        # Get high-confidence patterns
        relevant = [
            {
                "type": p.correction_type,
                "description": p.context,
                "confidence": p.confidence,
                "success_rate": p.success_rate,
                "examples": len(p.examples)
            }
            for p in self.learned_patterns.values()
            if p.confidence >= 0.6
        ]
        
        return json.dumps(relevant[:5], default=str)
    
    async def _match_pattern(self, input_data: Any, correction_type: str) -> Optional[str]:
        """
        Match input to learned patterns using LLM
        """
        if not self.learned_patterns:
            return None
        
        matching_prompt = f"""
        Match this input to learned patterns:
        
        Input: {json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)}
        Correction type: {correction_type}
        
        Available patterns:
        {json.dumps([
            {
                "id": p.pattern_id,
                "type": p.correction_type,
                "context": p.context,
                "confidence": p.confidence
            }
            for p in self.learned_patterns.values()
        ], default=str)}
        
        Respond in JSON:
        {{
            "best_match_id": "pattern_id or null",
            "match_confidence": 0.0-1.0
        }}
        """
        
        result = await self._llm_reason(matching_prompt)
        
        if result.get("match_confidence", 0) >= 0.7:
            return result.get("best_match_id")
        
        return None
    
    def _store_correction(self, original: Any, correction: CorrectionResult, context: Dict[str, Any]):
        """
        Store correction in history for learning
        """
        self.correction_history.append({
            "timestamp": datetime.now().isoformat(),
            "original": original,
            "corrected": correction.corrected,
            "confidence": correction.confidence,
            "reasoning": correction.reasoning,
            "pattern": correction.pattern_applied,
            "context": context
        })
        
        # Keep history manageable
        if len(self.correction_history) > 1000:
            self.correction_history = self.correction_history[-500:]
    
    def _generate_pattern_id(self, original: Any, correction: Any) -> str:
        """
        Generate unique ID for correction pattern
        """
        content = f"{type(original).__name__}_{type(correction).__name__}_{str(original)[:50]}_{str(correction)[:50]}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _llm_reason(self, prompt: str) -> Dict[str, Any]:
        """
        Core LLM reasoning for error correction
        """
        if not self.llm:
            logger.warning("No LLM available for error correction")
            return {}
        
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an intelligent error correction system. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 1.0,
                "response_format": {"type": "json_object"}
            }
            logger.info(f"[OpenAI Request] {json.dumps(payload, default=str)[:4000]}")
            response = self.llm.chat.completions.create(**payload)
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error correction LLM call failed: {e}")
            return {}
    
    async def apply_vm_corrections(self, input_text: str) -> Dict[str, Any]:
        """
        Apply specific corrections for VM requests
        Focused on common VM-related typos and variations
        """
        vm_correction_prompt = f"""
        Apply VM-specific corrections to this request:
        {input_text}
        
        Apply ONLY these specific corrections:
        1. OS corrections:
           - "red hat 8", "rhel 8", "redhat8" → "RHEL8"
           - "red hat 9", "rhel 9", "redhat9" → "RHEL9"
           - "windows 2019", "win19", "windows server 2019" → "Windows Server 2019"
           - "windows 2022", "win22", "windows server 2022" → "Windows Server 2022"
        
        2. Machine type corrections:
           - "n1" alone → "n1-standard-1"
           - "cheap", "cost-effective" → suggest "e2-micro" or "e2-small"
           - "high memory" → suggest "n2-highmem" types
        
        3. Provider corrections:
           - "google", "gcp" → "Google Cloud Platform"
           - "aws", "amazon" → "Amazon Web Services"
           - "azure", "microsoft" → "Microsoft Azure"
        
        DO NOT:
        - Add fields not mentioned (no firewall, SSH, service accounts)
        - Expand simple requests unnecessarily
        - Change the intent of the request
        
        Return JSON:
        {{
            "corrected_text": "corrected version",
            "corrections_made": ["list of specific corrections"],
            "confidence": 0.0-1.0
        }}
        """
        
        result = await self._llm_reason(vm_correction_prompt)
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get correction system statistics
        """
        return {
            "total_corrections": len(self.correction_history),
            "learned_patterns": len(self.learned_patterns),
            "high_confidence_patterns": sum(1 for p in self.learned_patterns.values() if p.confidence >= 0.8),
            "average_success_rate": sum(p.success_rate for p in self.learned_patterns.values()) / len(self.learned_patterns) if self.learned_patterns else 0
        }
    
    def export_patterns(self) -> List[Dict[str, Any]]:
        """
        Export learned patterns for persistence
        """
        return [
            {
                "id": p.pattern_id,
                "type": p.correction_type,
                "context": p.context,
                "examples": p.examples,
                "confidence": p.confidence,
                "success_rate": p.success_rate,
                "timestamp": p.timestamp.isoformat()
            }
            for p in self.learned_patterns.values()
        ]
    
    def import_patterns(self, patterns: List[Dict[str, Any]]):
        """
        Import learned patterns from storage
        """
        for p in patterns:
            self.learned_patterns[p["id"]] = CorrectionPattern(
                pattern_id=p["id"],
                original_type=p.get("original_type", "unknown"),
                correction_type=p["type"],
                context=p["context"],
                examples=p["examples"],
                confidence=p["confidence"],
                success_rate=p["success_rate"],
                timestamp=datetime.fromisoformat(p["timestamp"])
            )
