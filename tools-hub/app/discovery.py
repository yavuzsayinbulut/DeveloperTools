from __future__ import annotations

from pathlib import Path
from typing import List

from .constants import IGNORED_DIRS, TOOLS_DIR
from .models import DiscoveredApp
from .utils import detect_url_from_config, parse_readme, slugify


def discover_apps() -> List[DiscoveredApp]:
    apps: List[DiscoveredApp] = []

    for child in sorted(TOOLS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in IGNORED_DIRS:
            continue

        discovered = _discover_app(child)
        if discovered:
            apps.append(discovered)

    return apps


def _discover_app(app_dir: Path) -> DiscoveredApp | None:
    start_script = app_dir / "start.command"
    stop_script = app_dir / "stop.command"
    main_py = app_dir / "main.py"
    app_py = app_dir / "app.py"
    package_json = app_dir / "package.json"
    root_python = TOOLS_DIR / ".venv" / "bin" / "python"
    local_python = app_dir / "venv" / "bin" / "python"

    has_identity = any(
        path.exists() for path in (start_script, main_py, app_py, package_json)
    )
    if not has_identity:
        return None

    readme_candidates = sorted(app_dir.glob("README*"))
    readme_path = readme_candidates[0] if readme_candidates else None
    name, description, readme_url = (
        parse_readme(readme_path)
        if readme_path is not None
        else (app_dir.name, "", "")
    )

    start_mode = "manual"
    start_command: List[str] = []
    app_type = "utility"

    if start_script.exists():
        start_mode = "start.command"
        start_command = ["/bin/zsh", "start.command"]
    elif app_py.exists() and local_python.exists():
        start_mode = "python app.py"
        start_command = [str(local_python), "app.py"]
    elif main_py.exists() and root_python.exists():
        start_mode = "python main.py"
        start_command = [str(root_python), "main.py"]
    elif package_json.exists():
        start_mode = "npm start"
        start_command = ["npm", "start"]

    if app_py.exists():
        app_type = "web"
    elif main_py.exists():
        app_type = "desktop"
    elif package_json.exists():
        app_type = "node"

    default_url = readme_url
    if not default_url:
        default_url = detect_url_from_config(app_dir / "config.py")

    log_paths = []
    candidate_logs = [
        app_dir / ".hub_logs" / "stdout.log",
        app_dir / ".hub_logs" / "stderr.log",
        app_dir / "data" / "app.log",
        app_dir / "data" / "error.log",
        app_dir / "launchd.out.log",
        app_dir / "launchd.err.log",
    ]
    for path in candidate_logs:
        if path.exists():
            log_paths.append(str(path))

    return DiscoveredApp(
        key=slugify(app_dir.name),
        name=name or app_dir.name,
        path=str(app_dir),
        app_type=app_type,
        start_mode=start_mode,
        start_command=start_command,
        start_script=str(start_script) if start_script.exists() else "",
        stop_script=str(stop_script) if stop_script.exists() else "",
        default_url=default_url,
        description=description,
        readme_path=str(readme_path) if readme_path is not None else "",
        log_paths=log_paths,
        metadata={
            "folder_name": app_dir.name,
            "has_start_script": start_script.exists(),
            "has_stop_script": stop_script.exists(),
        },
    )
