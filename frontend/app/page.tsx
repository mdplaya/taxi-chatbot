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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const lastGroupRef = useRef<string | null>(null)
  
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  // Question group banner logic
  const businessFields = ['lineOfBusiness', 'id', 'appEnvironment', 'appEnvironmentSubtype', 'costCenter']
  const resourceFields = ['useType', 'os']
  const specialistFields = ['zone', 'machineType']
  const groupLabelFor = (qs: Array<{field: string}> | undefined): string => {
    const fields = (qs || []).map(q => q.field)
    const anyIn = (group: string[]) => fields.some(f => group.includes(f))
    if (anyIn(businessFields)) return 'Business Questions'
    if (anyIn(resourceFields)) return 'Resource Questions'
    if (anyIn(specialistFields)) return 'Resource Specialist Questions'
    return 'Clarification'
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
          message: currentInput,
          session_id: sessionId || ''
        })
        
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
          const group = groupLabelFor(data.questions)
          const msgs: Message[] = []
          if (group && lastGroupRef.current !== group) {
            msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: group })
            lastGroupRef.current = group
          }
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            type: 'questions',
            text: data.response,
            questions: data.questions
          }
          setMessages(prev => [...prev, ...msgs, botMessage])
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
          message: messageText,
          session_id: sessionId
        })
      })
      
      const data = await response.json()
      setSessionId(data.session_id)
      
      // Update mode from response
      if (data.mode) {
        setSystemMode(data.mode)
      }
      
      const group = data.needs_clarification ? groupLabelFor(data.questions) : null
      const msgs: Message[] = []
      if (group && lastGroupRef.current !== group) {
        msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: group })
        lastGroupRef.current = group
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
      
      const group = data.needs_clarification ? groupLabelFor(data.questions) : null
      const msgs: Message[] = []
      if (group && lastGroupRef.current !== group) {
        msgs.push({ id: (Date.now() + 0).toString(), type: 'divider', label: group })
        lastGroupRef.current = group
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
    <div className="min-h-screen bg-gray-50">
      <StatusBadge mode={systemMode} />
      <div className="max-w-4xl mx-auto p-4">
        <div className="bg-white rounded-lg shadow-lg">
          <div className="bg-blue-600 text-white p-4 rounded-t-lg">
            <h1 className="text-2xl font-bold">🚀 TAXI Infrastructure Bot</h1>
            <p className="text-sm opacity-90">Provision VMs across cloud providers</p>
          </div>
          
          <div className="h-[500px] overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-8">
                <p className="text-lg mb-2">Welcome! I can help you provision infrastructure.</p>
                <p className="text-sm">Try: "I want a VM in GCP" or "Create a Linux server for development"</p>
                {systemMode === 'offline' && (
                  <p className="text-xs mt-2 text-yellow-600">
                    Note: Running in offline mode. AI features are disabled.
                  </p>
                )}
              </div>
            )}
            
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-lg rounded-lg p-3 ${
                  msg.type === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {msg.type === 'divider' ? (
                    <div className="text-center">
                      <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider bg-indigo-100 text-indigo-800 px-2 py-1 rounded">
                        {msg.label}
                      </span>
                    </div>
                  ) : msg.type === 'questions' ? (
                    <div className="space-y-3">
                      <div>
                        <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider bg-indigo-100 text-indigo-800 px-2 py-1 rounded">
                          {groupLabelFor(msg.questions)}
                        </span>
                      </div>
                      <p className="font-semibold mb-3">{msg.text}</p>
                      {msg.questions?.map((q, idx) => (
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
                        Submit Answers
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
          
          <div className="p-4 border-t">
            <div className="flex space-x-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !loading && sendMessage()}
                placeholder="Type your message..."
                disabled={loading}
                className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 text-gray-900 bg-white"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </div>
        </div>
        
        {sessionId && (
          <div className="mt-4 text-center text-sm text-gray-600">
            Session ID: {sessionId}
          </div>
        )}
      </div>
    </div>
  )
}
