from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import Optional, Dict, Any, List, Literal
import logging
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import sys

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import agents
from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from models.taxi_models import VMRequest, ChatSession
from models.agent_session import AgentSession, ConversationState
from utils.llm_manager import llm_manager
from utils.llm_manager import set_llm_debug
from utils.fields import CANONICAL_VM_FIELDS, sanitize_answers
from utils.valkey_manager import get_valkey_manager
valkey_manager = get_valkey_manager()

# Load environment variables - find .env file in backend directory
from pathlib import Path
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Centralized logging
from utils.logging_config import (
    configure_logging,
    get_logger,
    set_session_id,
    reset_session_id,
)
configure_logging()
logger = get_logger(__name__)

# Check LLM availability on startup
current_mode = llm_manager.get_mode()
if current_mode == "offline":
    logger.warning("WARNING: Running in OFFLINE mode - using pattern matching instead of AI.")
    logger.warning("To enable AI features, please set a valid OpenAI API key in your .env file")
else:
    logger.info(f"Running in ONLINE mode - AI features enabled")

# Initialize FastAPI app
app = FastAPI(title="TAXI Chatbot API")

# Simple field normalization mapping
FIELD_NORMALIZATION = {
    "appEnvironment": {
        "PROD": "PROD",
        "PRODUCTION": "PROD",
        "NONPROD": "NONPROD",
        "NON-PROD": "NONPROD",
        "DEV": "NONPROD",
        "TEST": "NONPROD",
        "QA": "NONPROD",
        "DEVELOPMENT": "NONPROD",
        "TESTING": "NONPROD"
    },
    "appEnvironmentSubtype": {
        "dev": "dev",
        "development": "dev",
        "develop": "dev",
        "qa": "qa",
        "quality": "qa",
        "quality-assurance": "qa",
        "test": "test",
        "testing": "test",
        "integration": "test",
        "perf": "perf",
        "performance": "perf",
        "load": "perf"
    },
    "os": {
        "rhel": "LINUX_RHEL9",
        "red hat": "LINUX_RHEL9",
        "rhel8": "LINUX_RHEL8",
        "rhel9": "LINUX_RHEL9",
        "linux": "LINUX_RHEL9",
        "windows": "WINDOWS_22",
        "win": "WINDOWS_22",
        "windows22": "WINDOWS_22",
        "windows2022": "WINDOWS_22",
        "windows19": "WINDOWS_19",
        "windows2019": "WINDOWS_19"
    },
    "useType": {
        "app": "app",
        "application": "app",
        "database": "database",
        "db": "database"
    },
    "lineOfBusiness": {
        "RETAIL": "RETAIL",
        "ISTS": "ISTS", 
        "EDML": "EDML"
    }
}

def normalize_vm_field_value(field: str, value: Any) -> Any:
    """Normalize field values using direct lookup"""
    if value is None:
        return None
    
    if field in FIELD_NORMALIZATION:
        value_key = str(value).lower() if field != "lineOfBusiness" else str(value).upper()
        return FIELD_NORMALIZATION[field].get(value_key, value)
    
    return value

def infer_field_from_question(question: str) -> str:
    """Simple field inference using keyword matching"""
    if not question:
        return ""
    
    q = question.strip().lower()
    
    # Direct field mapping
    field_keywords = {
        "machineType": ["machine type", "instance type", "vm size"],
        "zone": ["zone", "region", "gcp zone", "gcp region"],
        "os": ["operating system", "os", "which os"],
        "useType": ["use type", "workload type", "app or database", "application or database"],
        "project": ["project"],
        "costCenter": ["cost center", "billing code"],
        "lineOfBusiness": ["line of business", "lob"],
        "id": ["email", "requestor", "requester"],
        "appEnvironment": ["environment"],
        "appEnvironmentSubtype": ["dev", "qa", "test", "perf"]
    }
    
    for field, keywords in field_keywords.items():
        if any(keyword in q for keyword in keywords):
            return field
    
    return ""

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
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
    mode: Literal["online", "offline"] = "offline"

class AnswerRequest(BaseModel):
    """Clarification answers from client"""
    session_id: str
    answers: Dict[str, str]

def generate_session_id() -> str:
    """Generate unique session ID"""
    return f"session-{uuid.uuid4().hex[:8]}"

def _set_llm_debug_from_request(request: Request) -> None:
    """Enable LLM debug logging if debug=true"""
    try:
        debug_param = request.query_params.get('debug')
        enabled = str(debug_param).lower() in {"1", "true", "yes"}
        set_llm_debug(enabled)
    except Exception:
        set_llm_debug(False)

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
async def chat(request: ChatRequest, raw_request: Request):
    _set_llm_debug_from_request(raw_request)
    """Main chat endpoint - processes user messages through agent pipeline"""
    
    session_id = request.session_id or generate_session_id()
    token = set_session_id(session_id)
    logger.info(f"Chat request: {request.message}")
    
    if session_id not in legacy_sessions:
        legacy_sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.now(),
            vm_request=VMRequest(),
            status="gathering_info"
        )
    
    session = legacy_sessions[session_id]
    orchestrator = OrchestratorAgent()
    
    try:
        current_mode = llm_manager.get_mode()
        
        # Build context
        provider_hint = None
        try:
            provider_hint = (request.context or {}).get('provider') if request.context else None
        except Exception:
            provider_hint = None
        
        # Process through orchestrator
        orch_input = {
            "message": request.message,
            "session_id": session_id,
            "provider": provider_hint
        }
        orchestrator_result = await orchestrator.process(orch_input, session_id)
        
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
        if orchestrator_result.get("action", {}).get("agent") == "compute":
            # Process through compute agent
            compute_agent = ComputeAgent()
            compute_result = await compute_agent.process(orchestrator_result["context"])
            specialist_name = compute_result.get("action", {}).get("agent", compute_result.get("next_agent"))
            
            if compute_result.get("action", {}).get("agent", compute_result.get("next_agent")) == "unavailable":
                specialist_name = compute_result.get("specialist_name", "unknown")
                cloud_map = {
                    "ec2_specialist": "AWS EC2",
                    "azure_vm_specialist": "Azure VM", 
                    "gce_specialist": "GCP GCE"
                }
                friendly_name = cloud_map.get(specialist_name, specialist_name)
                return ChatResponse(
                    response=f"The {friendly_name} specialist is not yet implemented. Currently, I can only help with GCP VMs.",
                    needs_clarification=False,
                    session_id=session_id,
                    status="unavailable",
                    mode=current_mode
                )
            elif specialist_name == "gce_specialist":
                # Route to GCE specialist
                gce_agent = GCESpecialistAgent()
                provision_result = await gce_agent.create_instance(
                    compute_result.get("context", orchestrator_result["context"])
                )
                
                # Check if clarification needed
                if provision_result.get("needs_clarification"):
                    questions = provision_result.get("questions", [])
                    
                    # Store partial data in session
                    if provision_result.get("partial_data"):
                        partial_data = provision_result["partial_data"]
                        for key, value in partial_data.items():
                            if value is not None and hasattr(session.vm_request, key):
                                normalized_value = normalize_vm_field_value(key, value)
                                try:
                                    setattr(session.vm_request, key, normalized_value)
                                except (ValueError, ValidationError):
                                    logger.warning(f"[API] Ignoring invalid value for {key}: {normalized_value}")
                    
                    session.status = "gathering_info"
                    legacy_sessions[session_id] = session
                    
                    # Format questions for client
                    formatted_questions = []
                    for q in questions[:3]:  # Ask up to 3 questions at a time
                        if isinstance(q, str):
                            inferred_field = infer_field_from_question(q)
                            field = inferred_field or ("machineType" if "machine" in q.lower() else "")
                            formatted_questions.append({
                                "field": field,
                                "question": q,
                                "description": ""
                            })
                        elif isinstance(q, dict):
                            question_text = q.get("question", "Please provide this information.")
                            fld = str(q.get("field", "") or "").strip()
                            if fld not in CANONICAL_VM_FIELDS:
                                inferred = infer_field_from_question(question_text)
                                if not inferred and "machine" in question_text.lower():
                                    inferred = "machineType"
                                fld = inferred or (fld if fld else "")
                            formatted_questions.append({
                                "field": fld,
                                "question": question_text,
                                "description": q.get("description", "")
                            })
                    
                    corrections_msg = ""
                    if provision_result.get("corrections_applied"):
                        corrections_msg = f"\n\n*Corrections applied: {', '.join(provision_result['corrections_applied'])}*"
                    
                    return ChatResponse(
                        response=f"I need some additional information to create your VM:{corrections_msg}",
                        needs_clarification=True,
                        questions=formatted_questions,
                        session_id=session_id,
                        status=session.status,
                        mode=current_mode
                    )
                
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
                        asked_fields = session.metadata.get('asked_fields', []) if hasattr(session, 'metadata') else []
                        context = {
                            'raw_request': request.message,
                            'conversation_history': session.messages if hasattr(session, 'messages') else [],
                            'session_id': session_id,
                            'asked_fields': asked_fields
                        }
                        clarification_agent = ClarificationAgent(context=context)
                        clarification_result = await clarification_agent.get_clarifications(
                            session.vm_request,
                            context
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
            
            elif specialist_name == "clarification":
                return ChatResponse(
                    response="I need more information about your compute request. Are you looking to create a VM in GCP, AWS, or Azure?",
                    needs_clarification=False,
                    session_id=session_id,
                    status="gathering_info",
                    mode=current_mode
                )
            
            else:
                return ChatResponse(
                    response=f"The {specialist_name} specialist is not yet implemented. Currently, I can only help with GCP VMs.",
                    needs_clarification=False,
                    session_id=session_id,
                    status="gathering_info",
                    mode=current_mode
                )
        
        elif orchestrator_result.get("action", {}).get("agent") == "clarification":
            # Ask Business questions via Clarification agent
            asked_fields = session.metadata.get('asked_fields', []) if hasattr(session, 'metadata') else []
            context = {
                'raw_request': request.message,
                'session_id': session_id,
                'asked_fields': asked_fields,
                'conversation_history': session.messages if hasattr(session, 'messages') else []
            }

            clarification_agent = ClarificationAgent(context=context)
            clarification_result = await clarification_agent.get_clarifications(
                session.vm_request,
                context
            )

            # Persist asked_fields in session metadata
            if hasattr(session, 'metadata'):
                session.metadata['asked_fields'] = context.get('asked_fields', [])

            return ChatResponse(
                response="I need some additional information:",
                needs_clarification=True,
                questions=clarification_result.get("questions", []),
                session_id=session_id,
                status="gathering_info",
                mode=current_mode
            )
        
        else:
            return ChatResponse(
                response=f"The {orchestrator_result.get('action', {}).get('agent', 'requested')} agent is not yet implemented. Currently, I can only help with creating VMs in GCP.",
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
    finally:
        try:
            reset_session_id(token)
        except Exception:
            pass

@app.post("/answer", response_model=ChatResponse)
async def answer_clarification(request: AnswerRequest, raw_request: Request):
    _set_llm_debug_from_request(raw_request)
    """Handle clarification answers from the user"""
    
    set_session_id(request.session_id)
    logger.info(f"Answer request for session {request.session_id}")
    
    # Try to get session from Valkey first
    session = await get_session(request.session_id)
    
    # If not in Valkey, check legacy sessions
    if not session:
        if request.session_id not in legacy_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Convert legacy session to AgentSession format
        legacy_session = legacy_sessions[request.session_id]
        session = AgentSession(
            session_id=request.session_id,
            state=ConversationState.GATHERING_INFO,
            current_vm_request=(
                legacy_session.vm_request.model_dump() if hasattr(legacy_session.vm_request, 'model_dump')
                else (legacy_session.vm_request.dict() if hasattr(legacy_session.vm_request, 'dict') else legacy_session.vm_request)
            ),
            conversation_history=[]
        )
    
    # Get the current VM request
    current_vm = session.current_vm_request or getattr(session, 'vm_request', None)
    if not current_vm:
        raise HTTPException(status_code=400, detail="No VM request found in session")
    
    # Convert dict to VMRequest if needed
    if isinstance(current_vm, dict):
        # Normalize all enum fields in the dict before creating VMRequest
        normalized_vm = {}
        for key, value in current_vm.items():
            normalized_vm[key] = normalize_vm_field_value(key, value)
        try:
            vm_request_obj = VMRequest(**normalized_vm)
        except ValidationError as e:
            errs = getattr(e, 'errors', lambda: [])()
            id_error = False
            for err in errs:
                loc = err.get('loc')
                if (isinstance(loc, (list, tuple)) and 'id' in loc) or loc == 'id':
                    id_error = True
                    break
            if id_error:
                logger.warning("[API] Invalid requestor email provided; removing 'id' and continuing clarification flow")
                normalized_vm.pop('id', None)
                vm_request_obj = VMRequest(**normalized_vm)
            else:
                raise
    else:
        vm_request_obj = current_vm
    
    # Get asked_fields from session metadata
    asked_fields = session.metadata.get('asked_fields', []) if hasattr(session, 'metadata') else []
    context = {
        'session_id': request.session_id,
        'asked_fields': asked_fields
    }
    
    # Update VM request with sanitized answers
    clarification_agent = ClarificationAgent(context=context)
    try:
        updated_vm_request = await clarification_agent.process_answers(
            vm_request_obj,
            sanitize_answers(request.answers)
        )
    except (ValueError, ValidationError) as e:
        # Handle invalid enum/field values during clarification
        err_msg = str(e)
        logger.error(f"[API] Clarification validation error: {err_msg}")
        
        # Persist any partial updates that succeeded before the error
        session.current_vm_request = (
            vm_request_obj.model_dump() if hasattr(vm_request_obj, 'model_dump')
            else (vm_request_obj.dict() if hasattr(vm_request_obj, 'dict') else vm_request_obj)
        )
        await save_session(session)

        # Ask for the problematic field and any other missing fields
        clarification_result = await clarification_agent.get_clarifications(
            vm_request_obj,
            context
        )

        current_mode = llm_manager.get_mode()
        return ChatResponse(
            response="I need a bit more information:",
            needs_clarification=True,
            questions=clarification_result.get("questions", []),
            session_id=request.session_id,
            status="gathering_info",
            mode=current_mode
        )
    
    # Store updated asked_fields in session metadata
    if hasattr(session, 'metadata'):
        session.metadata['asked_fields'] = context.get('asked_fields', [])
    
    # Update session with new VM request
    session.current_vm_request = (
        updated_vm_request.model_dump() if hasattr(updated_vm_request, 'model_dump')
        else (updated_vm_request.dict() if hasattr(updated_vm_request, 'dict') else updated_vm_request)
    )
    
    # Save the updated session
    await save_session(session)
    
    # Update legacy session if it exists
    if request.session_id in legacy_sessions:
        legacy_sessions[request.session_id].vm_request = updated_vm_request
    
    current_mode = llm_manager.get_mode()
    
    # Check if we have all required fields now
    clarification_result = await clarification_agent.get_clarifications(
        updated_vm_request,
        context
    )
    
    if clarification_result["complete"]:
        # Ready to provision
        gce_agent = GCESpecialistAgent()
        context = {
            "raw_request": session.conversation_history[0].content if session.conversation_history else "",
            "session_id": request.session_id,
            "vm_request": (
                updated_vm_request.model_dump() if hasattr(updated_vm_request, 'model_dump')
                else (updated_vm_request.dict() if hasattr(updated_vm_request, 'dict') else updated_vm_request)
            )
        }
        provision_result = await gce_agent.create_instance(context)
        
        if provision_result["success"]:
            # Update AgentSession state
            session.state = ConversationState.PROCESSING
            
            # Store provision details
            if not session.user_preferences:
                session.user_preferences = {}
            session.user_preferences["last_provision"] = {
                "taxi_payload": provision_result.get("payload_sent"),
                "taxi_response": provision_result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save session to Valkey
            await save_session(session)
            
            # Update legacy_sessions for backward compatibility
            if request.session_id in legacy_sessions:
                legacy_sessions[request.session_id].status = "provisioning"
                legacy_sessions[request.session_id].taxi_payload = provision_result.get("payload_sent")
                legacy_sessions[request.session_id].taxi_response = provision_result
            
            return ChatResponse(
                response=f"✅ VM provisioning started!\n"
                        f"Job ID: {provision_result['job_id']}\n"
                        f"Instance ID: {provision_result['instance_id']}",
                needs_clarification=False,
                session_id=request.session_id,
                final_payload=provision_result.get("payload_sent"),
                status="provisioning",
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
    """Get status of a provisioning session"""
    if session_id not in legacy_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = legacy_sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "vm_request": session.vm_request.model_dump() if hasattr(session.vm_request, 'model_dump') else (
            session.vm_request.dict() if hasattr(session.vm_request, 'dict') else session.vm_request
        ),
        "taxi_payload": session.taxi_payload,
        "taxi_response": session.taxi_response
    }

@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)"""
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

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    logger.info("TAXI Chatbot API starting up")
    
    # Test Valkey connection
    valkey_healthy = await valkey_manager.health_check()
    if valkey_healthy:
        logger.info("Valkey connection successful")
    else:
        logger.warning("Valkey connection failed - sessions will not persist")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("TAXI Chatbot API shutting down")

if __name__ == "__main__":
    import uvicorn as uv
    uv.run(app, host="0.0.0.0", port=8000, reload=True)