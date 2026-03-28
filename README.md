# AgentFlow — Autonomous Enterprise Workflow System

> 8 AI agents that work together to complete real enterprise tasks. When things break, they fix themselves. When it matters, they ask you first.

---

## What It Does

AgentFlow takes a business task — like onboarding a new employee, processing meeting action items, or handling a stuck approval — and **completes it end-to-end using 8 AI agents working together**.

Each agent has a specific job:

| # | Agent | What It Does |
|---|---|---|
| 1 | **Read Input** | Takes in the problem — who, what, when |
| 2 | **Find Problem** | Checks what's wrong or missing |
| 3 | **Build Plan** | Creates a step-by-step action list |
| 4 | **Quality Check** | Scores the plan from 1.0 to 4.0 |
| 5 | **Human Review** | You approve, reject, or ask questions |
| 6 | **Run Tasks** | Calls HR, JIRA, Slack, Calendar, etc. |
| 7 | **Audit & Log** | Records every decision for compliance |
| 8 | **Write Report** | Creates a bilingual summary report |

## What Makes It Different

### 🔧 Self-Healing
When a tool fails (API timeout, access denied, rate limit), agents **automatically retry with different strategies**. The dashboard shows you the exact error code and what recovery action was taken.

### 👁️ Full Transparency
Every decision, every tool call, every API response is logged in a **live audit trail**. You see exactly what happened and why. No black box.

### 🧑 Human Stays in Control
Before running critical actions, the system **pauses and asks for your approval**. You can approve, reject, or ask clarifying questions. High-confidence plans (GPA ≥ 3.5) can be auto-approved to demonstrate full autonomy.

### 🛡️ Edge Case Engine (11 Categories)
A centralized engine detects and handles 11 categories of edge cases in real-time — from identity conflicts to deadlock prevention, race conditions to security threats.

### ₹0 API Cost
Runs on **Google Gemini AI (free tier)**. Uses a dual-model strategy — lightweight model for simple tasks, capable model for complex reasoning.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) (directed agent graph) |
| **LLM** | Google Gemini 2.5 Flash + 3.1 Flash Lite (dual-tier) |
| **Backend** | FastAPI + WebSocket (real-time streaming) |
| **Frontend** | React (Vite) |
| **Database** | SQLite (8 tables, persistent audit trail) |
| **Language** | Python 3.9+ / JavaScript |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd agentflow
```

### 2. Backend Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey).

### 3. Start the API Server

```bash
python api_server.py
```

The server starts at `http://localhost:8000`.

### 4. Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

The dashboard opens at `http://localhost:5173`.

---

## How to Use

1. **Open the dashboard** at `http://localhost:5173`
2. **Pick a scenario** — Employee Onboarding, Meeting-to-Action, or SLA Breach Prevention
3. **Customize the inputs** — or use the defaults to test
4. **Hit "Launch Mission"** — watch the agents process in real-time
5. **Approve at HITL gate** — the system pauses for your review before executing
6. **See the results** — full audit trail, self-healing report, and bilingual summary

---

## Scenarios

### 👤 Employee Onboarding
A new employee joins. Agents create their HR record, JIRA account, Slack workspace invite, assign a buddy, schedule orientation meetings, and send a welcome pack.

### 📋 Meeting-to-Action
Paste a meeting transcript. Agents extract action items, assign owners, identify ambiguous items (flagged for human clarification), and create tracking tasks.

### ⚡ SLA Breach Prevention
A procurement approval is stuck because the approver is unavailable. Agents identify the bottleneck, find an authorized delegate, reroute the approval, and log the override with full compliance audit.

---

## Architecture

```
Input → Read Input → Find Problem → Build Plan → Quality Check
                                                       ↓
                                                 Human Review
                                                       ↓
Report ← Audit & Log ← Run Tasks (with Self-Healing Loop)
                            ↕               ↕
                     [HR] [JIRA] [Slack]  [Escalation Handler]
                     [Calendar] [Email]   (routes to authority)
```

- **LangGraph DAG**: Agents are nodes in a directed graph. Data flows from one to the next.
- **Self-Healing**: The Run Tasks agent retries failed tool calls with exponential backoff and credential rotation.
- **HITL Gate**: Execution is paused for human approval before any critical actions are run.
- **Auto-Approve**: Plans scoring GPA ≥ 3.5 with no flags bypass the HITL gate automatically.
- **Escalation Handler**: When max retries are exhausted, routes to the appropriate human authority.
- **WebSocket Streaming**: Every agent event is streamed to the dashboard in real-time.

---

## Edge Case Coverage (11 Categories)

| Category | Edge Cases |
|----------|-----------|
| 🔴 Identity & Entity | Duplicate names, name variations, missing fields, ghost entities, cross-system inconsistency, partial existence |
| 🔴 Workflow Deadlock | Circuit breaker, HITL timeout, planner loop detection, circular dependency, plan size overflow |
| 🔴 Race Conditions | Duplicate workflow prevention, idempotency keys, workflow lock/release |
| 🔴 Partial Failure | State consistency checker, dependency failure tracking, partial completion |
| 🔴 Tool/API Failure | 403, 429, 504, auth expiry, malformed response, credential rotation, error classification |
| 🔴 LLM Guardrails | Hallucinated tool detection, plan validation, grade validation, contradictory reasoning |
| 🔴 Audit & Compliance | Full audit log, edge case log, workflow state persistence, tool call tracing |
| 🔴 Security | Prompt injection (20+ patterns), SQL injection, sensitive data masking, input sanitization |
| 🔴 HITL Resilience | Timeout + auto-escalation, WebSocket reconnection, pending event buffer, auto-approve |
| 🔴 System & Infra | Crash recovery, state persistence, graceful degradation (LLM fallbacks) |
| 🔴 Scenario-Specific | Conflicting join dates, out-of-band approval resolution, ambiguous ownership, simultaneous resolution |

---

## Impact Model

| Scenario | Before (Manual) | After (AgentFlow) | Per-Task Savings | Annualized |
|----------|-----------------|-------------------|-----------------|------------|
| Employee Onboarding | 4-6 hours | <2 minutes | ~5.5 hrs/employee | ₹16,50,000/year |
| Meeting-to-Action | 45 min follow-up | <1 minute | ~44 min/meeting | ₹6,60,000/year |
| SLA Breach Prevention | 24-48 hrs routing | <2 minutes | ₹5L/day penalty avoided | ₹60,00,000/year |

**Assumptions**: 200 hires/year, 600 meetings/year, 12 SLA-critical approvals/year, ₹1,500/hr avg cost.

---

## Project Structure

```
agentflow/
├── api_server.py           # FastAPI server + LangGraph pipeline + WebSocket streaming
├── agents/
│   ├── ingestor.py         # Signal Ingestion Agent
│   ├── diagnostic.py       # Root Cause Analysis Agent
│   ├── planner.py          # Strategy Planning Agent
│   ├── grader.py           # Plan Quality Evaluator (GPA)
│   ├── escalation.py       # Escalation Handler Agent
│   ├── vernacular.py       # Bilingual Report Generator
│   ├── tools.py            # Enterprise tool simulations (with failures)
│   ├── edge_case_engine.py # 11-category edge case detection engine
│   ├── database.py         # SQLite persistence layer (8 tables)
│   ├── llm_factory.py      # Dual-model LLM cost optimizer
│   └── registry.py         # Agent state schema
├── dashboard/              # React frontend (Vite)
│   └── src/
│       ├── App.jsx         # Main application
│       ├── index.css       # Design system
│       └── hooks/
│           └── useAgentFlow.js  # WebSocket hook
└── requirements.txt
```

---

## License

MIT

---

*Built for ET AI Hackathon 2026*
