import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import hashlib

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SimLab Manager",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Data persistence helpers ─────────────────────────────────────────────────
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load(filename):
    path = f"{DATA_DIR}/{filename}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def save(filename, data):
    with open(f"{DATA_DIR}/{filename}.json", "w") as f:
        json.dump(data, f, indent=2, default=str)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Seed default users ────────────────────────────────────────────────────────
def seed_defaults():
    users = load("users")
    if not users:
        users = [
            {"id": "ADMIN001", "name": "Lab Admin", "email": "admin@lab.edu",
             "password": hash_pw("admin123"), "role": "admin"},
            {"id": "LEC001", "name": "Dr. Mensah", "email": "mensah@lab.edu",
             "password": hash_pw("lec123"), "role": "lecturer"},
            {"id": "STU001", "name": "Kofi Asante", "email": "kofi@lab.edu",
             "password": hash_pw("stu123"), "role": "student"},
        ]
        save("users", users)
    # seed workstations
    ws = load("workstations")
    if not ws:
        ws = [{"id": i, "label": f"PC-{i:02d}", "status": "available"} for i in range(1, 21)]
        save("workstations", ws)

seed_defaults()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; }
    .main-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.95rem; }
    .metric-card {
        background: white;
        border: 1px solid #e0e6ed;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: #1e3a5f; }
    .metric-card .label { font-size: 0.85rem; color: #666; margin-top: 0.2rem; }
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-green  { background: #d4edda; color: #155724; }
    .badge-yellow { background: #fff3cd; color: #856404; }
    .badge-red    { background: #f8d7da; color: #721c24; }
    .badge-blue   { background: #cce5ff; color: #004085; }
    section[data-testid="stSidebar"] { background: #1e3a5f !important; }
    section[data-testid="stSidebar"] * { color: white !important; }
    section[data-testid="stSidebar"] .stSelectbox label { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, val in [("logged_in", False), ("user", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════
def login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div class="main-header" style="text-align:center">
            <h1>🖥️ SimLab Manager</h1>
            <p>Simulation Laboratory Management System</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            student_id = st.text_input("Student / Staff ID", placeholder="e.g. STU001")
            password   = st.text_input("Password", type="password")
            submitted  = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            users = load("users")
            match = next((u for u in users
                          if u["id"] == student_id and u["password"] == hash_pw(password)), None)
            if match:
                st.session_state.logged_in = True
                st.session_state.user = match
                st.rerun()
            else:
                st.error("Invalid ID or password.")

        st.markdown("---")
        st.caption("**Demo credentials**")
        st.caption("Admin → ADMIN001 / admin123")
        st.caption("Lecturer → LEC001 / lec123")
        st.caption("Student → STU001 / stu123")

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR NAV
# ══════════════════════════════════════════════════════════════════════════════
def sidebar_nav():
    user = st.session_state.user
    role = user["role"]

    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.markdown(f"**Role:** {role.title()}  |  **ID:** {user['id']}")
        st.markdown("---")

        if role == "admin":
            pages = ["📊 Dashboard", "🎓 Students", "📅 Lab Sessions",
                     "🗓️ Bookings", "🖥️ Workstations", "📋 Attendance", "📈 Reports"]
        elif role == "lecturer":
            pages = ["📊 Dashboard", "📅 Lab Sessions", "📋 Attendance"]
        else:  # student
            pages = ["📊 My Dashboard", "🗓️ Book a Slot", "📋 My History"]

        choice = st.radio("Navigation", pages, label_visibility="collapsed")
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    return choice

# ══════════════════════════════════════════════════════════════════════════════
# PAGES — ADMIN
# ══════════════════════════════════════════════════════════════════════════════
def page_admin_dashboard():
    st.markdown('<div class="main-header"><h1>📊 Dashboard</h1><p>Overview of lab activity</p></div>', unsafe_allow_html=True)

    sessions    = load("sessions")
    bookings    = load("bookings")
    attendance  = load("attendance")
    users       = load("users")
    students    = [u for u in users if u["role"] == "student"]

    today = str(date.today())
    today_sessions  = [s for s in sessions  if s.get("date") == today]
    pending_bookings = [b for b in bookings if b.get("status") == "pending"]
    today_attendance = [a for a in attendance if a.get("date") == today]

    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, len(students),          "Registered Students"),
        (c2, len(today_sessions),    "Today's Sessions"),
        (c3, len(pending_bookings),  "Pending Bookings"),
        (c4, len(today_attendance),  "Check-ins Today"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="value">{val}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("📅 Today's Sessions")
        if today_sessions:
            for s in today_sessions:
                st.info(f"**{s['course']}** | {s['start_time']} – {s['end_time']} | Lecturer: {s['lecturer']}")
        else:
            st.write("No sessions scheduled for today.")

    with col_r:
        st.subheader("🔔 Pending Booking Requests")
        if pending_bookings:
            for b in pending_bookings:
                cols = st.columns([3, 1, 1])
                cols[0].write(f"**{b['student_name']}** ({b['student_id']}) — {b['date']} {b['time_slot']}")
                if cols[1].button("✅", key=f"approve_{b['id']}"):
                    bookings = load("bookings")
                    for bk in bookings:
                        if bk["id"] == b["id"]:
                            bk["status"] = "approved"
                    save("bookings", bookings)
                    st.rerun()
                if cols[2].button("❌", key=f"reject_{b['id']}"):
                    bookings = load("bookings")
                    for bk in bookings:
                        if bk["id"] == b["id"]:
                            bk["status"] = "rejected"
                    save("bookings", bookings)
                    st.rerun()
        else:
            st.write("No pending booking requests.")


def page_students():
    st.markdown('<div class="main-header"><h1>🎓 Student Management</h1><p>Register and manage students</p></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Students", "➕ Register Student"])

    with tab1:
        users = load("users")
        students = [u for u in users if u["role"] == "student"]
        if students:
            df = pd.DataFrame([{
                "ID": s["id"], "Name": s["name"], "Email": s["email"]
            } for s in students])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No students registered yet.")

    with tab2:
        with st.form("register_student"):
            c1, c2 = st.columns(2)
            sid   = c1.text_input("Student ID *")
            name  = c2.text_input("Full Name *")
            email = c1.text_input("Email")
            pw    = c2.text_input("Password *", type="password")
            if st.form_submit_button("Register Student", use_container_width=True):
                if sid and name and pw:
                    users = load("users")
                    if any(u["id"] == sid for u in users):
                        st.error("Student ID already exists.")
                    else:
                        users.append({"id": sid, "name": name, "email": email,
                                      "password": hash_pw(pw), "role": "student"})
                        save("users", users)
                        st.success(f"Student {name} registered successfully!")
                        st.rerun()
                else:
                    st.error("Please fill all required fields.")


def page_lab_sessions(role="admin"):
    st.markdown('<div class="main-header"><h1>📅 Lab Sessions</h1><p>Manage scheduled laboratory sessions</p></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Sessions", "➕ Create Session"])

    with tab1:
        sessions = load("sessions")
        if sessions:
            df = pd.DataFrame([{
                "ID": s["id"], "Course": s["course"], "Date": s["date"],
                "Start": s["start_time"], "End": s["end_time"],
                "Lecturer": s["lecturer"], "Max Students": s["max_students"]
            } for s in sessions])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No sessions created yet.")

    with tab2:
        users    = load("users")
        lecturers = [u for u in users if u["role"] in ("lecturer", "admin")]
        with st.form("create_session"):
            c1, c2 = st.columns(2)
            course   = c1.text_input("Course Name / Code *")
            lec_name = c2.selectbox("Lecturer", [l["name"] for l in lecturers])
            s_date   = c1.date_input("Date", min_value=date.today())
            s_start  = c2.text_input("Start Time (e.g. 08:00)")
            s_end    = c1.text_input("End Time   (e.g. 10:00)")
            max_stu  = c2.number_input("Max Students", 1, 20, 15)
            notes    = st.text_area("Notes (optional)")

            if st.form_submit_button("Create Session", use_container_width=True):
                if course and s_start and s_end:
                    sessions = load("sessions")
                    new_id = f"SES{len(sessions)+1:04d}"
                    sessions.append({
                        "id": new_id, "course": course, "lecturer": lec_name,
                        "date": str(s_date), "start_time": s_start, "end_time": s_end,
                        "max_students": int(max_stu), "notes": notes,
                        "created_by": st.session_state.user["id"]
                    })
                    save("sessions", sessions)
                    st.success(f"Session {new_id} created!")
                    st.rerun()
                else:
                    st.error("Please fill all required fields.")


def page_bookings():
    st.markdown('<div class="main-header"><h1>🗓️ Open-Access Bookings</h1><p>Manage individual computer booking requests</p></div>', unsafe_allow_html=True)

    bookings = load("bookings")
    tab1, tab2 = st.tabs(["🔔 All Requests", "📊 Booking Calendar"])

    with tab1:
        filter_status = st.selectbox("Filter by status", ["all", "pending", "approved", "rejected"])
        filtered = bookings if filter_status == "all" else [b for b in bookings if b["status"] == filter_status]

        if filtered:
            for b in sorted(filtered, key=lambda x: x["date"], reverse=True):
                badge_map = {"pending": "badge-yellow", "approved": "badge-green", "rejected": "badge-red"}
                badge = badge_map.get(b["status"], "badge-blue")
                cols = st.columns([4, 2, 1, 1])
                cols[0].markdown(f"**{b['student_name']}** (`{b['student_id']}`) — {b['date']} @ {b['time_slot']}")
                cols[1].markdown(f'<span class="status-badge {badge}">{b["status"].upper()}</span>', unsafe_allow_html=True)
                if b["status"] == "pending":
                    if cols[2].button("✅ Approve", key=f"app_{b['id']}"):
                        for bk in bookings:
                            if bk["id"] == b["id"]: bk["status"] = "approved"
                        save("bookings", bookings); st.rerun()
                    if cols[3].button("❌ Reject", key=f"rej_{b['id']}"):
                        for bk in bookings:
                            if bk["id"] == b["id"]: bk["status"] = "rejected"
                        save("bookings", bookings); st.rerun()
        else:
            st.info("No bookings found.")

    with tab2:
        approved = [b for b in bookings if b["status"] == "approved"]
        if approved:
            df = pd.DataFrame(approved)[["student_name", "date", "time_slot"]]
            df.columns = ["Student", "Date", "Time Slot"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No approved bookings yet.")


def page_workstations():
    st.markdown('<div class="main-header"><h1>🖥️ Workstation Management</h1><p>Track and manage lab computers</p></div>', unsafe_allow_html=True)

    workstations = load("workstations")

    st.subheader("Workstation Status Overview")
    cols = st.columns(5)
    for i, ws in enumerate(workstations):
        color = {"available": "🟢", "maintenance": "🔴", "in-use": "🟡"}.get(ws["status"], "⚪")
        with cols[i % 5]:
            st.markdown(f"**{ws['label']}**")
            st.markdown(f"{color} {ws['status'].title()}")
            new_status = st.selectbox("", ["available", "in-use", "maintenance"],
                                      index=["available", "in-use", "maintenance"].index(ws["status"]),
                                      key=f"ws_{ws['id']}", label_visibility="collapsed")
            if new_status != ws["status"]:
                for w in workstations:
                    if w["id"] == ws["id"]: w["status"] = new_status
                save("workstations", workstations)
                st.rerun()

    st.markdown("---")
    avail = sum(1 for w in workstations if w["status"] == "available")
    in_use = sum(1 for w in workstations if w["status"] == "in-use")
    maint = sum(1 for w in workstations if w["status"] == "maintenance")
    c1, c2, c3 = st.columns(3)
    c1.success(f"✅ Available: {avail}")
    c2.warning(f"🟡 In Use: {in_use}")
    c3.error(f"🔴 Maintenance: {maint}")


def page_attendance():
    st.markdown('<div class="main-header"><h1>📋 Attendance & Check-In</h1><p>Record student attendance for sessions and bookings</p></div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["✅ Check-In Student", "📋 View Records", "📤 Export"])

    with tab1:
        sessions  = load("sessions")
        bookings  = load("bookings")
        users     = load("users")
        ws_list   = load("workstations")
        avail_ws  = [w["label"] for w in ws_list if w["status"] == "available"]

        check_type = st.radio("Check-in type", ["Scheduled Session", "Open-Access Booking"], horizontal=True)

        with st.form("checkin_form"):
            student_id = st.text_input("Student ID *")
            if check_type == "Scheduled Session":
                session_opts = [f"{s['id']} | {s['course']} | {s['date']}" for s in sessions]
                selected_session = st.selectbox("Select Session", session_opts) if session_opts else st.text_input("No sessions available")
            else:
                booking_opts = [f"{b['id']} | {b['student_id']} | {b['date']} {b['time_slot']}"
                                for b in bookings if b["status"] == "approved"]
                selected_booking = st.selectbox("Select Booking", booking_opts) if booking_opts else st.text_input("No approved bookings")

            workstation = st.selectbox("Assign Workstation", avail_ws) if avail_ws else st.text_input("No workstations available")
            submitted   = st.form_submit_button("✅ Check In", use_container_width=True)

            if submitted and student_id:
                student = next((u for u in users if u["id"] == student_id), None)
                if not student:
                    st.error("Student ID not found.")
                else:
                    attendance = load("attendance")
                    ref_id = selected_session.split(" | ")[0] if check_type == "Scheduled Session" else selected_booking.split(" | ")[0]
                    record = {
                        "id": f"ATT{len(attendance)+1:05d}",
                        "student_id": student_id,
                        "student_name": student["name"],
                        "type": check_type,
                        "reference_id": ref_id,
                        "workstation": workstation,
                        "date": str(date.today()),
                        "time": datetime.now().strftime("%H:%M"),
                        "status": "present"
                    }
                    attendance.append(record)
                    save("attendance", attendance)
                    # mark workstation in-use
                    wss = load("workstations")
                    for w in wss:
                        if w["label"] == workstation: w["status"] = "in-use"
                    save("workstations", wss)
                    st.success(f"✅ {student['name']} checked in at {workstation}")

    with tab2:
        attendance = load("attendance")
        if attendance:
            df = pd.DataFrame(attendance)[["id", "student_id", "student_name", "type", "workstation", "date", "time", "status"]]
            df.columns = ["Record ID", "Stu. ID", "Name", "Type", "Workstation", "Date", "Time", "Status"]

            col1, col2 = st.columns(2)
            date_filter = col1.date_input("Filter by date", value=None)
            type_filter = col2.selectbox("Filter by type", ["All", "Scheduled Session", "Open-Access Booking"])

            if date_filter:
                df = df[df["Date"] == str(date_filter)]
            if type_filter != "All":
                df = df[df["Type"] == type_filter]

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No attendance records yet.")

    with tab3:
        attendance = load("attendance")
        if attendance:
            df = pd.DataFrame(attendance)
            csv = df.to_csv(index=False)
            st.download_button("📥 Download Attendance CSV", csv, "attendance.csv", "text/csv", use_container_width=True)
        else:
            st.info("No data to export yet.")


def page_reports():
    st.markdown('<div class="main-header"><h1>📈 Reports & Analytics</h1><p>Insights into lab usage and student activity</p></div>', unsafe_allow_html=True)

    attendance = load("attendance")
    if not attendance:
        st.info("No attendance data available yet.")
        return

    df = pd.DataFrame(attendance)
    df["date"] = pd.to_datetime(df["date"])

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Daily Check-ins (Last 14 Days)")
        daily = df.groupby("date").size().reset_index(name="count")
        daily = daily.sort_values("date").tail(14)
        fig = px.bar(daily, x="date", y="count", color_discrete_sequence=["#2d6a9f"])
        fig.update_layout(margin=dict(t=10), height=300)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Session vs Open-Access Split")
        type_counts = df["type"].value_counts().reset_index()
        type_counts.columns = ["Type", "Count"]
        fig2 = px.pie(type_counts, values="Count", names="Type",
                      color_discrete_sequence=["#1e3a5f", "#2d9fd6"])
        fig2.update_layout(margin=dict(t=10), height=300)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Workstation Usage Frequency")
    ws_counts = df["workstation"].value_counts().reset_index()
    ws_counts.columns = ["Workstation", "Uses"]
    fig3 = px.bar(ws_counts.head(15), x="Workstation", y="Uses", color_discrete_sequence=["#1e3a5f"])
    fig3.update_layout(margin=dict(t=10), height=300)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Most Active Students")
    top_students = df.groupby(["student_id", "student_name"]).size().reset_index(name="Visits")
    top_students = top_students.sort_values("Visits", ascending=False).head(10)
    st.dataframe(top_students, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGES — STUDENT
# ══════════════════════════════════════════════════════════════════════════════
def page_student_dashboard():
    user = st.session_state.user
    st.markdown(f'<div class="main-header"><h1>👋 Welcome, {user["name"]}</h1><p>Your lab activity overview</p></div>', unsafe_allow_html=True)

    attendance = load("attendance")
    my_records = [a for a in attendance if a["student_id"] == user["id"]]
    bookings   = load("bookings")
    my_bookings = [b for b in bookings if b["student_id"] == user["id"]]

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-card"><div class="value">{len(my_records)}</div><div class="label">Total Visits</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="value">{len(my_bookings)}</div><div class="label">My Bookings</div></div>', unsafe_allow_html=True)
    pending = len([b for b in my_bookings if b["status"] == "pending"])
    c3.markdown(f'<div class="metric-card"><div class="value">{pending}</div><div class="label">Pending Requests</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Recent Activity")
    if my_records:
        df = pd.DataFrame(my_records)[["date", "time", "type", "workstation", "status"]]
        df.columns = ["Date", "Time", "Type", "Workstation", "Status"]
        st.dataframe(df.sort_values("Date", ascending=False).head(10), use_container_width=True, hide_index=True)
    else:
        st.info("No visits recorded yet.")


def page_book_slot():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>🗓️ Book a Lab Slot</h1><p>Request open-access computer time</p></div>', unsafe_allow_html=True)

    time_slots = ["08:00 – 09:00", "09:00 – 10:00", "10:00 – 11:00",
                  "11:00 – 12:00", "13:00 – 14:00", "14:00 – 15:00",
                  "15:00 – 16:00", "16:00 – 17:00"]

    max_date = date.today() + timedelta(days=2)

    with st.form("booking_form"):
        booking_date = st.date_input("Select Date", min_value=date.today(), max_value=max_date)
        time_slot    = st.selectbox("Select Time Slot", time_slots)
        purpose      = st.text_area("Purpose / Reason for Visit")
        submitted    = st.form_submit_button("📩 Submit Booking Request", use_container_width=True)

        if submitted:
            bookings = load("bookings")
            # check for duplicate
            conflict = any(
                b["student_id"] == user["id"] and b["date"] == str(booking_date)
                and b["time_slot"] == time_slot and b["status"] != "rejected"
                for b in bookings
            )
            if conflict:
                st.error("You already have a booking for that slot.")
            else:
                bookings.append({
                    "id": f"BK{len(bookings)+1:04d}",
                    "student_id": user["id"],
                    "student_name": user["name"],
                    "date": str(booking_date),
                    "time_slot": time_slot,
                    "purpose": purpose,
                    "status": "pending",
                    "created_at": str(datetime.now())
                })
                save("bookings", bookings)
                st.success("✅ Booking request submitted! You'll be notified once approved.")

    st.markdown("---")
    st.subheader("My Booking History")
    bookings = load("bookings")
    my_bookings = [b for b in bookings if b["student_id"] == user["id"]]
    if my_bookings:
        df = pd.DataFrame(my_bookings)[["id", "date", "time_slot", "status"]]
        df.columns = ["Booking ID", "Date", "Time Slot", "Status"]
        st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No bookings yet.")


def page_my_history():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>📋 My Visit History</h1></div>', unsafe_allow_html=True)

    attendance = load("attendance")
    my_records = [a for a in attendance if a["student_id"] == user["id"]]
    if my_records:
        df = pd.DataFrame(my_records)[["date", "time", "type", "reference_id", "workstation", "status"]]
        df.columns = ["Date", "Time", "Type", "Reference", "Workstation", "Status"]
        st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No visit records yet.")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    login_page()
else:
    page = sidebar_nav()
    role = st.session_state.user["role"]

    if role == "admin":
        route = {
            "📊 Dashboard":       page_admin_dashboard,
            "🎓 Students":        page_students,
            "📅 Lab Sessions":    page_lab_sessions,
            "🗓️ Bookings":        page_bookings,
            "🖥️ Workstations":    page_workstations,
            "📋 Attendance":      page_attendance,
            "📈 Reports":         page_reports,
        }
    elif role == "lecturer":
        route = {
            "📊 Dashboard":       page_admin_dashboard,
            "📅 Lab Sessions":    page_lab_sessions,
            "📋 Attendance":      page_attendance,
        }
    else:
        route = {
            "📊 My Dashboard":   page_student_dashboard,
            "🗓️ Book a Slot":    page_book_slot,
            "📋 My History":     page_my_history,
        }

    fn = route.get(page)
    if fn:
        fn()
