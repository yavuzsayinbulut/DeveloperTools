from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


URL_RE = re.compile(r"https?://[^\s)>'\"]+")
HOST_RE = re.compile(r'HOST\s*=\s*["\']([^"\']+)["\']')
PORT_RE = re.compile(r"PORT\s*=\s*(\d+)")


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "app"


def parse_readme(readme_path: Path) -> tuple[str, str, str]:
    if not readme_path.exists():
        return readme_path.parent.name, "", ""

    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    heading = readme_path.parent.name
    description_lines = []
    default_url = ""

    for line in lines:
        stripped = line.strip()
        if not heading and stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
        elif stripped.startswith("#") and heading == readme_path.parent.name:
            heading = stripped.lstrip("#").strip() or heading

        if not default_url:
            match = URL_RE.search(stripped)
            if match:
                default_url = match.group(0).rstrip(".,*_`)")

    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if capture and description_lines:
                break
            capture = True
            continue
        if capture and stripped:
            description_lines.append(stripped)
            if len(description_lines) >= 2:
                break

    description = " ".join(description_lines).strip()
    return heading or readme_path.parent.name, description, default_url


def detect_url_from_config(config_path: Path) -> str:
    if not config_path.exists():
        return ""

    text = config_path.read_text(encoding="utf-8", errors="ignore")
    host_match = HOST_RE.search(text)
    port_match = PORT_RE.search(text)
    if host_match and port_match:
        return f"http://{host_match.group(1)}:{port_match.group(1)}"
    return ""


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
        )
        stat = result.stdout.strip()
        if not stat:
            return False
        return "Z" not in stat
    except Exception:
        return True


def terminate_pid(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False


def kill_pid(pid: int | None, timeout_seconds: float = 1.5) -> tuple[bool, str]:
    if not pid:
        return False, "Gecerli bir PID girilmedi."
    if not is_pid_running(pid):
        return False, f"PID {pid} icin calisan surec bulunamadi."

    terminate_pid(pid)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_pid_running(pid):
            return True, f"PID {pid} kapatildi."
        time.sleep(0.15)

    try:
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception as exc:
            return False, f"PID {pid} zorla kapatilamadi: {exc}"

    time.sleep(0.1)
    if not is_pid_running(pid):
        return True, f"PID {pid} zorla kapatildi."
    return False, f"PID {pid} kapatilmadi."


def find_pids_by_port(port: int) -> list[int]:
    if port <= 0 or port > 65535:
        return []

    commands = [
        ["lsof", "-ti", f"tcp:{port}"],
        ["lsof", "-tiTCP:{0}".format(port), "-sTCP:LISTEN"],
    ]
    seen: set[int] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                seen.add(int(line))
    return sorted(seen)


def _pid_cwd(pid: int) -> str:
    if not pid or pid <= 0:
        return ""
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def find_pids_by_path(app_path: str, entrypoints: tuple[str, ...] = ("main.py", "app.py")) -> list[int]:
    if not app_path:
        return []
    pids: set[int] = set()
    own_pid = os.getpid()
    abs_app_path = os.path.abspath(app_path)

    for entrypoint in entrypoints:
        target = os.path.join(abs_app_path, entrypoint)
        if not os.path.exists(target):
            continue
        try:
            result = subprocess.run(
                ["pgrep", "-f", target],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        for line in result.stdout.split():
            value = line.strip()
            if not value.isdigit():
                continue
            value_int = int(value)
            if value_int == own_pid:
                continue
            pids.add(value_int)

    if pids:
        return sorted(pids)

    for bundle_executable in Path(abs_app_path).glob("dist/*.app/Contents/MacOS/*"):
        if not bundle_executable.is_file():
            continue
        try:
            result = subprocess.run(
                ["pgrep", "-f", str(bundle_executable)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        for line in result.stdout.split():
            value = line.strip()
            if not value.isdigit():
                continue
            value_int = int(value)
            if value_int == own_pid:
                continue
            pids.add(value_int)

    if pids:
        return sorted(pids)

    # Fallback: a process may have argv like "Python main.py" with the app
    # directory as cwd (typical for shell scripts that `cd` before exec).
    # We scan any python invoking main.py / app.py and match via lsof cwd.
    candidates: set[int] = set()
    for entrypoint in entrypoints:
        try:
            result = subprocess.run(
                ["pgrep", "-f", entrypoint],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        for line in result.stdout.split():
            value = line.strip()
            if value.isdigit():
                candidates.add(int(value))

    candidates.discard(own_pid)
    for pid in candidates:
        if _pid_cwd(pid) == abs_app_path:
            pids.add(pid)
    return sorted(pids)


def find_ports_by_pid(pid: int) -> list[int]:
    if not pid or pid <= 0:
        return []
    try:
        result = subprocess.run(
            ["lsof", "-a", "-nP", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    ports: set[int] = set()
    for line in result.stdout.splitlines():
        match = re.search(r":(\d{1,5})\s+\(LISTEN\)", line)
        if match:
            value = int(match.group(1))
            if 0 < value <= 65535:
                ports.add(value)
    return sorted(ports)


def describe_pid(pid: int) -> str:
    if not pid or pid <= 0:
        return ""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def kill_port(port: int) -> tuple[bool, str]:
    pids = find_pids_by_port(port)
    if not pids:
        return False, f"Port {port} icin surec bulunamadi."

    messages = []
    success_count = 0
    for pid in pids:
        ok, message = kill_pid(pid)
        messages.append(message)
        if ok:
            success_count += 1

    if success_count == len(pids):
        return True, f"Port {port} icin {len(pids)} surec kapatildi."
    if success_count > 0:
        return True, " | ".join(messages)
    return False, " | ".join(messages)


def activate_pid(pid: int | None) -> bool:
    if not pid:
        return False
    script = (
        'tell application "System Events" '
        f'to set frontmost of the first process whose unix id is {pid} to true'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def format_dt(value: str) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def tail_file(path: str, max_lines: int = 80) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    return "\n".join(lines[-max_lines:])


def is_url_reachable(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    try:
        with urlopen(url, timeout=1.4) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except URLError:
        return False
    except Exception:
        return False
