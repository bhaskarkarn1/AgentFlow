import { useState, useEffect, useCallback, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws') + '/ws';

export function useAgentFlow() {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('idle');
  const [scenario, setScenario] = useState(null);
  const [taskId, setTaskId] = useState('');
  const [logs, setLogs] = useState([]);
  const [reasoning, setReasoning] = useState('');
  const [hitlData, setHitlData] = useState(null);
  const [pipelineState, setPipelineState] = useState({});
  const [metrics, setMetrics] = useState({ time: 0, cost: 0, steps: 0, totalSteps: 0, lightCalls: 0, heavyCalls: 0 });
  const [report, setReport] = useState('');
  const [executionResults, setExecutionResults] = useState([]);
  const [healingEvents, setHealingEvents] = useState([]);
  const [activeStep, setActiveStep] = useState(null);
  const [scenarioData, setScenarioData] = useState(null);

  // NEW: Edge case tracking
  const [edgeCases, setEdgeCases] = useState([]);
  const [edgeCaseSummary, setEdgeCaseSummary] = useState(null);
  const [hitlCountdown, setHitlCountdown] = useState(null);

  const wsRef = useRef(null);
  const startTimeRef = useRef(null);
  const timerRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pendingEventsRef = useRef([]);

  useEffect(() => {
    if (status === 'running' || status === 'hitl') {
      timerRef.current = setInterval(() => {
        if (startTimeRef.current) {
          const elapsed = (Date.now() - startTimeRef.current) / 1000;
          setMetrics(m => ({ ...m, time: Math.round(elapsed) }));
        }
      }, 100);
    } else if (status === 'completed') {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [status]);

  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(WS_URL);
        ws.onopen = () => {
          setConnected(true);
          // Flush any pending events
          if (pendingEventsRef.current.length > 0) {
            pendingEventsRef.current.forEach(msg => {
              try { ws.send(JSON.stringify(msg)); } catch(e) {}
            });
            pendingEventsRef.current = [];
          }
        };
        ws.onclose = () => {
          setConnected(false);
          // Auto-reconnect with exponential backoff
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connect, 2000);
        };
        ws.onerror = () => {
          // Error handler — reconnection is handled by onclose
        };
        ws.onmessage = (event) => handleMessage(JSON.parse(event.data));
        wsRef.current = ws;
      } catch (e) {
        // Connection failed — retry
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      }
    };
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, []);

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'workflow_start':
        setStatus('running');
        startTimeRef.current = Date.now();
        setTaskId(msg.task_id || '');
        setScenarioData(msg.scenario_data || null);
        setEdgeCases([]);
        setEdgeCaseSummary(null);
        setHitlCountdown(null);
        addLog('info', `🚀 Workflow started: ${msg.scenario} (${msg.task_id})`);
        break;

      case 'agent_start':
        setPipelineState(prev => ({ ...prev, [msg.node]: 'active' }));
        setActiveStep({ agent: msg.agent, node: msg.node });
        addLog('info', `🤖 ${msg.agent} activated`);
        if (msg.description) {
          addLog('info', `   ↳ ${msg.description}`);
        }
        setReasoning(prev => prev + `\n▸ ${msg.agent}\n  ${msg.description || 'Processing...'}\n`);
        break;

      case 'agent_complete':
        setPipelineState(prev => ({ ...prev, [msg.node]: 'completed' }));
        setMetrics(m => ({ ...m, steps: m.steps + 1 }));
        setActiveStep(null);
        if (msg.reasoning_summary?.length > 0) {
          msg.reasoning_summary.forEach(line => {
            setReasoning(prev => prev + `  ${line}\n`);
            if (line.includes('[') || line.includes('Generated Plan') || line.includes('Grade')) {
              const logType = line.includes('FAIL') || line.includes('ERROR') || line.includes('❌') ? 'error'
                : line.includes('SUCCESS') || line.includes('✅') ? 'success'
                : line.includes('Ambiguity') || line.includes('ESCALATION') || line.includes('⚠️') || line.includes('EDGE CASE') ? 'warning'
                : line.includes('🛡️') || line.includes('SECURITY') ? 'security'
                : line.includes('🔍') || line.includes('DUPLICATE') || line.includes('GHOST') ? 'edge-case' : 'info';
              addLog(logType, line);
            }
          });
        }
        if (msg.action_items_preview?.length > 0) {
          addLog('info', `📐 Action Plan Generated (${msg.action_items_preview.length} steps):`);
          msg.action_items_preview.forEach(item => {
            addLog('info', `   ${item.step}. [${item.tool}] ${item.description}`);
          });
        }
        if (msg.healing_events?.length > 0) {
          setHealingEvents(prev => [...prev, ...msg.healing_events]);
        }
        setReasoning(prev => prev + `  ✓ ${msg.agent} complete\n`);
        break;

      // NEW: Edge case detection events
      case 'edge_cases_detected': {
        const newCases = msg.edge_cases || [];
        setEdgeCases(prev => [...prev, ...newCases]);
        newCases.forEach(ec => {
          const icon = ec.severity === 'CRITICAL' ? '🔴' : ec.severity === 'HIGH' ? '🟠' : ec.severity === 'MEDIUM' ? '🟡' : '🔵';
          addLog('edge-case', `${icon} EDGE CASE [${ec.type}]: ${ec.message}`);
        });
        break;
      }

      case 'step_start': {
        const paramsStr = msg.params ? ` → ${JSON.stringify(msg.params).substring(0, 150)}` : '';
        addLog('info', `⚙️ [${msg.step_index || msg.step}/${msg.total_steps || '?'}] Calling ${msg.tool}.${msg.action}()`);
        addLog('info', `   ↳ ${msg.description}${paramsStr}`);
        setActiveStep({ step: msg.step, description: msg.description, tool: msg.tool });
        break;
      }

      case 'step_complete': {
        const responseStr = msg.response ? JSON.stringify(msg.response).substring(0, 200) : '';
        if (msg.attempt > 1) {
          addLog('success', `✅ Step ${msg.step}: ${msg.description} — RECOVERED on attempt ${msg.attempt}`);
        } else {
          addLog('success', `✅ Step ${msg.step}: ${msg.description} — Success`);
        }
        if (responseStr) {
          addLog('success', `   ↳ Response: ${responseStr}`);
        }
        break;
      }

      case 'step_fail': {
        addLog('error', `❌ Step ${msg.step}: ${msg.description} — FAILED`);
        addLog('error', `   ↳ Error: ${msg.error}`);
        if (msg.error_detail) {
          addLog('warning', `   ↳ Detail: ${msg.error_detail.substring(0, 200)}`);
        }
        if (msg.will_retry) {
          addLog('warning', `   🔄 Self-healing: Retrying (attempt ${msg.attempt + 1}/${msg.max_attempts})...`);
        } else {
          addLog('error', `   🚨 Max retries exhausted. Flagging for escalation.`);
        }
        setHealingEvents(prev => {
          const filtered = prev.filter(e => !(e.step === msg.step && e.status === 'retrying'));
          return [...filtered, {
            step: msg.step,
            description: msg.description,
            error: msg.error,
            error_detail: msg.error_detail || '',
            attempt: msg.attempt,
            max_attempts: msg.max_attempts,
            status: msg.will_retry ? 'retrying' : 'failed',
          }];
        });
        break;
      }

      case 'hitl_gate':
        setHitlData(msg);
        setPipelineState(prev => ({ ...prev, 'HITL_Gate': 'active' }));
        if (msg.auto_approved) {
          // Auto-approved — show briefly then clear
          setReasoning(prev => prev + `\n⚡ HUMAN REVIEW GATE\n  🤖 Plan auto-approved (GPA ≥ 3.5, no flags)\n`);
          addLog('success', '🤖 Auto-approved — plan scored high confidence, skipping manual review');
        } else {
          setStatus('hitl');
          setReasoning(prev => prev + `\n⚡ HUMAN REVIEW GATE\n  Awaiting supervisor decision...\n`);
          addLog('warning', '⚡ Human Review gate — Execution paused, awaiting human approval');
        }
        if (msg.edge_cases_count > 0) {
          addLog('edge-case', `   🔍 ${msg.edge_cases_count} edge cases detected during analysis`);
        }
        // Start countdown
        if (msg.hitl_timeout_seconds) {
          setHitlCountdown(msg.hitl_timeout_seconds);
        }
        break;

      // NEW: HITL countdown updates
      case 'hitl_countdown':
        setHitlCountdown(msg.remaining_seconds);
        break;

      // NEW: HITL timeout
      case 'hitl_timeout':
        addLog('warning', `⏰ HITL TIMEOUT: ${msg.message}`);
        setEdgeCases(prev => [...prev, {
          type: 'HITL_TIMEOUT', severity: 'HIGH',
          message: msg.message, handled: true
        }]);
        setHitlCountdown(0);
        break;

      case 'hitl_approved':
        setHitlData(null);
        setStatus('running');
        setPipelineState(prev => ({ ...prev, 'HITL_Gate': 'completed' }));
        if (msg.auto) {
          setReasoning(prev => prev + `  ✓ Auto-approved (high confidence). Proceeding to execution...\n`);
          addLog('success', '✅ Plan auto-approved by Agent Grader — proceeding with action plan');
        } else {
          setReasoning(prev => prev + `  ✓ Approved. Proceeding to execution...\n`);
          addLog('success', '✅ Execution approved by supervisor — proceeding with action plan');
        }
        setHitlCountdown(null);
        break;

      case 'workflow_complete':
        setStatus('completed');
        setReport(msg.report || '');
        setExecutionResults(msg.execution_results || []);
        if (msg.model_usage) {
          setMetrics(m => ({
            ...m,
            cost: msg.model_usage.total_cost_inr || 0,
            lightCalls: msg.model_usage.light_model_calls || 0,
            heavyCalls: msg.model_usage.heavy_model_calls || 0,
          }));
        }
        if (msg.edge_case_summary) {
          setEdgeCaseSummary(msg.edge_case_summary);
        }
        setHealingEvents(prev =>
          prev.map(e => e.status === 'retrying' ? { ...e, status: 'recovered' } : e)
        );
        setReasoning(prev => prev + `\n🎉 MISSION COMPLETE\n`);
        addLog('success', '🎉 Workflow completed successfully — all steps audited and logged');
        if (msg.edge_cases_total > 0) {
          addLog('edge-case', `🔍 Total edge cases handled: ${msg.edge_cases_total}`);
        }
        setHitlCountdown(null);
        break;

      case 'workflow_abort':
        setStatus('idle');
        addLog('error', 'Workflow aborted by supervisor');
        setHitlCountdown(null);
        break;

      case 'error':
        addLog('error', `System error: ${msg.message}`);
        break;
    }
  }, []);

  const addLog = useCallback((type, text) => {
    setLogs(prev => [...prev, { id: Date.now() + Math.random(), type, text, time: new Date() }]);
  }, []);

  const startScenario = useCallback(async (scenarioName, config = {}) => {
    setScenario(scenarioName);
    setStatus('running');
    startTimeRef.current = Date.now();
    setLogs([]);
    setReasoning('Initializing AgentFlow pipeline...\n');
    setReport('');
    setPipelineState({});
    setExecutionResults([]);
    setHealingEvents([]);
    setActiveStep(null);
    setEdgeCases([]);
    setEdgeCaseSummary(null);
    setHitlCountdown(null);

    try {
      const res = await fetch(`${API_URL}/api/start/${scenarioName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config }),
      });
      const data = await res.json();
      if (data.error) {
        addLog('error', data.error);
        if (data.edge_case) {
          addLog('edge-case', `🔍 Edge case prevented: ${data.edge_case}`);
          setEdgeCases(prev => [...prev, { type: data.edge_case, severity: 'HIGH', message: data.error }]);
        }
        setStatus('idle');
      }
    } catch (e) {
      addLog('error', `Failed to start: ${e.message}`);
      setStatus('idle');
    }
  }, []);

  const approve = useCallback((clarification = '') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'approve', clarification }));
    } else {
      // Buffer for reconnection
      pendingEventsRef.current.push({ type: 'approve', clarification });
    }
  }, []);

  const abort = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'abort' }));
    }
    setStatus('idle');
    setHitlData(null);
    setHitlCountdown(null);
  }, []);

  const reset = useCallback(() => {
    setStatus('idle');
    setScenario(null);
    setTaskId('');
    setLogs([]);
    setReasoning('');
    setReport('');
    setHitlData(null);
    setPipelineState({});
    setExecutionResults([]);
    setHealingEvents([]);
    setMetrics({ time: 0, cost: 0, steps: 0, totalSteps: 0, lightCalls: 0, heavyCalls: 0 });
    setActiveStep(null);
    setScenarioData(null);
    setEdgeCases([]);
    setEdgeCaseSummary(null);
    setHitlCountdown(null);
  }, []);

  return {
    connected, status, scenario, taskId, logs, reasoning, hitlData, pipelineState,
    metrics, report, executionResults, healingEvents, activeStep, scenarioData,
    edgeCases, edgeCaseSummary, hitlCountdown,
    startScenario, approve, abort, reset,
  };
}
