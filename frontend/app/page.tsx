'use client'

import { useState, useEffect, useRef } from 'react'

interface Message {
  id: string
  type: 'user' | 'bot' | 'questions'
  text?: string
  questions?: Array<{field: string; question: string; description: string}>
  payload?: any
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const sendMessage = async () => {
    if (!input.trim()) return
    
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      text: input
    }
    
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    
    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: sessionId
        })
      })
      
      const data = await response.json()
      setSessionId(data.session_id)
      
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: data.needs_clarification ? 'questions' : 'bot',
        text: data.response,
        questions: data.questions,
        payload: data.final_payload
      }
      
      setMessages(prev => [...prev, botMessage])
    } catch (error) {
      console.error('Error:', error)
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        text: 'Sorry, I encountered an error. Please try again.'
      }])
    }
    
    setLoading(false)
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
      
      const botMessage: Message = {
        id: Date.now().toString(),
        type: data.needs_clarification ? 'questions' : 'bot',
        text: data.response,
        questions: data.questions,
        payload: data.final_payload
      }
      
      setMessages(prev => [...prev, botMessage])
      setAnswers({})
    } catch (error) {
      console.error('Error:', error)
    }
    
    setLoading(false)
  }
  
  return (
    <div className="min-h-screen bg-gray-50">
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
              </div>
            )}
            
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-lg rounded-lg p-3 ${
                  msg.type === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {msg.type === 'questions' ? (
                    <div className="space-y-3">
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
                <div className="bg-gray-100 rounded-lg p-3">
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
                className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
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
