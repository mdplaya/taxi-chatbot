from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Literal
import logging
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import sys
import asyncio
import json

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import agents
from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from models.taxi_models import VMRequest, ChatSession, ProgressStep
from models.agent_session import AgentSession, ConversationState
from utils.llm_manager import llm_manager
from utils.progress_manager import progress_manager
from utils.valkey_manager import valkey_manager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check LLM availability on startup
current_mode = llm_manager.get_mode()
if current_mode == "offline":
    logger.warning("WARNING: Running in OFFLINE mode - using pattern matching instead of AI.")
    logger.warning("To enable AI features, please set a valid OpenAI API key in your .env file")
else:
    logger.info(f"Running in ONLINE mode - AI features enabled")

# Initialize FastAPI app
app = FastAPI(title="TAXI Chatbot API")

# Configure CORS for web and mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage now handled by Valkey
# Legacy in-memory sessions for backward compatibility
legacy_sessions: Dict[str, ChatSession] = {}

async def get_session(session_id: str) -> Optional[AgentSession]:
    """Get session from Valkey"""
    session_data = await valkey_manager.load_session(session_id)
    if session_data:
        return AgentSession.from_valkey_dict(session_data)
    return None

async def save_session(session: AgentSession) -> bool:
    """Save session to Valkey"""
    return await valkey_manager.save_session(
        session.session_id,
        session.to_valkey_dict()
    )

class ChatRequest(BaseModel):
    """Chat request from client"""
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    """Chat response to client"""
    response: str
    needs_clarification: bool
    questions: Optional[List[Dict[str, str]]] = None
    session_id: str
    final_payload: Optional[Dict[str, Any]] = None
    status: str
    mode: Literal["online", "offline"] = "offline"  # Current operation mode

class AnswerRequest(BaseModel):
    """Clarification answers from client"""
    session_id: str
    answers: Dict[str, str]

def generate_session_id() -> str:
    """Generate unique session ID"""
    return f"session-{uuid.uuid4().hex[:8]}"

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "TAXI Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": ["/chat", "/answer", "/session/{session_id}/status", "/health"]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    current_mode = llm_manager.get_mode()
    valkey_healthy = await valkey_manager.health_check()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mode": current_mode,
        "llm_available": current_mode == "online",
        "valkey_status": "connected" if valkey_healthy else "disconnected",
        "model_config": llm_manager.get_model_config()
    }

@app.get("/status")
async def status():
    """Get current system status and mode"""
    current_mode = llm_manager.get_mode()
    return {
        "mode": current_mode,
        "description": "AI-powered responses" if current_mode == "online" else "Pattern-based responses",
        "active_sessions": len(legacy_sessions)
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint - processes user messages through agent pipeline
    """
    logger.info(f"Chat request: {request.message}")
    
    # Get or create session
    session_id = request.session_id or generate_session_id()
    
    if session_id not in legacy_sessions:
        legacy_sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.now(),
            vm_request=VMRequest(),
            status="gathering_info"
        )
    
    session = legacy_sessions[session_id]
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent()
    
    try:
        # Get current mode
        current_mode = llm_manager.get_mode()
        
        # Process through orchestrator
        orchestrator_result = await orchestrator.process(request.message, session_id)
        
        # Ensure we have a valid result
        if not isinstance(orchestrator_result, dict):
            logger.error(f"Invalid orchestrator result type: {type(orchestrator_result)}")
            return ChatResponse(
                response="I'm having trouble processing your request. Please try again.",
                needs_clarification=False,
                session_id=session_id,
                status="error",
                mode=current_mode
            )
        
        # Handle routing based on next agent
        if orchestrator_result.get("next_agent") == "compute":
            # Process through compute agent
            compute_agent = ComputeAgent()
            compute_result = await compute_agent.process(orchestrator_result["context"])
            
            # Check compute result is valid
            if not isinstance(compute_result, dict):
                logger.error(f"Invalid compute result type: {type(compute_result)}, value: {compute_result}")
                compute_result = {"needs_clarification": True, "vm_request": {}}
            
            # Update session with extracted requirements
            if "vm_request" in compute_result:
                vm_request_dict = compute_result["vm_request"].dict() if hasattr(compute_result["vm_request"], 'dict') else compute_result["vm_request"]
                for key, value in vm_request_dict.items():
                    if value is not None:
                        setattr(session.vm_request, key, value)
            
            # Check if clarification needed
            if compute_result.get("needs_clarification"):
                # For now, return a simple clarification response without LLM
                missing = compute_result.get("missing_fields", [])
                
                # Create simple questions for missing fields
                simple_questions = []
                field_prompts = {
                    "appEnvironment": "What environment is this for? (PROD or NONPROD)",
                    "lineOfBusiness": "Which line of business? (RETAIL, ISTS, or EDML)",
                    "costCenter": "What's the 5-digit cost center code?",
                    "project": "What's your GCP project ID?",
                    "zone": "Which GCP zone? (e.g., us-central1-a)",
                    "os": "Which OS? (LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, or WINDOWS_22)",
                    "useType": "What's the use type? (app or database)",
                    "machineType": "What machine type? (e.g., e2-small, n1-standard-1)",
                    "id": "What should we name this VM?"
                }
                
                for field in missing[:3]:  # Ask for 3 fields at a time
                    simple_questions.append({
                        "field": field,
                        "question": field_prompts.get(field, f"What's the {field}?"),
                        "description": ""
                    })
                
                if simple_questions:
                    session.status = "gathering_info"
                    legacy_sessions[session_id] = session
                    
                    return ChatResponse(
                        response="I need some additional information to create your VM:",
                        needs_clarification=True,
                        questions=simple_questions,
                        session_id=session_id,
                        status=session.status,
                        mode=current_mode
                    )
            
            # Ready to provision
            if compute_result.get("provider") == "gcp":
                gce_agent = GCESpecialistAgent()
                provision_result = await gce_agent.create_instance(session.vm_request)
                
                if provision_result["success"]:
                    session.status = "provisioning"
                    session.taxi_payload = provision_result.get("payload_sent")
                    session.taxi_response = provision_result
                    legacy_sessions[session_id] = session
                    
                    return ChatResponse(
                        response=f"✅ VM provisioning started successfully!\n\n"
                                f"**Job ID**: {provision_result['job_id']}\n"
                                f"**Instance ID**: {provision_result['instance_id']}\n"
                                f"**Status**: {provision_result['status']}\n"
                                f"**Estimated Time**: 5-7 minutes\n\n"
                                f"You can check the status using the session ID: {session_id}",
                        needs_clarification=False,
                        session_id=session_id,
                        final_payload=provision_result.get("payload_sent"),
                        status=session.status,
                        mode=current_mode
                    )
                else:
                    # Handle provisioning error
                    if provision_result.get("needs_clarification"):
                        clarification_agent = ClarificationAgent()
                        clarification_result = await clarification_agent.get_clarifications(
                            session.vm_request,
                            {
                                'raw_request': request.message,
                                'conversation_history': session.messages if hasattr(session, 'messages') else [],
                                'session_id': session_id
                            }
                        )
                        
                        return ChatResponse(
                            response="I need some additional information:",
                            needs_clarification=True,
                            questions=clarification_result["questions"],
                            session_id=session_id,
                            status=session.status,
                            mode=current_mode
                        )
                    
                    return ChatResponse(
                        response=f"❌ Error provisioning VM: {provision_result.get('error', 'Unknown error')}",
                        needs_clarification=False,
                        session_id=session_id,
                        status="failed",
                        mode=current_mode
                    )
        
        elif orchestrator_result["next_agent"] == "clarification":
            # Need initial clarification
            return ChatResponse(
                response="I'm not sure what you'd like to do. Could you please provide more details about the resource you want to create?",
                needs_clarification=False,
                session_id=session_id,
                status="gathering_info",
                mode=current_mode
            )
        
        else:
            # Other agents not implemented yet
            return ChatResponse(
                response=f"The {orchestrator_result['next_agent']} agent is not yet implemented. Currently, I can only help with creating VMs in GCP.",
                needs_clarification=False,
                session_id=session_id,
                status="gathering_info",
                mode=current_mode
            )
    
    except Exception as e:
        import traceback
        logger.error(f"Error processing chat: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            response=f"An error occurred: {str(e)}",
            needs_clarification=False,
            session_id=session_id,
            status="error",
            mode=llm_manager.get_mode()
        )

@app.post("/answer", response_model=ChatResponse)
async def answer_clarification(request: AnswerRequest):
    """
    Handle clarification answers from the user
    """
    logger.info(f"Answer request for session {request.session_id}")
    
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[request.session_id]
    
    # Update VM request with answers
    clarification_agent = ClarificationAgent()
    session.vm_request = await clarification_agent.process_answers(
        session.vm_request,
        request.answers
    )
    
    # Get current mode
    current_mode = llm_manager.get_mode()
    
    # Check if we have all required fields now
    clarification_result = await clarification_agent.get_clarifications(
        session.vm_request,
        {
            'raw_request': session.messages[0] if session.messages else '',
            'conversation_history': session.messages if hasattr(session, 'messages') else [],
            'session_id': request.session_id,
            'context_type': 'answer_followup'
        }
    )
    
    if clarification_result["complete"]:
        # Ready to provision
        gce_agent = GCESpecialistAgent()
        provision_result = await gce_agent.create_instance(session.vm_request)
        
        if provision_result["success"]:
            session.status = "provisioning"
            session.taxi_payload = provision_result.get("payload_sent")
            session.taxi_response = provision_result
            sessions[request.session_id] = session
            
            return ChatResponse(
                response=f"✅ VM provisioning started!\n"
                        f"Job ID: {provision_result['job_id']}\n"
                        f"Instance ID: {provision_result['instance_id']}",
                needs_clarification=False,
                session_id=request.session_id,
                final_payload=provision_result.get("payload_sent"),
                status=session.status,
                mode=current_mode
            )
        else:
            return ChatResponse(
                response=f"Error: {provision_result.get('error', 'Unknown error')}",
                needs_clarification=False,
                session_id=request.session_id,
                status="failed",
                mode=current_mode
            )
    else:
        # Still need more information
        return ChatResponse(
            response="I need a bit more information:",
            needs_clarification=True,
            questions=clarification_result["questions"],
            session_id=request.session_id,
            status="gathering_info",
            mode=current_mode
        )

@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Get status of a provisioning session
    """
    if session_id not in legacy_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = legacy_sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "vm_request": session.vm_request.dict(),
        "taxi_payload": session.taxi_payload,
        "taxi_response": session.taxi_response
    }

@app.get("/sessions")
async def list_sessions():
    """
    List all active sessions (for debugging)
    """
    return {
        "count": len(legacy_sessions),
        "sessions": [
            {
                "session_id": sid,
                "status": session.status,
                "created_at": session.created_at.isoformat()
            }
            for sid, session in legacy_sessions.items()
        ]
    }

@app.get("/chat/stream")
async def chat_stream(request: Request, message: str, session_id: Optional[str] = None):
    """
    SSE endpoint for streaming chat with real-time progress updates
    """
    logger.info(f"SSE chat request: {message}")
    
    # Get or create session
    if not session_id:
        session_id = generate_session_id()
    
    if session_id not in legacy_sessions:
        legacy_sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.now(),
            vm_request=VMRequest(),
            status="gathering_info"
        )
    
    session = legacy_sessions[session_id]
    
    async def event_generator():
        """Generate SSE events for the chat stream"""
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "session_id": session_id,
                    "mode": llm_manager.get_mode()
                })
            }
            
            # Create progress callback for agents
            async def progress_callback(agent: str, step: str, message: str, percentage: Optional[int]):
                # Add to session progress
                session.add_progress(agent, step, message, "in_progress", percentage)
                # Add to progress manager
                await progress_manager.add_progress(
                    session_id, agent, step, message, percentage, "in_progress"
                )
            
            # Initialize orchestrator with progress callback
            orchestrator = OrchestratorAgent()
            
            # Process message with progress updates
            await progress_manager.add_progress(
                session_id, "Orchestrator", "analyzing", 
                "Analyzing your request...", 10, "started"
            )
            
            orchestrator_result = await orchestrator.process(message, session_id)
            
            # Handle response based on next agent
            if orchestrator_result["next_agent"] == "compute":
                await progress_manager.add_progress(
                    session_id, "Compute", "extracting", 
                    "Extracting VM requirements from your request...", 30, "in_progress"
                )
                
                compute_agent = ComputeAgent()
                # Create context for compute agent
                compute_context = {
                    "provider": orchestrator_result.get("context", {}).get("provider", "gcp"),
                    "raw_request": message,
                    "session_id": session_id,
                    "conversation_history": []
                }
                compute_result = await compute_agent.process(compute_context)
                
                # Update session with extracted requirements
                for key, value in compute_result.items():
                    if hasattr(session.vm_request, key) and value is not None:
                        setattr(session.vm_request, key, value)
                
                # Check for missing fields
                missing = session.vm_request.get_missing_fields()
                
                if missing:
                    await progress_manager.add_progress(
                        session_id, "Clarification", "checking", 
                        "Identifying missing information...", 50, "in_progress"
                    )
                    
                    clarification_agent = ClarificationAgent()
                    questions = await clarification_agent.generate_questions(
                        session.vm_request, missing
                    )
                    
                    # Send clarification response
                    yield {
                        "event": "clarification",
                        "data": json.dumps({
                            "response": "I need some additional information to provision your VM:",
                            "needs_clarification": True,
                            "questions": questions,
                            "session_id": session_id,
                            "status": "gathering_info"
                        })
                    }
                else:
                    # Ready to provision
                    await progress_manager.add_progress(
                        session_id, "GCE Specialist", "provisioning", 
                        "Preparing TAXI payload for VM provisioning...", 80, "in_progress"
                    )
                    
                    gce_agent = GCESpecialistAgent()
                    provision_result = gce_agent.provision(session.vm_request)
                    
                    session.taxi_payload = provision_result.get("payload")
                    session.taxi_response = provision_result.get("response")
                    session.status = "complete" if provision_result.get("success") else "failed"
                    
                    await progress_manager.add_progress(
                        session_id, "GCE Specialist", "complete", 
                        "VM provisioning request completed", 100, "completed"
                    )
                    
                    # Send final response
                    yield {
                        "event": "complete",
                        "data": json.dumps({
                            "response": provision_result.get("message", "VM provisioning completed"),
                            "needs_clarification": False,
                            "session_id": session_id,
                            "final_payload": session.taxi_payload,
                            "status": session.status
                        })
                    }
            
            else:
                # Other flows not fully implemented
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "response": f"Processing with {orchestrator_result['next_agent']} agent...",
                        "session_id": session_id
                    })
                }
                
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "session_id": session_id
                })
            }
    
    return EventSourceResponse(event_generator())

@app.get("/session/{session_id}/progress")
async def get_session_progress(
    session_id: str,
    limit: int = 10,
    since_timestamp: Optional[str] = None
):
    """
    Get recent progress events for a session (polling fallback)
    """
    if session_id not in legacy_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    since_dt = None
    if since_timestamp:
        try:
            since_dt = datetime.fromisoformat(since_timestamp)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Get progress from manager
    events = progress_manager.get_recent_progress(session_id, limit, since_dt)
    summary = progress_manager.get_session_progress_summary(session_id)
    
    return {
        "session_id": session_id,
        "summary": summary,
        "events": events
    }

@app.get("/session/{session_id}/progress/stream")
async def stream_session_progress(session_id: str):
    """
    SSE endpoint for streaming progress updates only
    """
    if session_id not in legacy_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def progress_stream():
        """Generate SSE stream from progress manager"""
        async for event in progress_manager.create_sse_stream(session_id):
            yield event
    
    return EventSourceResponse(progress_stream())

# New Conversational Endpoints

class CorrectionRequest(BaseModel):
    """Request for field correction"""
    session_id: str
    field: str
    old_value: Any
    new_value: Any

class ConfirmRequest(BaseModel):
    """Request for confirmation before action"""
    session_id: str
    action: str
    payload: Dict[str, Any]

class FeedbackRequest(BaseModel):
    """User feedback for learning"""
    session_id: str
    feedback_type: str  # 'positive', 'negative', 'correction'
    details: Dict[str, Any]

@app.post("/correct")
async def correct_field(request: CorrectionRequest):
    """Handle inline field corrections"""
    try:
        # Load session from Valkey
        session = await get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Track correction
        session.add_correction(
            field=request.field,
            old_value=request.old_value,
            new_value=request.new_value,
            corrected_by="user"
        )
        
        # Update VM request if applicable
        if session.current_vm_request and request.field in session.current_vm_request:
            session.current_vm_request[request.field] = request.new_value
        
        # Save session
        await save_session(session)
        
        # Let agents learn from this correction
        if session.current_agent:
            # This would trigger the agent's learn_from_correction method
            logger.info(f"Agent {session.current_agent} learning from correction: {request.field}")
        
        return {
            "success": True,
            "message": f"Field '{request.field}' corrected successfully",
            "session_id": request.session_id
        }
        
    except Exception as e:
        logger.error(f"Error handling correction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/confirm")
async def confirm_submission(request: ConfirmRequest):
    """Confirm before final submission"""
    try:
        # Load session from Valkey
        session = await get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update state to confirming
        session.update_state(ConversationState.CONFIRMING)
        session.add_message(
            role="user",
            content=f"Confirmed action: {request.action}",
            metadata={"payload": request.payload}
        )
        
        # Save session
        await save_session(session)
        
        # Process the confirmed action
        if request.action == "provision_vm":
            session.update_state(ConversationState.PROCESSING)
            await save_session(session)
            
            # Trigger provisioning with the confirmed payload
            gce_agent = GCESpecialistAgent()
            vm_request = VMRequest(**request.payload)
            provision_result = await gce_agent.create_instance(vm_request)
            
            session.final_payload = request.payload
            session.provision_result = provision_result
            session.update_state(
                ConversationState.COMPLETED if provision_result["success"] 
                else ConversationState.ERROR
            )
            await save_session(session)
            
            return {
                "success": provision_result["success"],
                "message": provision_result.get("message", "Action completed"),
                "result": provision_result,
                "session_id": request.session_id
            }
        
        return {
            "success": True,
            "message": f"Action '{request.action}' confirmed",
            "session_id": request.session_id
        }
        
    except Exception as e:
        logger.error(f"Error handling confirmation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/learn")
async def learn_from_feedback(request: FeedbackRequest):
    """Learn from user feedback"""
    try:
        # Load session from Valkey
        session = await get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Store feedback in session
        session.metadata["feedback"] = session.metadata.get("feedback", [])
        session.metadata["feedback"].append({
            "type": request.feedback_type,
            "details": request.details,
            "timestamp": datetime.now().isoformat()
        })
        
        # If positive feedback, save patterns for future use
        if request.feedback_type == "positive" and session.current_agent:
            # Save successful patterns to Valkey for cross-session learning
            await valkey_manager.save_learned_pattern(
                agent_name=session.current_agent,
                pattern_type="successful_interaction",
                pattern_data={
                    "context": session.get_recent_context(5),
                    "outcome": request.details
                },
                confidence=0.9
            )
        
        # Save session
        await save_session(session)
        
        return {
            "success": True,
            "message": "Thank you for your feedback. I'll use this to improve!",
            "session_id": request.session_id
        }
        
    except Exception as e:
        logger.error(f"Error handling feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{session_id}")
async def stream_progress(session_id: str):
    """Stream real-time progress updates via SSE"""
    async def event_generator():
        while True:
            try:
                # Get session from Valkey
                session = await get_session(session_id)
                if session:
                    yield {
                        "data": json.dumps({
                            "state": session.state,
                            "current_agent": session.current_agent,
                            "progress": f"Processing with {session.current_agent or 'system'}..."
                        })
                    }
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                break
    
    return EventSourceResponse(event_generator())

# Start progress manager cleanup task on startup
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    await progress_manager.start_cleanup_task()
    logger.info("Progress manager cleanup task started")
    
    # Test Valkey connection
    valkey_healthy = await valkey_manager.health_check()
    if valkey_healthy:
        logger.info("Valkey connection successful")
    else:
        logger.warning("Valkey connection failed - sessions will not persist")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    progress_manager.stop_cleanup_task()
    logger.info("Progress manager cleanup task stopped")

if __name__ == "__main__":
    import uvicorn as uv
    uv.run(app, host="0.0.0.0", port=8000, reload=True)
