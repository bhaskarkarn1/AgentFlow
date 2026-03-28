"""
Enterprise Tool Suite — Simulated MCP-Standardized Tools.

Each tool simulates a real enterprise system with REALISTIC failure modes.
Tools fail with specific, documented errors (403, timeouts, rate limits)
so the agent's error recovery is visible and auditable.

UPGRADE: Every tool call is now logged to agent_audit_log for full traceability.
"""
import json
import random
import time
from datetime import datetime, timedelta
from . import database as db  # type: ignore

# Track the current task_id for audit logging
_current_task_id = "UNKNOWN"

def set_current_task(task_id: str):
    """Set the current task ID for audit trail logging."""
    global _current_task_id
    _current_task_id = task_id


class ToolResult:
    """Standardized tool response format for audit trail."""
    def __init__(self, success: bool, data: dict, tool_name: str, action: str, error_detail: str = ""):
        self.success = success
        self.data = data
        self.tool_name = tool_name
        self.action = action
        self.error_detail = error_detail  # Human-readable error explanation
        self.timestamp = datetime.now().isoformat()

        # AUTO-LOG to audit trail (this was the critical gap — tool calls were never logged!)
        try:
            db.log_agent_action(
                task_id=_current_task_id,
                agent_name="Execution_Agent",
                action=action,
                tool_used=tool_name,
                input_data={"action": action},
                output_data=data,
                success=success,
                error_detail=error_detail
            )
        except Exception:
            pass  # Don't let audit logging crash the tool

    def to_dict(self):
        result = {
            "success": self.success,
            "data": self.data,
            "tool": self.tool_name,
            "action": self.action,
            "timestamp": self.timestamp,
        }
        if self.error_detail:
            result["error_detail"] = self.error_detail
        if not self.success:
            result["error"] = self.data.get("error", "UNKNOWN")
        return result

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} [{self.tool_name}] {self.action}: {json.dumps(self.data)}"


# =====================================================
# TOOL 1: HR System (Employee Records)
# =====================================================
class HRSystemTool:
    """Simulates an enterprise HR system (like Workday, BambooHR)."""

    _employees = {}

    def create_employee_record(self, employee_data: dict) -> ToolResult:
        """Create employee record in HR system."""
        emp_id = employee_data.get("employee_id", "UNKNOWN")
        name = employee_data.get("employee_name", emp_id)

        # Edge case: Detect missing critical fields
        missing = []
        for field in ["employee_name", "employee_id", "role", "department"]:
            if not employee_data.get(field):
                missing.append(field)
        if missing:
            return ToolResult(
                False,
                {"error": "MISSING_REQUIRED_FIELDS", "code": 422,
                 "missing_fields": missing},
                "HR_System", f"Create record for {name}",
                error_detail=f"HR System rejected record: missing required fields {missing}. "
                             f"Enterprise compliance requires all fields before provisioning. "
                             f"Self-healing: Auto-filling from organizational defaults."
            )

        # Edge case: Employee already exists in one system but not others (cross-system inconsistency)
        if random.random() < 0.07:
            return ToolResult(
                False,
                {"error": "PARTIAL_EXISTENCE", "code": 409,
                 "message": f"Employee '{name}' found in Active Directory but NOT in Workday",
                 "existing_systems": ["Active Directory", "SSO"],
                 "missing_systems": ["Workday", "BambooHR"]},
                "HR_System", f"Create record for {name}",
                error_detail=f"Cross-system inconsistency: Employee '{name}' already has an Active Directory "
                             f"account (created during a previous partial onboarding attempt) but no Workday record exists. "
                             f"Self-healing: Creating missing records to sync all systems. Previous AD account will be linked."
            )

        # Edge case: Conflicting start date (submitted vs system)
        start_date = employee_data.get("start_date", "")
        if start_date and random.random() < 0.06:
            return ToolResult(
                False,
                {"error": "CONFLICTING_JOIN_DATE", "code": 409,
                 "submitted_date": start_date,
                 "system_date": "2026-04-07",
                 "message": f"Join date conflict: HR submitted '{start_date}' but manager calendar shows '2026-04-07'"},
                "HR_System", f"Create record for {name}",
                error_detail=f"Date conflict detected: The submitted start date '{start_date}' conflicts with the "
                             f"manager's availability calendar which shows onboarding scheduled for 2026-04-07. "
                             f"Self-healing: Using the submitted date and flagging for manager confirmation."
            )

        # 10% chance of timeout (realistic enterprise system)
        if random.random() < 0.10:
            return ToolResult(
                False,
                {"error": "HR_SYSTEM_TIMEOUT", "code": 504},
                "HR_System", f"Create record for {name}",
                error_detail=f"HR System (Workday) connection timed out after 30s. The database server at hr-db.internal:5432 did not respond. This is a transient network issue — retrying with exponential backoff."
            )

        # 5% chance of credential expiry mid-execution
        if random.random() < 0.05:
            return ToolResult(
                False,
                {"error": "AUTH_TOKEN_EXPIRED", "code": 401},
                "HR_System", f"Create record for {name}",
                error_detail=f"OAuth2 access token for HR System has expired (issued 3600s ago). "
                             f"Self-healing: Refreshing token using service account credentials and retrying."
            )

        self._employees[emp_id] = {
            **employee_data,
            "status": "ACTIVE",
            "created_at": datetime.now().isoformat()
        }
        # Persist to enterprise database
        db.insert_employee(employee_data)
        return ToolResult(True, {
            "employee_id": emp_id,
            "employee_name": name,
            "status": "RECORD_CREATED",
            "systems_updated": ["Workday", "Active Directory", "SSO"]
        }, "HR_System", f"Create record for {name}")

    def assign_buddy(self, employee_id: str, buddy_pool: list) -> ToolResult:
        """Assign an onboarding buddy from the available pool."""
        if not buddy_pool:
            buddy_pool = ["Ananya Desai (SDE-III)", "Vikram Patel (Tech Lead)"]

        # Edge case: Empty buddy pool after filtering
        if len(buddy_pool) == 0:
            return ToolResult(
                False,
                {"error": "EMPTY_BUDDY_POOL", "code": 404,
                 "message": "No eligible buddies found in department"},
                "HR_System", f"Assign buddy for {employee_id}",
                error_detail=f"All buddies in the pool are either on PTO or already assigned to another new hire. "
                             f"Self-healing: Expanding search to adjacent teams and senior IC pool."
            )

        # 30% chance buddy is unavailable
        if random.random() < 0.30:
            return ToolResult(
                False,
                {"error": "BUDDY_CALENDAR_CONFLICT", "code": 409},
                "HR_System", f"Assign buddy for {employee_id}",
                error_detail=f"Calendar conflict detected: First-choice buddy is on PTO next week. The system auto-selects next available buddy from the pool and retries assignment."
            )

        buddy = random.choice(buddy_pool) if isinstance(buddy_pool, list) else "Ananya Desai (SDE-III)"
        # Persist buddy assignment
        db.update_employee_buddy(employee_id, buddy)
        return ToolResult(True, {
            "employee_id": employee_id,
            "buddy_assigned": buddy,
            "buddy_start_date": "Day 1",
            "orientation_scheduled": True
        }, "HR_System", f"Assign buddy for {employee_id}")

    def get_employee_status(self, employee_id: str) -> ToolResult:
        """Check employee status."""
        if employee_id in self._employees:
            return ToolResult(True, self._employees[employee_id],
                            "HR_System", f"Get status for {employee_id}")
        return ToolResult(False, {"error": "EMPLOYEE_NOT_FOUND"},
                         "HR_System", f"Get status for {employee_id}",
                         error_detail=f"Employee {employee_id} not found in HR database. This is expected for new hires — record will be created during onboarding.")


# =====================================================
# TOOL 2: JIRA / Project Tracker
# =====================================================
class JIRAConnectorTool:
    """Simulates JIRA or similar project management system."""

    _failure_count = 0

    def create_account(self, employee_id: str, role: str) -> ToolResult:
        """Create JIRA account — INTENTIONALLY UNRELIABLE (as per scenario pack)."""
        self._failure_count += 1

        # First attempt ALWAYS fails (matches Track 2 scenario requirement)
        if self._failure_count <= 1:
            return ToolResult(False, {
                "error": "HTTP_403_FORBIDDEN",
                "code": 403,
                "message": "Admin API quota exceeded"
            }, "JIRA", f"Create account for {employee_id} (role: {role})",
            error_detail=f"HTTP 403 Forbidden — Atlassian Cloud Admin API rate limit exceeded. The JIRA provisioning endpoint allows 10 account creations per minute. Self-healing action: Waiting for cooldown period, then retrying with rotated API credentials.")

        # 20% chance of failure on retries (429 rate limit)
        if random.random() < 0.20:
            return ToolResult(False, {
                "error": "HTTP_429_RATE_LIMITED",
                "code": 429,
                "message": "Too many requests",
                "retry_after_seconds": 15
            }, "JIRA", f"Create account for {employee_id} (role: {role})",
            error_detail=f"HTTP 429 Too Many Requests — The Atlassian API is still throttling. Rate limit resets in 15 seconds. Self-healing action: Backing off exponentially and retrying.")

        # 5% chance of malformed response (API returns success but data is wrong)
        if random.random() < 0.05:
            return ToolResult(False, {
                "error": "MALFORMED_RESPONSE",
                "code": 200,
                "message": "API returned 200 but response body is empty"
            }, "JIRA", f"Create account for {employee_id} (role: {role})",
            error_detail=f"HTTP 200 OK but response body was empty or malformed. API returned success code "
                        f"but account may not have been created. Self-healing: Verifying account existence before retrying.")

        self._failure_count = 0
        # Persist JIRA account creation as a task
        db.insert_jira_task({
            "task_id": f"JIRA-ACC-{employee_id}",
            "title": f"JIRA Account Created: {employee_id}",
            "assignee": employee_id,
            "description": f"Auto-provisioned JIRA account for {employee_id} with role {role}",
            "status": "DONE",
            "project": "ONBOARD"
        })
        return ToolResult(True, {
            "employee_id": employee_id,
            "jira_username": f"{employee_id.lower()}@company.jira",
            "role": role,
            "projects_assigned": ["ONBOARD", "TEAM-ENG"],
            "status": "ACCOUNT_CREATED"
        }, "JIRA", f"Create account for {employee_id} (role: {role})")

    def create_task(self, title: str, assignee: str, description: str = "") -> ToolResult:
        """Create a task/ticket in JIRA."""
        task_id = f"TASK-{random.randint(1000, 9999)}"
        # Persist JIRA task
        db.insert_jira_task({
            "task_id": task_id,
            "title": title,
            "assignee": assignee,
            "description": description,
            "status": "TODO",
            "project": "AGENTFLOW"
        })
        return ToolResult(True, {
            "task_id": task_id,
            "title": title,
            "assignee": assignee,
            "status": "TODO",
        }, "JIRA", f"Create task: {title[:50]}")

    @classmethod
    def reset(cls):
        """Reset failure counter for new scenario runs."""
        cls._failure_count = 0


# =====================================================
# TOOL 3: Communication (Slack / Email)
# =====================================================
class CommunicationTool:
    """Simulates Slack, Email, and notification systems."""

    _sent_messages = []

    def send_notification(self, recipients: list, subject: str, body: str,
                         channel: str = "email") -> ToolResult:
        """Send notification via email or Slack."""
        # Edge case: Empty recipients
        if not recipients or all(not r for r in recipients):
            return ToolResult(
                False,
                {"error": "NO_RECIPIENTS", "code": 422,
                 "message": "No valid recipients specified"},
                "Communication", f"Send {channel} notification",
                error_detail=f"Cannot send notification: recipient list is empty or contains only invalid entries. "
                             f"Self-healing: Checking scenario data for alternative contacts."
            )

        # 8% chance of SMTP failure
        if random.random() < 0.08:
            return ToolResult(
                False,
                {"error": "SMTP_RELAY_FAILED", "code": 550},
                "Communication", f"Send {channel} to {len(recipients)} recipients",
                error_detail=f"SMTP relay rejected: Mail server smtp.company.com returned error 550 'Relay access denied'. The corporate email gateway is temporarily blocking outbound messages. Self-healing action: Falling back to Slack notification channel."
            )

        msg_id = f"MSG-{random.randint(10000, 99999)}"
        self._sent_messages.append({
            "id": msg_id, "recipients": recipients,
            "subject": subject, "channel": channel
        })
        # Persist notification
        db.insert_notification({
            "message_id": msg_id,
            "recipients": recipients[:3],
            "subject": subject,
            "channel": channel
        })
        return ToolResult(True, {
            "message_id": msg_id,
            "recipients": recipients[:3],
            "channel": channel,
            "status": "DELIVERED"
        }, "Communication", f"Send {channel} to {len(recipients)} recipients")

    def send_welcome_pack(self, employee_name: str, employee_email: str) -> ToolResult:
        """Send onboarding welcome pack."""
        # Edge case: Invalid email
        if not employee_email or "@" not in str(employee_email):
            return ToolResult(
                False,
                {"error": "INVALID_RECIPIENT_EMAIL", "code": 422,
                 "message": f"Invalid email address: '{employee_email}'"},
                "Communication", f"Send welcome pack to {employee_name}",
                error_detail=f"Cannot deliver welcome pack: email '{employee_email}' is invalid. "
                             f"Self-healing: Generating email from name convention (firstname.lastname@company.com)."
            )

        return ToolResult(True, {
            "recipient": employee_name,
            "email": employee_email,
            "pack_contents": ["Company Handbook", "IT Setup Guide", "Benefits Overview", "Day 1 Checklist"],
            "delivery_method": "Email + Slack DM",
            "status": "WELCOME_PACK_SENT"
        }, "Communication", f"Send welcome pack to {employee_name}")


# =====================================================
# TOOL 4: Calendar System
# =====================================================
class CalendarTool:
    """Simulates Google Calendar / Outlook scheduling."""

    def schedule_meeting(self, title: str, participants: list,
                        date: str, duration_minutes: int = 60) -> ToolResult:
        """Schedule a meeting."""
        # Edge case: No participants
        if not participants or all(not p for p in participants):
            return ToolResult(
                False,
                {"error": "NO_PARTICIPANTS", "code": 422,
                 "message": "Cannot schedule meeting with no participants"},
                "Calendar", f"Schedule: {title}",
                error_detail=f"Meeting '{title}' has no valid participants. "
                             f"Self-healing: Using scenario data to populate participant list."
            )

        meeting_id = f"MTG-{random.randint(1000, 9999)}"
        # Persist calendar event
        db.insert_calendar_event({
            "meeting_id": meeting_id,
            "title": title,
            "participants": participants[:4],
            "date": date,
            "duration_minutes": duration_minutes
        })
        return ToolResult(True, {
            "meeting_id": meeting_id,
            "title": title,
            "participants": participants[:4],
            "date": date,
            "duration": f"{duration_minutes}min",
            "calendar_link": f"https://calendar.company.com/{meeting_id}",
            "status": "SCHEDULED"
        }, "Calendar", f"Schedule: {title}")


# =====================================================
# TOOL 5: Approval System (Procurement)
# =====================================================
class ApprovalSystemTool:
    """Simulates an enterprise approval/procurement system."""

    _delegation_chain = []  # Track delegation chain for circular detection

    def get_approval_status(self, approval_id: str) -> ToolResult:
        """Check status of a pending approval."""
        # Edge case: Approval already completed outside the system (email chain, verbal, etc.)
        if random.random() < 0.08:
            return ToolResult(True, {
                "approval_id": approval_id,
                "status": "ALREADY_APPROVED",
                "approved_by": "Arun Kapoor (Director Operations)",
                "approved_at": datetime.now().isoformat(),
                "message": "Approval was completed outside the system via email chain",
                "resolution_path": "OUT_OF_BAND",
                "audit_note": "System detected this was resolved externally — no further action needed"
            }, "ApprovalSystem", f"Get status for {approval_id}")

        # Edge case: Simultaneous resolution — another agent/person resolved it while we're checking
        if random.random() < 0.05:
            return ToolResult(True, {
                "approval_id": approval_id,
                "status": "RESOLVED_CONCURRENT",
                "resolved_by": "Pooja Reddy (Senior Manager)",
                "resolved_at": datetime.now().isoformat(),
                "message": "Approval was resolved by another process while this check was in progress",
                "resolution_path": "PARALLEL_RESOLUTION"
            }, "ApprovalSystem", f"Get status for {approval_id}")

        return ToolResult(True, {
            "approval_id": approval_id,
            "status": "STUCK",
            "pending_since_hours": 48,
            "current_approver": "Meera Shankar (VP Operations)",
            "approver_status": "ON_LEAVE_MEDICAL",
            "return_date": "2026-03-30",
            "sla_deadline": "2026-03-27T09:00:00",
            "sla_hours_remaining": 12,
            "amount": "₹45,00,000",
            "risk_level": "HIGH"
        }, "ApprovalSystem", f"Get status for {approval_id}")

    def get_delegates(self, approver_name: str) -> ToolResult:
        """Find authorized delegates for an approver."""
        delegates = [
            {"name": "Arun Kapoor", "title": "Director Operations", "authority_level": "FULL"},
            {"name": "Pooja Reddy", "title": "Senior Manager", "authority_level": "PARTIAL_UNDER_50L"}
        ]

        # Edge case: Track delegation chain for circular detection
        self._delegation_chain.append(approver_name)
        
        # Edge case: No delegates available (both on leave)
        if random.random() < 0.08:
            return ToolResult(
                False,
                {"error": "NO_DELEGATES_AVAILABLE", "code": 404,
                 "message": "All authorized delegates are currently unavailable"},
                "ApprovalSystem", f"Get delegates for {approver_name}",
                error_detail=f"No delegates available for '{approver_name}': "
                             f"Arun Kapoor is in a conference (unavailable until 4 PM), "
                             f"Pooja Reddy is on annual leave. "
                             f"Self-healing: Escalating to next level of authority (CEO office)."
            )

        return ToolResult(True, {
            "original_approver": approver_name,
            "delegates": delegates,
            "delegation_policy": "Auto-delegate allowed for amounts under ₹50L when approver is on leave",
            "delegation_chain": self._delegation_chain[-3:]  # Show recent chain for audit
        }, "ApprovalSystem", f"Get delegates for {approver_name}")

    def reroute_approval(self, approval_id: str, new_approver: str,
                        reason: str) -> ToolResult:
        """Reroute an approval to a delegate."""
        # Edge case: Circular delegation check
        self._delegation_chain.append(new_approver)
        approver_names = [n.split("(")[0].strip().lower() for n in self._delegation_chain]
        if len(approver_names) != len(set(approver_names)):
            return ToolResult(
                False,
                {"error": "CIRCULAR_DELEGATION", "code": 409,
                 "chain": self._delegation_chain,
                 "message": f"Circular delegation detected: {' → '.join(self._delegation_chain)}"},
                "ApprovalSystem", f"Reroute {approval_id} to {new_approver}",
                error_detail=f"CRITICAL: Circular delegation loop detected. Approval keeps bouncing between "
                             f"the same people: {' → '.join(self._delegation_chain)}. "
                             f"Self-healing: Breaking the loop and escalating to VP/CEO level authority."
            )

        # Edge case: Delegate lacks authority for this amount
        if random.random() < 0.08:
            return ToolResult(
                False,
                {"error": "INSUFFICIENT_AUTHORITY", "code": 403,
                 "message": f"{new_approver} can only approve amounts under ₹50L"},
                "ApprovalSystem", f"Reroute {approval_id} to {new_approver}",
                error_detail=f"Delegate '{new_approver}' has PARTIAL authority (under ₹50L) but this "
                             f"approval is for ₹45,00,000. While within limit, the system requires explicit "
                             f"senior override for amounts above ₹25L. Self-healing: Adding co-approval from next delegate in chain."
            )

        # 15% chance the delegate is also unavailable
        if random.random() < 0.15:
            return ToolResult(
                False,
                {"error": "DELEGATE_UNAVAILABLE", "code": 503,
                 "message": f"{new_approver} is in a meeting"},
                "ApprovalSystem", f"Reroute {approval_id} to {new_approver}",
                error_detail=f"Delegate '{new_approver}' is currently unavailable (status: IN_MEETING). The approval system cannot obtain digital signature. Self-healing action: Scheduling retry in 5 minutes or escalating to next delegate in chain."
            )

        audit_id = f"AUD-{random.randint(10000, 99999)}"
        # Persist approval reroute
        db.update_approval_request(approval_id, new_approver, reason, audit_id)
        return ToolResult(True, {
            "approval_id": approval_id,
            "rerouted_to": new_approver,
            "reason": reason,
            "override_logged": True,
            "audit_id": audit_id,
            "compliance_check": "PASSED",
            "delegation_chain": self._delegation_chain[-3:],
            "status": "REROUTED_PENDING_DELEGATE"
        }, "ApprovalSystem", f"Reroute {approval_id} to {new_approver}")

    @classmethod
    def reset_chain(cls):
        """Reset delegation chain for new scenario."""
        cls._delegation_chain = []


# =====================================================
# TOOL 6: ERP System (Legacy)
# =====================================================
class ERPConnectorTool:
    """Standardized MCP Tool for Enterprise Data Retrieval."""

    def fetch_shipment_data(self, shipment_id: str) -> str:
        database = {
            "IN-MUNDRA-992": {
                "cargo": "High-Precision Semiconductor Sensors",
                "priority": "LEVEL_1",
                "daily_penalty": 500000,
                "alternate_port": "Port of Kandla"
            }
        }
        return json.dumps(database.get(shipment_id, {"error": "Record not found"}))


# =====================================================
# Initialize all tool instances
# =====================================================
hr_tool = HRSystemTool()
jira_tool = JIRAConnectorTool()
comms_tool = CommunicationTool()
calendar_tool = CalendarTool()
approval_tool = ApprovalSystemTool()
erp_tool = ERPConnectorTool()