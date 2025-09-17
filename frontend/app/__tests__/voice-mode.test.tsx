import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import Chat from '../page'

declare global {
  interface Navigator {
    mediaDevices: {
      getUserMedia: jest.Mock
    }
  }
}

const createFetchMock = () => {
  return jest.fn((input: RequestInfo | URL) => {
    const url = input.toString()
    if (url.endsWith('/status')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ mode: 'online', active_sessions: 0 }),
      } as Response)
    }
    if (url.includes('/voice/session')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ session_id: 'voice-123' }),
      } as Response)
    }
    if (url.includes('/voice/stream')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ session_id: 'voice-123', transcript: 'hello', is_final: false }),
      } as Response)
    }
    if (url.includes('/voice/respond')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          session_id: 'voice-123',
          text: 'hello',
          audio_base64: 'dGVzdA==',
          content_type: 'audio/mpeg',
          created_at: new Date().toISOString(),
          chat: {
            response: 'hello',
            needs_clarification: false,
            questions: null,
            session_id: 'voice-123',
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
      text: () => Promise.resolve(''),
    } as Response)
  })
}

describe('Voice mode UI', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(global as any).fetch = createFetchMock()
    navigator.mediaDevices = {
      getUserMedia: jest.fn().mockResolvedValue({
        getTracks: () => [{ stop: jest.fn() }],
      }),
    } as any
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders voice controls when feature enabled', async () => {
    render(<Chat />)

    expect(await screen.findByRole('button', { name: /voice mode/i })).toBeInTheDocument()
  })

  it('handles microphone permission denial gracefully', async () => {
    navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(new Error('denied'))

    render(<Chat />)

    const voiceButton = await screen.findByRole('button', { name: /voice mode/i })
    fireEvent.click(voiceButton)

    expect(await screen.findByText(/microphone access denied/i)).toBeInTheDocument()
  })

  it('plays synthesized audio when backend responds', async () => {
    const playMock = jest
      .spyOn(window.HTMLMediaElement.prototype, 'play')
      .mockImplementation(() => Promise.resolve())

    render(<Chat />)

    await screen.findByRole('button', { name: /voice mode/i })

    const fakeEvent = new CustomEvent('voice-response', {
      detail: {
        transcript: 'test words',
        audioBase64: 'dGVzdA==',
        contentType: 'audio/mpeg',
      },
    })
    window.dispatchEvent(fakeEvent)

    await waitFor(() => {
      expect(playMock).toHaveBeenCalled()
    })
  })
})
