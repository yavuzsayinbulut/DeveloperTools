import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="TODO")  # TODO, IN_PROGRESS, IN_REVIEW, DONE, ARCHIVED
    priority = db.Column(db.String(10), default="medium")  # low, medium, high, critical
    category = db.Column(db.String(20), default="backend")  # backend, frontend, devops, hotfix, refactor, analysis
    jira_url = db.Column(db.String(500), default="")
    mr_url = db.Column(db.String(500), default="")
    tco_number = db.Column(db.String(20), default="")
    deployment_date = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "category": self.category,
            "jira_url": self.jira_url,
            "mr_url": self.mr_url,
            "tco_number": self.tco_number,
            "deployment_date": self.deployment_date.isoformat() if self.deployment_date else None,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Reminder(db.Model):
    __tablename__ = "reminders"
    id = db.Column(db.Integer, primary_key=True)
    note = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), default="genel")  # deployment, task, review, meeting, daily, genel
    remind_at = db.Column(db.DateTime, nullable=False)
    recurrence = db.Column(db.String(20), default="once")  # once, daily, weekdays, tue_thu, weekly, custom
    related_task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    status = db.Column(db.String(20), default="active")  # active, done, cancelled
    priority = db.Column(db.String(10), default="medium")
    notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    related_task = db.relationship("Task", backref="reminders", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "note": self.note,
            "category": self.category,
            "remind_at": self.remind_at.isoformat() if self.remind_at else None,
            "recurrence": self.recurrence,
            "related_task_id": self.related_task_id,
            "related_task_title": self.related_task.title if self.related_task else None,
            "status": self.status,
            "priority": self.priority,
            "notified": self.notified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DailyNote(db.Model):
    __tablename__ = "daily_notes"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    content = db.Column(db.Text, default="")
    tags = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MdIndex(db.Model):
    __tablename__ = "md_index"
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(500), unique=True, nullable=False)
    rel_path = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(20), default="proje")
    title = db.Column(db.String(300), default="")
    content = db.Column(db.Text, default="")
    tco_numbers = db.Column(db.String(500), default="")
    last_modified = db.Column(db.Float, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "file_path": self.file_path,
            "rel_path": self.rel_path,
            "category": self.category,
            "title": self.title,
            "tco_numbers": self.tco_numbers,
            "last_modified": self.last_modified,
        }


class ActivityLog(db.Model):
    __tablename__ = "activity_log"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(30), default="")
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FutureDeployment(db.Model):
    __tablename__ = "future_deployments"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    task = db.Column(db.String(20), default="")
    jira_url = db.Column(db.String(500), default="")
    summary = db.Column(db.Text, default="")
    contacts = db.Column(db.String(500), default="")
    repos_json = db.Column(db.Text, default="[]")
    status = db.Column(db.String(20), default="bekliyor")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def repos(self):
        try:
            return json.loads(self.repos_json) if self.repos_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @repos.setter
    def repos(self, value):
        self.repos_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "title": self.title,
            "task": self.task,
            "jira_url": self.jira_url,
            "summary": self.summary,
            "contacts": [c.strip() for c in self.contacts.split(",") if c.strip()] if self.contacts else [],
            "repos": self.repos,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_markdown(self):
        lines = [f"## {self.date} - {self.title}", ""]
        if self.task:
            lines.append(f"- Task: `{self.task}`")
        if self.jira_url:
            lines.append(f"- Jira: {self.jira_url}")
        if self.summary:
            lines.append(f"- Ozet: {self.summary}")
        repos = self.repos
        if repos:
            lines.append("- Repolar:")
            for repo in repos:
                lines.append(f"  - `{repo.get('name', '')}`:")
                if repo.get("mr_url"):
                    lines.append(f"    - MR: {repo['mr_url']}")
                if repo.get("branch"):
                    lines.append(f"    - Branch: `{repo['branch']}`")
                if repo.get("commit"):
                    lines.append(f"    - Commit: `{repo['commit']}`")
                if repo.get("test_merge"):
                    lines.append(f"    - Test Branch Merge: `{repo['test_merge']}`")
                if repo.get("test_note"):
                    lines.append(f"    - Test Branch Notu: {repo['test_note']}")
                if repo.get("detail"):
                    lines.append(f"    - Detay: {repo['detail']}")
        return "\n".join(lines)


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), default="")


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _seed_settings()


def _seed_settings():
    defaults = {
        "notification_hour": "9",
        "notification_minute": "0",
        "theme": "dark",
        "browser": "chrome",
        "daily_note_reminder": "true",
        "deployment_reminder": "true",
        "morning_briefing": "true",
    }
    for k, v in defaults.items():
        if not Setting.query.get(k):
            db.session.add(Setting(key=k, value=v))
    db.session.commit()
