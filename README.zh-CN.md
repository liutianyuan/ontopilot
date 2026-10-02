<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="版本">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="许可证">
</p>

<div align="center">

**[English](README.md) · [中文](README.zh-CN.md)**

</div>

<h1 align="center">基于知识编织的智能体平台</h1>
<p align="center"><em>基于 Ontology 的业务决策支持系统 + LLM 智能代理</em></p>

本工程是“基于知识编织的智能体平台”的**后端运行服务**。本体、规则、动作、权限和实例均来自 `nano-ontoprompt` 已发布知识主题；本工程负责对话编排、证据报告、确认流程、Trace 与审计。

---

## 功能特性

- **知识主题驱动** — 每个 Nano 已发布知识主题就是一个可选本体
- **LLM 代理** — LangGraph 驱动，根据 Ontology 动态加载工具
- **基于角色的权限** — 按角色细粒度控制查询、函数、操作和数据范围
- **操作引擎** — 先预览后执行的工作流，自动验证和确认
- **单步仿真** — 分支-应用-对比 KPI 仿真，辅助决策比较
- **会话管理** — 多轮对话自动保存，历史浏览
- **Trace 与审计** — 完整操作追踪记录和审计日志
- **FastAPI 后端** — 异步 REST API + SSE 流式实时响应
- **统一前端** — Nano 智能体工作台提供主题切换、会话、表格报告、确认和推理过程

## 架构

```
Nano 已发布知识主题
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Schema      │───▶│ Ontology     │───▶│ LangGraph   │
│ Registry    │    │ Runtime      │    │ Agent + LLM │
├─────────────┤    ├──────────────┤    ├─────────────┤
│ Topic API   │    │ ActionExec   │    │ FastAPI     │
│ (Nano)      │    │ Remote Rules│    │ 后端       │
├─────────────┤    │ Governance   │    ├─────────────┤
│ Permission  │    │ Simulation   │    │ React       │
│ Evaluator   │    │ Context      │    │ Nano UI     │
└─────────────┘    └──────────────┘    └─────────────┘
```

## 快速开始

### 环境要求

- Python 3.11+

### 启动后端

```bash
./scripts/dev-api.sh
```

该脚本会通过 `uv` 同步依赖，并执行 `uv run python main.py`。
API 服务运行在 `http://localhost:8100`。

### 前端入口

本工程现为纯后端智能体运行服务，不再维护独立前端。统一界面位于
`nano-ontoprompt/frontend` 的“智能体工作台”，通过 `VITE_AGENT_API_BASE`
连接本服务（默认 `http://localhost:8100/api`）。浏览器只携带 Nano 登录令牌，
本服务再向 Nano 校验用户身份、角色和所选知识主题。

### 默认登录账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 超级管理员 | `admin` | `admin123` |
| 调度员 | `dispatcher` | `disp123` |
| 区域经理 | `manager` | `mgr123` |
| 肾内科医生 | `nephro` | `nephro123` |

生产部署后请使用超级管理员账号及时修改默认密码。

## Ubuntu 生产部署

推荐使用 **systemd + Nginx**：systemd 在 `127.0.0.1:8100` 常驻运行 FastAPI；Nano 前端的 Nginx 将智能体 API 转发到本服务。支持 Ubuntu 22.04/24.04。

### 一键部署

先将项目克隆到服务器，并填写模型密钥：

```bash
git clone <仓库地址> ontopilot
cd ontopilot
cp .env.example .env
cp config/settings.yaml.example config/settings.yaml
nano .env
```

运行部署脚本（安装 `uv` 并创建后端 systemd 服务）：

```bash
chmod +x scripts/deploy-ubuntu.sh
./scripts/deploy-ubuntu.sh
```

部署完成后由 Nano 前端或网关访问 `http://127.0.0.1:8100/api`。

### 分步部署命令

后端：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
cp -n .env.example .env
cp -n config/settings.yaml.example config/settings.yaml
uv sync --frozen --no-dev
RELOAD=0 HOST=127.0.0.1 PORT=8100 uv run python main.py


nohup env RELOAD=0 HOST=127.0.0.1 PORT=8100 uv run python main.py > ontopilot-api.log 2>&1 &


nohup env \
  RELOAD=0 \
  HOST=127.0.0.1 \
  PORT=8101 \
  NANO_API_BASE=http://127.0.0.1:28081/api/v1 \
  CORS_ALLOWED_ORIGINS=http://182.18.82.150:11081 \
  NANO_TOPIC_ID= \
  NANO_ONTOLOGY_ID= \
  uv run python main.py > ontopilot-api.log 2>&1 &

```
本机
nohup env \
  RELOAD=0 \
  HOST=127.0.0.1 \
  PORT=8101 \
  NANO_API_BASE=http://127.0.0.1:28081/api/v1 \
  CORS_ALLOWED_ORIGINS=http://182.18.82.150:10081 \
  NANO_TOPIC_ID= \
  NANO_ONTOLOGY_ID= \
  uv run python main.py > ontopilot-api.log 2>&1 &

生产环境请使用脚本生成的 systemd 与 Nginx 配置，而不是让上述后端命令占用终端。常用运维命令：

```bash
sudo systemctl status ontopilot
sudo journalctl -u ontopilot -f
sudo systemctl restart ontopilot
```

更新版本后，在项目目录重新执行 `./scripts/deploy-ubuntu.sh` 即可重新安装依赖并重启服务。脚本不会覆盖已有的 `.env` 和 `config/settings.yaml`。

## 示例

平台内置 **5 个业务 Ontology**，覆盖不同场景：

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

config/              # Ontology 配置文件
tests/               # 测试套件
```

## 许可证

MIT

---

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=jingw2/ontopilot&type=Date)](https://star-history.com/#jingw2/ontopilot&Date)

</div>
