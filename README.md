# 🚀 AgentFlow — Autonomous Enterprise Workflow Engine

> **8 AI agents** that work together to complete real enterprise tasks end-to-end. When things break, they fix themselves. When it matters, they ask you first.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-agent--flow--amber.vercel.app-blue?style=for-the-badge)](https://agent-flow-amber.vercel.app)
[![Backend API](https://img.shields.io/badge/API-Render-purple?style=for-the-badge)](https://agentflow-api-788z.onrender.com)

---

## 🌐 Live Demo

| Component | URL |
|-----------|-----|
| **Dashboard** | [https://agent-flow-amber.vercel.app](https://agent-flow-amber.vercel.app) |
| **Backend API** | [https://agentflow-api-788z.onrender.com](https://agentflow-api-788z.onrender.com) |
| **API Docs** | [https://agentflow-api-788z.onrender.com/docs](https://agentflow-api-788z.onrender.com/docs) |

> ⚠️ **Note**: The backend runs on Render free tier and sleeps after 15 minutes of inactivity. First request after sleep takes ~30–50 seconds to wake up. Visit the API URL first, then open the dashboard.

---

## What It Does

AgentFlow takes a business task — like onboarding a new employee, processing meeting action items, or handling a stuck approval — and **completes it end-to-end using 8 AI agents working together**.

Each agent has a specific job:

| # | Agent | What It Does |
|---|---|---|
| 1 | **Signal Ingestor** | Takes in the problem — who, what, when. Runs security scans. |
| 2 | **Root Cause Analyzer** | Checks enterprise systems to diagnose what's wrong |
| 3 | **Strategy Planner** | Creates a step-by-step action plan |
| 4 | **GPA Evaluator** | Scores the plan quality from 1.0 to 4.0 |
| 5 | **Human Review (HITL)** | You approve, reject, or ask questions |
| 6 | **Execution Engine** | Calls HR, JIRA, Slack, Calendar, etc. with self-healing |
| 7 | **Escalation Handler** | Routes failures to the right human authority |
| 8 | **Vernacular Reporter** | Creates a bilingual Hindi + English summary |

---

## What Makes It Different

### 🔧 Self-Healing
When a tool fails (API timeout, access denied, rate limit), agents **automatically retry with different strategies** — exponential backoff, credential rotation, and graceful degradation. The dashboard shows you the exact error code and what recovery action was taken.

### 👁️ Full Transparency
Every decision, every tool call, every API response is logged in a **live audit trail**. No black box. You see exactly what the AI decided and why — in real-time on the dashboard.

### 🧑 Human-in-the-Loop (HITL)
Before running critical actions, the system **pauses and asks for your approval**. You can approve, reject, or ask clarifying questions. High-confidence plans (GPA ≥ 3.5) can auto-approve to demonstrate full autonomy. If no human responds within 5 minutes, the system auto-escalates.

### 🛡️ Edge Case Engine (11 Categories, 51+ Cases)
A centralized engine detects and handles edge cases in real-time — from duplicate identity detection to circular delegation loops, prompt injection blocking to stale state detection.

### 💰 ₹0 API Cost
Runs on **Google Gemini AI (free tier)**. Uses a dual-model strategy — lightweight model (Flash Lite) for simple extraction, capable model (Flash 2.5) for deep reasoning. Zero API spend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) (stateful directed agent graph) |
| **LLM** | Google Gemini 2.5 Flash + 3.1 Flash Lite (dual-tier routing) |
| **Backend** | FastAPI + WebSocket (real-time streaming) |
| **Frontend** | React (Vite) — real-time agent pipeline dashboard |
| **Database** | SQLite (8 tables — audit trail, workflow state, security events) |
| **Deployment** | Vercel (frontend) + Render (backend) |
| **Language** | Python 3.11 / JavaScript (ES2022) |

---

## 🖥️ Run Locally (Step-by-Step Setup)

### Prerequisites
- **Python 3.9+** installed
- **Node.js 18+** and **npm** installed
- **Google Gemini API key** (free) — get one at [Google AI Studio](https://aistudio.google.com/apikey)

### Step 1: Clone the Repository

```bash
git clone https://github.com/bhaskarkarn1/AgentFlow.git
cd AgentFlow
```

### Step 2: Backend Setup

```bash
# Create a Python virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt

# Create environment file with your Gemini API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

> **Important**: Replace `your_api_key_here` with your actual Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). The free tier is sufficient.

### Step 3: Start the Backend Server

```bash
python api_server.py
```

You should see:
```
Starting AgentFlow API Server v2.0 on port 8000...
API Docs:  http://0.0.0.0:8000/docs
```

### Step 4: Start the Dashboard (New Terminal)

```bash
cd dashboard
npm install
npm run dev
```

You should see:
```
  VITE v6.x.x  ready in XXms
  ➜  Local:   http://localhost:5173/
```

### Step 5: Open and Use

1. **Open** `http://localhost:5173` in your browser
2. The dashboard should show **"Connected"** (green badge) — this means it's talking to the backend
3. **Pick a scenario** from the dropdown (Employee Onboarding, Meeting-to-Action, or SLA Breach)
4. **Click "Launch Mission"** — watch the 8 agents process in real-time
5. **Approve at the HITL gate** — the system pauses for your review before executing
6. **See the results** — full audit trail, edge case detection, self-healing report, and bilingual summary

### Optional: Clean Demo State

```bash
# Delete the database to start fresh (from the project root)
rm -f enterprise.db
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Dashboard shows "Disconnected" | Make sure `python api_server.py` is running on port 8000 |
| "GOOGLE_API_KEY not found" | Check `.env` file exists and has the correct key |
| Agents fail with "model not found" | Your API key may not have access to Gemini 2.5 Flash / 3.1 Flash Lite — check [Google AI Studio](https://aistudio.google.com/) |
| `npm install` fails | Make sure Node.js 18+ is installed: `node --version` |
| Port 8000 already in use | Kill existing process: `lsof -ti:8000 | xargs kill` |

---

## 📋 Scenarios

### 👤 Employee Onboarding
A new employee joins. Agents create their HR record, JIRA account, Slack workspace invite, assign a buddy, schedule orientation meetings, and send a welcome pack — with duplicate detection, identity validation, and ghost entity detection.

### 📋 Meeting-to-Action
Paste a meeting transcript. Agents extract action items, assign owners, **explicitly flag ambiguous items** for human clarification (HITL), create JIRA tasks, and send summaries to all participants.

### ⚡ SLA Breach Prevention
A procurement approval is stuck because the approver is on leave. Agents identify the bottleneck, find an authorized delegate, detect circular delegation loops, reroute the approval, and log the override with full compliance audit.

---

## 🏗️ Architecture

```
Input → Signal Ingestor → Root Cause Analyzer → Strategy Planner → GPA Evaluator
                                                                        ↓
                                                                  Human Review (HITL)
                                                                        ↓
Report ← Compliance Auditor ← Execution Engine (with Self-Healing Loop)
                                    ↕                    ↕
                             [HR] [JIRA] [Slack]    [Escalation Handler]
                             [Calendar] [ERP]       (routes to authority)
```

**For a detailed architecture document, see [`ARCHITECTURE.md`](ARCHITECTURE.md).**

---

## 🛡️ Edge Case Coverage (11 Categories)

| Category | Edge Cases |
|----------|-----------| 
| Identity & Entity | Duplicate names, name variations, missing fields, ghost entities, cross-system inconsistency |
| Workflow Deadlock | Circuit breaker, HITL timeout, planner loop detection, circular dependency, plan overflow |
| Race Conditions | Duplicate workflow prevention, idempotency keys, workflow lock/release |
| Partial Failure | State consistency checker, dependency failure tracking, partial completion |
| Tool/API Failure | 403, 429, 504, auth expiry, credential rotation, error classification |
| LLM Guardrails | Hallucinated tool detection, plan validation, grade validation, contradictory reasoning |
| Security | Prompt injection (20+ patterns), SQL injection, sensitive data masking |
| HITL Resilience | 5-min timeout + auto-escalation, WebSocket reconnection, auto-approve for GPA ≥ 3.5 |
| Audit & Compliance | Full audit log, edge case log, workflow state persistence, tool call tracing |
| System & Infra | Crash recovery, state persistence, graceful LLM fallback to rule-based logic |
| Scenario-Specific | Conflicting dates, out-of-band resolution, ambiguous ownership, circular delegation |

---

## 💰 Impact Model

| Scenario | Before (Manual) | After (AgentFlow) | Annual Savings |
|----------|-----------------|-------------------|----------------|
| Employee Onboarding | 4–6 hours/hire | < 2 minutes | **₹15,00,000/year** |
| Meeting-to-Action | 45 min follow-up | < 1 minute | **₹6,00,000/year** |
| SLA Breach Prevention | 24–48 hrs routing | < 2 minutes | **₹45,00,000/year** |
| **Total** | | | **₹66,00,000+/year** |

**Assumptions**: 200 hires/year, 600 meetings/year, 12 SLA-critical approvals/year, ₹1,500/hr avg cost.

**For detailed calculations, see [`IMPACT_MODEL.md`](IMPACT_MODEL.md).**

---

## 📁 Project Structure

```
AgentFlow/
├── api_server.py              # FastAPI server + LangGraph pipeline + WebSocket
├── render.yaml                # Render deployment configuration
├── requirements.txt           # Python dependencies
├── ARCHITECTURE.md            # Detailed architecture document (submission)
├── IMPACT_MODEL.md            # Business impact analysis (submission)
├── agents/
│   ├── ingestor.py            # Agent 1: Signal Ingestion
│   ├── diagnostic.py          # Agent 2: Root Cause Analysis
│   ├── planner.py             # Agent 3: Strategy Planning
│   ├── grader.py              # Agent 4: GPA Quality Evaluation
│   ├── escalation.py          # Agent 5: Escalation Handler
│   ├── vernacular.py          # Agent 6: Bilingual Report Generator
│   ├── tools.py               # Enterprise tool connectors (with failure injection)
│   ├── edge_case_engine.py    # 11-category edge case detection engine
│   ├── database.py            # SQLite persistence (8 tables, audit trail)
│   ├── llm_factory.py         # Dual-tier LLM cost optimizer
│   └── registry.py            # Agent state schema (TypedDict)
└── dashboard/                 # React frontend (Vite)
    ├── src/
    │   ├── App.jsx            # Main dashboard application
    │   ├── index.css          # Design system
    │   └── hooks/
    │       └── useAgentFlow.js  # WebSocket hook + API client
    ├── package.json
    └── vite.config.js
```

---

## 📎 Submission Documents

| Document | Description | Link |
|----------|-------------|------|
| **Architecture** | Agent roles, communication, tool integrations, error handling | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Impact Model** | Quantified business impact with assumptions | [`IMPACT_MODEL.md`](IMPACT_MODEL.md) |
| **Live Demo** | Working public URL for evaluation | [agent-flow-amber.vercel.app](https://agent-flow-amber.vercel.app) |
| **Source Code** | This repository with full commit history | [GitHub](https://github.com/bhaskarkarn1/AgentFlow) |

---

## License

MIT

---

*Built for ET AI Hackathon 2026*
