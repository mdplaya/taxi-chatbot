#!/usr/bin/env python3
"""
Phase 4 Learning System Demo - WITH OPENAI API
Demonstrates ACTUAL LLM-powered learning and adaptation capabilities
This requires an OpenAI API key to be set in the environment
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.learning import LearningEngine, Pattern, PatternType, UserPreferences
from utils.valkey_manager import ValkeyManager
from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from unittest.mock import AsyncMock

# Load environment variables
load_dotenv()


def check_api_key():
    """Check if OpenAI API key is available"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("\n" + "⚠️ "*20)
        print("WARNING: OpenAI API Key not configured!")
        print("⚠️ "*20)
        print("\nTo run this demo with actual LLM capabilities:")
        print("1. Get an OpenAI API key from https://platform.openai.com")
        print("2. Set it in backend/.env file:")
        print("   OPENAI_API_KEY=sk-your-actual-key-here")
        print("\nWithout an API key, the demo will show the structure")
        print("but won't demonstrate actual AI-powered learning.\n")
        return False
    return True


async def demo_pattern_recognition_with_llm():
    """Demonstrate ACTUAL pattern recognition using LLM"""
    print("\n" + "="*60)
    print("DEMO: Pattern Recognition with LLM")
    print("="*60)
    
    # Initialize learning engine with mock Valkey for demo
    mock_valkey = AsyncMock(spec=ValkeyManager)
    mock_valkey.save_learned_pattern = AsyncMock(return_value=True)
    mock_valkey.get_learned_patterns = AsyncMock(return_value=[])
    
    engine = LearningEngine(mock_valkey)
    
    # Real session history to analyze
    session_history = [
        {"agent": "orchestrator", "action": "route", "target": "compute", "user_input": "I need a VM in production", "confidence": 0.9},
        {"agent": "compute", "action": "extract", "fields": ["environment", "machine_type"], "extracted": {"environment": "prod"}, "confidence": 0.85},
        {"agent": "clarification", "action": "ask", "question": "Which zone would you prefer?", "user_response": "us-east4-a", "confidence": 0.8},
        {"agent": "gce_specialist", "action": "provision", "result": "success", "vm_type": "n1-standard-4", "confidence": 0.95},
        {"agent": "orchestrator", "action": "route", "target": "compute", "user_input": "Another production VM please", "confidence": 0.92},
        {"agent": "compute", "action": "extract", "fields": ["environment"], "extracted": {"environment": "prod"}, "confidence": 0.88},
        {"agent": "gce_specialist", "action": "provision", "result": "success", "confidence": 0.96}
    ]
    
    print("\nSession History for Analysis:")
    for i, step in enumerate(session_history, 1):
        print(f"  {i}. {step['agent']}: {step['action']} (confidence: {step['confidence']})")
    
    if engine.llm:
        print("\n🤖 Sending to LLM for pattern analysis...")
        print(f"   Model: {engine.model}")
        print(f"   Temperature: {engine.temperature}")
        
        # Get actual patterns from LLM
        patterns = await engine.identify_success_patterns(session_history, "success")
        
        if patterns:
            print("\n✨ Patterns Identified by AI:")
            for pattern in patterns:
                print(f"\n  Pattern Type: {pattern.type.value.upper()}")
                print(f"  Description: {pattern.description}")
                print(f"  Confidence: {pattern.confidence:.2%}")
                print(f"  Occurrences: {pattern.occurrences}")
                if pattern.metadata:
                    print(f"  Metadata: {json.dumps(pattern.metadata, indent=4)}")
        else:
            print("\n  No patterns identified (may need more occurrences)")
    else:
        print("\n❌ LLM not available - cannot demonstrate actual pattern recognition")


async def demo_user_preference_learning_with_llm():
    """Demonstrate ACTUAL user preference learning using LLM"""
    print("\n" + "="*60)
    print("DEMO: User Preference Learning with LLM")
    print("="*60)
    
    # Initialize learning engine
    mock_valkey = AsyncMock(spec=ValkeyManager)
    mock_valkey.save_agent_memory = AsyncMock(return_value=True)
    
    engine = LearningEngine(mock_valkey)
    
    # Real user interactions to analyze
    interactions = [
        {"message": "Deploy a VM in us-east4 for our production environment", "timestamp": "2024-01-10T10:00:00"},
        {"message": "I need RHEL 8 as always", "timestamp": "2024-01-10T10:01:00"},
        {"message": "Make it an n1-standard-4 instance", "timestamp": "2024-01-10T10:02:00"},
        {"message": "Actually, let's go with n1-standard-8 for better performance", "timestamp": "2024-01-10T10:03:00"},
        {"message": "Create another RHEL VM in us-east4-a", "timestamp": "2024-01-11T14:00:00"},
        {"message": "Production environment again, n1-standard-8", "timestamp": "2024-01-11T14:01:00"},
        {"message": "One more VM, same config as before - RHEL in production", "timestamp": "2024-01-12T09:00:00"}
    ]
    
    print("\nUser Interaction History:")
    for i, interaction in enumerate(interactions, 1):
        print(f"  {i}. {interaction['message']}")
    
    if engine.llm:
        print("\n🤖 Analyzing preferences with LLM...")
        
        # Get actual preferences from LLM
        preferences = await engine.learn_user_preferences("demo_user_123", interactions)
        
        print("\n✨ AI-Extracted User Preferences:")
        print(f"\n  User ID: {preferences.user_id}")
        
        if preferences.cloud_provider:
            confidence = preferences.confidence_scores.get("cloud_provider", 0)
            print(f"  Cloud Provider: {preferences.cloud_provider} (confidence: {confidence:.2%})")
        
        if preferences.operating_system:
            confidence = preferences.confidence_scores.get("operating_system", 0)
            print(f"  Operating System: {preferences.operating_system} (confidence: {confidence:.2%})")
        
        if preferences.machine_types:
            confidence = preferences.confidence_scores.get("machine_types", 0)
            print(f"  Machine Types: {', '.join(preferences.machine_types)} (confidence: {confidence:.2%})")
        
        if preferences.regions:
            confidence = preferences.confidence_scores.get("regions", 0)
            print(f"  Preferred Regions: {', '.join(preferences.regions)} (confidence: {confidence:.2%})")
        
        if preferences.communication_style:
            confidence = preferences.confidence_scores.get("communication_style", 0)
            print(f"  Communication Style: {preferences.communication_style} (confidence: {confidence:.2%})")
        
        if preferences.custom_preferences:
            print(f"\n  Additional Preferences Detected:")
            for key, value in preferences.custom_preferences.items():
                print(f"    - {key}: {value}")
    else:
        print("\n❌ LLM not available - cannot demonstrate actual preference learning")


async def demo_agent_reflection_with_llm():
    """Demonstrate ACTUAL agent reflection using LLM"""
    print("\n" + "="*60)
    print("DEMO: Agent-Specific Reflection with LLM")
    print("="*60)
    
    # Create an orchestrator agent with mocked dependencies
    orchestrator = OrchestratorAgent()
    
    if orchestrator.llm:
        print("\n🤖 Orchestrator Agent Reflection:")
        print("  Scenario: Routed 'I need a VM' to compute agent")
        print("  Outcome: Successfully provisioned")
        
        # Perform actual reflection
        reflection_result = await orchestrator.reflect_on_routing(
            routing_decision="compute",
            outcome="success",
            session_context={
                "user_input": "I need a VM in GCP",
                "extracted_keywords": ["VM", "GCP"],
                "confidence_before": 0.7,
                "time_taken": 1.2
            }
        )
        
        print("\n✨ AI-Generated Reflection Analysis:")
        print(f"  Correct Routing: {reflection_result.get('correct_routing', 'Unknown')}")
        
        if reflection_result.get("better_agent"):
            print(f"  Better Agent Suggested: {reflection_result['better_agent']}")
        
        if reflection_result.get("routing_patterns"):
            print(f"\n  Routing Patterns Identified:")
            for pattern in reflection_result["routing_patterns"]:
                print(f"    • {pattern}")
        
        if reflection_result.get("confidence_adjustment"):
            print(f"\n  Confidence Adjustments:")
            for agent, adjustment in reflection_result["confidence_adjustment"].items():
                sign = "+" if adjustment > 0 else ""
                print(f"    • {agent}: {sign}{adjustment}")
        
        if reflection_result.get("lessons"):
            print(f"\n  Lessons Learned:")
            for lesson in reflection_result["lessons"]:
                print(f"    • {lesson}")
        
        if reflection_result.get("user_type_pattern"):
            print(f"\n  User Type Pattern: {reflection_result['user_type_pattern']}")
        
        # Demonstrate conversation flow evaluation
        print("\n" + "-"*40)
        print("\n🤖 Evaluating Conversation Flow:")
        
        conversation_history = [
            {"timestamp": "10:00:00", "agent": "orchestrator", "action": "route", "result": "compute"},
            {"timestamp": "10:00:01", "agent": "compute", "action": "extract", "result": {"env": "prod", "os": "rhel"}},
            {"timestamp": "10:00:02", "agent": "clarification", "action": "ask_zone", "result": "us-east4-a"},
            {"timestamp": "10:00:03", "agent": "gce_specialist", "action": "provision", "result": "success"}
        ]
        
        flow_evaluation = await orchestrator.evaluate_conversation_flow(conversation_history)
        
        print("\n✨ AI-Generated Flow Analysis:")
        print(f"  Coherence Score: {flow_evaluation.get('coherence_score', 0)}/10")
        print(f"  Efficiency Score: {flow_evaluation.get('efficiency_score', 0)}/10")
        
        if flow_evaluation.get("unnecessary_steps"):
            print(f"\n  Unnecessary Steps:")
            for step in flow_evaluation["unnecessary_steps"]:
                print(f"    • {step}")
        
        if flow_evaluation.get("missed_opportunities"):
            print(f"\n  Missed Opportunities:")
            for opp in flow_evaluation["missed_opportunities"]:
                print(f"    • {opp}")
        
        if flow_evaluation.get("improvements"):
            print(f"\n  Suggested Improvements:")
            for imp in flow_evaluation["improvements"]:
                print(f"    • {imp}")
    else:
        print("\n❌ LLM not available - cannot demonstrate actual reflection")


async def demo_improvement_suggestions_with_llm():
    """Demonstrate ACTUAL improvement suggestions using LLM"""
    print("\n" + "="*60)
    print("DEMO: AI-Generated Improvement Suggestions")
    print("="*60)
    
    # Initialize learning engine
    mock_valkey = AsyncMock(spec=ValkeyManager)
    engine = LearningEngine(mock_valkey)
    
    # Real performance data to analyze
    recent_performance = [
        {"action": "route_to_compute", "success": True, "latency": 0.8, "confidence": 0.9},
        {"action": "extract_requirements", "success": True, "latency": 1.2, "confidence": 0.85},
        {"action": "clarify_zone", "success": True, "latency": 5.2, "confidence": 0.7},
        {"action": "extract_requirements", "success": False, "error": "Could not identify OS", "latency": 1.5},
        {"action": "route_to_compute", "success": True, "latency": 0.6, "confidence": 0.95},
        {"action": "provision", "success": True, "latency": 3.2, "confidence": 0.9},
        {"action": "extract_requirements", "success": False, "error": "Machine type ambiguous", "latency": 1.8},
        {"action": "clarify_machine_type", "success": True, "latency": 4.5, "confidence": 0.75},
        {"action": "provision", "success": True, "latency": 2.9, "confidence": 0.92},
        {"action": "route_to_compute", "success": True, "latency": 0.7, "confidence": 0.93}
    ]
    
    print("\nAnalyzing Compute Agent Performance:")
    successes = sum(1 for p in recent_performance if p["success"])
    print(f"  Total Actions: {len(recent_performance)}")
    print(f"  Success Rate: {successes}/{len(recent_performance)} ({successes/len(recent_performance)*100:.1f}%)")
    print(f"  Average Latency: {sum(p['latency'] for p in recent_performance)/len(recent_performance):.2f}s")
    
    failures = [p for p in recent_performance if not p["success"]]
    if failures:
        print(f"\n  Recent Failures:")
        for failure in failures:
            print(f"    • {failure['action']}: {failure.get('error', 'Unknown error')}")
    
    if engine.llm:
        print("\n🤖 Generating AI-Powered Improvement Suggestions...")
        
        # Get actual improvement suggestions from LLM
        suggestions = await engine.suggest_improvements("compute", recent_performance)
        
        if suggestions:
            print("\n✨ AI-Generated Improvement Suggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"\n  {i}. [{suggestion.impact.upper()}] {suggestion.suggestion}")
                print(f"     Confidence: {suggestion.confidence:.2%}")
                print(f"     Implementation: {suggestion.implementation}")
                if suggestion.estimated_benefit:
                    print(f"     Expected Benefit: {suggestion.estimated_benefit}")
        else:
            print("\n  No high-confidence suggestions generated")
    else:
        print("\n❌ LLM not available - cannot generate actual improvement suggestions")


async def demo_real_learning_coordination():
    """Demonstrate ACTUAL cross-agent learning coordination"""
    print("\n" + "="*60)
    print("DEMO: Cross-Agent Learning Coordination with LLM")
    print("="*60)
    
    # Initialize learning engine
    mock_valkey = AsyncMock(spec=ValkeyManager)
    mock_valkey.save_learned_pattern = AsyncMock(return_value=True)
    engine = LearningEngine(mock_valkey)
    
    if engine.llm:
        print("\n🤖 Coordinating Learning Across Agents...")
        
        # Create agent memory snapshots
        from utils.learning import AgentMemory
        
        agent_memories = {
            "orchestrator": AgentMemory(
                agent_name="orchestrator",
                learned_patterns=[
                    {"pattern": "VM requests go to compute", "confidence": 0.9},
                    {"pattern": "Database requests need clarification", "confidence": 0.7}
                ],
                corrections=[
                    {"field": "routing", "original": "clarification", "corrected": "compute", "reason": "Had VM keyword"}
                ],
                performance_metrics={"success_rate": 0.88, "avg_confidence": 0.85}
            ),
            "compute": AgentMemory(
                agent_name="compute",
                learned_patterns=[
                    {"pattern": "Production is most common environment", "confidence": 0.8},
                    {"pattern": "RHEL is preferred OS", "confidence": 0.75}
                ],
                corrections=[
                    {"field": "os", "original": "ubuntu", "corrected": "rhel", "reason": "User preference"}
                ],
                performance_metrics={"success_rate": 0.75, "avg_confidence": 0.78}
            ),
            "clarification": AgentMemory(
                agent_name="clarification",
                learned_patterns=[
                    {"pattern": "Zone often missing, needs asking", "confidence": 0.85},
                    {"pattern": "Users understand 'Which zone?' better than technical terms", "confidence": 0.9}
                ],
                corrections=[],
                performance_metrics={"success_rate": 0.92, "avg_confidence": 0.88}
            )
        }
        
        print("\nAgent Memory States:")
        for agent_name, memory in agent_memories.items():
            print(f"\n  {agent_name.capitalize()}:")
            print(f"    Patterns learned: {len(memory.learned_patterns)}")
            print(f"    Corrections: {len(memory.corrections)}")
            print(f"    Success rate: {memory.performance_metrics['success_rate']:.2%}")
        
        # Coordinate learning
        coordination_result = await engine.coordinate_agent_learning(
            agent_memories,
            "success"
        )
        
        print("\n✨ AI-Generated Coordination Analysis:")
        
        if coordination_result.get("shared_patterns"):
            print("\n  Patterns to Share Across Agents:")
            for pattern in coordination_result["shared_patterns"]:
                print(f"    • Pattern: {pattern.get('pattern', 'Unknown')}")
                print(f"      Affects: {', '.join(pattern.get('agents_affected', []))}")
                print(f"      Action: {pattern.get('action', 'Unknown')}")
        
        if coordination_result.get("conflicts"):
            print("\n  Conflicts Detected:")
            for conflict in coordination_result["conflicts"]:
                print(f"    • {conflict.get('description', 'Unknown conflict')}")
                print(f"      Resolution: {conflict.get('resolution', 'No resolution suggested')}")
        
        if coordination_result.get("coordination_actions"):
            print("\n  Coordination Actions:")
            for action in coordination_result["coordination_actions"]:
                print(f"    • {action}")
    else:
        print("\n❌ LLM not available - cannot demonstrate actual coordination")


async def main():
    """Run all LLM-powered demos"""
    print("\n" + "🤖"*30)
    print("   PHASE 4: LLM-POWERED LEARNING SYSTEM DEMO")
    print("🤖"*30)
    
    # Check for API key
    has_api_key = check_api_key()
    
    if has_api_key:
        print("\n✅ OpenAI API Key detected - Running with ACTUAL AI capabilities!")
        print(f"   Model: gpt-5-mini (or configured fallback)")
        print(f"   Temperature: 1.0")
        print("\nNOTE: This demo makes real API calls and may incur costs.\n")
    else:
        print("\n⚠️  Running in LIMITED mode - Install API key to see real AI learning\n")
    
    # Run demos
    await demo_pattern_recognition_with_llm()
    await demo_user_preference_learning_with_llm()
    await demo_agent_reflection_with_llm()
    await demo_improvement_suggestions_with_llm()
    await demo_real_learning_coordination()
    
    print("\n" + "="*60)
    if has_api_key:
        print("✅ LLM-POWERED DEMO COMPLETE")
        print("="*60)
        print("\n🎯 What You Just Witnessed:")
        print("  • REAL pattern recognition using GPT")
        print("  • ACTUAL preference extraction via AI")
        print("  • GENUINE reflection analysis with LLM")
        print("  • AI-GENERATED improvement suggestions")
        print("  • TRUE cross-agent learning coordination")
        print("\n💡 All learning decisions made by AI, NO hardcoded logic!")
    else:
        print("⚠️  DEMO STRUCTURE SHOWN - ADD API KEY FOR FULL EXPERIENCE")
        print("="*60)
        print("\nTo see actual AI-powered learning:")
        print("  1. Get OpenAI API key: https://platform.openai.com")
        print("  2. Add to backend/.env: OPENAI_API_KEY=sk-...")
        print("  3. Run this demo again")
    
    print("\n📚 System Capabilities:")
    print("  • Pattern Recognition - AI identifies patterns in interactions")
    print("  • Preference Learning - AI extracts user preferences")
    print("  • Agent Reflection - AI analyzes and improves decisions")
    print("  • Improvement Generation - AI suggests optimizations")
    print("  • Learning Coordination - AI coordinates cross-agent learning")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())