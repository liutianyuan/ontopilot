import React, { useState } from 'react'
import { TraceEvent } from '../types'

const LAYER_ICON: Record<string, string> = {
  context: '🏢',
  query: '🔍',
  logic: '⚙️',
  action: '⚡',
  governance: '🛡️',
  simulation: '🔬',
  response: '💬',
}

const STATUS_COLOR: Record<string, string> = {
  success: 'text-green-600',
  pass: 'text-green-600',
  pending_confirmation: 'text-yellow-600',
  denied: 'text-red-600',
  failed: 'text-red-600',
}

interface Props {
  events: TraceEvent[]
}

export function TracePanel({ events }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (events.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        发送消息后，推理过程将在此显示
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-2">
      {events.map(event => (
        <div key={event.id} className="border rounded-lg overflow-hidden">
          <button
            onClick={() => toggle(event.id)}
            className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-left"
          >
            <span className="flex items-center gap-2 text-sm">
              <span>{LAYER_ICON[event.layer] || '•'}</span>
              <span className="font-medium text-gray-700">{event.name}</span>
              <span className={`text-xs ${STATUS_COLOR[event.status] || 'text-gray-500'}`}>
                {event.status}
              </span>
            </span>
            <span className="text-xs text-gray-400">{event.duration_ms}ms</span>
          </button>
          {expanded.has(event.id) && (
            <div className="px-3 py-2 text-xs bg-white space-y-1">
              <div>
                <span className="text-gray-500">输入: </span>
                <code className="text-gray-700">{JSON.stringify(event.input_summary, null, 2)}</code>
              </div>
              <div>
                <span className="text-gray-500">输出: </span>
                <code className="text-gray-700">{JSON.stringify(event.output_summary, null, 2)}</code>
              </div>
              {event.audit_id && (
                <div className="text-gray-400">审计ID: {event.audit_id}</div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
