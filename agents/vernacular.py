from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore


class VernacularAgent:
    """
    Agent 8: The Vernacular Communication Specialist.
    
    Generates localized reports and summaries in the appropriate language/format.
    Uses the LIGHT model (translation/formatting doesn't need heavy reasoning).
    
    Supports Hindi (Devanagari) for Indian enterprise contexts.
    Now includes edge case summary in final report for auditability.
    """
    def __init__(self):
        self.model = LLMFactory.get_light_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        plan = state.get("recovery_plan", "No plan available.")
        execution_results = state.get("execution_results", [])
        investigation_logs = state.get("investigation_logs", [])
        edge_cases = state.get("edge_cases_detected", [])

        print(f"\n--- VERNACULAR SPECIALIST STARTING ---")

        prompt = self._build_prompt(scenario_type, plan, execution_results, investigation_logs, edge_cases)

        try:
            response = self.model.invoke(prompt)
            report = LLMFactory.safe_content(response)
            LLMFactory.log_usage("Vernacular", "gemini-2.0-flash-lite", len(prompt))
        except Exception as e:
            report = f"Workflow completed for {scenario_type}. Check audit logs for details."
            print(f"⚠️ LLM failed, using basic report: {e}")

        print(f"Vernacular report generated.")

        return {
            "recovery_path": report,
            "current_status": "COMPLETED",
            "investigation_logs": [
                f"[Vernacular] Final report generated in Hindi + English",
                f"[Vernacular] Edge cases documented: {len(edge_cases)}",
                f"[Vernacular] Workflow status: COMPLETED"
            ],
            "model_usage": [LLMFactory.log_usage("Vernacular", "gemini-2.0-flash-lite", len(prompt))]
        }

    def _build_prompt(self, scenario_type, plan, results, logs, edge_cases=None):
        results_summary = str(results)[:400] if results else "No execution results"
        logs_summary = "\n".join(logs[-12:]) if logs else "No logs"
        
        # Build edge case summary for inclusion in report
        edge_summary = ""
        if edge_cases:
            edge_summary = f"\n\nEDGE CASES HANDLED ({len(edge_cases)} total):\n"
            by_severity = {}
            for ec in edge_cases:
                sev = ec.get("severity", "UNKNOWN")
                by_severity.setdefault(sev, []).append(ec.get("type", "UNKNOWN"))
            for sev, types in by_severity.items():
                edge_summary += f"  {sev}: {', '.join(types[:5])}\n"
            edge_summary += "\nInclude a section titled 'Edge Cases & Self-Healing Summary' that lists the edge cases handled during this workflow."

        if scenario_type == "onboarding":
            return f"""TASK: Generate a bilingual (Hindi + English) onboarding completion report.

PLAN EXECUTED: {plan[:300]}
EXECUTION RESULTS: {results_summary}
AUDIT LOG: {logs_summary}
{edge_summary}

FORMAT: 
1. Start with a Hindi summary (2-3 lines in Devanagari) for the HR team
2. Then provide an English executive summary
3. List completed steps with ✅/❌ status
4. Note any escalations or manual actions still needed
5. Include edge case summary if any were detected
6. Show self-healing recovery actions taken"""

        elif scenario_type == "meeting":
            return f"""TASK: Generate a meeting action summary for all participants.

PLAN: {plan[:300]}
RESULTS: {results_summary}
{edge_summary}

FORMAT:
1. Meeting title and date
2. Hindi summary (1-2 lines in Devanagari)
3. Action items table: Task | Owner | Deadline | Status
4. Flag any items that needed human clarification with ⚠️
5. Include edge case summary (ambiguity detection, ownership conflicts)
6. Note: This is the automated summary sent to all participants"""

        elif scenario_type == "sla_breach":
            return f"""TASK: Generate an SLA compliance report in Hindi and English.

PLAN: {plan[:300]}
RESULTS: {results_summary}
AUDIT LOG: {logs_summary}
{edge_summary}

FORMAT:
1. Hindi summary (2-3 lines in Devanagari) explaining what happened
2. English executive summary
3. Business impact: penalty avoided, time saved
4. Audit trail: who approved, when, override justification
5. Edge case summary (delegation conflicts, authority issues)
6. Compliance status"""

        return f"""Generate a report for {scenario_type}.
Plan: {plan[:200]}
Results: {results_summary}
{edge_summary}"""