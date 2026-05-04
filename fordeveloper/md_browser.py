import os
import re
import markdown
from pygments.formatters import HtmlFormatter
from config import PROJECTS_ROOT, get_md_category, get_workspace_root


def scan_md_files(root=None):
    """Scan all .md files under projects root, return structured list."""
    root = root or get_workspace_root()
    files = []
    skip_dirs = {".git", "node_modules", "bin", "obj", ".idea", ".vs", ".claude"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root)
            category = get_md_category(full_path)
            title = _extract_title(full_path, fname)
            tco_numbers = _extract_tco_numbers(full_path)
            try:
                mtime = os.path.getmtime(full_path)
            except OSError:
                mtime = 0

            files.append({
                "path": full_path,
                "rel_path": rel_path,
                "name": fname,
                "category": category,
                "title": title,
                "tco_numbers": tco_numbers,
                "last_modified": mtime,
                "dir": os.path.relpath(dirpath, root),
            })

    files.sort(key=lambda x: x["last_modified"], reverse=True)
    return files


def _extract_title(path, fallback):
    """Extract first heading or use filename."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
                if line.startswith("## "):
                    return line[3:].strip()
        return fallback.replace(".md", "")
    except Exception:
        return fallback.replace(".md", "")


def _extract_tco_numbers(path):
    """Extract all TCO-XXXX references from file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = set(re.findall(r"TCO-\d+", content))
        return ",".join(sorted(matches))
    except Exception:
        return ""


def render_md(path):
    """Render markdown file to HTML."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return "<p>Dosya okunamadi.</p>", ""

    md = markdown.Markdown(extensions=[
        "fenced_code",
        "codehilite",
        "tables",
        "toc",
        "nl2br",
        "sane_lists",
    ], extension_configs={
        "codehilite": {"css_class": "highlight", "linenums": False},
        "toc": {"title": ""},
    })

    html = md.convert(content)
    toc = getattr(md, "toc", "")

    # Make URLs clickable and open in new tab
    html = re.sub(
        r'<a href="(https?://[^"]+)"',
        r'<a href="\1" target="_blank" rel="noopener"',
        html,
    )

    return html, toc


def build_file_tree(files):
    """Build nested tree structure from flat file list."""
    tree = {}
    for f in files:
        parts = f["rel_path"].split(os.sep)
        node = tree
        for i, part in enumerate(parts[:-1]):
            if part not in node:
                node[part] = {"__is_dir": True, "__children": {}}
            node = node[part]["__children"]
        fname = parts[-1]
        node[fname] = {
            "__is_dir": False,
            "__file": f,
        }
    return tree


def get_pygments_css():
    """Get Pygments CSS for code highlighting."""
    return HtmlFormatter(style="monokai").get_style_defs(".highlight")
