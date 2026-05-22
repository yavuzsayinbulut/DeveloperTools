from __future__ import annotations

import os
import signal
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import jsonify, request

from delivery_radar import build_delivery_radar
from git_activity import build_sidebar_payload, build_team_payload
from intelligence import (
    build_decision_memory,
    build_follow_up_radar,
    build_tco_intelligence,
    smart_search,
)
from models import DailyNote, FutureDeployment, MdIndex, Reminder, Setting, Task, db
from parser import parse_deployment_log
from search_engine import rebuild_index, search_md
from security import set_pin


def create_task(log_activity):
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
    log_activity("create", "task", task.id, f"Task olusturuldu: {task.title}")
    return jsonify(task.to_dict()), 201


def update_task(task_id: int, log_activity):
    task = Task.query.get_or_404(task_id)
    data = request.json

    old_status = task.status
    for field in [
        "title",
        "description",
        "status",
        "priority",
        "category",
        "jira_url",
        "mr_url",
        "tco_number",
        "sort_order",
    ]:
        if field in data:
            setattr(task, field, data[field])
    if "deployment_date" in data:
        task.deployment_date = date.fromisoformat(data["deployment_date"]) if data["deployment_date"] else None
    task.updated_at = datetime.utcnow()
    db.session.commit()

    if old_status != task.status:
        log_activity("status_change", "task", task.id, f"{task.title}: {old_status} -> {task.status}")
    else:
        log_activity("update", "task", task.id, f"Task guncellendi: {task.title}")

    return jsonify(task.to_dict())


def delete_task(task_id: int, log_activity):
    task = Task.query.get_or_404(task_id)
    log_activity("delete", "task", task.id, f"Task silindi: {task.title}")
    db.session.delete(task)
    db.session.commit()
    return jsonify({"ok": True})


def reorder_tasks():
    data = request.json
    task_ids = data.get("task_ids", [])
    status = data.get("status")
    for index, task_id in enumerate(task_ids):
        task = Task.query.get(task_id)
        if task:
            task.sort_order = index
            if status:
                task.status = status
            task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


def create_reminder(log_activity):
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
    log_activity("create", "reminder", reminder.id, f"Hatirlatma: {reminder.note[:80]}")
    return jsonify(reminder.to_dict()), 201


def update_reminder(reminder_id: int, log_activity):
    reminder = Reminder.query.get_or_404(reminder_id)
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
    log_activity("update", "reminder", reminder.id, f"Hatirlatma guncellendi: {reminder.note[:80]}")
    return jsonify(reminder.to_dict())


def delete_reminder(reminder_id: int, log_activity):
    reminder = Reminder.query.get_or_404(reminder_id)
    log_activity("delete", "reminder", reminder.id, f"Hatirlatma silindi: {reminder.note[:80]}")
    db.session.delete(reminder)
    db.session.commit()
    return jsonify({"ok": True})


def save_daily_note(log_activity):
    data = request.json
    note_date = date.fromisoformat(data["date"])
    note = DailyNote.query.filter_by(date=note_date).first()
    if note:
        note.content = data.get("content", "")
        note.tags = data.get("tags", "")
        note.updated_at = datetime.utcnow()
    else:
        note = DailyNote(date=note_date, content=data.get("content", ""), tags=data.get("tags", ""))
        db.session.add(note)
    db.session.commit()
    log_activity("save", "daily_note", note.id, f"Daily note: {note_date.isoformat()}")
    return jsonify(note.to_dict())


def save_settings(rescan_workspace):
    data = request.json or {}
    rescan_keys = {"workspace_root", "deployment_log_path"}
    rescan_needed = False
    for key in rescan_keys:
        if key not in data:
            continue
        existing = Setting.query.get(key)
        old_value = existing.value if existing else ""
        if str(data[key]) != str(old_value):
            rescan_needed = True
            break

    for key, value in data.items():
        setting = Setting.query.get(key)
        if setting:
            setting.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
    db.session.commit()

    rescan_summary = None
    if rescan_needed:
        rescan_summary = rescan_workspace()

    return jsonify({"ok": True, "rescanned": rescan_needed, "summary": rescan_summary})


def workspace_rescan(rescan_workspace):
    try:
        summary = rescan_workspace()
        return jsonify({"ok": True, "summary": summary})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def change_pin(log_activity):
    data = request.json
    new_pin = data.get("pin", "")
    if len(new_pin) < 4:
        return jsonify({"error": "PIN en az 4 karakter olmali"}), 400
    set_pin(new_pin)
    log_activity("change_pin", "auth", description="PIN degistirildi")
    return jsonify({"ok": True})


def create_future_deployment(log_activity):
    data = request.json
    deployment = FutureDeployment(
        date=data.get("date", ""),
        title=data.get("title", ""),
        task=data.get("task", ""),
        jira_url=data.get("jira_url", ""),
        summary=data.get("summary", ""),
        contacts=data.get("contacts", ""),
        status="bekliyor",
    )
    deployment.repos = data.get("repos", [])
    db.session.add(deployment)
    db.session.commit()
    log_activity(
        "create",
        "future_deployment",
        deployment.id,
        f"Gelecek deployment: {deployment.task} - {deployment.title[:60]}",
    )
    return jsonify(deployment.to_dict()), 201


def update_future_deployment(fd_id: int, log_activity):
    deployment = FutureDeployment.query.get_or_404(fd_id)
    data = request.json

    old_status = deployment.status
    for field in ["date", "title", "task", "jira_url", "summary", "contacts"]:
        if field in data:
            setattr(deployment, field, data[field])
    if "repos" in data:
        deployment.repos = data["repos"]
    if "status" in data:
        deployment.status = data["status"]
        if data["status"] == "tamamlandi" and old_status != "tamamlandi":
            deployment.completed_at = datetime.utcnow()
        elif data["status"] == "bekliyor":
            deployment.completed_at = None
    deployment.updated_at = datetime.utcnow()
    db.session.commit()

    if old_status != deployment.status:
        log_activity(
            "status_change",
            "future_deployment",
            deployment.id,
            f"Deployment {deployment.task}: {old_status} -> {deployment.status}",
        )
    else:
        log_activity(
            "update",
            "future_deployment",
            deployment.id,
            f"Deployment guncellendi: {deployment.task} - {deployment.title[:60]}",
        )

    return jsonify(deployment.to_dict())


def delete_future_deployment(fd_id: int, log_activity):
    deployment = FutureDeployment.query.get_or_404(fd_id)
    log_activity(
        "delete",
        "future_deployment",
        deployment.id,
        f"Deployment silindi: {deployment.task} - {deployment.title[:60]}",
    )
    db.session.delete(deployment)
    db.session.commit()
    return jsonify({"ok": True})


def future_deployment_markdown(fd_id: int):
    deployment = FutureDeployment.query.get_or_404(fd_id)
    return jsonify({"markdown": deployment.to_markdown()})


def rebuild_search_index():
    stats = rebuild_index()
    stats["ok"] = True
    return jsonify(stats)


def deployment_markdown():
    task = request.args.get("task", "")
    deploy_date = request.args.get("date", "")
    entries = parse_deployment_log()
    for entry in entries:
        if entry["task"] == task and entry["date"] == deploy_date:
            return jsonify({"markdown": entry["raw"]})
    return jsonify({"markdown": ""}), 404


def deployment_stats():
    range_type = request.args.get("range", "month")
    all_deployments = FutureDeployment.query.all()
    today = date.today()
    data = []

    def bucket(items, label):
        return {
            "label": label,
            "total": len(items),
            "bekliyor": len([item for item in items if item.status == "bekliyor"]),
            "tamamlandi": len([item for item in items if item.status == "tamamlandi"]),
            "ids": [item.id for item in items],
        }

    if range_type == "week":
        day_names = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        for index in range(6, -1, -1):
            item_date = today - timedelta(days=index)
            date_string = item_date.isoformat()
            items = [item for item in all_deployments if item.date == date_string]
            data.append(bucket(items, f"{day_names[item_date.weekday()]} {item_date.day}"))
    elif range_type == "month":
        for index in range(3, -1, -1):
            week_end = today - timedelta(weeks=index)
            week_start = week_end - timedelta(days=6)
            window_start, window_end = week_start.isoformat(), week_end.isoformat()
            items = [item for item in all_deployments if window_start <= item.date <= window_end]
            data.append(
                bucket(items, f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}")
            )
    elif range_type == "3month":
        from dateutil.relativedelta import relativedelta

        months_tr = ["Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]
        for index in range(2, -1, -1):
            month_date = today - relativedelta(months=index)
            month_start = month_date.replace(day=1)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
            window_start, window_end = month_start.isoformat(), month_end.isoformat()
            items = [item for item in all_deployments if window_start <= item.date <= window_end]
            data.append(bucket(items, f"{months_tr[month_start.month - 1]} {month_start.year}"))
    elif range_type == "year":
        from dateutil.relativedelta import relativedelta

        months_tr = ["Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]
        for index in range(11, -1, -1):
            month_date = today - relativedelta(months=index)
            month_start = month_date.replace(day=1)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
            window_start, window_end = month_start.isoformat(), month_end.isoformat()
            items = [item for item in all_deployments if window_start <= item.date <= window_end]
            data.append(bucket(items, months_tr[month_start.month - 1]))

    repo_counts = defaultdict(int)
    for deployment in all_deployments:
        for repo in deployment.repos:
            repo_counts[repo.get("name", "?")] += 1
    top_repos = sorted(repo_counts.items(), key=lambda item: -item[1])[:8]

    return jsonify(
        {
            "data": data,
            "summary": {
                "total": len(all_deployments),
                "bekliyor": len([item for item in all_deployments if item.status == "bekliyor"]),
                "tamamlandi": len([item for item in all_deployments if item.status == "tamamlandi"]),
            },
            "repos": [{"name": name, "count": count} for name, count in top_repos],
        }
    )


def deployments_by_ids():
    ids_str = request.args.get("ids", "")
    if not ids_str:
        return jsonify([])
    try:
        ids = [int(item) for item in ids_str.split(",") if item.strip()]
    except ValueError:
        return jsonify([])
    deployments = (
        FutureDeployment.query.filter(FutureDeployment.id.in_(ids))
        .order_by(FutureDeployment.date.desc())
        .all()
    )
    return jsonify([deployment.to_dict() for deployment in deployments])


def git_pulse_sidebar():
    refresh = request.args.get("refresh") == "1"
    return jsonify(build_sidebar_payload(force=refresh))


def team_pulse():
    refresh = request.args.get("refresh") == "1"
    return jsonify(build_team_payload(force=refresh))


def delivery_radar():
    refresh = request.args.get("refresh") == "1"
    days = request.args.get("days", "60")
    query = request.args.get("q", "")
    return jsonify(build_delivery_radar(days=days, query=query, force=refresh))


def follow_up_radar():
    return jsonify(build_follow_up_radar())


def decision_memory():
    tco = request.args.get("tco", "").strip()
    repo = request.args.get("repo", "").strip()
    tcos = [tco] if tco else None
    repos = [repo] if repo else None
    return jsonify(build_decision_memory(tcos=tcos, repos=repos))


def tco_intelligence():
    tco = request.args.get("tco", "").strip()
    if not tco:
        return jsonify({"error": "tco is required"}), 400
    return jsonify(build_tco_intelligence(tco))


def smart_insights(next_deployment_day):
    today = date.today()
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    next_deploy = next_deployment_day()
    days_until = (next_deploy - today).days
    is_today = days_until == 0

    upcoming = FutureDeployment.query.filter_by(status="bekliyor").all()
    all_deployments = FutureDeployment.query.all()
    insights = []

    bekliyor_count = len(upcoming)
    if is_today and bekliyor_count > 0:
        insights.append(
            {
                "id": "deploy_today",
                "type": "critical",
                "category": "deployment",
                "title": "Bugun Deployment Gunu!",
                "text": f"{bekliyor_count} deployment bekliyor. Hepsinin test merge durumunu kontrol et.",
                "action": "/upcoming-deployments",
            }
        )
    elif days_until == 1 and bekliyor_count > 0:
        insights.append(
            {
                "id": "deploy_tomorrow",
                "type": "warning",
                "category": "deployment",
                "title": "Yarin Deployment",
                "text": f"{bekliyor_count} deployment bekliyor. Hazirliklari tamamla.",
                "action": "/upcoming-deployments",
            }
        )
    elif days_until <= 3 and bekliyor_count > 0:
        day_names_tr = {0: "Pazartesi", 1: "Sali", 2: "Carsamba", 3: "Persembe", 4: "Cuma"}
        insights.append(
            {
                "id": "deploy_soon",
                "type": "info",
                "category": "deployment",
                "title": f"Deployment {days_until} gun sonra ({day_names_tr.get(next_deploy.weekday(), '')})",
                "text": f"{bekliyor_count} deployment bekliyor.",
                "action": "/upcoming-deployments",
            }
        )

    no_merge = []
    for deployment in upcoming:
        for repo in deployment.repos:
            merge_status = repo.get("test_merge", "")
            if merge_status in ("Yapilmadi", "Bilinmiyor", "Teyit Bekliyor"):
                no_merge.append(
                    {
                        "task": deployment.task,
                        "repo": repo.get("name", "?"),
                        "status": merge_status,
                        "id": deployment.id,
                    }
                )
    if no_merge:
        names = ", ".join(f"{item['task']}({item['repo'].split('/')[-1]})" for item in no_merge[:4])
        insights.append(
            {
                "id": "test_merge_missing",
                "type": "warning",
                "category": "deployment",
                "title": f"{len(no_merge)} repo'da test merge eksik",
                "text": names,
                "action": "/upcoming-deployments",
                "details": no_merge,
            }
        )

    for deployment in upcoming:
        try:
            deploy_date = date.fromisoformat(deployment.date)
            age = (today - deploy_date).days
            if age >= 7:
                insights.append(
                    {
                        "id": f"stale_{deployment.id}",
                        "type": "info",
                        "category": "deployment",
                        "title": f"{deployment.task} {age} gundur bekliyor",
                        "text": deployment.title,
                        "action": f"/deployment/{deployment.id}",
                    }
                )
        except ValueError:
            pass

    daily_note = DailyNote.query.filter_by(date=today).first()
    if not (daily_note and daily_note.content):
        insights.append(
            {
                "id": "daily_note",
                "type": "neutral",
                "category": "daily",
                "title": "Daily note yazilmadi",
                "text": "Bugunun notunu yazmaya ne dersin?",
                "action": "/daily-notes",
            }
        )

    overdue = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at < today_start,
    ).all()
    if overdue:
        insights.append(
            {
                "id": "overdue_reminders",
                "type": "warning",
                "category": "reminder",
                "title": f"{len(overdue)} gecmis hatirlatma",
                "text": ", ".join(reminder.note[:30] for reminder in overdue[:3]),
                "action": "/reminders",
            }
        )

    upcoming_reminders = Reminder.query.filter(
        Reminder.status == "active",
        Reminder.remind_at >= today_start,
        Reminder.remind_at <= datetime(now.year, now.month, now.day, 23, 59, 59),
    ).all()
    if upcoming_reminders:
        next_reminder = upcoming_reminders[0]
        insights.append(
            {
                "id": "next_reminder",
                "type": "neutral",
                "category": "reminder",
                "title": f"Sonraki hatirlatma: {next_reminder.remind_at.strftime('%H:%M')}",
                "text": next_reminder.note[:60],
                "action": "/reminders",
            }
        )

    in_review_count = Task.query.filter_by(status="IN_REVIEW").count()
    if in_review_count:
        insights.append(
            {
                "id": "in_review",
                "type": "info",
                "category": "task",
                "title": f"{in_review_count} task review bekliyor",
                "text": "Review'deki tasklari kontrol et.",
                "action": "/tasks",
            }
        )

    stale_tasks = Task.query.filter(
        Task.status.in_(["IN_PROGRESS", "TODO"]),
        Task.updated_at < datetime.utcnow() - timedelta(days=5),
    ).all()
    if stale_tasks:
        insights.append(
            {
                "id": "stale_tasks",
                "type": "neutral",
                "category": "task",
                "title": f"{len(stale_tasks)} task 5+ gundur guncellenmedi",
                "text": ", ".join(task.title[:25] for task in stale_tasks[:3]),
                "action": "/tasks",
            }
        )

    this_week_completed = len(
        [
            deployment
            for deployment in all_deployments
            if deployment.status == "tamamlandi"
            and deployment.completed_at
            and deployment.completed_at >= datetime.utcnow() - timedelta(days=7)
        ]
    )
    if this_week_completed:
        insights.append(
            {
                "id": "week_summary",
                "type": "success",
                "category": "summary",
                "title": f"Bu hafta {this_week_completed} deployment tamamlandi",
                "text": "Harika is!",
                "action": "/deployments",
            }
        )

    return jsonify(insights)


def boot_status():
    indexed = MdIndex.query.count()
    deployments = FutureDeployment.query.count()
    tasks = Task.query.count()
    reminders = Reminder.query.filter_by(status="active").count()
    notes = DailyNote.query.count()
    return jsonify(
        {
            "indexed_files": indexed,
            "deployments": deployments,
            "tasks": tasks,
            "reminders": reminders,
            "daily_notes": notes,
        }
    )


def search_api():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    results = search_md(query, limit=20)
    return jsonify(results)


def restart_process():
    def restart():
        import time

        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=restart, daemon=True).start()
    return jsonify({"ok": True})
