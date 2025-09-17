import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import Chat from '../page'

const createFetchMock = () =>
  jest.fn((input: RequestInfo | URL) => {
    const url = input.toString()

    if (url.endsWith('/status')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ mode: 'online', active_sessions: 0 }),
      } as Response)
    }

    if (url.endsWith('/chat')) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            response: 'hello',
            needs_clarification: false,
            questions: null,
            session_id: 'session-123',
            final_payload: null,
            status: 'ok',
            mode: 'online',
          }),
      } as Response)
    }

    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(''),
    } as Response)
  })

describe('Chat feedback', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(global as any).fetch = createFetchMock()
    ;(global as any).EventSource = undefined
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('provides immediate sending feedback in the composer', async () => {
    render(<Chat />)

    const input = screen.getByPlaceholderText(/ask anything/i)
    const sendButton = screen.getByRole('button', { name: /send/i })

    fireEvent.change(input, { target: { value: 'provision a vm' } })
    fireEvent.click(sendButton)

    await waitFor(() => {
      const feedback = screen.getByTestId('composer-feedback')
      expect(feedback).toHaveTextContent(/connecting/i)
    })
  })
})
