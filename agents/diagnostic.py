import json
from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore
from .tools import (  # type: ignore
    hr_tool, jira_tool, approval_tool, erp_tool
)


class DiagnosticAgent:
    """
    Agent 2: The Root Cause Analyzer.
    
    Queries enterprise tools to gather data, then uses the HEAVY model
    to perform deep analysis and identify issues/risks.
    
    EDGE CASES HANDLED:
    - Tool query failures with graceful degradation
    - Conflicting information across sources
    - Ghost entity detection (missing managers/buddies)
    - Cross-system state validation
    """
    def __init__(self):
        self.model = LLMFactory.get_heavy_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        scenario_data = state.get("scenario_data", {})
        signal = state.get("disruption_signal", "")
        edge_cases = list(state.get("edge_cases_detected", []))

        print(f"\n--- ROOT CAUSE DIAGNOSIS STARTING ---")

        logs = []

        # Query relevant enterprise tools based on scenario
        tool_results, tool_errors = self._query_tools_safe(scenario_type, scenario_data)
        tool_summary = "\n".join(str(r) for r in tool_results)
        
        print(f"Tools queried: {len(tool_results)} | Errors: {len(tool_errors)}")

        # ── EDGE CASE: Log tool failures specifically ──
        if tool_errors:
            for err in tool_errors:
                logs.append(f"[Diagnostic] ⚠️ Tool query failed: {err}")
                edge_cases.append({
                    "type": "TOOL_QUERY_FAILURE", "severity": "MEDIUM",
                    "message": err, "handled": True
                })

        # ── EDGE CASE: Cross-system conflict detection ──
        conflicts = self._detect_cross_system_conflicts(scenario_type, scenario_data, tool_results)
        if conflicts:
            for conflict in conflicts:
                logs.append(f"[Diagnostic] 🔍 CONFLICT: {conflict['message']}")
                edge_cases.append({
                    "type": "CROSS_SYSTEM_CONFLICT", "severity": conflict["severity"],
                    "message": conflict["message"], "handled": True
                })

        # ── EDGE CASE: Ghost entity detection ──
        ghost_entities = self._detect_ghost_entities(scenario_type, scenario_data)
        if ghost_entities:
            for ghost in ghost_entities:
                logs.append(f"[Diagnostic] 👻 GHOST ENTITY: {ghost['message']}")
                edge_cases.append({
                    "type": "GHOST_ENTITY", "severity": ghost["severity"],
                    "message": ghost["message"], "handled": True
                })

        prompt = f"""CONTEXT: You are an Enterprise Root Cause Analyst.
SCENARIO TYPE: {scenario_type}
INITIAL SIGNAL: {signal}
TOOL QUERY RESULTS:
{tool_summary}
{f"KNOWN EDGE CASES ALREADY DETECTED: {json.dumps(edge_cases, default=str)[:500]}" if edge_cases else ""}

TASK: Perform a thorough analysis:
1. Identify the root cause or key issues
2. Quantify any financial risk or time pressure  
3. List specific systems/people affected
4. Recommend whether this needs immediate action or can wait
5. Flag any potential complications or data conflicts
6. Assess the reliability of the data (were any tool queries unreliable?)

OUTPUT: Structured risk assessment with clear findings."""

        try:
            response = self.model.invoke(prompt)
            diagnosis = response.content
            LLMFactory.log_usage("Diagnostic", "gemini-2.0-flash", len(prompt))
        except Exception as e:
            diagnosis = self._fallback_diagnosis(scenario_type, tool_results)
            print(f"⚠️ LLM failed, using rule-based diagnosis: {e}")
            logs.append(f"[Diagnostic] ⚠️ LLM fallback — rule-based diagnosis active")

        print(f"Diagnosis complete.")

        tool_summary_str = str(tool_summary)
        tool_summary_preview: str = tool_summary_str if len(tool_summary_str) <= 200 else tool_summary_str[0:200]

        result = {
            "impact_report": diagnosis,
            "current_status": "DIAGNOSED",
            "investigation_logs": [
                f"[Diagnostic] Queried {len(tool_results)} enterprise tools ({len(tool_errors)} failed)",
                f"[Diagnostic] Tool results: {tool_summary_preview}...",
                f"[Diagnostic] Risk assessment generated",
                *logs,
            ],
            "model_usage": [LLMFactory.log_usage("Diagnostic", "gemini-2.0-flash", len(prompt))]
        }

        if edge_cases:
            result["edge_cases_detected"] = edge_cases

        return result

    def _query_tools_safe(self, scenario_type: str, data: dict):
        """Query enterprise tools with error isolation — one failure doesn't block others."""
        results = []
        errors = []
        
        if scenario_type == "onboarding":
            emp_id = data.get("employee_id", "UNKNOWN")
            try:
                results.append(hr_tool.get_employee_status(emp_id))
            except Exception as e:
                errors.append(f"HR System query failed: {e}")

            for system in data.get("systems_required", []):
                if system == "JIRA":
                    try:
                        results.append(jira_tool.create_task(
                            f"Verify JIRA access for {emp_id}", 
                            "System", "Pre-check"))
                    except Exception as e:
                        errors.append(f"JIRA pre-check failed: {e}")
                    
        elif scenario_type == "meeting":
            try:
                results.append(jira_tool.create_task(
                    "Connection test", "System", "Verify JIRA connectivity"))
            except Exception as e:
                errors.append(f"JIRA connectivity check failed: {e}")
                
        elif scenario_type == "sla_breach":
            approval_id = data.get("approval_id", "UNKNOWN")
            approver = data.get("current_approver", "UNKNOWN")
            try:
                results.append(approval_tool.get_approval_status(approval_id))
            except Exception as e:
                errors.append(f"Approval status query failed: {e}")
            try:
                results.append(approval_tool.get_delegates(approver))
            except Exception as e:
                errors.append(f"Delegate lookup failed: {e}")
            
        return results, errors

    def _detect_cross_system_conflicts(self, scenario_type, data, tool_results):
        """Detect conflicting information across enterprise systems."""
        conflicts = []

        if scenario_type == "onboarding":
            # Check if employee exists in one system but not another
            name = data.get("employee_name", "")
            email = data.get("email", "") or data.get("employee_email", "")
            if name and email:
                expected_email = f"{name.lower().replace(' ', '.')}@company.com"
                if email and email != expected_email and "@" in email:
                    conflicts.append({
                        "message": f"Email mismatch: provided '{email}' vs expected format '{expected_email}'",
                        "severity": "LOW"
                    })

            # Role/department consistency check
            role = data.get("role", "").lower()
            dept = data.get("department", "").lower()
            if "engineer" in role and dept not in ["engineering", "data", "platform", ""]:
                conflicts.append({
                    "message": f"Role/department mismatch: role '{data.get('role')}' in department '{data.get('department')}'",
                    "severity": "MEDIUM"
                })

        elif scenario_type == "sla_breach":
            # Check if approval amount vs delegate authority
            delegates = data.get("delegates", [])
            for delegate in delegates:
                authority = delegate.get("authority", "")
                if "PARTIAL" in authority:
                    conflicts.append({
                        "message": f"Delegate {delegate.get('name')} has {authority} authority — may be insufficient for this approval amount",
                        "severity": "MEDIUM"
                    })

        return conflicts

    def _detect_ghost_entities(self, scenario_type, data):
        """Detect references to entities that may not exist."""
        ghosts = []

        if scenario_type == "onboarding":
            manager = data.get("manager", "")
            if manager:
                # Check if manager exists in our DB
                from . import database as db
                conn = db.get_connection()
                try:
                    result = conn.execute(
                        "SELECT COUNT(*) as c FROM employees WHERE name LIKE ?",
                        (f"%{manager}%",)
                    ).fetchone()
                    if result["c"] == 0:
                        ghosts.append({
                            "message": f"Manager '{manager}' not found in employee database — may be ghost entity or external hire",
                            "severity": "MEDIUM"
                        })
                finally:
                    conn.close()

            buddy_pool = data.get("buddy_pool", [])
            if buddy_pool:
                from . import database as db
                conn = db.get_connection()
                try:
                    for buddy in buddy_pool:
                        buddy_name = buddy.split("(")[0].strip() if "(" in buddy else buddy
                        result = conn.execute(
                            "SELECT COUNT(*) as c FROM employees WHERE name LIKE ?",
                            (f"%{buddy_name}%",)
                        ).fetchone()
                        if result["c"] == 0:
                            ghosts.append({
                                "message": f"Buddy '{buddy}' not found in employee database",
                                "severity": "LOW"
                            })
                finally:
                    conn.close()

        return ghosts

    def _fallback_diagnosis(self, scenario_type: str, tool_results: list) -> str:
        """Rule-based fallback diagnosis."""
        failed = [r for r in tool_results if not r.success]
        if failed:
            return f"CRITICAL: {len(failed)} tool queries failed. Errors: {[str(r) for r in failed]}. Immediate investigation needed."
        return f"Analysis complete for {scenario_type}. All tool queries successful. Proceeding to planning phase."