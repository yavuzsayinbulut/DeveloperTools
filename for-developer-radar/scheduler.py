from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


scheduler = BackgroundScheduler(daemon=True)


def init_scheduler(app):
    """Initialize and start the background scheduler."""

    def _check_reminders():
        with app.app_context():
            from models import db, Reminder
            from notifier import send_reminder_notification

            now = datetime.utcnow()
            window = now + timedelta(minutes=1)

            pending = Reminder.query.filter(
                Reminder.status == "active",
                Reminder.notified == False,
                Reminder.remind_at <= window,
            ).all()

            for r in pending:
                send_reminder_notification(r)
                r.notified = True

                if r.recurrence == "once":
                    r.status = "done"
                else:
                    r.notified = False
                    r.remind_at = _next_occurrence(r.remind_at, r.recurrence)

            db.session.commit()

    def _deployment_check():
        with app.app_context():
            now = datetime.now()
            if now.weekday() not in (1, 3):  # Tuesday=1, Thursday=3
                return
            from parser import parse_deployment_log
            from notifier import send_deployment_reminder
            entries = parse_deployment_log()
            today_str = now.strftime("%Y-%m-%d")
            today_entries = [e for e in entries if e["date"] == today_str]
            send_deployment_reminder(today_entries if today_entries else entries[:3])

    def _morning_briefing():
        with app.app_context():
            from models import Task, Reminder
            from notifier import send_morning_briefing

            now = datetime.now()
            is_deploy = now.weekday() in (1, 3)
            active_tasks = Task.query.filter(Task.status.in_(["TODO", "IN_PROGRESS", "IN_REVIEW"])).count()
            today_reminders = Reminder.query.filter(
                Reminder.status == "active",
                Reminder.remind_at <= datetime(now.year, now.month, now.day, 23, 59, 59),
            ).count()
            send_morning_briefing(active_tasks, today_reminders, is_deploy)

    def _daily_note_reminder():
        with app.app_context():
            from models import DailyNote
            from notifier import send_daily_note_reminder
            from datetime import date

            today = date.today()
            note = DailyNote.query.filter_by(date=today).first()
            if not note or not note.content.strip():
                send_daily_note_reminder()

    def _reindex_and_sync():
        with app.app_context():
            from search_engine import rebuild_index
            rebuild_index()
            from git_activity import warm_git_activity_cache
            warm_git_activity_cache(force=True)
            # Sync DEPLOYMENT_LOG.md entries
            from parser import parse_deployment_log
            from models import db, FutureDeployment
            entries = parse_deployment_log()
            for entry in entries:
                if not entry.get("task"):
                    continue
                existing = FutureDeployment.query.filter_by(task=entry["task"], date=entry["date"]).first()
                if not existing:
                    fd = FutureDeployment(
                        date=entry["date"], title=entry["title"], task=entry["task"],
                        jira_url=entry.get("jira_url", ""), summary=entry.get("summary", ""),
                        contacts=", ".join(entry.get("contacts", [])), status="bekliyor",
                    )
                    fd.repos = entry.get("repos", [])
                    db.session.add(fd)
            db.session.commit()

    scheduler.add_job(_check_reminders, "interval", minutes=1, id="check_reminders", replace_existing=True)
    scheduler.add_job(_deployment_check, "cron", hour=9, minute=0, day_of_week="tue,thu", id="deployment_check", replace_existing=True)
    scheduler.add_job(_morning_briefing, "cron", hour=9, minute=0, id="morning_briefing", replace_existing=True)
    scheduler.add_job(_daily_note_reminder, "cron", hour=9, minute=30, id="daily_note_reminder", replace_existing=True)
    scheduler.add_job(_reindex_and_sync, "interval", minutes=30, id="reindex_and_sync", replace_existing=True)

    scheduler.start()


def _next_occurrence(current, recurrence):
    """Calculate next occurrence based on recurrence type."""
    if recurrence == "daily":
        return current + timedelta(days=1)
    elif recurrence == "weekdays":
        nxt = current + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt
    elif recurrence == "tue_thu":
        nxt = current + timedelta(days=1)
        while nxt.weekday() not in (1, 3):
            nxt += timedelta(days=1)
        return nxt
    elif recurrence == "weekly":
        return current + timedelta(weeks=1)
    return current + timedelta(days=1)
