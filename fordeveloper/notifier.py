import subprocess
import platform
import shutil

BASE_URL = "http://127.0.0.1:5555"

_has_terminal_notifier = shutil.which("terminal-notifier") is not None


def send_notification(title, message, path=None):
    """Send macOS notification. Clicking opens the relevant page in browser."""
    if platform.system() != "Darwin":
        print(f"[NOTIFY] {title}: {message}")
        return

    url = BASE_URL + (path or "/")

    if _has_terminal_notifier:
        _send_terminal_notifier(title, message, url)
    else:
        _send_osascript(title, message)


def _send_terminal_notifier(title, message, url):
    try:
        subprocess.run([
            "terminal-notifier",
            "-title", title,
            "-message", message,
            "-open", url,
            "-sound", "default",
            "-group", "fordeveloper",
            "-appIcon", "",
        ], capture_output=True, timeout=5)
    except Exception as e:
        print(f"[NOTIFY ERROR] {e}")


def _send_osascript(title, message):
    message = message.replace('"', '\\"')
    title = title.replace('"', '\\"')
    script = f'display notification "{message}" with title "{title}" sound name "default"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception as e:
        print(f"[NOTIFY ERROR] {e}")


def send_deployment_reminder(entries):
    """Send deployment day notification - opens deployments page."""
    if not entries:
        send_notification(
            "Deployment Gunu",
            "Bugun deployment gunu! Henuz kayit yok.",
            "/deployments",
        )
        return

    count = len(entries)
    tasks = [e["task"] for e in entries if e["task"]]
    task_list = ", ".join(tasks[:5])
    msg = f"{count} kayit var. Task'lar: {task_list}"
    send_notification("Deployment Gunu", msg, "/deployments")


def send_reminder_notification(reminder):
    """Send reminder notification - opens reminders page."""
    path = "/reminders"
    if reminder.related_task_id:
        path = "/tasks"
    send_notification(
        f"Hatirlatma ({reminder.category})",
        reminder.note[:150],
        path,
    )


def send_morning_briefing(task_count, reminder_count, is_deploy_day):
    """Send morning summary - opens dashboard."""
    parts = []
    if is_deploy_day:
        parts.append("Bugun deployment gunu!")
    parts.append(f"{task_count} aktif task")
    parts.append(f"{reminder_count} hatirlatma")

    send_notification("Gunaydin", " | ".join(parts), "/")


def send_daily_note_reminder():
    """Send daily note reminder - opens daily notes page."""
    send_notification(
        "Daily Note",
        "Bugunun notunu yazmayi unutma!",
        "/daily-notes",
    )
