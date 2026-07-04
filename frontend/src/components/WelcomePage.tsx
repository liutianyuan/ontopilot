import React from 'react'
import { ViewType } from './Sidebar'

interface Props {
  onStart: () => void
  onViewChange: (view: ViewType) => void
}

export function WelcomePage({ onStart, onViewChange }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-white text-gray-800">
      <div className="max-w-2xl mx-auto text-center px-6">
        {/* Logo / Brand */}
        <div className="mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-3xl shadow-lg mb-4">
            O
          </div>
          <h1 className="text-4xl font-bold text-gray-900 tracking-tight">OntoPilot</h1>
          <p className="mt-3 text-lg text-gray-500 leading-relaxed">
            基于本体的智能 Agent 运行时，支持业务查询、风险分析、决策仿真与操作执行
          </p>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
          <button
            onClick={onStart}
            className="group flex items-center gap-4 p-5 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-all text-left"
          >
            <span className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center text-lg group-hover:bg-blue-200">
              💬
            </span>
            <div>
              <div className="font-semibold text-gray-900">开始对话</div>
              <div className="text-sm text-gray-500 mt-0.5">与 Agent 交互，查询和分析业务数据</div>
            </div>
          </button>

          <button
            onClick={() => onViewChange('ontology')}
            className="group flex items-center gap-4 p-5 rounded-xl border border-gray-200 hover:border-green-300 hover:bg-green-50 transition-all text-left"
          >
            <span className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-100 text-green-600 flex items-center justify-center text-lg group-hover:bg-green-200">
              📤
            </span>
            <div>
              <div className="font-semibold text-gray-900">导入 Ontology</div>
              <div className="text-sm text-gray-500 mt-0.5">上传 YAML 本体定义文件</div>
            </div>
          </button>

          <button
            onClick={() => onViewChange('config')}
            className="group flex items-center gap-4 p-5 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
          >
            <span className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 text-gray-600 flex items-center justify-center text-lg group-hover:bg-gray-200">
              ⚙️
            </span>
            <div>
              <div className="font-semibold text-gray-900">模型配置</div>
              <div className="text-sm text-gray-500 mt-0.5">切换 LLM 提供商和模型参数</div>
            </div>
          </button>

          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-4 p-5 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
          >
            <span className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 text-gray-600 flex items-center justify-center text-lg group-hover:bg-gray-200">
              📖
            </span>
            <div>
              <div className="font-semibold text-gray-900">使用指南</div>
              <div className="text-sm text-gray-500 mt-0.5">了解 OntoPilot 的功能和用法</div>
            </div>
          </a>
        </div>

        {/* Workflow steps */}
        <div className="mt-12 pt-8 border-t border-gray-100">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">三步开始使用</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-6">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 text-sm font-bold mb-2">1</div>
              <div className="text-sm font-medium text-gray-900">配置本体</div>
              <div className="text-xs text-gray-500 mt-1">上传或加载预置的 Ontology YAML</div>
            </div>
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 text-sm font-bold mb-2">2</div>
              <div className="text-sm font-medium text-gray-900">配置模型</div>
              <div className="text-xs text-gray-500 mt-1">选择 LLM 提供商和模型参数</div>
            </div>
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 text-sm font-bold mb-2">3</div>
              <div className="text-sm font-medium text-gray-900">开始对话</div>
              <div className="text-xs text-gray-500 mt-1">Agent 能查询数据、分析风险、执行业务操作</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
