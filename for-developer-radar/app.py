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
from api_views import (
    boot_status as boot_status_api,
    change_pin as change_pin_api,
    create_future_deployment as create_future_deployment_api,
    create_reminder as create_reminder_api,
    create_task as create_task_api,
    decision_memory as decision_memory_api,
    delete_future_deployment as delete_future_deployment_api,
    delete_reminder as delete_reminder_api,
    delete_task as delete_task_api,
    delivery_radar as delivery_radar_api,
    deployment_markdown as deployment_markdown_api,
    deployment_stats as deployment_stats_api,
    deployments_by_ids as deployments_by_ids_api,
    follow_up_radar as follow_up_radar_api,
    future_deployment_markdown as future_deployment_markdown_api,
    git_pulse_sidebar as git_pulse_sidebar_api,
    rebuild_search_index as rebuild_search_index_api,
    reorder_tasks as reorder_tasks_api,
    restart_process as restart_process_api,
    save_daily_note as save_daily_note_api,
    save_settings as save_settings_api,
    search_api as search_api_json,
    smart_insights as smart_insights_api,
    tco_intelligence as tco_intelligence_api,
    team_pulse as team_pulse_api,
    update_future_deployment as update_future_deployment_api,
    update_reminder as update_reminder_api,
    update_task as update_task_api,
    workspace_rescan as workspace_rescan_api,
)
from page_views import (
    render_about_page,
    render_daily_notes_page,
    render_dashboard,
    render_deployment_detail,
    render_deployments,
    render_docs_page,
    render_reminders_page,
    render_repo_deployments,
    render_search_page,
    render_settings_page,
    render_tasks_board,
    render_delivery_radar_page,
    render_team_pulse_page,
    render_upcoming_deployments,
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_ENSURE_ASCII"] = False
app.config["SECRET_KEY"] = os.urandom(32).hex()

_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)
_UI_EFFECTS_ENABLED = False
try:
    import ui_effects  # shared animations package living next to fordeveloper
    app.register_blueprint(ui_effects.create_blueprint())
    _UI_EFFECTS_ENABLED = True
except Exception as exc:  # pragma: no cover
    print(f"[ui_effects] blueprint not registered: {exc}")

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
    ("/delivery-radar", "Delivery Radar"),
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
    return {"anim_config": cfg, "ui_effects_enabled": _UI_EFFECTS_ENABLED}


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


@app.route("/")
def dashboard():
    return render_dashboard(_next_deployment_day)


@app.route("/deployments")
def deployments():
    return render_deployments(_is_deploy_day)


@app.route("/deployment/<int:fd_id>")
def deployment_detail(fd_id):
    return render_deployment_detail(fd_id)


@app.route("/repo-deployments")
def repo_deployments():
    return render_repo_deployments()


@app.route("/upcoming-deployments")
def upcoming_deployments():
    return render_upcoming_deployments(_sync_deployment_log, _is_deploy_day)


@app.route("/tasks")
def tasks_board():
    return render_tasks_board()


@app.route("/reminders")
def reminders_page():
    return render_reminders_page()


@app.route("/daily-notes")
def daily_notes_page():
    return render_daily_notes_page()


@app.route("/search")
def search_page():
    return render_search_page()


@app.route("/docs")
def docs_page():
    return render_docs_page()


@app.route("/about")
def about_page():
    return render_about_page()


@app.route("/team-pulse")
def team_pulse_page():
    return render_team_pulse_page()


@app.route("/delivery-radar")
def delivery_radar_page():
    return render_delivery_radar_page()


@app.route("/settings")
def settings_page():
    return render_settings_page(_load_anim_settings, ANIM_PAGES)


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    return create_task_api(_log_activity)


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def api_update_task(task_id):
    return update_task_api(task_id, _log_activity)


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    return delete_task_api(task_id, _log_activity)


@app.route("/api/tasks/reorder", methods=["POST"])
def api_reorder_tasks():
    return reorder_tasks_api()


@app.route("/api/reminders", methods=["POST"])
def api_create_reminder():
    return create_reminder_api(_log_activity)


@app.route("/api/reminders/<int:rid>", methods=["PUT"])
def api_update_reminder(rid):
    return update_reminder_api(rid, _log_activity)


@app.route("/api/reminders/<int:rid>", methods=["DELETE"])
def api_delete_reminder(rid):
    return delete_reminder_api(rid, _log_activity)


@app.route("/api/daily-notes", methods=["POST"])
def api_save_daily_note():
    return save_daily_note_api(_log_activity)


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    return save_settings_api(_rescan_workspace)


@app.route("/api/workspace/rescan", methods=["POST"])
def api_workspace_rescan():
    return workspace_rescan_api(_rescan_workspace)


@app.route("/api/change-pin", methods=["POST"])
def api_change_pin():
    return change_pin_api(_log_activity)


@app.route("/api/future-deployments", methods=["POST"])
def api_create_future_deployment():
    return create_future_deployment_api(_log_activity)


@app.route("/api/future-deployments/<int:fd_id>", methods=["PUT"])
def api_update_future_deployment(fd_id):
    return update_future_deployment_api(fd_id, _log_activity)


@app.route("/api/future-deployments/<int:fd_id>", methods=["DELETE"])
def api_delete_future_deployment(fd_id):
    return delete_future_deployment_api(fd_id, _log_activity)


@app.route("/api/future-deployments/<int:fd_id>/markdown")
def api_future_deployment_markdown(fd_id):
    return future_deployment_markdown_api(fd_id)


@app.route("/api/index/rebuild", methods=["POST"])
def api_rebuild_index():
    return rebuild_search_index_api()


@app.route("/api/deployment-markdown")
def api_deployment_markdown():
    return deployment_markdown_api()


@app.route("/api/deployment-stats")
def api_deployment_stats():
    return deployment_stats_api()


@app.route("/api/future-deployments/by-ids")
def api_deployments_by_ids():
    return deployments_by_ids_api()


@app.route("/api/git-pulse/sidebar")
def api_git_pulse_sidebar():
    return git_pulse_sidebar_api()


@app.route("/api/team-pulse")
def api_team_pulse():
    return team_pulse_api()


@app.route("/api/delivery-radar")
def api_delivery_radar():
    return delivery_radar_api()


@app.route("/api/follow-up-radar")
def api_follow_up_radar():
    return follow_up_radar_api()


@app.route("/api/decision-memory")
def api_decision_memory():
    return decision_memory_api()


@app.route("/api/tco-intelligence")
def api_tco_intelligence():
    return tco_intelligence_api()


@app.route("/api/smart-insights")
def api_smart_insights():
    return smart_insights_api(_next_deployment_day)


@app.route("/api/boot-status")
def api_boot_status():
    return boot_status_api()


@app.route("/api/search")
def api_search():
    return search_api_json()


@app.route("/api/restart", methods=["POST"])
def api_restart():
    return restart_process_api()


# ─── Run ──────────────────────────────────────────────────

def _get_port():
    with app.app_context():
        setting = Setting.query.get("port")
        if setting and setting.value.isdigit():
            return int(setting.value)
    return PORT


if __name__ == "__main__":
    run_port = _get_port()
    app.run(host=HOST, port=run_port, debug=False, use_reloader=False)
