from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import render_template, request

from config import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    PROJECTS_ROOT,
    get_deployment_log_path,
    get_workspace_root,
)
from intelligence import smart_search
from md_browser import build_file_tree, get_pygments_css, render_md, scan_md_files
from models import ActivityLog, DailyNote, FutureDeployment, MdIndex, Reminder, Setting, Task
from search_engine import trace_tco


def render_dashboard(next_deployment_day):
    today = date.today()
    next_deploy = next_deployment_day()
    days_until = (next_deploy - today).days
    is_today = days_until == 0

    tasks_by_status = {}
    for status in ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]:
        tasks_by_status[status] = Task.query.filter_by(status=status).count()

    active_tasks = (
        Task.query.filter(Task.status.in_(["TODO", "IN_PROGRESS", "IN_REVIEW"]))
        .order_by(Task.updated_at.desc())
        .limit(10)
        .all()
    )

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
    today_reminders = (
        Reminder.query.filter(
            Reminder.status == "active",
            Reminder.remind_at >= today_start,
            Reminder.remind_at <= today_end,
        )
        .order_by(Reminder.remind_at)
        .all()
    )

    daily_note = DailyNote.query.filter_by(date=today).first()
    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()

    upcoming_deployments = (
        FutureDeployment.query.filter_by(status="bekliyor").order_by(FutureDeployment.date.desc()).all()
    )
    completed_deployments = (
        FutureDeployment.query.filter_by(status="tamamlandi")
        .order_by(FutureDeployment.completed_at.desc())
        .limit(5)
        .all()
    )
    all_deployments = FutureDeployment.query.all()

    mini_chart = []
    for index in range(3, -1, -1):
        week_end = today - timedelta(weeks=index)
        week_start = week_end - timedelta(days=6)
        window_start, window_end = week_start.isoformat(), week_end.isoformat()
        items = [item for item in all_deployments if window_start <= item.date <= window_end]
        mini_chart.append(
            {
                "label": week_start.strftime("%d %b"),
                "count": len(items),
                "ids": [item.id for item in items],
            }
        )

    repo_counts = defaultdict(int)
    for deployment in all_deployments:
        for repo in deployment.repos:
            repo_counts[repo.get("name", "?")] += 1
    top_repos = sorted(repo_counts.items(), key=lambda item: -item[1])[:5]

    indexed_count = MdIndex.query.count()

    smart_tips = []
    bekliyor_count = len(upcoming_deployments)
    if is_today and bekliyor_count > 0:
        smart_tips.append(
            {
                "icon": "!",
                "type": "warning",
                "text": f"Bugun deployment gunu ve {bekliyor_count} bekleyen deployment var!",
            }
        )
    elif days_until == 1 and bekliyor_count > 0:
        smart_tips.append(
            {
                "icon": "!",
                "type": "warning",
                "text": f"Yarin deployment gunu. {bekliyor_count} deployment bekliyor.",
            }
        )

    no_test_merge = []
    for deployment in upcoming_deployments:
        for repo in deployment.repos:
            if repo.get("test_merge") in ("Yapilmadi", "Bilinmiyor", "Teyit Bekliyor"):
                no_test_merge.append(f"{deployment.task} ({repo.get('name', '?')})")
    if no_test_merge:
        smart_tips.append(
            {
                "icon": "?",
                "type": "info",
                "text": f"Test branch merge eksik: {', '.join(no_test_merge[:3])}",
            }
        )

    if not (daily_note and daily_note.content):
        smart_tips.append({"icon": "~", "type": "neutral", "text": "Bugunun daily note'u henuz yazilmadi."})

    overdue_reminders = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at < today_start,
    ).count()
    if overdue_reminders:
        smart_tips.append(
            {
                "icon": "!",
                "type": "warning",
                "text": f"{overdue_reminders} gecmis hatirlatma bekliyor.",
            }
        )

    day_names_tr = {
        0: "Pazartesi",
        1: "Sali",
        2: "Carsamba",
        3: "Persembe",
        4: "Cuma",
        5: "Cumartesi",
        6: "Pazar",
    }

    return render_template(
        "dashboard.html",
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


def render_deployments(is_deploy_day):
    completed = (
        FutureDeployment.query.filter_by(status="tamamlandi")
        .order_by(FutureDeployment.completed_at.desc())
        .all()
    )
    filter_date = request.args.get("date", "")
    filter_month = request.args.get("month", "")
    if filter_date:
        completed = [item for item in completed if item.date == filter_date]
    elif filter_month:
        completed = [item for item in completed if item.date[:7] == filter_month]

    month_groups = defaultdict(int)
    all_completed = FutureDeployment.query.filter_by(status="tamamlandi").all()
    for item in all_completed:
        year_month = item.date[:7]
        month_groups[year_month] += 1
    ordered_groups = sorted(month_groups.items(), key=lambda item: item[0], reverse=True)

    return render_template(
        "deployments.html",
        completed_deployments=completed,
        month_groups=ordered_groups,
        filter_date=filter_date,
        filter_month=filter_month,
        is_deploy_today=is_deploy_day(),
    )


def render_deployment_detail(fd_id: int):
    deployment = FutureDeployment.query.get_or_404(fd_id)
    return render_template("deployment_detail.html", fd=deployment)


def render_repo_deployments():
    repo_name = request.args.get("repo", "")
    all_deployments = FutureDeployment.query.order_by(FutureDeployment.date.desc()).all()

    if repo_name:
        filtered = [
            deployment
            for deployment in all_deployments
            if any(repo.get("name", "") == repo_name for repo in deployment.repos)
        ]
    else:
        filtered = all_deployments

    repo_counts = defaultdict(int)
    for deployment in all_deployments:
        for repo in deployment.repos:
            repo_counts[repo.get("name", "?")] += 1
    repo_list = sorted(repo_counts.items(), key=lambda item: -item[1])

    return render_template(
        "repo_deployments.html",
        deployments=filtered,
        repo_name=repo_name,
        repo_list=repo_list,
    )


def render_upcoming_deployments(sync_deployment_log, is_deploy_day):
    sync_deployment_log()
    upcoming = (
        FutureDeployment.query.filter_by(status="bekliyor").order_by(FutureDeployment.date.desc()).all()
    )
    completed = (
        FutureDeployment.query.filter_by(status="tamamlandi")
        .order_by(FutureDeployment.completed_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "upcoming_deployments.html",
        deployments=upcoming,
        completed=completed,
        is_deploy_today=is_deploy_day(),
    )


def render_tasks_board():
    all_tasks = Task.query.order_by(Task.sort_order, Task.updated_at.desc()).all()
    statuses = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE", "ARCHIVED"]
    columns = {status: [task for task in all_tasks if task.status == status] for status in statuses}
    return render_template("tasks.html", columns=columns, statuses=statuses)


def render_reminders_page():
    status_filter = request.args.get("status", "active")
    query = Reminder.query
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    reminders = query.order_by(Reminder.remind_at).all()
    tasks = Task.query.filter(Task.status != "ARCHIVED").order_by(Task.title).all()
    return render_template(
        "reminders.html",
        reminders=reminders,
        status_filter=status_filter,
        all_tasks=tasks,
    )


def render_daily_notes_page():
    notes = DailyNote.query.order_by(DailyNote.date.desc()).all()
    today = date.today()
    current_note = DailyNote.query.filter_by(date=today).first()
    selected_date = request.args.get("date", today.isoformat())
    if selected_date != today.isoformat():
        try:
            selected = date.fromisoformat(selected_date)
            current_note = DailyNote.query.filter_by(date=selected).first()
        except ValueError:
            pass
    return render_template(
        "daily_notes.html",
        notes=notes,
        current_note=current_note,
        today=today,
        selected_date=selected_date,
    )


def render_search_page():
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

    return render_template(
        "search.html",
        query=query,
        results=results,
        trace_results=trace_results,
        is_trace=is_trace,
        category=category,
        category_colors=CATEGORY_COLORS,
        category_labels=CATEGORY_LABELS,
        smart_summary=smart_summary,
        smart_tokens=smart_tokens,
        search_suggestions=search_suggestions,
        trace_target=trace_target,
    )


def render_docs_page():
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
            for file_info in files:
                if file_info["rel_path"] == selected:
                    selected_file = file_info
                    break

    return render_template(
        "docs.html",
        files=files,
        tree=tree,
        selected=selected,
        content_html=content_html,
        toc_html=toc_html,
        selected_file=selected_file,
        category_colors=CATEGORY_COLORS,
        category_labels=CATEGORY_LABELS,
        pygments_css=get_pygments_css(),
    )


def render_about_page():
    stats = {
        "indexed_files": MdIndex.query.count(),
        "deployments": FutureDeployment.query.count(),
        "bekliyor": FutureDeployment.query.filter_by(status="bekliyor").count(),
        "tamamlandi": FutureDeployment.query.filter_by(status="tamamlandi").count(),
        "tasks": Task.query.count(),
        "reminders": Reminder.query.count(),
        "daily_notes": DailyNote.query.count(),
        "activity_logs": ActivityLog.query.count(),
        "repos": len(
            set(
                repo.get("name", "")
                for deployment in FutureDeployment.query.all()
                for repo in deployment.repos
            )
        ),
    }
    return render_template("about.html", stats=stats)


def render_team_pulse_page():
    return render_template("team_pulse.html")


def render_delivery_radar_page():
    return render_template("delivery_radar.html")


def render_settings_page(load_anim_settings, anim_pages):
    all_settings = {setting.key: setting.value for setting in Setting.query.all()}
    anim_settings = load_anim_settings()
    pages_off = [
        page.strip()
        for page in (anim_settings.get("anim_pages_off") or "").split(",")
        if page.strip()
    ]
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
        anim_pages=anim_pages,
        anim_pages_off=pages_off,
        workspace_info=workspace_info,
    )
