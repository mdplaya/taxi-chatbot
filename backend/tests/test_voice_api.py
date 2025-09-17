import asyncio
import base64
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from api.schemas import ChatResponse
from backend.utils.config import VoiceSettings, get_voice_settings
from backend.utils.voice import ElevenLabsVoiceClient


def _activate_voice_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_STT_MODEL", "test-stt")
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "test-tts")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_voice_env(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_STT_MODEL", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_MODEL", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    get_voice_settings.cache_clear()

    yield

    get_voice_settings.cache_clear()


class DummyStream:
    """Reusable async iterator for API-level tests."""

    def __init__(self, transcript: str):
        self.transcript = transcript

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def __aiter__(self):
        yield {"transcript": self.transcript, "is_final": False}
        yield {"transcript": self.transcript + " final", "is_final": True}


class DummyWebSocket:
    """Simple in-memory WebSocket stub for streaming tests."""

    def __init__(self, responses: List[str]):
        self.responses = responses
        self.sent: List[bytes] = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    async def send(self, data: bytes) -> None:
        self.sent.append(data)

    async def recv(self) -> Optional[str]:
        if self.responses:
            # simulate network task switching
            await asyncio.sleep(0)
            return self.responses.pop(0)
        await asyncio.sleep(0)
        return json.dumps({"type": "close"})

    async def close(self) -> None:
        self.closed = True


@dataclass
class FakeConvertResponse:
    text: str = ""
    segments: Optional[List[Dict[str, str]]] = None


class FakeAsyncTextToSpeech:
    def __init__(self, payload_bytes: bytes):
        self.payload_bytes = payload_bytes
        self.calls: List[Dict[str, str]] = []

    async def convert(self, voice_id: str, *, text: str, model_id: Optional[str] = None, **kwargs):
        self.calls.append({"voice_id": voice_id, "text": text, "model_id": model_id})

        async def iterator():
            yield self.payload_bytes

        return iterator()


class FakeAsyncSpeechToText:
    def __init__(self):
        self.calls: List[Dict[str, str]] = []

    async def convert(self, *, model_id: str, file, **kwargs):  # noqa: ANN001 - match SDK signature
        self.calls.append({"model_id": model_id})
        return FakeConvertResponse(text="rest fallback transcript")


class FakeAsyncElevenLabs:
    def __init__(self, *, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.speech_to_text = FakeAsyncSpeechToText()
        self.text_to_speech = FakeAsyncTextToSpeech(payload_bytes=b"sdk-bytes")


def test_voice_session_requires_config():
    response = client.post("/voice/session", json={"session_id": "abc"})
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"].startswith("Voice configuration missing")


def test_voice_stream_transcribes_chunk(monkeypatch):
    _activate_voice_env(monkeypatch)

    dummy_stream = DummyStream("hello there")

    monkeypatch.setattr(
        "backend.utils.voice.ElevenLabsVoiceClient.transcribe_stream",
        lambda *args, **kwargs: dummy_stream,
    )
    monkeypatch.setattr(
        "utils.voice.ElevenLabsVoiceClient.transcribe_stream",
        lambda *args, **kwargs: dummy_stream,
    )

    response = client.post(
        "/voice/stream",
        data=b"fake-bytes",
        headers={
            "content-type": "audio/wav",
            "x-session-id": "session-1",
            "x-audio-format": "pcm16",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-1"
    assert body["transcript"] == "hello there"
    assert body["is_final"] is False


def test_voice_respond_generates_tts(monkeypatch):
    _activate_voice_env(monkeypatch)

    async def fake_run_chat_pipeline(**kwargs):
        return ChatResponse(
            response="Hello world",
            needs_clarification=False,
            questions=None,
            session_id="session-1",
            final_payload=None,
            status="ok",
            mode="online",
        )

    monkeypatch.setattr(
        "backend.api.voice.run_chat_pipeline",
        fake_run_chat_pipeline,
    )
    monkeypatch.setattr(
        "api.voice.run_chat_pipeline",
        fake_run_chat_pipeline,
    )
    monkeypatch.setattr(
        "api.chat_pipeline.run_chat_pipeline",
        fake_run_chat_pipeline,
    )
    monkeypatch.setattr(
        "backend.api.chat_pipeline.run_chat_pipeline",
        fake_run_chat_pipeline,
        raising=False,
    )

    import backend.api.voice as voice_module

    assert voice_module.run_chat_pipeline is fake_run_chat_pipeline

    fake_client = ElevenLabsVoiceClient(
        VoiceSettings(
            api_key="test-key",
            stt_model="test-stt",
            tts_model="test-tts",
            voice_id="test-voice",
        )
    )

    synth_bytes = b"test-audio"
    encoded = base64.b64encode(synth_bytes).decode("ascii")

    async def fake_synthesize(*args, **kwargs):
        return synth_bytes

    monkeypatch.setattr(fake_client, "synthesize_speech", fake_synthesize)

    monkeypatch.setattr(
        "backend.api.voice.ElevenLabsVoiceClient",
        lambda settings: fake_client,
    )
    monkeypatch.setattr(
        "api.voice.ElevenLabsVoiceClient",
        lambda settings: fake_client,
    )

    response = client.post(
        "/voice/respond",
        json={
            "session_id": "session-1",
            "text": "Hello world",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-1"
    assert payload["audio_base64"] == encoded
    assert payload["content_type"] == "audio/mpeg"

    assert payload["chat"]["response"] == "Hello world"


def test_transcribe_stream_prefers_websocket(monkeypatch):
    settings = VoiceSettings(
        api_key="test-key",
        stt_model="stt-model",
        tts_model="tts-model",
        voice_id="test-voice",
        endpoint="https://api.elevenlabs.io/v1",
    )

    responses = [
        json.dumps({"type": "partial_transcript", "data": {"text": "hello", "is_final": False}}),
        json.dumps({"type": "transcript", "data": {"text": "hello final", "is_final": True}}),
    ]
    fake_ws = DummyWebSocket(responses)

    captured = {}

    def fake_connect(url: str, *, headers: Dict[str, str]):
        captured["url"] = url
        captured["headers"] = headers
        return fake_ws

    monkeypatch.setattr("backend.utils.voice._connect_websocket", fake_connect)
    monkeypatch.setattr("utils.voice._connect_websocket", fake_connect)
    monkeypatch.setattr("backend.utils.voice.AsyncElevenLabs", FakeAsyncElevenLabs)
    monkeypatch.setattr("utils.voice.AsyncElevenLabs", FakeAsyncElevenLabs)

    async def run() -> None:
        client = ElevenLabsVoiceClient(settings)
        collected: List[Dict[str, str]] = []
        async with client.transcribe_stream(audio=b"abc", audio_format="pcm16", session_id="sess-1") as stream:
            async for chunk in stream:
                collected.append(chunk)

        assert captured["url"].startswith("wss://api.elevenlabs.io")
        assert captured["headers"]["xi-api-key"] == "test-key"
        assert len(fake_ws.sent) == 2  # config + audio bytes
        handshake = json.loads(fake_ws.sent[0].decode())
        assert handshake["session_id"] == "sess-1"
        assert handshake["model_id"] == "stt-model"
        assert handshake["audio_format"] == "pcm16"

        assert collected == [
            {"transcript": "hello", "is_final": False},
            {"transcript": "hello final", "is_final": True},
        ]

    asyncio.run(run())


def test_transcribe_stream_falls_back_to_rest(monkeypatch):
    settings = VoiceSettings(
        api_key="test-key",
        stt_model="stt-model",
        tts_model="tts-model",
        voice_id="test-voice",
    )

    class BrokenWebSocket:
        async def __aenter__(self):  # noqa: D401 - minimal stub
            raise ConnectionError("ws down")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_connect(*args, **kwargs):
        return BrokenWebSocket()

    monkeypatch.setattr("backend.utils.voice._connect_websocket", fake_connect)
    monkeypatch.setattr("utils.voice._connect_websocket", fake_connect)
    monkeypatch.setattr("backend.utils.voice.AsyncElevenLabs", FakeAsyncElevenLabs)
    monkeypatch.setattr("utils.voice.AsyncElevenLabs", FakeAsyncElevenLabs)

    async def run() -> None:
        client = ElevenLabsVoiceClient(settings)
        async with client.transcribe_stream(audio=b"abc", audio_format="pcm16", session_id="sess-1") as stream:
            chunks = [chunk async for chunk in stream]

        assert chunks == [
            {"transcript": "rest fallback transcript", "is_final": True},
        ]

    asyncio.run(run())
