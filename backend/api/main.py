from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

# Import agents
from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from models.taxi_models import VMRequest, ChatSession

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# In-memory session storage (use Redis in production)
sessions: Dict[str, ChatSession] = {}

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
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint - processes user messages through agent pipeline
    """
    logger.info(f"Chat request: {request.message}")
    
    # Get or create session
    session_id = request.session_id or generate_session_id()
    
    if session_id not in sessions:
        sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.now(),
            vm_request=VMRequest(),
            status="gathering_info"
        )
    
    session = sessions[session_id]
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent()
    
    try:
        # Process through orchestrator
        orchestrator_result = await orchestrator.process(request.message, session_id)
        
        # Handle routing based on next agent
        if orchestrator_result["next_agent"] == "compute":
            # Process through compute agent
            compute_agent = ComputeAgent()
            compute_result = await compute_agent.process(orchestrator_result["context"])
            
            # Update session with extracted requirements
            if "vm_request" in compute_result:
                vm_request_dict = compute_result["vm_request"].dict() if hasattr(compute_result["vm_request"], 'dict') else compute_result["vm_request"]
                for key, value in vm_request_dict.items():
                    if value is not None:
                        setattr(session.vm_request, key, value)
            
            # Check if clarification needed
            if compute_result.get("needs_clarification"):
                clarification_agent = ClarificationAgent()
                clarification_result = await clarification_agent.get_clarifications(
                    session.vm_request,
                    request.message
                )
                
                if not clarification_result["complete"]:
                    session.status = "gathering_info"
                    sessions[session_id] = session
                    
                    return ChatResponse(
                        response="I need some additional information to create your VM:",
                        needs_clarification=True,
                        questions=clarification_result["questions"],
                        session_id=session_id,
                        status=session.status
                    )
            
            # Ready to provision
            if compute_result.get("provider") == "gcp":
                gce_agent = GCESpecialistAgent()
                provision_result = await gce_agent.create_instance(session.vm_request)
                
                if provision_result["success"]:
                    session.status = "provisioning"
                    session.taxi_payload = provision_result.get("payload_sent")
                    session.taxi_response = provision_result
                    sessions[session_id] = session
                    
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
                        status=session.status
                    )
                else:
                    # Handle provisioning error
                    if provision_result.get("needs_clarification"):
                        clarification_agent = ClarificationAgent()
                        clarification_result = await clarification_agent.get_clarifications(
                            session.vm_request,
                            request.message
                        )
                        
                        return ChatResponse(
                            response="I need some additional information:",
                            needs_clarification=True,
                            questions=clarification_result["questions"],
                            session_id=session_id,
                            status=session.status
                        )
                    
                    return ChatResponse(
                        response=f"❌ Error provisioning VM: {provision_result.get('error', 'Unknown error')}",
                        needs_clarification=False,
                        session_id=session_id,
                        status="failed"
                    )
        
        elif orchestrator_result["next_agent"] == "clarification":
            # Need initial clarification
            return ChatResponse(
                response="I'm not sure what you'd like to do. Could you please provide more details about the resource you want to create?",
                needs_clarification=False,
                session_id=session_id,
                status="gathering_info"
            )
        
        else:
            # Other agents not implemented yet
            return ChatResponse(
                response=f"The {orchestrator_result['next_agent']} agent is not yet implemented. Currently, I can only help with creating VMs in GCP.",
                needs_clarification=False,
                session_id=session_id,
                status="gathering_info"
            )
    
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        return ChatResponse(
            response=f"An error occurred: {str(e)}",
            needs_clarification=False,
            session_id=session_id,
            status="error"
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
    
    # Check if we have all required fields now
    clarification_result = await clarification_agent.get_clarifications(
        session.vm_request,
        ""
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
                status=session.status
            )
        else:
            return ChatResponse(
                response=f"Error: {provision_result.get('error', 'Unknown error')}",
                needs_clarification=False,
                session_id=request.session_id,
                status="failed"
            )
    else:
        # Still need more information
        return ChatResponse(
            response="I need a bit more information:",
            needs_clarification=True,
            questions=clarification_result["questions"],
            session_id=request.session_id,
            status="gathering_info"
        )

@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Get status of a provisioning session
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
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
        "count": len(sessions),
        "sessions": [
            {
                "session_id": sid,
                "status": session.status,
                "created_at": session.created_at.isoformat()
            }
            for sid, session in sessions.items()
        ]
    }

if __name__ == "__main__":
    import uvicorn as uv
    uv.run(app, host="0.0.0.0", port=8000, reload=True)
