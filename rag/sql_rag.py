"""
Module 4 — SQL RAG

Plain Python function: sql_rag_chain(question) -> str

Three explicit steps (grading requirement):
  1. Translate natural language question → SQL  (LLM call)
  2. Clean raw LLM output → bare SQL statement  (regex extraction)
  3. Execute SQL → pass results to LLM → natural language answer

Only callable by billing_executive and admin (enforced by the FastAPI
/chat endpoint; this module itself does not check roles).
"""

import re
import sqlite3
import logging
from pathlib import Path
from typing import Optional

import anthropic

log = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = _PROJECT_ROOT / "data" / "mediassist_data" / "db" / "mediassist.db"

# ── LLM ─────────────────────────────────────────────────────────────────
LLM_MODEL = "claude-haiku-4-5-20251001"
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env
    return _client


# ── Schema fed to the LLM ────────────────────────────────────────────────
_DB_SCHEMA = """
Database: mediassist.db  (SQLite)

Table: claims
  claim_id        TEXT PRIMARY KEY   -- e.g. CLM-2024-1000
  patient_id      TEXT               -- e.g. PAT-51347
  patient_name    TEXT
  department      TEXT               -- nephrology | cardiology | neurology |
                                     --   gynaecology | orthopaedics |
                                     --   general_medicine | emergency
  claim_type      TEXT               -- reimbursement | cashless
  diagnosis_code  TEXT               -- ICD-10 code e.g. N17.9
  insurer         TEXT               -- New India Assurance | Bajaj Allianz |
                                     --   United India | HDFC Ergo | Star Health |
                                     --   Care Health | ICICI Lombard | Niva Bupa
  claimed_amount  REAL
  approved_amount REAL               -- NULL when pending/rejected
  status          TEXT               -- pending | submitted | approved |
                                     --   rejected | escalated
  submitted_date  TEXT               -- YYYY-MM-DD
  resolved_date   TEXT               -- YYYY-MM-DD or NULL

Table: maintenance_tickets
  ticket_id       TEXT PRIMARY KEY   -- e.g. TKT-2024-2000
  equipment_name  TEXT               -- human-readable equipment name
  equipment_id    TEXT               -- e.g. EQ-HC-3588
  category        TEXT               -- sterilisation | infusion | radiology |
                                     --   monitoring | surgical | laboratory
  campus          TEXT               -- hospital/campus name
  issue_type      TEXT               -- preventive_maintenance | sensor_failure |
                                     --   battery_replacement | fault_reported |
                                     --   calibration_due
  fault_code      TEXT               -- may be NULL
  raised_by       TEXT
  raised_date     TEXT               -- YYYY-MM-DD
  resolved_date   TEXT               -- YYYY-MM-DD or NULL
  status          TEXT               -- open | in_progress | resolved | escalated
  resolution_note TEXT               -- may be NULL
"""


# ── Step 1: NL → SQL ─────────────────────────────────────────────────────

def _generate_sql(question: str) -> str:
    prompt = (
        "You are a SQLite expert. Using ONLY the schema below, write a single "
        "SQL query that answers the question.\n\n"
        f"Schema:\n{_DB_SCHEMA}\n"
        f"Question: {question}\n\n"
        "Rules:\n"
        "- Return ONLY the SQL query, no explanation, no markdown fences.\n"
        "- Use SQLite-compatible syntax.\n"
        "- End the query with a semicolon.\n"
        "- If the question cannot be answered from this schema, return: "
        "SELECT 'UNANSWERABLE' AS result;"
    )
    response = _get_client().messages.create(
        model=LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    log.debug("Raw SQL from LLM:\n%s", raw)
    return raw


# ── Step 2: Clean raw LLM output → bare SQL ──────────────────────────────

def _clean_sql(raw: str) -> str:
    """
    Strip markdown fences, explanation text, and trailing prose.
    Returns the first complete SQL statement found.
    """
    # Remove ```sql ... ``` or ``` ... ``` fences
    raw = re.sub(r"```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```", "", raw)

    # Find the first line that starts a SQL statement
    sql_start = re.search(
        r"^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP|EXPLAIN)",
        raw,
        re.IGNORECASE | re.MULTILINE,
    )
    if sql_start:
        raw = raw[sql_start.start():]

    # Truncate after the first semicolon (end of statement)
    semi = raw.find(";")
    if semi != -1:
        raw = raw[: semi + 1]

    return raw.strip()


# ── Step 3: Execute SQL → NL answer ─────────────────────────────────────

def _execute_sql(sql: str) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return {"columns": columns, "rows": rows, "error": None}
    except sqlite3.Error as exc:
        log.error("SQL execution error: %s\nSQL: %s", exc, sql)
        return {"columns": [], "rows": [], "error": str(exc)}
    finally:
        conn.close()


def _generate_answer(question: str, sql: str, result: dict) -> str:
    if result["error"]:
        rows_text = f"Error executing query: {result['error']}"
    elif not result["rows"]:
        rows_text = "Query returned no rows."
    else:
        header = " | ".join(result["columns"])
        data_rows = "\n".join(
            " | ".join(str(v) if v is not None else "NULL" for v in row)
            for row in result["rows"][:50]   # cap at 50 rows in prompt
        )
        rows_text = f"{header}\n{data_rows}"

    prompt = (
        "You are a helpful data analyst for MediAssist Health Network.\n"
        "Answer the question below using the SQL query results provided.\n"
        "Be concise and specific — include numbers where relevant.\n\n"
        f"Question: {question}\n\n"
        f"SQL executed:\n{sql}\n\n"
        f"Results:\n{rows_text}"
    )
    response = _get_client().messages.create(
        model=LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Public API ───────────────────────────────────────────────────────────

def sql_rag_chain(question: str) -> str:
    """
    Three-step SQL RAG chain.

    Parameters
    ----------
    question  Natural language analytical question about claims or
              maintenance tickets.

    Returns
    -------
    Natural language answer produced by the LLM from the query results.
    """
    log.info("SQL RAG | question: %s", question)

    # Step 1 — NL → SQL
    raw_sql = _generate_sql(question)
    log.info("Step 1 — raw LLM output:\n%s", raw_sql)

    # Step 2 — clean
    clean = _clean_sql(raw_sql)
    log.info("Step 2 — cleaned SQL:\n%s", clean)

    # Step 3 — execute + answer
    result = _execute_sql(clean)
    log.info(
        "Step 3 — %d row(s) returned%s",
        len(result["rows"]),
        f" | error: {result['error']}" if result["error"] else "",
    )

    answer = _generate_answer(question, clean, result)
    log.info("Answer: %s", answer[:120])
    return answer
