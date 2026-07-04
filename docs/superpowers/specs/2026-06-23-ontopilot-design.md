# OntoPilot — Implementation Design

**Date:** 2026-06-23  
**Based on:** PRD v0.3 (`ontopilot-prd-final.md`)  
**Status:** Approved, ready for implementation

---

## 1. Scope

Build OntoPilot in 4 phases, all in one implementation cycle:

- **Phase 0A** — No-LLM Ontology Runtime skeleton (schema, store, query, functions, actions, governance, audit, trace)
- **Phase 0B** — LangGraph agent with LLM tool calling
- **Phase 1** — Single-step simulation engine
- **Phase 2** — Baseline evaluation framework (3-mode comparison)
- **Phase 3** — FastAPI backend + React/Tailwind frontend

---

## 2. Tech Stack

| Concern | Choice |
|---|---|
| Python tooling | `uv` (pyproject.toml) |
| Agent orchestration | LangGraph `StateGraph` |
| LLM | Anthropic SDK + OpenAI SDK, provider set in `config/settings.yaml` |
| Object store | SQLite (stdlib `sqlite3`) + in-memory dict cache |
| API layer | FastAPI + `uvicorn` |
| Frontend | Vite + React 18 + Tailwind CSS |
| Real-time trace | Server-Sent Events (SSE) |
| Testing | `pytest` |

---

## 3. Project Structure

```
ontopilot/
├── pyproject.toml
├── config/
│   ├── ontology_schema.yaml      # Object types, links, actions, functions
│   ├── permissions.yaml          # Role definitions + data scope
│   ├── context_sources.yaml      # Context Builder configuration
│   ├── seed_data.yaml            # Minimal seed dataset
│   └── settings.yaml             # LLM provider, model, api_key env var names
├── ontopilot/
│   ├── cli.py                    # CLI entry point (run_case, chat)
│   ├── runtime.py                # OntologyRuntime — unified API
│   ├── schema.py                 # SchemaRegistry — loads ontology_schema.yaml
│   ├── store.py                  # ObjectStore + LinkResolver (SQLite-backed)
│   ├── context.py                # ContextBuilder — deterministic context injection
│   ├── functions.py              # FunctionRegistry + business logic
│   ├── actions.py                # ActionRegistry + ActionExecutor (lifecycle)
│   ├── governance.py             # PermissionEvaluator + DataScopeFilter
│   ├── audit.py                  # AuditLogger (append-only SQLite table)
│   ├── trace.py                  # TraceRecorder — shared TraceEvent schema
│   ├── simulation.py             # SingleStepSimulator — fork + KPI calc
│   ├── llm.py                    # LLM provider factory (Anthropic / OpenAI)
│   ├── agent.py                  # LangGraph StateGraph orchestrator
│   ├── tools.py                  # LangGraph @tool wrappers for Runtime methods
│   ├── prompt.py                 # PromptBuilder — 4-zone template
│   └── evaluation.py             # BaselineEvaluator — 3-mode comparison
├── api/
│   ├── main.py                   # FastAPI app
│   ├── routes/
│   │   ├── chat.py               # POST /api/chat, GET /api/chat/stream (SSE)
│   │   ├── sessions.py           # Session management
│   │   └── audit.py              # GET /api/audit
│   └── schemas.py                # Pydantic models
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── ChatPanel.tsx
│       │   ├── TracePanel.tsx
│       │   └── SimulationPanel.tsx
│       └── hooks/
│           └── useSSE.ts
└── tests/
    ├── test_runtime.py
    ├── test_query.py
    ├── test_functions.py
    ├── test_actions.py
    ├── test_governance.py
    └── test_simulation.py
```

---

## 4. Key Architectural Decisions

### 4.1 OntologyRuntime — 6-step pipeline

Every call to `runtime.*` runs in order:
1. Schema validation (params match schema definition)
2. Permission check (`governance.py` evaluates role vs requested operation)
3. Data scope filter (restrict results to user's region)
4. Execution (actual query / function call / action)
5. Trace event recorded via `trace.py`
6. Audit log written via `audit.py`

No method bypasses this pipeline.

### 4.2 LangGraph wiring

`tools.py` defines 5 LangGraph `@tool` functions:
- `object_query` → `runtime.query()`
- `call_function` → `runtime.call_function()`
- `preview_action` → `runtime.preview_action()`
- `execute_action` → `runtime.execute_action()`
- `simulate_decisions` → `runtime.simulate()`

`agent.py` `StateGraph` has two nodes: `llm_node` and `tool_node`. Loop: `llm_node → tool_node → llm_node` until no tool calls. When `preview_action` returns `requires_confirmation: true`, graph enters `awaiting_confirmation` terminal state and returns the preview to the caller. On the next user turn with `confirmed: true`, the graph executes.

### 4.3 LLM provider abstraction

`llm.py` `create_llm(settings)` factory:
- `provider = anthropic` → `langchain_anthropic.ChatAnthropic`
- `provider = openai` → `langchain_openai.ChatOpenAI`

Both implement `BaseChatModel` with `.bind_tools()`, so LangGraph's `ToolNode` is provider-agnostic.

### 4.4 Real-time trace streaming

Backend: FastAPI `StreamingResponse` with `text/event-stream` content type. Each `TraceEvent` is serialized to JSON and emitted as an SSE `data:` line.

Frontend: `useSSE` hook in React subscribes to `GET /api/chat/stream?session_id=...`. Events are pushed into component state. `TracePanel` renders each event as a collapsible row. `SimulationPanel` activates only when a `layer: simulation` event arrives.

### 4.5 Action lifecycle

```
previewed → pending_confirmation → executed → audited
```

`preview_action` always runs first (even for non-confirmation actions, for trace completeness). For `requires_confirmation: false` actions, the graph proceeds immediately to `execute_action`. For `requires_confirmation: true`, the graph pauses and returns the preview JSON to the user.

---

## 5. Ontology Objects & Schema

Defined in `config/ontology_schema.yaml` (full YAML in PRD §5.4):
- **Object types:** Shipment, Order, Customer, Carrier, Warehouse, ExceptionCase
- **Links:** Shipment→Order→Customer, Shipment→Carrier, Shipment→Warehouse, ExceptionCase→Shipment
- **Actions:** updateETA, assignCarrier, createExceptionCase
- **Functions:** calculateDelayRisk, recommendCarrier, compareDecisions

---

## 6. Seed Data

Defined in `config/seed_data.yaml` (PRD §5.5):
- 2 Warehouses (华南仓, 华东仓)
- 3 Carriers (A=cheap/slow, B=balanced, C=expensive/fast)
- 5 Customers (at least 1 VIP)
- 10 Orders
- 30 Shipments (≥7 delayed, ≥3 VIP/premium)
- 0–3 ExceptionCases

---

## 7. Evaluation Framework

**3 modes** (PRD §12.1):
- **Mode A — Pure LLM:** static business description, no tools
- **Mode B — LLM + SQL:** read-only SQL query tool, no Ontology semantic layer
- **Mode C — OntoPilot:** full Runtime (context, query, functions, actions, governance, simulation)

**5 auto-evaluated metrics** (PRD §12.2):
1. Data accuracy (object IDs exist in store)
2. Tool path correctness (expected tools called)
3. Permission compliance (denied operations rejected)
4. Action confirmation rate (high-risk actions enter `pending_confirmation`)
5. Audit coverage (every operation has trace + audit)

**10 test cases** (PRD §12.3, case_01 through case_10, including 3 adversarial cases).

---

## 8. Frontend UX

Three-panel layout (PRD §19.1):
- **Left:** ChatPanel — user input, message history, role selector
- **Center:** TracePanel — real-time collapsible trace events per layer
- **Right:** SimulationPanel — KPI comparison table (activates on simulation events)

5-step guided tour (PRD §19.2) implemented as tooltips/highlights.

---

## 9. Success Criteria

Matches PRD §18 exactly:
- **P0:** CLI runs ≥3 cases with trace events, audit logs, permission enforcement
- **P1:** LLM uses correct tools, object IDs from store, risk from Function not hallucinated
- **P2:** Decision comparison with KPI table and simulation assumptions
- **P3:** Non-technical audience can follow the 5-layer interaction in the UI
