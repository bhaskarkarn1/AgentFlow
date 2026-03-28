import { useState, useEffect, useRef } from 'react'
import { useAgentFlow } from './hooks/useAgentFlow'
import './index.css'

const SCENARIOS = [
  { id: 'onboarding', title: 'Employee Onboarding', icon: '👤', steps: 6,
    description: 'New hire joins. Create accounts across HR, JIRA, Slack. Handle system errors with retry & escalation.',
    fields: [
      { key: 'employee_name', label: 'Employee Name', default: 'Priya Sharma', placeholder: 'e.g. Rahul Verma' },
      { key: 'role', label: 'Role / Designation', default: 'SDE-II', placeholder: 'e.g. Product Manager' },
      { key: 'department', label: 'Department', default: 'Engineering', placeholder: 'e.g. Marketing' },
      { key: 'start_date', label: 'Start Date', default: '2026-04-01', type: 'date' },
    ]},
  { id: 'meeting', title: 'Meeting-to-Action', icon: '📋', steps: 3,
    description: 'Extract action items from transcript. Assign owners. Flag ambiguous items for human clarification.',
    fields: [
      { key: 'meeting_title', label: 'Meeting Title', default: 'Q1 Product Roadmap Review', placeholder: 'e.g. Sprint Planning' },
      { key: 'transcript', label: 'Meeting Transcript', default: '', type: 'textarea',
        placeholder: 'Paste your meeting transcript here, or leave blank to use a sample transcript...' },
    ]},
  { id: 'sla_breach', title: 'SLA Breach Prevention', icon: '⚡', steps: 4,
    description: 'Procurement approval stuck. Identify bottleneck, reroute to delegate, log override with compliance audit.',
    fields: [
      { key: 'item_description', label: 'Approval Item', default: 'Cloud Infrastructure Upgrade', placeholder: 'e.g. Software License Renewal' },
      { key: 'current_approver', label: 'Stuck Approver', default: 'Meera Shankar (VP Operations)', placeholder: 'e.g. John Smith (Director)' },
      { key: 'reason_stuck', label: 'Reason Stuck', default: 'Medical Leave', placeholder: 'e.g. On Vacation, Unresponsive' },
      { key: 'hours_stuck', label: 'Hours Since Submission', default: '48', type: 'number' },
      { key: 'sla_deadline_hours', label: 'SLA Deadline (hours)', default: '72', type: 'number' },
    ]},
]

const PIPELINE_NODES = [
  { key: 'Signal_Ingestion_Claw', label: 'Read Input', icon: '📡', desc: 'Understands the request' },
  { key: 'Root_Cause_Agent', label: 'Find Problem', icon: '🔍', desc: 'Diagnoses root cause' },
  { key: 'Strategy_Planner', label: 'Build Plan', icon: '📐', desc: 'Creates action steps' },
  { key: 'Agent_Grader', label: 'Quality Check', icon: '🎓', desc: 'Scores plan quality' },
  { key: 'HITL_Gate', label: 'Human Review', icon: '🧑', desc: 'You approve or reject' },
  { key: 'Execution_Agent', label: 'Run Tasks', icon: '⚙️', desc: 'Calls enterprise tools' },
  { key: 'Escalation_Handler', label: 'Escalation', icon: '🚨', desc: 'Routes to human authority' },
  { key: 'Compliance_Auditor', label: 'Audit & Log', icon: '📋', desc: 'Records every decision' },
  { key: 'Vernacular_Specialist', label: 'Write Report', icon: '🌐', desc: 'Final summary' },
]

const IMPACT_MODELS = {
  onboarding: {
    metric: 'Time Saved',
    before: '4-6 hours manual',
    after: '<2 minutes automated',
    savings: '~5.5 hrs/employee',
    annual: '1,100 hrs/year (for 200 new hires)',
    costSaved: '₹16,50,000/year',
    assumptions: 'Based on 200 new hires/year, ₹1,500/hr avg HR cost, 80% automation rate',
  },
  meeting: {
    metric: 'Productivity Gain',
    before: '45 min manual follow-up',
    after: '<1 minute automated',
    savings: '~44 min/meeting',
    annual: '440 hrs/year (for 600 meetings)',
    costSaved: '₹6,60,000/year',
    assumptions: 'Based on 600 team meetings/year, ₹1,500/hr avg employee cost',
  },
  sla_breach: {
    metric: 'Revenue Protected',
    before: '24-48 hr manual rerouting',
    after: '<2 minutes automated',
    savings: '₹5,00,000/day penalty avoided',
    annual: '₹60,00,000/year avoided',
    costSaved: '₹60,00,000/year',
    assumptions: 'Based on 12 SLA-critical approvals/year, ₹5L/day penalty rate',
  },
}

const ARCH_ROW1 = [
  { icon: '📡', label: 'Read Input', desc: 'Takes in the problem — who, what, when' },
  { icon: '🔍', label: 'Find Problem', desc: 'Figures out what is wrong or missing' },
  { icon: '📐', label: 'Build Plan', desc: 'Creates a step-by-step action list' },
  { icon: '🎓', label: 'Quality Check', desc: 'Scores the plan from 1.0 to 4.0' },
]

const ARCH_ROW2 = [
  { icon: '🧑', label: 'Human Review', desc: 'You approve, reject, or ask questions' },
  { icon: '⚙️', label: 'Run Tasks', desc: 'Calls HR, JIRA, Slack, Calendar, etc.' },
  { icon: '📋', label: 'Audit & Log', desc: 'Records every decision for compliance' },
  { icon: '🌐', label: 'Write Report', desc: 'Creates a bilingual summary report' },
]

const DIFFERENTIATORS = [
  {
    icon: '🔧', title: 'Self-Healing',
    desc: 'When a tool fails — API timeout, access denied, rate limit hit — agents automatically retry with different strategies. No human needed.',
  },
  {
    icon: '👁️', title: 'Full Transparency',
    desc: 'Every decision, every tool call, every response is logged in a live audit trail. You see exactly what happened and why. No black box.',
  },
  {
    icon: '🧑', title: 'Human Stays in Control',
    desc: 'Before running any critical action, the system pauses and asks for your approval. Nothing happens without your OK.',
  },
  {
    icon: '🛡️', title: 'Edge Case Engine',
    desc: '11 categories of edge cases handled: identity conflicts, deadlocks, race conditions, security threats, partial failures, and more.',
  },
]

const EDGE_CASE_ICONS = {
  'CRITICAL': '🔴',
  'HIGH': '🟠',
  'MEDIUM': '🟡',
  'LOW': '🔵',
  'INFO': '⚪',
}

function App() {
  const {
    connected, status, scenario, taskId, logs, reasoning, hitlData, pipelineState,
    metrics, report, executionResults, healingEvents, activeStep,
    edgeCases, edgeCaseSummary, hitlCountdown,
    startScenario, approve, abort, reset,
  } = useAgentFlow()

  const [configMode, setConfigMode] = useState(null)
  const [formValues, setFormValues] = useState({})
  const [clarification, setClarification] = useState('')
  const logEndRef = useRef(null)
  const reasoningEndRef = useRef(null)

  // Enterprise Database state
  const [dbTables, setDbTables] = useState([])
  const [dbTableData, setDbTableData] = useState(null)
  const [dbLoading, setDbLoading] = useState(false)
  const [showDbBrowser, setShowDbBrowser] = useState(false)

  // Dashboard panel tab state
  const [rightPanelTab, setRightPanelTab] = useState('reasoning')

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    reasoningEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [reasoning])

  // Auto-switch to report when completed
  useEffect(() => {
    if (status === 'completed' && report) {
      setRightPanelTab('report')
    } else if (status === 'running' || status === 'hitl') {
      setRightPanelTab('reasoning')
    }
  }, [status, report])

  const DB_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const fetchTables = async () => {
    setDbLoading(true)
    try {
      const res = await fetch(`${DB_API}/api/database/tables`)
      const data = await res.json()
      setDbTables(data)
    } catch (e) { console.error('Failed to fetch tables:', e) }
    setDbLoading(false)
  }

  const fetchTableData = async (tableName) => {
    setDbLoading(true)
    try {
      const res = await fetch(`${DB_API}/api/database/table/${tableName}`)
      const data = await res.json()
      setDbTableData(data)
    } catch (e) { console.error('Failed to fetch table data:', e) }
    setDbLoading(false)
  }

  const openDbBrowser = () => {
    setShowDbBrowser(true)
    setDbTableData(null)
    fetchTables()
  }

  const statusLabel = {
    idle: 'STANDBY', running: 'PROCESSING', hitl: 'AWAITING HUMAN', completed: 'MISSION COMPLETE',
  }

  const handleCardClick = (s) => {
    setConfigMode(s)
    const defaults = {}
    s.fields.forEach(f => { defaults[f.key] = f.default || '' })
    setFormValues(defaults)
  }

  const handleLaunch = () => {
    startScenario(configMode.id, formValues)
    setConfigMode(null)
  }

  // ==========================================
  // SCREEN 1: Landing Page
  // ==========================================
  if (status === 'idle' && !scenario && !configMode) {
    return (
      <div className="landing-page">
        <Header status="idle" statusLabel="STANDBY" connected={connected} />

        {/* ——— HERO SECTION ——— */}
        <section className="hero-section">
          <div className="hero-content">
            <div className="hero-badge">Multi-Agent AI System</div>
            <h1 className="hero-title">AgentFlow</h1>
            <p className="hero-tagline">Your AI Operations Team</p>
            <p className="hero-desc">
              8 AI agents work together to complete real enterprise tasks like <span className="glow-text">employee onboarding, meeting follow-ups, and approval routing</span> from start to finish. When things break, they fix themselves. When it matters, they ask you first.
            </p>
            <div className="hero-usp">
              <span className="hero-usp-label">What this does:</span>
              Takes a business task → Plans the solution → Runs it across your company tools → Handles failures automatically → Gives you a complete report
            </div>
            <div className="hero-stats-row">
              <div className="hero-stat">
                <div className="hero-stat-value">8</div>
                <div className="hero-stat-label">AI Agents</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-value">11</div>
                <div className="hero-stat-label">Edge Cases</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-value">100%</div>
                <div className="hero-stat-label">Auditable</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-value">₹0</div>
                <div className="hero-stat-label">API Cost</div>
              </div>
            </div>
            <a className="hero-cta" href="#architecture">See How It Works ↓</a>
          </div>
        </section>

        {/* ——— ARCHITECTURE SECTION ——— */}
        <section className="arch-section" id="architecture">
          <h2 className="section-title">How 8 AI Agents Work Together</h2>
          <p className="section-desc">
            Each agent has one specific job. Data flows from one agent to the next.
            If something fails, the system heals itself and retries.
          </p>

          <div className="arch-diagram">
            {/* ROW 1: Agents 1-4 */}
            <div className="arch-row">
              {ARCH_ROW1.map((node, i) => (
                <div className="arch-row-item" key={i}>
                  <div className="arch-node">
                    <div className="arch-node-num">{i + 1}</div>
                    <div className="arch-node-icon">{node.icon}</div>
                    <div className="arch-node-label">{node.label}</div>
                    <div className="arch-node-desc">{node.desc}</div>
                  </div>
                  {i < 3 && <div className="arch-edge-h"><div className="arch-edge-flow" /></div>}
                </div>
              ))}
            </div>

            {/* VERTICAL CONNECTOR */}
            <div className="arch-vertical-connector">
              <div className="arch-edge-v"><div className="arch-edge-flow-v" /></div>
            </div>

            {/* ROW 2: Agents 5-8 */}
            <div className="arch-row arch-row-reverse">
              {ARCH_ROW2.map((node, i) => (
                <div className="arch-row-item" key={i}>
                  <div className={`arch-node ${i === 1 ? 'arch-node-healing' : ''}`}>
                    <div className="arch-node-num">{i + 5}</div>
                    <div className="arch-node-icon">{node.icon}</div>
                    <div className="arch-node-label">{node.label}</div>
                    <div className="arch-node-desc">{node.desc}</div>
                  </div>
                  {i < 3 && <div className="arch-edge-h"><div className="arch-edge-flow" /></div>}
                </div>
              ))}
            </div>

            {/* SELF-HEALING ANNOTATION */}
            <div className="arch-healing-label">
              <div className="arch-healing-icon">🔄</div>
              <div>
                <strong>Self-Healing Loop</strong>
                <span>When a tool fails, the "Run Tasks" agent retries automatically with a different strategy</span>
              </div>
            </div>

            {/* TOOLS ROW */}
            <div className="arch-tools-row">
              <div className="arch-tools-label">Connected Enterprise Tools:</div>
              <div className="arch-tools-list">
                <span className="arch-tool">🏢 HR System</span>
                <span className="arch-tool">📌 JIRA</span>
                <span className="arch-tool">💬 Slack</span>
                <span className="arch-tool">📅 Calendar</span>
                <span className="arch-tool">📧 Email</span>
              </div>
            </div>
          </div>
        </section>

        {/* ——— DIFFERENTIATORS SECTION ——— */}
        <section className="diff-section">
          <h2 className="section-title">What Makes This Different?</h2>
          <p className="section-desc">
            Most AI tools answer questions. AgentFlow takes action.
            It connects to your real systems and gets actual work done.
          </p>
          <div className="diff-cards">
            {DIFFERENTIATORS.map((d, i) => (
              <div key={i} className="diff-card">
                <div className="diff-card-icon">{d.icon}</div>
                <div className="diff-card-title">{d.title}</div>
                <div className="diff-card-desc">{d.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ——— HOW IT WORKS SECTION ——— */}
        <section className="how-section">
          <h2 className="section-title">How to Use It</h2>
          <div className="how-steps">
            <div className="how-step">
              <div className="how-step-num">1</div>
              <div className="how-step-title">Pick a Scenario</div>
              <div className="how-step-desc">Choose from real enterprise tasks below</div>
            </div>
            <div className="how-arrow">→</div>
            <div className="how-step">
              <div className="how-step-num">2</div>
              <div className="how-step-title">Customize Inputs</div>
              <div className="how-step-desc">Enter names, dates, or any test data you want</div>
            </div>
            <div className="how-arrow">→</div>
            <div className="how-step">
              <div className="how-step-num">3</div>
              <div className="how-step-title">Watch Agents Work</div>
              <div className="how-step-desc">See every decision, every tool call, every recovery — live</div>
            </div>
          </div>
        </section>

        {/* ——— SCENARIOS SECTION ——— */}
        <section className="scenarios-section" id="scenarios">
          <h2 className="section-title">Try It Yourself</h2>
          <p className="section-desc">
            Pick a scenario. Customize the inputs with your own data. Then watch the agents handle it.
          </p>
          <div className="scenario-cards">
            {SCENARIOS.map(s => (
              <div key={s.id} className="scenario-card" onClick={() => handleCardClick(s)}>
                <div className="scenario-icon">{s.icon}</div>
                <div className="scenario-title">{s.title}</div>
                <div className="scenario-desc">{s.description}</div>
                <div className="scenario-steps">{s.steps} autonomous steps →</div>
              </div>
            ))}
          </div>
        </section>

        {/* ——— ENTERPRISE DATABASE SECTION ——— */}
        <section className="db-promo-section" id="enterprise-data">
          <div className="db-promo-content">
            <div className="db-promo-icon">🗄️</div>
            <h2 className="db-promo-title">Enterprise Database</h2>
            <p className="db-promo-desc">
              Real data. Not mocked responses. Every agent action securely writes to a persistent SQLite database that you can view in real time.
            </p>
            <button className="db-promo-btn" onClick={openDbBrowser}>
              <span className="btn-icon">🔍</span>
              Browse Enterprise Data
            </button>
          </div>
          <div className="db-promo-glow"></div>
        </section>

        {/* ——— DATABASE BROWSER OVERLAY ——— */}
        {showDbBrowser && (
          <div className="hitl-overlay">
            <div className="db-browser-modal">
              <div className="db-browser-header">
                <h2>🗄️ Enterprise Database Browser</h2>
                <button className="btn btn-abort" onClick={() => { setShowDbBrowser(false); setDbTableData(null) }}>✕ Close</button>
              </div>

              {!dbTableData ? (
                <div className="db-tables-grid">
                  {dbLoading ? <p style={{color: '#94a3b8'}}>Loading tables...</p> : (
                    dbTables.map(t => (
                      <div key={t.name} className="db-table-card" onClick={() => fetchTableData(t.name)}>
                        <div className="db-table-icon">
                          {t.name === 'employees' ? '👥' : t.name === 'jira_tasks' ? '📋' : t.name === 'calendar_events' ? '📅' : t.name === 'notifications' ? '📧' : t.name === 'approval_requests' ? '✅' : t.name === 'edge_case_log' ? '🔍' : t.name === 'security_events' ? '🛡️' : t.name === 'workflow_state' ? '💾' : '📊'}
                        </div>
                        <div className="db-table-name">{t.name.replace(/_/g, ' ')}</div>
                        <div className="db-table-count">{t.rows} records</div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="db-table-view">
                  <div className="db-table-back">
                    <button className="btn" onClick={() => setDbTableData(null)} style={{background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', border: 'none', padding: '8px 16px', cursor: 'pointer', borderRadius: 8}}>← Back to Tables</button>
                    <span className="db-table-label">{dbTableData.table?.replace(/_/g, ' ')} — {dbTableData.count} records</span>
                  </div>
                  <div className="db-table-scroll">
                    <table className="db-data-table">
                      <thead>
                        <tr>
                          {dbTableData.columns?.map(col => <th key={col}>{col}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {dbTableData.rows?.map((row, i) => (
                          <tr key={i} className={row.created_by === 'AGENT' ? 'agent-created' : ''}>
                            {dbTableData.columns?.map(col => (
                              <td key={col}>
                                {typeof row[col] === 'string' && row[col]?.length > 80
                                  ? row[col].substring(0, 80) + '...'
                                  : String(row[col] ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {dbTableData.rows?.some(r => r.created_by === 'AGENT') && (
                    <div className="db-legend">
                      <span className="db-legend-dot"></span> Rows highlighted in purple were created by AI agents during execution
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ——— FOOTER ——— */}
        <footer className="landing-footer">
          <div>Built with LangGraph + Gemini AI + React + SQLite · ET AI Hackathon 2026</div>
        </footer>
      </div>
    )
  }

  // ==========================================
  // SCREEN 2: Configuration Form
  // ==========================================
  if (configMode && status === 'idle') {
    return (
      <>
        <Header status="idle" statusLabel="CONFIGURING" connected={connected} />
        <div className="config-screen">
          <div className="config-card">
            <div className="config-header">
              <span className="config-icon">{configMode.icon}</span>
              <div>
                <h2 className="config-title">{configMode.title}</h2>
                <p className="config-desc">{configMode.description}</p>
              </div>
            </div>

            <div className="config-form">
              <div className="config-form-title">Customize Scenario Inputs</div>
              <p className="config-form-sub">Edit any field below to test with your own data, or use the defaults.</p>

              {configMode.fields.map(field => (
                <div key={field.key} className="form-group">
                  <label className="form-label">{field.label}</label>
                  {field.type === 'textarea' ? (
                    <textarea
                      className="form-input form-textarea"
                      value={formValues[field.key] || ''}
                      onChange={e => setFormValues(v => ({...v, [field.key]: e.target.value}))}
                      placeholder={field.placeholder}
                      rows={5}
                    />
                  ) : (
                    <input
                      className="form-input"
                      type={field.type || 'text'}
                      value={formValues[field.key] || ''}
                      onChange={e => setFormValues(v => ({...v, [field.key]: e.target.value}))}
                      placeholder={field.placeholder}
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="config-actions">
              <button className="btn btn-approve btn-launch" onClick={handleLaunch}>
                ⚡ Launch Mission
              </button>
              <button className="btn btn-back" onClick={() => setConfigMode(null)}>
                ← Back
              </button>
            </div>
          </div>
        </div>
      </>
    )
  }

  // ==========================================
  // SCREEN 3: Active Dashboard
  // ==========================================
  const currentScenario = SCENARIOS.find(s => s.id === scenario)
  const completedNodes = Object.values(pipelineState).filter(v => v === 'completed').length

  // Edge case severity counts
  const edgeSeverity = {}
  edgeCases.forEach(ec => {
    const s = ec.severity || 'INFO'
    edgeSeverity[s] = (edgeSeverity[s] || 0) + 1
  })

  return (
    <>
      <Header status={status} statusLabel={statusLabel[status]} connected={connected} />

      {/* COMPLETION BANNER */}
      {status === 'completed' && (
        <div className="completion-banner">
          <div className="completion-inner">
            <div className="completion-icon">✅</div>
            <div className="completion-text">
              <div className="completion-title">MISSION COMPLETE</div>
              <div className="completion-sub">All {currentScenario?.steps || '?'} steps executed autonomously in {metrics.time}s</div>
            </div>
            <div className="completion-metrics">
              <div className="completion-metric">
                <span className="completion-metric-value">{metrics.time}s</span>
                <span className="completion-metric-label">Time</span>
              </div>
              <div className="completion-metric">
                <span className="completion-metric-value">{healingEvents.length}</span>
                <span className="completion-metric-label">Failures Healed</span>
              </div>
              <div className="completion-metric">
                <span className="completion-metric-value">{edgeCases.length}</span>
                <span className="completion-metric-label">Edge Cases</span>
              </div>
              <div className="completion-metric">
                <span className="completion-metric-value">₹{metrics.cost.toFixed(2)}</span>
                <span className="completion-metric-label">API Cost</span>
              </div>
            </div>
          </div>
          {/* IMPACT MODEL - Required by hackathon submission */}
          {scenario && IMPACT_MODELS[scenario] && (
            <div className="impact-model">
              <div className="impact-model-header">
                <span className="impact-model-icon">📈</span>
                <span className="impact-model-title">Business Impact Model</span>
              </div>
              <div className="impact-model-grid">
                <div className="impact-item">
                  <div className="impact-label">Before (Manual)</div>
                  <div className="impact-value before">{IMPACT_MODELS[scenario].before}</div>
                </div>
                <div className="impact-item">
                  <div className="impact-label">After (AgentFlow)</div>
                  <div className="impact-value after">{IMPACT_MODELS[scenario].after}</div>
                </div>
                <div className="impact-item">
                  <div className="impact-label">Per-Task Savings</div>
                  <div className="impact-value">{IMPACT_MODELS[scenario].savings}</div>
                </div>
                <div className="impact-item highlight">
                  <div className="impact-label">Annualized Savings</div>
                  <div className="impact-value">{IMPACT_MODELS[scenario].costSaved}</div>
                </div>
              </div>
              <div className="impact-assumptions">
                💡 Assumptions: {IMPACT_MODELS[scenario].assumptions}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="dashboard">
        {/* LEFT: Mission + Self-Healing + Edge Cases */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-header-icon">📋</span>
            <span className="panel-header-title">Mission Brief</span>
          </div>
          <div className="panel-body">
            {currentScenario && (
              <>
                <div className="mission-card">
                  <div className="mission-label">Scenario</div>
                  <div className="mission-value highlight">{currentScenario.icon} {currentScenario.title}</div>
                </div>
                {taskId && (
                  <div className="mission-card">
                    <div className="mission-label">Task ID</div>
                    <div className="mission-value" style={{fontFamily: "'JetBrains Mono', monospace", fontSize: 13}}>{taskId}</div>
                  </div>
                )}
                <div className="mission-card">
                  <div className="mission-label">Progress</div>
                  <div className="progress-bar-container">
                    <div className="progress-bar" style={{width: `${(completedNodes / PIPELINE_NODES.length) * 100}%`}} />
                  </div>
                  <div className="mission-value" style={{fontSize: 12, marginTop: 4, color: status === 'completed' ? 'var(--success)' : 'var(--info)'}}>
                    {completedNodes}/{PIPELINE_NODES.length} agents completed
                  </div>
                </div>
              </>
            )}

            {/* EDGE CASE PANEL */}
            <div className="healing-section">
              <div className="healing-title">🔍 Edge Case Engine</div>
              {edgeCases.length === 0 ? (
                <div className="healing-empty">
                  {status === 'completed' ? '✅ No edge cases detected — clean execution' : 'Monitoring for edge cases...'}
                </div>
              ) : (
                <>
                  <div className="edge-case-summary-bar">
                    {Object.entries(edgeSeverity).sort(([a], [b]) => {
                      const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 }
                      return (order[a] ?? 5) - (order[b] ?? 5)
                    }).map(([sev, count]) => (
                      <span key={sev} className={`edge-severity-badge severity-${sev.toLowerCase()}`}>
                        {EDGE_CASE_ICONS[sev]} {count} {sev}
                      </span>
                    ))}
                  </div>
                  <div className="edge-case-list">
                    {edgeCases.slice(-8).map((ec, i) => (
                      <div key={i} className={`edge-case-item severity-${(ec.severity || 'info').toLowerCase()}-bg`}>
                        <div className="edge-case-header">
                          <span>{EDGE_CASE_ICONS[ec.severity] || '⚪'} {ec.type?.replace(/_/g, ' ')}</span>
                          <span className={`edge-case-badge ${ec.handled ? 'handled' : 'unhandled'}`}>
                            {ec.handled ? '✓ HANDLED' : '⚠ PENDING'}
                          </span>
                        </div>
                        <div className="edge-case-message">{ec.message}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* SELF-HEALING REPORT */}
            <div className="healing-section">
              <div className="healing-title">🔧 Self-Healing Report</div>
              {healingEvents.length === 0 ? (
                <div className="healing-empty">
                  {status === 'completed' ? '✅ No failures detected — flawless execution' : 'Monitoring for failures...'}
                </div>
              ) : (
                healingEvents.map((evt, i) => {
                  const isRecovered = evt.recovered === true || evt.status === 'recovered';
                  const isRetrying = evt.status === 'retrying';
                  return (
                    <div key={i} className={`healing-event ${isRecovered ? 'healed' : isRetrying ? 'retrying' : 'failed'}`}>
                      <div className="healing-event-header">
                        <span>{isRecovered ? '✅' : isRetrying ? '🔄' : '🚨'} Step {evt.step}</span>
                        <span className={`healing-badge ${isRecovered ? 'recovered' : isRetrying ? 'retrying-badge' : 'escalated'}`}>
                          {isRecovered ? 'RECOVERED' : isRetrying ? 'RETRYING' : 'ESCALATED'}
                        </span>
                      </div>
                      <div className="healing-event-desc">{evt.description}</div>
                      <div className="healing-event-error">❌ {evt.error}</div>
                      {evt.error_detail && (
                        <div className="healing-event-detail">{evt.error_detail}</div>
                      )}
                      <div className="healing-event-fix">
                        {evt.recovery_action
                          ? `💡 ${evt.recovery_action}`
                          : isRecovered
                            ? `✅ Auto-healed on attempt ${evt.attempts || evt.attempt + 1}`
                            : isRetrying
                              ? `🔄 Retrying (attempt ${evt.attempt + 1}/${evt.max_attempts})...`
                              : `🚨 Escalated after ${evt.attempts || evt.max_attempts} attempts`}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {(status === 'completed') && (
              <button className="btn btn-back" style={{marginTop: 16}} onClick={reset}>← New Scenario</button>
            )}
          </div>
        </div>

        {/* CENTER: Task Ledger */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-header-icon">📜</span>
            <span className="panel-header-title">Task Ledger — Live Audit Trail</span>
            {status === 'running' && activeStep && (
              <span className="active-indicator">⚙️ {activeStep.agent || activeStep.description}</span>
            )}
          </div>
          <div className="panel-body">
            {logs.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📜</div>
                <div className="empty-state-text">Waiting for agent activity...</div>
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={log.id} className="log-entry">
                  <div className={`log-number ${log.type}`}>{i + 1}</div>
                  <div className="log-content">{log.text}</div>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>

        {/* RIGHT: Agent Reasoning / Edge Cases / Report */}
        <div className="panel" style={{borderRight: 'none'}}>
          <div className="panel-header">
            <span className="panel-header-icon">{rightPanelTab === 'report' ? '📊' : rightPanelTab === 'edge-cases' ? '🔍' : '🧠'}</span>
            <span className="panel-header-title">{rightPanelTab === 'report' ? 'Final Report' : rightPanelTab === 'edge-cases' ? 'Edge Cases' : 'Agent Reasoning'}</span>
            <div className="panel-tabs">
              <button className={`panel-tab ${rightPanelTab === 'reasoning' ? 'active' : ''}`} onClick={() => setRightPanelTab('reasoning')}>🧠</button>
              <button className={`panel-tab ${rightPanelTab === 'edge-cases' ? 'active' : ''}`} onClick={() => setRightPanelTab('edge-cases')}>
                🔍{edgeCases.length > 0 && <span className="tab-badge">{edgeCases.length}</span>}
              </button>
              {report && <button className={`panel-tab ${rightPanelTab === 'report' ? 'active' : ''}`} onClick={() => setRightPanelTab('report')}>📊</button>}
            </div>
          </div>
          <div className="panel-body">
            {rightPanelTab === 'report' && report ? (
              <div className="report-container">
                {report.split('\n').map((line, i) => {
                  const trimmed = line.trim();
                  if (!trimmed) return <div key={i} className="report-spacer" />;
                  if (trimmed.startsWith('# ') || trimmed.startsWith('## ') || trimmed.match(/^[A-Zऀ-ॿ].{3,}:?$/) || trimmed.match(/^\d+\..+Summary/) || trimmed.startsWith('---')) {
                    return <h3 key={i} className="report-heading">{trimmed.replace(/^#+\s*/, '').replace(/^---+$/, '')}</h3>;
                  }
                  if (trimmed.startsWith('✅') || trimmed.startsWith('❌') || trimmed.startsWith('⚠️') || trimmed.startsWith('🔍') || trimmed.startsWith('📊') || trimmed.startsWith('💡')) {
                    return <div key={i} className="report-status-line">{trimmed}</div>;
                  }
                  if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.match(/^\d+\./)) {
                    return <div key={i} className="report-bullet">{trimmed}</div>;
                  }
                  if (trimmed.startsWith('|')) {
                    return <div key={i} className="report-table-line">{trimmed}</div>;
                  }
                  return <div key={i} className="report-line">{trimmed}</div>;
                })}
              </div>
            ) : rightPanelTab === 'edge-cases' ? (
              <div className="edge-cases-full">
                {edgeCases.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">🔍</div>
                    <div className="empty-state-text">No edge cases detected yet</div>
                  </div>
                ) : (
                  <>
                    <div className="edge-cases-header">
                      <div className="edge-cases-count">{edgeCases.length} edge cases detected</div>
                      <div className="edge-case-summary-bar">
                        {Object.entries(edgeSeverity).map(([sev, count]) => (
                          <span key={sev} className={`edge-severity-badge severity-${sev.toLowerCase()}`}>
                            {EDGE_CASE_ICONS[sev]} {count}
                          </span>
                        ))}
                      </div>
                    </div>
                    {edgeCases.map((ec, i) => (
                      <div key={i} className={`edge-case-detail severity-${(ec.severity || 'info').toLowerCase()}-bg`}>
                        <div className="edge-case-detail-header">
                          <span className="edge-case-detail-icon">{EDGE_CASE_ICONS[ec.severity] || '⚪'}</span>
                          <span className="edge-case-detail-type">{ec.type?.replace(/_/g, ' ')}</span>
                          <span className={`edge-case-badge ${ec.handled ? 'handled' : 'unhandled'}`}>
                            {ec.handled ? '✓ HANDLED' : '⚠️ PENDING'}
                          </span>
                        </div>
                        <div className="edge-case-detail-message">{ec.message}</div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            ) : reasoning ? (
              <div className="reasoning-text">
                {reasoning}
                <div ref={reasoningEndRef} />
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🧠</div>
                <div className="empty-state-text">Agent chain-of-thought will appear here...</div>
              </div>
            )}
          </div>
        </div>

        {/* BOTTOM: Agent Flow Graph */}
        <div className="flow-graph-bar">
          <div className="flow-graph-nodes">
            {PIPELINE_NODES.map((node, i) => {
              const state = pipelineState[node.key] || 'waiting';
              const nextState = i < PIPELINE_NODES.length - 1 ? (pipelineState[PIPELINE_NODES[i+1].key] || 'waiting') : 'waiting';
              const edgeActive = state === 'completed' && (nextState === 'active' || nextState === 'completed');
              return (
                <div className="flow-graph-segment" key={node.key}>
                  <div className={`flow-node ${state}`} title={node.desc}>
                    <div className="flow-node-icon">
                      {state === 'completed' ? '✓' : state === 'active' ? '●' : node.icon}
                    </div>
                    <div className="flow-node-label">{node.label}</div>
                    {state === 'active' && <div className="flow-node-desc">{node.desc}</div>}
                  </div>
                  {i < PIPELINE_NODES.length - 1 && (
                    <div className={`flow-edge ${edgeActive ? 'edge-active' : state === 'completed' && nextState === 'waiting' ? 'edge-next' : ''}`}>
                      <div className="flow-edge-line" />
                      <div className="flow-edge-arrow">›</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {/* Self-Healing + Edge Case indicator */}
          {(healingEvents.length > 0 || edgeCases.length > 0) && (
            <div className="flow-healing-strip">
              {healingEvents.length > 0 && (
                <span>🔧 Self-Healing: {healingEvents.filter(e => e.status === 'recovered' || e.recovered === true).length}/{healingEvents.length} recovered</span>
              )}
              {edgeCases.length > 0 && (
                <span style={{marginLeft: healingEvents.length > 0 ? 16 : 0}}>🔍 Edge Cases: {edgeCases.length} detected, {edgeCases.filter(e => e.handled).length} handled</span>
              )}
            </div>
          )}
          <div className="metrics-bar">
            <div className="metric">
              <span className="metric-icon">⏱️</span>
              <span className="metric-label">Elapsed</span>
              <span className="metric-value time">{metrics.time}s</span>
            </div>
            <div className="metric">
              <span className="metric-icon">💰</span>
              <span className="metric-label">API Cost</span>
              <span className="metric-value cost">₹{metrics.cost.toFixed(2)}</span>
            </div>
            <div className="metric">
              <span className="metric-icon">🔧</span>
              <span className="metric-label">Healed</span>
              <span className="metric-value" style={{color: healingEvents.length > 0 ? 'var(--warning)' : 'var(--success)'}}>
                {healingEvents.filter(e => e.recovered !== false).length}/{healingEvents.length || 0}
              </span>
            </div>
            <div className="metric">
              <span className="metric-icon">🔍</span>
              <span className="metric-label">Edge Cases</span>
              <span className="metric-value" style={{color: edgeCases.length > 0 ? 'var(--warning)' : 'var(--success)'}}>
                {edgeCases.length}
              </span>
            </div>
            <div className="metric">
              <span className="metric-icon">🤖</span>
              <span className="metric-label">LLM Calls</span>
              <span className="metric-value" style={{color: 'var(--accent-secondary)'}}>
                {metrics.lightCalls + metrics.heavyCalls}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* HITL Modal */}
      {hitlData && (
        <div className="hitl-overlay">
          <div className="hitl-modal">
            <div className="hitl-title">⚡ Human Review Required</div>
            <div className="hitl-subtitle">
              The agents have analyzed the situation and built an action plan.
              Review it below and decide: run it, or stop.
            </div>

            {/* HITL Countdown Timer */}
            {hitlCountdown !== null && hitlCountdown > 0 && (
              <div className="hitl-countdown">
                <div className="hitl-countdown-bar">
                  <div className="hitl-countdown-fill" style={{width: `${(hitlCountdown / 300) * 100}%`}} />
                </div>
                <div className="hitl-countdown-text">
                  ⏰ Auto-escalation in {Math.floor(hitlCountdown / 60)}:{(hitlCountdown % 60).toString().padStart(2, '0')}
                </div>
              </div>
            )}

            <div className="hitl-grade">{hitlData.grade?.substring(0, 400)}</div>

            {hitlData.clarification_needed && (
              <>
                <div className="hitl-clarification">
                  ⚠️ Clarification Needed: {hitlData.clarification_context}
                </div>
                <input
                  type="text"
                  className="hitl-input"
                  placeholder="Type your clarification here..."
                  value={clarification}
                  onChange={(e) => setClarification(e.target.value)}
                />
              </>
            )}

            {/* Auto-approval indicator */}
            {hitlData.auto_approved && (
              <div className="hitl-auto-approve">
                🤖 Plan auto-approved by Agent Grader (GPA ≥ 3.5, no flags). Proceeding automatically...
              </div>
            )}

            {/* Edge cases detected notice */}
            {hitlData.edge_cases_count > 0 && (
              <div className="hitl-edge-cases">
                🔍 {hitlData.edge_cases_count} edge case(s) detected during analysis — see Edge Case panel for details
              </div>
            )}

            <div style={{fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16}}>
              {hitlData.action_count} action steps ready to run:
            </div>
            {hitlData.action_items?.slice(0, 6).map((item, i) => (
              <div key={i} style={{fontSize: 12, color: 'var(--text-muted)', padding: '3px 0', fontFamily: "'JetBrains Mono', monospace"}}>
                {item.step}. {item.description}
              </div>
            ))}

            {!hitlData.auto_approved && (
              <div className="hitl-actions" style={{marginTop: 20}}>
                <button className="btn btn-approve" onClick={() => { approve(clarification); setClarification(''); }}>
                  ✅ Approve & Run
                </button>
                <button className="btn btn-abort" onClick={abort}>
                  🚨 Abort
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

function Header({ status, statusLabel, connected }) {
  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">⚡</div>
        <div>
          <div className="header-title">AGENTFLOW</div>
          <div className="header-subtitle">Agent Control Tower</div>
        </div>
      </div>
      <div className="header-status">
        <div className={`status-badge ${connected ? '' : 'error'}`}>
          <span className="status-dot" />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
        <div className={`status-badge ${status}`}>
          <span className="status-dot" />
          {statusLabel}
        </div>
      </div>
    </header>
  )
}

export default App
