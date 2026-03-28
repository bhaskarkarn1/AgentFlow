import json
import re
from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore
from .edge_case_engine import LLMGuardrails  # type: ignore


class AgentGrader:
    """
    Agent 4: The Agent GPA Evaluator.
    
    Evaluates the quality of the recovery plan before execution.
    Uses the HEAVY model for evaluation (requires judgment).
    
    EDGE CASES HANDLED:
    - GPA validation (0.0-4.0 range enforcement)
    - Contradictory reasoning detection
    - Low-quality plan rejection (GPA < 2.0 → force replan)
    - Forced ambiguity flagging for meeting scenarios
    - Grade output parsing robustness
    """
    def __init__(self):
        self.model = LLMFactory.get_heavy_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        signal = state.get("disruption_signal", "")
        plan = state.get("recovery_plan", "")
        impact = state.get("impact_report", "")
        action_items = state.get("action_items", [])
        edge_cases = list(state.get("edge_cases_detected", []))

        signal_preview: str = str(signal)[:300]
        impact_preview: str = str(impact)[:300]
        plan_preview: str = str(plan)[:500]
        action_preview: str = json.dumps(action_items, indent=2, default=str)[:500]

        logs = []

        # Build edge case context for grader
        edge_case_context = ""
        if edge_cases:
            edge_case_context = f"\n\nEDGE CASES DETECTED BY UPSTREAM AGENTS:\n{json.dumps(edge_cases, default=str)[:400]}"
            edge_case_context += "\nEnsure the plan addresses these edge cases. Score LOWER if edge cases are ignored."

        prompt = f"""TASK: Evaluate this agent's recovery plan. Be a strict but fair grader.

SCENARIO: {scenario_type}
ORIGINAL SIGNAL: {signal_preview}
RISK ANALYSIS: {impact_preview}
PROPOSED PLAN: {plan_preview}
ACTION STEPS: {action_preview}
{edge_case_context}

EVALUATION CRITERIA:
1. COMPLETENESS: Does the plan cover all necessary steps? (0-4)
2. CORRECTNESS: Are the proposed actions technically sound? (0-4)
3. ERROR HANDLING: Does the plan include retry logic and escalation? (0-4)
4. EFFICIENCY: Is the plan optimized (no unnecessary steps)? (0-4)
5. EDGE CASE HANDLING: Does the plan address detected edge cases? (0-4)

{"6. AMBIGUITY CHECK (CRITICAL for meeting scenario): Does the plan correctly flag action items with no clear owner as AMBIGUOUS? If the plan GUESSES an owner instead of flagging, score LOWER." if scenario_type == "meeting" else ""}

OUTPUT FORMAT (STRICT — follow EXACTLY):
GPA: [number 0.0-4.0]
VERDICT: [one sentence]
AMBIGUITY_DETECTED: [true/false]
{"AMBIGUOUS_ITEMS: [list any items with unclear ownership]" if scenario_type == "meeting" else ""}
AUTO_APPROVE: [true if GPA >= 3.5 and no critical flags, false otherwise]
EDGE_CASES_ADDRESSED: [true/false]"""

        try:
            response = self.model.invoke(prompt)
            grade = LLMFactory.safe_content(response)
            LLMFactory.log_usage("Grader", "gemini-2.0-flash", len(prompt))
        except Exception as e:
            grade = "GPA: 3.0\nVERDICT: Evaluation failed, defaulting to moderate confidence.\nAMBIGUITY_DETECTED: false\nAUTO_APPROVE: false\nEDGE_CASES_ADDRESSED: false"
            print(f"⚠️ LLM failed, using default grade: {e}")
            logs.append(f"[Grader] ⚠️ LLM fallback — using default conservative grade")

        # ── EDGE CASE: Validate grade output ──
        grade_validation = LLMGuardrails.validate_grade_output(grade)
        if not grade_validation["valid"]:
            for issue in grade_validation["issues"]:
                logs.append(f"[Grader] 🤖 GRADE VALIDATION: {issue['message']}")
                edge_cases.append({
                    "type": issue["type"], "severity": "MEDIUM",
                    "message": issue["message"], "handled": True
                })

        # ── EDGE CASE: Extract and validate GPA ──
        gpa = grade_validation.get("gpa")
        if gpa is not None:
            if gpa > 4.0:
                gpa = 4.0
                logs.append(f"[Grader] ✂️ GPA clamped to 4.0 (was {grade_validation['gpa']})")
            elif gpa < 0:
                gpa = 0.0
                logs.append(f"[Grader] ✂️ GPA clamped to 0.0 (was {grade_validation['gpa']})")

            # ── EDGE CASE: Low quality plan rejection ──
            if gpa < 2.0:
                logs.append(f"[Grader] 🔴 LOW QUALITY PLAN (GPA: {gpa}) — flagging for improvement")
                edge_cases.append({
                    "type": "LOW_QUALITY_PLAN", "severity": "HIGH",
                    "message": f"Plan scored GPA {gpa}/4.0 — below minimum threshold",
                    "handled": True
                })

        # Parse the grade response
        clarification_needed = self._detect_ambiguity(grade, scenario_type)
        auto_approve = "auto_approve: true" in grade.lower()

        # ── EDGE CASE: Force ambiguity detection for meeting scenarios ──
        if scenario_type == "meeting" and not clarification_needed:
            # Meetings ALWAYS have at least one ambiguous item per the scenario pack
            transcript = state.get("scenario_data", {}).get("transcript", "")
            if "someone" in transcript.lower() or "figure out" in transcript.lower() or "not sure" in transcript.lower():
                clarification_needed = True
                logs.append(f"[Grader] ⚠️ FORCED AMBIGUITY: Meeting transcript contains ambiguous ownership signals")
                edge_cases.append({
                    "type": "FORCED_AMBIGUITY_DETECTION", "severity": "MEDIUM",
                    "message": "Meeting transcript has ambiguous task ownership — flagged for human clarification",
                    "handled": True
                })

        print(f"Grade: {grade[:80]}...")
        print(f"Clarification needed: {clarification_needed}")
        print(f"Auto-approve: {auto_approve}")

        result = {
            "strategy_grade": grade,
            "investigation_logs": [
                f"[Grader] GPA evaluation complete" + (f" (GPA: {gpa})" if gpa is not None else ""),
                f"[Grader] Ambiguity detected: {clarification_needed}",
                f"[Grader] Auto-approve recommended: {auto_approve}",
                *logs,
            ],
            "model_usage": [LLMFactory.log_usage("Grader", "gemini-2.0-flash", len(prompt))]
        }

        # Set clarification flag for meeting scenarios with ambiguous items
        if clarification_needed:
            result["clarification_needed"] = True
            result["clarification_context"] = self._extract_ambiguous_items(grade)
        
        if edge_cases:
            result["edge_cases_detected"] = edge_cases

        return result

    def _detect_ambiguity(self, grade_text: str, scenario_type: str) -> bool:
        """Check if the grader detected ambiguous ownership."""
        grade_lower = grade_text.lower()
        if scenario_type == "meeting":
            return ("ambiguity_detected: true" in grade_lower or 
                    "ambiguous" in grade_lower or
                    "unclear owner" in grade_lower or
                    "no clear owner" in grade_lower)
        return False

    def _extract_ambiguous_items(self, grade_text: str) -> str:
        """Extract the ambiguous items description from grade text."""
        lines = grade_text.split("\n")
        for line in lines:
            if "ambiguous" in line.lower() and ("item" in line.lower() or "owner" in line.lower()):
                return line.strip()
        return "One or more action items have ambiguous ownership. Please clarify the owner."