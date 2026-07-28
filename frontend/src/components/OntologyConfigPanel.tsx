import React, { useState, useEffect, useRef } from 'react'
import { OntologyDetail } from '../types'

interface OntologyInfo {
  id: string
  name: string
  filename: string
  object_types: string[]
  actions: string[]
  functions: string[]
}

interface Props {
  onActivate: (filename: string) => void
}

interface CreateResult {
  object_types: string[]
  actions: string[]
  functions: string[]
  object_type_count: number
  action_count: number
  function_count: number
  tools_created: number
}

const CREATION_STEPS = [
  { label: '解析 Ontology Schema', key: 'schema' },
  { label: '创建对象存储层', key: 'store' },
  { label: '注册对象类型工具', key: 'objects' },
  { label: '注册操作工具', key: 'actions' },
  { label: '注册函数工具', key: 'functions' },
  { label: '初始化权限与审计引擎', key: 'perms' },
]

export function OntologyConfigPanel({ onActivate }: Props) {
  const [mode, setMode] = useState<'list' | 'import'>('list')
  const [ontologies, setOntologies] = useState<OntologyInfo[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showProgress, setShowProgress] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [progressResult, setProgressResult] = useState<CreateResult | null>(null)
  const progressTimer = useRef<number | null>(null)

  // Detail expand
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<OntologyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Track active ontology
  const [activeOntology, setActiveOntology] = useState<string | null>(null)

  useEffect(() => {
    fetchOntologies()
    return () => {
      if (progressTimer.current) clearInterval(progressTimer.current)
    }
  }, [])

  const fetchOntologies = async () => {
    try {
      const res = await fetch('/api/ontology/list')
      if (res.ok) {
        const data = await res.json()
        setOntologies(data.ontologies || [])
      }
    } catch {}
  }

  const fetchDetail = async (filename: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const res = await fetch(`/api/ontology/detail/${filename}`)
      if (res.ok) {
        setDetail(await res.json())
      }
    } catch {} finally {
      setDetailLoading(false)
    }
  }

  const toggleExpand = (id: string, filename: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      setDetail(null)
    } else {
      setExpandedId(id)
      fetchDetail(filename)
    }
  }

  const startProgress = () => {
    setShowProgress(true)
    setProgressStep(0)
    setProgressResult(null)
    progressTimer.current = window.setInterval(() => {
      setProgressStep(prev => Math.min(prev + 1, CREATION_STEPS.length))
    }, 400)
  }

  const finishProgress = (result: CreateResult) => {
    if (progressTimer.current) clearInterval(progressTimer.current)
    setProgressStep(CREATION_STEPS.length)
    setProgressResult(result)
    setTimeout(() => {
      setShowProgress(false)
      setProgressResult(null)
    }, 2500)
  }

  const failProgress = () => {
    if (progressTimer.current) clearInterval(progressTimer.current)
    setShowProgress(false)
    setProgressResult(null)
  }

  const filtered = ontologies.filter(o => {
    if (!filter.trim()) return true
    const q = filter.toLowerCase()
    return (
      o.name.toLowerCase().includes(q) ||
      o.filename.toLowerCase().includes(q) ||
      o.object_types.some(t => t.toLowerCase().includes(q))
    )
  })

  const handleDelete = async (filename: string, name: string) => {
    if (!window.confirm(`确定要删除本体 "${name}" (${filename})？\n此操作不可撤销。`)) return
    try {
      const res = await fetch(`/api/ontology/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '删除失败')
      }
      setMessage({ type: 'success', text: `已删除: ${filename}` })
      if (expandedId === filename) {
        setExpandedId(null)
        setDetail(null)
      }
      await fetchOntologies()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '删除失败' })
    }
  }

  const handleActivate = async (filename: string) => {
    startProgress()
    try {
      const res = await fetch('/api/ontology/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      })
      if (!res.ok) throw new Error('Activate failed')
      const data = await res.json()
      finishProgress(data as CreateResult)
      setMessage({ type: 'success', text: data.message || `已激活: ${filename}` })
      setActiveOntology(filename)
      onActivate(filename)
    } catch {
      failProgress()
      setMessage({ type: 'error', text: '激活失败' })
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    startProgress()
    setMessage(null)
    try {
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      const res = await fetch('/api/ontology/upload', { method: 'POST', body: formData })
      if (!res.ok) {
        failProgress()
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const data = await res.json()
      finishProgress(data as CreateResult)
      setMessage({ type: 'success', text: data.message || `已上传 ${files.length} 个文件` })
      await fetchOntologies()
    } catch (err) {
      failProgress()
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '上传失败' })
    } finally {
      e.target.value = ''
    }
  }

  const handleReload = async () => {
    startProgress()
    setMessage(null)
    try {
      const res = await fetch('/api/ontology/import', { method: 'POST' })
      if (!res.ok) {
        failProgress()
        throw new Error('Import failed')
      }
      const data = await res.json()
      finishProgress(data as CreateResult)
      await fetchOntologies()
      setMessage({ type: 'success', text: data.message || '种子数据已重新加载' })
    } catch {
      failProgress()
      setMessage({ type: 'error', text: '导入失败' })
    }
  }

  return (
    <div className="h-full overflow-y-auto p-8 relative">
      {/* Progress overlay */}
      {showProgress && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4">
            <div className="flex justify-center mb-5">
              {progressStep < CREATION_STEPS.length ? (
                <div className="w-12 h-12 rounded-full border-4 border-blue-100 border-t-blue-600 animate-spin" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </div>
            <h3 className="text-lg font-semibold text-center text-gray-800 mb-6">
              {progressStep < CREATION_STEPS.length ? '正在创建 Agent 工具...' : '创建完成'}
            </h3>
            <div className="space-y-3 mb-6">
              {CREATION_STEPS.map((step, i) => {
                const done = i < progressStep
                const running = i === progressStep && progressStep < CREATION_STEPS.length
                return (
                  <div key={step.key} className="flex items-center gap-3">
                    <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs
                      ${done ? 'bg-green-100 text-green-600' : running ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-400'}`}
                    >
                      {done ? (
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : running ? (
                        <div className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-gray-300" />
                      )}
                    </div>
                    <span className={`text-sm ${done ? 'text-gray-700' : running ? 'text-blue-700 font-medium' : 'text-gray-400'}`}>
                      {step.label}
                    </span>
                    {done && step.key === 'objects' && progressResult && (
                      <span className="text-xs text-blue-600 ml-auto">{progressResult.object_type_count} 个</span>
                    )}
                    {done && step.key === 'actions' && progressResult && (
                      <span className="text-xs text-green-600 ml-auto">{progressResult.action_count} 个</span>
                    )}
                    {done && step.key === 'functions' && progressResult && (
                      <span className="text-xs text-purple-600 ml-auto">{progressResult.function_count} 个</span>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="w-full bg-gray-100 rounded-full h-1.5 mb-2">
              <div
                className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.round((progressStep / CREATION_STEPS.length) * 100)}%` }}
              />
            </div>
            {progressResult && (
              <div className="text-center text-xs text-gray-500">
                共创建 {progressResult.tools_created} 个工具
                （{progressResult.object_type_count} 对象类型、
                {progressResult.action_count} 操作、
                {progressResult.function_count} 函数）
              </div>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">本体配置</h2>
        {mode === 'list' && (
          <button
            onClick={() => { setMode('import'); setMessage(null) }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            导入 Ontology
          </button>
        )}
        {mode === 'import' && (
          <button
            onClick={() => setMode('list')}
            className="px-4 py-2 text-gray-600 rounded-lg text-sm hover:bg-gray-100 transition-colors"
          >
            返回列表
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

      {/* Import mode */}
      {mode === 'import' && (
        <div className="max-w-lg space-y-8">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">上传 Ontology YAML</h3>
            <p className="text-sm text-gray-500 mb-4">
              上传 ontology 定义文件（.yaml）。可以同时选择配套的 seed、permissions、context 文件一起上传。
              <br />系统会自动检测并加载 companion 文件。
            </p>
            <label className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 cursor-pointer disabled:opacity-50 transition-colors">
              <input
                type="file"
                accept=".yaml,.yml"
                multiple
                onChange={handleFileUpload}
                disabled={loading}
                className="hidden"
              />
              {loading ? '处理中...' : '选择 YAML 文件（可多选）'}
            </label>
          </div>
          <div className="pt-6 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">加载预置演示数据</h3>
            <p className="text-sm text-gray-500 mb-4">
              使用 config/seed_data.yaml 中的预置种子数据重新填充演示数据库。
            </p>
            <button
              onClick={handleReload}
              disabled={loading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {loading ? '加载中...' : '重新加载种子数据'}
            </button>
          </div>
        </div>
      )}

      {/* List mode */}
      {mode === 'list' && (
        <>
          <div className="mb-4">
            <input
              type="text"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="搜索本体名称、文件名或对象类型..."
              className="w-full max-w-md border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <p className="text-sm">{ontologies.length === 0 ? '暂无本体配置' : '未找到匹配的本体'}</p>
              <p className="text-xs mt-1">
                {ontologies.length === 0 ? '点击右上角「导入 Ontology」开始' : '尝试其他搜索关键词'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map(o => {
                const isExpanded = expandedId === o.id
                const isActive = activeOntology === o.filename

                return (
                  <div key={o.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                    {/* Card header — clickable */}
                    <button
                      onClick={() => toggleExpand(o.id, o.filename)}
                      className="w-full flex items-start justify-between p-4 hover:bg-gray-50 transition-colors text-left"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-800 text-sm">{o.name}</span>
                          {isActive && (
                            <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">当前</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5 font-mono">{o.filename}</div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {o.object_types.map(t => (
                            <span key={t} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{t}</span>
                          ))}
                          {o.actions.length > 0 && (
                            <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs">
                              {o.actions.length} 个操作
                            </span>
                          )}
                          {o.functions.length > 0 && (
                            <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                              {o.functions.length} 个函数
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0 ml-4" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => handleActivate(o.filename)}
                          disabled={isActive}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            isActive
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'border border-blue-300 text-blue-600 hover:bg-blue-50'
                          }`}
                        >
                          {isActive ? '已激活' : '激活使用'}
                        </button>
                        <button
                          onClick={() => handleDelete(o.filename, o.name)}
                          disabled={isActive}
                          className={`p-1.5 rounded-lg transition-colors ${
                            isActive
                              ? 'text-gray-200 cursor-not-allowed'
                              : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                          }`}
                          title={isActive ? '请先切换到其他本体再删除' : '删除本体'}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                        <svg
                          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                          fill="none" stroke="currentColor" viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </button>

                    {/* Expanded detail panel */}
                    {isExpanded && (
                      <div className="border-t border-gray-200 bg-gray-50 px-4 py-4">
                        {detailLoading ? (
                          <p className="text-xs text-gray-400">加载中...</p>
                        ) : detail ? (
                          <div className="space-y-5 text-sm">
                            {/* Object types */}
                            <div>
                              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">对象类型</h4>
                              <div className="space-y-3">
                                {detail.object_types.map(ot => (
                                  <div key={ot.name} className="bg-white rounded-lg border border-gray-200 p-3">
                                    <div className="font-medium text-gray-800 mb-1">{ot.name}</div>
                                    {ot.description && (
                                      <p className="text-xs text-gray-500 mb-2">{ot.description}</p>
                                    )}
                                    {ot.properties.length > 0 && (
                                      <div className="mb-2">
                                        <span className="text-xs text-gray-400">属性:</span>
                                        <div className="flex flex-wrap gap-1 mt-0.5">
                                          {ot.properties.map(p => (
                                            <span key={p.name} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                              {p.name}: {p.type}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {ot.links.length > 0 && (
                                      <div>
                                        <span className="text-xs text-gray-400">关联:</span>
                                        <div className="flex flex-wrap gap-1 mt-0.5">
                                          {ot.links.map(l => (
                                            <span key={l.name} className="px-1.5 py-0.5 bg-yellow-50 text-yellow-700 rounded text-xs">
                                              {l.name} → {l.target}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Actions */}
                            {detail.actions.length > 0 && (
                              <div>
                                <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">操作</h4>
                                <div className="flex flex-wrap gap-2">
                                  {detail.actions.map(a => (
                                    <div key={a.name} className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                                      <span className="font-medium text-green-700 text-xs">{a.name}</span>
                                      {a.params.length > 0 && (
                                        <div className="text-xs text-gray-400 mt-0.5">
                                          参数: {a.params.join(', ')}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Functions */}
                            {detail.functions.length > 0 && (
                              <div>
                                <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">函数</h4>
                                <div className="flex flex-wrap gap-2">
                                  {detail.functions.map(f => (
                                    <div key={f.name} className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                                      <span className="font-medium text-purple-700 text-xs">{f.name}</span>
                                      {f.params.length > 0 && (
                                        <div className="text-xs text-gray-400 mt-0.5">
                                          参数: {f.params.join(', ')}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Available tools */}
                            <div>
                              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">可用工具 ({detail.tools.length})</h4>
                              <div className="flex flex-wrap gap-1.5">
                                {detail.tools.map(t => {
                                  let color = 'bg-gray-100 text-gray-600'
                                  if (t.startsWith('query_') || t.startsWith('get_') || t.startsWith('search_')) color = 'bg-blue-50 text-blue-700'
                                  else if (t.startsWith('execute_action')) color = 'bg-green-50 text-green-700'
                                  else if (t.startsWith('call_function')) color = 'bg-purple-50 text-purple-700'
                                  else if (t.startsWith('traverse_')) color = 'bg-yellow-50 text-yellow-700'
                                  return (
                                    <span key={t} className={`px-2 py-0.5 rounded text-xs font-mono ${color}`}>{t}</span>
                                  )
                                })}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400">无法加载详情</p>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
