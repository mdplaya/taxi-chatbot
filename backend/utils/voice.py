import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple, Union

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import File as ElevenLabsFile
from elevenlabs.core.api_error import ApiError
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import VoiceSettings

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MiB safety limit per chunk
DEFAULT_CONTENT_TYPE = "audio/mpeg"
_WS_MAX_MESSAGE_BYTES = 2 * 1024 * 1024
_WS_OPEN_TIMEOUT = 10.0
_WS_CLOSE_TIMEOUT = 5.0
_WS_RECV_TIMEOUT = 30.0


class TranscriptChunk(Dict[str, Any]):
    transcript: str
    is_final: bool


def _ws_endpoint_from_http(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/speech-to-text/stream"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/speech-to-text/stream"
    # already websocket-compatible (e.g. wss://)
    return base + "/speech-to-text/stream"


def _resolve_file_metadata(audio_format: str) -> Tuple[str, str, str]:
    fmt = (audio_format or "").strip().lower()
    if fmt in {"pcm16", "pcm_s16le_16", "pcm", "audio/pcm"}:
        return "pcm_s16le_16", "stream.pcm", "application/octet-stream"
    if fmt in {"audio/wav", "wav", "audio/x-wav"}:
        return "other", "stream.wav", "audio/wav"
    if fmt in {"audio/mpeg", "mp3", "audio/mp3"}:
        return "other", "stream.mp3", "audio/mpeg"
    if fmt.startswith("audio/webm") or fmt.startswith("video/webm"):
        return "other", "stream.webm", "audio/webm"
    if fmt.startswith("audio/ogg") or fmt.startswith("application/ogg"):
        return "other", "stream.ogg", "audio/ogg"
    if fmt.startswith("audio/mp4") or fmt.startswith("video/mp4"):
        return "other", "stream.m4a", "audio/mp4"
    if fmt and fmt.startswith("audio/"):
        return "other", "stream.audio", fmt
    return "other", "stream.bin", "application/octet-stream"


@asynccontextmanager
async def _connect_websocket(url: str, *, headers: Dict[str, str]):
    async with websockets.connect(  # type: ignore[arg-type]
        url,
        additional_headers=headers,
        max_size=_WS_MAX_MESSAGE_BYTES,
        open_timeout=_WS_OPEN_TIMEOUT,
        close_timeout=_WS_CLOSE_TIMEOUT,
    ) as websocket:
        yield websocket


class ElevenLabsVoiceClient:
    """Async ElevenLabs client supporting websocket streaming with REST fallback."""

    def __init__(self, settings: VoiceSettings):
        self.settings = settings
        self._sdk: Optional[AsyncElevenLabs] = None

    def _sdk_client(self) -> AsyncElevenLabs:
        if self._sdk is None:
            self._sdk = AsyncElevenLabs(
                api_key=self.settings.api_key,
                base_url=self._sdk_base_url(),
            )
        return self._sdk

    def _sdk_base_url(self) -> str:
        base = self.settings.endpoint.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        return base

    def _auth_headers(self) -> Dict[str, str]:
        return {"xi-api-key": self.settings.api_key}

    @asynccontextmanager
    async def transcribe_stream(
        self,
        *,
        audio: bytes,
        audio_format: str,
        session_id: str,
    ) -> AsyncIterator[AsyncIterator[TranscriptChunk]]:
        if not audio:
            raise ValueError("Empty audio payload")
        if len(audio) > MAX_AUDIO_BYTES:
            raise ValueError("Audio payload exceeds maximum chunk size")

        try:
            async with self._websocket_stream(
                audio=audio,
                audio_format=audio_format,
                session_id=session_id,
            ) as stream:
                yield stream
                return
        except (WebSocketException, ConnectionClosed, ConnectionError, OSError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning("ElevenLabs websocket streaming failed, falling back to REST: %s", exc)

        async with self._rest_stream(audio=audio, audio_format=audio_format) as stream:
            yield stream

    @asynccontextmanager
    async def _websocket_stream(
        self,
        *,
        audio: bytes,
        audio_format: str,
        session_id: str,
    ) -> AsyncIterator[AsyncIterator[TranscriptChunk]]:
        headers = {
            **self._auth_headers(),
            "x-session-id": session_id,
            "x-audio-format": audio_format,
            "x-model-id": self.settings.stt_model,
        }
        ws_url = _ws_endpoint_from_http(self.settings.endpoint)

        async with _connect_websocket(ws_url, headers=headers) as websocket:
            handshake = json.dumps(
                {
                    "type": "config",
                    "session_id": session_id,
                    "audio_format": audio_format,
                    "model_id": self.settings.stt_model,
                }
            ).encode("utf-8")

            await websocket.send(handshake)
            await websocket.send(audio)

            async def iterator() -> AsyncIterator[TranscriptChunk]:
                while True:
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=_WS_RECV_TIMEOUT)
                    except asyncio.TimeoutError:
                        logger.warning("Timed out waiting for ElevenLabs websocket transcript chunk")
                        break
                    except ConnectionClosed:
                        break
                    if raw is None:
                        break
                    chunk = self._parse_ws_payload(raw)
                    if chunk is None:
                        continue
                    if chunk is False:  # sentinel instructing termination
                        break
                    yield chunk

            try:
                yield iterator()
            finally:
                await websocket.close()

    @asynccontextmanager
    async def _rest_stream(
        self,
        *,
        audio: bytes,
        audio_format: str,
    ) -> AsyncIterator[AsyncIterator[TranscriptChunk]]:
        sdk = self._sdk_client()

        file_format, filename, content_type = _resolve_file_metadata(audio_format)
        file_payload: ElevenLabsFile = (filename, audio, content_type)
        segments: List[TranscriptChunk]
        try:
            response = await sdk.speech_to_text.convert(
                model_id=self.settings.stt_model,
                file=file_payload,
                file_format=file_format,
            )
        except ApiError as exc:
            detail = ""
            status = ""
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                payload = body.get("detail")
                if isinstance(payload, dict):
                    status = str(payload.get("status") or "")
                    detail = payload.get("message") or status
                elif isinstance(payload, str):
                    detail = payload
            message = f"ElevenLabs speech-to-text request failed with status {exc.status_code}"
            if detail:
                message = f"{message}: {detail}"
            if status == "invalid_content":
                logger.warning("ElevenLabs rejected audio chunk: %s", detail or "invalid content")
                segments = [{"transcript": "", "is_final": True}]
            else:
                raise RuntimeError(message) from exc
        else:
            segments = self._normalize_rest_response(response)

        async def iterator() -> AsyncIterator[TranscriptChunk]:
            for segment in segments:
                yield segment

        yield iterator()

    def _parse_ws_payload(self, payload: Any) -> Optional[Union[TranscriptChunk, bool]]:  # noqa: ANN401
        data: Any = payload
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                logger.debug("Ignoring non-text websocket payload from ElevenLabs")
                return None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.debug("Ignoring invalid JSON websocket payload from ElevenLabs")
                return None

        if not isinstance(data, dict):
            return None

        message_type = data.get("type")
        if message_type == "close":
            return False
        if message_type == "error":
            error_detail = data.get("error") or data
            raise ValueError(f"ElevenLabs websocket error: {error_detail}")

        if message_type in {"transcript", "partial_transcript", None}:
            body = data.get("data") if isinstance(data.get("data"), dict) else data
            transcript = (body.get("transcript") or body.get("text") or "").strip()
            if not transcript:
                return None
            is_final = bool(body.get("is_final")) or message_type == "transcript"
            return {"transcript": transcript, "is_final": is_final}

        return None

    def _normalize_rest_response(self, response: Any) -> List[TranscriptChunk]:  # noqa: ANN401
        segments: List[TranscriptChunk] = []

        raw_segments: Optional[Iterable[Any]] = getattr(response, "segments", None)
        if raw_segments:
            for segment in raw_segments:
                text = (
                    getattr(segment, "transcript", None)
                    or getattr(segment, "text", None)
                    or (segment.get("transcript") if isinstance(segment, dict) else None)
                    or (segment.get("text") if isinstance(segment, dict) else None)
                    or ""
                ).strip()
                if not text:
                    continue
                is_final = bool(
                    getattr(segment, "is_final", False)
                    if not isinstance(segment, dict)
                    else segment.get("is_final", False)
                )
                segments.append({"transcript": text, "is_final": is_final})

        text = getattr(response, "text", None) or (response.get("text") if isinstance(response, dict) else None)
        if text:
            segments.append({"transcript": str(text).strip(), "is_final": True})

        if not segments:
            segments.append({"transcript": "", "is_final": True})

        return segments

    async def synthesize_speech(
        self,
        *,
        text: str,
        voice_options: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        if not text:
            raise ValueError("Cannot synthesize empty text")

        sdk = self._sdk_client()

        kwargs: Dict[str, Any] = {"model_id": self.settings.tts_model}
        if voice_options:
            allowed = {
                "voice_settings",
                "optimize_streaming_latency",
                "output_format",
                "language_code",
                "seed",
                "previous_text",
                "next_text",
            }
            for key in allowed:
                if key in voice_options:
                    kwargs[key] = voice_options[key]

        stream = sdk.text_to_speech.convert(
            self.settings.voice_id,
            text=text,
            **kwargs,
        )

        chunks: List[bytes] = []
        async for chunk in stream:
            if chunk:
                chunks.append(chunk)

        if not chunks:
            raise RuntimeError("ElevenLabs returned no audio data")

        return b"".join(chunks)
