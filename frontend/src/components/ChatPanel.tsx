import React, { useState, useRef, useEffect } from 'react'
import { Message } from '../types'
import { Markdown } from './Markdown'

interface Props {
  messages: Message[]
  onSend: (message: string, confirmed: boolean) => void
  awaitingConfirmation: boolean
  loading: boolean
}

export function ChatPanel({ messages, onSend, awaitingConfirmation, loading }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || loading) return
    onSend(input.trim(), false)
    setInput('')
  }

  const handleConfirm = () => {
    onSend('确认执行', true)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const emptyState = messages.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {emptyState ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-xl shadow-sm mb-4">
              O
            </div>
            <h2 className="text-xl font-semibold text-gray-800">开始对话</h2>
            <p className="text-sm text-gray-400 mt-2 max-w-sm">
              查询业务数据、分析风险、仿真决策方案，Agent 将基于 Ontology 执行操作
            </p>
          </div>
        ) : (
          <div className="py-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={`px-4 ${msg.role === 'user' ? 'bg-white' : 'bg-gray-50'}`}>
                <div className="max-w-3xl mx-auto flex gap-4 py-3">
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-white'
                  }`}>
                    {msg.role === 'user' ? 'U' : 'O'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-500 mb-1">
                      {msg.role === 'user' ? '你' : 'OntoPilot'}
                    </div>
                    <div className="text-sm text-gray-800 leading-relaxed">
                      {msg.role === 'user' ? msg.content : <Markdown content={msg.content} />}
                    </div>
                    {msg.awaiting_confirmation && (
                      <div className="mt-3 pt-3 border-t border-yellow-200">
                        <p className="text-xs text-yellow-700 mb-2">需要确认后才能执行此操作</p>
                        <button
                          onClick={handleConfirm}
                          className="px-3 py-1.5 bg-yellow-500 text-white rounded-lg text-xs font-medium hover:bg-yellow-600 transition-colors"
                        >
                          确认执行
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="px-4 bg-gray-50">
                <div className="max-w-3xl mx-auto flex gap-4 py-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-700 text-white flex items-center justify-center text-sm font-bold">
                    O
                  </div>
                  <div className="flex-1">
                    <div className="text-xs font-medium text-gray-500 mb-2">OntoPilot</div>
                    <div className="flex gap-1">
                      <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{animationDelay: '0ms'}} />
                      <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{animationDelay: '150ms'}} />
                      <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{animationDelay: '300ms'}} />
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Confirmation bar (shown when awaiting confirmation from messages) */}
      {!emptyState && awaitingConfirmation && !messages.some(m => m.awaiting_confirmation) && (
        <div className="px-4 py-3 bg-yellow-50 border-t border-yellow-200">
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            <p className="text-sm text-yellow-800">上述操作需要确认</p>
            <button
              onClick={handleConfirm}
              className="px-4 py-1.5 bg-yellow-500 text-white rounded-lg text-sm font-medium hover:bg-yellow-600"
            >
              确认执行
            </button>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t bg-white">
        <div className="max-w-3xl mx-auto p-4">
          <div className="flex items-end gap-2 border border-gray-300 rounded-xl px-4 py-3 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all bg-white">
            <textarea
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入业务问题，例如：查询华南仓所有延迟的货物..."
              className="flex-1 resize-none outline-none text-sm text-gray-800 placeholder-gray-400 bg-transparent max-h-32"
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="flex-shrink-0 px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '...' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
