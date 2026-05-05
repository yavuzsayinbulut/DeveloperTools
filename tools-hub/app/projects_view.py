from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .state import HubState


ENVIRONMENTS: List[tuple[str, str]] = [
    ("local", "Local"),
    ("dev", "Dev"),
    ("stage", "Stage"),
    ("prod", "Prod"),
]

SERVICE_TYPES: List[tuple[str, str]] = [
    ("swagger", "Swagger"),
    ("hangfire", "Hangfire"),
]


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "project"


def _empty_service_map() -> Dict[str, str]:
    return {key: "" for key, _ in ENVIRONMENTS}


def _normalize_project(payload: Dict[str, object]) -> Dict[str, object]:
    name = str(payload.get("name") or "").strip() or "Yeni Proje"
    key = str(payload.get("key") or "").strip() or _slugify(name)
    source_path = str(payload.get("source_path") or "").strip()
    project_type = str(payload.get("project_type") or "").strip()
    services: Dict[str, Dict[str, str]] = {}
    raw_services = payload.get("services") if isinstance(payload.get("services"), dict) else {}
    for service_key, _ in SERVICE_TYPES:
        urls = _empty_service_map()
        raw = raw_services.get(service_key) if isinstance(raw_services, dict) else None
        if isinstance(raw, dict):
            for env_key, _ in ENVIRONMENTS:
                value = raw.get(env_key)
                if isinstance(value, str):
                    urls[env_key] = value.strip()
        # Backwards-compat: top-level swagger/hangfire dicts
        legacy = payload.get(service_key)
        if isinstance(legacy, dict):
            for env_key, _ in ENVIRONMENTS:
                value = legacy.get(env_key)
                if isinstance(value, str) and not urls[env_key]:
                    urls[env_key] = value.strip()
        services[service_key] = urls
    return {
        "key": key,
        "name": name,
        "source_path": source_path,
        "project_type": project_type,
        "services": services,
    }


# --- Folder scanning ---------------------------------------------------------

IGNORED_SCAN_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".vs",
    ".idea",
    ".vscode",
    ".gradle",
    ".cache",
    ".terraform",
    ".next",
    ".nuxt",
    ".dart_tool",
    "node_modules",
    "bower_components",
    "bin",
    "obj",
    "dist",
    "build",
    "out",
    "target",
    "vendor",
    "Pods",
    "DerivedData",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "packages",
    "TestResults",
    "coverage",
    "cmake-build-debug",
    "cmake-build-release",
}


def _prettify_folder_name(name: str) -> str:
    if "-" in name or "_" in name:
        cleaned = re.sub(r"[-_]+", " ", name).strip()
        return " ".join(part.capitalize() for part in cleaned.split() if part) or name
    return name


def _detect_dotnet_project(folder: Path) -> Optional[str]:
    candidates: List[Path] = []
    for ext in ("*.csproj", "*.fsproj", "*.vbproj"):
        candidates.extend(sorted(folder.glob(ext)))
    if not candidates:
        return None
    folder_lower = folder.name.lower()
    for project_file in candidates:
        if project_file.stem.lower() == folder_lower:
            return project_file.stem
    return candidates[0].stem


def _detect_node_project(folder: Path) -> Optional[str]:
    package_json = folder / "package.json"
    if not package_json.exists():
        return None
    try:
        data = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return _prettify_folder_name(folder.name)
    name = data.get("name") if isinstance(data, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip().split("/")[-1]
    return _prettify_folder_name(folder.name)


def _strip_xml_namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _detect_java_project(folder: Path) -> Optional[str]:
    pom = folder / "pom.xml"
    if pom.exists():
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(pom).getroot()
            best_name = ""
            best_artifact = ""
            for child in list(root):
                tag = _strip_xml_namespace(child.tag)
                if tag == "name" and child.text and not best_name:
                    best_name = child.text.strip()
                elif tag == "artifactId" and child.text and not best_artifact:
                    best_artifact = child.text.strip()
            if best_name:
                return best_name
            if best_artifact:
                return best_artifact
        except Exception:
            pass
        return _prettify_folder_name(folder.name)

    for gradle_marker in ("build.gradle.kts", "build.gradle"):
        if (folder / gradle_marker).exists():
            settings = folder / "settings.gradle.kts"
            if not settings.exists():
                settings = folder / "settings.gradle"
            if settings.exists():
                try:
                    text = settings.read_text(encoding="utf-8", errors="ignore")
                    match = re.search(r"rootProject\.name\s*=\s*['\"]([^'\"]+)['\"]", text)
                    if match:
                        return match.group(1).strip()
                except Exception:
                    pass
            return _prettify_folder_name(folder.name)
    return None


def _detect_go_project(folder: Path) -> Optional[str]:
    gomod = folder / "go.mod"
    if not gomod.exists():
        return None
    try:
        for line in gomod.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("module "):
                module = stripped[len("module ") :].strip().strip('"')
                if module:
                    last = module.split("/")[-1]
                    return last or module
    except Exception:
        pass
    return _prettify_folder_name(folder.name)


def _detect_php_project(folder: Path) -> Optional[str]:
    composer = folder / "composer.json"
    if composer.exists():
        try:
            data = json.loads(composer.read_text(encoding="utf-8", errors="ignore"))
            name = data.get("name") if isinstance(data, dict) else None
            if isinstance(name, str) and name.strip():
                return name.strip().split("/")[-1]
        except Exception:
            pass
        return _prettify_folder_name(folder.name)
    for marker in ("artisan", "wp-config.php", "index.php"):
        if (folder / marker).exists():
            return _prettify_folder_name(folder.name)
    return None


def _detect_python_project(folder: Path) -> Optional[str]:
    pyproject = folder / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"^\s*name\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return _prettify_folder_name(folder.name)
    markers = ("setup.py", "setup.cfg", "manage.py", "requirements.txt", "main.py", "app.py", "Pipfile")
    if any((folder / marker).exists() for marker in markers):
        return _prettify_folder_name(folder.name)
    return None


def _detect_local_url_dotnet(folder: Path) -> str:
    candidates = [
        folder / "Properties" / "launchSettings.json",
        folder / "launchSettings.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        profiles = data.get("profiles") if isinstance(data, dict) else None
        if not isinstance(profiles, dict):
            continue
        for profile in profiles.values():
            if not isinstance(profile, dict):
                continue
            urls = profile.get("applicationUrl")
            if not isinstance(urls, str):
                continue
            options = [u.strip() for u in urls.split(";") if u.strip()]
            https_first = next((u for u in options if u.startswith("https://")), None)
            if https_first:
                return https_first
            if options:
                return options[0]
    return ""


def _resolve_spring_port(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if not value:
        return ""
    if value.isdigit():
        return value
    match = re.match(r"\$\{[^:}]+:(\d+)\}", value)
    if match:
        return match.group(1)
    return ""


def _detect_local_url_java(folder: Path) -> str:
    properties = folder / "src" / "main" / "resources" / "application.properties"
    if properties.exists():
        try:
            text = properties.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        port = ""
        context = ""
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, raw_value = stripped.partition("=")
            key = key.strip()
            raw_value = raw_value.strip()
            if key == "server.port" and not port:
                port = _resolve_spring_port(raw_value)
            elif key in ("server.servlet.context-path", "server.context-path") and not context:
                context = raw_value.strip("'\"")
        if port:
            base = f"http://localhost:{port}"
            if context:
                if not context.startswith("/"):
                    context = "/" + context
                base += context.rstrip("/")
            return base
    return ""


def _detect_local_url_node(folder: Path) -> str:
    env_file = folder / ".env"
    if not env_file.exists():
        return ""
    try:
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, raw_value = stripped.partition("=")
            if key.strip().upper() == "PORT":
                value = raw_value.strip().strip('"').strip("'")
                if value.isdigit():
                    return f"http://localhost:{value}"
    except Exception:
        return ""
    return ""


def _detect_project_payload(folder: Path) -> Optional[Dict[str, object]]:
    name: Optional[str] = None
    project_type = ""
    base_url = ""

    dotnet_name = _detect_dotnet_project(folder)
    if dotnet_name:
        name = dotnet_name
        project_type = ".NET"
        base_url = _detect_local_url_dotnet(folder)

    if not name:
        java_name = _detect_java_project(folder)
        if java_name:
            name = java_name
            project_type = "Java"
            base_url = _detect_local_url_java(folder)

    if not name:
        node_name = _detect_node_project(folder)
        if node_name:
            name = node_name
            project_type = "Node"
            base_url = _detect_local_url_node(folder)

    if not name:
        go_name = _detect_go_project(folder)
        if go_name:
            name = go_name
            project_type = "Go"

    if not name:
        php_name = _detect_php_project(folder)
        if php_name:
            name = php_name
            project_type = "PHP"

    if not name:
        python_name = _detect_python_project(folder)
        if python_name:
            name = python_name
            project_type = "Python"

    if not name:
        return None

    swagger = {env: "" for env, _ in ENVIRONMENTS}
    hangfire = {env: "" for env, _ in ENVIRONMENTS}
    if base_url:
        trimmed = base_url.rstrip("/")
        swagger["local"] = f"{trimmed}/swagger"
        hangfire["local"] = f"{trimmed}/hangfire"

    return {
        "key": _slugify(name),
        "name": name,
        "source_path": str(folder),
        "project_type": project_type,
        "services": {"swagger": swagger, "hangfire": hangfire},
    }


def scan_directory(root: Path, max_depth: int = 6, max_results: int = 500) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    seen_paths: set[str] = set()

    def walk(folder: Path, depth: int) -> None:
        if depth > max_depth or len(results) >= max_results:
            return
        try:
            children = sorted(folder.iterdir(), key=lambda item: item.name.lower())
        except (OSError, PermissionError):
            return
        for child in children:
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name in IGNORED_SCAN_DIRS:
                continue
            payload = _detect_project_payload(child)
            if payload:
                path_key = str(payload["source_path"])
                if path_key not in seen_paths:
                    seen_paths.add(path_key)
                    results.append(payload)
            walk(child, depth + 1)

    if root.is_dir():
        results_payload = _detect_project_payload(root)
        if results_payload:
            seen_paths.add(str(results_payload["source_path"]))
            results.append(results_payload)
        walk(root, 1)
    return results


class ProjectEditDialog(QDialog):
    def __init__(self, parent: QWidget, project: Optional[Dict[str, object]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Proje Duzenle" if project else "Yeni Proje")
        self.setMinimumWidth(640)
        self._fields: Dict[tuple[str, str], QLineEdit] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Proje adi ve ortamlara gore Swagger / Hangfire URL'lerini gir. "
            "Bos birakilan alanlar gizlenmez ama tiklayinca uyari verir."
        )
        info.setWordWrap(True)
        info.setObjectName("MutedLabel")
        layout.addWidget(info)

        name_row = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ornek: Customer API")
        name_row.addRow("Proje Adi", self.name_input)
        layout.addLayout(name_row)

        for service_key, service_label in SERVICE_TYPES:
            section = QLabel(service_label)
            section.setObjectName("SectionLabel")
            layout.addWidget(section)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(8)
            for col, (env_key, env_label) in enumerate(ENVIRONMENTS):
                label = QLabel(env_label)
                label.setObjectName("MutedLabel")
                grid.addWidget(label, 0, col)

                editor = QLineEdit()
                editor.setPlaceholderText(self._placeholder_for(service_key, env_key))
                grid.addWidget(editor, 1, col)
                self._fields[(service_key, env_key)] = editor
            layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgec")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if project:
            self._load_project(project)

    @staticmethod
    def _placeholder_for(service_key: str, env_key: str) -> str:
        if service_key == "swagger" and env_key == "local":
            return "http://localhost:5001/swagger"
        if service_key == "swagger":
            return f"https://{env_key}-api.ornek.com/swagger"
        if service_key == "hangfire" and env_key == "local":
            return "http://localhost:5001/hangfire"
        return f"https://{env_key}-api.ornek.com/hangfire"

    def _load_project(self, project: Dict[str, object]) -> None:
        normalized = _normalize_project(project)
        self.name_input.setText(str(normalized["name"]))
        services = normalized["services"]
        if isinstance(services, dict):
            for (service_key, env_key), editor in self._fields.items():
                bucket = services.get(service_key)
                if isinstance(bucket, dict):
                    editor.setText(str(bucket.get(env_key, "")))

    def to_payload(self, existing_key: str = "") -> Dict[str, object]:
        services: Dict[str, Dict[str, str]] = {}
        for service_key, _ in SERVICE_TYPES:
            services[service_key] = {
                env_key: self._fields[(service_key, env_key)].text().strip()
                for env_key, _ in ENVIRONMENTS
            }
        name = self.name_input.text().strip() or "Yeni Proje"
        key = existing_key or _slugify(name)
        return {"key": key, "name": name, "services": services}


class ProjectListItem(QFrame):
    def __init__(
        self,
        project: Dict[str, object],
        selected: bool,
        on_click: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.project = project
        self.on_click = on_click
        self.setObjectName("Card")
        self.setProperty("selected", selected)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        name = QLabel(str(project.get("name") or "Proje"))
        name.setStyleSheet("font-size: 14px; font-weight: 700;")
        name.setWordWrap(True)
        title_row.addWidget(name, 1)

        project_type = str(project.get("project_type") or "").strip()
        if project_type:
            type_badge = QLabel(project_type)
            type_badge.setObjectName("BadgeBlue")
            title_row.addWidget(type_badge, 0, Qt.AlignTop)
        layout.addLayout(title_row)

        services = project.get("services") if isinstance(project.get("services"), dict) else {}
        filled_envs: List[str] = []
        for env_key, env_label in ENVIRONMENTS:
            for service_key, _ in SERVICE_TYPES:
                bucket = services.get(service_key) if isinstance(services, dict) else None
                if isinstance(bucket, dict) and bucket.get(env_key):
                    if env_label not in filled_envs:
                        filled_envs.append(env_label)
                    break
        meta = QLabel(" / ".join(filled_envs) if filled_envs else "URL eklenmemis")
        meta.setObjectName("MutedLabel")
        layout.addWidget(meta)

        source_path = str(project.get("source_path") or "")
        if source_path:
            display = source_path
            home = str(Path.home())
            if display.startswith(home):
                display = "~" + display[len(home):]
            source = QLabel(display)
            source.setObjectName("MutedLabel")
            source.setStyleSheet("font-size: 11px; color: #8a93a8;")
            source.setWordWrap(True)
            layout.addWidget(source)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        key = str(self.project.get("key") or "")
        if key:
            self.on_click(key)


class ProjectsView(QWidget):
    def __init__(self, state: HubState) -> None:
        super().__init__()
        self.state = state
        self.projects: List[Dict[str, object]] = []
        self.selected_key: str = self.state.get_projects_window().get("selected_key", "")
        self._build()
        self.reload()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        outer.addWidget(splitter, 1)

        # Left: project list
        left = QFrame()
        left.setObjectName("Surface")
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 18, 18, 14)
        left_layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title = QLabel("Projeler")
        title.setObjectName("SectionLabel")
        header_row.addWidget(title)
        header_row.addStretch()

        scan_button = QPushButton("Klasör Tara")
        scan_button.clicked.connect(self.scan_folder)
        scan_button.setCursor(Qt.PointingHandCursor)
        header_row.addWidget(scan_button)

        add_button = QPushButton("Yeni Proje")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self.add_project)
        header_row.addWidget(add_button)
        left_layout.addLayout(header_row)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(10)
        self.list_scroll.setWidget(self.list_container)
        left_layout.addWidget(self.list_scroll, 1)

        splitter.addWidget(left)

        # Right: project detail
        right = QFrame()
        right.setObjectName("Surface")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(22, 22, 22, 22)
        right_layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.detail_title = QLabel("Proje Seç")
        self.detail_title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #0F172A; letter-spacing: -0.4px;"
        )
        title_row.addWidget(self.detail_title)

        self.detail_type_badge = QLabel("")
        self.detail_type_badge.setObjectName("BadgeIndigo")
        self.detail_type_badge.setVisible(False)
        title_row.addWidget(self.detail_type_badge, 0, Qt.AlignVCenter)

        title_row.addStretch()

        self.edit_button = QPushButton("Düzenle")
        self.edit_button.clicked.connect(self.edit_selected)
        title_row.addWidget(self.edit_button)

        self.delete_button = QPushButton("Sil")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.clicked.connect(self.delete_selected)
        title_row.addWidget(self.delete_button)

        right_layout.addLayout(title_row)

        self.detail_hint = QLabel("Soldan bir proje seç veya yeni proje ekle.")
        self.detail_hint.setObjectName("MutedLabel")
        self.detail_hint.setWordWrap(True)
        self.detail_hint.setStyleSheet("color: #64748B; font-size: 13px;")
        right_layout.addWidget(self.detail_hint)

        self.source_label = QLabel("")
        self.source_label.setObjectName("FaintLabel")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.source_label.setVisible(False)
        self.source_label.setStyleSheet(
            "color: #94A3B8; font-size: 11.5px; "
            "font-family: 'JetBrains Mono', 'SF Mono', 'Menlo', monospace;"
        )
        right_layout.addWidget(self.source_label)

        services_scroll = QScrollArea()
        services_scroll.setWidgetResizable(True)
        services_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        services_scroll.setFrameShape(QFrame.NoFrame)
        self.services_container = QWidget()
        self.services_layout = QVBoxLayout(self.services_container)
        self.services_layout.setContentsMargins(0, 4, 0, 0)
        self.services_layout.setSpacing(14)
        services_scroll.setWidget(self.services_container)
        right_layout.addWidget(services_scroll, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([320, 880])

    def reload(self) -> None:
        raw = self.state.get_projects()
        self.projects = [_normalize_project(item) for item in raw if isinstance(item, dict)]
        if self.projects and not any(p.get("key") == self.selected_key for p in self.projects):
            self.selected_key = str(self.projects[0]["key"])
            self.state.update_projects_window(selected_key=self.selected_key)
        self._render_list()
        self._render_detail()

    def _render_list(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.projects:
            empty = QLabel("Henuz bir proje eklenmedi. 'Yeni Proje' ile baslayabilirsin.")
            empty.setObjectName("MutedLabel")
            empty.setWordWrap(True)
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch()
            return

        for project in self.projects:
            key = str(project.get("key") or "")
            card = ProjectListItem(
                project=project,
                selected=key == self.selected_key,
                on_click=self.select_project,
            )
            self.list_layout.addWidget(card)
        self.list_layout.addStretch()

    def _render_detail(self) -> None:
        # Clear services
        while self.services_layout.count():
            item = self.services_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        project = self.get_selected_project()
        if not project:
            self.detail_title.setText("Proje Sec")
            self.detail_hint.setText("Soldan bir proje sec veya yeni proje ekle.")
            self.detail_hint.setVisible(True)
            self.source_label.setVisible(False)
            self.detail_type_badge.setVisible(False)
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return

        self.detail_title.setText(str(project.get("name") or "Proje"))
        self.detail_hint.setVisible(False)
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)

        project_type = str(project.get("project_type") or "").strip()
        if project_type:
            self.detail_type_badge.setText(project_type)
            self.detail_type_badge.setVisible(True)
        else:
            self.detail_type_badge.setVisible(False)

        source_path = str(project.get("source_path") or "")
        if source_path:
            display = source_path
            home = str(Path.home())
            if display.startswith(home):
                display = "~" + display[len(home):]
            self.source_label.setText(f"Kaynak: {display}")
            self.source_label.setVisible(True)
        else:
            self.source_label.setVisible(False)

        services = project.get("services") if isinstance(project.get("services"), dict) else {}
        for service_key, service_label in SERVICE_TYPES:
            section = QFrame()
            section.setObjectName("Card")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(18, 16, 18, 14)
            section_layout.setSpacing(10)

            head_row = QHBoxLayout()
            head = QLabel(service_label)
            head.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #0F172A; letter-spacing: -0.1px;"
            )
            head_row.addWidget(head)
            head_row.addStretch()

            bucket = services.get(service_key) if isinstance(services, dict) else None
            filled = sum(
                1
                for env_key, _ in ENVIRONMENTS
                if isinstance(bucket, dict) and bucket.get(env_key)
            )
            count_label = QLabel(f"{filled}/{len(ENVIRONMENTS)} ortam")
            count_label.setObjectName("FaintLabel")
            count_label.setStyleSheet("color: #94A3B8; font-size: 11.5px; font-weight: 500;")
            head_row.addWidget(count_label)
            section_layout.addLayout(head_row)

            divider = QFrame()
            divider.setObjectName("SectionDivider")
            section_layout.addWidget(divider)

            for env_key, env_label in ENVIRONMENTS:
                row_widget = QFrame()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 4, 0, 4)
                row.setSpacing(12)

                badge = QLabel(env_label)
                badge.setObjectName("BadgeIndigo" if env_key == "local" else "BadgeGray")
                badge.setFixedWidth(64)
                badge.setAlignment(Qt.AlignCenter)
                row.addWidget(badge)

                url_value = ""
                if isinstance(bucket, dict):
                    url_value = str(bucket.get(env_key) or "")

                preview = QLabel(url_value or "—")
                preview.setWordWrap(False)
                preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
                if url_value:
                    preview.setStyleSheet(
                        "color: #1F2937; font-size: 12.5px; "
                        "font-family: 'JetBrains Mono', 'SF Mono', 'Menlo', monospace;"
                    )
                else:
                    preview.setStyleSheet(
                        "color: #C9CFDB; font-size: 12.5px; font-style: italic;"
                    )
                preview.setMinimumWidth(0)
                row.addWidget(preview, 1)

                open_button = QPushButton("Aç")
                open_button.setEnabled(bool(url_value))
                if url_value:
                    open_button.setObjectName("PrimaryButton")
                open_button.setCursor(Qt.PointingHandCursor)
                open_button.setFixedWidth(64)
                if url_value:
                    open_button.clicked.connect(
                        lambda _checked=False, url=url_value: QDesktopServices.openUrl(QUrl(url))
                    )
                row.addWidget(open_button)

                copy_button = QPushButton("Kopyala")
                copy_button.setEnabled(bool(url_value))
                copy_button.setCursor(Qt.PointingHandCursor)
                copy_button.setFixedWidth(80)
                copy_button.clicked.connect(
                    lambda _checked=False, url=url_value: self._copy_to_clipboard(url)
                )
                row.addWidget(copy_button)

                section_layout.addWidget(row_widget)

            self.services_layout.addWidget(section)

        self.services_layout.addStretch()

    def _copy_to_clipboard(self, url: str) -> None:
        if not url:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(url)

    def get_selected_project(self) -> Optional[Dict[str, object]]:
        for project in self.projects:
            if str(project.get("key") or "") == self.selected_key:
                return project
        return None

    def select_project(self, key: str) -> None:
        self.selected_key = key
        self.state.update_projects_window(selected_key=key)
        self._render_list()
        self._render_detail()

    def add_project(self) -> None:
        dialog = ProjectEditDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.to_payload()
        existing_keys = {str(p.get("key")) for p in self.projects}
        base_key = str(payload["key"])
        new_key = base_key
        idx = 2
        while new_key in existing_keys:
            new_key = f"{base_key}-{idx}"
            idx += 1
        payload["key"] = new_key
        self.projects.append(_normalize_project(payload))
        self.state.set_projects(self.projects)
        self.selected_key = new_key
        self.state.update_projects_window(selected_key=new_key)
        self._render_list()
        self._render_detail()

    def scan_folder(self) -> None:
        last_root = self.state.get_projects_window().get("last_scan_root", "") or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self,
            "Proje klasoru sec",
            last_root,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not directory:
            return

        self.state.update_projects_window(last_scan_root=directory)
        detected = scan_directory(Path(directory))
        if not detected:
            QMessageBox.information(
                self,
                "Klasor Tara",
                "Bu klasorun altinda otomatik algilanabilen proje bulunamadi.\n\n"
                "Desteklenen diller ve isaretler:\n"
                "- .NET: *.csproj, *.fsproj, *.vbproj\n"
                "- Java: pom.xml, build.gradle(.kts)\n"
                "- Node/JS: package.json\n"
                "- Go: go.mod\n"
                "- Python: pyproject.toml, setup.py, manage.py, main.py, app.py\n"
                "- PHP: composer.json, artisan, index.php",
            )
            return

        existing_paths = {str(p.get("source_path") or "").lower() for p in self.projects}
        existing_keys = {str(p.get("key") or "") for p in self.projects}

        added = 0
        skipped = 0
        first_new_key: str = ""
        for payload in detected:
            payload_path = str(payload.get("source_path") or "").lower()
            if payload_path and payload_path in existing_paths:
                skipped += 1
                continue
            base_key = str(payload.get("key") or "project")
            new_key = base_key
            idx = 2
            while new_key in existing_keys:
                new_key = f"{base_key}-{idx}"
                idx += 1
            payload["key"] = new_key
            normalized = _normalize_project(payload)
            self.projects.append(normalized)
            existing_keys.add(new_key)
            existing_paths.add(payload_path)
            if not first_new_key:
                first_new_key = new_key
            added += 1

        self.state.set_projects(self.projects)
        if first_new_key:
            self.selected_key = first_new_key
            self.state.update_projects_window(selected_key=first_new_key)
        self._render_list()
        self._render_detail()

        message = f"{added} proje eklendi."
        if skipped:
            message += f" {skipped} proje zaten kayitli."
        QMessageBox.information(self, "Klasor Tara", message)

    def edit_selected(self) -> None:
        project = self.get_selected_project()
        if not project:
            return
        dialog = ProjectEditDialog(self, project)
        if dialog.exec() != QDialog.Accepted:
            return
        existing_key = str(project.get("key") or "")
        payload = dialog.to_payload(existing_key=existing_key)
        for index, item in enumerate(self.projects):
            if str(item.get("key") or "") == existing_key:
                self.projects[index] = _normalize_project(payload)
                break
        self.state.set_projects(self.projects)
        self._render_list()
        self._render_detail()

    def delete_selected(self) -> None:
        project = self.get_selected_project()
        if not project:
            return
        answer = QMessageBox.question(
            self,
            "Proje Sil",
            f"'{project.get('name')}' projesi silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        key = str(project.get("key") or "")
        self.projects = [p for p in self.projects if str(p.get("key") or "") != key]
        self.state.set_projects(self.projects)
        if self.projects:
            self.selected_key = str(self.projects[0]["key"])
        else:
            self.selected_key = ""
        self.state.update_projects_window(selected_key=self.selected_key)
        self._render_list()
        self._render_detail()
