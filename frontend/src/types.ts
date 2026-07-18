export interface TraceEvent {
  id: string
  conversation_id: string
  turn_id: string
  timestamp: string
  layer: 'context' | 'query' | 'logic' | 'action' | 'governance' | 'simulation' | 'response'
  name: string
  status: 'started' | 'success' | 'failed' | 'denied' | 'pending_confirmation'
  input_summary: Record<string, unknown>
  output_summary: Record<string, unknown>
  permission_result: 'pass' | 'deny' | 'not_applicable'
  duration_ms: number
  audit_id: string | null
  error: string | null
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  awaiting_confirmation?: boolean
}

export interface OntologyProperty {
  name: string
  type: string
  description: string
}

export interface OntologyLink {
  name: string
  target: string
}

export interface OntologyObjectType {
  name: string
  description: string
  properties: OntologyProperty[]
  links: OntologyLink[]
}

export interface OntologyDetail {
  object_types: OntologyObjectType[]
  actions: { name: string; params: string[]; description: string }[]
  functions: { name: string; params: string[]; description: string }[]
  tools: string[]
}
