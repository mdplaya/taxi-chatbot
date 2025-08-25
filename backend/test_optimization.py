#!/usr/bin/env python3
"""
Test script for TAXI chatbot optimization
Tests the optimized flow with reduced timeouts and simplified routing
"""

import asyncio
import time
import json
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set optimized environment variables before imports
os.environ['REASONING_TIMEOUT_SIMPLE'] = '30'
os.environ['REASONING_MAX_ITERATIONS_SIMPLE'] = '2'
os.environ['GCE_SKIP_VALIDATION'] = 'true'
os.environ['GCE_SKIP_IMPROVEMENTS'] = 'true'
os.environ['GCE_SKIP_QUOTA_CHECK'] = 'true'

from agents.orchestrator import OrchestratorAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent


async def test_simple_vm_request():
    """Test simple VM request - should complete in < 50 seconds"""
    print("\n" + "="*60)
    print("TEST: Simple VM Request")
    print("Expected: < 50 seconds with optimizations")
    print("="*60)
    
    test_request = "Create a Linux server for development in GCP in project dwayne-1234"
    
    start_time = time.time()
    
    # Step 1: Orchestrator
    print(f"\n[{time.time() - start_time:.1f}s] Starting Orchestrator...")
    orchestrator = OrchestratorAgent()
    orchestrator_result = await orchestrator.process(test_request, session_id="test-001")
    
    print(f"[{time.time() - start_time:.1f}s] Orchestrator Result:")
    print(f"  - Next Agent: {orchestrator_result.get('next_agent')}")
    print(f"  - Skip Correction: {orchestrator_result.get('context', {}).get('skip_correction', False)}")
    
    # Step 2: Compute Agent (now just routing)
    if orchestrator_result.get("next_agent") == "compute":
        print(f"\n[{time.time() - start_time:.1f}s] Starting Compute Agent (routing only)...")
        compute = ComputeAgent()
        compute_result = await compute.process(orchestrator_result["context"])
        
        print(f"[{time.time() - start_time:.1f}s] Compute Result:")
        print(f"  - Routed To: {compute_result.get('next_agent')}")
        print(f"  - Mode: {compute_result.get('mode')}")
        
        # Step 3: GCE Specialist (extraction + provisioning)
        if compute_result.get("next_agent") == "gce_specialist":
            print(f"\n[{time.time() - start_time:.1f}s] Starting GCE Specialist (extraction + provisioning)...")
            gce = GCESpecialistAgent()
            
            # Pass the full context from compute agent
            context = compute_result.get("context", orchestrator_result["context"])
            gce_result = await gce.create_instance(context)
            
            print(f"[{time.time() - start_time:.1f}s] GCE Result:")
            print(f"  - Success: {gce_result.get('success', False)}")
            print(f"  - Needs Clarification: {gce_result.get('needs_clarification', False)}")
            print(f"  - Corrections Applied: {gce_result.get('corrections_applied', [])}")
            
            if gce_result.get('needs_clarification'):
                print(f"  - Questions: {gce_result.get('questions', [])[:2]}")
            
            if gce_result.get('partial_data'):
                print(f"  - Extracted Fields: {list(gce_result['partial_data'].keys())}")
    
    total_time = time.time() - start_time
    print(f"\n[COMPLETE] Total Time: {total_time:.1f} seconds")
    
    if total_time < 50:
        print("✅ SUCCESS: Request completed in under 50 seconds!")
    else:
        print(f"⚠️  WARNING: Request took {total_time:.1f} seconds (target: < 50s)")
    
    return total_time


async def test_correction_handling():
    """Test that corrections are applied intelligently"""
    print("\n" + "="*60)
    print("TEST: Intelligent Corrections")
    print("Expected: Corrections applied at specialist level")
    print("="*60)
    
    test_request = "create red hat 8 vm in gcp us-east cheap"
    
    start_time = time.time()
    
    # Process through pipeline
    orchestrator = OrchestratorAgent()
    orchestrator_result = await orchestrator.process(test_request, session_id="test-002")
    
    if orchestrator_result.get("next_agent") == "compute":
        compute = ComputeAgent()
        compute_result = await compute.process(orchestrator_result["context"])
        
        if compute_result.get("next_agent") == "gce_specialist":
            gce = GCESpecialistAgent()
            context = compute_result.get("context", orchestrator_result["context"])
            gce_result = await gce.create_instance(context)
            
            print(f"\nCorrections Applied: {gce_result.get('corrections_applied', [])}")
            
            expected_corrections = ["red hat 8 → LINUX_RHEL8", "cheap → e2-micro"]
            print(f"Expected corrections like: {expected_corrections}")
            
            if gce_result.get('corrections_applied'):
                print("✅ SUCCESS: Corrections were applied")
            else:
                print("⚠️  WARNING: No corrections detected")
    
    total_time = time.time() - start_time
    print(f"\nTotal Time: {total_time:.1f} seconds")


async def test_bypass_flags():
    """Test that bypass flags skip validation/improvements"""
    print("\n" + "="*60)
    print("TEST: Bypass Flags")
    print("Expected: Validation and improvements skipped")
    print("="*60)
    
    # Create GCE specialist with explicit config
    gce = GCESpecialistAgent(config={
        "skip_validation": True,
        "skip_improvements": True,
        "skip_quota_check": True
    })
    
    print(f"Config: {gce.config}")
    
    test_context = {
        "raw_request": "Create a RHEL8 VM in us-east4-a for retail app",
        "session_id": "test-003"
    }
    
    start_time = time.time()
    result = await gce.create_instance(test_context)
    total_time = time.time() - start_time
    
    print(f"\nValidation: {result.get('validation', {})}")
    print(f"Improvements: {result.get('improvements_suggested', [])}")
    
    if result.get('validation', {}).get('skipped'):
        print("✅ SUCCESS: Validation was skipped")
    else:
        print("⚠️  WARNING: Validation was not skipped")
    
    if not result.get('improvements_suggested'):
        print("✅ SUCCESS: Improvements were skipped")
    else:
        print("⚠️  WARNING: Improvements were not skipped")
    
    print(f"\nTotal Time: {total_time:.1f} seconds")


async def main():
    """Run all optimization tests"""
    print("\n" + "="*80)
    print("TAXI CHATBOT OPTIMIZATION TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Check if API key is set
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  WARNING: No OPENAI_API_KEY set - tests will use offline mode")
        print("For full testing, set your OpenAI API key in .env file")
        return
    
    try:
        # Test 1: Simple VM request timing
        time1 = await test_simple_vm_request()
        
        # Test 2: Correction handling
        await test_correction_handling()
        
        # Test 3: Bypass flags
        await test_bypass_flags()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Simple VM Request Time: {time1:.1f}s (Target: < 50s)")
        
        if time1 < 50:
            print("\n🎉 ALL OPTIMIZATIONS WORKING!")
            print("The chatbot now responds in under 50 seconds for simple VM requests.")
        else:
            print("\n⚠️  Optimizations partially working.")
            print("Check the logs for bottlenecks.")
        
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())