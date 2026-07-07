<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
</p>

<div align="center">

**[English](README.md) · [中文](README.zh-CN.md)**

</div>

<h1 align="center">OntoPilot</h1>
<p align="center"><em>Ontology-powered business decision support system with LLM agent</em></p>

OntoPilot is a framework for building knowledge-grounded LLM agents driven by **ontology definitions** — YAML schemas that declaratively define business object types, actions, functions, permissions, and context. The LLM agent queries, computes, simulates, and executes business operations strictly within the boundaries defined by the ontology.

---

## Features

- **Declarative Ontology** — Define object types, relationships, actions, and functions in simple YAML files
- **LLM Agent** — LangGraph-based agent dynamically loads tools from the ontology schema
- **Role-Based Access** — Fine-grained permissions per role (query, function, action, data scope)
- **Action Engine** — Preview-then-execute workflow with automatic validation and confirmation
- **Single-Step Simulation** — Fork-apply-compare KPI simulation for decision comparison
- **Session Management** — Multi-turn conversations with auto-save and history browsing
- **Trace & Audit** — Full trace recording and audit logging for every operation
- **FastAPI Backend** — Async REST API with SSE streaming for real-time responses
- **React Frontend** — Modern UI with model/ontology switching, session sidebar, and trace visualization

## Architecture

```
ontology YAML files
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Schema      │───▶│ Ontology     │───▶│ LangGraph   │
│ Registry    │    │ Runtime      │    │ Agent + LLM │
├─────────────┤    ├──────────────┤    ├─────────────┤
│ ObjectStore │    │ ActionExec   │    │ FastAPI     │
│ (SQLite)    │    │ FunctionReg  │    │ Backend     │
├─────────────┤    │ Governance   │    ├─────────────┤
│ Permission  │    │ Simulation   │    │ React       │
│ Evaluator   │    │ Context      │    │ Frontend    │
└─────────────┘    └──────────────┘    └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run the backend
python main.py
```

The API server starts at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5174` with Vite proxy to the backend.

## Examples

OntoPilot ships with **5 built-in ontologies** covering different business domains:

| Ontology | Objects | Actions | Description |
|----------|---------|---------|-------------|
| **Simple** | Person, City, Company, Book | — | Multi-hop queries across linked types |
| **Medium** | Person, Org, Event, Pub, City | createEvent, assignEmployee | CRUD + link traversal |
| **Complex** | Dept, Project, KPI, Document, Skill, Risk, Person | 4 actions, 4 functions | Project health, skill gap, simulation |
| **Procurement** | Material, Supplier, AllocationPlan, PurchaseOrder, Score | createAllocation, adjustBatch, confirmAllocation, scoreSupplier | Allocation planning, risk assessment |
| **Logistics** | Shipment, Order, Customer, Carrier, Warehouse, ExceptionCase | createShipment, assignCarrier, updateETA, openExceptionCase | Carrier optimization, delay risk, simulation |

### Dialog Smoke Test

```bash
python tests/test_dialog_smoke.py
```

Run 50 dialog rounds (10 per ontology) to verify the full pipeline end-to-end.

## Project Structure

```
ontopilot/           # Core library
  ├── schema.py      # Schema registry — parses YAML definitions
  ├── store.py       # Object store — SQLite-backed persistence
  ├── governance.py  # Permission evaluator — RBAC per role
  ├── context.py     # Context builder — dynamic scoped context
  ├── functions.py   # Function registry — business logic functions
  ├── actions.py     # Action executor — preview & execute workflow
  ├── simulation.py  # Simulation engine — fork & compare KPIs
  ├── runtime.py     # OntologyRuntime — orchestrates all components
  ├── agent.py       # LangGraph agent — LLM + tool orchestration
  ├── prompt.py      # Prompt builder — system prompt construction
  ├── tools.py       # LangGraph tools — bound to runtime
  ├── llm.py         # LLM factory — model provider abstraction
  ├── trace.py       # Trace recorder — operation trace events
  ├── audit.py       # Audit logger — persistent audit trail
  ├── cli.py         # CLI entry point
  └── evaluation.py  # Evaluation framework

api/                 # FastAPI backend
  ├── main.py        # App entry point & middleware
  └── routes/        # Route modules (chat, settings, sessions, users, audit)

frontend/            # React frontend (Vite + Tailwind)
  └── src/
      ├── App.tsx
      └── components/  # UI components

config/              # Ontology configuration files
tests/               # Test suite
```

## License

MIT

---

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=jingw2/ontopilot&type=Date)](https://star-history.com/#jingw2/ontopilot&Date)

</div>
