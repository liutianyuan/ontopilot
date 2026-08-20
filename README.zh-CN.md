<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="版本">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="许可证">
</p>

<div align="center">

**[English](README.md) · [中文](README.zh-CN.md)**

</div>

<h1 align="center">OntoPilot</h1>
<p align="center"><em>基于 Ontology 的业务决策支持系统 + LLM 智能代理</em></p>

OntoPilot 是一个构建**知识驱动的 LLM 智能代理**框架，核心机制是通过 **YAML 本体定义**来声明式地描述业务对象类型、操作、函数、权限和上下文。LLM 代理在 Ontology 定义的边界内进行查询、计算、仿真和执行业务操作。

---

## 功能特性

- **声明式 Ontology** — 用 YAML 文件定义业务对象、关系、操作和函数
- **LLM 代理** — LangGraph 驱动，根据 Ontology 动态加载工具
- **基于角色的权限** — 按角色细粒度控制查询、函数、操作和数据范围
- **操作引擎** — 先预览后执行的工作流，自动验证和确认
- **单步仿真** — 分支-应用-对比 KPI 仿真，辅助决策比较
- **会话管理** — 多轮对话自动保存，历史浏览
- **Trace 与审计** — 完整操作追踪记录和审计日志
- **FastAPI 后端** — 异步 REST API + SSE 流式实时响应
- **React 前端** — 现代化 UI，支持模型/Ontology 切换、会话侧栏和推理过程展示

## 架构

```
Ontology YAML 文件
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Schema      │───▶│ Ontology     │───▶│ LangGraph   │
│ Registry    │    │ Runtime      │    │ Agent + LLM │
├─────────────┤    ├──────────────┤    ├─────────────┤
│ ObjectStore │    │ ActionExec   │    │ FastAPI     │
│ (SQLite)    │    │ FunctionReg  │    │ 后端       │
├─────────────┤    │ Governance   │    ├─────────────┤
│ Permission  │    │ Simulation   │    │ React       │
│ Evaluator   │    │ Context      │    │ 前端       │
└─────────────┘    └──────────────┘    └─────────────┘
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 启动后端

```bash
./scripts/dev-api.sh
```

该脚本会通过 `uv` 同步依赖，并执行 `uv run python main.py`。
API 服务运行在 `http://localhost:8000`。

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

开发服务器运行在 `http://localhost:5174`（通过 Vite 代理转发到后端）。

## 示例

OntoPilot 内置 **5 个业务 Ontology**，覆盖不同场景：

| Ontology | 对象 | 操作 | 描述 |
|----------|------|------|------|
| **Simple** | Person, City, Company, Book | — | 跨类型多跳查询 |
| **Medium** | Person, Org, Event, Pub, City | createEvent, assignEmployee | CRUD + 关联遍历 |
| **Complex** | Dept, Project, KPI, Document, Skill, Risk | 4 个操作, 4 个函数 | 项目健康度、技能缺口、仿真 |
| **Procurement** | 物料、供应商、分货计划、采购订单、评分 | 创建/调整/确认分货、供应商评分 | 分货规划、风险评估 |
| **Logistics** | 运单、订单、客户、承运商、仓库、异常 | 创建运单、分配承运商、更新ETA、开异常 | 承运商优化、延误风险、仿真 |

### 对话框冒烟测试

```bash
python tests/test_dialog_smoke.py
```

运行 50 轮对话（每个 Ontology 10 轮），端到端验证完整流程。

## 项目结构

```
ontopilot/           # 核心库
  ├── schema.py      # Schema 注册器 — 解析 YAML 定义
  ├── store.py       # 对象存储 — SQLite 持久化
  ├── governance.py  # 权限评估 — 基于角色的访问控制
  ├── context.py     # 上下文构建 — 动态范围上下文
  ├── functions.py   # 函数注册器 — 业务逻辑函数
  ├── actions.py     # 操作执行器 — 预览与执行工作流
  ├── simulation.py  # 仿真引擎 — 分支 & 对比 KPI
  ├── runtime.py     # OntologyRuntime — 编排所有组件
  ├── agent.py       # LangGraph 智能代理 — LLM + 工具编排
  ├── prompt.py      # Prompt 构建器 — 系统提示词构建
  ├── tools.py       # LangGraph 工具 — 绑定到 Runtime
  ├── llm.py         # LLM 工厂 — 模型提供商抽象
  ├── trace.py       # 追踪记录器 — 操作追踪事件
  ├── audit.py       # 审计日志 — 持久化审计记录
  ├── cli.py         # CLI 入口
  └── evaluation.py  # 评估框架

api/                 # FastAPI 后端
  ├── main.py        # 应用入口 & 中间件
  └── routes/        # 路由模块 (chat, settings, sessions, users, audit)

frontend/            # React 前端 (Vite + Tailwind)
  └── src/
      ├── App.tsx    # 主应用组件
      └── components/  # UI 组件

config/              # Ontology 配置文件
tests/               # 测试套件
```

## 许可证

MIT

---

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=jingw2/ontopilot&type=Date)](https://star-history.com/#jingw2/ontopilot&Date)

</div>
