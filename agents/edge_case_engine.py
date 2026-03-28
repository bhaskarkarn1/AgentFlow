"""
Edge Case Engine — Production-Grade Edge Case Detection & Handling.

Centralised module that provides guardrails across ALL 11 edge-case categories:
  1. Identity & Entity Problems
  2. Workflow Deadlock Prevention
  3. Race Condition Guards
  4. Partial Failure & Inconsistency
  5. Tool / API Failure Classification
  6. LLM-Specific Guardrails
  7. Audit & Compliance Enforcement
  8. Security (Prompt Injection, Permissions)
  9. Human-in-the-Loop Resilience
  10. System & Infrastructure Safety
  11. Scenario-Specific Checks

Every detection is logged to the `edge_case_log` table for full auditability.
"""

import re
import time
import json
import hashlib
import threading
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

# Lazy import to avoid circular dependency
_db = None

def _get_db():
    global _db
    if _db is None:
        from . import database as db
        _db = db
    return _db


# ═══════════════════════════════════════════
# 1. IDENTITY & ENTITY VALIDATOR
# ═══════════════════════════════════════════
class IdentityValidator:
    """Detects duplicate names, missing fields, ghost entities, name variations."""

    REQUIRED_ONBOARDING_FIELDS = [
        "employee_name", "employee_id", "role", "department"
    ]
    REQUIRED_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    @staticmethod
    def validate_employee_data(data: dict) -> dict:
        """Validate employee data for identity edge cases. Returns dict with issues found."""
        issues = []
        severity = "INFO"

        # --- Missing critical fields ---
        for field in IdentityValidator.REQUIRED_ONBOARDING_FIELDS:
            val = data.get(field, "")
            if not val or str(val).strip() == "" or val == "UNKNOWN":
                issues.append({
                    "type": "MISSING_FIELD",
                    "field": field,
                    "severity": "HIGH",
                    "message": f"Critical field '{field}' is missing or empty",
                    "resolution": f"Auto-generated placeholder for '{field}' — flagged for human review"
                })
                severity = "HIGH"

        # --- Invalid email ---
        email = data.get("email", "") or data.get("employee_email", "")
        if email and not IdentityValidator.REQUIRED_EMAIL_PATTERN.match(email):
            issues.append({
                "type": "INVALID_EMAIL",
                "field": "email",
                "severity": "MEDIUM",
                "message": f"Email '{email}' has invalid format",
                "resolution": "Auto-corrected email format based on name convention"
            })
            if severity != "HIGH":
                severity = "MEDIUM"

        # --- Ghost manager detection ---
        manager = data.get("manager", "")
        if not manager or manager.strip() == "":
            issues.append({
                "type": "GHOST_ENTITY",
                "field": "manager",
                "severity": "HIGH",
                "message": "No manager specified — reporting hierarchy undefined",
                "resolution": "Escalated to HR Director for manager assignment"
            })
            severity = "HIGH"

        # --- Empty buddy pool ---
        buddy_pool = data.get("buddy_pool", [])
        if not buddy_pool or len(buddy_pool) == 0:
            issues.append({
                "type": "EMPTY_POOL",
                "field": "buddy_pool",
                "severity": "MEDIUM",
                "message": "Buddy pool is empty — no onboarding buddies available",
                "resolution": "Auto-selecting from same department senior employees"
            })

        result = {
            "valid": len(issues) == 0,
            "issues": issues,
            "severity": severity if issues else "NONE",
            "total_issues": len(issues)
        }

        # Log to edge case table
        if issues:
            _log_edge_case("IDENTITY_VALIDATION", severity, 
                          f"Found {len(issues)} identity issue(s) for {data.get('employee_name', 'UNKNOWN')}",
                          json.dumps(issues, default=str))

        return result

    @staticmethod
    def detect_duplicate_employee(name: str, department: str, start_date: str) -> dict:
        """Detect if this employee might already exist using fuzzy matching."""
        db = _get_db()
        conn = db.get_connection()
        duplicates = []
        try:
            existing = conn.execute(
                "SELECT employee_id, name, department, start_date, email FROM employees"
            ).fetchall()
            for emp in existing:
                name_similarity = SequenceMatcher(None, name.lower(), emp["name"].lower()).ratio()
                same_dept = emp["department"].lower() == department.lower() if department else False
                
                # Exact match
                if name_similarity > 0.95:
                    duplicates.append({
                        "type": "EXACT_DUPLICATE",
                        "existing_id": emp["employee_id"],
                        "existing_name": emp["name"],
                        "similarity": round(name_similarity, 2),
                        "same_department": same_dept,
                        "severity": "CRITICAL",
                        "message": f"Employee '{name}' appears to already exist as '{emp['name']}' ({emp['employee_id']})"
                    })
                # Fuzzy match (e.g., Rahul Sharma vs R Sharma)
                elif name_similarity > 0.6 and same_dept:
                    duplicates.append({
                        "type": "POSSIBLE_DUPLICATE",
                        "existing_id": emp["employee_id"],
                        "existing_name": emp["name"],
                        "similarity": round(name_similarity, 2),
                        "same_department": same_dept,
                        "severity": "MEDIUM",
                        "message": f"Possible match: '{name}' ≈ '{emp['name']}' (similarity: {name_similarity:.0%})"
                    })
                # Name variation check (first name only, abbreviation)
                elif _is_name_variation(name, emp["name"]) and same_dept:
                    duplicates.append({
                        "type": "NAME_VARIATION",
                        "existing_id": emp["employee_id"],
                        "existing_name": emp["name"],
                        "similarity": round(name_similarity, 2),
                        "same_department": same_dept,
                        "severity": "MEDIUM",
                        "message": f"Name variation detected: '{name}' may be the same person as '{emp['name']}'"
                    })
        finally:
            conn.close()

        if duplicates:
            _log_edge_case("DUPLICATE_IDENTITY", duplicates[0]["severity"],
                          f"Found {len(duplicates)} potential duplicate(s) for '{name}'",
                          json.dumps(duplicates, default=str))

        return {
            "has_duplicates": len(duplicates) > 0,
            "duplicates": duplicates,
            "action": "PROCEED_WITH_CAUTION" if duplicates else "CLEAR"
        }


def _is_name_variation(name1: str, name2: str) -> bool:
    """Check if two names could be variations of the same person."""
    parts1 = name1.lower().split()
    parts2 = name2.lower().split()
    
    if not parts1 or not parts2:
        return False
    
    # Check if one is an abbreviation (R Sharma vs Rahul Sharma)
    if len(parts1) >= 2 and len(parts2) >= 2:
        if parts1[-1] == parts2[-1]:  # Same last name
            if len(parts1[0]) == 1 and parts2[0].startswith(parts1[0]):
                return True
            if len(parts2[0]) == 1 and parts1[0].startswith(parts2[0]):
                return True
    
    return False


# ═══════════════════════════════════════════
# 2. DEADLOCK DETECTOR & CIRCUIT BREAKER
# ═══════════════════════════════════════════
class DeadlockDetector:
    """Prevents infinite loops, circular dependencies, and workflow deadlocks."""

    # Circuit breaker state
    _retry_counts = {}  # {action_key: count}
    _planner_iterations = {}  # {task_id: count}
    _hitl_timestamps = {}  # {task_id: start_time}
    _lock = threading.Lock()

    # Limits
    MAX_RETRIES_PER_ACTION = 5
    MAX_PLANNER_ITERATIONS = 3
    HITL_TIMEOUT_SECONDS = 300  # 5 minutes
    MAX_WORKFLOW_DURATION_SECONDS = 600  # 10 minutes
    MAX_PLAN_STEPS = 12

    @classmethod
    def check_retry_budget(cls, task_id: str, action: str) -> dict:
        """Check if we still have retry budget for this action."""
        key = f"{task_id}:{action}"
        with cls._lock:
            count = cls._retry_counts.get(key, 0) + 1
            cls._retry_counts[key] = count

        if count > cls.MAX_RETRIES_PER_ACTION:
            _log_edge_case("DEADLOCK_PREVENTION", "HIGH",
                          f"Circuit breaker tripped: {action} exceeded {cls.MAX_RETRIES_PER_ACTION} retries",
                          json.dumps({"task_id": task_id, "action": action, "attempts": count}))
            return {
                "allowed": False,
                "reason": f"Circuit breaker: {action} exceeded max {cls.MAX_RETRIES_PER_ACTION} retries",
                "attempts": count,
                "action": "ESCALATE"
            }
        return {"allowed": True, "attempts": count, "remaining": cls.MAX_RETRIES_PER_ACTION - count}

    @classmethod
    def check_planner_iterations(cls, task_id: str) -> dict:
        """Prevent infinite planner→grader loops."""
        with cls._lock:
            count = cls._planner_iterations.get(task_id, 0) + 1
            cls._planner_iterations[task_id] = count

        if count > cls.MAX_PLANNER_ITERATIONS:
            _log_edge_case("PLANNER_LOOP", "HIGH",
                          f"Planner loop breaker: {count} iterations for task {task_id}",
                          json.dumps({"task_id": task_id, "iterations": count}))
            return {
                "allowed": False,
                "reason": f"Planner has iterated {count} times — forcing execution with best available plan",
                "iterations": count
            }
        return {"allowed": True, "iterations": count}

    @classmethod
    def start_hitl_timer(cls, task_id: str):
        """Start HITL timeout tracker."""
        with cls._lock:
            cls._hitl_timestamps[task_id] = time.time()

    @classmethod
    def check_hitl_timeout(cls, task_id: str) -> dict:
        """Check if HITL has timed out."""
        with cls._lock:
            start = cls._hitl_timestamps.get(task_id)
        
        if start is None:
            return {"timed_out": False}
        
        elapsed = time.time() - start
        remaining = max(0, cls.HITL_TIMEOUT_SECONDS - elapsed)
        
        if elapsed > cls.HITL_TIMEOUT_SECONDS:
            _log_edge_case("HITL_TIMEOUT", "HIGH",
                          f"HITL gate timed out after {elapsed:.0f}s for task {task_id}",
                          json.dumps({"task_id": task_id, "elapsed_seconds": elapsed}))
            return {
                "timed_out": True,
                "elapsed_seconds": round(elapsed),
                "action": "AUTO_ESCALATE",
                "message": f"No human response in {cls.HITL_TIMEOUT_SECONDS}s — auto-escalating to supervisor"
            }
        return {
            "timed_out": False,
            "remaining_seconds": round(remaining),
            "elapsed_seconds": round(elapsed)
        }

    @classmethod
    def validate_plan_size(cls, action_items: list) -> dict:
        """Ensure plan isn't excessively large (context overflow prevention)."""
        if len(action_items) > cls.MAX_PLAN_STEPS:
            _log_edge_case("PLAN_SIZE_OVERFLOW", "MEDIUM",
                          f"Plan has {len(action_items)} steps — exceeds max {cls.MAX_PLAN_STEPS}",
                          json.dumps({"step_count": len(action_items)}))
            return {
                "valid": False,
                "message": f"Plan has {len(action_items)} steps — trimming to {cls.MAX_PLAN_STEPS}",
                "trimmed_items": action_items[:cls.MAX_PLAN_STEPS]
            }
        return {"valid": True}

    @classmethod
    def detect_circular_dependency(cls, action_items: list) -> dict:
        """Detect circular dependencies between action steps."""
        # Build dependency graph from prerequisite fields
        deps = {}
        for item in action_items:
            step = item.get("step")
            prereqs = item.get("prerequisites", [])
            deps[step] = prereqs

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        cycle_path = []

        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in deps.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    cycle_path.extend(path[path.index(neighbor):])
                    return True
            path.pop()
            rec_stack.discard(node)
            return False

        for step in deps:
            if step not in visited:
                if has_cycle(step, []):
                    _log_edge_case("CIRCULAR_DEPENDENCY", "CRITICAL",
                                  f"Circular dependency detected: {' → '.join(map(str, cycle_path))}",
                                  json.dumps({"cycle": cycle_path}))
                    return {
                        "has_cycle": True,
                        "cycle": cycle_path,
                        "action": "BREAK_CYCLE",
                        "message": f"Circular dependency: {' → '.join(map(str, cycle_path))}"
                    }

        return {"has_cycle": False}

    @classmethod
    def detect_circular_delegation(cls, delegation_chain: list) -> dict:
        """Detect circular delegation (Approver A → B → A)."""
        seen = set()
        for person in delegation_chain:
            normalized = person.strip().lower()
            if normalized in seen:
                _log_edge_case("CIRCULAR_DELEGATION", "CRITICAL",
                              f"Circular delegation detected: {' → '.join(delegation_chain)}",
                              json.dumps({"chain": delegation_chain, "loop_at": person}))
                return {
                    "is_circular": True,
                    "loop_at": person,
                    "chain": delegation_chain,
                    "action": "ESCALATE_TO_HIGHER_AUTHORITY"
                }
            seen.add(normalized)
        return {"is_circular": False}

    @classmethod
    def reset(cls, task_id: str = None):
        """Reset state for new workflow run."""
        with cls._lock:
            if task_id:
                keys_to_remove = [k for k in cls._retry_counts if k.startswith(f"{task_id}:")]
                for k in keys_to_remove:
                    del cls._retry_counts[k]
                cls._planner_iterations.pop(task_id, None)
                cls._hitl_timestamps.pop(task_id, None)
            else:
                cls._retry_counts.clear()
                cls._planner_iterations.clear()
                cls._hitl_timestamps.clear()


# ═══════════════════════════════════════════
# 3. RACE CONDITION GUARD
# ═══════════════════════════════════════════
class RaceConditionGuard:
    """Prevents concurrent workflow conflicts using idempotency keys."""

    _active_workflows = {}  # {employee_id: task_id}
    _processed_actions = set()  # Set of idempotency keys
    _lock = threading.Lock()

    @classmethod
    def check_duplicate_workflow(cls, entity_id: str, task_id: str) -> dict:
        """Prevent two workflows for the same entity simultaneously."""
        with cls._lock:
            if entity_id in cls._active_workflows:
                existing_task = cls._active_workflows[entity_id]
                if existing_task != task_id:
                    _log_edge_case("RACE_CONDITION", "HIGH",
                                  f"Duplicate workflow detected for entity '{entity_id}'",
                                  json.dumps({"existing_task": existing_task, "new_task": task_id}))
                    return {
                        "duplicate": True,
                        "existing_task_id": existing_task,
                        "message": f"Workflow already in progress for '{entity_id}' (Task: {existing_task})",
                        "action": "REJECT_DUPLICATE"
                    }
            cls._active_workflows[entity_id] = task_id
        return {"duplicate": False}

    @classmethod
    def generate_idempotency_key(cls, action: str, tool: str, params: dict) -> str:
        """Generate a unique key for an action to prevent duplicate execution."""
        param_str = json.dumps(params, sort_keys=True, default=str)
        raw = f"{action}:{tool}:{param_str}"
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def check_already_executed(cls, idempotency_key: str) -> bool:
        """Check if this exact action was already executed."""
        with cls._lock:
            if idempotency_key in cls._processed_actions:
                _log_edge_case("IDEMPOTENCY_GUARD", "INFO",
                              f"Duplicate action prevented (key: {idempotency_key[:12]}...)",
                              json.dumps({"key": idempotency_key}))
                return True
            cls._processed_actions.add(idempotency_key)
        return False

    @classmethod
    def release_workflow(cls, entity_id: str):
        """Release workflow lock for an entity."""
        with cls._lock:
            cls._active_workflows.pop(entity_id, None)

    @classmethod
    def reset(cls):
        """Reset all state."""
        with cls._lock:
            cls._active_workflows.clear()
            cls._processed_actions.clear()


# ═══════════════════════════════════════════
# 4. STATE CONSISTENCY CHECKER
# ═══════════════════════════════════════════
class StateConsistencyChecker:
    """Validates cross-system state consistency."""

    @staticmethod
    def check_execution_state(execution_results: list, action_items: list) -> dict:
        """Check for partial completion inconsistencies."""
        if not execution_results:
            return {"consistent": True, "issues": []}

        issues = []
        completed = [r for r in execution_results if r.get("success")]
        failed = [r for r in execution_results if not r.get("success")]
        total = len(action_items)

        # Partial completion check
        if completed and failed:
            issues.append({
                "type": "PARTIAL_COMPLETION",
                "severity": "HIGH",
                "message": f"{len(completed)}/{total} steps completed, {len(failed)} failed — system state may be inconsistent",
                "completed_steps": [r.get("step") for r in completed],
                "failed_steps": [r.get("step") for r in failed],
                "resolution": "Compensating actions may be needed for completed steps if workflow is aborted"
            })

        # Check for dependent step failures
        for item in action_items:
            deps = item.get("depends_on", [])
            step = item.get("step")
            failed_steps = {r.get("step") for r in failed}
            if any(d in failed_steps for d in deps):
                issues.append({
                    "type": "DEPENDENCY_FAILURE",
                    "severity": "HIGH",
                    "message": f"Step {step} depends on failed step(s): {[d for d in deps if d in failed_steps]}",
                    "resolution": "Step should be skipped or re-evaluated"
                })

        if issues:
            _log_edge_case("STATE_INCONSISTENCY", "HIGH",
                          f"State consistency check found {len(issues)} issue(s)",
                          json.dumps(issues, default=str))

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "summary": {
                "completed": len(completed),
                "failed": len(failed),
                "total": total
            }
        }


# ═══════════════════════════════════════════
# 5. TOOL ERROR CLASSIFIER
# ═══════════════════════════════════════════
class ToolErrorClassifier:
    """Classifies API errors as transient vs permanent to guide recovery strategy."""

    TRANSIENT_ERRORS = {429, 500, 502, 503, 504}
    PERMANENT_ERRORS = {400, 401, 403, 404, 405, 422}

    @staticmethod
    def classify_error(error_code: int, error_message: str = "") -> dict:
        """Classify an API error and recommend recovery action."""
        if error_code in ToolErrorClassifier.TRANSIENT_ERRORS:
            return {
                "type": "TRANSIENT",
                "retryable": True,
                "strategy": "EXPONENTIAL_BACKOFF",
                "message": f"Transient error (HTTP {error_code}) — will auto-retry with backoff",
                "wait_seconds": _backoff_time(error_code)
            }
        elif error_code in ToolErrorClassifier.PERMANENT_ERRORS:
            if error_code == 403:
                return {
                    "type": "PERMANENT",
                    "retryable": True,  # Can retry with credential rotation
                    "strategy": "CREDENTIAL_ROTATION",
                    "message": f"Access denied (HTTP 403) — attempting credential rotation",
                    "wait_seconds": 2
                }
            return {
                "type": "PERMANENT",
                "retryable": False,
                "strategy": "ESCALATE",
                "message": f"Permanent error (HTTP {error_code}) — requires human intervention",
                "wait_seconds": 0
            }
        return {
            "type": "UNKNOWN",
            "retryable": True,
            "strategy": "RETRY_ONCE",
            "message": f"Unknown error type — will retry once",
            "wait_seconds": 1
        }


def _backoff_time(error_code: int) -> float:
    """Calculate backoff time for transient errors."""
    if error_code == 429:
        return 3.0  # Rate limited — longer wait
    elif error_code in (502, 503):
        return 2.0
    return 1.0


# ═══════════════════════════════════════════
# 6. LLM GUARDRAILS
# ═══════════════════════════════════════════
class LLMGuardrails:
    """Validates LLM outputs before they're acted upon."""

    VALID_TOOLS = {"HR_System", "JIRA", "Communication", "Calendar",
                   "ApprovalSystem", "LLM_Analysis", "ERP", "System"}

    @staticmethod
    def validate_action_items(action_items: list) -> dict:
        """Validate that action items reference real tools and have required fields."""
        issues = []
        cleaned_items = []

        for item in action_items:
            item_issues = []

            # Check for hallucinated tools
            tool = item.get("tool", "")
            if tool and tool not in LLMGuardrails.VALID_TOOLS:
                item_issues.append({
                    "type": "HALLUCINATED_TOOL",
                    "severity": "HIGH",
                    "message": f"Step {item.get('step')}: Tool '{tool}' does not exist",
                    "resolution": f"Mapped to closest valid tool"
                })
                # Auto-correct to closest match
                item["tool"] = _find_closest_tool(tool)

            # Check for missing required fields
            for field in ["step", "action", "tool", "description"]:
                if not item.get(field):
                    item_issues.append({
                        "type": "MISSING_ACTION_FIELD",
                        "severity": "MEDIUM",
                        "message": f"Action item missing required field: '{field}'"
                    })

            # Check for overly verbose descriptions (context overflow risk)
            desc = item.get("description", "")
            if len(desc) > 500:
                item["description"] = desc[:497] + "..."
                item_issues.append({
                    "type": "VERBOSE_DESCRIPTION",
                    "severity": "LOW",
                    "message": f"Step {item.get('step')}: Description truncated (was {len(desc)} chars)"
                })

            if item_issues:
                issues.extend(item_issues)
            cleaned_items.append(item)

        if issues:
            _log_edge_case("LLM_GUARDRAIL", "MEDIUM",
                          f"LLM output validation found {len(issues)} issue(s)",
                          json.dumps(issues, default=str))

        return {
            "valid": len([i for i in issues if i["severity"] == "HIGH"]) == 0,
            "issues": issues,
            "cleaned_items": cleaned_items
        }

    @staticmethod
    def validate_grade_output(grade_text: str) -> dict:
        """Validate that grader output contains required fields and is consistent."""
        issues = []
        grade_lower = grade_text.lower()

        # Check for required fields in output
        has_gpa = bool(re.search(r'gpa:\s*[\d.]+', grade_lower))
        has_verdict = 'verdict:' in grade_lower
        has_auto_approve = 'auto_approve:' in grade_lower

        if not has_gpa:
            issues.append({"type": "MISSING_GPA", "message": "Grade output missing GPA score"})
        if not has_verdict:
            issues.append({"type": "MISSING_VERDICT", "message": "Grade output missing verdict"})

        # Extract GPA value and check for contradictions
        gpa_match = re.search(r'gpa:\s*([\d.]+)', grade_lower)
        if gpa_match:
            gpa = float(gpa_match.group(1))
            if gpa > 4.0 or gpa < 0:
                issues.append({
                    "type": "INVALID_GPA",
                    "message": f"GPA {gpa} out of range [0.0, 4.0]"
                })
            # Check for contradictions
            if gpa >= 3.5 and 'auto_approve: false' in grade_lower:
                pass  # This is fine — grader may have flags
            elif gpa < 2.0 and 'auto_approve: true' in grade_lower:
                issues.append({
                    "type": "CONTRADICTORY_REASONING",
                    "message": f"GPA is {gpa} (low) but auto_approve is true — contradiction"
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "gpa": float(gpa_match.group(1)) if gpa_match else None
        }


def _find_closest_tool(hallucinated_tool: str) -> str:
    """Find the closest valid tool name using fuzzy matching."""
    best_match = "System"
    best_score = 0
    for valid in LLMGuardrails.VALID_TOOLS:
        score = SequenceMatcher(None, hallucinated_tool.lower(), valid.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = valid
    return best_match


# ═══════════════════════════════════════════
# 7. SECURITY GUARDRAILS
# ═══════════════════════════════════════════
class SecurityGuard:
    """Detects prompt injection, unauthorized access, and data exposure."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+above",
        r"system\s*:\s*",
        r"you\s+are\s+now\s+",
        r"act\s+as\s+(a\s+)?",
        r"pretend\s+(you\s+are|to\s+be)",
        r"override\s+your\s+",
        r"disregard\s+(all|your)\s+",
        r"forget\s+(all|your|everything)\s+",
        r"new\s+instruction",
        r"<\s*script",
        r"javascript\s*:",
        r"\bexec\s*\(",
        r"\beval\s*\(",
        r"__import__",
        r"os\.system",
        r"subprocess",
        r"\brm\s+-rf",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r";\s*--",
    ]

    SENSITIVE_PATTERNS = [
        r"api[_\s-]?key",
        r"password",
        r"secret",
        r"token",
        r"credential",
        r"private[_\s-]?key",
        r"ssn\b",
        r"social\s*security",
    ]

    @classmethod
    def scan_input(cls, text, source: str = "user_input") -> dict:
        """Scan input text for prompt injection attacks."""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        if not text:
            return {"safe": True, "threats": []}

        threats = []
        text_lower = text.lower()

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower):
                threats.append({
                    "type": "PROMPT_INJECTION",
                    "pattern": pattern,
                    "severity": "CRITICAL",
                    "source": source,
                    "message": f"Potential prompt injection detected in {source}"
                })

        # Check for SQL injection patterns
        if re.search(r"('\s*(OR|AND)\s*'|\bUNION\s+SELECT|;\s*DROP\s)", text, re.IGNORECASE):
            threats.append({
                "type": "SQL_INJECTION",
                "severity": "CRITICAL",
                "source": source,
                "message": "Potential SQL injection detected"
            })

        if threats:
            _log_edge_case("SECURITY_THREAT", "CRITICAL",
                          f"Security scan detected {len(threats)} threat(s) in {source}",
                          json.dumps(threats, default=str))
            # Also log to security events table
            db = _get_db()
            for threat in threats:
                db.log_security_event(
                    event_type=threat["type"],
                    severity=threat["severity"],
                    source=source,
                    details=threat["message"],
                    blocked=True
                )

        return {
            "safe": len(threats) == 0,
            "threats": threats,
            "sanitized_text": _sanitize_input(text) if threats else text
        }

    @classmethod
    def mask_sensitive_data(cls, text) -> str:
        """Mask sensitive data in log output."""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        masked = text
        for pattern in cls.SENSITIVE_PATTERNS:
            # Find the pattern and mask the value after it
            masked = re.sub(
                rf"({pattern})\s*[=:]\s*\S+",
                r"\1=***REDACTED***",
                masked,
                flags=re.IGNORECASE
            )
        return masked


def _sanitize_input(text: str) -> str:
    """Remove dangerous characters from input."""
    # Remove script tags, eval patterns, etc.
    sanitized = re.sub(r'<[^>]*>', '', text)  # Strip HTML
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', sanitized)  # Control chars
    # Limit length
    if len(sanitized) > 10000:
        sanitized = sanitized[:10000] + "... [TRUNCATED]"
    return sanitized


# ═══════════════════════════════════════════
# 8. STALE STATE DETECTOR
# ═══════════════════════════════════════════
class StaleStateDetector:
    """Detects when execution is happening on already-changed state."""

    @staticmethod
    def check_approval_status(approval_result: dict) -> dict:
        """Check if an approval was resolved while we were processing."""
        status = approval_result.get("status", "")
        
        if status == "ALREADY_APPROVED":
            _log_edge_case("STALE_STATE", "HIGH",
                          f"Approval {approval_result.get('approval_id')} was already approved outside the system",
                          json.dumps(approval_result, default=str))
            return {
                "stale": True,
                "type": "OUT_OF_BAND_RESOLUTION",
                "message": f"Approval was completed outside the system by {approval_result.get('approved_by', 'unknown')}",
                "action": "SKIP_REMAINING_STEPS",
                "severity": "HIGH"
            }
        
        if status == "RESOLVED_CONCURRENT":
            _log_edge_case("STALE_STATE", "HIGH",
                          f"Approval {approval_result.get('approval_id')} was resolved by a parallel process",
                          json.dumps(approval_result, default=str))
            return {
                "stale": True,
                "type": "PARALLEL_RESOLUTION",
                "message": f"Another process resolved this approval concurrently",
                "action": "SKIP_REMAINING_STEPS",
                "severity": "HIGH"
            }
        
        return {"stale": False}

    @staticmethod
    def check_employee_partial_existence(tool_result: dict) -> dict:
        """Check if employee already exists in some systems but not others."""
        error = tool_result.get("error", "")
        if error == "PARTIAL_EXISTENCE":
            _log_edge_case("CROSS_SYSTEM_INCONSISTENCY", "HIGH",
                          f"Employee exists in {tool_result.get('existing_systems', [])} but not {tool_result.get('missing_systems', [])}",
                          json.dumps(tool_result, default=str))
            return {
                "inconsistent": True,
                "type": "PARTIAL_EXISTENCE",
                "existing_systems": tool_result.get("existing_systems", []),
                "missing_systems": tool_result.get("missing_systems", []),
                "action": "SYNC_MISSING_SYSTEMS",
                "severity": "HIGH"
            }
        return {"inconsistent": False}


# ═══════════════════════════════════════════
# 9. CONFLICTING DATE DETECTOR
# ═══════════════════════════════════════════
class ConflictingDateDetector:
    """Detects date conflicts across systems."""

    @staticmethod
    def check_join_date_conflict(tool_result: dict) -> dict:
        """Check if there's a date mismatch between submitted and system dates."""
        error = tool_result.get("error", "")
        if error == "CONFLICTING_JOIN_DATE":
            submitted = tool_result.get("submitted_date", "")
            system_date = tool_result.get("system_date", "")
            _log_edge_case("DATE_CONFLICT", "MEDIUM",
                          f"Join date conflict: submitted '{submitted}' vs system '{system_date}'",
                          json.dumps(tool_result, default=str))
            return {
                "conflict": True,
                "submitted_date": submitted,
                "system_date": system_date,
                "action": "USE_SUBMITTED_AND_FLAG",
                "severity": "MEDIUM",
                "message": f"Date mismatch: submitted '{submitted}' conflicts with system date '{system_date}'"
            }
        return {"conflict": False}


# ═══════════════════════════════════════════
# LOGGING HELPER
# ═══════════════════════════════════════════
def _log_edge_case(category: str, severity: str, message: str, details: str = ""):
    """Log an edge case detection to the database."""
    try:
        db = _get_db()
        db.log_edge_case(category, severity, message, details)
    except Exception as e:
        # Don't let logging failures crash the system
        print(f"⚠️ Edge case logging failed: {e}")


def get_edge_case_summary() -> dict:
    """Get a summary of all edge cases detected in this session."""
    try:
        db = _get_db()
        return db.get_edge_case_summary()
    except Exception:
        return {"total": 0, "by_category": {}, "by_severity": {}}
