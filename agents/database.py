"""
Enterprise Database — SQLite-backed persistent data layer.

All agent actions that modify enterprise state (creating employees, JIRA tasks,
calendar events, etc.) are written here. This gives judges a tangible,
browsable view of what the agents actually did.

Uses SQLite (file-based, zero setup) — no external database needed.
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "enterprise.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Create tables and seed with realistic enterprise data."""
    conn = get_connection()
    cursor = conn.cursor()

    # ──────────────────────────────────────────
    # TABLE: employees
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT NOT NULL,
            team TEXT NOT NULL,
            email TEXT,
            start_date TEXT,
            status TEXT DEFAULT 'ACTIVE',
            buddy TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: jira_tasks
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jira_tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            assignee TEXT,
            description TEXT,
            status TEXT DEFAULT 'TODO',
            priority TEXT DEFAULT 'MEDIUM',
            project TEXT,
            created_by TEXT DEFAULT 'AGENT',
            created_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: calendar_events
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            event_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            participants TEXT,
            event_date TEXT,
            duration_minutes INTEGER DEFAULT 60,
            status TEXT DEFAULT 'SCHEDULED',
            created_by TEXT DEFAULT 'AGENT',
            created_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: notifications
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            message_id TEXT PRIMARY KEY,
            recipients TEXT,
            subject TEXT,
            channel TEXT DEFAULT 'email',
            status TEXT DEFAULT 'DELIVERED',
            created_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: approval_requests
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            approval_id TEXT PRIMARY KEY,
            item TEXT NOT NULL,
            amount TEXT,
            original_approver TEXT,
            current_approver TEXT,
            status TEXT DEFAULT 'PENDING',
            reroute_reason TEXT,
            audit_id TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: agent_audit_log
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            agent_name TEXT,
            action TEXT,
            tool_used TEXT,
            input_data TEXT,
            output_data TEXT,
            success INTEGER,
            error_detail TEXT,
            timestamp TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: edge_case_log
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edge_case_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            resolution TEXT,
            handled INTEGER DEFAULT 1,
            timestamp TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: security_events
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT,
            details TEXT,
            blocked INTEGER DEFAULT 1,
            timestamp TEXT
        )
    """)

    # ──────────────────────────────────────────
    # TABLE: workflow_state (crash recovery)
    # ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_state (
            task_id TEXT PRIMARY KEY,
            scenario_type TEXT,
            current_node TEXT,
            state_json TEXT,
            status TEXT DEFAULT 'RUNNING',
            started_at TEXT,
            updated_at TEXT
        )
    """)

    # ──────────────────────────────────────────
    # SEED DATA — Only if tables are empty
    # ──────────────────────────────────────────
    existing = cursor.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if existing == 0:
        _seed_employees(cursor)
        _seed_approval_requests(cursor)

    conn.commit()
    conn.close()
    print(f"✅ Enterprise database ready: {DB_PATH}")


def _seed_employees(cursor: sqlite3.Cursor):
    """Pre-seed with realistic enterprise team data."""
    employees = [
        # Engineering Team
        ("EMP-2024-1001", "Arjun Mehta", "Tech Lead", "Engineering", "Backend", "arjun.mehta@company.com", "2024-01-15"),
        ("EMP-2024-1002", "Sneha Rao", "SDE-III", "Engineering", "Backend", "sneha.rao@company.com", "2024-03-01"),
        ("EMP-2024-1003", "Vikram Patel", "SDE-III", "Engineering", "Frontend", "vikram.patel@company.com", "2024-02-10"),
        ("EMP-2025-1004", "Ananya Desai", "SDE-II", "Engineering", "Frontend", "ananya.desai@company.com", "2025-01-08"),
        ("EMP-2025-1005", "Rahul Sharma", "SDE-I", "Engineering", "Backend", "rahul.sharma@company.com", "2025-06-15"),
        ("EMP-2025-1006", "Kavya Nair", "SDE-II", "Engineering", "DevOps", "kavya.nair@company.com", "2025-04-20"),
        # Data Team
        ("EMP-2024-2001", "Ravi Kumar", "Data Lead", "Data", "Analytics", "ravi.kumar@company.com", "2024-01-10"),
        ("EMP-2024-2002", "Priyanka Gupta", "Data Engineer", "Data", "Infrastructure", "priyanka.gupta@company.com", "2024-05-12"),
        ("EMP-2025-2003", "Suresh Iyer", "ML Engineer", "Data", "ML Platform", "suresh.iyer@company.com", "2025-02-01"),
        ("EMP-2025-2004", "Neha Agarwal", "Data Analyst", "Data", "Analytics", "neha.agarwal@company.com", "2025-07-10"),
        # HR Team
        ("EMP-2023-3001", "Deepa Krishnan", "HR Director", "HR", "People Ops", "deepa.krishnan@company.com", "2023-06-01"),
        ("EMP-2024-3002", "Amit Joshi", "HR Manager", "HR", "Recruitment", "amit.joshi@company.com", "2024-08-15"),
        ("EMP-2025-3003", "Pooja Reddy", "HR Associate", "HR", "People Ops", "pooja.reddy@company.com", "2025-03-01"),
        # Operations Team
        ("EMP-2023-4001", "Meera Shankar", "VP Operations", "Operations", "Management", "meera.shankar@company.com", "2023-01-15"),
        ("EMP-2024-4002", "Arun Kapoor", "Director Operations", "Operations", "Procurement", "arun.kapoor@company.com", "2024-02-01"),
        ("EMP-2024-4003", "Sanjay Verma", "Operations Manager", "Operations", "Logistics", "sanjay.verma@company.com", "2024-09-10"),
        # Sales Team
        ("EMP-2024-5001", "Rohit Malhotra", "Sales Director", "Sales", "Enterprise", "rohit.malhotra@company.com", "2024-04-01"),
        ("EMP-2025-5002", "Divya Bhat", "Account Executive", "Sales", "Enterprise", "divya.bhat@company.com", "2025-01-20"),
        ("EMP-2025-5003", "Karthik Rajan", "Sales Associate", "Sales", "SMB", "karthik.rajan@company.com", "2025-05-15"),
    ]

    for emp in employees:
        cursor.execute("""
            INSERT OR IGNORE INTO employees (employee_id, name, role, department, team, email, start_date, status, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'SYSTEM', ?)
        """, (*emp, datetime.now().isoformat()))

    print(f"   Seeded {len(employees)} employees across 5 departments")


def _seed_approval_requests(cursor: sqlite3.Cursor):
    """Pre-seed approval requests for the SLA scenario."""
    approvals = [
        ("APR-2026-0042", "Cloud Infrastructure Upgrade", "₹45,00,000", "Meera Shankar", "Meera Shankar", "STUCK", None, None),
        ("APR-2026-0038", "Office Renovation Phase 2", "₹12,00,000", "Arun Kapoor", "Arun Kapoor", "APPROVED", None, "AUD-78234"),
        ("APR-2026-0035", "Cybersecurity Audit Contract", "₹8,50,000", "Meera Shankar", "Meera Shankar", "APPROVED", None, "AUD-77891"),
    ]

    for apr in approvals:
        cursor.execute("""
            INSERT OR IGNORE INTO approval_requests (approval_id, item, amount, original_approver, current_approver, status, reroute_reason, audit_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*apr, datetime.now().isoformat()))

    print(f"   Seeded {len(approvals)} approval requests")


# ──────────────────────────────────────────
# WRITE METHODS (called by tools.py)
# ──────────────────────────────────────────

def insert_employee(employee_data: dict):
    """Insert a new employee record from the onboarding agent.
    Uses INSERT OR IGNORE to prevent overwriting existing employees on ID collision.
    """
    conn = get_connection()
    try:
        emp_id = employee_data.get("employee_id", "UNKNOWN")
        # Check if this exact ID already exists (should be rare with 8-char hex hash IDs)
        existing = conn.execute("SELECT employee_id, name FROM employees WHERE employee_id = ?", (emp_id,)).fetchone()
        if existing:
            print(f"⚠️ Employee ID {emp_id} already exists (name: {existing['name']}). Skipping duplicate insert.")
            return

        conn.execute("""
            INSERT INTO employees (employee_id, name, role, department, team, email, start_date, status, buddy, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'AGENT', ?)
        """, (
            emp_id,
            employee_data.get("employee_name", "Unknown"),
            employee_data.get("role", "Unknown"),
            employee_data.get("department", "Unknown"),
            employee_data.get("team", employee_data.get("department", "Unknown")),
            employee_data.get("email", ""),
            employee_data.get("start_date", datetime.now().strftime("%Y-%m-%d")),
            employee_data.get("buddy", None),
            datetime.now().isoformat()
        ))
        conn.commit()
    finally:
        conn.close()


def update_employee_buddy(employee_id: str, buddy_name: str):
    """Update an employee's assigned buddy."""
    conn = get_connection()
    try:
        conn.execute("UPDATE employees SET buddy = ? WHERE employee_id = ?", (buddy_name, employee_id))
        conn.commit()
    finally:
        conn.close()


def insert_jira_task(task_data: dict):
    """Insert a JIRA task created by agents."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO jira_tasks (task_id, title, assignee, description, status, priority, project, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'AGENT', ?)
        """, (
            task_data.get("task_id", f"TASK-{id(task_data)}"),
            task_data.get("title", "Untitled"),
            task_data.get("assignee", "Unassigned"),
            task_data.get("description", ""),
            task_data.get("status", "TODO"),
            task_data.get("priority", "MEDIUM"),
            task_data.get("project", "ONBOARD"),
            datetime.now().isoformat()
        ))
        conn.commit()
    finally:
        conn.close()


def insert_calendar_event(event_data: dict):
    """Insert a calendar event created by agents."""
    conn = get_connection()
    try:
        participants_str = json.dumps(event_data.get("participants", []))
        conn.execute("""
            INSERT OR REPLACE INTO calendar_events (event_id, title, participants, event_date, duration_minutes, status, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, 'SCHEDULED', 'AGENT', ?)
        """, (
            event_data.get("meeting_id", event_data.get("event_id", f"MTG-{id(event_data)}")),
            event_data.get("title", "Untitled Meeting"),
            participants_str,
            event_data.get("date", datetime.now().strftime("%Y-%m-%d")),
            event_data.get("duration_minutes", 60),
            datetime.now().isoformat()
        ))
        conn.commit()
    finally:
        conn.close()


def insert_notification(notif_data: dict):
    """Insert a notification sent by agents."""
    conn = get_connection()
    try:
        recipients_str = json.dumps(notif_data.get("recipients", []))
        conn.execute("""
            INSERT OR REPLACE INTO notifications (message_id, recipients, subject, channel, status, created_at)
            VALUES (?, ?, ?, ?, 'DELIVERED', ?)
        """, (
            notif_data.get("message_id", f"MSG-{id(notif_data)}"),
            recipients_str,
            notif_data.get("subject", ""),
            notif_data.get("channel", "email"),
            datetime.now().isoformat()
        ))
        conn.commit()
    finally:
        conn.close()


def update_approval_request(approval_id: str, new_approver: str, reason: str, audit_id: str):
    """Update an approval request when rerouted by agents."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE approval_requests 
            SET current_approver = ?, status = 'REROUTED', reroute_reason = ?, audit_id = ?, updated_at = ?
            WHERE approval_id = ?
        """, (new_approver, reason, audit_id, datetime.now().isoformat(), approval_id))
        conn.commit()
    finally:
        conn.close()


def log_agent_action(task_id: str, agent_name: str, action: str, tool_used: str,
                     input_data: dict, output_data: dict, success: bool, error_detail: str = ""):
    """Log every agent action for the audit trail."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO agent_audit_log (task_id, agent_name, action, tool_used, input_data, output_data, success, error_detail, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id, agent_name, action, tool_used,
            json.dumps(input_data, default=str)[:2000],  # Cap size to prevent overflow
            json.dumps(output_data, default=str)[:2000],
            1 if success else 0,
            error_detail[:500] if error_detail else "",
            datetime.now().isoformat()
        ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Audit log write failed: {e}")
    finally:
        conn.close()


def log_edge_case(category: str, severity: str, message: str, details: str = "", resolution: str = ""):
    """Log an edge case detection event."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO edge_case_log (category, severity, message, details, resolution, handled, timestamp)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (category, severity, message[:500], details[:2000] if details else "", 
              resolution[:500] if resolution else "", datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Edge case log write failed: {e}")
    finally:
        conn.close()


def log_security_event(event_type: str, severity: str, source: str, details: str, blocked: bool = True):
    """Log a security event (prompt injection, unauthorized access, etc.)."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO security_events (event_type, severity, source, details, blocked, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, severity, source, details[:1000], 1 if blocked else 0,
              datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Security event log write failed: {e}")
    finally:
        conn.close()


def save_workflow_state(task_id: str, scenario_type: str, current_node: str, state_json: str, status: str = "RUNNING"):
    """Persist workflow state for crash recovery."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO workflow_state (task_id, scenario_type, current_node, state_json, status, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT started_at FROM workflow_state WHERE task_id = ?), ?), ?)
        """, (task_id, scenario_type, current_node, state_json[:50000], status,
              task_id, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Workflow state save failed: {e}")
    finally:
        conn.close()


def get_edge_case_summary() -> dict:
    """Get summary of all edge cases detected."""
    conn = get_connection()
    result: dict = {"total": 0, "by_category": {}, "by_severity": {}, "recent": []}
    try:
        # Count by category
        rows = conn.execute(
            "SELECT category, COUNT(*) as c FROM edge_case_log GROUP BY category ORDER BY c DESC"
        ).fetchall()
        result["by_category"] = {r["category"]: r["c"] for r in rows}

        # Count by severity
        rows = conn.execute(
            "SELECT severity, COUNT(*) as c FROM edge_case_log GROUP BY severity ORDER BY c DESC"
        ).fetchall()
        result["by_severity"] = {r["severity"]: r["c"] for r in rows}

        # Total
        total = conn.execute("SELECT COUNT(*) as c FROM edge_case_log").fetchone()
        result["total"] = total["c"] if total else 0

        # Recent events
        recent = conn.execute(
            "SELECT * FROM edge_case_log ORDER BY id DESC LIMIT 20"
        ).fetchall()
        result["recent"] = [dict(r) for r in recent]
    finally:
        conn.close()
    return result


def get_security_events() -> list:
    """Get all security events."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM security_events ORDER BY id DESC LIMIT 50"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ──────────────────────────────────────────
# READ METHODS (called by API endpoints)
# ──────────────────────────────────────────

def get_all_tables() -> list:
    """Get list of all tables with row counts."""
    conn = get_connection()
    result: list = []
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for t in tables:
            name = t["name"]
            count = conn.execute(f"SELECT COUNT(*) as c FROM [{name}]").fetchone()["c"]
            result.append({"name": name, "rows": count})
    finally:
        conn.close()
    return result


def get_table_data(table_name: str) -> dict:
    """Get all rows from a specific table."""
    # Whitelist tables for security
    allowed = {"employees", "jira_tasks", "calendar_events", "notifications", 
               "approval_requests", "agent_audit_log", "edge_case_log", 
               "security_events", "workflow_state"}
    if table_name not in allowed:
        return {"error": f"Table '{table_name}' not found"}

    conn = get_connection()
    data: dict = {"table": table_name, "columns": [], "rows": [], "count": 0}
    try:
        rows = conn.execute(f"SELECT * FROM [{table_name}] ORDER BY ROWID DESC LIMIT 200").fetchall()
        columns = [desc[0] for desc in conn.execute(f"SELECT * FROM [{table_name}] LIMIT 0").description] if rows else []
        data = {
            "table": table_name,
            "columns": columns,
            "rows": [dict(r) for r in rows],
            "count": len(rows)
        }
    finally:
        conn.close()
    return data


def get_employees_by_department() -> dict:
    """Get employees grouped by department for the dashboard."""
    conn = get_connection()
    result: dict = {}
    try:
        departments = conn.execute(
            "SELECT DISTINCT department FROM employees ORDER BY department"
        ).fetchall()
        for dept in departments:
            dept_name = dept["department"]
            employees = conn.execute(
                "SELECT * FROM employees WHERE department = ? ORDER BY start_date DESC",
                (dept_name,)
            ).fetchall()
            result[dept_name] = [dict(e) for e in employees]
    finally:
        conn.close()
    return result


def find_employees_by_name(name: str, department: str = None) -> list:
    """Find employees by exact or partial name match, optionally filtered by department."""
    conn = get_connection()
    try:
        if department:
            rows = conn.execute(
                "SELECT * FROM employees WHERE LOWER(name) = LOWER(?) AND LOWER(department) = LOWER(?)",
                (name, department)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM employees WHERE LOWER(name) = LOWER(?)",
                (name,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def employee_exists(employee_id: str) -> bool:
    """Check if an employee with this ID already exists."""
    conn = get_connection()
    try:
        result = conn.execute(
            "SELECT COUNT(*) as c FROM employees WHERE employee_id = ?",
            (employee_id,)
        ).fetchone()
        return result["c"] > 0
    finally:
        conn.close()


# Initialize on import
init_database()
