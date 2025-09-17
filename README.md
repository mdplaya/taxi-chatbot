# TAXI Chatbot - Infrastructure Provisioning Assistant

## ⚡ Performance Updates

Recent optimizations have significantly improved system performance:
- **Response Time**: Simple VM requests now respond in under 1 second (previously 10+ seconds)
- **API Efficiency**: Reduced API calls from 10+ to 1-2 for simple requests
- **UI Fix**: Chat input field now properly displays typed text
- **Reliability**: Added timeouts and fallbacks to prevent hanging
- See `PERFORMANCE_FIXES.md` for technical details

## 🚀 Quick Start (for Monday Demo)

### Prerequisites
- Python 3.9+
- Node.js 16+
- Docker & Docker Compose (optional but recommended)

### Option 1: Docker Deployment (Fastest - 5 minutes)

```bash
# 1. Navigate to project directory
cd taxi-chatbot

# 2. Build and start all services
docker-compose up --build

# 3. Access the application
# - Web Interface: http://localhost:3000
# - API (for iOS): http://localhost:8000/docs
# - MCP Server: http://localhost:8001
```

### Option 2: Local Development Setup (10 minutes)

#### Backend Setup
```bash
# 1. Create Python virtual environment
python -m venv venv

# 2. Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 3. Install Python dependencies
cd backend
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env

# 5. Start MCP Server (Terminal 1)
python mcp_server/server.py

# 6. Start API Server (Terminal 2)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Voice Mode Configuration (ElevenLabs)
1. Create an ElevenLabs API key and choose the streaming STT model, TTS model, and voice ID you plan to use.
2. Update both `.env` (project root) and `backend/.env` with the following entries:
   - `ELEVENLABS_API_KEY`
   - `ELEVENLABS_STT_MODEL`
   - `ELEVENLABS_TTS_MODEL`
   - `ELEVENLABS_VOICE_ID`
   - (Optional) `ELEVENLABS_API_ENDPOINT` if you need a regional endpoint override.
3. Install the ElevenLabs SDK locally (`pip install elevenlabs`) or rebuild the Docker image to pull the dependency automatically.
4. When running via Docker, these variables automatically pass through to the API container (`docker-compose.yml`).
5. Start the backend API normally; the `/voice/session`, `/voice/stream`, and `/voice/respond` endpoints will proxy ElevenLabs while reusing the existing agent orchestration. Streaming transcription now uses the ElevenLabs WebSocket API with a REST fallback so short-lived outages keep the feature usable.
6. In the web UI, toggle **Voice Mode** under the provider chips, grant microphone permissions, and use **Start recording** to capture audio. The assistant synchronizes transcripts with chat history and replies using ElevenLabs TTS.

> 🔒 Voice credentials stay in environment variables only; the server never logs or returns secret values.

#### Frontend Setup
```bash
# 7. In a new terminal, navigate to frontend
cd frontend

# 8. Install Node dependencies
npm install

# 9. Start Next.js development server
npm run dev
```

## 🧪 Testing the System

### Test Flow 1: Complete VM Request
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want a VM in GCP"}'
```

### Test Flow 2: With Clarifications
1. Open http://localhost:3000
2. Type: "I need a Linux VM for our retail application"
3. Answer the clarification questions
4. Verify the generated TAXI payload

### Test Flow 3: iOS API Test
```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint (iOS compatible)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a VM in GCP for development",
    "session_id": null
  }'
```

## 📱 iOS Integration

The API is CORS-enabled and ready for iOS integration:

**Base URL**: `http://your-server:8000`

**Endpoints**:
- `POST /chat` - Main conversation endpoint
- `POST /answer` - Submit clarification answers
- `GET /session/{session_id}/status` - Check provisioning status

**Swift Example**:
```swift
let url = URL(string: "http://your-server:8000/chat")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")

let body = ["message": "I want a VM in GCP", "session_id": nil]
request.httpBody = try JSONSerialization.data(withJSONObject: body)

URLSession.shared.dataTask(with: request) { data, response, error in
    // Handle response
}.resume()
```

## 🏗️ Architecture Overview

```
User Input → Orchestrator Agent → Compute Agent → GCE Specialist Agent
                    ↓
            Clarification Agent (if needed)
                    ↓
              MCP Server → TAXI API (mocked)
```

## 🔧 Configuration

### Environment Variables (.env)
```
# MCP Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8001

# API Server
API_HOST=0.0.0.0
API_PORT=8000
OPENAI_API_KEY=your-key-here  # For Marvin.ai

# TAXI API (for production)
TAXI_API_URL=https://your-taxi-api.com
TAXI_API_KEY=your-taxi-key
```

### Modifying Agent Behavior

Edit agent prompts in:
- `backend/agents/orchestrator.py`
- `backend/agents/clarification.py`
- `backend/agents/compute.py`
- `backend/agents/gce_specialist.py`

### Adding New Fields

1. Update Pydantic models in `backend/models/taxi_models.py`
2. Add field to required fields list in `VMRequest.get_missing_fields()`
3. Update TAXI payload builder in `mcp_server/tools.py`

## 🚢 Production Deployment

### Option 1: AWS EC2
```bash
# 1. Launch EC2 instance (t3.medium recommended)
# 2. SSH into instance
# 3. Clone repository
git clone your-repo-url
cd taxi-chatbot

# 4. Install Docker
sudo yum update -y
sudo yum install docker -y
sudo service docker start

# 5. Install Docker Compose
sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 6. Run application
sudo docker-compose up -d
```

### Option 2: Google Cloud Run
```bash
# 1. Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT/taxi-chatbot

# 2. Deploy to Cloud Run
gcloud run deploy taxi-chatbot \
  --image gcr.io/YOUR_PROJECT/taxi-chatbot \
  --platform managed \
  --allow-unauthenticated \
  --port 8000
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Find and kill process using port 8000
   lsof -ti:8000 | xargs kill -9
   ```

2. **MCP Server connection failed**
   - Check MCP server is running: `curl http://localhost:8001/health`
   - Verify MCP_SERVER_URL in API environment

3. **Marvin.ai errors**
   - Ensure OPENAI_API_KEY is set in .env
   - Check API key has sufficient credits

4. **CORS errors from frontend**
   - Verify API URL in frontend/.env.local
   - Check CORS settings in backend/api/main.py

## 📊 Monday Demo Checklist

- [ ] All services running (MCP, API, Frontend)
- [ ] Test basic flow: "I want a VM in GCP"
- [ ] Test clarification flow with missing fields
- [ ] Verify TAXI payload matches specification
- [ ] API accessible for iOS testing
- [ ] Document any issues/limitations

## 📝 Demo Script

1. **Basic Request**
   - "I want a VM in GCP"
   - System asks for clarifications
   - Fill in: NONPROD, dev, RETAIL, 12345, etc.
   - Show generated TAXI payload

2. **Complete Request**
   - "Create a RHEL8 VM in us-east4-a for our retail app development environment using n1-standard-1"
   - System processes without clarifications
   - Immediate TAXI payload generation

3. **iOS API Demo**
   - Show Postman/curl hitting the API
   - Demonstrate session management
   - Show same payload generation

## 🆘 Emergency Contacts

- Backend Issues: Check `backend/logs/`
- Frontend Issues: Check browser console
- MCP Issues: Check `mcp_server/logs/`

## 📚 Additional Resources

- [MCP Protocol Docs](https://modelcontextprotocol.io)
- [Marvin.ai Docs](https://www.askmarvin.ai/)
- [TAXI API Specification](internal-docs-link)

---
**Last Updated**: Sunday Evening
**Version**: 1.0.0-demo
**Status**: Ready for Monday Demo
