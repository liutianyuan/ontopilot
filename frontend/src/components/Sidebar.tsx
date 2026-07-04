import React from 'react'

export type ViewType = 'chat' | 'config' | 'ontology' | 'users'

interface Props {
  activeView: ViewType
  onViewChange: (view: ViewType) => void
  collapsed: boolean
  onToggleCollapse: () => void
  onHome: () => void
}

const items: { id: ViewType; label: string; icon: React.ReactNode }[] = [
  {
    id: 'chat',
    label: '对话',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    id: 'ontology',
    label: '本体配置',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    ),
  },
  {
    id: 'config',
    label: '模型配置',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    id: 'users',
    label: '用户管理',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    ),
  },
]

export function Sidebar({ activeView, onViewChange, collapsed, onToggleCollapse, onHome }: Props) {
  return (
    <div className={`flex flex-col bg-white border-r border-gray-200 transition-all duration-200 ${collapsed ? 'w-12' : 'w-44'}`}>
      {/* Logo area */}
      <div className={`flex items-center border-b border-gray-200 ${collapsed ? 'justify-center h-12' : 'px-4 h-12'}`}>
        {!collapsed && <span className="text-sm font-bold text-gray-800">OntoPilot</span>}
      </div>

      {/* Nav items */}
      <div className="flex-1 py-2 space-y-0.5">
        <button
          onClick={onHome}
          className={`flex items-center gap-3 w-full text-left transition-colors ${
            collapsed
              ? 'justify-center h-10'
              : 'px-4 h-10'
          } hover:bg-gray-100 text-gray-500 hover:text-gray-700`}
          title="首页"
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          {!collapsed && <span className="text-sm">首页</span>}
        </button>

        {items.map(item => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`flex items-center gap-3 w-full text-left transition-colors ${
              collapsed
                ? 'justify-center h-10'
                : 'px-4 h-10'
            } ${
              activeView === item.id
                ? 'bg-blue-50 text-blue-600 font-medium'
                : 'hover:bg-gray-100 text-gray-600 hover:text-gray-800'
            }`}
            title={item.label}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && <span className="text-sm">{item.label}</span>}
          </button>
        ))}
      </div>

      {/* Collapse toggle */}
      <div className="border-t border-gray-200 p-1">
        <button
          onClick={onToggleCollapse}
          className="flex items-center justify-center w-full h-8 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          title={collapsed ? '展开菜单' : '收起菜单'}
        >
          <svg className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </div>
  )
}
