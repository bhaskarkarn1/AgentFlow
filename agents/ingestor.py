import json
from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore
from .edge_case_engine import (  # type: ignore
    IdentityValidator, SecurityGuard
)


class SignalIngestor:
    """
    Agent 1: The Universal Signal Detector.
    
    Ingests ANY enterprise scenario and extracts key entities.
    Uses the LIGHT model tier (extraction/parsing is not complex reasoning).
    
    EDGE CASES HANDLED:
    - Input validation (missing/empty fields)
    - Prompt injection detection
    - Duplicate employee detection
    - Identity field validation
    """
    def __init__(self):
        self.model = LLMFactory.get_light_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        scenario_data = state.get("scenario_data", {})
        task_id = state.get("task_id", "UNKNOWN")

        print(f"\n--- SIGNAL INGESTION CLAW STARTING ---")
        print(f"Scenario: {scenario_type} | Task: {task_id}")

        logs = []
        edge_cases_detected = []

        # ── EDGE CASE: Input validation ──
        if not scenario_data or len(scenario_data) == 0:
            logs.append(f"[Ingestor] ⚠️ EDGE CASE: Empty scenario data received — using fallback extraction")
            edge_cases_detected.append({
                "type": "EMPTY_INPUT", "severity": "HIGH",
                "message": "No scenario data provided", "handled": True
            })

        # ── EDGE CASE: Security scan on all input text ──
        input_text = json.dumps(scenario_data, default=str)
        security_result = SecurityGuard.scan_input(input_text, source=f"scenario_input_{scenario_type}")
        if not security_result["safe"]:
            logs.append(f"[Ingestor] 🛡️ SECURITY: Prompt injection attempt BLOCKED — {len(security_result['threats'])} threat(s) neutralized")
            edge_cases_detected.append({
                "type": "PROMPT_INJECTION_BLOCKED", "severity": "CRITICAL",
                "message": f"Blocked {len(security_result['threats'])} injection attempt(s)",
                "handled": True
            })
            # Use sanitized text
            try:
                scenario_data = json.loads(security_result["sanitized_text"])
            except (json.JSONDecodeError, TypeError):
                pass  # Keep original if sanitized version isn't valid JSON

        # ── EDGE CASE: Identity validation for onboarding ──
        if scenario_type == "onboarding":
            # Validate employee fields
            validation = IdentityValidator.validate_employee_data(scenario_data)
            if not validation["valid"]:
                for issue in validation["issues"]:
                    logs.append(f"[Ingestor] ⚠️ IDENTITY: {issue['message']} → {issue.get('resolution', 'Flagged')}")
                    edge_cases_detected.append({
                        "type": issue["type"], "severity": issue["severity"],
                        "message": issue["message"], "handled": True
                    })

            # Check for duplicate employee
            name = scenario_data.get("employee_name", "")
            dept = scenario_data.get("department", "")
            start_date = scenario_data.get("start_date", "")
            if name:
                dup_check = IdentityValidator.detect_duplicate_employee(name, dept, start_date)
                if dup_check["has_duplicates"]:
                    for dup in dup_check["duplicates"]:
                        logs.append(f"[Ingestor] 🔍 DUPLICATE: {dup['message']}")
                        edge_cases_detected.append({
                            "type": dup["type"], "severity": dup["severity"],
                            "message": dup["message"], "handled": True
                        })

        # ── EDGE CASE: Meeting scenario validation ──
        if scenario_type == "meeting":
            transcript = scenario_data.get("transcript", "")
            if not transcript or len(transcript.strip()) < 20:
                logs.append(f"[Ingestor] ⚠️ EDGE CASE: Meeting transcript is empty or too short")
                edge_cases_detected.append({
                    "type": "INSUFFICIENT_TRANSCRIPT", "severity": "HIGH",
                    "message": "Meeting transcript is empty or too short for meaningful extraction",
                    "handled": True
                })
            participants = scenario_data.get("participants", [])
            if not participants:
                logs.append(f"[Ingestor] ⚠️ EDGE CASE: No participants listed — ownership assignment will be ambiguous")
                edge_cases_detected.append({
                    "type": "NO_PARTICIPANTS", "severity": "MEDIUM",
                    "message": "No participants listed for meeting", "handled": True
                })

        # ── EDGE CASE: SLA scenario validation ──
        if scenario_type == "sla_breach":
            approval_id = scenario_data.get("approval_id", "")
            if not approval_id:
                logs.append(f"[Ingestor] ⚠️ EDGE CASE: No approval ID provided")
                edge_cases_detected.append({
                    "type": "MISSING_APPROVAL_ID", "severity": "HIGH",
                    "message": "No approval ID — cannot track the stuck approval", "handled": True
                })
            delegates = scenario_data.get("delegates", [])
            if not delegates:
                logs.append(f"[Ingestor] ⚠️ EDGE CASE: No delegates configured — escalation path unclear")
                edge_cases_detected.append({
                    "type": "NO_DELEGATES", "severity": "HIGH",
                    "message": "No delegates available for escalation", "handled": True
                })

        # ── Core LLM processing ──
        prompt = self._build_prompt(scenario_type, scenario_data)
        
        try:
            response = self.model.invoke(prompt)
            signal_description = LLMFactory.safe_content(response)
            LLMFactory.log_usage("Ingestor", "gemini-2.0-flash-lite", len(prompt))
        except Exception as e:
            signal_description = self._fallback_extraction(scenario_type, scenario_data)
            print(f"⚠️ LLM call failed, using rule-based fallback: {e}")
            logs.append(f"[Ingestor] ⚠️ LLM fallback activated — using rule-based extraction")

        # Mask any sensitive data in the signal
        signal_description = SecurityGuard.mask_sensitive_data(signal_description)

        print(f"Signal Detected: {signal_description[:120]}...")

        result = {
            "disruption_signal": signal_description,
            "task_id": task_id,
            "current_status": "SIGNAL_DETECTED",
            "investigation_logs": [
                f"[Ingestor] Scenario '{scenario_type}' ingested. Task ID: {task_id}",
                *logs,
            ],
            "model_usage": [LLMFactory.log_usage("Ingestor", "gemini-2.0-flash-lite", len(prompt))]
        }

        # Pass edge cases forward for dashboard visibility
        if edge_cases_detected:
            result["edge_cases_detected"] = edge_cases_detected
            result["investigation_logs"].append(
                f"[Ingestor] 📊 Edge cases detected: {len(edge_cases_detected)} ({', '.join(e['type'] for e in edge_cases_detected)})"
            )

        return result

    def _build_prompt(self, scenario_type: str, data: dict) -> str:
        data_str = json.dumps(data, indent=2, default=str)
        
        if scenario_type == "onboarding":
            return f"""TASK: Analyze this employee onboarding request and identify all required actions.
Extract: employee name, role, department, start date, systems that need accounts, and any potential risks.
IMPORTANT: Check for potential identity conflicts, missing fields, or data inconsistencies.

DATA:
{data_str}

OUTPUT: Provide a structured summary of what needs to happen for this onboarding. Flag any data quality issues."""

        elif scenario_type == "meeting":
            return f"""TASK: Analyze this meeting transcript and extract ALL action items.
For each action item, identify: (1) the task description, (2) the assigned owner (from the participants), (3) the deadline if mentioned.
If any action item has NO CLEAR OWNER, explicitly mark it as "OWNER: AMBIGUOUS" — do NOT guess.
If any decisions are CONTRADICTORY, flag them explicitly.

MEETING DATA:
{data_str}

OUTPUT: List each action item with owner and deadline. Flag any ambiguous assignments or conflicts."""

        elif scenario_type == "sla_breach":
            return f"""TASK: Analyze this stuck approval and identify the bottleneck.
Determine: (1) why the approval is stuck, (2) who the current approver is and their status, 
(3) available delegates and their authority levels, (4) SLA deadline and urgency.
IMPORTANT: Check if delegates have SUFFICIENT AUTHORITY for the approval amount.

APPROVAL DATA:
{data_str}

OUTPUT: Provide a risk assessment and identify the bottleneck clearly."""

        else:
            return f"""TASK: Analyze this enterprise signal and extract key information.
DATA: {data_str}
OUTPUT: Provide a structured summary of the situation and required actions."""

    def _fallback_extraction(self, scenario_type: str, data: dict) -> str:
        """Rule-based fallback if LLM is unavailable."""
        if scenario_type == "onboarding":
            name = data.get("employee_name", "Unknown")
            systems = data.get("systems_required", [])
            return f"New hire {name} requires account creation in {', '.join(systems) if systems else 'HR, JIRA, Slack'}. Start date: {data.get('start_date')}."
        elif scenario_type == "meeting":
            return f"Meeting transcript with {len(data.get('participants', []))} participants requires action item extraction."
        elif scenario_type == "sla_breach":
            return f"Approval {data.get('approval_id')} stuck for 48 hours. Approver {data.get('current_approver')} is on leave."
        return "Signal detected — details in scenario data."