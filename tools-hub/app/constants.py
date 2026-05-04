from pathlib import Path

APP_NAME = "Tools Hub"
HUB_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = HUB_DIR.parent
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "ToolsHub"
STATE_FILE = SUPPORT_DIR / "state.json"
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".claude",
    "tools-hub",
}
