# app.py
# DevRPG + AI Quest Generator + Login (per-user save) + Locked Roles
# Run: streamlit run app.py

import streamlit as st
import json, os, math, random, uuid, hashlib
from datetime import date, datetime

# =========================
# FILES / CONSTANTS
# =========================
USERS_FILE = "users.json"
ROLE_OPTIONS = ["Fullstack", "Backend", "Frontend", "QA", "Data", "Manager"]

def user_data_file(username: str) -> str:
    safe = "".join([c for c in (username or "").lower() if c.isalnum() or c in ("_", "-")]).strip()
    return f"devrpg_{safe}.json"

# =========================
# AUTH HELPERS
# =========================
def hash_pw(pw: str) -> str:
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()

def load_users() -> dict:
    if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users: dict):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USERS_FILE)

# =========================
# DEFAULT STATE
# =========================
def default_state():
    return {
        "profile": {
            "username": None,
            "role": "Fullstack",      # ALWAYS overridden by users.json (locked)
            "mode": "single",         # single / team (basic UI only)
            "team_name": "IBF Digital Team"
        },
        "xp": 0,
        "coins": 0,
        "focus": 100,
        "streak": 0,
        "last_day": None,
        "xp_boost": 0.0,
        "stats": {"intelligence": 1, "speed": 1, "stability": 1},
        "quests": [],
        "history": []
    }

# =========================
# SAFE STORAGE
# =========================
def deep_merge(default, incoming):
    if isinstance(default, dict) and isinstance(incoming, dict):
        out = dict(default)
        for k, v in incoming.items():
            if k in out:
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    return incoming

def load_data(filepath: str):
    d = default_state()
    if not filepath or not os.path.exists(filepath):
        return d
    try:
        if os.path.getsize(filepath) == 0:
            return d
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return deep_merge(d, loaded)
    except (json.JSONDecodeError, OSError):
        try:
            bad_name = filepath.replace(".json", f".bad_{int(datetime.now().timestamp())}.json")
            os.rename(filepath, bad_name)
        except Exception:
            pass
        return d

def save_data(filepath: str, data: dict):
    if not filepath:
        return
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filepath)

# =========================
# OFFLINE QUEST GENERATOR
# =========================
def offline_generate_quests(text: str):
    t = (text or "").strip()
    low = t.lower()
    quests = []

    if any(k in low for k in ["bug", "fix", "error", "issue", "crash"]):
        quests += [
            ("Reproduce bug + identify root cause", "Medium", 40, 20, "intelligence"),
            ("Implement fix + regression check", "Hard", 80, 35, "stability"),
        ]

    if any(k in low for k in ["api", "endpoint", "laravel", "backend"]):
        quests += [
            ("Design API contract (request/response)", "Easy", 20, 10, "intelligence"),
            ("Implement API + validation + auth", "Hard", 80, 35, "intelligence"),
        ]

    if any(k in low for k in ["ui", "frontend", "quasar", "page", "screen", "vue"]):
        quests += [
            ("Build UI components + state handling", "Medium", 40, 20, "speed"),
            ("Integrate UI with API + loading/error states", "Medium", 40, 20, "speed"),
        ]

    if any(k in low for k in ["sql", "query", "slow", "optimize", "performance", "index", "database", "db"]):
        quests += [
            ("Profile query + add indexes", "Hard", 80, 35, "intelligence"),
            ("Optimize queries + verify speed", "Medium", 40, 20, "stability"),
        ]

    if any(k in low for k in ["report", "dashboard", "analytics", "chart", "kpi"]):
        quests += [
            ("Define metrics + filters (report spec)", "Easy", 20, 10, "intelligence"),
            ("Add export (CSV/Excel) if needed", "Easy", 20, 10, "stability"),
        ]

    quests += [
        ("Clarify requirements + acceptance criteria", "Easy", 20, 10, "stability"),
        ("Write tests / QA checklist", "Medium", 40, 20, "stability"),
        ("Deploy to staging + smoke test", "Hard", 80, 35, "stability"),
        ("Update docs / release notes", "Easy", 20, 10, "stability"),
    ]

    seen = set()
    final = []
    for name, diff, xp, focus, stat in quests:
        if name not in seen:
            seen.add(name)
            final.append({"name": name, "difficulty": diff, "xp": xp, "focus_cost": focus, "stat_gain": stat})

    main = f"Deliver: {t[:90]}" if t else "Deliver the requested feature"
    return {"main_quest": main, "quests": final[:10]}

# =========================
# ROLES BONUS
# =========================
def get_role_bonus(role: str, quest_name: str):
    q = (quest_name or "").lower()
    bonus = 1.0
    focus_discount = 0

    if role == "Backend":
        if any(k in q for k in ["api", "endpoint", "laravel", "sql", "db", "database", "migration"]):
            bonus = 1.10

    elif role == "Frontend":
        if any(k in q for k in ["ui", "page", "screen", "quasar", "vue", "component"]):
            bonus = 1.10

    elif role == "QA":
        if any(k in q for k in ["test", "qa", "bug", "regression", "smoke"]):
            bonus = 1.10
            focus_discount = 2

    elif role == "Data":
        if any(k in q for k in ["report", "dashboard", "analytics", "kpi", "chart"]):
            bonus = 1.15

    elif role == "Manager":
        if any(k in q for k in ["boss", "release", "deployment", "sprint", "planning"]):
            bonus = 1.20
        else:
            bonus = 1.05

    elif role == "Fullstack":
        if any(k in q for k in ["api", "endpoint", "laravel", "sql", "db", "database", "migration"]):
            bonus = max(bonus, 1.08)
        if any(k in q for k in ["ui", "page", "screen", "quasar", "vue", "component"]):
            bonus = max(bonus, 1.08)
        if any(k in q for k in ["integrate", "integration", "connect", "fetch", "auth", "sanctum"]):
            bonus = max(bonus, 1.12)
            focus_discount = 3
        if any(k in q for k in ["deploy", "deployment", "staging", "prod", "pipeline"]):
            bonus = max(bonus, 1.10)

    return bonus, focus_discount

# =========================
# GAME LOGIC
# =========================
def calc_level(xp: int) -> int:
    return int(math.sqrt(xp / 100)) + 1

def title_by_level(lvl: int) -> str:
    titles = [
        (1, "Junior Adventurer"),
        (3, "Code Warrior"),
        (5, "System Architect"),
        (8, "Deployment Overlord"),
        (12, "Production Emperor"),
        (20, "IBF Legend"),
    ]
    t = "Junior Adventurer"
    for l, name in titles:
        if lvl >= l:
            t = name
    return t

def log(data, action, detail=""):
    data["history"].append({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "detail": detail
    })

def next_id() -> str:
    return uuid.uuid4().hex

def apply_xp_boost_once(data, base_xp: int) -> int:
    boost = float(data.get("xp_boost", 0.0) or 0.0)
    gained = int(base_xp * (1.0 + boost))
    data["xp_boost"] = 0.0
    return gained

def clamp_focus(x: int) -> int:
    return max(0, min(100, x))

def ensure_daily_reset(filepath: str, data, today_str: str):
    if data.get("last_day") == today_str:
        return

    if data.get("last_day") is None:
        data["streak"] = 1
    else:
        last_date = datetime.strptime(data["last_day"], "%Y-%m-%d").date()
        diff = (date.today() - last_date).days
        if diff == 1:
            data["streak"] += 1
        else:
            data["streak"] = 1

    data["last_day"] = today_str
    data["focus"] = 100
    data["xp_boost"] = 0.0

    log(data, "NEW_DAY", f"Streak: {data['streak']}")
    save_data(filepath, data)

# =========================
# UI SETUP
# =========================
st.set_page_config(page_title="DevRPG ⚔️", page_icon="⚔️", layout="wide")

# ---- LOGIN GATE ----
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

users = load_users()

def login_ui():
    st.title("🔐 DevRPG Access")
    st.caption("Register once. Role is locked permanently after registration.")

    tab_login, tab_register = st.tabs(["✅ Login", "🆕 Register"])

    # LOGIN
    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_user").strip()
            pw = st.text_input("Password / PIN", type="password", key="login_pw").strip()
            submit = st.form_submit_button("Login")

        if submit:
            if not username or not pw:
                st.error("Username and password are required.")
                st.stop()

            u = users.get(username)
            if not u or u.get("pw") != hash_pw(pw):
                st.error("Invalid username/password.")
                st.stop()

            st.session_state.auth_user = username
            st.success(f"Welcome back **{username}** ✅")
            st.info(f"🎭 Role: **{u.get('role','Fullstack')}** 🔒")
            st.rerun()

    # REGISTER
    with tab_register:
        with st.form("register_form", clear_on_submit=False):
            username = st.text_input("New Username", key="reg_user").strip()
            pw1 = st.text_input("Create Password / PIN", type="password", key="reg_pw1").strip()
            pw2 = st.text_input("Confirm Password / PIN", type="password", key="reg_pw2").strip()

            # role ONLY at registration
            role = st.selectbox("Choose your role (one-time)", ROLE_OPTIONS, index=0, key="reg_role")

            submit = st.form_submit_button("Create Account")

        if submit:
            if not username or not pw1 or not pw2:
                st.error("All fields are required.")
                st.stop()

            if username in users:
                existing_role = users[username].get("role", "Fullstack")
                st.error(f"Username already exists. Role is **{existing_role}** 🔒 (cannot re-choose).")
                st.stop()

            if pw1 != pw2:
                st.error("Passwords do not match.")
                st.stop()

            if len(pw1) < 4:
                st.error("Password/PIN too short. Use at least 4 characters.")
                st.stop()

            users[username] = {
                "pw": hash_pw(pw1),
                "role": role,
                "role_locked": True
            }
            save_users(users)

            st.success("Account created ✅ Now go to Login tab.")
            st.info(f"🎭 Role locked as: **{role}** 🔒")
            st.stop()

if not st.session_state.auth_user:
    login_ui()
    st.stop()  # IMPORTANT: stop running the rest of the app until logged in

# ---- Load per-user data ----
username = st.session_state.auth_user
DATA_FILE = user_data_file(username)

data = load_data(DATA_FILE)
data["profile"]["username"] = username

# ALWAYS enforce locked role from users.json
locked_role = users.get(username, {}).get("role", "Fullstack")
data["profile"]["role"] = locked_role

today = str(date.today())
ensure_daily_reset(DATA_FILE, data, today)

lvl = calc_level(int(data["xp"]))
title = title_by_level(lvl)

# =========================
# SIDEBAR HUD
# =========================
st.sidebar.title("🧙 DevRPG Character")
st.sidebar.write(f"👤 **User:** {username}")
st.sidebar.write(f"🎭 **Role:** {locked_role} 🔒")

data["profile"]["mode"] = st.sidebar.selectbox("🎮 Mode", ["single", "team"], index=0, key="sidebar_mode")
if data["profile"]["mode"] == "team":
    data["profile"]["team_name"] = st.sidebar.text_input(
        "👥 Team Name",
        value=data["profile"].get("team_name", "IBF Digital Team"),
        key="sidebar_team"
    )

st.sidebar.write(f"**{title}**")
st.sidebar.metric("Level", lvl)
st.sidebar.metric("XP", int(data["xp"]))
st.sidebar.metric("Coins", int(data["coins"]))
st.sidebar.metric("Focus 🔥", int(data["focus"]))
st.sidebar.metric("Streak", f"{int(data['streak'])} days")

st.sidebar.subheader("Stats")
st.sidebar.write(f"🧠 Intelligence: **{int(data['stats']['intelligence'])}**")
st.sidebar.write(f"⚡ Speed: **{int(data['stats']['speed'])}**")
st.sidebar.write(f"🛡 Stability: **{int(data['stats']['stability'])}**")

if float(data.get("xp_boost", 0.0) or 0.0) > 0:
    st.sidebar.info(f"XP Boost active: +{int(data['xp_boost']*100)}% (next quest)")

st.sidebar.divider()
if st.sidebar.button("🚪 Logout", key="logout_btn"):
    st.session_state.auth_user = None
    st.rerun()

with st.sidebar.expander("⚙️ Debug / Reset", expanded=False):
    if st.button("Reset MY data (this user)", key="reset_my_data"):
        try:
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
        except Exception:
            pass
        st.warning("Your data reset. Refresh the page (F5).")

# persist current data
save_data(DATA_FILE, data)

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["🏠 Dashboard", "⚔️ Campaign", "🧪 Break & Recovery", "👹 Boss Raid", "🎁 Armory", "🤖 AI Task Generator", "🤖 AI Quest Generator"]
)

# =========================
# TAB 1: DASHBOARD
# =========================
with tab1:
    st.title("🏠 Dashboard")
    st.caption("Daily campaign overview. Ship features. Slay bugs. Protect production.")

    st.progress((int(data["xp"]) % 1000) / 1000)

    colA, colB, colC, colD = st.columns(4)

    with colA:
        if st.button("🎲 Roll Random Event", key="roll_event"):
            event = random.choice([
                {"name": "🚨 Production Alert!", "desc": "Next quest XP +40%.", "boost": 0.40},
                {"name": "🧪 QA Flood!", "desc": "Next quest XP +20%.", "boost": 0.20},
                {"name": "🌤 Stable Day!", "desc": "Next quest XP +10%.", "boost": 0.10},
                {"name": "⚡ Focus Surge!", "desc": "+20 Focus instantly.", "boost": 0.0, "focus": 20},
            ])

            if event.get("focus"):
                data["focus"] = clamp_focus(int(data["focus"]) + int(event["focus"]))
                log(data, "EVENT", f"{event['name']} (+{event['focus']} Focus)")
            else:
                data["xp_boost"] = max(float(data.get("xp_boost", 0.0) or 0.0), float(event["boost"]))
                log(data, "EVENT", f"{event['name']} (XP boost set)")

            save_data(DATA_FILE, data)
            st.success(f"{event['name']} — {event['desc']}")

    with colB:
        done_today = sum(1 for q in data["quests"] if q.get("done_date") == today)
        st.metric("Done today", done_today)

    with colC:
        pending = sum(1 for q in data["quests"] if not q.get("done"))
        st.metric("Pending", pending)

    with colD:
        st.metric("Today", today)

    st.divider()

    col1, col2 = st.columns([0.55, 0.45])
    with col1:
        st.subheader("📌 Quest Board Snapshot")
        pending_q = [q for q in data["quests"] if not q.get("done")]
        if not pending_q:
            st.info("No pending quests. Add quests in ⚔️ Campaign tab.")
        else:
            for q in pending_q[:8]:
                bonus, focus_discount = get_role_bonus(locked_role, q["name"])
                effective_focus = max(0, int(q["focus_cost"]) - focus_discount)
                st.write(f"- **{q['name']}** ({q['difficulty']}) — {q['xp']} XP • Focus -{effective_focus} • Role x{bonus:.2f}")

    with col2:
        st.subheader("📜 Recent Activity")
        if not data["history"]:
            st.info("No activity yet.")
        else:
            for h in reversed(data["history"][-12:]):
                st.write(f"- `{h['ts']}` **{h['action']}** — {h['detail']}")

# =========================
# TAB 2: CAMPAIGN
# =========================
with tab2:
    st.title("⚔️ Daily Campaign")
    st.caption("Create quests, complete them, earn XP + coins, grow stats. Use breaks to restore Focus.")

    with st.expander("🎯 Quick Add Presets (IBF Senior Fullstack)", expanded=False):
        preset = st.selectbox(
            "Pick a preset quest",
            [
                "Fullstack integration (API + UI + Auth) — Hard",
                "Fix API bug (Laravel) — Medium",
                "Frontend integration (Quasar) — Medium",
                "Production incident — Hard",
                "Optimize slow query (MySQL) — Hard",
                "Write tests / PR review — Easy",
                "Deploy to staging + smoke test — Hard",
                "Documentation / release note — Easy",
            ],
            index=0,
            key="preset_select"
        )

        if st.button("➕ Add Preset Quest", key="add_preset"):
            name_map = {
                "Fullstack integration (API + UI + Auth) — Hard": ("Fullstack integration (API + UI + Auth)", "Hard"),
                "Fix API bug (Laravel) — Medium": ("Fix API bug (Laravel)", "Medium"),
                "Frontend integration (Quasar) — Medium": ("Frontend integration (Quasar)", "Medium"),
                "Production incident — Hard": ("Production incident / hotfix", "Hard"),
                "Optimize slow query (MySQL) — Hard": ("Optimize slow query (MySQL)", "Hard"),
                "Write tests / PR review — Easy": ("Write tests / review PRs", "Easy"),
                "Deploy to staging + smoke test — Hard": ("Deploy to staging + smoke test", "Hard"),
                "Documentation / release note — Easy": ("Documentation / release note", "Easy"),
            }
            n, dff = name_map[preset]
            xp_map = {"Easy": 20, "Medium": 40, "Hard": 80}
            focus_cost_map = {"Easy": 10, "Medium": 20, "Hard": 35}
            stat_gain_map = {"Easy": "stability", "Medium": "speed", "Hard": "intelligence"}

            q = {
                "id": next_id(),
                "name": n,
                "difficulty": dff,
                "xp": xp_map[dff],
                "coins": max(1, int(xp_map[dff] / 5)),
                "focus_cost": focus_cost_map[dff],
                "stat_gain": stat_gain_map[dff],
                "created_date": today,
                "done": False,
                "done_date": None
            }
            data["quests"].append(q)
            log(data, "ADD_QUEST", f"{n} ({dff})")
            save_data(DATA_FILE, data)
            st.success("Preset quest added!")

    st.divider()

    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1, key="manual_diff")
    base_xp_map = {"Easy": 20, "Medium": 40, "Hard": 80}
    base_focus_cost = {"Easy": 10, "Medium": 20, "Hard": 35}
    base_stat_gain = {"Easy": "stability", "Medium": "speed", "Hard": "intelligence"}

    quest_name = st.text_input("Quest name", placeholder="e.g., Implement Orders Summary API + integrate UI + tests", key="manual_name")

    col1, col2, col3 = st.columns([0.33, 0.33, 0.34])
    with col1:
        xp_reward = st.number_input("Base XP", min_value=10, max_value=500, value=base_xp_map[difficulty], step=5, key="manual_xp")
    with col2:
        focus_cost = st.number_input("Focus cost", min_value=5, max_value=80, value=base_focus_cost[difficulty], step=1, key="manual_focus")
    with col3:
        coins_reward = st.number_input("Coins", min_value=0, max_value=200, value=max(1, int(xp_reward / 5)), step=1, key="manual_coins")

    st.caption(f"Stat gain on complete: **{base_stat_gain[difficulty]}**")

    if st.button("➕ Add Quest", key="manual_add"):
        if not quest_name.strip():
            st.warning("Enter a quest name.")
        else:
            q = {
                "id": next_id(),
                "name": quest_name.strip(),
                "difficulty": difficulty,
                "xp": int(xp_reward),
                "coins": int(coins_reward),
                "focus_cost": int(focus_cost),
                "stat_gain": base_stat_gain[difficulty],
                "created_date": today,
                "done": False,
                "done_date": None
            }
            data["quests"].append(q)
            log(data, "ADD_QUEST", f"{q['name']} ({difficulty})")
            save_data(DATA_FILE, data)
            st.success("Quest added!")

    st.divider()

    pending = [q for q in data["quests"] if not q.get("done")]
    done_today = [q for q in data["quests"] if q.get("done_date") == today]

    colL, colR = st.columns(2)

    with colL:
        st.subheader("🕒 Pending Quests")
        if not pending:
            st.info("No pending quests.")

        for q in pending:
            bonus, focus_discount = get_role_bonus(locked_role, q["name"])
            effective_focus = max(0, int(q["focus_cost"]) - focus_discount)

            with st.container(border=True):
                st.write(f"**{q['name']}**")
                st.write(
                    f"{q['difficulty']} • Base {q['xp']} XP • {q['coins']} coins • "
                    f"Focus -{effective_focus} • Stat: {q['stat_gain']} • Role x{bonus:.2f}"
                )

                cA, cB, cC = st.columns([0.34, 0.33, 0.33])
                with cA:
                    if st.button("✅ Complete", key=f"complete_{q['id']}"):
                        if int(data["focus"]) < int(effective_focus):
                            st.error("Not enough Focus. Go to 🧪 Break & Recovery.")
                        else:
                            base_xp = apply_xp_boost_once(data, int(q["xp"]))
                            gained_xp = int(base_xp * bonus)

                            data["xp"] = int(data["xp"]) + gained_xp
                            data["coins"] = int(data["coins"]) + int(q["coins"])
                            data["focus"] = clamp_focus(int(data["focus"]) - int(effective_focus))

                            sg = q.get("stat_gain", "speed")
                            data["stats"][sg] = int(data["stats"][sg]) + 1

                            q["done"] = True
                            q["done_date"] = today

                            log(data, "DONE_QUEST", f"{q['name']} (+{gained_xp} XP, +{q['coins']}c, role {locked_role})")
                            save_data(DATA_FILE, data)
                            st.balloons()

                with cB:
                    if st.button("🗑 Delete", key=f"del_{q['id']}"):
                        data["quests"] = [x for x in data["quests"] if x.get("id") != q.get("id")]
                        log(data, "DELETE_QUEST", q["name"])
                        save_data(DATA_FILE, data)
                        st.rerun()

                with cC:
                    if st.button("↩️ Defer", key=f"defer_{q['id']}"):
                        q["focus_cost"] = min(80, int(q["focus_cost"]) + 2)
                        log(data, "DEFER_QUEST", q["name"])
                        save_data(DATA_FILE, data)
                        st.toast("Deferred. Slightly higher focus cost next time 😈")

    with colR:
        st.subheader("✅ Completed Today")
        if not done_today:
            st.info("Nothing completed today yet.")
        for q in done_today:
            with st.container(border=True):
                st.write(f"**{q['name']}**")
                st.write(f"Completed • {q['difficulty']} • Base {q['xp']} XP")

# =========================
# TAB 3: BREAK & RECOVERY
# =========================
with tab3:
    st.title("🧪 Break & Recovery")
    st.caption("Breaks are part of the RPG. Recover focus to keep crushing tasks.")

    breaks = [
        ("🚶 Walk 10 minutes", 15),
        ("🧘 Stretch 5 minutes", 10),
        ("💧 Water + eye rest", 10),
        ("🍽 Lunch (no screen)", 35),
        ("😴 Power nap 15 minutes", 25),
    ]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recover Focus")
        for label, gain in breaks:
            if st.button(f"{label}  (+{gain} Focus)", key=f"break_{label}"):
                data["focus"] = clamp_focus(int(data["focus"]) + int(gain))
                log(data, "BREAK", f"{label} (+{gain} focus)")
                save_data(DATA_FILE, data)
                st.success(f"Recovered +{gain} Focus!")

    with col2:
        st.subheader("Focus Rules (Game)")
        st.write("- If Focus is low, Hard quests fail.")
        st.write("- Take breaks to keep speed + quality high.")
        st.write("- Random events may give Focus Surge.")
        st.divider()
        if st.button("🧯 Emergency Recovery (+30 Focus, -10 coins)", key="emergency"):
            if int(data["coins"]) < 10:
                st.warning("Not enough coins for Emergency Recovery.")
            else:
                data["coins"] = int(data["coins"]) - 10
                data["focus"] = clamp_focus(int(data["focus"]) + 30)
                log(data, "EMERGENCY_RECOVERY", "+30 Focus (-10 coins)")
                save_data(DATA_FILE, data)
                st.success("Emergency Recovery used!")

# =========================
# TAB 4: BOSS RAID
# =========================
with tab4:
    st.title("👹 Boss Raid")
    st.caption("Use this for major deliveries: releases, migrations, big modules, critical incidents.")

    boss_type = st.selectbox(
        "Boss Type",
        ["Major Release", "DB Migration", "Critical Production Incident", "New Module Delivery"],
        key="boss_type"
    )
    boss_reward_xp = st.slider("Boss XP Reward", 100, 1200, 300, step=25, key="boss_xp")
    boss_reward_coins = st.slider("Boss Coins Reward", 20, 400, 80, step=5, key="boss_coins")

    boss_done = st.text_area(
        "Boss 'Done' condition (Definition of Done)",
        placeholder="Example: deployed to staging + smoke tests passed + PR merged + release notes updated",
        height=90,
        key="boss_done"
    )

    if st.button("💀 Defeat Boss", key="boss_defeat"):
        data["xp"] = int(data["xp"]) + int(boss_reward_xp)
        data["coins"] = int(data["coins"]) + int(boss_reward_coins)
        data["stats"]["intelligence"] = int(data["stats"]["intelligence"]) + 2
        data["stats"]["stability"] = int(data["stats"]["stability"]) + 1
        log(data, "BOSS_DEFEATED", f"{boss_type} (+{boss_reward_xp} XP, +{boss_reward_coins}c) | DoD: {boss_done[:120]}")
        save_data(DATA_FILE, data)
        st.success("BOSS DEFEATED 💀 Massive rewards!")
        st.balloons()

# =========================
# TAB 5: ARMORY
# =========================
with tab5:
    st.title("🎁 Armory (Rewards Shop)")
    st.caption("Spend coins on real-life rewards. Keep it healthy + motivating.")

    rewards = [
        ("☕ Coffee treat", 20),
        ("🎧 Music session 20m", 25),
        ("🍜 Treat meal", 80),
        ("🎮 Gaming 1 hour", 90),
        ("🛍 Gear fund (keyboard/mouse)", 150),
    ]

    for name, cost in rewards:
        colL, colR = st.columns([0.7, 0.3])
        colL.write(f"**{name}** — {cost} coins")
        if colR.button("Redeem", key=f"redeem_{name}"):
            if int(data["coins"]) < cost:
                st.warning("Not enough coins.")
            else:
                data["coins"] = int(data["coins"]) - cost
                log(data, "REDEEM", f"{name} (-{cost}c)")
                save_data(DATA_FILE, data)
                st.success(f"Redeemed: {name}")

    st.divider()
    with st.expander("📦 Export / Backup"):
        st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")

# =========================
# TAB 6: AI TASK GENERATOR (Prompt Builder)
# =========================
with tab6:
    st.title("🤖 AI Task Generator (Prompt Builder)")
    st.caption("This does NOT call an API. It builds a strong prompt you paste into ChatGPT.")

    work_request = st.text_area(
        "Work Request",
        placeholder="Example: Build HR Order Summary dashboard with filters + API endpoints + UI + export CSV.",
        height=170,
        key="prompt_work"
    )

    col1, col2, col3 = st.columns(3)
    deadline = col1.text_input("Deadline (optional)", placeholder="e.g., 2026-02-20", key="prompt_deadline")
    environment = col2.selectbox("Environment", ["dev", "staging", "prod"], index=1, key="prompt_env")
    team = col3.multiselect(
        "Team",
        ["backend (me)", "frontend", "QA", "data assistant", "PM/Manager"],
        default=["backend (me)", "frontend", "QA"],
        key="prompt_team"
    )

    mode = st.radio("Generate", ["RPG Quests + Jira Tasks", "Jira Tasks only"], horizontal=True, key="prompt_mode")

    st.divider()
    if st.button("✨ Generate Prompt", key="prompt_generate"):
        team_str = ", ".join(team) if team else "backend (me), frontend, QA"
        deadline_str = deadline.strip() if deadline.strip() else "none"

        if mode == "RPG Quests + Jira Tasks":
            prompt = f"""
You are the Game Master of a Developer RPG for IBF (Laravel REST API + MySQL + Quasar + AWS).

Convert the work request below into:

A) RPG Quest Tree
- Main Quest (1)
- Sub Quests (5–10) with: Difficulty, time estimate, XP, Focus cost, stat gain
- Optional Side Quests (2–4)
- Boss Battle Definition of Done

B) Jira-ready breakdown
- Epic
- User stories + acceptance criteria
- Tasks (Backend/Frontend/QA/DevOps)
- Risks + dependencies
- Priority order
- Estimates (S/M/L) and Priority (P0/P1/P2)

Work Request:
{work_request}

Constraints:
- Deadline: {deadline_str}
- Environment: {environment}
- Team: {team_str}

Return clean markdown tables.
""".strip()
        else:
            prompt = f"""
You are a Senior Tech Lead and Scrum Master at IBF.

Create a Jira breakdown for this requirement:
{work_request}

Context:
- Stack: Laravel REST API + MySQL + Quasar (Vue3) + AWS
- Roles: Admin/HR/User
- NFR: security, performance, logging, maintainability

Constraints:
- Deadline: {deadline_str}
- Environment: {environment}
- Team: {team_str}

Output:
1) Epic name
2) User stories (each with acceptance criteria)
3) Tasks by role: Backend, Frontend, QA, DevOps
4) Estimates (S/M/L) and priority (P0/P1/P2)
5) Dependencies + risks
""".strip()

        st.subheader("✅ Copy this prompt into ChatGPT")
        st.code(prompt, language="text")

# =========================
# TAB 7: AI QUEST GENERATOR
# =========================
with tab7:
    st.title("🤖 AI Quest Generator (Offline)")
    st.caption("Generate quests automatically (Offline Mode only).")

    work_request = st.text_area("Describe your task / feature", height=180, key="ai_work")

    if st.button("⚡ Generate Quests", key="ai_generate"):
        if not work_request.strip():
            st.warning("Please describe the task first.")
            st.stop()

        try:
            ai_data = offline_generate_quests(work_request)
            st.success("Generated with Offline Mode ✅")
        except Exception as e:
            st.error(f"Offline generator failed: {e}")
            st.stop()

        st.write("### 🎯 Main Quest")
        st.write(ai_data.get("main_quest", ""))

        added = 0
        for q in ai_data.get("quests", []):
            quest = {
                "id": next_id(),
                "name": q.get("name", "Untitled Quest"),
                "difficulty": q.get("difficulty", "Easy"),
                "xp": int(q.get("xp", 40)),
                "coins": max(1, int(int(q.get("xp", 40)) / 5)),
                "focus_cost": int(q.get("focus_cost", 20)),
                "stat_gain": q.get("stat_gain", "intelligence"),
                "created_date": today,
                "done": False,
                "done_date": None
            }
            data["quests"].append(quest)
            added += 1

        log(data, "AI_IMPORT", f"Imported {added} quests")
        save_data(DATA_FILE, data)

        st.balloons()
        st.success(f"✅ Added {added} quests to your Campaign tab!")
