import { MutableRefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react'

type VoiceResponseEventDetail = {
  transcript: string
  audioBase64: string
  contentType: string
}

type VoiceSessionOptions = {
  apiUrl: string
  sessionId: string | null
  onTranscript?: (transcript: string, isFinal: boolean) => void
  onFinalResponse?: (response: any) => void
}

type VoiceSessionState = {
  voiceEnabled: boolean
  isRecording: boolean
  error: string | null
  transcript: string
  toggleVoice: () => Promise<void>
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearError: () => void
  audioRef: MutableRefObject<HTMLAudioElement | null>
}

const DATA_PREFIX = 'data:'

const blobToArrayBuffer = (blob: Blob): Promise<ArrayBuffer> => {
  if (typeof (blob as any).arrayBuffer === 'function') {
    return (blob as any).arrayBuffer()
  }
  return new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error || new Error('Failed to read blob'))
    reader.readAsArrayBuffer(blob)
  })
}

export function useVoiceSession({ apiUrl, sessionId, onTranscript, onFinalResponse }: VoiceSessionOptions): VoiceSessionState {
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState('')
  const [voiceSessionId, setVoiceSessionId] = useState<string | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const bufferedChunksRef = useRef<Blob[]>([])
  const lastChunkTypeRef = useRef<string>('')
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const ensureVoiceSession = useCallback(async () => {
    const payload = sessionId ? { session_id: sessionId } : {}
    const response = await fetch(`${apiUrl}/voice/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({ detail: 'Voice session failed' }))
      throw new Error(data.detail || 'Voice session failed')
    }
    const data = await response.json()
    setVoiceSessionId(data.session_id)
    return data.session_id as string
  }, [apiUrl, sessionId])

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    setIsRecording(false)
  }, [])

  const cleanupStream = useCallback(() => {
    const stream = mediaStreamRef.current
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }
    stopRecording()
    setVoiceEnabled(false)
    bufferedChunksRef.current = []
    lastChunkTypeRef.current = ''
  }, [stopRecording])

  const playAudio = useCallback((detail: VoiceResponseEventDetail) => {
    if (!detail.audioBase64 || !audioRef.current) return
    const src = detail.audioBase64.startsWith(DATA_PREFIX)
      ? detail.audioBase64
      : `${DATA_PREFIX}${detail.contentType};base64,${detail.audioBase64}`
    audioRef.current.src = src
    audioRef.current.currentTime = 0
    audioRef.current.play().catch(() => {})
  }, [])

  useEffect(() => {
    const onVoiceResponse = (event: Event) => {
      const custom = event as CustomEvent<VoiceResponseEventDetail>
      playAudio(custom.detail)
    }
    window.addEventListener('voice-response', onVoiceResponse)
    return () => {
      window.removeEventListener('voice-response', onVoiceResponse)
    }
  }, [playAudio])

  const toggleVoice = useCallback(async () => {
    if (voiceEnabled) {
      cleanupStream()
      return
    }
    try {
      setError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      await ensureVoiceSession()
      setVoiceEnabled(true)
    } catch (err: any) {
      cleanupStream()
      setError(err?.message?.toLowerCase().includes('denied') ? 'Microphone access denied' : 'Unable to access microphone')
    }
  }, [voiceEnabled, cleanupStream, ensureVoiceSession])

  const dispatchVoiceResponseEvent = useCallback((detail: VoiceResponseEventDetail) => {
    const event = new CustomEvent<VoiceResponseEventDetail>('voice-response', { detail })
    window.dispatchEvent(event)
  }, [])

  const sendVoiceTranscript = useCallback(async (text: string) => {
    try {
      const response = await fetch(`${apiUrl}/voice/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: voiceSessionId || sessionId,
          text,
        }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Voice response failed' }))
        throw new Error(data.detail || 'Voice response failed')
      }
      const payload = await response.json()
      dispatchVoiceResponseEvent({
        transcript: text,
        audioBase64: payload.audio_base64,
        contentType: payload.content_type,
      })
      onFinalResponse?.(payload)
    } catch (err: any) {
      console.error('Voice response error', err)
      setError('Unable to generate spoken response')
    }
  }, [apiUrl, dispatchVoiceResponseEvent, onFinalResponse, sessionId, voiceSessionId])

  const processChunk = useCallback(async (blob: Blob) => {
    if (!voiceSessionId && !sessionId) return
    const sid = voiceSessionId || sessionId
    try {
      const arrayBuffer = await blobToArrayBuffer(blob)
      const response = await fetch(`${apiUrl}/voice/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'x-session-id': sid || '',
          'x-audio-format': blob.type || 'webm',
        },
        body: arrayBuffer,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Transcription failed' }))
        throw new Error(data.detail || 'Transcription failed')
      }
      const data = await response.json()
      if (data.transcript) {
        setTranscript(data.transcript)
        onTranscript?.(data.transcript, data.is_final)
        if (data.is_final) {
          await sendVoiceTranscript(data.transcript)
        }
      }
    } catch (err: any) {
      console.error('Voice stream error', err)
      setError('Unable to transcribe audio')
    }
  }, [apiUrl, onTranscript, sendVoiceTranscript, sessionId, voiceSessionId])

  const startRecording = useCallback(async () => {
    if (!voiceEnabled) {
      await toggleVoice()
    }
    if (!mediaStreamRef.current) {
      setError('Microphone not initialized')
      return
    }
    if (!voiceSessionId && !sessionId) {
      try {
        await ensureVoiceSession()
      } catch (err) {
        setError((err as Error).message)
        return
      }
    }
    if (typeof MediaRecorder === 'undefined') {
      // MediaRecorder not supported (e.g., tests). Treat as no-op but surface state changes.
      setIsRecording(true)
      return
    }
    try {
      bufferedChunksRef.current = []
      lastChunkTypeRef.current = ''
      const recorder = new MediaRecorder(mediaStreamRef.current)
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          bufferedChunksRef.current.push(event.data)
          if (!lastChunkTypeRef.current && event.data.type) {
            lastChunkTypeRef.current = event.data.type
          }
        }
      }
      recorder.onstop = async () => {
        setIsRecording(false)
        try {
          if (!bufferedChunksRef.current.length) {
            return
          }
          const type = lastChunkTypeRef.current || (bufferedChunksRef.current[0]?.type || 'audio/webm')
          const combined = new Blob(bufferedChunksRef.current, { type })
          bufferedChunksRef.current = []
          lastChunkTypeRef.current = ''
          await processChunk(combined)
        } finally {
          bufferedChunksRef.current = []
          lastChunkTypeRef.current = ''
        }
      }
      mediaRecorderRef.current = recorder
      recorder.start(500)
      setIsRecording(true)
    } catch (err: any) {
      console.error('Recorder error', err)
      setError('Unable to start recording')
    }
  }, [ensureVoiceSession, processChunk, sessionId, toggleVoice, voiceEnabled, voiceSessionId])

  const clearError = useCallback(() => setError(null), [])

  useEffect(() => {
    return () => {
      cleanupStream()
    }
  }, [cleanupStream])

  return useMemo(() => ({
    voiceEnabled,
    isRecording,
    error,
    transcript,
    toggleVoice,
    startRecording,
    stopRecording,
    clearError,
    audioRef,
  }), [audioRef, clearError, error, isRecording, startRecording, stopRecording, toggleVoice, transcript, voiceEnabled])
}

export type VoiceSessionHook = ReturnType<typeof useVoiceSession>
