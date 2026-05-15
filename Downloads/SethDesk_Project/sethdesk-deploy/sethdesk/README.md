# SethDesk — Personal Work Management Dashboard

> Built for **Seth Dwumah**, Simulation Engineer at the University of Energy and Natural Resources (UENR), Ghana.  
> Inspired by Notion, Jira, ClickUp, and Monday.com.

---

## ✨ Features

| Module | Description |
|---|---|
| **Dashboard** | Live stats, completion trend chart, status donut, active projects & activity feed |
| **Projects** | Cards with progress bars, priority badges, edit/delete; filter by status |
| **Tasks** | Full table with search, filters, one-click complete, delete |
| **Kanban** | 5-column visual board (Todo → In Progress → Review → Done → Blocked) |
| **Calendar** | Monthly view with task due-date dots |
| **Analytics** | Bar, pie, and line charts from live data |
| **Reports** | Project completion summary with progress bars |
| **AI Assistant** | Multi-agent Gemini 2.5 Flash chat — auto-routes to the right specialist |

### 🤖 AI Agents

| Agent | Expertise |
|---|---|
| 📊 **Coach Ada** | Project planning, scheduling, task prioritization |
| 🔬 **Dr. Mensah** | Research methodology, petroleum engineering, literature |
| ⚙️ **Eng. Kwame** | Aspen HYSYS / Aspen Plus simulation |
| ✍️ **Prof. Olu** | Academic writing, SPE papers, thesis chapters |

The AI automatically routes your question to the right agent based on keywords.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10 or 3.11
- A free Google Gemini API key → https://aistudio.google.com/app/apikey

### 1. Clone / extract and enter the folder
```bash
cd sethdesk
```

### 2. Create a virtual environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your Gemini API key
```bash
# Copy the template
cp .env.example .env

# Open .env and replace YOUR_GEMINI_API_KEY_HERE with your real key
```

### 5. Run the server
```bash
uvicorn api.index:app --reload --port 8000
```

### 6. Open in your browser
```
http://localhost:8000
```

The SQLite database is created automatically at `/tmp/sethdesk.db` and seeded with your starter projects and tasks on first run.

---

## ☁️ Deploy to Vercel (Free)

### Step 1 — Install Vercel CLI
```bash
npm install -g vercel
```

### Step 2 — Login
```bash
vercel login
```

### Step 3 — Deploy
```bash
vercel --prod
```

### Step 4 — Add environment variable in Vercel dashboard
1. Go to your project on https://vercel.com
2. **Settings → Environment Variables**
3. Add:  
   - **Key:** `GEMINI_API_KEY`  
   - **Value:** your key from https://aistudio.google.com/app/apikey
4. Redeploy (Deployments → ⋯ → Redeploy)

> **Important:** Vercel Serverless uses an ephemeral filesystem — the SQLite database resets on each cold start.  
> For **persistent data**, replace SQLite with a hosted PostgreSQL from [Supabase](https://supabase.com) (free tier) or [Neon](https://neon.tech) (free tier) and update `api/index.py`.

---

## 📁 Project Structure

```
sethdesk/
├── api/
│   └── index.py          # FastAPI backend — all routes + AI agents
├── public/
│   └── index.html        # Frontend — dashboard, all views, chat panel
├── .env.example          # Environment variable template
├── .gitignore
├── requirements.txt      # Python dependencies
├── vercel.json           # Vercel routing config
└── README.md
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Server + Gemini status check |
| GET | `/api/projects` | List all projects |
| POST | `/api/projects` | Create a project |
| PUT | `/api/projects/{id}` | Update a project |
| DELETE | `/api/projects/{id}` | Delete project + its tasks |
| GET | `/api/tasks` | List all tasks |
| POST | `/api/tasks` | Create a task |
| PUT | `/api/tasks/{id}` | Update a task (e.g. toggle complete) |
| DELETE | `/api/tasks/{id}` | Delete a task |
| POST | `/api/chat` | Send message to AI multi-agent system |

---

## 🔮 Upgrading to Persistent Storage (Optional)

Replace the SQLite section in `api/index.py` with a PostgreSQL adapter:

```bash
pip install psycopg2-binary
```

Then set `DATABASE_URL=postgresql://...` in your Vercel environment variables and update `get_db()` accordingly.

---

## 🙏 Credits

- **Design inspiration:** Notion, Jira, ClickUp, Monday.com  
- **Built by:** Kobby (Rise-Edu Network)  
- **For:** Seth Dwumah — UENR MPhil Candidate
