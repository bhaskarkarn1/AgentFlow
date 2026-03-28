from typing import TypedDict, List, Dict, Any, Annotated, Optional
import operator


class AgentState(TypedDict):
    """
    Universal state shared across all agents via LangGraph's Task Ledger.
    Supports multiple enterprise scenarios through a single pipeline.
    """
    # --- Core Identifiers ---
    task_id: str
    scenario_type: str  # "onboarding" | "meeting" | "sla_breach"
    scenario_data: Dict[str, Any]  # Raw input data for the scenario

    # --- Pipeline State ---
    current_status: str
    disruption_signal: str      # Ingestor output: what was detected
    impact_report: str          # Diagnostic output: analysis
    recovery_plan: str          # Planner output: action plan
    strategy_grade: str         # Grader output: GPA score
    recovery_path: str          # Vernacular output: final report

    # --- Execution Tracking ---
    action_items: List[Dict[str, Any]]   # Steps to execute (from planner)
    execution_results: List[Dict[str, Any]]  # Results of each executed step

    # --- Error Recovery & Branching ---
    error_flag: bool
    recovery_attempts: int
    escalation_needed: bool         # Route to escalation agent
    clarification_needed: bool      # Route to HITL for ambiguity
    clarification_context: str      # What needs clarification
    clarification_response: str     # Human's answer

    # --- Edge Case Tracking (append-only) ---
    edge_cases_detected: Annotated[List[Dict[str, Any]], operator.add]

    # --- Audit Trail (append-only via operator.add reducer) ---
    investigation_logs: Annotated[List[str], operator.add]

    # --- Cost Tracking (append-only) ---
    model_usage: Annotated[List[Dict[str, Any]], operator.add]  # {agent, model, tokens_est}


class NexusRegistry:
    """Registry of all agent node names in the LangGraph workflow."""
    INGESTOR = "Signal_Ingestion_Claw"
    DIAGNOSTIC = "Root_Cause_Agent"
    ORCHESTRATOR = "Strategy_Planner"
    GRADER = "Agent_Grader"
    ACTION_CLAW = "Execution_Agent"
    AUDITOR = "Compliance_Auditor"
    VERNACULAR = "Vernacular_Specialist"
    ESCALATION = "Escalation_Handler"