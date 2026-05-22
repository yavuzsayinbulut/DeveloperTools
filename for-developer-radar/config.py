import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_WORKSPACE_ROOT = "/Users/yavuz.sayinbulut/Desktop/Finance"
DEPLOYMENT_LOG_PATH = os.path.join(PROJECTS_ROOT, "DEPLOYMENT_LOG.md")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "delivery_radar.db")

os.makedirs(DATA_DIR, exist_ok=True)


def _read_setting(key):
    """Read a Setting row safely. Returns None outside app context or on error."""
    try:
        from flask import has_app_context
        if not has_app_context():
            return None
        from models import Setting
        s = Setting.query.get(key)
        return s.value if s and s.value else None
    except Exception:
        return None


def get_workspace_root():
    """User-configurable workspace root (md scan + git scan + DEPLOYMENT_LOG dir).
    Falls back to PROJECTS_ROOT if unset / invalid."""
    raw = _read_setting("workspace_root")
    if raw:
        path = os.path.expanduser(raw)
        if os.path.isdir(path):
            return path
    if os.path.isdir(DEFAULT_WORKSPACE_ROOT):
        return DEFAULT_WORKSPACE_ROOT
    return PROJECTS_ROOT


def get_deployment_log_path():
    """Path to DEPLOYMENT_LOG.md. Honors explicit override; otherwise lives at
    {workspace_root}/DEPLOYMENT_LOG.md."""
    raw = _read_setting("deployment_log_path")
    if raw:
        path = os.path.expanduser(raw)
        if os.path.isfile(path):
            return path
    return os.path.join(get_workspace_root(), "DEPLOYMENT_LOG.md")

PORT = 5556
HOST = "127.0.0.1"

DEFAULT_NOTIFICATION_HOUR = 9
DEFAULT_NOTIFICATION_MINUTE = 0

MD_CATEGORIES = {
    "AGENTS.md": "rehber",
    "AGENTS-CHANGES.md": "degisiklik",
    "PROMPTING.md": "rehber",
    "DEPLOYMENT_LOG.md": "deployment",
    "CLAUDE.md": "rehber",
    "README.md": "proje",
    "TEMPLATE.md": "template",
    "DEVELOPMENT_TEMPLATE.md": "template",
    "CODE_REVIEW_TEMPLATE.md": "template",
    "MANUAL_TEST_TEMPLATE.md": "template",
}

def get_md_category(file_path):
    basename = os.path.basename(file_path)
    if basename in MD_CATEGORIES:
        return MD_CATEGORIES[basename]
    try:
        rel = os.path.relpath(file_path, get_workspace_root())
    except Exception:
        rel = os.path.relpath(file_path, PROJECTS_ROOT)
    if rel.startswith("tasks/"):
        return "task"
    if rel.startswith("docs/architecture"):
        return "mimari"
    if rel.startswith("docs/"):
        return "dokuman"
    if "AGENTS-CHANGES" in basename:
        return "degisiklik"
    if "AGENTS" in basename:
        return "rehber"
    return "proje"

CATEGORY_COLORS = {
    "rehber": "#6366f1",
    "degisiklik": "#f59e0b",
    "deployment": "#ef4444",
    "task": "#10b981",
    "mimari": "#8b5cf6",
    "dokuman": "#3b82f6",
    "template": "#6b7280",
    "proje": "#06b6d4",
}

CATEGORY_LABELS = {
    "rehber": "Rehber",
    "degisiklik": "Degisiklik Kaydi",
    "deployment": "Deployment",
    "task": "Task",
    "mimari": "Mimari",
    "dokuman": "Dokuman",
    "template": "Template",
    "proje": "Proje",
}
