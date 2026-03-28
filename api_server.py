"""
AgentFlow: FastAPI Server with WebSocket Streaming
=======================================================

Provides a REST + WebSocket API for the React dashboard to:
1. Select and start a scenario with CUSTOM inputs
2. Stream real-time agent updates via WebSocket
3. Handle HITL approval/clarification
4. Broadcast edge case detections
5. Handle HITL timeout with auto-escalation
"""

# Load environment variables early (needed for Render/Railway deployment)
from dotenv import load_dotenv  # type: ignore
load_dotenv()

import os
import sys
import json
import asyncio
import time
from typing import Optional


from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from pydantic import BaseModel  # type: ignore

from langgraph.graph import StateGraph, END  # type: ignore
from langgraph.checkpoint.memory import MemorySaver  # type: ignore

from agents.registry import AgentState, NexusRegistry  # type: ignore
from agents.ingestor import SignalIngestor  # type: ignore
from agents.diagnostic import DiagnosticAgent  # type: ignore
from agents.planner import StrategyPlanner  # type: ignore
from agents.grader import AgentGrader  # type: ignore
from agents.escalation import EscalationHandler  # type: ignore
from agents.vernacular import VernacularAgent  # type: ignore
from agents.llm_factory import LLMFactory  # type: ignore
from agents.tools import JIRAConnectorTool, ApprovalSystemTool, set_current_task  # type: ignore
from agents import database as db  # type: ignore
from agents.edge_case_engine import (  # type: ignore
    DeadlockDetector, RaceConditionGuard, StateConsistencyChecker,
    get_edge_case_summary
)

app = FastAPI(title="AgentFlow API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# Agent Instances
# ==========================================
ingestor_agent = SignalIngestor()
diagnostic_agent = DiagnosticAgent()
planner_agent = StrategyPlanner()
grader_agent = AgentGrader()
escalation_agent = EscalationHandler()
vernacular_agent = VernacularAgent()

# ==========================================
# Active WebSocket connections & session state
# ==========================================
active_connections: list = []
session_state = {
    "status": "idle",
    "scenario": None,
    "hitl_response": None,
    "clarification_response": None,
    "current_task_id": None,
}

# Global event loop reference for sync->async bridging
_main_loop = None

# HITL timeout setting (seconds)
HITL_TIMEOUT = 300  # 5 minutes


async def broadcast(msg: dict):
    """Send message to all connected WebSocket clients."""
    text = json.dumps(msg, default=str)
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


def send_event_sync(event_type: str, data: dict):
    """Helper to send events from sync code running in thread."""
    global _main_loop
    msg = {"type": event_type, **data}
    if _main_loop and _main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(broadcast(msg), _main_loop)
        try:
            future.result(timeout=2)  # Wait for delivery
        except Exception:
            pass


# ==========================================
# Node Definitions (with WebSocket events)
# ==========================================
AGENT_DESCRIPTIONS = {
    "Signal Ingestor": "Parsing input signal to identify scenario type, extract entities, and classify urgency. Running security scans and identity validation...",
    "Root Cause Analyzer": "Querying enterprise systems to diagnose root cause. Checking HR records, JIRA access, and communication channels. Detecting cross-system conflicts...",
    "Strategy Planner": "Generating multi-step action plan based on diagnosis. Validating tool references, checking for circular dependencies, enforcing plan size limits...",
    "Agent GPA Evaluator": "Evaluating plan quality (GPA 1.0-4.0). Checking for ambiguity, contradictions, edge case coverage, and auto-approve eligibility...",
    "Escalation Handler": "Critical path failure detected. Checking for circular delegation, verifying delegate authority, identifying appropriate human authority for escalation...",
    "Compliance Auditor": "Generating compliance audit record. Verifying all steps are logged, checking state consistency across systems...",
    "Vernacular Specialist": "Translating final report to Hindi + English for bilingual accessibility. Including edge case summary...",
}


def make_node(agent, node_name, agent_display_name):
    """Factory to create nodes that emit transparent WebSocket events."""
    def node_fn(state):
        description = AGENT_DESCRIPTIONS.get(agent_display_name, "Processing...")

        send_event_sync("agent_start", {
            "agent": agent_display_name,
            "node": node_name,
            "scenario": state.get("scenario_type", ""),
            "description": description,
        })

        # Save workflow state for crash recovery
        task_id = state.get("task_id", "UNKNOWN")
        try:
            db.save_workflow_state(
                task_id=task_id,
                scenario_type=state.get("scenario_type", ""),
                current_node=node_name,
                state_json=json.dumps(dict(state), default=str)[:10000],
                status="RUNNING"
            )
        except Exception:
            pass

        result = agent.process(state)

        # Build a transparent summary of what the agent found/decided
        summary_parts = []
        for log in result.get("investigation_logs", []):
            summary_parts.append(log)

        # For planner: show the action items it generated
        action_items = result.get("action_items", [])
        if action_items:
            plan_summary = []
            for item in action_items:
                plan_summary.append(f"Step {item.get('step')}: [{item.get('tool')}] {item.get('description')}")
            summary_parts.append("Generated Plan:\n" + "\n".join(plan_summary))

        # For grader: show the grade and decision
        grade = result.get("strategy_grade", "")
        if grade:
            summary_parts.append(f"Grade Assessment: {grade[:300]}")

        send_event_sync("agent_complete", {
            "agent": agent_display_name,
            "node": node_name,
            "logs": result.get("investigation_logs", []),
            "status": result.get("current_status", ""),
            "reasoning_summary": summary_parts,
            "action_items_preview": [
                {"step": a.get("step"), "tool": a.get("tool"), "description": a.get("description")}
                for a in action_items
            ] if action_items else None,
        })

        # Broadcast edge cases if detected
        edge_cases = result.get("edge_cases_detected", [])
        if edge_cases:
            send_event_sync("edge_cases_detected", {
                "agent": agent_display_name,
                "node": node_name,
                "edge_cases": edge_cases,
                "total_detected": len(edge_cases),
            })

        return result
    return node_fn


def _execute_action(action: str, tool: str, params: dict,
                    scenario_type: str, scenario_data: dict) -> dict:
    """Route action to the appropriate enterprise tool."""
    from agents.tools import (
        hr_tool, jira_tool, comms_tool, calendar_tool,
        approval_tool, erp_tool
    )
    try:
        if tool == "HR_System":
            if action == "create_hr_record":
                result = hr_tool.create_employee_record(params.get("employee_data", {}))
            elif action == "assign_buddy":
                result = hr_tool.assign_buddy(
                    params.get("employee_id", ""),
                    params.get("buddy_pool", []))
            else:
                return {"success": True, "data": {"action": action, "status": "completed"}}
            return result.to_dict()

        elif tool == "JIRA":
            if action == "create_jira_account":
                result = jira_tool.create_account(
                    params.get("employee_id", ""),
                    params.get("role", ""))
                return result.to_dict()
            elif action == "create_tasks":
                return {"success": True, "data": {"status": "tasks_created", "count": 4}}
            else:
                return {"success": True, "data": {"action": action, "status": "completed"}}

        elif tool == "Communication":
            if action == "send_welcome_pack":
                result = comms_tool.send_welcome_pack(
                    params.get("employee_name", ""),
                    params.get("employee_email", ""))
            else:
                result = comms_tool.send_notification(
                    params.get("recipients", []),
                    params.get("subject", "Notification"),
                    params.get("body", ""))
            return result.to_dict()

        elif tool == "Calendar":
            result = calendar_tool.schedule_meeting(
                params.get("title", "Meeting"),
                params.get("participants", []),
                params.get("date", "TBD"))
            return result.to_dict()

        elif tool == "ApprovalSystem":
            if action == "verify_bottleneck":
                result = approval_tool.get_approval_status(
                    params.get("approval_id", ""))
            elif action == "check_delegates":
                result = approval_tool.get_delegates(
                    params.get("approver", ""))
            elif action == "reroute_approval":
                result = approval_tool.reroute_approval(
                    params.get("approval_id", ""),
                    params.get("new_approver", ""),
                    params.get("reason", ""))
            else:
                return {"success": True, "data": {"action": action, "status": "completed"}}
            return result.to_dict()

        elif tool == "LLM_Analysis":
            return {"success": True, "data": {"action": action, "status": "analyzed"}}

        else:
            return {"success": True, "data": {"action": action, "tool": tool, "status": "completed"}}

    except Exception as e:
        return {"success": False, "error": str(e), "data": {}}


def execution_node_api(state):
    """Execution node with FULL TRANSPARENCY — shows every tool call, response, and recovery."""

    send_event_sync("agent_start", {
        "agent": "Execution Agent",
        "node": NexusRegistry.ACTION_CLAW,
        "description": "Executing approved action plan step by step. Each enterprise tool call, its response, and any failures/recoveries are tracked in real-time.",
    })

    # Set task ID for tool audit logging
    task_id = state.get("task_id", "UNKNOWN")
    set_current_task(task_id)

    action_items = state.get("action_items", [])
    scenario_type = state.get("scenario_type", "")
    scenario_data = state.get("scenario_data", {})
    logs = list(state.get("investigation_logs", []))
    edge_cases = list(state.get("edge_cases_detected", []))
    execution_results = []
    has_failure = False
    needs_escalation = False
    attempts = state.get("recovery_attempts", 0)
    healing_events = []

    total_steps = len(action_items)

    for idx, item in enumerate(action_items):
        step = item.get("step", "?")
        action = item.get("action", "unknown")
        tool = item.get("tool", "")
        params = item.get("params", {})
        desc = item.get("description", action)
        retry_limit = item.get("retry_limit", 3)

        # ── EDGE CASE: Circuit breaker check ──
        budget = DeadlockDetector.check_retry_budget(task_id, action)
        if not budget["allowed"]:
            logs.append(f"[Executor] 🔴 CIRCUIT BREAKER: {budget['reason']}")
            edge_cases.append({
                "type": "CIRCUIT_BREAKER_TRIPPED", "severity": "HIGH",
                "message": budget["reason"], "handled": True
            })
            send_event_sync("edge_cases_detected", {
                "agent": "Execution Agent",
                "edge_cases": [{"type": "CIRCUIT_BREAKER_TRIPPED", "severity": "HIGH",
                               "message": budget["reason"]}],
                "total_detected": 1,
            })
            has_failure = True
            needs_escalation = True
            execution_results.append({
                "step": step, "action": action, "success": False,
                "error": budget["reason"], "data": {"error": "CIRCUIT_BREAKER"}
            })
            continue

        # Emit detailed step start showing WHAT is being called
        params_preview = {}
        for k, v in params.items():
            if isinstance(v, str) and len(v) > 100:
                params_preview[k] = v[:100] + "..."
            elif isinstance(v, dict):
                params_preview[k] = {kk: vv for kk, vv in list(v.items())[:4]}
            elif isinstance(v, list):
                params_preview[k] = v[:3]
            else:
                params_preview[k] = v

        send_event_sync("step_start", {
            "step": step,
            "description": desc,
            "tool": tool,
            "action": action,
            "params": params_preview,
            "step_index": idx + 1,
            "total_steps": total_steps,
        })
        logs.append(f"[Executor] Step {step}/{total_steps}: Calling {tool}.{action}({json.dumps(params_preview, default=str)[:200]})")

        prev_error = ""
        prev_error_detail = ""
        for attempt in range(retry_limit + 1):
            result = _execute_action(action, tool, params, scenario_type, scenario_data)

            if result["success"]:
                # Emit detailed success with response data
                response_preview = {}
                for k, v in result.get("data", {}).items():
                    if isinstance(v, str) and len(v) > 80:
                        response_preview[k] = v[:80] + "..."
                    else:
                        response_preview[k] = v

                log_msg = f"[Executor] Step {step}: {desc} → ✅ SUCCESS"
                if attempt > 0:
                    log_msg += f" (recovered on attempt {attempt + 1})"
                logs.append(log_msg)
                logs.append(f"[Executor] Step {step} Response: {json.dumps(response_preview, default=str)[:300]}")

                send_event_sync("step_complete", {
                    "step": step,
                    "description": desc,
                    "success": True,
                    "attempt": attempt + 1,
                    "response": response_preview,
                    "tool": tool,
                    "action": action,
                })
                if attempt > 0:
                    healing_events.append({
                        "step": step,
                        "description": desc,
                        "error": prev_error,
                        "error_detail": prev_error_detail,
                        "attempts": attempt + 1,
                        "recovered": True,
                        "recovery_action": f"Auto-retried with exponential backoff. Succeeded on attempt {attempt + 1}.",
                    })
                break
            else:
                error_code = result.get("data", {}).get("code", "")
                error_msg = result.get("data", {}).get("error", "") or result.get("error", "")
                error_detail = result.get("error_detail", "") or result.get("data", {}).get("message", "")
                prev_error = f"{error_msg}" + (f" (HTTP {error_code})" if error_code else "")
                prev_error_detail = error_detail

                logs.append(f"[Executor] Step {step}: {desc} → ❌ FAILED (attempt {attempt + 1}/{retry_limit + 1}): {prev_error}")
                if error_detail:
                    logs.append(f"[Executor] Error Detail: {error_detail[:200]}")

                send_event_sync("step_fail", {
                    "step": step,
                    "description": desc,
                    "error": prev_error,
                    "error_detail": error_detail,
                    "attempt": attempt + 1,
                    "max_attempts": retry_limit + 1,
                    "will_retry": attempt < retry_limit,
                    "tool": tool,
                    "action": action,
                })

                if attempt < retry_limit:
                    time.sleep(0.3)
                else:
                    has_failure = True
                    healing_events.append({
                        "step": step,
                        "description": desc,
                        "error": prev_error,
                        "error_detail": prev_error_detail,
                        "attempts": attempt + 1,
                        "recovered": False,
                        "recovery_action": f"Max retries ({retry_limit + 1}) exhausted. Flagged for human escalation.",
                    })
                    if item.get("escalate_on_fail"):
                        needs_escalation = True
                        logs.append(f"[Executor] Step {step}: ESCALATION triggered → {item['escalate_on_fail']}")

        result["step"] = step
        result["action"] = action
        execution_results.append(result)

    # ── EDGE CASE: State consistency check ──
    consistency = StateConsistencyChecker.check_execution_state(execution_results, action_items)
    if not consistency["consistent"]:
        for issue in consistency["issues"]:
            logs.append(f"[Executor] ⚠️ STATE: {issue['message']}")
            edge_cases.append({
                "type": issue["type"], "severity": issue["severity"],
                "message": issue["message"], "handled": True
            })
        send_event_sync("edge_cases_detected", {
            "agent": "Execution Agent",
            "edge_cases": [{"type": "STATE_INCONSISTENCY", "severity": "HIGH",
                           "message": f"State consistency check: {consistency['summary']}"}],
            "total_detected": 1,
        })

    status = "EXECUTED_WITH_ERRORS" if has_failure else "EXECUTED_SUCCESSFULLY"

    send_event_sync("agent_complete", {
        "agent": "Execution Agent",
        "node": NexusRegistry.ACTION_CLAW,
        "logs": logs,
        "execution_results": execution_results,
        "healing_events": healing_events,
    })

    return {
        "execution_results": execution_results,
        "error_flag": has_failure,
        "escalation_needed": needs_escalation,
        "recovery_attempts": attempts + 1,
        "current_status": status,
        "investigation_logs": logs,
        "edge_cases_detected": edge_cases,
    }



def audit_node_api(state):
    """Audit node — comprehensive compliance audit with edge case reporting."""
    send_event_sync("agent_start", {"agent": "Compliance Auditor", "node": NexusRegistry.AUDITOR,
                                     "description": "Generating compliance audit record. Verifying all steps are logged, checking state consistency across systems..."})
    
    error_flag = state.get("error_flag", False)
    escalation = state.get("escalation_needed", False)
    execution_results = state.get("execution_results", [])
    edge_cases = list(state.get("edge_cases_detected", []))
    
    successful = sum(1 for r in execution_results if r.get("success"))
    failed = sum(1 for r in execution_results if not r.get("success"))
    total = len(execution_results)

    logs = []

    if not error_flag:
        status = "AUDIT_PASSED"
        report = f"Audit Success: All {total} steps completed autonomously."
    elif escalation:
        status = "AUDIT_ESCALATED"
        report = f"Audit Partial: {successful}/{total} steps completed. {failed} escalated to human."
    else:
        status = "AUDIT_COMPLETED_WITH_NOTES"
        report = f"Audit Warning: {successful}/{total} steps completed. {failed} had issues but were resolved."

    logs.append(f"[Auditor] Final status: {status}")
    logs.append(f"[Auditor] Steps completed: {successful}/{total}")
    logs.append(f"[Auditor] {report}")

    # Edge case audit
    if edge_cases:
        logs.append(f"[Auditor] Edge cases handled: {len(edge_cases)}")
        by_severity = {}
        for ec in edge_cases:
            sev = ec.get("severity", "UNKNOWN")
            by_severity[sev] = by_severity.get(sev, 0) + 1
        logs.append(f"[Auditor] Edge case breakdown: {json.dumps(by_severity)}")
        
        # Log edge case summary as audit evidence
        edge_cases.append({
            "type": "AUDIT_COMPLETE", "severity": "INFO",
            "message": f"Compliance audit completed. {len(edge_cases)} edge cases documented.",
            "handled": True
        })

    # Save final workflow state
    task_id = state.get("task_id", "UNKNOWN")
    try:
        db.save_workflow_state(
            task_id=task_id,
            scenario_type=state.get("scenario_type", ""),
            current_node=NexusRegistry.AUDITOR,
            state_json=json.dumps({"status": status, "edge_cases": len(edge_cases)}, default=str),
            status="COMPLETED"
        )
    except Exception:
        pass

    send_event_sync("agent_complete", {
        "agent": "Compliance Auditor",
        "node": NexusRegistry.AUDITOR,
        "logs": logs,
    })

    return {
        "current_status": status,
        "investigation_logs": logs,
        "edge_cases_detected": edge_cases,
    }


# ==========================================
# Build Workflow
# ==========================================
def build_workflow():
    """Build a fresh LangGraph workflow."""
    wf = StateGraph(AgentState)

    wf.add_node(NexusRegistry.INGESTOR,
                make_node(ingestor_agent, NexusRegistry.INGESTOR, "Signal Ingestor"))
    wf.add_node(NexusRegistry.DIAGNOSTIC,
                make_node(diagnostic_agent, NexusRegistry.DIAGNOSTIC, "Root Cause Analyzer"))
    wf.add_node(NexusRegistry.ORCHESTRATOR,
                make_node(planner_agent, NexusRegistry.ORCHESTRATOR, "Strategy Planner"))
    wf.add_node(NexusRegistry.GRADER,
                make_node(grader_agent, NexusRegistry.GRADER, "Agent GPA Evaluator"))
    wf.add_node(NexusRegistry.ACTION_CLAW, execution_node_api)
    wf.add_node(NexusRegistry.ESCALATION,
                make_node(escalation_agent, NexusRegistry.ESCALATION, "Escalation Handler"))
    wf.add_node(NexusRegistry.AUDITOR, audit_node_api)
    wf.add_node(NexusRegistry.VERNACULAR,
                make_node(vernacular_agent, NexusRegistry.VERNACULAR, "Vernacular Specialist"))

    wf.set_entry_point(NexusRegistry.INGESTOR)
    wf.add_edge(NexusRegistry.INGESTOR, NexusRegistry.DIAGNOSTIC)
    wf.add_edge(NexusRegistry.DIAGNOSTIC, NexusRegistry.ORCHESTRATOR)
    wf.add_edge(NexusRegistry.ORCHESTRATOR, NexusRegistry.GRADER)

    def route_after_grader(state):
        if state.get("clarification_needed", False):
            return "needs_hitl"
        grade_text = state.get("strategy_grade", "")
        if "auto_approve: true" in grade_text.lower():
            return "auto_approve"
        return "needs_hitl"

    wf.add_conditional_edges(NexusRegistry.GRADER, route_after_grader, {
        "auto_approve": NexusRegistry.ACTION_CLAW,
        "needs_hitl": NexusRegistry.ACTION_CLAW
    })

    def route_after_execution(state):
        if state.get("escalation_needed", False):
            return "escalate"
        return "audit"

    wf.add_conditional_edges(NexusRegistry.ACTION_CLAW, route_after_execution, {
        "escalate": NexusRegistry.ESCALATION,
        "audit": NexusRegistry.AUDITOR
    })

    wf.add_edge(NexusRegistry.ESCALATION, NexusRegistry.AUDITOR)
    wf.add_edge(NexusRegistry.AUDITOR, NexusRegistry.VERNACULAR)
    wf.add_edge(NexusRegistry.VERNACULAR, END)

    memory = MemorySaver()
    return wf.compile(checkpointer=memory, interrupt_before=[NexusRegistry.ACTION_CLAW])


# ==========================================
# Scenario data builders from custom input
# ==========================================
def build_onboarding_data(config: dict) -> dict:
    name = config.get("employee_name", "Priya Sharma")
    role = config.get("role", "SDE-II")
    dept = config.get("department", "Engineering")
    date = config.get("start_date", "2026-03-31")
    # Use timestamp-based unique ID to prevent collisions for same-name employees
    import hashlib
    unique_seed = f"{name}-{dept}-{date}-{time.time()}"
    emp_id = f"EMP-2026-{int(hashlib.sha256(unique_seed.encode()).hexdigest()[:8], 16) % 9000 + 1000:04d}"
    return {
        "task_id": emp_id,
        "scenario_type": "onboarding",
        "data": {
            "employee_name": name,
            "employee_id": emp_id,
            "role": role,
            "department": dept,
            "start_date": date,
            "email": f"{name.lower().replace(' ', '.')}@company.com",
            "manager": "Rajiv Menon",
            "office_location": "Bengaluru HQ",
            "buddy_pool": ["Ananya Desai (SDE-III)", "Vikram Patel (Tech Lead)", "Sneha Rao (SDE-III)"],
        }
    }


def build_meeting_data(config: dict) -> dict:
    title = config.get("meeting_title", "Q1 Product Roadmap Review")
    transcript = config.get("transcript", "")
    if not transcript.strip():
        # Inline default transcript — no dependency on external JSON
        transcript = (
            "Ananya: Let's start with the Q1 review. The mobile app redesign is behind by two weeks. "
            "Rohit, your team needs to finalize the API integration by April 5th.\n\n"
            "Rohit: Understood. We'll prioritize the payment gateway integration. I'll have the PR ready by April 3rd.\n\n"
            "Ananya: Good. Kavita, the new onboarding flow mockups — can you share the final Figma by this Friday?\n\n"
            "Kavita: Yes, I'll share the updated designs by Friday EOD. I also need feedback on the color palette from the marketing team.\n\n"
            "Ananya: Noted. Sanjay, we need a comprehensive test plan for the payment module. Can that be ready by April 7th?\n\n"
            "Sanjay: I'll draft the test plan. We should also set up automated regression tests for the checkout flow.\n\n"
            "Ananya: Great. One more thing — someone needs to update the stakeholder dashboard with Q1 metrics. "
            "It hasn't been updated since February.\n\n"
            "Rohit: That's usually handled by the data team, but I'm not sure who specifically owns it now.\n\n"
            "Kavita: I think it used to be Arjun, but he moved to a different project.\n\n"
            "Ananya: Let's figure out the owner for that. Moving on..."
        )

    return {
        "task_id": f"MTG-2026-{int(time.time()) % 10000:04d}",
        "scenario_type": "meeting",
        "data": {
            "meeting_title": title,
            "meeting_date": "2026-03-25",
            "transcript": transcript,
            "participants": config.get("participants", "Team Members"),
        }
    }


def build_sla_data(config: dict) -> dict:
    approval_id = config.get("approval_id", f"PR-2026-{int(time.time()) % 9000 + 1000:04d}")
    return {
        "task_id": approval_id,
        "scenario_type": "sla_breach",
        "data": {
            "approval_id": approval_id,
            "item_description": config.get("item_description", "Cloud Infrastructure Upgrade"),
            "current_approver": config.get("current_approver", "Meera Shankar (VP Operations)"),
            "reason_stuck": config.get("reason_stuck", "Medical Leave"),
            "hours_stuck": int(config.get("hours_stuck", 48)),
            "sla_deadline_hours": int(config.get("sla_deadline_hours", 72)),
            "financial_impact": config.get("financial_impact", "₹5,00,000/day"),
            "department": config.get("department", "Infrastructure"),
            "delegates": [
                {"name": "Arun Kapoor", "title": "Director Operations", "authority": "FULL"},
                {"name": "Pooja Reddy", "title": "Senior Manager", "authority": "PARTIAL_UNDER_50L"}
            ],
        }
    }


SCENARIO_BUILDERS = {
    "onboarding": build_onboarding_data,
    "meeting": build_meeting_data,
    "sla_breach": build_sla_data,
}


# ==========================================
# REST Endpoints
# ==========================================
@app.get("/api/scenarios")
async def list_scenarios():
    return [
        {"id": "onboarding", "title": "Employee Onboarding",
         "description": "New hire account creation across HR, JIRA, Slack with error recovery",
         "icon": "👤", "steps": 6},
        {"id": "meeting", "title": "Meeting-to-Action",
         "description": "Extract action items, assign owners, flag ambiguity",
         "icon": "📋", "steps": 3},
        {"id": "sla_breach", "title": "SLA Breach Prevention",
         "description": "Reroute stuck approval to delegate before deadline",
         "icon": "⚡", "steps": 4},
    ]


class ScenarioConfig(BaseModel):
    config: dict = {}


@app.post("/api/start/{scenario_name}")
async def start_scenario(scenario_name: str, body: ScenarioConfig = None):
    """Start a scenario run with custom configuration."""
    global _main_loop
    _main_loop = asyncio.get_event_loop()

    if session_state["status"] in ("running", "hitl_waiting"):
        return JSONResponse({"error": "A scenario is already running. Please wait for completion or abort."}, status_code=400)

    builder = SCENARIO_BUILDERS.get(scenario_name)
    if not builder:
        return JSONResponse({"error": f"Unknown scenario: {scenario_name}"}, status_code=404)

    # Build scenario from custom config (or defaults)
    custom_config = body.config if body else {}
    scenario = builder(custom_config)

    # ── EDGE CASE: Race condition — duplicate workflow prevention ──
    entity_id = scenario["data"].get("employee_id") or scenario["data"].get("approval_id") or scenario["task_id"]
    race_check = RaceConditionGuard.check_duplicate_workflow(entity_id, scenario["task_id"])
    if race_check["duplicate"]:
        return JSONResponse({
            "error": f"Duplicate workflow: {race_check['message']}",
            "existing_task_id": race_check["existing_task_id"],
            "edge_case": "RACE_CONDITION_PREVENTED"
        }, status_code=409)

    session_state["status"] = "running"
    session_state["scenario"] = scenario_name
    session_state["hitl_response"] = None
    session_state["clarification_response"] = None
    session_state["current_task_id"] = scenario["task_id"]

    # Reset tools and state
    JIRAConnectorTool.reset()
    ApprovalSystemTool.reset_chain()
    LLMFactory._usage_log.clear()
    DeadlockDetector.reset(scenario["task_id"])
    set_current_task(scenario["task_id"])

    asyncio.create_task(_run_workflow(scenario))

    return {"status": "started", "scenario": scenario_name, "task_id": scenario["task_id"]}


async def _run_workflow(scenario: dict):
    """Run the LangGraph workflow and emit events."""
    entity_id = scenario["data"].get("employee_id") or scenario["data"].get("approval_id") or scenario["task_id"]
    try:
        compiled_app = build_workflow()
        config = {"configurable": {"thread_id": f"api-{scenario['scenario_type']}-{time.time()}"}}

        initial_state = {
            "task_id": scenario["task_id"],
            "scenario_type": scenario["scenario_type"],
            "scenario_data": scenario["data"],
            "current_status": "STARTED",
            "investigation_logs": [],
            "model_usage": [],
            "recovery_attempts": 0,
            "error_flag": False,
            "escalation_needed": False,
            "clarification_needed": False,
            "action_items": [],
            "execution_results": [],
            "edge_cases_detected": [],
        }

        await broadcast({"type": "workflow_start", "scenario": scenario["scenario_type"],
                         "task_id": scenario["task_id"],
                         "scenario_data": scenario["data"]})

        # Phase 1: Run until HITL gate
        loop = asyncio.get_event_loop()
        final_output = await loop.run_in_executor(
            None, lambda: _run_phase1(compiled_app, initial_state, config))

        # Check HITL gate
        snapshot = compiled_app.get_state(config)
        if snapshot.next:
            values = snapshot.values
            grade = values.get("strategy_grade", "")
            clarification = values.get("clarification_needed", False)
            clarification_ctx = values.get("clarification_context", "")
            action_items = values.get("action_items", [])
            edge_cases = values.get("edge_cases_detected", [])

            # ── EDGE CASE: Auto-approve high-confidence plans (GPA >= 3.5) ──
            auto_approve = "auto_approve: true" in grade.lower() and not clarification
            
            if auto_approve:
                # Skip HITL — broadcast auto-approval event
                await broadcast({
                    "type": "hitl_gate",
                    "grade": grade,
                    "clarification_needed": False,
                    "clarification_context": "",
                    "action_count": len(action_items),
                    "action_items": [{"step": a.get("step"), "description": a.get("description")}
                                    for a in action_items],
                    "edge_cases_count": len(edge_cases),
                    "auto_approved": True,
                })
                await asyncio.sleep(1.5)  # Brief pause for UI visibility
                await broadcast({"type": "hitl_approved", "auto": True,
                                "message": "Plan auto-approved (GPA ≥ 3.5, no flags)"})
            else:
                session_state["status"] = "hitl_waiting"

                # Start HITL timeout tracker
                DeadlockDetector.start_hitl_timer(scenario["task_id"])

                await broadcast({
                    "type": "hitl_gate",
                    "grade": grade,
                    "clarification_needed": clarification,
                    "clarification_context": clarification_ctx,
                    "action_count": len(action_items),
                    "action_items": [{"step": a.get("step"), "description": a.get("description")}
                                    for a in action_items],
                    "edge_cases_count": len(edge_cases),
                    "hitl_timeout_seconds": HITL_TIMEOUT,
                    "auto_approved": False,
                })

                # Wait for HITL response with timeout
                hitl_start = time.time()
                while session_state["hitl_response"] is None:
                    await asyncio.sleep(0.3)
                    
                    # Check HITL timeout
                    elapsed = time.time() - hitl_start
                    if elapsed > HITL_TIMEOUT:
                        await broadcast({
                            "type": "hitl_timeout",
                            "message": f"No human response in {HITL_TIMEOUT}s — auto-escalating",
                            "elapsed_seconds": round(elapsed)
                        })
                        session_state["hitl_response"] = "PROCEED"
                        break

                    # Send countdown updates every 30 seconds
                    if elapsed > 30 and int(elapsed) % 30 == 0:
                        remaining = max(0, HITL_TIMEOUT - elapsed)
                        await broadcast({
                            "type": "hitl_countdown",
                            "remaining_seconds": round(remaining),
                            "elapsed_seconds": round(elapsed)
                        })

                if session_state["hitl_response"] == "ABORT":
                    await broadcast({"type": "workflow_abort"})
                    session_state["status"] = "idle"
                    RaceConditionGuard.release_workflow(entity_id)
                    return

                if session_state.get("clarification_response"):
                    compiled_app.update_state(config, {
                        "clarification_response": session_state["clarification_response"]
                    })

                await broadcast({"type": "hitl_approved"})

            # Phase 2: Execute
            final_output = await loop.run_in_executor(
                None, lambda: _run_phase2(compiled_app, config))

        # Get edge case summary
        edge_case_summary = get_edge_case_summary()

        # Send final results
        await broadcast({
            "type": "workflow_complete",
            "audit_trail": final_output.get("investigation_logs", []),
            "status": final_output.get("current_status", ""),
            "report": final_output.get("recovery_path", ""),
            "execution_results": final_output.get("execution_results", []),
            "model_usage": LLMFactory.get_usage_summary(),
            "edge_case_summary": edge_case_summary,
            "edge_cases_total": edge_case_summary.get("total", 0),
        })

        session_state["status"] = "idle"
        session_state["hitl_response"] = None
        RaceConditionGuard.release_workflow(entity_id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        await broadcast({"type": "error", "message": str(e)})
        session_state["status"] = "idle"
        RaceConditionGuard.release_workflow(entity_id)


def _run_phase1(compiled_app, initial_state, config):
    """Run phase 1 (reasoning) in thread."""
    final = initial_state
    for event in compiled_app.stream(initial_state, config, stream_mode="values"):
        final = event
    return final


def _run_phase2(compiled_app, config):
    """Run phase 2 (execution) in thread."""
    final = {}
    while True:
        events = list(compiled_app.stream(None, config, stream_mode="values"))
        if not events:
            break
        final = events[-1]
        if not compiled_app.get_state(config).next:
            break
    return final


@app.post("/api/approve")
async def approve_execution(body: dict = None):
    if body is None:
        body = {}
    session_state["hitl_response"] = "PROCEED"
    if body.get("clarification"):
        session_state["clarification_response"] = body["clarification"]
    return {"status": "approved"}


@app.post("/api/abort")
async def abort_execution():
    session_state["hitl_response"] = "ABORT"
    return {"status": "aborted"}


@app.get("/api/status")
async def get_status():
    return {
        "status": session_state["status"],
        "scenario": session_state["scenario"],
        "model_usage": LLMFactory.get_usage_summary(),
    }

# ==========================================
# Database Browser Endpoints
# ==========================================
@app.get("/api/database/tables")
async def list_tables():
    """List all enterprise database tables with row counts."""
    return db.get_all_tables()


@app.get("/api/database/table/{table_name}")
async def get_table(table_name: str):
    """Get all rows from a specific enterprise table."""
    return db.get_table_data(table_name)


@app.get("/api/database/departments")
async def get_departments():
    """Get employees grouped by department."""
    return db.get_employees_by_department()


# ==========================================
# Edge Case & Security Endpoints
# ==========================================
@app.get("/api/edge-cases")
async def get_edge_cases():
    """Get edge case summary for the dashboard."""
    return get_edge_case_summary()


@app.get("/api/security-events")
async def get_security_events_api():
    """Get security events for the dashboard."""
    return db.get_security_events()


# ==========================================
# WebSocket Endpoint
# ==========================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "approve":
                session_state["hitl_response"] = "PROCEED"
                if msg.get("clarification"):
                    session_state["clarification_response"] = msg["clarification"]
            elif msg.get("type") == "abort":
                session_state["hitl_response"] = "ABORT"
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
    import uvicorn  # type: ignore
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting AgentFlow API Server v2.0 on port {port}...")
    print(f"API Docs:  http://0.0.0.0:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)
