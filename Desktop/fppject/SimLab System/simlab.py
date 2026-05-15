import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date, timedelta
import plotly.express as px
import hashlib
import re

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SimLab Manager",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_DIR    = "data"
ADMIN_CODE  = "SIMLAB2024"   # invite code required for admin registration
TIME_SLOTS  = ["08:00–09:00","09:00–10:00","10:00–11:00","11:00–12:00",
               "13:00–14:00","14:00–15:00","15:00–16:00","16:00–17:00"]
MAX_BOOKING_DAYS_AHEAD = 2
os.makedirs(DATA_DIR, exist_ok=True)

# ── Persistence ───────────────────────────────────────────────────────────────
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

def add_notification(user_id, message, notif_type="info"):
    notifs = load("notifications")
    notifs.append({
        "id": f"N{len(notifs)+1:05d}",
        "user_id": user_id,
        "message": message,
        "type": notif_type,
        "read": False,
        "created_at": str(datetime.now())
    })
    save("notifications", notifs)

def add_audit(actor_id, action, detail=""):
    audit = load("audit")
    audit.append({
        "id": f"A{len(audit)+1:05d}",
        "actor": actor_id,
        "action": action,
        "detail": detail,
        "timestamp": str(datetime.now())
    })
    save("audit", audit)

# ── Seed defaults ─────────────────────────────────────────────────────────────
def seed_defaults():
    users = load("users")
    if not users:
        users = [
            {"id":"ADMIN001","name":"Lab Admin","email":"admin@lab.edu",
             "password":hash_pw("admin123"),"role":"admin",
             "security_q":"What is your pet's name?","security_a":hash_pw("buddy")},
            {"id":"LEC001","name":"Dr. Mensah","email":"mensah@lab.edu",
             "password":hash_pw("lec123"),"role":"lecturer",
             "security_q":"What city were you born in?","security_a":hash_pw("accra")},
            {"id":"STU001","name":"Kofi Asante","email":"kofi@lab.edu",
             "password":hash_pw("stu123"),"role":"student",
             "security_q":"What is your mother's maiden name?","security_a":hash_pw("boateng")},
        ]
        save("users", users)
    ws = load("workstations")
    if not ws:
        ws = [{"id":i,"label":f"PC-{i:02d}","status":"available","notes":""}
              for i in range(1, 21)]
        save("workstations", ws)

seed_defaults()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main-header {
    background: linear-gradient(135deg,#1e3a5f 0%,#2d6a9f 100%);
    padding:1.5rem 2rem; border-radius:12px; color:white; margin-bottom:1.5rem;
  }
  .main-header h1{margin:0;font-size:1.8rem;}
  .main-header p{margin:.3rem 0 0;opacity:.85;font-size:.95rem;}
  .metric-card{background:white;border:1px solid #e0e6ed;border-radius:10px;
    padding:1.2rem 1.5rem;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06);}
  .metric-card .value{font-size:2rem;font-weight:700;color:#1e3a5f;}
  .metric-card .label{font-size:.85rem;color:#666;margin-top:.2rem;}
  .notif-banner{padding:.6rem 1rem;border-radius:8px;margin-bottom:.5rem;font-size:.9rem;}
  .notif-info{background:#cce5ff;color:#004085;}
  .notif-success{background:#d4edda;color:#155724;}
  .notif-warning{background:#fff3cd;color:#856404;}
  .notif-error{background:#f8d7da;color:#721c24;}
  .slot-available{background:#d4edda;color:#155724;padding:.3rem .8rem;
    border-radius:6px;font-size:.82rem;font-weight:600;}
  .slot-full{background:#f8d7da;color:#721c24;padding:.3rem .8rem;
    border-radius:6px;font-size:.82rem;font-weight:600;}
  section[data-testid="stSidebar"]{background:#1e3a5f !important;}
  section[data-testid="stSidebar"] *{color:white !important;}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("logged_in",False),("user",None),("auth_page","login")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_unread_count(user_id):
    return sum(1 for n in load("notifications")
               if n["user_id"] == user_id and not n["read"])

def slot_booking_count(slot_date, time_slot):
    return sum(1 for b in load("bookings")
               if b["date"] == str(slot_date)
               and b["time_slot"] == time_slot
               and b["status"] == "approved")

def sessions_overlap(date, start, end, exclude_id=None):
    """Check if a new session overlaps existing ones on the same date."""
    for s in load("sessions"):
        if s["date"] != str(date): continue
        if exclude_id and s["id"] == exclude_id: continue
        try:
            es = datetime.strptime(s["start_time"],"%H:%M")
            ee = datetime.strptime(s["end_time"],  "%H:%M")
            ns = datetime.strptime(start,           "%H:%M")
            ne = datetime.strptime(end,             "%H:%M")
            if ns < ee and ne > es:
                return s
        except Exception:
            pass
    return None

def generate_recurring_sessions(course, lecturer, start_date, start_time, end_time,
                                  max_students, weeks, notes, created_by):
    sessions = load("sessions")
    added = 0
    for w in range(weeks):
        d = start_date + timedelta(weeks=w)
        conflict = sessions_overlap(d, start_time, end_time)
        if conflict:
            st.warning(f"Week {w+1} ({d}) skipped — overlaps with '{conflict['course']}'")
            continue
        sid = f"SES{len(sessions)+1:04d}"
        sessions.append({
            "id": sid, "course": course, "lecturer": lecturer,
            "date": str(d), "start_time": start_time, "end_time": end_time,
            "max_students": int(max_students), "notes": notes,
            "created_by": created_by, "recurring": True
        })
        added += 1
    save("sessions", sessions)
    return added

def auto_reject_expired_bookings():
    bookings = load("bookings")
    now = datetime.now()
    changed = False
    for b in bookings:
        if b["status"] != "pending": continue
        try:
            slot_start = b["time_slot"].split("–")[0].strip()
            slot_dt = datetime.strptime(f"{b['date']} {slot_start}", "%Y-%m-%d %H:%M")
            if now > slot_dt - timedelta(hours=1):
                b["status"] = "rejected"
                b["rejection_reason"] = "Auto-rejected: not approved before cutoff"
                add_notification(b["student_id"],
                    f"Your booking for {b['date']} {b['time_slot']} was auto-rejected (not approved in time).",
                    "error")
                changed = True
        except Exception:
            pass
    if changed:
        save("bookings", bookings)

# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGES
# ══════════════════════════════════════════════════════════════════════════════
def auth_pages():
    auto_reject_expired_bookings()
    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        st.markdown("""
        <div class="main-header" style="text-align:center">
          <h1>🖥️ SimLab Manager</h1>
          <p>Simulation Laboratory Management System</p>
        </div>""", unsafe_allow_html=True)

        tab_login, tab_register, tab_reset = st.tabs(
            ["🔑 Login", "📝 Register", "🔒 Reset Password"])

        # ── LOGIN ──────────────────────────────────────────────────────────
        with tab_login:
            with st.form("login_form"):
                uid = st.text_input("Student / Staff ID", placeholder="e.g. STU001")
                pw  = st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    users = load("users")
                    match = next((u for u in users
                                  if u["id"]==uid and u["password"]==hash_pw(pw)), None)
                    if match:
                        st.session_state.logged_in = True
                        st.session_state.user = match
                        add_audit(uid, "LOGIN")
                        st.rerun()
                    else:
                        st.error("Invalid ID or password.")
            st.caption("**Demo credentials** — Admin: ADMIN001/admin123 | Lecturer: LEC001/lec123 | Student: STU001/stu123")

        # ── REGISTER ───────────────────────────────────────────────────────
        with tab_register:
            role_choice = st.selectbox("Registering as", ["student","lecturer","admin"])
            with st.form("register_form"):
                c1, c2 = st.columns(2)
                new_id    = c1.text_input("ID *", placeholder="e.g. STU002")
                new_name  = c2.text_input("Full Name *")
                new_email = c1.text_input("Email *")
                new_pw    = c2.text_input("Password *", type="password")
                new_pw2   = c1.text_input("Confirm Password *", type="password")
                sec_q     = c2.selectbox("Security Question",
                    ["What is your pet's name?",
                     "What city were you born in?",
                     "What is your mother's maiden name?",
                     "What was your first school's name?"])
                sec_a     = st.text_input("Security Answer *")
                if role_choice == "admin":
                    invite = st.text_input("Admin Invite Code *", type="password")
                else:
                    invite = None

                if st.form_submit_button("Create Account", use_container_width=True):
                    errors = []
                    if not all([new_id, new_name, new_email, new_pw, sec_a]):
                        errors.append("All fields are required.")
                    if new_pw != new_pw2:
                        errors.append("Passwords do not match.")
                    if len(new_pw) < 6:
                        errors.append("Password must be at least 6 characters.")
                    if role_choice == "admin" and invite != ADMIN_CODE:
                        errors.append("Invalid admin invite code.")
                    users = load("users")
                    if any(u["id"]==new_id for u in users):
                        errors.append("That ID is already registered.")
                    if errors:
                        for e in errors: st.error(e)
                    else:
                        users.append({
                            "id": new_id, "name": new_name, "email": new_email,
                            "password": hash_pw(new_pw), "role": role_choice,
                            "security_q": sec_q, "security_a": hash_pw(sec_a.lower().strip())
                        })
                        save("users", users)
                        add_audit(new_id, "REGISTER", f"role={role_choice}")
                        st.success(f"✅ Account created! You can now log in as **{new_id}**.")

        # ── RESET PASSWORD ─────────────────────────────────────────────────
        with tab_reset:
            reset_tab1, reset_tab2 = st.tabs(["Reset via Security Question", "Change Password (logged in)"])

            with reset_tab1:
                with st.form("reset_form"):
                    r_id  = st.text_input("Your ID *")
                    users = load("users")
                    user_match = next((u for u in users if u["id"]==r_id), None)
                    if user_match:
                        st.info(f"Security Question: **{user_match['security_q']}**")
                    r_ans    = st.text_input("Security Answer *")
                    r_new_pw = st.text_input("New Password *", type="password")
                    r_new_pw2= st.text_input("Confirm New Password *", type="password")
                    if st.form_submit_button("Reset Password", use_container_width=True):
                        users = load("users")
                        u = next((x for x in users if x["id"]==r_id), None)
                        if not u:
                            st.error("ID not found.")
                        elif u.get("security_a") != hash_pw(r_ans.lower().strip()):
                            st.error("Security answer is incorrect.")
                        elif r_new_pw != r_new_pw2:
                            st.error("Passwords do not match.")
                        elif len(r_new_pw) < 6:
                            st.error("Password must be at least 6 characters.")
                        else:
                            u["password"] = hash_pw(r_new_pw)
                            save("users", users)
                            add_audit(r_id, "PASSWORD_RESET")
                            st.success("✅ Password reset successfully! Please log in.")

            with reset_tab2:
                st.info("You must be logged in to change your password. Use this section after logging in via **⚙️ Profile & Settings** in the sidebar.")

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar_nav():
    user  = st.session_state.user
    role  = user["role"]
    unread = get_unread_count(user["id"])

    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.markdown(f"**{role.title()}**  ·  `{user['id']}`")
        if unread:
            st.markdown(f"🔔 **{unread} unread notification{'s' if unread>1 else ''}**")
        st.markdown("---")

        if role == "admin":
            pages = ["📊 Dashboard","🔔 Notifications","🎓 Students",
                     "📅 Lab Sessions","🗓️ Bookings","🖥️ Workstations",
                     "📋 Attendance","📈 Reports","⚙️ Profile & Settings"]
        elif role == "lecturer":
            pages = ["📊 Dashboard","🔔 Notifications","📅 Lab Sessions",
                     "📋 Attendance","⚙️ Profile & Settings"]
        else:
            pages = ["📊 My Dashboard","🔔 Notifications","🗓️ Book a Slot",
                     "📋 My History","⚙️ Profile & Settings"]

        choice = st.radio("Nav", pages, label_visibility="collapsed")
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            add_audit(user["id"], "LOGOUT")
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    return choice

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def page_notifications():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>🔔 Notifications</h1></div>', unsafe_allow_html=True)

    notifs = load("notifications")
    mine   = [n for n in notifs if n["user_id"] == user["id"]]

    if not mine:
        st.info("You have no notifications yet.")
        return

    col1, col2 = st.columns([6,1])
    col1.write(f"**{sum(1 for n in mine if not n['read'])} unread** of {len(mine)} total")
    if col2.button("Mark all read"):
        for n in notifs:
            if n["user_id"] == user["id"]: n["read"] = True
        save("notifications", notifs)
        st.rerun()

    for n in sorted(mine, key=lambda x: x["created_at"], reverse=True):
        css = {"info":"notif-info","success":"notif-success",
               "warning":"notif-warning","error":"notif-error"}.get(n["type"],"notif-info")
        dot = "" if n["read"] else "🔵 "
        st.markdown(
            f'<div class="notif-banner {css}">{dot}{n["message"]}<br>'
            f'<small style="opacity:.7">{n["created_at"][:16]}</small></div>',
            unsafe_allow_html=True
        )
        if not n["read"]:
            if st.button("Mark read", key=f"rd_{n['id']}"):
                for x in notifs:
                    if x["id"] == n["id"]: x["read"] = True
                save("notifications", notifs)
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE & SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
def page_profile():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>⚙️ Profile & Settings</h1></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 My Profile", "🔑 Change Password"])

    with tab1:
        with st.form("profile_form"):
            c1, c2 = st.columns(2)
            new_name  = c1.text_input("Full Name",  value=user["name"])
            new_email = c2.text_input("Email",       value=user.get("email",""))
            new_sec_q = c1.selectbox("Security Question",
                ["What is your pet's name?","What city were you born in?",
                 "What is your mother's maiden name?","What was your first school's name?"],
                index=["What is your pet's name?","What city were you born in?",
                       "What is your mother's maiden name?","What was your first school's name?"]
                      .index(user.get("security_q","What is your pet's name?"))
                      if user.get("security_q") in
                      ["What is your pet's name?","What city were you born in?",
                       "What is your mother's maiden name?","What was your first school's name?"]
                      else 0)
            new_sec_a = c2.text_input("New Security Answer (leave blank to keep current)")
            if st.form_submit_button("Update Profile", use_container_width=True):
                users = load("users")
                for u in users:
                    if u["id"] == user["id"]:
                        u["name"]  = new_name
                        u["email"] = new_email
                        u["security_q"] = new_sec_q
                        if new_sec_a.strip():
                            u["security_a"] = hash_pw(new_sec_a.lower().strip())
                        user.update(u)
                        st.session_state.user = u
                save("users", users)
                add_audit(user["id"], "PROFILE_UPDATE")
                st.success("✅ Profile updated!")

    with tab2:
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password *", type="password")
            new_pw  = st.text_input("New Password *", type="password")
            new_pw2 = st.text_input("Confirm New Password *", type="password")
            if st.form_submit_button("Change Password", use_container_width=True):
                users = load("users")
                u = next((x for x in users if x["id"]==user["id"]), None)
                if u["password"] != hash_pw(old_pw):
                    st.error("Current password is incorrect.")
                elif new_pw != new_pw2:
                    st.error("New passwords do not match.")
                elif len(new_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    u["password"] = hash_pw(new_pw)
                    save("users", users)
                    add_audit(user["id"], "PASSWORD_CHANGE")
                    st.success("✅ Password changed successfully!")

# ══════════════════════════════════════════════════════════════════════════════
# SEARCH BAR (shown on relevant pages)
# ══════════════════════════════════════════════════════════════════════════════
def render_search(placeholder="Search students by name or ID..."):
    return st.text_input("🔍 Search", placeholder=placeholder, label_visibility="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PAGES
# ══════════════════════════════════════════════════════════════════════════════
def page_admin_dashboard():
    auto_reject_expired_bookings()
    st.markdown('<div class="main-header"><h1>📊 Dashboard</h1><p>Overview of lab activity</p></div>', unsafe_allow_html=True)

    sessions   = load("sessions")
    bookings   = load("bookings")
    attendance = load("attendance")
    users      = load("users")
    students   = [u for u in users if u["role"]=="student"]
    today      = str(date.today())

    today_sessions   = [s for s in sessions  if s.get("date")==today]
    pending_bookings = [b for b in bookings  if b.get("status")=="pending"]
    today_att        = [a for a in attendance if a.get("date")==today]
    checked_out      = [a for a in today_att  if a.get("checked_out")]

    c1,c2,c3,c4,c5 = st.columns(5)
    for col,val,label in [
        (c1, len(students),         "Registered Students"),
        (c2, len(today_sessions),   "Today's Sessions"),
        (c3, len(pending_bookings), "Pending Bookings"),
        (c4, len(today_att),        "Check-ins Today"),
        (c5, len(today_att)-len(checked_out), "Currently In Lab"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="value">{val}</div>'
                     f'<div class="label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    cl, cr = st.columns(2)

    with cl:
        st.subheader("📅 Today's Sessions")
        if today_sessions:
            for s in today_sessions:
                checked = len([a for a in today_att if a.get("reference_id")==s["id"]])
                st.info(f"**{s['course']}** | {s['start_time']}–{s['end_time']} "
                        f"| {checked}/{s['max_students']} students checked in")
        else:
            st.write("No sessions today.")

    with cr:
        st.subheader("🔔 Pending Booking Requests")
        if pending_bookings:
            for b in pending_bookings[:5]:
                cols = st.columns([4,1,1])
                cols[0].write(f"**{b['student_name']}** — {b['date']} {b['time_slot']}")
                if cols[1].button("✅",key=f"da_{b['id']}"):
                    bookings_data = load("bookings")
                    for bk in bookings_data:
                        if bk["id"]==b["id"]: bk["status"]="approved"
                    save("bookings", bookings_data)
                    add_notification(b["student_id"],
                        f"Your booking for {b['date']} {b['time_slot']} has been approved! ✅","success")
                    st.rerun()
                if cols[2].button("❌",key=f"dr_{b['id']}"):
                    bookings_data = load("bookings")
                    for bk in bookings_data:
                        if bk["id"]==b["id"]: bk["status"]="rejected"
                    save("bookings", bookings_data)
                    add_notification(b["student_id"],
                        f"Your booking for {b['date']} {b['time_slot']} was not approved.","error")
                    st.rerun()
        else:
            st.write("No pending requests.")


def page_students():
    st.markdown('<div class="main-header"><h1>🎓 Student Management</h1></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Students", "➕ Register Student"])

    with tab1:
        search = render_search("Search by name or ID...")
        users  = load("users")
        studs  = [u for u in users if u["role"]=="student"]
        if search:
            studs = [s for s in studs if search.lower() in s["name"].lower()
                     or search.lower() in s["id"].lower()]
        if studs:
            df = pd.DataFrame([{"ID":s["id"],"Name":s["name"],"Email":s.get("email","")}
                                for s in studs])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(studs)} student(s) found.")
        else:
            st.info("No students found.")

    with tab2:
        with st.form("reg_stu"):
            c1,c2 = st.columns(2)
            sid   = c1.text_input("Student ID *")
            name  = c2.text_input("Full Name *")
            email = c1.text_input("Email")
            pw    = c2.text_input("Password *", type="password")
            if st.form_submit_button("Register", use_container_width=True):
                if sid and name and pw:
                    users = load("users")
                    if any(u["id"]==sid for u in users):
                        st.error("ID already exists.")
                    else:
                        users.append({"id":sid,"name":name,"email":email,
                                      "password":hash_pw(pw),"role":"student",
                                      "security_q":"What is your pet's name?",
                                      "security_a":hash_pw("changeme")})
                        save("users", users)
                        add_audit(st.session_state.user["id"],"REGISTER_STUDENT",sid)
                        st.success(f"Student {name} registered!")
                        st.rerun()
                else:
                    st.error("Fill all required fields.")


def page_lab_sessions(role="admin"):
    st.markdown('<div class="main-header"><h1>📅 Lab Sessions</h1></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Sessions", "➕ Create Session"])

    with tab1:
        search = render_search("Search by course or lecturer...")
        sessions = load("sessions")
        if search:
            sessions = [s for s in sessions if search.lower() in s["course"].lower()
                        or search.lower() in s["lecturer"].lower()]
        if sessions:
            attendance = load("attendance")
            rows = []
            for s in sorted(sessions, key=lambda x: x["date"], reverse=True):
                checked = len([a for a in attendance if a.get("reference_id")==s["id"]])
                rows.append({"ID":s["id"],"Course":s["course"],"Date":s["date"],
                             "Time":f"{s['start_time']}–{s['end_time']}",
                             "Lecturer":s["lecturer"],
                             "Checked In":f"{checked}/{s['max_students']}",
                             "Recurring":s.get("recurring",False)})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No sessions yet.")

    with tab2:
        users     = load("users")
        lecturers = [u for u in users if u["role"] in ("lecturer","admin")]
        sub_tab1, sub_tab2 = st.tabs(["Single Session", "Recurring (Weekly)"])

        with sub_tab1:
            with st.form("single_session"):
                c1,c2 = st.columns(2)
                course   = c1.text_input("Course Name / Code *")
                lec_name = c2.selectbox("Lecturer", [l["name"] for l in lecturers])
                s_date   = c1.date_input("Date", min_value=date.today())
                s_start  = c2.text_input("Start Time (HH:MM) *", placeholder="08:00")
                s_end    = c1.text_input("End Time   (HH:MM) *", placeholder="10:00")
                max_stu  = c2.number_input("Max Students", 1, 20, 15)
                notes    = st.text_area("Notes")
                if st.form_submit_button("Create Session", use_container_width=True):
                    if course and s_start and s_end:
                        conflict = sessions_overlap(s_date, s_start, s_end)
                        if conflict:
                            st.error(f"⚠️ Time conflict with existing session: **{conflict['course']}** "
                                     f"({conflict['start_time']}–{conflict['end_time']})")
                        else:
                            sessions = load("sessions")
                            sid = f"SES{len(sessions)+1:04d}"
                            sessions.append({
                                "id":sid,"course":course,"lecturer":lec_name,
                                "date":str(s_date),"start_time":s_start,"end_time":s_end,
                                "max_students":int(max_stu),"notes":notes,
                                "created_by":st.session_state.user["id"],"recurring":False
                            })
                            save("sessions", sessions)
                            add_audit(st.session_state.user["id"],"CREATE_SESSION",sid)
                            st.success(f"Session **{sid}** created!")
                            st.rerun()
                    else:
                        st.error("Fill all required fields.")

        with sub_tab2:
            with st.form("recurring_session"):
                c1,c2 = st.columns(2)
                r_course   = c1.text_input("Course Name / Code *")
                r_lec      = c2.selectbox("Lecturer", [l["name"] for l in lecturers], key="rlec")
                r_start_dt = c1.date_input("First Session Date", min_value=date.today(), key="rsd")
                r_start    = c2.text_input("Start Time (HH:MM) *", key="rst", placeholder="08:00")
                r_end      = c1.text_input("End Time   (HH:MM) *", key="ret", placeholder="10:00")
                r_weeks    = c2.number_input("Number of Weeks", 1, 24, 12)
                r_max      = c1.number_input("Max Students", 1, 20, 15, key="rmx")
                r_notes    = st.text_area("Notes", key="rnt")
                if st.form_submit_button("Create Recurring Sessions", use_container_width=True):
                    if r_course and r_start and r_end:
                        added = generate_recurring_sessions(
                            r_course, r_lec, r_start_dt, r_start, r_end,
                            r_max, r_weeks, r_notes, st.session_state.user["id"])
                        st.success(f"✅ {added} session(s) created across {r_weeks} weeks.")
                        st.rerun()
                    else:
                        st.error("Fill all required fields.")


def page_bookings():
    auto_reject_expired_bookings()
    st.markdown('<div class="main-header"><h1>🗓️ Open-Access Bookings</h1></div>', unsafe_allow_html=True)

    bookings = load("bookings")
    tab1, tab2 = st.tabs(["🔔 Requests", "📅 Slot Overview"])

    with tab1:
        search = render_search("Search by student name or ID...")
        col1,col2 = st.columns(2)
        filter_status = col1.selectbox("Status", ["all","pending","approved","rejected"])
        filter_date   = col2.date_input("Date filter", value=None)

        filtered = bookings
        if filter_status != "all":
            filtered = [b for b in filtered if b["status"]==filter_status]
        if filter_date:
            filtered = [b for b in filtered if b["date"]==str(filter_date)]
        if search:
            filtered = [b for b in filtered
                        if search.lower() in b["student_name"].lower()
                        or search.lower() in b["student_id"].lower()]

        if filtered:
            for b in sorted(filtered, key=lambda x: x["date"], reverse=True):
                badge = {"pending":"🟡","approved":"🟢","rejected":"🔴"}.get(b["status"],"⚪")
                cols = st.columns([4,2,1,1])
                cols[0].write(f"**{b['student_name']}** (`{b['student_id']}`) — "
                              f"{b['date']} @ {b['time_slot']}")
                cols[1].write(f"{badge} {b['status'].title()}")
                if b["status"]=="pending":
                    if cols[2].button("✅",key=f"ap_{b['id']}"):
                        for bk in bookings:
                            if bk["id"]==b["id"]: bk["status"]="approved"
                        save("bookings", bookings)
                        add_notification(b["student_id"],
                            f"Your booking for {b['date']} {b['time_slot']} is approved! ✅","success")
                        st.rerun()
                    if cols[3].button("❌",key=f"rj_{b['id']}"):
                        for bk in bookings:
                            if bk["id"]==b["id"]: bk["status"]="rejected"
                        save("bookings", bookings)
                        add_notification(b["student_id"],
                            f"Your booking for {b['date']} {b['time_slot']} was not approved.","error")
                        st.rerun()
        else:
            st.info("No bookings match your filters.")

    with tab2:
        st.subheader("Slot Availability (Next 3 Days)")
        MAX_PER_SLOT = 5
        for d_offset in range(3):
            check_date = date.today() + timedelta(days=d_offset)
            st.markdown(f"**📅 {check_date.strftime('%A, %d %B %Y')}**")
            cols = st.columns(len(TIME_SLOTS))
            for i, slot in enumerate(TIME_SLOTS):
                count = slot_booking_count(check_date, slot)
                avail = MAX_PER_SLOT - count
                label = f"{slot}\n{'✅' if avail > 0 else '🔴'} {avail}/{MAX_PER_SLOT}"
                cols[i].caption(label)
            st.markdown("---")


def page_workstations():
    st.markdown('<div class="main-header"><h1>🖥️ Workstation Management</h1></div>', unsafe_allow_html=True)

    workstations = load("workstations")
    tab1, tab2 = st.tabs(["📋 Status Board", "📜 Usage History"])

    with tab1:
        avail = sum(1 for w in workstations if w["status"]=="available")
        in_use = sum(1 for w in workstations if w["status"]=="in-use")
        maint  = sum(1 for w in workstations if w["status"]=="maintenance")
        c1,c2,c3 = st.columns(3)
        c1.success(f"✅ Available: {avail}")
        c2.warning(f"🟡 In Use: {in_use}")
        c3.error(f"🔴 Maintenance: {maint}")

        st.markdown("---")
        cols = st.columns(4)
        for i, ws in enumerate(workstations):
            with cols[i % 4]:
                icon = {"available":"🟢","in-use":"🟡","maintenance":"🔴"}.get(ws["status"],"⚪")
                st.markdown(f"**{icon} {ws['label']}**")
                new_status = st.selectbox("",["available","in-use","maintenance"],
                    index=["available","in-use","maintenance"].index(ws["status"]),
                    key=f"wss_{ws['id']}", label_visibility="collapsed")
                if ws["status"] == "maintenance" or new_status == "maintenance":
                    note = st.text_input("Maintenance note", value=ws.get("notes",""),
                                         key=f"wn_{ws['id']}", placeholder="e.g. Screen broken")
                else:
                    note = ws.get("notes","")
                if new_status != ws["status"] or note != ws.get("notes",""):
                    for w in workstations:
                        if w["id"]==ws["id"]:
                            w["status"] = new_status
                            w["notes"]  = note
                    save("workstations", workstations)
                    st.rerun()

    with tab2:
        search = render_search("Search by workstation label (e.g. PC-01)...")
        attendance = load("attendance")
        ws_records = [a for a in attendance if a.get("workstation")]
        if search:
            ws_records = [a for a in ws_records
                          if search.lower() in a["workstation"].lower()]
        if ws_records:
            df = pd.DataFrame(ws_records)[["workstation","student_id","student_name","date","time","type"]]
            df.columns = ["Workstation","Student ID","Student Name","Date","Time","Type"]
            st.dataframe(df.sort_values(["Workstation","Date"],ascending=[True,False]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No workstation usage records yet.")


def page_attendance():
    st.markdown('<div class="main-header"><h1>📋 Attendance & Check-In</h1></div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["✅ Check-In", "🚪 Check-Out", "📋 Records & Export"])

    with tab1:
        sessions = load("sessions")
        bookings = load("bookings")
        users    = load("users")
        ws_list  = load("workstations")
        avail_ws = [w["label"] for w in ws_list if w["status"]=="available"]

        check_type = st.radio("Type", ["Scheduled Session","Open-Access Booking"], horizontal=True)
        with st.form("checkin"):
            stu_id = st.text_input("Student ID *")
            if check_type == "Scheduled Session":
                opts = [f"{s['id']} | {s['course']} | {s['date']} {s['start_time']}–{s['end_time']}"
                        for s in sessions]
                sel  = st.selectbox("Session", opts) if opts else st.text_input("No sessions")
            else:
                opts = [f"{b['id']} | {b['student_id']} | {b['date']} {b['time_slot']}"
                        for b in bookings if b["status"]=="approved"]
                sel  = st.selectbox("Booking", opts) if opts else st.text_input("No approved bookings")

            ws = st.selectbox("Assign Workstation", avail_ws) if avail_ws else st.text_input("None available")
            if st.form_submit_button("✅ Check In", use_container_width=True):
                student = next((u for u in users if u["id"]==stu_id), None)
                if not student:
                    st.error("Student ID not found.")
                else:
                    attendance = load("attendance")
                    # check not already checked in today
                    already = any(a["student_id"]==stu_id and a["date"]==str(date.today())
                                  and not a.get("checked_out") for a in attendance)
                    if already:
                        st.warning("Student is already checked in and hasn't checked out yet.")
                    else:
                        ref_id = sel.split(" | ")[0] if sel else ""
                        record = {
                            "id": f"ATT{len(attendance)+1:05d}",
                            "student_id": stu_id, "student_name": student["name"],
                            "type": check_type, "reference_id": ref_id,
                            "workstation": ws, "date": str(date.today()),
                            "time": datetime.now().strftime("%H:%M"),
                            "status": "present", "checked_out": False, "checkout_time": None
                        }
                        attendance.append(record)
                        save("attendance", attendance)
                        wss = load("workstations")
                        for w in wss:
                            if w["label"]==ws: w["status"]="in-use"
                        save("workstations", wss)
                        add_notification(stu_id, f"You checked in at {ws} on {date.today()} {record['time']}","info")
                        st.success(f"✅ {student['name']} checked in at {ws}")

    with tab2:
        attendance = load("attendance")
        active = [a for a in attendance if not a.get("checked_out") and a["date"]==str(date.today())]
        if not active:
            st.info("No students currently checked in.")
        else:
            st.write(f"**{len(active)} student(s) currently in lab:**")
            for a in active:
                c1,c2 = st.columns([4,1])
                c1.write(f"**{a['student_name']}** (`{a['student_id']}`) — {a['workstation']} since {a['time']}")
                if c2.button("🚪 Check Out", key=f"co_{a['id']}"):
                    for rec in attendance:
                        if rec["id"]==a["id"]:
                            rec["checked_out"]   = True
                            rec["checkout_time"] = datetime.now().strftime("%H:%M")
                    save("attendance", attendance)
                    wss = load("workstations")
                    for w in wss:
                        if w["label"]==a["workstation"]: w["status"]="available"
                    save("workstations", wss)
                    add_notification(a["student_id"],
                        f"You checked out of {a['workstation']} at {datetime.now().strftime('%H:%M')}","info")
                    st.rerun()

    with tab3:
        attendance = load("attendance")
        if not attendance:
            st.info("No records yet.")
            return
        df = pd.DataFrame(attendance)
        c1,c2,c3 = st.columns(3)
        d_filter   = c1.date_input("Date",       value=None)
        t_filter   = c2.selectbox("Type",        ["All","Scheduled Session","Open-Access Booking"])
        src_filter = c3.text_input("Student ID / Name search")

        if d_filter: df = df[df["date"]==str(d_filter)]
        if t_filter!="All": df = df[df["type"]==t_filter]
        if src_filter:
            df = df[df["student_id"].str.contains(src_filter, case=False) |
                    df["student_name"].str.contains(src_filter, case=False)]

        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "attendance.csv","text/csv", use_container_width=True)


def page_reports():
    st.markdown('<div class="main-header"><h1>📈 Reports & Analytics</h1></div>', unsafe_allow_html=True)

    attendance = load("attendance")
    if not attendance:
        st.info("No data yet."); return

    df = pd.DataFrame(attendance)
    df["date"] = pd.to_datetime(df["date"])

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Daily Check-ins (Last 14 Days)")
        daily = df.groupby("date").size().reset_index(name="count").tail(14)
        fig = px.bar(daily, x="date", y="count", color_discrete_sequence=["#2d6a9f"])
        fig.update_layout(margin=dict(t=10), height=280)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Session vs Open-Access Split")
        tc = df["type"].value_counts().reset_index()
        tc.columns = ["Type","Count"]
        fig2 = px.pie(tc, values="Count", names="Type",
                      color_discrete_sequence=["#1e3a5f","#2d9fd6"])
        fig2.update_layout(margin=dict(t=10), height=280)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Workstation Usage")
    wc = df["workstation"].value_counts().reset_index()
    wc.columns = ["Workstation","Uses"]
    fig3 = px.bar(wc.head(20), x="Workstation", y="Uses", color_discrete_sequence=["#1e3a5f"])
    fig3.update_layout(margin=dict(t=10), height=280)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Most Active Students")
    top = df.groupby(["student_id","student_name"]).size().reset_index(name="Visits")
    top = top.sort_values("Visits", ascending=False).head(10)
    st.dataframe(top, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# STUDENT PAGES
# ══════════════════════════════════════════════════════════════════════════════
def page_student_dashboard():
    user = st.session_state.user
    st.markdown(f'<div class="main-header"><h1>👋 Welcome, {user["name"]}</h1>'
                f'<p>Your lab activity overview</p></div>', unsafe_allow_html=True)

    att        = load("attendance")
    bookings   = load("bookings")
    my_att     = [a for a in att     if a["student_id"]==user["id"]]
    my_bk      = [b for b in bookings if b["student_id"]==user["id"]]
    pending    = [b for b in my_bk if b["status"]=="pending"]
    approved   = [b for b in my_bk if b["status"]=="approved"]
    checked_in = [a for a in my_att if not a.get("checked_out") and a["date"]==str(date.today())]

    c1,c2,c3,c4 = st.columns(4)
    for col,val,label in [
        (c1, len(my_att),    "Total Visits"),
        (c2, len(my_bk),     "My Bookings"),
        (c3, len(pending),   "Pending Requests"),
        (c4, len(approved),  "Upcoming Approved"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="value">{val}</div>'
                     f'<div class="label">{label}</div></div>', unsafe_allow_html=True)

    if checked_in:
        st.success(f"🟢 You are currently checked in at **{checked_in[0]['workstation']}** since {checked_in[0]['time']}")

    st.markdown("---")
    st.subheader("Recent Activity")
    if my_att:
        df = pd.DataFrame(my_att)[["date","time","type","workstation","status","checked_out","checkout_time"]]
        df.columns = ["Date","Time","Type","Workstation","Status","Checked Out","Checkout Time"]
        st.dataframe(df.sort_values("Date",ascending=False).head(10),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No visits recorded yet.")

    st.subheader("Upcoming Approved Bookings")
    upcoming = [b for b in approved if b["date"] >= str(date.today())]
    if upcoming:
        df2 = pd.DataFrame(upcoming)[["id","date","time_slot"]]
        df2.columns = ["Booking ID","Date","Time Slot"]
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming bookings.")


def page_book_slot():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>🗓️ Book a Lab Slot</h1>'
                '<p>Request open-access computer time (up to 2 days ahead)</p></div>',
                unsafe_allow_html=True)

    max_date    = date.today() + timedelta(days=MAX_BOOKING_DAYS_AHEAD)
    MAX_PER_SLOT = 5

    # ── Slot availability grid ────────────────────────────────────────────
    st.subheader("📊 Slot Availability")
    for d_offset in range(MAX_BOOKING_DAYS_AHEAD+1):
        check_date = date.today() + timedelta(days=d_offset)
        st.markdown(f"**{check_date.strftime('%A, %d %b')}**")
        cols = st.columns(len(TIME_SLOTS))
        for i, slot in enumerate(TIME_SLOTS):
            count = slot_booking_count(check_date, slot)
            avail = MAX_PER_SLOT - count
            cols[i].markdown(
                f"<div style='text-align:center;font-size:.75rem'>{slot}<br>"
                f"<b style='color:{'#155724' if avail>0 else '#721c24'}'>"
                f"{'✅' if avail>0 else '🔴'} {avail} left</b></div>",
                unsafe_allow_html=True)
        st.markdown("")

    st.markdown("---")
    with st.form("bk_form"):
        c1,c2 = st.columns(2)
        bk_date  = c1.date_input("Date", min_value=date.today(), max_value=max_date)
        bk_slot  = c2.selectbox("Time Slot", TIME_SLOTS)
        purpose  = st.text_area("Purpose / Reason for Visit (max 300 chars)", max_chars=300)
        if st.form_submit_button("📩 Submit Request", use_container_width=True):
            bookings = load("bookings")
            count = slot_booking_count(bk_date, bk_slot)
            if count >= MAX_PER_SLOT:
                st.error("❌ That slot is fully booked. Please choose another.")
            else:
                conflict = any(
                    b["student_id"]==user["id"] and b["date"]==str(bk_date)
                    and b["time_slot"]==bk_slot and b["status"]!="rejected"
                    for b in bookings)
                if conflict:
                    st.error("You already have a booking for that slot.")
                else:
                    bookings.append({
                        "id": f"BK{len(bookings)+1:04d}",
                        "student_id": user["id"], "student_name": user["name"],
                        "date": str(bk_date), "time_slot": bk_slot,
                        "purpose": purpose, "status": "pending",
                        "created_at": str(datetime.now())
                    })
                    save("bookings", bookings)
                    # notify admins
                    users = load("users")
                    for u in users:
                        if u["role"]=="admin":
                            add_notification(u["id"],
                                f"New booking request from {user['name']} for {bk_date} {bk_slot}","info")
                    st.success("✅ Request submitted! You'll be notified when approved.")

    st.markdown("---")
    st.subheader("My Booking History")
    bookings = load("bookings")
    mine = [b for b in bookings if b["student_id"]==user["id"]]
    if mine:
        df = pd.DataFrame(mine)[["id","date","time_slot","status","purpose"]]
        df.columns = ["ID","Date","Time Slot","Status","Purpose"]
        st.dataframe(df.sort_values("Date",ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No bookings yet.")


def page_my_history():
    user = st.session_state.user
    st.markdown('<div class="main-header"><h1>📋 My Visit History</h1></div>', unsafe_allow_html=True)

    att  = load("attendance")
    mine = [a for a in att if a["student_id"]==user["id"]]
    if mine:
        df = pd.DataFrame(mine)
        cols_wanted = [c for c in ["date","time","type","workstation","status","checkout_time"] if c in df.columns]
        df = df[cols_wanted]
        st.dataframe(df.sort_values("date",ascending=False), use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False)
        st.download_button("📥 Download My History", csv, "my_history.csv","text/csv")
    else:
        st.info("No visit records yet.")

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    auth_pages()
else:
    auto_reject_expired_bookings()
    page = sidebar_nav()
    role = st.session_state.user["role"]

    if role == "admin":
        route = {
            "📊 Dashboard":          page_admin_dashboard,
            "🔔 Notifications":      page_notifications,
            "🎓 Students":           page_students,
            "📅 Lab Sessions":       page_lab_sessions,
            "🗓️ Bookings":           page_bookings,
            "🖥️ Workstations":       page_workstations,
            "📋 Attendance":         page_attendance,
            "📈 Reports":            page_reports,
            "⚙️ Profile & Settings": page_profile,
        }
    elif role == "lecturer":
        route = {
            "📊 Dashboard":          page_admin_dashboard,
            "🔔 Notifications":      page_notifications,
            "📅 Lab Sessions":       page_lab_sessions,
            "📋 Attendance":         page_attendance,
            "⚙️ Profile & Settings": page_profile,
        }
    else:
        route = {
            "📊 My Dashboard":       page_student_dashboard,
            "🔔 Notifications":      page_notifications,
            "🗓️ Book a Slot":        page_book_slot,
            "📋 My History":         page_my_history,
            "⚙️ Profile & Settings": page_profile,
        }

    fn = route.get(page)
    if fn: fn()
