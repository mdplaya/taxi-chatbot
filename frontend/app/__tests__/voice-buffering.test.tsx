import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import Chat from '../page'

const createFetchMock = () =>
  jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString()

    if (url.endsWith('/status')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ mode: 'online', active_sessions: 0 }),
      } as Response)
    }

    if (url.endsWith('/voice/session')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ session_id: 'voice-session-1' }),
      } as Response)
    }

    if (url.endsWith('/voice/stream')) {
      const body = init?.body as Uint8Array
      const size = body?.byteLength ?? 0
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            session_id: 'voice-session-1',
            transcript: size > 2000 ? 'this is a test' : '(background noise)',
            is_final: true,
          }),
      } as Response)
    }

    if (url.endsWith('/voice/respond')) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            session_id: 'voice-session-1',
            text: 'confirmed',
            audio_base64: 'dGVzdA==',
            content_type: 'audio/mpeg',
            created_at: new Date().toISOString(),
            chat: {
              response: 'confirmed',
              needs_clarification: false,
              questions: null,
              session_id: 'voice-session-1',
              final_payload: null,
              status: 'ok',
              mode: 'online',
            },
          }),
      } as Response)
    }

    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response)
  })

describe('Voice buffering', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(global as any).fetch = createFetchMock()
    ;(global as any).EventSource = undefined
    jest
      .spyOn(window.HTMLMediaElement.prototype, 'play')
      .mockImplementation(() => Promise.resolve())

    navigator.mediaDevices = {
      getUserMedia: jest.fn().mockResolvedValue({
        getTracks: () => [{ stop: jest.fn() }],
      }),
    } as any

    ;(window as any).MediaRecorder = class {
      private readonly stream: MediaStream
      private handler: ((event: { data: Blob }) => void) | null = null
      private stopHandler: (() => void) | null = null
      private readonly chunk = new Blob([new Uint8Array(3000).fill(1)], { type: 'audio/webm' })

      constructor(stream: MediaStream) {
        this.stream = stream
      }

      start() {
        setTimeout(() => {
          this.handler?.({ data: this.chunk })
          this.stopHandler?.()
        }, 10)
      }

      stop() {
        this.stopHandler?.()
      }

      set ondataavailable(handler: (event: { data: Blob }) => void) {
        this.handler = handler
      }

      get ondataavailable() {
        return this.handler
      }

      set onstop(handler: () => void) {
        this.stopHandler = handler
      }

      get onstop() {
        return this.stopHandler
      }
    }
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('sends buffered audio chunks once recording stops', async () => {
    render(<Chat />)

    const voiceButton = await screen.findByRole('button', { name: /voice mode/i })
    fireEvent.click(voiceButton)

    const recordButton = await screen.findByRole('button', { name: /start recording/i })
    fireEvent.click(recordButton)

    const transcriptMatches = await screen.findAllByText(/this is a test/i)
    expect(transcriptMatches.length).toBeGreaterThanOrEqual(1)
  })
})
