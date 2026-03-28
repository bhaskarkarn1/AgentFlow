from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore
from .edge_case_engine import DeadlockDetector  # type: ignore


class EscalationHandler:
    """
    Agent 6: The Escalation Specialist.
    
    Activated when the Executor fails after max retries.
    Routes the issue to the appropriate human authority based on scenario.
    Uses the LIGHT model (escalation logic is straightforward).
    
    EDGE CASES HANDLED:
    - Circular delegation detection (A → B → A)
    - No delegate available scenario
    - Delegate authority level verification
    - Escalation chain audit trail
    """
    def __init__(self):
        self.model = LLMFactory.get_light_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        execution_results = state.get("execution_results", [])
        action_items = state.get("action_items", [])
        edge_cases = list(state.get("edge_cases_detected", []))

        print(f"\n--- ESCALATION HANDLER ACTIVATED ---")

        logs = []

        # Find the failed steps
        failed_steps = [r for r in execution_results if not r.get("success", True)]
        
        # ── EDGE CASE: Circular delegation check ──
        delegation_chain = []
        for result in execution_results:
            data = result.get("data", {})
            if isinstance(data, dict):
                chain = data.get("delegation_chain", [])
                delegation_chain.extend(chain)
                rerouted_to = data.get("rerouted_to")
                if rerouted_to:
                    delegation_chain.append(rerouted_to)

        if delegation_chain:
            circular_check = DeadlockDetector.detect_circular_delegation(delegation_chain)
            if circular_check["is_circular"]:
                logs.append(f"[Escalation] 🔄 CIRCULAR DELEGATION DETECTED: {circular_check['chain']}")
                logs.append(f"[Escalation] Breaking loop at: {circular_check['loop_at']}")
                logs.append(f"[Escalation] Action: {circular_check['action']}")
                edge_cases.append({
                    "type": "CIRCULAR_DELEGATION", "severity": "CRITICAL",
                    "message": f"Circular delegation: {' → '.join(circular_check['chain'])}",
                    "handled": True
                })

        escalation_target = self._determine_escalation_target(scenario_type, failed_steps, edge_cases)
        
        # ── EDGE CASE: No delegate available ──
        no_delegate = any(
            r.get("data", {}).get("error") == "NO_DELEGATES_AVAILABLE" 
            for r in failed_steps if isinstance(r.get("data"), dict)
        )
        if no_delegate:
            logs.append(f"[Escalation] 🚨 NO DELEGATES AVAILABLE — escalating to executive level")
            escalation_target = "CEO Office (all delegates exhausted — requires executive override)"
            edge_cases.append({
                "type": "NO_DELEGATES", "severity": "CRITICAL",
                "message": "All delegates unavailable — executive escalation required",
                "handled": True
            })

        # ── EDGE CASE: Authority verification ──
        insufficient_auth = any(
            r.get("data", {}).get("error") == "INSUFFICIENT_AUTHORITY"
            for r in failed_steps if isinstance(r.get("data"), dict)
        )
        if insufficient_auth:
            logs.append(f"[Escalation] 🔐 AUTHORITY ISSUE — delegate lacks required approval authority")
            edge_cases.append({
                "type": "INSUFFICIENT_AUTHORITY", "severity": "HIGH",
                "message": "Delegate authority insufficient for this approval amount",
                "handled": True
            })

        prompt = f"""CONTEXT: An automated workflow has failed after multiple retries.
SCENARIO: {scenario_type}
FAILED STEPS: {str(failed_steps)[:300]}
EDGE CASES: {str(edge_cases[-3:])[:200] if edge_cases else "None"}

TASK: Generate a concise escalation notice for: {escalation_target}
Include: what failed, how many retries were attempted, what action is needed from the human.
If there's a circular delegation issue, explain that the loop was broken and why executive intervention is needed.
Keep it professional and actionable."""

        try:
            response = self.model.invoke(prompt)
            escalation_message = response.content
            LLMFactory.log_usage("Escalation", "gemini-2.0-flash-lite", len(prompt))
        except Exception as e:
            escalation_message = f"ESCALATION: {len(failed_steps)} step(s) failed after max retries. Manual intervention required."

        print(f"Escalated to: {escalation_target}")

        result = {
            "current_status": "ESCALATED",
            "escalation_needed": False,  # Resolved by escalating
            "investigation_logs": [
                f"[Escalation] {len(failed_steps)} failed steps escalated to {escalation_target}",
                f"[Escalation] Notice: {escalation_message[:200]}...",
                *logs,
            ],
            "model_usage": [LLMFactory.log_usage("Escalation", "gemini-2.0-flash-lite", len(prompt))]
        }

        if edge_cases:
            result["edge_cases_detected"] = edge_cases

        return result

    def _determine_escalation_target(self, scenario_type, failed_steps, edge_cases=None):
        """Determine who to escalate to based on scenario and edge cases."""
        # Check for critical edge cases that need higher authority
        critical_cases = [e for e in (edge_cases or []) if e.get("severity") == "CRITICAL"]
        
        if critical_cases:
            return "Senior Management (critical edge cases detected requiring executive oversight)"

        if scenario_type == "onboarding":
            return "IT Administrator (JIRA account creation requires admin privileges)"
        elif scenario_type == "meeting":
            return "Meeting Organizer (Ambiguous action items need human clarification)"
        elif scenario_type == "sla_breach":
            return "VP Manager (Delegate is also unavailable, need higher authority)"
        return "System Administrator"
