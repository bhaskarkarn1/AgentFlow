# AgentFlow — System Architecture

> Multi-Agent Enterprise Workflow Orchestrator | ET AI Hackathon 2026

---

## High-Level Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │              React Dashboard (Vite)             │
                    │  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
                    │  │ Scenario │ │  Agent   │ │  Edge Case &   │  │
                    │  │ Selector │ │ Pipeline │ │ Self-Healing   │  │
                    │  │ + Config │ │ Timeline │ │   Panels       │  │
                    │  └──────────┘ └──────────┘ └────────────────┘  │
                    └───────────────────┬─────────────────────────────┘
                                        │ WebSocket (real-time events)
                                        │ REST API (commands)
                    ┌───────────────────▼─────────────────────────────┐
                    │           FastAPI Backend (api_server.py)        │
                    │                                                  │
                    │  ┌──────────────────────────────────────────┐    │
                    │  │         LangGraph Stateful DAG           │    │
                    │  │                                          │    │
                    │  │  ┌─────────┐   ┌──────────┐             │    │
                    │  │  │ Signal  │──▶│Root Cause│             │    │
                    │  │  │Ingestor │   │ Analyzer │             │    │
                    │  │  └─────────┘   └────┬─────┘             │    │
                    │  │                     ▼                    │    │
                    │  │              ┌──────────┐               │    │
                    │  │              │ Strategy │               │    │
                    │  │              │ Planner  │               │    │
                    │  │              └────┬─────┘               │    │
                    │  │                   ▼                     │    │
                    │  │              ┌──────────┐               │    │
                    │  │              │Agent GPA │               │    │
                    │  │              │Evaluator │◄─── Loop ───┐ │    │
                    │  │              └────┬─────┘             │ │    │
                    │  │                   ▼                   │ │    │
                    │  │              ┌──────────┐             │ │    │
                    │  │              │  HITL    │ (Human      │ │    │
                    │  │              │  Gate    │  Approval)  │ │    │
                    │  │              └────┬─────┘             │ │    │
                    │  │                   ▼                   │ │    │
                    │  │  ┌──────────┐ ┌────────┐ ┌────────┐  │ │    │
                    │  │  │Execution │ │Escalat.│ │Complia.│  │ │    │
                    │  │  │  Engine  │ │Handler │ │ Auditor│  │ │    │
                    │  │  └────┬─────┘ └────────┘ └────────┘  │ │    │
                    │  │       ▼                               │ │    │
                    │  │  ┌──────────┐                         │ │    │
                    │  │  │Vernacular│  (Bilingual Report)     │ │    │
                    │  │  │ Agent    │                         │ │    │
                    │  │  └──────────┘                         │ │    │
                    │  └──────────────────────────────────────────┘    │
                    │                                                  │
                    │  ┌──────────────┐  ┌────────────────────────┐    │
                    │  │ Edge Case    │  │  Enterprise Tool       │    │
                    │  │ Engine       │  │  Connectors            │    │
                    │  │ (11 cats,    │  │  ┌────┐┌────┐┌──────┐ │    │
                    │  │  51+ cases)  │  │  │ HR ││JIRA││Slack │ │    │
                    │  └──────────────┘  │  ├────┤├────┤├──────┤ │    │
                    │                    │  │Cal.││ERP ││Apprvl│ │    │
                    │  ┌──────────────┐  │  └────┘└────┘└──────┘ │    │
                    │  │ LLM Factory  │  └────────────────────────┘    │
                    │  │ (Dual-Tier)  │                                │
                    │  │ Light: Flash │  ┌────────────────────────┐    │
                    │  │ Heavy: 2.5   │  │ SQLite Persistence     │    │
                    │  └──────────────┘  │ (8 tables, audit log)  │    │
                    │                    └────────────────────────┘    │
                    └──────────────────────────────────────────────────┘
```

---

## Agent Roles & Communication

AgentFlow uses **LangGraph** to orchestrate 8 specialized agents as nodes in a directed acyclic graph (DAG). Each agent receives the full workflow state, performs its task, and passes enriched state to the next agent.

### Agent Pipeline

| # | Agent | Model Tier | Role | Key Capability |
|---|-------|-----------|------|----------------|
| 1 | **Signal Ingestor** | Light (Flash Lite) | Parse input signal, extract entities, classify urgency | Security scanning, identity validation, duplicate detection |
| 2 | **Root Cause Analyzer** | Heavy (Flash 2.5) | Query enterprise tools, diagnose root cause | Cross-system conflict detection, ghost entity detection |
| 3 | **Strategy Planner** | Heavy (Flash 2.5) | Generate multi-step execution plan | Hallucinated tool detection, circular dependency check |
| 4 | **Agent GPA Evaluator** | Heavy (Flash 2.5) | Score plan quality (0.0–4.0 GPA) | Contradictory reasoning detection, ambiguity flagging |
| 5 | **HITL Gate** | None (Logic) | Pause for human approval/rejection | 5-min timeout → auto-escalation, WebSocket-based |
| 6 | **Execution Engine** | None (Tool Calls) | Execute plan steps via enterprise tools | Self-healing: exponential backoff, credential rotation |
| 7 | **Escalation Handler** | Light (Flash Lite) | Route failures to appropriate authority | Circular delegation detection, authority verification |
| 8 | **Vernacular Reporter** | Light (Flash Lite) | Generate bilingual Hindi+English report | Includes edge case summary, compliance status |

### Communication Pattern

- **State Passing**: Agents communicate via a shared `AgentState` (TypedDict) passed through LangGraph edges
- **WebSocket Broadcasting**: Every agent start/complete event is broadcast to the dashboard in real-time
- **Conditional Routing**: LangGraph conditional edges route to Escalation Handler on failure, or loop Planner↔Grader if GPA < 2.0
- **HITL Interrupt**: LangGraph's `interrupt_before` mechanism pauses execution at the HITL gate

---

## Tool Integrations

| Tool | System | Operations | Failure Modes Simulated |
|------|--------|-----------|------------------------|
| HR System | Employee records | Create record, assign buddy, get status | 403 Forbidden, partial existence |
| JIRA | Project tracker | Create account, create task, verify access | 503 Service Unavailable, auth expiry |
| Communication | Slack/Email | Send invites, notifications, summaries | 429 Rate Limit |
| Calendar | Scheduling | Schedule orientation, meetings | Conflict detection |
| Approval System | Procurement | Check status, get delegates, reroute | Circular delegation, insufficient authority |
| ERP | Finance | Purchase orders, budget queries | 504 Gateway Timeout |

Each tool implements **realistic failure injection** to demonstrate autonomous recovery.

---

## Error Handling & Self-Healing

### 3-Layer Defense

```
Layer 1: PREVENTION
├── Input security scanning (20+ injection patterns)
├── Duplicate workflow prevention (race condition guard)
├── LLM output validation (hallucinated tool detection)
└── Plan size limits (context overflow prevention)

Layer 2: RECOVERY
├── Exponential backoff for transient errors (429, 502, 503, 504)
├── Credential rotation for auth failures (403)
├── LLM fallback to rule-based extraction on model failure
└── Circuit breaker (max 5 retries per action)

Layer 3: ESCALATION
├── Route to appropriate human authority on unrecoverable failure
├── Circular delegation detection → escalate to higher authority
├── HITL timeout (5 min) → auto-escalate to supervisor
└── Full audit trail for post-mortem analysis
```

### Edge Case Engine (11 Categories, 51+ Cases)

| Category | Examples |
|----------|----------|
| Identity & Entity | Duplicate names, ghost managers, cross-system inconsistency |
| Workflow Deadlock | Circuit breaker, planner loop detection, HITL timeout |
| Race Conditions | Duplicate workflow prevention, idempotency guards |
| Tool/API Failure | HTTP 403/429/504, auth expiry, credential rotation |
| LLM Guardrails | Hallucinated tools, contradictory reasoning, missing fields |
| Security | Prompt injection (20+ patterns), SQL injection, data masking |
| State Consistency | Partial completion, dependency failure, stale state |

---

## Data Persistence

SQLite database with 8 tables:

| Table | Purpose |
|-------|---------|
| `employees` | Employee records (onboarding) |
| `audit_logs` | Complete decision audit trail |
| `workflow_states` | Checkpoint/recovery state |
| `edge_case_log` | Edge case detection history |
| `security_events` | Security threat log |
| `tool_call_log` | Every tool invocation with result |
| `jira_tasks` | JIRA task tracking |
| `approval_chains` | Approval routing audit |

---

## Deployment Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   Vercel (CDN)  │         │  Render (Free)   │
│                 │  HTTPS  │                  │
│  React/Vite     │────────▶│  FastAPI +       │
│  Static Build   │  WSS    │  Uvicorn +       │
│                 │◀────────│  LangGraph +     │
│  Dashboard UI   │         │  SQLite          │
└─────────────────┘         └────────┬─────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ Google Gemini AI │
                            │ (Free Tier API)  │
                            └─────────────────┘
```

| Component | URL | Notes |
|-----------|-----|-------|
| Frontend | `https://agent-flow-amber.vercel.app` | Auto-deploys from GitHub `main` branch |
| Backend | `https://agentflow-api-788z.onrender.com` | Sleeps after 15 min inactivity (free tier) |
| API Docs | `https://agentflow-api-788z.onrender.com/docs` | Interactive Swagger UI |

---

## Cost-Efficient LLM Routing

```
┌─────────────────────────────────────────┐
│           LLM Factory (Dual-Tier)       │
│                                         │
│  ┌──────────────┐  ┌────────────────┐   │
│  │  Light Tier   │  │  Heavy Tier    │   │
│  │  Flash Lite   │  │  Flash 2.5    │   │
│  │              │  │               │   │
│  │  • Ingestor  │  │  • Diagnostic │   │
│  │  • Escalation│  │  • Planner    │   │
│  │  • Vernacular│  │  • Grader     │   │
│  │              │  │               │   │
│  │  Fast, cheap │  │  Deep reason  │   │
│  └──────────────┘  └────────────────┘   │
│                                         │
│  Total API Cost: ₹0 (Google Free Tier)  │
└─────────────────────────────────────────┘
```

---

*AgentFlow — Built for ET AI Hackathon 2026*
