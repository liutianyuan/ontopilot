import { useEffect, useRef, useCallback } from 'react'
import { TraceEvent } from '../types'

export function useSSE(sessionId: string | null, onEvent: (event: TraceEvent) => void) {
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!sessionId) return
    // Close old connection if any
    if (esRef.current) {
      esRef.current.close()
    }
    const es = new EventSource(`/api/chat/stream?session_id=${sessionId}`)
    esRef.current = es
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        // Keepalive pings — ignore
        if (data.type === 'keepalive') return
        // End-of-turn — ignore (stream stays alive for next turn)
        if (data.__end_of_turn__) return
        onEvent(data as TraceEvent)
      } catch {
        // ignore parse errors
      }
    }
    es.onerror = () => {
      // Browser will auto-reconnect EventSource on error
    }
  }, [sessionId, onEvent])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
    }
  }, [connect])
}
