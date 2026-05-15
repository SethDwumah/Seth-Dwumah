"""
SethDesk API
FastAPI backend for Seth Dwumah's project management dashboard.
Deployable on Vercel | Database: SQLite (/tmp — ephemeral on Vercel)
AI: Google Gemini 1.5 Flash — multi-agent system (Research, Simulation, Planning, Writing)

Author: SethDesk Backend v1.0
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
import json
import os
import re
from datetime import datetime
from pathlib import Path

# ─── FASTAPI SETUP ───────────────────────────────────────────
app = FastAPI(title="SethDesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── DATABASE CONFIG ─────────────────────────────────────────
# Vercel writes to /tmp only; swap DB_URL env var to a postgres:// string
# (e.g. Supabase) for persistent production storage.
DB_PATH = os.environ.get("DB_PATH", "/tmp/sethdesk.db")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ─── DATABASE HELPERS ────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def row_to_dict(row) -> dict:
    return dict(row) if row else {}


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            type        TEXT DEFAULT 'other',
            priority    TEXT DEFAULT 'medium',
            status      TEXT DEFAULT 'active',
            progress    INTEGER DEFAULT 0,
            color       TEXT DEFAULT '#0F766E',
            due_date    TEXT,
            members     TEXT DEFAULT '["SD"]',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            project_id  INTEGER,
            status      TEXT DEFAULT 'todo',
            priority    TEXT DEFAULT 'medium',
            due_date    TEXT,
            notes       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            agent_name TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()

    # Seed only if projects table is empty
    c.execute("SELECT COUNT(*) FROM projects")
    if c.fetchone()[0] == 0:
        _seed(conn)

    conn.close()


def _seed(conn: sqlite3.Connection):
    """Populate initial project and task data for Seth."""
    c = conn.cursor()

    projects_seed = [
        ("MPhil Thesis — Hydrogen from Biomass Waste",
         "CO₂-hydrate water purification using hydrogen from biomass gasification at UENR.",
         "mphil", "high", "active", 65, "#0F766E", "2026-08-30"),
        ("Aspen HYSYS Simulation — NGL Recovery at GPP 2",
         "Cryogenic NGL recovery process simulation at Ghana GPP 2 for MPhil thesis Chapter 3 methodology.",
         "simulation", "high", "active", 40, "#6366F1", "2026-07-15"),
        ("SPE NAICE 2026 — ML Production Prediction",
         "Machine learning models for petroleum production prediction with SHAP attribution and Streamlit dashboard.",
         "academic", "high", "active", 80, "#8B5CF6", "2026-06-01"),
        ("SASEC 2026 Conference Paper",
         "Biomass to hydrogen for CO₂-hydrate water purification — Aspen Plus simulation and analysis. Submitted.",
         "academic", "medium", "completed", 100, "#10B981", "2026-05-01"),
        ("Coursework & Assignments — MPhil Year 1",
         "UENR MPhil coursework, assignments, and required academic deliverables for the academic year.",
         "teaching", "low", "active", 35, "#F59E0B", "2026-12-31"),
    ]

    for p in projects_seed:
        c.execute(
            "INSERT INTO projects (name,description,type,priority,status,progress,color,due_date) "
            "VALUES (?,?,?,?,?,?,?,?)", p
        )
    conn.commit()

    c.execute("SELECT id FROM projects ORDER BY id")
    pids = [row[0] for row in c.fetchall()]

    tasks_seed = [
        ("Write Chapter 3 — Methodology",           pids[0], "in-progress", "high",   "2026-05-25"),
        ("Literature review on hydrogen from biomass", pids[0], "completed",  "high",  "2026-04-20"),
        ("Run Aspen HYSYS simulation Case 2",         pids[1], "in-progress", "high",  "2026-05-20"),
        ("Validate simulation results against plant data", pids[1], "todo",   "high",  "2026-06-10"),
        ("Extract heat exchanger duty tables",        pids[1], "review",     "medium", "2026-05-18"),
        ("SHAP feature attribution analysis",         pids[2], "completed",  "high",   "2026-05-10"),
        ("Prepare Streamlit dashboard for ML model",  pids[2], "in-progress","medium", "2026-05-28"),
        ("Submit final paper to SPE NAICE 2026",      pids[2], "todo",       "urgent", "2026-06-01"),
        ("Finalize Aspen Plus simulation result tables", pids[3], "completed","medium","2026-04-28"),
        ("Write conference paper abstract",           pids[3], "completed",  "medium", "2026-04-15"),
        ("Review course materials — Reservoir Engineering", pids[4], "todo", "medium", "2026-05-30"),
        ("Submit term project report",                pids[4], "blocked",    "high",   "2026-05-15"),
    ]

    for t in tasks_seed:
        c.execute(
            "INSERT INTO tasks (name,project_id,status,priority,due_date) VALUES (?,?,?,?,?)", t
        )
    conn.commit()


# Run on import (cold-start safe)
init_db()


# ─── PYDANTIC MODELS ─────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    type: Optional[str] = "other"
    priority: Optional[str] = "medium"
    status: Optional[str] = "active"
    progress: Optional[int] = 0
    color: Optional[str] = "#0F766E"
    due_date: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    color: Optional[str] = None
    due_date: Optional[str] = None


class TaskCreate(BaseModel):
    name: str
    project_id: Optional[int] = None
    status: Optional[str] = "todo"
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None
    notes: Optional[str] = ""


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []


# ─── PROJECTS ENDPOINTS ──────────────────────────────────────
@app.get("/api/projects")
def get_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects (name,description,type,priority,status,progress,color,due_date) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (body.name, body.description, body.type, body.priority,
         body.status, body.progress, body.color, body.due_date)
    )
    conn.commit()
    c.execute("SELECT * FROM projects WHERE id=?", (c.lastrowid,))
    result = row_to_dict(c.fetchone())
    conn.close()
    return result


@app.put("/api/projects/{pid}")
def update_project(pid: int, body: ProjectUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields provided")
    conn = get_db()
    c = conn.cursor()
    set_sql = ", ".join(f"{k}=?" for k in fields)
    c.execute(f"UPDATE projects SET {set_sql} WHERE id=?", [*fields.values(), pid])
    conn.commit()
    c.execute("SELECT * FROM projects WHERE id=?", (pid,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")
    return row_to_dict(row)


@app.delete("/api/projects/{pid}")
def delete_project(pid: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
    c.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── TASKS ENDPOINTS ─────────────────────────────────────────
@app.get("/api/tasks")
def get_tasks():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks ORDER BY due_date ASC, created_at DESC")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (name,project_id,status,priority,due_date,notes) VALUES (?,?,?,?,?,?)",
        (body.name, body.project_id, body.status, body.priority, body.due_date, body.notes)
    )
    conn.commit()
    c.execute("SELECT * FROM tasks WHERE id=?", (c.lastrowid,))
    result = row_to_dict(c.fetchone())
    conn.close()
    return result


@app.put("/api/tasks/{tid}")
def update_task(tid: int, body: TaskUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields provided")
    conn = get_db()
    c = conn.cursor()
    set_sql = ", ".join(f"{k}=?" for k in fields)
    c.execute(f"UPDATE tasks SET {set_sql} WHERE id=?", [*fields.values(), tid])
    conn.commit()
    c.execute("SELECT * FROM tasks WHERE id=?", (tid,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Task not found")
    return row_to_dict(row)


@app.delete("/api/tasks/{tid}")
def delete_task(tid: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── AGENTIC CHAT ────────────────────────────────────────────

AGENTS: Dict[str, Dict] = {
    "research": {
        "name": "Dr. Mensah",
        "emoji": "🔬",
        "color": "#6366F1",
        "role": "Senior Research Expert in Petroleum & Chemical Engineering",
        "expertise": (
            "Academic research methodology, systematic literature review, petroleum reservoir engineering, "
            "hydrogen production from biomass gasification, CO₂ hydrate technology, gas processing, "
            "thermodynamic modelling, academic publishing (SPE, conference papers, journals)."
        ),
    },
    "simulation": {
        "name": "Eng. Kwame",
        "emoji": "⚙️",
        "color": "#F59E0B",
        "role": "Chemical Process Simulation Specialist",
        "expertise": (
            "Aspen HYSYS, Aspen Plus, process flowsheet design, cryogenic NGL recovery, "
            "thermodynamic property packages, column sequencing, heat exchanger networks, "
            "sensitivity analysis, simulation troubleshooting, Ghana GPP plant modelling."
        ),
    },
    "planning": {
        "name": "Coach Ada",
        "emoji": "📊",
        "color": "#0F766E",
        "role": "Academic Project Manager & Productivity Coach",
        "expertise": (
            "Research project planning, MPhil thesis timeline design, task decomposition, "
            "academic deadline management, milestone tracking, weekly sprints, "
            "research workflow optimisation, handling multiple concurrent projects."
        ),
    },
    "writing": {
        "name": "Prof. Olu",
        "emoji": "✍️",
        "color": "#10B981",
        "role": "Academic Writing Specialist",
        "expertise": (
            "SPE conference and journal papers, thesis chapter writing, abstract drafting, "
            "literature review structure, methodology sections, results & discussion, "
            "academic language style, paper formatting, editing and proofreading."
        ),
    },
}


def _route_agent(message: str) -> str:
    """Keyword-based routing — zero latency, no extra API call."""
    m = message.lower()

    # High-weight phrases that decisively identify an agent
    DECISIVE = {
        "simulation": ["hysys", "aspen plus", "aspen hysys", "flowsheet", "convergence",
                       "cryogenic", "ngl recovery", "gpp", "property package"],
        "planning":   ["plan my week", "plan this week", "help me plan", "next steps",
                       "what should i do", "prioritize", "schedule", "overdue"],
        "writing":    ["write the abstract", "draft the", "edit my", "proofread",
                       "citation style", "write a section"],
        "research":   ["literature review", "what is the mechanism", "co2 hydrate",
                       "hydrogen production", "biomass gasification"],
    }
    for agent, phrases in DECISIVE.items():
        if any(phrase in m for phrase in phrases):
            return agent

    # Standard keyword scoring
    scores = {
        "simulation": sum(1 for kw in [
            "hysys", "aspen", "simulation", "ngl", "cryogenic", "flowsheet",
            "column", "separator", "reactor", "heat exchanger", "thermodynamic",
            "flash", "stream", "compressor", "gpp", "tray", "reboiler"
        ] if kw in m),
        "research": sum(1 for kw in [
            "research", "literature", "reference", "citation", "hydrogen",
            "biomass", "co2", "hydrate", "methodology", "theory", "review",
            "reservoir", "petroleum", "gasification", "publication", "journal"
        ] if kw in m),
        "writing": sum(1 for kw in [
            "write", "draft", "paper", "abstract", "chapter",
            "paragraph", "section", "introduction", "conclusion",
            "edit", "proofread", "format", "references"
        ] if kw in m),
        "planning": sum(1 for kw in [
            "plan", "schedule", "deadline", "task", "project", "timeline",
            "organize", "priority", "week", "milestone", "progress",
            "manage", "overdue", "when", "next step", "todo", "focus"
        ] if kw in m),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "planning"


def _build_context(conn: sqlite3.Connection) -> str:
    c = conn.cursor()
    c.execute("SELECT id,name,status,progress,due_date,priority FROM projects")
    projects = [row_to_dict(r) for r in c.fetchall()]
    c.execute(
        "SELECT name,project_id,status,priority,due_date FROM tasks "
        "WHERE status != 'completed' ORDER BY due_date LIMIT 12"
    )
    active_tasks = [row_to_dict(r) for r in c.fetchall()]
    c.execute("SELECT status, COUNT(*) as n FROM tasks GROUP BY status")
    stats = {r["status"]: r["n"] for r in c.fetchall()}
    return (
        f"Seth's projects:\n{json.dumps(projects, indent=2)}\n\n"
        f"Active/pending tasks:\n{json.dumps(active_tasks, indent=2)}\n\n"
        f"Task status counts: {json.dumps(stats)}"
    )


def _call_gemini(system: str, history: list, message: str) -> str:
    """Call Gemini 2.5 Flash via REST to avoid heavy SDK on Vercel."""
    import urllib.request, urllib.error

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )

    # Build contents: system-as-first-user-turn trick supported by Gemini REST
    contents = []

    # Inject system prompt as a user/model exchange at the start
    contents.append({"role": "user",  "parts": [{"text": system}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I am ready to assist Seth."}]})

    # Past conversation (last 8 turns)
    for h in history[-8:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})

    # Current message
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = json.dumps({
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return (
        data["candidates"][0]["content"]["parts"][0]["text"]
        .strip()
    )


@app.post("/api/chat")
def chat(body: ChatRequest):
    if not GEMINI_API_KEY:
        return {
            "agent": "SethDesk AI", "emoji": "🤖", "color": "#0F766E",
            "message": (
                "⚠️ **Gemini API key not configured.**\n\n"
                "Add `GEMINI_API_KEY=your_key` to your `.env` file "
                "(or Vercel environment variables) to enable the AI assistant.\n\n"
                "Get a free key at https://aistudio.google.com/app/apikey"
            ),
        }

    conn = get_db()
    ctx = _build_context(conn)
    conn.close()

    agent_key = _route_agent(body.message)
    agent = AGENTS[agent_key]

    system_prompt = f"""You are {agent['name']}, {agent['role']}.
Your expertise: {agent['expertise']}

You are the personal AI assistant for Seth Dwumah, an MPhil candidate at the 
University of Energy and Natural Resources (UENR), Sunyani, Ghana.

Seth's workspace context (live data):
{ctx}

Guidelines:
- Be practical, specific, and concise (max 4 short paragraphs or a clean list).
- Reference Seth's actual projects and tasks when relevant.
- Use markdown formatting (bold, bullets) for clarity.
- If you recommend creating a task or updating progress, say so explicitly.
- Address Seth by name occasionally to keep the tone personal.
"""

    try:
        reply = _call_gemini(system_prompt, body.history, body.message)
    except Exception as exc:
        reply = (
            f"⚠️ I ran into a problem: `{exc}`\n\n"
            "Please check that your `GEMINI_API_KEY` is valid and has quota remaining."
        )

    return {
        "agent": agent["name"],
        "emoji": agent["emoji"],
        "color": agent["color"],
        "message": reply,
    }


# ─── HEALTH CHECK ────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini": bool(GEMINI_API_KEY),
    }


# ─── STATIC FILES (local dev only) ───────────────────────────
# On Vercel, index.html at project root is served by CDN automatically.
# Locally, uvicorn serves from root (new layout) or public/ (legacy).
_root = Path(__file__).parent.parent
_serve_dir = None
if (_root / "index.html").exists():
    _serve_dir = _root
elif (_root / "public" / "index.html").exists():
    _serve_dir = _root / "public"
# On Vercel, index.html is served by the CDN (declared in vercel.json builds).
# Only mount StaticFiles locally so the Lambda stays lean and the catch-all
# StaticFiles handler does not shadow any API routes inside the function.
if _serve_dir and not os.environ.get("VERCEL"):
    app.mount("/", StaticFiles(directory=str(_serve_dir), html=True), name="static")


# ─── VERCEL HANDLER ──────────────────────────────────────────
# Mangum wraps the ASGI app for Vercel's serverless Python runtime.
# MUST be named `handler` at module level — Vercel looks for this name.
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None  # running locally with uvicorn — mangum not needed
