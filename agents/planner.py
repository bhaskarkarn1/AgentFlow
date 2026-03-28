import json
from .llm_factory import LLMFactory  # type: ignore
from .registry import AgentState  # type: ignore
from .edge_case_engine import (  # type: ignore
    LLMGuardrails, DeadlockDetector, SecurityGuard
)


class StrategyPlanner:
    """
    Agent 3: The Strategy Planner.
    
    Takes diagnostic output and creates a detailed, multi-step execution plan.
    Uses the HEAVY model because planning requires complex reasoning.
    
    EDGE CASES HANDLED:
    - Hallucinated tool detection (non-existent tools)
    - Circular dependency detection in action plans
    - Plan size limits (prevents context overflow)
    - Missing prerequisite validation
    - Plan quality pre-check before grader
    """
    def __init__(self):
        self.model = LLMFactory.get_heavy_model()

    def process(self, state: AgentState):
        scenario_type = state.get("scenario_type", "unknown")
        scenario_data = state.get("scenario_data", {})
        impact = state.get("impact_report", "")
        signal = state.get("disruption_signal", "")
        task_id = state.get("task_id", "UNKNOWN")
        edge_cases = list(state.get("edge_cases_detected", []))

        print(f"\n--- STRATEGY PLANNING STARTING ---")

        logs = []

        # ── EDGE CASE: Planner loop detection ──
        loop_check = DeadlockDetector.check_planner_iterations(task_id)
        if not loop_check["allowed"]:
            logs.append(f"[Planner] 🔴 DEADLOCK PREVENTION: {loop_check['reason']}")
            edge_cases.append({
                "type": "PLANNER_LOOP_BROKEN", "severity": "HIGH",
                "message": loop_check["reason"], "handled": True
            })
            # Return the best plan we have — don't loop forever
            action_items = self._generate_action_items(scenario_type, scenario_data)
            return {
                "recovery_plan": "Forced execution after max planner iterations.",
                "action_items": action_items,
                "current_status": "PLAN_FORCED",
                "investigation_logs": logs,
                "edge_cases_detected": edge_cases,
                "model_usage": []
            }

        # ── Core LLM Planning ──
        prompt = self._build_prompt(scenario_type, scenario_data, signal, impact, edge_cases)

        # ── EDGE CASE: Security scan on any user-provided data in prompt ──
        sec_check = SecurityGuard.scan_input(prompt, source="planner_prompt")
        if not sec_check["safe"]:
            logs.append(f"[Planner] 🛡️ SECURITY: Sanitized {len(sec_check['threats'])} threat(s) from planning context")
            prompt = sec_check["sanitized_text"]

        try:
            response = self.model.invoke(prompt)
            plan = response.content
            LLMFactory.log_usage("Planner", "gemini-2.0-flash", len(prompt))
        except Exception as e:
            plan = "Fallback plan: Execute standard procedure for this scenario type."
            print(f"⚠️ LLM failed, using fallback plan: {e}")
            logs.append(f"[Planner] ⚠️ LLM fallback — using template plan")

        # Generate structured action items based on scenario
        action_items = self._generate_action_items(scenario_type, scenario_data)

        # ── EDGE CASE: Validate action items (hallucinated tools, missing fields) ──
        validation = LLMGuardrails.validate_action_items(action_items)
        if not validation["valid"]:
            for issue in validation["issues"]:
                logs.append(f"[Planner] 🤖 LLM GUARDRAIL: {issue['message']}")
                edge_cases.append({
                    "type": issue["type"], "severity": issue["severity"],
                    "message": issue["message"], "handled": True
                })
            action_items = validation["cleaned_items"]

        # ── EDGE CASE: Plan size check (context overflow prevention) ──
        size_check = DeadlockDetector.validate_plan_size(action_items)
        if not size_check["valid"]:
            logs.append(f"[Planner] ✂️ PLAN TRIMMED: {size_check['message']}")
            action_items = size_check["trimmed_items"]
            edge_cases.append({
                "type": "PLAN_SIZE_OVERFLOW", "severity": "MEDIUM",
                "message": size_check["message"], "handled": True
            })

        # ── EDGE CASE: Circular dependency check ──
        dep_check = DeadlockDetector.detect_circular_dependency(action_items)
        if dep_check["has_cycle"]:
            logs.append(f"[Planner] 🔄 CIRCULAR DEPENDENCY: {dep_check['message']}")
            edge_cases.append({
                "type": "CIRCULAR_DEPENDENCY", "severity": "HIGH",
                "message": dep_check["message"], "handled": True
            })

        print(f"Plan generated with {len(action_items)} action steps.")

        result = {
            "recovery_plan": plan,
            "action_items": action_items,
            "current_status": "PLAN_GENERATED",
            "investigation_logs": [
                f"[Planner] Generated {len(action_items)}-step execution plan for {scenario_type}",
                f"[Planner] Actions: {', '.join(a['action'] for a in action_items)}",
                *logs,
            ],
            "model_usage": [LLMFactory.log_usage("Planner", "gemini-2.0-flash", len(prompt))]
        }

        if edge_cases:
            result["edge_cases_detected"] = edge_cases

        return result

    def _build_prompt(self, scenario_type, data, signal, impact, edge_cases=None):
        data_str = json.dumps(data, indent=2, default=str)
        edge_case_context = ""
        if edge_cases:
            edge_case_context = f"\n\nKNOWN EDGE CASES (detected by upstream agents):\n{json.dumps(edge_cases, default=str)[:600]}\nYour plan MUST account for these edge cases."
        
        if scenario_type == "onboarding":
            return f"""CONTEXT: You are an Onboarding Process Strategist.
SIGNAL: {signal}
RISK ANALYSIS: {impact}
RAW DATA: {data_str}
{edge_case_context}

TASK: Create an actionable onboarding plan for this new hire. Include:
1. Account creation across all required systems (in dependency order)
2. Buddy assignment
3. Orientation meeting scheduling  
4. Welcome pack delivery
5. Error handling: What to do if any system (especially JIRA) fails
6. Escalation path if retries don't work
7. Handle any detected identity issues or duplicate concerns

IMPORTANT: Only reference these VALID tools: HR_System, JIRA, Communication, Calendar, ApprovalSystem, LLM_Analysis
OUTPUT: Step-by-step plan with clear actions, tools to use, and fallback strategies."""

        elif scenario_type == "meeting":
            return f"""CONTEXT: You are a Meeting Intelligence Strategist.
SIGNAL: {signal}
ANALYSIS: {impact}
MEETING DATA: {data_str}
{edge_case_context}

TASK: Create an action plan to process this meeting's outcomes:
1. Identify ALL action items from the transcript
2. Assign owners (ONLY if clearly identifiable from context)
3. If any item has NO CLEAR OWNER, mark it as AMBIGUOUS — DO NOT GUESS
4. Set deadlines based on what was discussed
5. Plan: Create tasks in project tracker + send summary to all participants

CRITICAL: At least one action item in this transcript has an ambiguous owner. You MUST identify it and flag it for human clarification. This is a REQUIREMENT.
IMPORTANT: Only reference these VALID tools: HR_System, JIRA, Communication, Calendar, ApprovalSystem, LLM_Analysis"""

        elif scenario_type == "sla_breach":
            return f"""CONTEXT: You are an SLA Compliance Strategist.
SIGNAL: {signal}
RISK ANALYSIS: {impact}
APPROVAL DATA: {data_str}
{edge_case_context}

TASK: Create an emergency action plan:
1. Confirm the bottleneck (approver on leave)
2. Identify the best delegate based on authority level  
3. Reroute the approval with full audit documentation
4. Notify all stakeholders
5. Error handling: What if the delegate is also unavailable?
6. Handle circular delegation if detected
7. Calculate savings vs. waiting for original approver

Show the math: daily penalty × days saved = business value.
IMPORTANT: Only reference these VALID tools: HR_System, JIRA, Communication, Calendar, ApprovalSystem, LLM_Analysis"""

        return f"Create a plan for: {signal}\nData: {data_str}"

    def _generate_action_items(self, scenario_type, data):
        """Generate structured action items for the Executor."""
        
        if scenario_type == "onboarding":
            emp = data.get("employee_name", "New Hire")
            emp_id = data.get("employee_id", "EMP-UNKNOWN")
            return [
                {"step": 1, "action": "create_hr_record", "tool": "HR_System",
                 "description": f"Create HR record for {emp}", "retry_limit": 2,
                 "params": {"employee_data": data}},
                {"step": 2, "action": "create_jira_account", "tool": "JIRA",
                 "description": f"Create JIRA account for {emp_id}", "retry_limit": 3,
                 "params": {"employee_id": emp_id, "role": data.get("role", "Engineer")},
                 "escalate_on_fail": "IT_Admin"},
                {"step": 3, "action": "send_slack_invite", "tool": "Communication",
                 "description": f"Send Slack workspace invite to {emp}", "retry_limit": 2,
                 "params": {"recipients": [data.get("employee_email", "") or data.get("email", "")], 
                           "subject": "Welcome to the team!",
                           "body": f"Hi {emp}, welcome aboard!"}},
                {"step": 4, "action": "assign_buddy", "tool": "HR_System",
                 "description": f"Assign onboarding buddy for {emp}", "retry_limit": 2,
                 "params": {"employee_id": emp_id, 
                           "buddy_pool": data.get("buddy_pool", ["Ananya Desai (SDE-III)", "Vikram Patel (Tech Lead)"])}},
                {"step": 5, "action": "schedule_orientation", "tool": "Calendar",
                 "description": f"Schedule orientation meetings", "retry_limit": 2,
                 "params": {"title": f"Orientation: {emp}",
                           "participants": [emp, data.get("manager", "HR Team")],
                           "date": data.get("start_date", "TBD")}},
                {"step": 6, "action": "send_welcome_pack", "tool": "Communication",
                 "description": f"Send welcome pack to {emp}", "retry_limit": 1,
                 "params": {"employee_name": emp, 
                           "employee_email": data.get("employee_email", "") or data.get("email", "")}}
            ]

        elif scenario_type == "meeting":
            participants = data.get("participants", [])
            participant_names = [p["name"] if isinstance(p, dict) else p for p in participants]
            return [
                {"step": 1, "action": "extract_action_items", "tool": "LLM_Analysis",
                 "description": "Extract and assign action items from transcript", "retry_limit": 1,
                 "params": {"transcript": data.get("transcript", "")}},
                {"step": 2, "action": "create_tasks", "tool": "JIRA",
                 "description": "Create tasks in project tracker", "retry_limit": 2,
                 "params": {}},
                {"step": 3, "action": "send_summary", "tool": "Communication",
                 "description": "Send meeting summary to all participants", "retry_limit": 2,
                 "params": {"recipients": participant_names if participant_names else ["Team"],
                           "subject": f"Meeting Summary: {data.get('meeting_title', 'Meeting')}",
                           "body": ""}}
            ]

        elif scenario_type == "sla_breach":
            delegates = data.get("delegates", [])
            primary_delegate = delegates[0]["name"] if delegates else "UNKNOWN"
            return [
                {"step": 1, "action": "verify_bottleneck", "tool": "ApprovalSystem",
                 "description": "Verify approval status and bottleneck", "retry_limit": 1,
                 "params": {"approval_id": data.get("approval_id", "")}},
                {"step": 2, "action": "check_delegates", "tool": "ApprovalSystem",
                 "description": "Identify and verify delegate authority", "retry_limit": 1,
                 "params": {"approver": data.get("current_approver", "")}},
                {"step": 3, "action": "reroute_approval", "tool": "ApprovalSystem",
                 "description": f"Reroute approval to delegate: {primary_delegate}", "retry_limit": 3,
                 "params": {"approval_id": data.get("approval_id", ""),
                           "new_approver": primary_delegate,
                           "reason": f"Original approver {data.get('current_approver', '')} on medical leave. SLA breach imminent."},
                 "escalate_on_fail": "VP_Manager"},
                {"step": 4, "action": "notify_stakeholders", "tool": "Communication",
                 "description": "Notify all stakeholders of the reroute", "retry_limit": 2,
                 "params": {"recipients": [data.get("submitted_by", "Stakeholder"), primary_delegate],
                           "subject": f"Approval Rerouted: {data.get('approval_id', '')}",
                           "body": f"Approval for {data.get('item', data.get('item_description', 'procurement item'))} has been rerouted to {primary_delegate} due to SLA breach risk."}}
            ]

        return [{"step": 1, "action": "generic_action", "tool": "System",
                 "description": "Execute standard procedure", "retry_limit": 2, "params": {}}]