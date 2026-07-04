import React, { useState, useEffect } from 'react'

interface ModelConfig {
  id: string
  name: string
  provider: string
  model: string
  api_key_env: string
  api_key: string
  base_url: string
  max_tokens: number
  temperature: number
}

const PROVIDERS: { value: string; label: string; compatible: boolean }[] = [
  { value: 'anthropic', label: 'Anthropic', compatible: false },
  { value: 'anthropic_compatible', label: 'Anthropic Compatible', compatible: true },
  { value: 'openai', label: 'OpenAI', compatible: false },
  { value: 'openai_compatible', label: 'OpenAI Compatible', compatible: true },
]

function emptyModel(): ModelConfig {
  return {
    id: '',
    name: '',
    provider: 'anthropic',
    model: '',
    api_key_env: '',
    api_key: '',
    base_url: '',
    max_tokens: 4096,
    temperature: 0,
  }
}

function generateId(): string {
  return 'model-' + Date.now().toString(36)
}

export function ModelConfigPanel() {
  const [models, setModels] = useState<ModelConfig[]>([])
  const [activeModelId, setActiveModelId] = useState('')
  const [draft, setDraft] = useState<ModelConfig | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    fetch('/api/settings')
      .then(res => res.json())
      .then(data => {
        setModels(data.models || [])
        setActiveModelId(data.active_model_id || '')
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [])

  const activeProvider = () => PROVIDERS.find(p => p.value === draft?.provider)

  const startAdd = () => {
    setDraft(emptyModel())
    setEditingId(null)
    setTestResult(null)
    setMessage(null)
  }

  const startEdit = (m: ModelConfig) => {
    setDraft({ ...m })
    setEditingId(m.id)
    setTestResult(null)
    setMessage(null)
  }

  const cancelForm = () => {
    setDraft(null)
    setEditingId(null)
    setTestResult(null)
  }

  const updateDraft = (field: string, value: string | number) => {
    if (!draft) return
    setDraft(prev => ({ ...prev!, [field]: value }))
  }

  const handleTest = async () => {
    if (!draft) return
    setTesting(true)
    setTestResult(null)
    setMessage(null)
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 20000)
      const res = await fetch('/api/settings/test-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: draft }),
        signal: controller.signal,
      })
      clearTimeout(timeout)
      const data = await res.json()
      setTestResult(data)
      // Auto-hide success after 5s
      if (data.status === 'ok') {
        setTimeout(() => setTestResult(null), 5000)
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setTestResult({ status: 'error', message: '连接超时（20秒），请检查 API 地址和 Key 是否正确' })
      } else {
        setTestResult({ status: 'error', message: '请求失败：' + (err?.message || '未知错误') })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!draft || !draft.name.trim() || !draft.model.trim()) {
      setMessage({ type: 'error', text: '请填写模型名称和模型名称字段' })
      return
    }
    setSaving(true)
    setMessage(null)

    let updated: ModelConfig[]
    if (editingId) {
      updated = models.map(m => (m.id === editingId ? draft : m))
    } else {
      updated = [...models, { ...draft, id: generateId() }]
    }

    const settings = {
      models: updated,
      active_model_id: activeModelId,
    }

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      })
      if (!res.ok) throw new Error('Save failed')
      setModels(updated)
      setMessage({ type: 'success', text: '模型配置已保存' })
      setDraft(null)
      setEditingId(null)
    } catch {
      setMessage({ type: 'error', text: '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    const updated = models.filter(m => m.id !== id)
    const newActive = activeModelId === id
      ? (updated.length > 0 ? updated[0].id : '')
      : activeModelId

    const settings = {
      models: updated,
      active_model_id: newActive,
    }

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      })
      if (!res.ok) throw new Error('Delete failed')
      setModels(updated)
      setActiveModelId(newActive)
      setMessage({ type: 'success', text: '已删除模型' })
    } catch {
      setMessage({ type: 'error', text: '删除失败' })
    }
  }

  const setActive = async (id: string) => {
    const settings = {
      models,
      active_model_id: id,
    }
    try {
      await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      })
      setActiveModelId(id)
      setMessage({ type: 'success', text: '已切换为默认模型' })
    } catch {
      setMessage({ type: 'error', text: '切换失败' })
    }
  }

  if (!loaded) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        加载中...
      </div>
    )
  }

  const formOpen = draft !== null

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">模型配置</h2>
        {!formOpen && (
          <button
            onClick={startAdd}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            添加模型
          </button>
        )}
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Add / Edit form */}
      {formOpen && (
        <div className="mb-6 p-5 border border-blue-200 bg-blue-50 rounded-xl">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            {editingId ? '编辑模型' : '添加模型'}
          </h3>

          {/* Test result banner — always visible at top of form */}
          {testing && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-indigo-50 border border-indigo-200 text-indigo-700 flex items-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
              正在测试连通性，请稍候...
            </div>
          )}
          {testResult && (
            <div className={`mb-4 p-3 rounded-lg text-sm font-medium ${
              testResult.status === 'ok'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {testResult.status === 'ok' ? '✅ 连通性测试成功' : '❌ 连通性测试失败'}
              {testResult.message && (
                <p className="text-xs mt-1 font-normal opacity-80">{testResult.message}</p>
              )}
            </div>
          )}
          <div className="space-y-4 max-w-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">名称</label>
                <input
                  type="text"
                  value={draft.name}
                  onChange={e => updateDraft('name', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. My Model"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">提供商</label>
                <select
                  value={draft.provider}
                  onChange={e => updateDraft('provider', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  {PROVIDERS.map(p => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">模型名称</label>
                <input
                  type="text"
                  value={draft.model}
                  onChange={e => updateDraft('model', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. claude-sonnet-4-5"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input
                  type="password"
                  value={draft.api_key}
                  onChange={e => updateDraft('api_key', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="直接输入 API Key"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key 环境变量（备选）</label>
                <input
                  type="text"
                  value={draft.api_key_env}
                  onChange={e => updateDraft('api_key_env', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. ANTHROPIC_API_KEY"
                />
              </div>
            </div>
            {activeProvider()?.compatible && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Base URL</label>
                <input
                  type="text"
                  value={draft.base_url}
                  onChange={e => updateDraft('base_url', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. https://api.example.com/v1"
                />
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Max Tokens</label>
                <input
                  type="number"
                  value={draft.max_tokens}
                  onChange={e => updateDraft('max_tokens', Number(e.target.value))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Temperature</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={draft.temperature}
                  onChange={e => updateDraft('temperature', Number(e.target.value))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleTest}
                disabled={testing}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {testing && <div className="w-3.5 h-3.5 rounded-full border-2 border-white/40 border-t-white animate-spin" />}
                {testing ? '测试中...' : '测试连通性'}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                onClick={cancelForm}
                className="px-4 py-2 text-gray-600 rounded-lg text-sm hover:bg-gray-100 transition-colors"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Model list */}
      {models.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-sm">暂无模型配置</p>
          <p className="text-xs mt-1">点击「添加模型」开始配置</p>
        </div>
      ) : (
        <div className="space-y-3">
          {models.map(m => (
            <div
              key={m.id}
              className={`flex items-center justify-between p-4 rounded-xl border ${
                m.id === activeModelId
                  ? 'border-blue-300 bg-blue-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              } transition-colors`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-800 text-sm">{m.name}</span>
                  {m.id === activeModelId && (
                    <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">默认</span>
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-1 space-x-2">
                  <span>{PROVIDERS.find(p => p.value === m.provider)?.label || m.provider}</span>
                  <span>·</span>
                  <span>{m.model}</span>
                  {m.base_url && (
                    <>
                      <span>·</span>
                      <span className="font-mono text-gray-400">{m.base_url}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                {m.id !== activeModelId && (
                  <button
                    onClick={() => setActive(m.id)}
                    className="px-2.5 py-1 border border-gray-300 rounded-lg text-xs text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    设为默认
                  </button>
                )}
                <button
                  onClick={() => startEdit(m)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                  title="编辑"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  onClick={() => handleDelete(m.id)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="删除"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
