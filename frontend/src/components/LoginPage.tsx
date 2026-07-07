import React, { useState } from 'react'

interface LoginUser {
  id: string
  username: string
  role: string
  display_name: string
  warehouse?: string
  userId?: string
}

interface Props {
  onLogin: (user: LoginUser) => void
}

const ACCOUNTS: { username: string; label: string; password: string; desc: string }[] = [
  { username: 'admin', label: '超级管理员', password: 'admin123', desc: '用户管理、角色权限配置' },
  { username: 'dispatcher', label: '调度员', password: 'disp123', desc: '查看货物、处理异常' },
  { username: 'manager', label: '区域经理', password: 'mgr123', desc: '查询、分析、决策' },
]

const ROLE_MAP: Record<string, { warehouse: string; userId: string }> = {
  admin: { warehouse: '', userId: 'admin_001' },
  dispatcher: { warehouse: 'WH-SC-001', userId: 'dispatcher_001' },
  regional_manager: { warehouse: 'WH-SC-001', userId: 'manager_001' },
}

export function LoginPage({ onLogin }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const account = ACCOUNTS.find(a => a.username === selected)

  const handleLogin = async () => {
    if (!selected || !password) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: selected, password }),
      })
      const body = await res.text()
      let data: any
      try {
        data = JSON.parse(body)
      } catch {
        throw new Error(
          `服务器返回了非 JSON 响应（HTTP ${res.status}）。请检查后端服务是否已启动（python main.py）。`
        )
      }
      if (!res.ok) throw new Error(data.detail || '登录失败')
      const user = data.user as LoginUser
      const extra = ROLE_MAP[user.role] || { warehouse: '', userId: user.id }
      onLogin({
        ...user,
        warehouse: extra.warehouse,
        userId: extra.userId,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      <div className="m-auto flex flex-col items-center w-full max-w-md px-4">
        {/* Logo */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-gray-800">OntoPilot</h1>
          <p className="text-sm text-gray-500 mt-1">基于本体的智能 Agent 运行时</p>
        </div>

        {/* Login card */}
        <div className="w-full bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-5">选择账号登录</h2>

          {/* Account selection */}
          <div className="space-y-2 mb-5">
            {ACCOUNTS.map(acc => {
              const isSelected = selected === acc.username
              return (
                <button
                  key={acc.username}
                  onClick={() => { setSelected(acc.username); setPassword(''); setError('') }}
                  className={`w-full text-left flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                    isSelected
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium text-white ${
                    acc.username === 'admin' ? 'bg-purple-500'
                    : acc.username === 'dispatcher' ? 'bg-green-500'
                    : 'bg-blue-500'
                  }`}>
                    {acc.label.charAt(0)}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-800">{acc.label}</div>
                    <div className="text-xs text-gray-400">{acc.desc}</div>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Password input */}
          {selected && (
            <div className="mb-5">
              <label className="block text-xs text-gray-500 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                placeholder={`输入密码 (${account?.password})`}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                autoFocus
              />
            </div>
          )}

          {error && (
            <div className="mb-4 p-2 bg-red-50 text-red-600 rounded-lg text-xs">{error}</div>
          )}

          <button
            onClick={handleLogin}
            disabled={!selected || !password || loading}
            className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? '登录中...' : '进入系统'}
          </button>
        </div>
      </div>
    </div>
  )
}
