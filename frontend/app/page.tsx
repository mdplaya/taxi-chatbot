'use client'

import { useState, useEffect, useRef } from 'react'

interface Message {
  id: string
  type: 'user' | 'bot' | 'questions' | 'divider'
  text?: string
  questions?: Array<{field: string; question: string; description: string}>
  payload?: any
  label?: string
}

// Status Badge Component
function StatusBadge({ mode }: { mode: 'online' | 'offline' | null }) {
  if (!mode) return null
  
  return (
    <div 
      className={`fixed top-4 right-4 px-3 py-1 rounded-full text-sm font-medium shadow-lg z-50 ${
        mode === 'online' 
          ? 'bg-green-100 text-green-800 border border-green-200'
          : 'bg-yellow-100 text-yellow-800 border border-yellow-200'
      }`}
      title={mode === 'online' 
        ? 'AI-powered responses enabled' 
        : 'Using pattern-based responses (AI unavailable)'
      }
    >
      <div className="flex items-center space-x-2">
        <div className={`w-2 h-2 rounded-full ${
          mode === 'online' ? 'bg-green-500' : 'bg-yellow-500'
        } animate-pulse`}></div>
        <span>{mode === 'online' ? 'ONLINE' : 'OFFLINE'}</span>
      </div>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [systemMode, setSystemMode] = useState<'online' | 'offline' | null>(null)
  const [progressMessage, setProgressMessage] = useState<string>('')
  const [progressPercentage, setProgressPercentage] = useState<number>(0)
  const [provider, setProvider] = useState<'gcp' | 'azure' | 'onprem' | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const lastGroupRef = useRef<string | null>(null)
  
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  // Question group banner logic
  const businessFields = ['lineOfBusiness', 'id', 'appEnvironment', 'appEnvironmentSubtype', 'costCenter']
  const resourceFields = ['useType', 'os']
  const specialistFields = ['zone', 'machineType']

  type GroupMeta = { key: 'business' | 'resource' | 'specialist' | 'other'; label: string; bg: string; text: string; tooltip: string }

  const groupMetaFor = (qs: Array<{field: string}> | undefined): GroupMeta => {
    const fields = (qs || []).map(q => q.field)
    const anyIn = (group: string[]) => fields.some(f => group.includes(f))
    if (anyIn(businessFields)) {
      return {
        key: 'business',
        label: 'Business Questions',
        bg: 'bg-amber-100',
        text: 'text-amber-900',
        tooltip: 'Business context: line of business, requestor email, environment, and cost center.'
      }
    }
    if (anyIn(resourceFields)) {
      return {
        key: 'resource',
        label: 'Resource Questions',
        bg: 'bg-blue-100',
        text: 'text-blue-900',
        tooltip: 'Resource details: how the VM will be used and the operating system.'
      }
    }
    if (anyIn(specialistFields)) {
      return {
        key: 'specialist',
        label: 'Resource Specialist Questions',
        bg: 'bg-purple-100',
        text: 'text-purple-900',
        tooltip: 'Cloud-specific details: target zone and GCP machine type.'
      }
    }
    return { key: 'other', label: 'Clarification', bg: 'bg-gray-100', text: 'text-gray-900', tooltip: 'Additional details to proceed.' }
  }
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])
  
  // Check system status on mount
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/status`)
        const data = await response.json()
        setSystemMode(data.mode)
      } catch (error) {
        console.error('Error checking status:', error)
      }
    }
    checkStatus()
    
    // Recheck every 30 seconds
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [API_URL])
  
  // Append provider hint when GCP is toggled and no provider is mentioned
  const withProviderHint = (text: string): string => {
    if (!provider) return text
    const t = (text || '').toLowerCase()
    const mentionsProvider = [
      'gcp', 'google cloud', 'google', 'gce',
      'aws', 'amazon', 'ec2',
      'azure', 'microsoft',
      'on-prem', 'onprem', 'datacenter', 'vmware'
    ].some(k => t.includes(k))
    if (mentionsProvider) return text
    if (provider === 'gcp') return text.trim().length ? `${text.trim()} in GCP` : 'in GCP'
    if (provider === 'azure') return text.trim().length ? `${text.trim()} in Azure` : 'in Azure'
    if (provider === 'onprem') return text.trim().length ? `${text.trim()} on-prem` : 'on-prem'
    return text
  }

  const sendMessage = async () => {
    if (!input.trim()) return
    
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      text: input
    }
    
    const currentInput = input
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setProgressMessage('Connecting...')
    setProgressPercentage(0)
    
    // Check if SSE is supported
    const useSSE = typeof EventSource !== 'undefined'
    
    if (useSSE) {
      // Use SSE for real-time updates
      try {
        // Close any existing connection
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
        }
        
        // Create SSE connection
        const params = new URLSearchParams({
          message: withProviderHint(currentInput),
          session_id: sessionId || ''
        } as any)
        if (provider) params.set('provider', provider)
        
        const eventSource = new EventSource(`${API_URL}/chat/stream?${params}`)
        eventSourceRef.current = eventSource
        
        eventSource.addEventListener('connected', (event) => {
          const data = JSON.parse(event.data)
          setSessionId(data.session_id)
          setSystemMode(data.mode)
        })
        
        eventSource.addEventListener('progress', (event) => {
          const data = JSON.parse(event.data)
          setProgressMessage(data.message || 'Processing...')
          if (data.percentage !== undefined) {
            setProgressPercentage(data.percentage)
          }
        })
        
        eventSource.addEventListener('clarification', (event) => {
          const data = JSON.parse(event.data)
          const meta = groupMetaFor(data.questions)
          const msgs: Message[] = []
          if (meta.label && lastGroupRef.current !== meta.label) {
            msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: meta.label })
            lastGroupRef.current = meta.label
          }
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            type: 'questions',
            text: data.response,
            questions: data.questions
          }
          setMessages(prev => [...prev, ...msgs, botMessage])
          setAnswers({})
          setLoading(false)
          eventSource.close()
        })
        
        eventSource.addEventListener('complete', (event) => {
          const data = JSON.parse(event.data)
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            type: 'bot',
            text: data.response,
            payload: data.final_payload
          }
          setMessages(prev => [...prev, botMessage])
          setLoading(false)
          eventSource.close()
        })
        
        eventSource.addEventListener('error', (event: any) => {
          console.error('SSE Error:', event)
          if (event.data) {
            const data = JSON.parse(event.data)
            setMessages(prev => [...prev, {
              id: (Date.now() + 1).toString(),
              type: 'bot',
              text: `Error: ${data.error || 'Connection failed'}`
            }])
          }
          setLoading(false)
          eventSource.close()
        })
        
        eventSource.onerror = () => {
          // Fallback to regular fetch if SSE fails
          sendMessageFallback(currentInput)
          eventSource.close()
        }
        
      } catch (error) {
        console.error('SSE Error:', error)
        // Fallback to regular fetch
        sendMessageFallback(currentInput)
      }
    } else {
      // Use regular fetch as fallback
      sendMessageFallback(currentInput)
    }
  }
  
  const sendMessageFallback = async (messageText: string) => {
    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: withProviderHint(messageText),
          session_id: sessionId,
          context: provider ? { provider } : undefined
        })
      })
      
      const data = await response.json()
      setSessionId(data.session_id)
      
      // Update mode from response
      if (data.mode) {
        setSystemMode(data.mode)
      }
      
      const meta = data.needs_clarification ? groupMetaFor(data.questions) : null
      const msgs: Message[] = []
      if (meta && meta.label && lastGroupRef.current !== meta.label) {
        msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: meta.label })
        lastGroupRef.current = meta.label
      }
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: data.needs_clarification ? 'questions' : 'bot',
        text: data.response,
        questions: data.questions,
        payload: data.final_payload
      }

      setMessages(prev => [...prev, ...msgs, botMessage])
    } catch (error) {
      console.error('Error:', error)
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        text: 'Sorry, I encountered an error. Please try again.'
      }])
    } finally {
      setLoading(false)
      setProgressMessage('')
      setProgressPercentage(0)
    }
  }
  
  const submitAnswers = async () => {
    setLoading(true)
    
    try {
      const response = await fetch(`${API_URL}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          answers: answers
        })
      })
      
      const data = await response.json()
      
      // Update mode from response
      if (data.mode) {
        setSystemMode(data.mode)
      }
      
      const meta = data.needs_clarification ? groupMetaFor(data.questions) : null
      const msgs: Message[] = []
      if (meta && meta.label && lastGroupRef.current !== meta.label) {
        msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: meta.label })
        lastGroupRef.current = meta.label
      }
      const botMessage: Message = {
        id: Date.now().toString(),
        type: data.needs_clarification ? 'questions' : 'bot',
        text: data.response,
        questions: data.questions,
        payload: data.final_payload
      }

      setMessages(prev => [...prev, ...msgs, botMessage])
      setAnswers({})
    } catch (error) {
      console.error('Error:', error)
    }
    
    setLoading(false)
  }
  
  return (
    <div className="min-h-screen bg-white">
      <StatusBadge mode={systemMode} />
      <div className="max-w-4xl mx-auto p-4">
        <div className="bg-white rounded-lg shadow-sm">
          {/* Removed blue header bar */}
          
          <div className={`h-[500px] overflow-y-auto p-4 space-y-4 ${messages.length > 0 ? 'pb-[35vh]' : 'pb-40'}` }>
            {/* Message stream only; chat input rendered below */}
            {false && null}
            
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-lg rounded-lg p-3 ${
                  msg.type === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {msg.type === 'divider' ? (
                    <div className="text-center">
                      <span
                        className={`text-[10px] sm:text-xs font-semibold uppercase tracking-wider px-2 py-1 rounded ${
                          msg.label?.startsWith('Business') ? 'bg-amber-100 text-amber-900' :
                          msg.label?.startsWith('Resource Specialist') ? 'bg-purple-100 text-purple-900' :
                          msg.label?.startsWith('Resource') ? 'bg-blue-100 text-blue-900' : 'bg-gray-100 text-gray-900'
                        }`}
                        title={msg.label?.startsWith('Business')
                          ? 'Business context: line of business, requestor email, environment, and cost center.'
                          : msg.label?.startsWith('Resource Specialist')
                          ? 'Cloud-specific details: target zone and GCP machine type.'
                          : msg.label?.startsWith('Resource')
                          ? 'Resource details: how the VM will be used and the operating system.'
                          : 'Additional details to proceed.'}
                      >
                        {msg.label}
                      </span>
                    </div>
                  ) : msg.type === 'questions' ? (
                    <div className="space-y-3 animate-in fade-in-50 slide-in-from-bottom-2 duration-300">
                      {(() => {
                        const shown = msg.questions && msg.questions.length ? [msg.questions[0]] : []
                        const meta = groupMetaFor(shown)
                        return (
                          <div>
                            <span
                              className={`text-[10px] sm:text-xs font-semibold uppercase tracking-wider px-2 py-1 rounded ${meta.bg} ${meta.text}`}
                              title={meta.tooltip}
                            >
                              {meta.label}
                            </span>
                          </div>
                        )
                      })()}
                      <p className="font-semibold mb-3">{msg.text}</p>
                      {(msg.questions && msg.questions.length ? [msg.questions[0]] : []).map((q, idx) => (
                        <div key={idx} className="space-y-1">
                          <label className="block text-sm font-medium">
                            {q.question}
                          </label>
                          <input
                            type="text"
                            className="w-full px-3 py-2 border rounded-md text-sm"
                            placeholder={q.description}
                            onChange={(e) => setAnswers({...answers, [q.field]: e.target.value})}
                          />
                        </div>
                      ))}
                      <button
                        onClick={submitAnswers}
                        disabled={loading}
                        className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
                      >
                        Submit Answer
                      </button>
                    </div>
                  ) : (
                    <>
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                      {msg.payload && (
                        <details className="mt-2">
                          <summary className="cursor-pointer text-sm font-semibold">
                            View TAXI Payload
                          </summary>
                          <pre className="mt-2 text-xs overflow-x-auto bg-gray-800 text-white p-2 rounded">
                            {JSON.stringify(msg.payload, null, 2)}
                          </pre>
                        </details>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg p-3 max-w-md">
                  {progressMessage && (
                    <div className="mb-2">
                      <div className="text-sm text-gray-600 mb-1">{progressMessage}</div>
                      {progressPercentage > 0 && (
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                            style={{width: `${progressPercentage}%`}}
                          ></div>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
        
        {sessionId && (
          <div className="mt-4 text-center text-sm text-gray-600">
            Session ID: {sessionId}
          </div>
        )}
      </div>
      {/* Fixed overlay chatbox independent of inner scroll */}
      <div className={`fixed left-0 right-0 ${messages.length > 0 ? 'top-[75vh] translate-y-0' : 'top-1/2 -translate-y-1/2'}
        border-t bg-gradient-to-t from-white/95 to-white/60 backdrop-blur supports-[backdrop-filter]:bg-white/70
        shadow-[0_-24px_64px_rgba(0,0,0,0.18)] transition-all duration-500 ease-out will-change-[top,transform]`}>
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex flex-col items-center gap-2">
            <h1 className="text-xl font-semibold">TAXI Infrastructure Bot</h1>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setProvider(prev => (prev === 'gcp' ? null : 'gcp'))}
                className={`px-3 py-1 rounded-full text-sm border inline-flex items-center gap-2 transition-colors ${
                  provider === 'gcp' ? 'bg-green-600 text-white border-green-600' : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
                }`}
                title={provider === 'gcp' ? 'GCP selected. Click to unset.' : 'Deploy to Google Cloud Platform'}
              >
                <span className="w-2 h-2 rounded-full bg-current"></span>
                GCP
              </button>
              <button
                type="button"
                onClick={() => setProvider(prev => (prev === 'azure' ? null : 'azure'))}
                className={`px-3 py-1 rounded-full text-sm border inline-flex items-center gap-2 transition-colors ${
                  provider === 'azure' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
                }`}
                title={provider === 'azure' ? 'Azure selected. Click to unset.' : 'Deploy to Microsoft Azure'}
              >
                Azure
              </button>
              <button
                type="button"
                onClick={() => setProvider(prev => (prev === 'onprem' ? null : 'onprem'))}
                className={`px-3 py-1 rounded-full text-sm border inline-flex items-center gap-2 transition-colors ${
                  provider === 'onprem' ? 'bg-gray-700 text-white border-gray-700' : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
                }`}
                title={provider === 'onprem' ? 'On‑Prem selected. Click to unset.' : 'Deploy to On‑Prem'}
              >
                OnPrem
              </button>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-[640px]">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !loading && sendMessage()}
                placeholder="Ask anything"
                disabled={loading}
                className="flex-1 px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-300 text-gray-900"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="px-4 py-2 rounded-xl bg-gray-900 text-white hover:bg-black disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
