import React, { useState, useEffect } from 'react'

interface User {
  id: string
  username: string
  role: string
  display_name: string
}

interface RolePerm {
  query_types: string[]
  functions: string[]
  actions: Record<string, any>
  data_scope: Record<string, any>
}

interface LoginUser {
  id: string
  username: string
  role: string
  display_name: string
  warehouse?: string
  userId?: string
}

interface Props {
  currentUser: LoginUser
  onLogout: () => void
}

const ROLES = ['admin', 'dispatcher', 'regional_manager']

export function UserManagement({ currentUser, onLogout }: Props) {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Record<string, RolePerm>>({})
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [tab, setTab] = useState<'users' | 'roles'>('users')

  const isAdmin = currentUser.role === 'admin'

  // Add/Edit user modal
  const [userModal, setUserModal] = useState<{ mode: 'add' | 'edit'; user?: User } | null>(null)
  const [userForm, setUserForm] = useState({ username: '', password: '', role: 'dispatcher', display_name: '' })

  // Role editor
  const [editRole, setEditRole] = useState<string | null>(null)
  const [roleForm, setRoleForm] = useState<RolePerm>({ query_types: [], functions: [], actions: {}, data_scope: {} })

  useEffect(() => {
    fetchUsers()
    fetchRoles()
  }, [])

  const fetchUsers = async () => {
    try {
      const res = await fetch('/api/users')
      if (res.ok) {
        setUsers((await res.json()).users || [])
      }
    } catch {} finally {
      setLoading(false)
    }
  }

  const fetchRoles = async () => {
    try {
      const res = await fetch('/api/roles')
      if (res.ok) {
        setRoles((await res.json()).roles || {})
      }
    } catch {}
  }

  const openAddUser = () => {
    setUserForm({ username: '', password: '', role: 'dispatcher', display_name: '' })
    setUserModal({ mode: 'add' })
  }

  const openEditUser = (u: User) => {
    setUserForm({ username: u.username, password: '', role: u.role, display_name: u.display_name })
    setUserModal({ mode: 'edit', user: u })
  }

  const saveUser = async () => {
    if (!userForm.username || !userForm.display_name) return
    if (userModal?.mode === 'add' && !userForm.password) return
    setMessage(null)
    try {
      if (userModal?.mode === 'add') {
        const res = await fetch('/api/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(userForm),
        })
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '创建失败')
      } else if (userModal?.mode === 'edit' && userModal.user) {
        const body: any = { role: userForm.role, display_name: userForm.display_name }
        if (userForm.password) body.password = userForm.password
        const res = await fetch(`/api/users/${userModal.user.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '更新失败')
      }
      setUserModal(null)
      setMessage({ type: 'success', text: userModal?.mode === 'add' ? '用户已创建' : '用户已更新' })
      fetchUsers()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '操作失败' })
    }
  }

  const deleteUser = async (u: User) => {
    if (!window.confirm(`确定删除用户「${u.display_name}」吗？`)) return
    setMessage(null)
    try {
      const res = await fetch(`/api/users/${u.id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '删除失败')
      setMessage({ type: 'success', text: '用户已删除' })
      fetchUsers()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '删除失败' })
    }
  }

  const openRoleEditor = (roleName: string) => {
    const perm = roles[roleName] || { query_types: [], functions: [], actions: {}, data_scope: {} }
    setRoleForm({
      query_types: [...(perm.query_types || [])],
      functions: [...(perm.functions || [])],
      actions: JSON.parse(JSON.stringify(perm.actions || {})),
      data_scope: JSON.parse(JSON.stringify(perm.data_scope || {})),
    })
    setEditRole(roleName)
  }

  const saveRole = async () => {
    if (!editRole) return
    setMessage(null)
    try {
      const res = await fetch(`/api/roles/${editRole}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(roleForm),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '保存失败')
      setEditRole(null)
      setMessage({ type: 'success', text: `角色「${editRole}」权限已更新` })
      fetchRoles()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    }
  }

  if (loading) {
    return <div className="h-full overflow-y-auto p-8"><p className="text-sm text-gray-500">加载中...</p></div>
  }

  return (
    <div className="h-full overflow-y-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">用户管理</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{currentUser.display_name} · {currentUser.role}</span>
          {isAdmin && (
            <button
              onClick={openAddUser}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors"
            >
              + 添加用户
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-4 border-b border-gray-200">
        <button
          onClick={() => setTab('users')}
          className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'users' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          用户列表
        </button>
        <button
          onClick={() => setTab('roles')}
          className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'roles' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          角色权限
        </button>
      </div>

      {/* Users tab */}
      {tab === 'users' && (
        <div className="grid gap-2">
          {users.map(u => (
            <div key={u.id} className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium text-white ${
                  u.role === 'admin' ? 'bg-purple-500' : u.role === 'regional_manager' ? 'bg-blue-500' : 'bg-green-500'
                }`}>
                  {u.display_name.charAt(0)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{u.display_name}</span>
                    {u.username === currentUser.username && (
                      <span className="text-xs text-blue-500">当前</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-400">@{u.username} · {u.role}</div>
                </div>
              </div>
              {isAdmin && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => openEditUser(u)}
                    className="px-2 py-1 text-xs text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => deleteUser(u)}
                    className="px-2 py-1 text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  >
                    删除
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Roles tab */}
      {tab === 'roles' && (
        <div className="grid gap-2">
          {ROLES.map(roleName => {
            const perm = roles[roleName]
            return (
              <div key={roleName} className="bg-white border border-gray-200 rounded-lg">
                <button
                  onClick={() => isAdmin && openRoleEditor(roleName)}
                  className={`w-full flex items-center justify-between px-4 py-3 ${isAdmin ? 'hover:bg-gray-50 cursor-pointer' : ''}`}
                >
                  <div className="text-left">
                    <div className="text-sm font-medium text-gray-800">{roleName}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {perm ? (
                        <>
                          可查询: [{perm.query_types?.join(', ') || ''}] ·
                          函数: [{perm.functions?.join(', ') || ''}] ·
                          操作: {Object.keys(perm.actions || {}).length} 个
                        </>
                      ) : '未配置'}
                    </div>
                  </div>
                  {isAdmin && (
                    <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Add/Edit User Modal ── */}
      {userModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setUserModal(null)}>
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-gray-800 mb-4">
              {userModal.mode === 'add' ? '添加用户' : '编辑用户'}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">用户名</label>
                <input
                  type="text"
                  value={userForm.username}
                  onChange={e => setUserForm(f => ({ ...f, username: e.target.value }))}
                  disabled={userModal.mode === 'edit'}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-50"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  {userModal.mode === 'add' ? '密码' : '新密码（留空不修改）'}
                </label>
                <input
                  type="password"
                  value={userForm.password}
                  onChange={e => setUserForm(f => ({ ...f, password: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">显示名称</label>
                <input
                  type="text"
                  value={userForm.display_name}
                  onChange={e => setUserForm(f => ({ ...f, display_name: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">角色</label>
                <select
                  value={userForm.role}
                  onChange={e => setUserForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setUserModal(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                取消
              </button>
              <button onClick={saveUser} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                {userModal.mode === 'add' ? '创建' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Role Permission Editor Modal ── */}
      {editRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditRole(null)}>
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-gray-800 mb-4">编辑角色权限: {editRole}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">可查询对象类型</label>
                <input
                  type="text"
                  value={roleForm.query_types.join(', ')}
                  onChange={e => setRoleForm(f => ({ ...f, query_types: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))}
                  placeholder="Shipment, Order, ExceptionCase"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <p className="text-xs text-gray-400 mt-1">逗号分隔</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">可用函数</label>
                <input
                  type="text"
                  value={roleForm.functions.join(', ')}
                  onChange={e => setRoleForm(f => ({ ...f, functions: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))}
                  placeholder="calculateDelayRisk, recommendCarrier"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <p className="text-xs text-gray-400 mt-1">逗号分隔</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">操作权限</label>
                <div className="text-xs text-gray-400 mb-2">JSON 格式，如: {"{"}"assignCarrier": {"{"}"requires_confirmation": true{"}"}{"}"}</div>
                <textarea
                  value={JSON.stringify(roleForm.actions, null, 2)}
                  onChange={e => { try { setRoleForm(f => ({ ...f, actions: JSON.parse(e.target.value) })) } catch {} }}
                  rows={4}
                  className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">数据范围</label>
                <textarea
                  value={JSON.stringify(roleForm.data_scope, null, 2)}
                  onChange={e => { try { setRoleForm(f => ({ ...f, data_scope: JSON.parse(e.target.value) })) } catch {} }}
                  rows={3}
                  className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setEditRole(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                取消
              </button>
              <button onClick={saveRole} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                保存权限
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
