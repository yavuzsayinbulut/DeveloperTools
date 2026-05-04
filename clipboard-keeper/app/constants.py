from pathlib import Path

APP_NAME = "Clipboard Keeper Pro"
APP_ID = "com.yavuzsayinbulut.clipboardkeeperpro"
ROOT_DIR = Path(__file__).resolve().parent.parent
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "ClipboardKeeperPro"
DATA_FILE = SUPPORT_DIR / "state.json"
IMAGE_DIR = SUPPORT_DIR / "images"
DEFAULT_EXPORT_DIR = Path.home() / "Documents" / "Clipboard Keeper Exports"
LAUNCH_AGENT_PATH = (
    Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
)
