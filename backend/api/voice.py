import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from api.chat_pipeline import run_chat_pipeline
from api.deps import logger
from api.schemas import (
    ChatResponse,
    VoiceResponse,
    VoiceResponseRequest,
    VoiceSessionRequest,
    VoiceStreamResponse,
)
from utils.config import VoiceConfigMissing, get_voice_settings, voice_settings_available
from utils.voice import DEFAULT_CONTENT_TYPE, ElevenLabsVoiceClient, VoiceQuotaExceeded

router = APIRouter(prefix="/voice", tags=["voice"])
MAX_STREAM_BYTES = 2 * 1024 * 1024


def _ensure_configured() -> None:
    if not voice_settings_available():
        raise HTTPException(status_code=503, detail="Voice configuration missing; set ELEVENLABS env vars")


def _generate_session_id() -> str:
    return f"voice-{uuid.uuid4().hex[:8]}"


@router.post("/session")
async def create_voice_session(request: VoiceSessionRequest) -> dict:
    _ensure_configured()
    return {"session_id": request.session_id or _generate_session_id()}


@router.post("/stream", response_model=VoiceStreamResponse)
async def stream_transcription(
    request: Request,
    session_id: str = Header(..., alias="x-session-id"),
    audio_format: str = Header("pcm16", alias="x-audio-format"),
) -> VoiceStreamResponse:
    _ensure_configured()
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Audio payload required")
    if len(body) > MAX_STREAM_BYTES:
        raise HTTPException(status_code=413, detail="Audio payload too large")

    try:
        settings = get_voice_settings()
    except VoiceConfigMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    client = ElevenLabsVoiceClient(settings)
    try:
        async with client.transcribe_stream(
            audio=body,
            audio_format=audio_format,
            session_id=session_id,
        ) as stream:
            async for chunk in stream:
                transcript = (chunk.get("transcript") or "").strip()
                if transcript:
                    return VoiceStreamResponse(
                        session_id=session_id,
                        transcript=transcript,
                        is_final=bool(chunk.get("is_final", False)),
                    )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - safe surface for API
        logger.exception("Voice transcription failed")
        raise HTTPException(status_code=502, detail="Voice transcription failed") from exc

    return VoiceStreamResponse(session_id=session_id, transcript="", is_final=False)


@router.post("/respond", response_model=VoiceResponse)
async def voice_respond(payload: VoiceResponseRequest) -> VoiceResponse:
    _ensure_configured()
    if not payload.text:
        raise HTTPException(status_code=400, detail="Text is required")
    try:
        settings = get_voice_settings()
    except VoiceConfigMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    chat_response: ChatResponse = await run_chat_pipeline(
        message=payload.text,
        session_id=payload.session_id,
        raw_message=payload.text,
    )

    client = ElevenLabsVoiceClient(settings)
    try:
        audio_bytes = await client.synthesize_speech(
            text=chat_response.response,
            voice_options=payload.voice_options,
        )
    except VoiceQuotaExceeded as exc:
        logger.warning("Voice synthesis quota exceeded: %s", exc)
        return VoiceResponse(
            session_id=chat_response.session_id,
            text=chat_response.response,
            audio_base64="",
            content_type=DEFAULT_CONTENT_TYPE,
            created_at=datetime.now(timezone.utc),
            chat=chat_response,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - safe surface for API
        logger.exception("Voice synthesis failed")
        raise HTTPException(status_code=502, detail="Voice synthesis failed") from exc

    encoded_audio = base64.b64encode(audio_bytes).decode("ascii")
    return VoiceResponse(
        session_id=chat_response.session_id,
        text=chat_response.response,
        audio_base64=encoded_audio,
        content_type=DEFAULT_CONTENT_TYPE,
        created_at=datetime.now(timezone.utc),
        chat=chat_response,
    )
