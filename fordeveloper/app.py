import os
import sys
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime, date, timedelta
from collections import defaultdict
from models import db, Task, Reminder, DailyNote, MdIndex, ActivityLog, Setting, FutureDeployment, init_db
from parser import parse_deployment_log, get_deployment_stats
from md_browser import scan_md_files, render_md, build_file_tree, get_pygments_css
from search_engine import rebuild_index, search_md, trace_tco
from scheduler import init_scheduler
from config import PORT, HOST, DB_PATH, DATA_DIR, PROJECTS_ROOT, CATEGORY_COLORS, CATEGORY_LABELS, get_workspace_root, get_deployment_log_path
from security import verify_machine, require_auth, verify_pin, create_session, destroy_session, set_pin, encrypt_value, decrypt_value
from git_activity import build_sidebar_payload, build_team_payload
from intelligence import smart_search, build_follow_up_radar, build_decision_memory, build_tco_intelligence

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_ENSURE_ASCII"] = False
app.config["SECRET_KEY"] = os.urandom(32).hex()

init_db(app)

# Machine verification on startup
if not verify_machine():
    print("SECURITY ERROR: Machine fingerprint mismatch! This app is bound to a specific machine.")
    sys.exit(1)

with app.app_context():
    rebuild_index()


def _sync_deployment_log():
    """Import DEPLOYMENT_LOG.md entries into FutureDeployment table if not already present.
    All new entries start as bekliyor - user controls status manually via drag & drop."""
    entries = parse_deployment_log()
    for entry in entries:
        if not entry.get("task"):
            continue
        existing = FutureDeployment.query.filter_by(task=entry["task"], date=entry["date"]).first()
        if existing:
            continue
        fd = FutureDeployment(
            date=entry["date"],
            title=entry["title"],
            task=entry["task"],
            jira_url=entry.get("jira_url", ""),
            summary=entry.get("summary", ""),
            contacts=", ".join(entry.get("contacts", [])),
            status="bekliyor",
        )
        fd.repos = entry.get("repos", [])
        db.session.add(fd)
    db.session.commit()


with app.app_context():
    _sync_deployment_log()

init_scheduler(app)


# ─── Helpers ──────────────────────────────────────────────

def _log_activity(action, entity_type="", entity_id=None, description=""):
    entry = ActivityLog(action=action, entity_type=entity_type, entity_id=entity_id, description=description[:500])
    db.session.add(entry)
    db.session.commit()


def _next_deployment_day():
    today = date.today()
    for i in range(7):
        d = today + timedelta(days=i)
        if d.weekday() in (1, 3):  # Tue, Thu
            return d
    return today


def _is_deploy_day():
    return date.today().weekday() in (1, 3)


# ─── Animation Settings ──────────────────────────────────

ANIM_PAGES = [
    ("/", "Dashboard"),
    ("/upcoming-deployments", "Gelecek Deploy"),
    ("/deployments", "Deployments"),
    ("/repo-deployments", "Repo Stats"),
    ("/team-pulse", "Team Pulse"),
    ("/tasks", "Tasks"),
    ("/reminders", "Reminders"),
    ("/daily-notes", "Daily Notes"),
    ("/search", "Search"),
    ("/docs", "Docs"),
    ("/about", "Hakkinda"),
    ("/settings", "Settings"),
]

ANIM_DEFAULTS = {
    "anim_mode": "high",  # high | medium | low | off
    "anim_splash": "true",
    "anim_splash_interval_min": "30",
    "anim_transitions": "true",
    "anim_transition_chance": "45",
    "anim_page_boot": "true",
    "anim_page_reveal": "true",
    "anim_docs_scan": "true",
    "anim_idle_pulse": "true",
    "anim_pages_off": "",  # comma-separated paths
}


def _load_anim_settings():
    rows = Setting.query.filter(Setting.key.like("anim_%")).all()
    raw = {s.key: s.value for s in rows}
    out = {}
    for key, default in ANIM_DEFAULTS.items():
        out[key] = raw.get(key, default)
    return out


def _build_anim_config():
    s = _load_anim_settings()

    def is_true(v):
        return str(v).lower() == "true"

    def to_int(v, fallback):
        try:
            return int(v)
        except (TypeError, ValueError):
            return fallback

    mode = s["anim_mode"] if s["anim_mode"] in ("high", "medium", "low", "off") else "high"
    pages_off = [p.strip() for p in (s["anim_pages_off"] or "").split(",") if p.strip()]

    # mode dampens transition chance; "off" zeroes everything
    chance = to_int(s["anim_transition_chance"], 45)
    if mode == "off":
        chance = 0
    elif mode == "low":
        chance = min(chance, 10)
    elif mode == "medium":
        chance = min(chance, 25)

    return {
        "mode": mode,
        "splash": is_true(s["anim_splash"]) and mode != "off",
        "splash_interval_min": max(0, to_int(s["anim_splash_interval_min"], 30)),
        "transitions": is_true(s["anim_transitions"]) and mode != "off",
        "transition_chance": chance,
        "page_boot": is_true(s["anim_page_boot"]) and mode not in ("off", "low"),
        "page_reveal": is_true(s["anim_page_reveal"]) and mode != "off",
        "docs_scan": is_true(s["anim_docs_scan"]) and mode not in ("off", "low"),
        "idle_pulse": is_true(s["anim_idle_pulse"]) and mode not in ("off", "low"),
        "pages_off": pages_off,
    }


_ANIM_FALLBACK = {
    "mode": "high",
    "splash": True,
    "splash_interval_min": 30,
    "transitions": True,
    "transition_chance": 45,
    "page_boot": True,
    "page_reveal": True,
    "docs_scan": True,
    "idle_pulse": True,
    "pages_off": [],
}


@app.context_processor
def _inject_anim_config():
    try:
        cfg = _build_anim_config()
    except Exception:
        cfg = dict(_ANIM_FALLBACK)
    return {"anim_config": cfg}


# ─── Auth Guard ───────────────────────────────────────────

def _is_auth_required():
    """Auth gate is on by default; user can disable it from settings."""
    try:
        s = Setting.query.get("auth_required")
        if s and str(s.value).lower() == "false":
            return False
    except Exception:
        pass
    return True


@app.before_request
def _check_auth():
    from security import validate_session
    # Skip auth for login, logout, static files
    if request.path in ("/login", "/logout") or request.path.startswith("/static/"):
        return None
    # Boot status API is needed by login splash
    if request.path == "/api/boot-status":
        return None
    if not _is_auth_required():
        return None
    token = request.cookies.get("ys_session")
    if not validate_session(token, request.remote_addr):
        if request.path.startswith("/api/"):
            return (jsonify({"error": "unauthorized"}), 401)
        return redirect("/login")


# ─── Auth Pages ───────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    from flask import make_response
    if not _is_auth_required():
        return redirect("/")
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if verify_pin(pin):
            token = create_session(request.remote_addr)
            resp = make_response(redirect("/"))
            resp.set_cookie("ys_session", token, max_age=86400, httponly=True, samesite="Lax")
            _log_activity("login", "auth", description="Basarili giris")
            return resp
        _log_activity("login_failed", "auth", description="Basarisiz giris denemesi")
        return render_template("login.html", error="Yanlis PIN")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    from flask import make_response
    token = request.cookies.get("ys_session")
    if token:
        destroy_session(token)
    resp = make_response(redirect("/login"))
    resp.delete_cookie("ys_session")
    return resp


# ─── Pages ────────────────────────────────────────────────

@app.route("/")
def dashboard():
    today = date.today()
    next_deploy = _next_deployment_day()
    days_until = (next_deploy - today).days
    is_today = days_until == 0

    tasks_by_status = {}
    for s in ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]:
        tasks_by_status[s] = Task.query.filter_by(status=s).count()

    active_tasks = Task.query.filter(Task.status.in_(["TODO", "IN_PROGRESS", "IN_REVIEW"])).order_by(Task.updated_at.desc()).limit(10).all()

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
    today_reminders = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at >= today_start,
        Reminder.remind_at <= today_end,
    ).order_by(Reminder.remind_at).all()

    daily_note = DailyNote.query.filter_by(date=today).first()
    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()

    upcoming_deployments = FutureDeployment.query.filter_by(status="bekliyor").order_by(FutureDeployment.date.desc()).all()
    completed_deployments = FutureDeployment.query.filter_by(status="tamamlandi").order_by(FutureDeployment.completed_at.desc()).limit(5).all()
    all_deployments = FutureDeployment.query.all()

    # Mini chart: last 4 weeks with ids
    mini_chart = []
    for i in range(3, -1, -1):
        week_end = today - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)
        ws, we = week_start.isoformat(), week_end.isoformat()
        items = [f for f in all_deployments if ws <= f.date <= we]
        mini_chart.append({
            "label": week_start.strftime("%d %b"),
            "count": len(items),
            "ids": [f.id for f in items],
        })

    # Repo breakdown
    repo_counts = defaultdict(int)
    for fd in all_deployments:
        for r in fd.repos:
            repo_counts[r.get("name", "?")] += 1
    top_repos = sorted(repo_counts.items(), key=lambda x: -x[1])[:5]

    # Index stats
    indexed_count = MdIndex.query.count()

    # Smart tips
    smart_tips = []
    bekliyor_count = len(upcoming_deployments)
    if is_today and bekliyor_count > 0:
        smart_tips.append({"icon": "!", "type": "warning", "text": f"Bugun deployment gunu ve {bekliyor_count} bekleyen deployment var!"})
    elif days_until == 1 and bekliyor_count > 0:
        smart_tips.append({"icon": "!", "type": "warning", "text": f"Yarin deployment gunu. {bekliyor_count} deployment bekliyor."})

    no_test_merge = []
    for fd in upcoming_deployments:
        for r in fd.repos:
            if r.get("test_merge") in ("Yapilmadi", "Bilinmiyor", "Teyit Bekliyor"):
                no_test_merge.append(f"{fd.task} ({r.get('name', '?')})")
    if no_test_merge:
        smart_tips.append({"icon": "?", "type": "info", "text": f"Test branch merge eksik: {', '.join(no_test_merge[:3])}"})

    if not (daily_note and daily_note.content):
        smart_tips.append({"icon": "~", "type": "neutral", "text": "Bugunun daily note'u henuz yazilmadi."})

    overdue_reminders = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at < today_start,
    ).count()
    if overdue_reminders:
        smart_tips.append({"icon": "!", "type": "warning", "text": f"{overdue_reminders} gecmis hatirlatma bekliyor."})

    day_names_tr = {0: "Pazartesi", 1: "Sali", 2: "Carsamba", 3: "Persembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}

    return render_template("dashboard.html",
        next_deploy=next_deploy,
        next_deploy_day=day_names_tr.get(next_deploy.weekday(), ""),
        days_until=days_until,
        is_deploy_today=is_today,
        tasks_by_status=tasks_by_status,
        active_tasks=active_tasks,
        today_reminders=today_reminders,
        daily_note=daily_note,
        recent_activity=recent_activity,
        upcoming_deployments=upcoming_deployments,
        completed_deployments=completed_deployments,
        mini_chart=mini_chart,
        top_repos=top_repos,
        indexed_count=indexed_count,
        smart_tips=smart_tips,
        today=today,
    )


@app.route("/deployments")
def deployments():
    completed = FutureDeployment.query.filter_by(status="tamamlandi").order_by(FutureDeployment.completed_at.desc()).all()
    filter_date = request.args.get("date", "")
    filter_month = request.args.get("month", "")
    if filter_date:
        completed = [c for c in completed if c.date == filter_date]
    elif filter_month:
        completed = [c for c in completed if c.date[:7] == filter_month]

    # Group by year-month for sidebar
    month_groups = defaultdict(int)
    all_completed = FutureDeployment.query.filter_by(status="tamamlandi").all()
    for c in all_completed:
        ym = c.date[:7]
        month_groups[ym] += 1
    month_groups = sorted(month_groups.items(), key=lambda x: x[0], reverse=True)

    return render_template("deployments.html",
        completed_deployments=completed,
        month_groups=month_groups,
        filter_date=filter_date,
        filter_month=filter_month,
        is_deploy_today=_is_deploy_day())


@app.route("/deployment/<int:fd_id>")
def deployment_detail(fd_id):
    fd = FutureDeployment.query.get_or_404(fd_id)
    return render_template("deployment_detail.html", fd=fd)


@app.route("/repo-deployments")
def repo_deployments():
    repo_name = request.args.get("repo", "")
    all_fd = FutureDeployment.query.order_by(FutureDeployment.date.desc()).all()

    if repo_name:
        filtered = [fd for fd in all_fd if any(r.get("name", "") == repo_name for r in fd.repos)]
    else:
        filtered = all_fd

    # Build repo list with counts
    repo_counts = defaultdict(int)
    for fd in all_fd:
        for r in fd.repos:
            repo_counts[r.get("name", "?")] += 1
    repo_list = sorted(repo_counts.items(), key=lambda x: -x[1])

    return render_template("repo_deployments.html",
        deployments=filtered,
        repo_name=repo_name,
        repo_list=repo_list)


@app.route("/upcoming-deployments")
def upcoming_deployments():
    _sync_deployment_log()
    upcoming = FutureDeployment.query.filter_by(status="bekliyor").order_by(FutureDeployment.date.desc()).all()
    completed = FutureDeployment.query.filter_by(status="tamamlandi").order_by(FutureDeployment.completed_at.desc()).limit(10).all()
    return render_template("upcoming_deployments.html", deployments=upcoming, completed=completed, is_deploy_today=_is_deploy_day())


@app.route("/tasks")
def tasks_board():
    all_tasks = Task.query.order_by(Task.sort_order, Task.updated_at.desc()).all()
    statuses = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE", "ARCHIVED"]
    columns = {s: [t for t in all_tasks if t.status == s] for s in statuses}
    return render_template("tasks.html", columns=columns, statuses=statuses)


@app.route("/reminders")
def reminders_page():
    status_filter = request.args.get("status", "active")
    q = Reminder.query
    if status_filter != "all":
        q = q.filter_by(status=status_filter)
    all_reminders = q.order_by(Reminder.remind_at).all()
    all_tasks = Task.query.filter(Task.status != "ARCHIVED").order_by(Task.title).all()
    return render_template("reminders.html", reminders=all_reminders, status_filter=status_filter, all_tasks=all_tasks)


@app.route("/daily-notes")
def daily_notes_page():
    notes = DailyNote.query.order_by(DailyNote.date.desc()).all()
    today = date.today()
    current_note = DailyNote.query.filter_by(date=today).first()
    selected_date = request.args.get("date", today.isoformat())
    if selected_date != today.isoformat():
        try:
            d = date.fromisoformat(selected_date)
            current_note = DailyNote.query.filter_by(date=d).first()
        except ValueError:
            pass
    return render_template("daily_notes.html", notes=notes, current_note=current_note, today=today, selected_date=selected_date)


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    results = []
    trace_results = []
    is_trace = False
    smart_summary = ""
    smart_tokens = []
    search_suggestions = []
    trace_target = ""

    if query:
        import re
        tco_match = re.match(r"^(TCO-\d+)$", query, re.IGNORECASE)
        if tco_match:
            is_trace = True
            trace_target = tco_match.group(1).upper()
            trace_results = trace_tco(trace_target)
        else:
            smart_result = smart_search(query, category if category else None)
            smart_summary = smart_result.get("summary", "")
            smart_tokens = smart_result.get("tokens", [])
            search_suggestions = smart_result.get("suggestions", [])
            if smart_result.get("trace_tco"):
                is_trace = True
                trace_target = smart_result["trace_tco"]
                trace_results = trace_tco(trace_target)
            else:
                results = smart_result.get("results", [])
    else:
        search_suggestions = smart_search("", None).get("suggestions", [])

    return render_template("search.html",
        query=query, results=results, trace_results=trace_results,
        is_trace=is_trace, category=category,
        category_colors=CATEGORY_COLORS, category_labels=CATEGORY_LABELS,
        smart_summary=smart_summary, smart_tokens=smart_tokens,
        search_suggestions=search_suggestions, trace_target=trace_target)


@app.route("/docs")
def docs_page():
    files = scan_md_files()
    tree = build_file_tree(files)
    selected = request.args.get("path", "")
    content_html = ""
    toc_html = ""
    selected_file = None

    if selected:
        full_path = os.path.join(get_workspace_root(), selected)
        if os.path.isfile(full_path) and full_path.endswith(".md"):
            content_html, toc_html = render_md(full_path)
            for f in files:
                if f["rel_path"] == selected:
                    selected_file = f
                    break

    return render_template("docs.html",
        files=files, tree=tree, selected=selected,
        content_html=content_html, toc_html=toc_html,
        selected_file=selected_file,
        category_colors=CATEGORY_COLORS, category_labels=CATEGORY_LABELS,
        pygments_css=get_pygments_css())


@app.route("/about")
def about_page():
    stats = {
        "indexed_files": MdIndex.query.count(),
        "deployments": FutureDeployment.query.count(),
        "bekliyor": FutureDeployment.query.filter_by(status="bekliyor").count(),
        "tamamlandi": FutureDeployment.query.filter_by(status="tamamlandi").count(),
        "tasks": Task.query.count(),
        "reminders": Reminder.query.count(),
        "daily_notes": DailyNote.query.count(),
        "activity_logs": ActivityLog.query.count(),
        "repos": len(set(
            r.get("name", "")
            for fd in FutureDeployment.query.all()
            for r in fd.repos
        )),
    }
    return render_template("about.html", stats=stats)


@app.route("/team-pulse")
def team_pulse_page():
    return render_template("team_pulse.html")


@app.route("/settings")
def settings_page():
    all_settings = {s.key: s.value for s in Setting.query.all()}
    anim_settings = _load_anim_settings()
    pages_off = [p.strip() for p in (anim_settings.get("anim_pages_off") or "").split(",") if p.strip()]
    workspace_info = {
        "default_root": PROJECTS_ROOT,
        "current_root": get_workspace_root(),
        "default_deployment_log": os.path.join(get_workspace_root(), "DEPLOYMENT_LOG.md"),
        "current_deployment_log": get_deployment_log_path(),
    }
    return render_template(
        "settings.html",
        settings=all_settings,
        anim_settings=anim_settings,
        anim_pages=ANIM_PAGES,
        anim_pages_off=pages_off,
        workspace_info=workspace_info,
    )


# ─── API: Tasks ───────────────────────────────────────────

@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.json
    task = Task(
        title=data.get("title", ""),
        description=data.get("description", ""),
        status=data.get("status", "TODO"),
        priority=data.get("priority", "medium"),
        category=data.get("category", "backend"),
        jira_url=data.get("jira_url", ""),
        mr_url=data.get("mr_url", ""),
        tco_number=data.get("tco_number", ""),
        deployment_date=date.fromisoformat(data["deployment_date"]) if data.get("deployment_date") else None,
    )
    db.session.add(task)
    db.session.commit()
    _log_activity("create", "task", task.id, f"Task olusturuldu: {task.title}")
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def api_update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.json

    old_status = task.status
    for field in ["title", "description", "status", "priority", "category", "jira_url", "mr_url", "tco_number", "sort_order"]:
        if field in data:
            setattr(task, field, data[field])
    if "deployment_date" in data:
        task.deployment_date = date.fromisoformat(data["deployment_date"]) if data["deployment_date"] else None
    task.updated_at = datetime.utcnow()
    db.session.commit()

    if old_status != task.status:
        _log_activity("status_change", "task", task.id, f"{task.title}: {old_status} -> {task.status}")
    else:
        _log_activity("update", "task", task.id, f"Task guncellendi: {task.title}")

    return jsonify(task.to_dict())


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    _log_activity("delete", "task", task.id, f"Task silindi: {task.title}")
    db.session.delete(task)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/tasks/reorder", methods=["POST"])
def api_reorder_tasks():
    data = request.json  # {"task_ids": [3, 1, 5], "status": "IN_PROGRESS"}
    task_ids = data.get("task_ids", [])
    status = data.get("status")
    for i, tid in enumerate(task_ids):
        task = Task.query.get(tid)
        if task:
            task.sort_order = i
            if status:
                task.status = status
            task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


# ─── API: Reminders ──────────────────────────────────────

@app.route("/api/reminders", methods=["POST"])
def api_create_reminder():
    data = request.json
    reminder = Reminder(
        note=data.get("note", ""),
        category=data.get("category", "genel"),
        remind_at=datetime.fromisoformat(data["remind_at"]),
        recurrence=data.get("recurrence", "once"),
        related_task_id=data.get("related_task_id") or None,
        priority=data.get("priority", "medium"),
    )
    db.session.add(reminder)
    db.session.commit()
    _log_activity("create", "reminder", reminder.id, f"Hatirlatma: {reminder.note[:80]}")
    return jsonify(reminder.to_dict()), 201


@app.route("/api/reminders/<int:rid>", methods=["PUT"])
def api_update_reminder(rid):
    reminder = Reminder.query.get_or_404(rid)
    data = request.json
    for field in ["note", "category", "recurrence", "status", "priority"]:
        if field in data:
            setattr(reminder, field, data[field])
    if "remind_at" in data:
        reminder.remind_at = datetime.fromisoformat(data["remind_at"])
    if "related_task_id" in data:
        reminder.related_task_id = data["related_task_id"] or None
    if data.get("status") == "active":
        reminder.notified = False
    db.session.commit()
    _log_activity("update", "reminder", reminder.id, f"Hatirlatma guncellendi: {reminder.note[:80]}")
    return jsonify(reminder.to_dict())


@app.route("/api/reminders/<int:rid>", methods=["DELETE"])
def api_delete_reminder(rid):
    reminder = Reminder.query.get_or_404(rid)
    _log_activity("delete", "reminder", reminder.id, f"Hatirlatma silindi: {reminder.note[:80]}")
    db.session.delete(reminder)
    db.session.commit()
    return jsonify({"ok": True})


# ─── API: Daily Notes ────────────────────────────────────

@app.route("/api/daily-notes", methods=["POST"])
def api_save_daily_note():
    data = request.json
    d = date.fromisoformat(data["date"])
    note = DailyNote.query.filter_by(date=d).first()
    if note:
        note.content = data.get("content", "")
        note.tags = data.get("tags", "")
        note.updated_at = datetime.utcnow()
    else:
        note = DailyNote(date=d, content=data.get("content", ""), tags=data.get("tags", ""))
        db.session.add(note)
    db.session.commit()
    _log_activity("save", "daily_note", note.id, f"Daily note: {d.isoformat()}")
    return jsonify(note.to_dict())


# ─── API: Settings ────────────────────────────────────────

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.json or {}

    # Detect changes that require a workspace re-scan.
    rescan_keys = {"workspace_root", "deployment_log_path"}
    rescan_needed = False
    for k in rescan_keys:
        if k not in data:
            continue
        existing = Setting.query.get(k)
        old_val = existing.value if existing else ""
        if str(data[k]) != str(old_val):
            rescan_needed = True
            break

    for k, v in data.items():
        setting = Setting.query.get(k)
        if setting:
            setting.value = str(v)
        else:
            db.session.add(Setting(key=k, value=str(v)))
    db.session.commit()

    rescan_summary = None
    if rescan_needed:
        rescan_summary = _rescan_workspace()

    return jsonify({"ok": True, "rescanned": rescan_needed, "summary": rescan_summary})


def _rescan_workspace():
    """Reset and rebuild the md index from the current workspace_root,
    then re-sync DEPLOYMENT_LOG into FutureDeployment."""
    MdIndex.query.delete()
    db.session.commit()
    summary = rebuild_index()
    try:
        _sync_deployment_log()
    except Exception:
        pass
    return summary


@app.route("/api/workspace/rescan", methods=["POST"])
def api_workspace_rescan():
    try:
        summary = _rescan_workspace()
        return jsonify({"ok": True, "summary": summary})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ─── API: Change PIN ─────────────────────────────────────

@app.route("/api/change-pin", methods=["POST"])
def api_change_pin():
    data = request.json
    new_pin = data.get("pin", "")
    if len(new_pin) < 4:
        return jsonify({"error": "PIN en az 4 karakter olmali"}), 400
    set_pin(new_pin)
    _log_activity("change_pin", "auth", description="PIN degistirildi")
    return jsonify({"ok": True})


# ─── API: Future Deployments ─────────────────────────────

@app.route("/api/future-deployments", methods=["POST"])
def api_create_future_deployment():
    data = request.json
    fd = FutureDeployment(
        date=data.get("date", ""),
        title=data.get("title", ""),
        task=data.get("task", ""),
        jira_url=data.get("jira_url", ""),
        summary=data.get("summary", ""),
        contacts=data.get("contacts", ""),
        status="bekliyor",
    )
    fd.repos = data.get("repos", [])
    db.session.add(fd)
    db.session.commit()
    _log_activity("create", "future_deployment", fd.id, f"Gelecek deployment: {fd.task} - {fd.title[:60]}")
    return jsonify(fd.to_dict()), 201


@app.route("/api/future-deployments/<int:fd_id>", methods=["PUT"])
def api_update_future_deployment(fd_id):
    fd = FutureDeployment.query.get_or_404(fd_id)
    data = request.json

    old_status = fd.status
    for field in ["date", "title", "task", "jira_url", "summary", "contacts"]:
        if field in data:
            setattr(fd, field, data[field])
    if "repos" in data:
        fd.repos = data["repos"]
    if "status" in data:
        fd.status = data["status"]
        if data["status"] == "tamamlandi" and old_status != "tamamlandi":
            fd.completed_at = datetime.utcnow()
        elif data["status"] == "bekliyor":
            fd.completed_at = None
    fd.updated_at = datetime.utcnow()
    db.session.commit()

    if old_status != fd.status:
        _log_activity("status_change", "future_deployment", fd.id, f"Deployment {fd.task}: {old_status} -> {fd.status}")
    else:
        _log_activity("update", "future_deployment", fd.id, f"Deployment guncellendi: {fd.task} - {fd.title[:60]}")

    return jsonify(fd.to_dict())


@app.route("/api/future-deployments/<int:fd_id>", methods=["DELETE"])
def api_delete_future_deployment(fd_id):
    fd = FutureDeployment.query.get_or_404(fd_id)
    _log_activity("delete", "future_deployment", fd.id, f"Deployment silindi: {fd.task} - {fd.title[:60]}")
    db.session.delete(fd)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/future-deployments/<int:fd_id>/markdown")
def api_future_deployment_markdown(fd_id):
    fd = FutureDeployment.query.get_or_404(fd_id)
    return jsonify({"markdown": fd.to_markdown()})


# ─── API: Index ───────────────────────────────────────────

@app.route("/api/index/rebuild", methods=["POST"])
def api_rebuild_index():
    stats = rebuild_index()
    stats["ok"] = True
    return jsonify(stats)


# ─── API: Deployment Markdown ────────────────────────────

@app.route("/api/deployment-markdown")
def api_deployment_markdown():
    task = request.args.get("task", "")
    deploy_date = request.args.get("date", "")
    entries = parse_deployment_log()
    for e in entries:
        if e["task"] == task and e["date"] == deploy_date:
            return jsonify({"markdown": e["raw"]})
    return jsonify({"markdown": ""}), 404


# ─── API: Deployment Stats ───────────────────────────────

@app.route("/api/deployment-stats")
def api_deployment_stats():
    range_type = request.args.get("range", "month")
    all_fd = FutureDeployment.query.all()
    today = date.today()
    data = []

    def _bucket(items, label):
        return {
            "label": label,
            "total": len(items),
            "bekliyor": len([f for f in items if f.status == "bekliyor"]),
            "tamamlandi": len([f for f in items if f.status == "tamamlandi"]),
            "ids": [f.id for f in items],
        }

    if range_type == "week":
        day_names = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            items = [f for f in all_fd if f.date == ds]
            data.append(_bucket(items, f"{day_names[d.weekday()]} {d.day}"))
    elif range_type == "month":
        for i in range(3, -1, -1):
            week_end = today - timedelta(weeks=i)
            week_start = week_end - timedelta(days=6)
            ws, we = week_start.isoformat(), week_end.isoformat()
            items = [f for f in all_fd if ws <= f.date <= we]
            data.append(_bucket(items, f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}"))
    elif range_type == "3month":
        from dateutil.relativedelta import relativedelta
        months_tr = ["Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]
        for i in range(2, -1, -1):
            m_date = today - relativedelta(months=i)
            m_start = m_date.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            ms, me = m_start.isoformat(), m_end.isoformat()
            items = [f for f in all_fd if ms <= f.date <= me]
            data.append(_bucket(items, f"{months_tr[m_start.month - 1]} {m_start.year}"))
    elif range_type == "year":
        from dateutil.relativedelta import relativedelta
        months_tr = ["Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]
        for i in range(11, -1, -1):
            m_date = today - relativedelta(months=i)
            m_start = m_date.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            ms, me = m_start.isoformat(), m_end.isoformat()
            items = [f for f in all_fd if ms <= f.date <= me]
            data.append(_bucket(items, months_tr[m_start.month - 1]))

    # Repo breakdown
    repo_counts = defaultdict(int)
    for fd in all_fd:
        for r in fd.repos:
            repo_counts[r.get("name", "?")] += 1
    top_repos = sorted(repo_counts.items(), key=lambda x: -x[1])[:8]

    return jsonify({
        "data": data,
        "summary": {
            "total": len(all_fd),
            "bekliyor": len([f for f in all_fd if f.status == "bekliyor"]),
            "tamamlandi": len([f for f in all_fd if f.status == "tamamlandi"]),
        },
        "repos": [{"name": n, "count": c} for n, c in top_repos],
    })


# ─── API: Deployment List by IDs ─────────────────────────

@app.route("/api/future-deployments/by-ids")
def api_deployments_by_ids():
    ids_str = request.args.get("ids", "")
    if not ids_str:
        return jsonify([])
    try:
        ids = [int(x) for x in ids_str.split(",") if x.strip()]
    except ValueError:
        return jsonify([])
    fds = FutureDeployment.query.filter(FutureDeployment.id.in_(ids)).order_by(FutureDeployment.date.desc()).all()
    return jsonify([fd.to_dict() for fd in fds])


# ─── API: Git Pulse ─────────────────────────────────────

@app.route("/api/git-pulse/sidebar")
def api_git_pulse_sidebar():
    refresh = request.args.get("refresh") == "1"
    return jsonify(build_sidebar_payload(force=refresh))


@app.route("/api/team-pulse")
def api_team_pulse():
    refresh = request.args.get("refresh") == "1"
    return jsonify(build_team_payload(force=refresh))


# ─── API: Intelligence ──────────────────────────────────

@app.route("/api/follow-up-radar")
def api_follow_up_radar():
    return jsonify(build_follow_up_radar())


@app.route("/api/decision-memory")
def api_decision_memory():
    tco = request.args.get("tco", "").strip()
    repo = request.args.get("repo", "").strip()
    tcos = [tco] if tco else None
    repos = [repo] if repo else None
    return jsonify(build_decision_memory(tcos=tcos, repos=repos))


@app.route("/api/tco-intelligence")
def api_tco_intelligence():
    tco = request.args.get("tco", "").strip()
    if not tco:
        return jsonify({"error": "tco is required"}), 400
    return jsonify(build_tco_intelligence(tco))


# ─── API: Smart Insights ─────────────────────────────────

@app.route("/api/smart-insights")
def api_smart_insights():
    today = date.today()
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    next_deploy = _next_deployment_day()
    days_until = (next_deploy - today).days
    is_today = days_until == 0

    upcoming = FutureDeployment.query.filter_by(status="bekliyor").all()
    all_fd = FutureDeployment.query.all()
    insights = []

    # ─── Deployment uyarıları
    bek_count = len(upcoming)
    if is_today and bek_count > 0:
        insights.append({"id": "deploy_today", "type": "critical", "category": "deployment",
            "title": "Bugun Deployment Gunu!",
            "text": f"{bek_count} deployment bekliyor. Hepsinin test merge durumunu kontrol et.",
            "action": "/upcoming-deployments"})
    elif days_until == 1 and bek_count > 0:
        insights.append({"id": "deploy_tomorrow", "type": "warning", "category": "deployment",
            "title": "Yarin Deployment",
            "text": f"{bek_count} deployment bekliyor. Hazirliklari tamamla.",
            "action": "/upcoming-deployments"})
    elif days_until <= 3 and bek_count > 0:
        day_names_tr = {0: "Pazartesi", 1: "Sali", 2: "Carsamba", 3: "Persembe", 4: "Cuma"}
        insights.append({"id": "deploy_soon", "type": "info", "category": "deployment",
            "title": f"Deployment {days_until} gun sonra ({day_names_tr.get(next_deploy.weekday(), '')})",
            "text": f"{bek_count} deployment bekliyor.",
            "action": "/upcoming-deployments"})

    # Test merge eksik
    no_merge = []
    for fd in upcoming:
        for r in fd.repos:
            tm = r.get("test_merge", "")
            if tm in ("Yapilmadi", "Bilinmiyor", "Teyit Bekliyor"):
                no_merge.append({"task": fd.task, "repo": r.get("name", "?"), "status": tm, "id": fd.id})
    if no_merge:
        names = ", ".join(f"{m['task']}({m['repo'].split('/')[-1]})" for m in no_merge[:4])
        insights.append({"id": "test_merge_missing", "type": "warning", "category": "deployment",
            "title": f"{len(no_merge)} repo'da test merge eksik",
            "text": names,
            "action": "/upcoming-deployments",
            "details": no_merge})

    # Uzun suredir bekleyen deployment
    for fd in upcoming:
        try:
            fd_date = date.fromisoformat(fd.date)
            age = (today - fd_date).days
            if age >= 7:
                insights.append({"id": f"stale_{fd.id}", "type": "info", "category": "deployment",
                    "title": f"{fd.task} {age} gundur bekliyor",
                    "text": fd.title,
                    "action": f"/deployment/{fd.id}"})
        except ValueError:
            pass

    # ─── Daily note
    daily_note = DailyNote.query.filter_by(date=today).first()
    if not (daily_note and daily_note.content):
        insights.append({"id": "daily_note", "type": "neutral", "category": "daily",
            "title": "Daily note yazilmadi",
            "text": "Bugunun notunu yazmaya ne dersin?",
            "action": "/daily-notes"})

    # ─── Hatirlatma
    overdue = Reminder.query.filter(Reminder.status == "active", Reminder.remind_at < today_start).all()
    if overdue:
        insights.append({"id": "overdue_reminders", "type": "warning", "category": "reminder",
            "title": f"{len(overdue)} gecmis hatirlatma",
            "text": ", ".join(r.note[:30] for r in overdue[:3]),
            "action": "/reminders"})

    upcoming_reminders = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at >= today_start,
        Reminder.remind_at <= datetime(now.year, now.month, now.day, 23, 59, 59),
    ).all()
    if upcoming_reminders:
        next_r = upcoming_reminders[0]
        insights.append({"id": "next_reminder", "type": "neutral", "category": "reminder",
            "title": f"Sonraki hatirlatma: {next_r.remind_at.strftime('%H:%M')}",
            "text": next_r.note[:60],
            "action": "/reminders"})

    # ─── Task
    in_review = Task.query.filter_by(status="IN_REVIEW").count()
    if in_review:
        insights.append({"id": "in_review", "type": "info", "category": "task",
            "title": f"{in_review} task review bekliyor",
            "text": "Review'deki tasklari kontrol et.",
            "action": "/tasks"})

    stale_tasks = Task.query.filter(
        Task.status.in_(["IN_PROGRESS", "TODO"]),
        Task.updated_at < datetime.utcnow() - timedelta(days=5),
    ).all()
    if stale_tasks:
        insights.append({"id": "stale_tasks", "type": "neutral", "category": "task",
            "title": f"{len(stale_tasks)} task 5+ gundur guncellenmedi",
            "text": ", ".join(t.title[:25] for t in stale_tasks[:3]),
            "action": "/tasks"})

    # ─── Haftalik ozet
    this_week_completed = len([f for f in all_fd if f.status == "tamamlandi" and f.completed_at and f.completed_at >= datetime.utcnow() - timedelta(days=7)])
    if this_week_completed:
        insights.append({"id": "week_summary", "type": "success", "category": "summary",
            "title": f"Bu hafta {this_week_completed} deployment tamamlandi",
            "text": "Harika is!",
            "action": "/deployments"})

    return jsonify(insights)


# ─── API: Boot Status ────────────────────────────────────

@app.route("/api/boot-status")
def api_boot_status():
    indexed = MdIndex.query.count()
    deployments = FutureDeployment.query.count()
    tasks = Task.query.count()
    reminders = Reminder.query.filter_by(status="active").count()
    notes = DailyNote.query.count()
    return jsonify({
        "indexed_files": indexed,
        "deployments": deployments,
        "tasks": tasks,
        "reminders": reminders,
        "daily_notes": notes,
    })


# ─── API: Search (JSON) ──────────────────────────────────

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    results = search_md(query, limit=20)
    return jsonify(results)


# ─── API: Restart ────────────────────────────────────────

@app.route("/api/restart", methods=["POST"])
def api_restart():
    def _restart():
        import time
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)
    import threading
    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({"ok": True})


# ─── Run ──────────────────────────────────────────────────

def _get_port():
    with app.app_context():
        setting = Setting.query.get("port")
        if setting and setting.value.isdigit():
            return int(setting.value)
    return PORT


if __name__ == "__main__":
    run_port = _get_port()
    app.run(host=HOST, port=run_port, debug=True, use_reloader=False)
