import React, { useState, useCallback, useEffect } from 'react'
import { ChatPanel } from './components/ChatPanel'
import { TracePanel } from './components/TracePanel'
import { OntologyGraphPanel } from './components/OntologyGraphPanel'
import { Sidebar, ViewType } from './components/Sidebar'
import { ModelConfigPanel } from './components/ModelConfigPanel'
import { OntologyConfigPanel } from './components/OntologyConfigPanel'
import { UserManagement } from './components/UserManagement'
import { WelcomePage } from './components/WelcomePage'
import { LoginPage } from './components/LoginPage'
import { useSSE } from './hooks/useSSE'
import { Message, TraceEvent } from './types'

interface LoginUser {
  id: string
  username: string
  role: string
  display_name: string
  warehouse?: string
  userId?: string
}

interface ModelOption {
  id: string
  name: string
  provider: string
}

interface OntologyOption {
  id: string
  name: string
}

interface SessionSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  user_id: string
  role: string
}

export default function App() {
  const [user, setUser] = useState<LoginUser | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false)
  const [activeView, setActiveView] = useState<ViewType>('chat')
  const [rightPanel, setRightPanel] = useState<'trace' | 'ontology' | null>(null)
  const [startedChat, setStartedChat] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showWelcome, setShowWelcome] = useState(true)
  const [models, setModels] = useState<ModelOption[]>([])
  const [ontologies, setOntologies] = useState<OntologyOption[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [selectedOntology, setSelectedOntology] = useState<string>('')

  const showLanding = showWelcome && activeView === 'chat'

  const handleLogin = (loggedInUser: LoginUser) => {
    setUser(loggedInUser)
  }

  const handleLogout = () => {
    setUser(null)
    setSessionId(null)
    setMessages([])
    setTraceEvents([])
    setAwaitingConfirmation(false)
    setStartedChat(false)
    setShowWelcome(true)
  }

  const fetchSessions = () => {
    fetch('/api/sessions').then(r => r.json()).then(data => {
      setSessions(data.sessions || [])
    }).catch(() => {})
  }

  const switchSession = async (sid: string) => {
    try {
      const res = await fetch(`/api/sessions/${sid}`)
      if (!res.ok) {
        console.error('switchSession failed: HTTP', res.status)
        return
      }
      const data = await res.json()
      if (!data.session) {
        console.error('switchSession: no session in response')
        return
      }
      setSessionId(sid)
      setMessages((data.session.messages || []).map((m: { role: string; content: string; timestamp: string }) => ({
        role: m.role === 'human' ? 'user' : 'assistant',
        content: m.content,
        timestamp: m.timestamp,
      })))
      setAwaitingConfirmation(false)
      setTraceEvents([])
      setStartedChat(true)
      setShowWelcome(false)
    } catch (e) {
      console.error('switchSession error:', e)
    }
  }

  const deleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('确定要删除此会话吗？')) return
    try {
      await fetch(`/api/sessions/${sid}`, { method: 'DELETE' })
      if (sessionId === sid) {
        setSessionId(null)
        setMessages([])
        setStartedChat(false)
        setShowWelcome(true)
      }
      fetchSessions()
    } catch {}
  }

  // Load models and ontologies on mount
  useEffect(() => {
    fetchSessions()
    Promise.all([
      fetch('/api/settings').then(r => r.json()),
      fetch('/api/ontology/list').then(r => r.json()),
    ]).then(([settingsData, ontologyData]) => {
      const ms = (settingsData.models || []).map((m: { id: string; name: string; provider: string }) => ({
        id: m.id,
        name: m.name,
        provider: m.provider,
      }))
      setModels(ms)
      if (ms.length > 0) {
        setSelectedModel(settingsData.active_model_id || ms[0].id)
      }
      const os = (ontologyData.ontologies || []).map((o: { id: string; name: string }) => ({
        id: o.id,
        name: o.name,
      }))
      setOntologies(os)
      if (os.length > 0) {
        setSelectedOntology(os[0].id)
      }
    }).catch(() => {})
  }, [])

  const handleTraceEvent = useCallback((event: TraceEvent) => {
    setTraceEvents(prev => [...prev, event])
  }, [])

  useSSE(sessionId, handleTraceEvent)

  const handleViewChange = (view: ViewType) => {
    if (view === 'chat') {
      setShowWelcome(false)
      fetch('/api/settings').then(r => r.json()).then(data => {
        const ms = (data.models || []).map((m: any) => ({ id: m.id, name: m.name, provider: m.provider }))
        setModels(ms)
        if (ms.length > 0 && !ms.find((m: ModelOption) => m.id === selectedModel)) {
          setSelectedModel(data.active_model_id || ms[0].id)
        }
      }).catch(() => {})
      fetch('/api/ontology/list').then(r => r.json()).then(data => {
        const os = (data.ontologies || []).map((o: any) => ({ id: o.filename, name: o.name }))
        setOntologies(os)
        if (os.length > 0 && !os.find((o: OntologyOption) => o.id === selectedOntology)) {
          setSelectedOntology(os[0].id)
        }
      }).catch(() => {})
    }
    setActiveView(view)
  }

  const sendMessage = async (message: string, confirmed: boolean) => {
    setStartedChat(true)
    setShowWelcome(false)
    setLoading(true)
    setTraceEvents([])

    const userMsg: Message = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: user?.userId || user?.id,
          role: user?.role,
          warehouse_id: user?.warehouse || (user?.role === 'admin' ? '' : 'WH-SC-001'),
          message,
          confirmed,
          model_id: selectedModel || undefined,
          ontology_id: selectedOntology || undefined,
        }),
      })
      let data: any
      const body = await res.text()
      try {
        data = JSON.parse(body)
      } catch {
        data = {
          response: `❌ 服务器错误（${res.status}）：${body || '未知错误'}\n\n请检查后端服务是否正常运行，以及模型配置是否正确。`,
          session_id: sessionId || '',
          awaiting_confirmation: false,
          trace_events: [],
        }
      }
      setSessionId(data.session_id)
      setAwaitingConfirmation(data.awaiting_confirmation)
      fetchSessions()

      const teArray = (data.trace_events || []) as TraceEvent[]
      setTraceEvents(teArray)

      const assistantMsg: Message = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
        awaiting_confirmation: data.awaiting_confirmation,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      console.error('Chat error:', err)
      const errorMsg: Message = {
        role: 'assistant',
        content: `❌ 请求失败，请检查网络连接和后端服务。`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const goHome = () => {
    setStartedChat(false)
    setShowWelcome(true)
    setActiveView('chat')
  }

  const startChat = () => {
    setStartedChat(true)
    setShowWelcome(false)
    setActiveView('chat')
  }

  const newChat = () => {
    setSessionId(null)
    setMessages([])
    setTraceEvents([])
    setAwaitingConfirmation(false)
    setStartedChat(true)
    setShowWelcome(false)
  }

  // ── Not logged in → show login page ──
  if (!user) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <div className="h-screen flex bg-gray-50 text-gray-800">
      {/* Sidebar */}
      <Sidebar
        activeView={activeView}
        onViewChange={handleViewChange}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onHome={goHome}
      />

      {/* Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header bar (only in chat view with messages) */}
        {!showLanding && activeView === 'chat' && (
          <header className="flex items-center justify-between px-6 py-2 border-b bg-white">
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold text-gray-700">OntoPilot</span>
              <span className="text-gray-300">|</span>
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-md">
                {user.display_name} · {user.role === 'admin' ? '管理员' : user.role === 'regional_manager' ? '区域经理' : '调度员'}
              </span>
              {/* Model selector */}
              {models.length > 0 && (
                <select
                  value={selectedModel}
                  onChange={e => setSelectedModel(e.target.value)}
                  className="ml-1 text-xs border rounded px-2 py-1 text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-400"
                  title="选择模型"
                >
                  {models.map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              )}
              {/* Ontology selector */}
              {ontologies.length > 0 && (
                <select
                  value={selectedOntology}
                  onChange={e => {
                    setSelectedOntology(e.target.value)
                    setSessionId(null)
                    setMessages([])
                    setTraceEvents([])
                    setAwaitingConfirmation(false)
                    setStartedChat(false)
                  }}
                  className="ml-1 text-xs border rounded px-2 py-1 text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-400"
                  title="选择本体"
                >
                  {ontologies.map(o => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={newChat}
                className="px-2.5 py-1 rounded-md text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              >
                + 新对话
              </button>
              <button
                onClick={() => setRightPanel(rightPanel === 'trace' ? null : 'trace')}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  rightPanel === 'trace'
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                推理过程
              </button>
              <button
                onClick={() => setRightPanel(rightPanel === 'ontology' ? null : 'ontology')}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  rightPanel === 'ontology'
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                本体可视化
              </button>
              <button
                onClick={handleLogout}
                className="px-2.5 py-1 rounded-md text-xs font-medium text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                退出
              </button>
            </div>
          </header>
        )}

        {/* Landing page */}
        {showLanding && (
          <WelcomePage
            onStart={startChat}
            onViewChange={handleViewChange}
          />
        )}

        {/* Config panel */}
        {activeView === 'config' && (
          <div className="flex-1 overflow-hidden">
            <ModelConfigPanel />
          </div>
        )}

        {/* Ontology panel */}
        {activeView === 'ontology' && (
          <div className="flex-1 overflow-hidden">
            <OntologyConfigPanel onActivate={setSelectedOntology} />
          </div>
        )}

        {/* Users panel */}
        {activeView === 'users' && (
          <div className="flex-1 overflow-hidden">
            <UserManagement currentUser={user} onLogout={handleLogout} />
          </div>
        )}

        {/* Chat + optional panels */}
        {activeView === 'chat' && !showLanding && (
          <div className="flex-1 flex overflow-hidden">
            {/* Session list sidebar */}
            {sessions.length > 0 && (
              <div className="w-56 flex-shrink-0 border-r bg-white overflow-y-auto flex flex-col">
                <div className="px-3 py-2 border-b border-gray-100 text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>历史会话</span>
                  <span className="text-gray-300 font-normal">({sessions.length})</span>
                </div>
                <div className="flex-1 overflow-y-auto">
                  {sessions.slice(0, 50).map(s => {
                    const isActive = s.id === sessionId
                    return (
                      <div
                        key={s.id}
                        className={`group relative border-b border-gray-50 transition-colors ${
                          isActive
                            ? 'bg-blue-50 border-l-2 border-l-blue-500'
                            : 'border-l-2 border-l-transparent'
                        }`}
                      >
                        <button
                          onClick={() => switchSession(s.id)}
                          className={`w-full text-left px-3 py-2.5 pr-8 ${isActive ? '' : 'hover:bg-gray-50'}`}
                        >
                          <div className={`text-xs font-medium truncate ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>
                            {s.title}
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {new Date(s.updated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            {s.message_count > 0 && <span> · {s.message_count} 条</span>}
                          </div>
                        </button>
                        <button
                          onClick={(e) => deleteSession(s.id, e)}
                          className="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-all pointer-events-none group-hover:pointer-events-auto"
                          title="删除会话"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Chat area */}
            <div className={`flex flex-col ${rightPanel ? 'w-1/2' : 'flex-1'} transition-all`}>
              <ChatPanel
                messages={messages}
                onSend={sendMessage}
                awaitingConfirmation={awaitingConfirmation}
                loading={loading}
              />
            </div>

            {/* Trace / ontology panel */}
            {rightPanel === 'trace' && (
              <div className="w-1/2 flex flex-col border-l bg-white">
                <div className="px-4 py-2 bg-gray-50 border-b text-xs font-medium text-gray-500 uppercase tracking-wider">
                  推理过程
                </div>
                <div className="flex-1 overflow-hidden">
                  <TracePanel events={traceEvents} />
                </div>
              </div>
            )}
            {rightPanel === 'ontology' && (
              <div className="w-1/2 flex flex-col border-l bg-white">
                <div className="px-4 py-2 bg-gray-50 border-b text-xs font-medium text-gray-500 uppercase tracking-wider">
                  本体可视化
                </div>
                <div className="flex-1 overflow-hidden">
                  <OntologyGraphPanel ontologyId={selectedOntology} traceEvents={traceEvents} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
