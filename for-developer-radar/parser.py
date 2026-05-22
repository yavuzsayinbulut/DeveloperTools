import re
import os
from config import DEPLOYMENT_LOG_PATH, get_deployment_log_path


def parse_deployment_log(path=None):
    """Parse DEPLOYMENT_LOG.md into structured entries."""
    path = path or get_deployment_log_path()
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    blocks = re.split(r"(?=^## \d{4}-\d{2}-\d{2})", content, flags=re.MULTILINE)

    for block in blocks:
        block = block.strip()
        header_match = re.match(r"^## (\d{4}-\d{2}-\d{2}) - (.+)$", block, re.MULTILINE)
        if not header_match:
            continue

        entry = {
            "date": header_match.group(1),
            "title": header_match.group(2).strip(),
            "task": "",
            "jira_url": "",
            "summary": "",
            "repos": [],
            "contacts": [],
            "raw": block,
        }

        task_match = re.search(r"- Task:\s*`?(TCO-\d+)`?", block)
        if task_match:
            entry["task"] = task_match.group(1)

        jira_match = re.search(r"- Jira:\s*(https?://\S+)", block)
        if jira_match:
            entry["jira_url"] = jira_match.group(1)

        summary_match = re.search(r"- Ozet:\s*(.+)", block)
        if summary_match:
            entry["summary"] = summary_match.group(1).strip()

        contacts_match = re.search(r"- Ilgililer:\s*(.+)", block)
        if contacts_match:
            raw = contacts_match.group(1)
            entry["contacts"] = [c.strip().strip("`").strip("'").strip('"') for c in raw.split(",")]

        repo_blocks = re.split(r"  - `([^`]+)`:", block)
        for i in range(1, len(repo_blocks), 2):
            repo_name = repo_blocks[i]
            repo_content = repo_blocks[i + 1] if i + 1 < len(repo_blocks) else ""

            repo = {"name": repo_name, "mr_url": "", "branch": "", "commit": "", "test_merge": "", "test_note": "", "detail": ""}

            mr_match = re.search(r"- MR:\s*(https?://\S+)", repo_content)
            if mr_match:
                repo["mr_url"] = mr_match.group(1)

            branch_match = re.search(r"- Branch:\s*`?([^`\n]+)`?", repo_content)
            if branch_match:
                repo["branch"] = branch_match.group(1).strip()

            commit_match = re.search(r"- Commit:\s*`?([^`\n]+)`?", repo_content)
            if commit_match:
                repo["commit"] = commit_match.group(1).strip()

            merge_match = re.search(r"- Test Branch Merge:\s*`?([^`\n]+)`?", repo_content)
            if merge_match:
                repo["test_merge"] = merge_match.group(1).strip()

            note_match = re.search(r"- Test Branch Notu:\s*(.+?)(?=\n    - |\n  - `|\n##|\Z)", repo_content, re.DOTALL)
            if note_match:
                repo["test_note"] = note_match.group(1).strip()

            detail_match = re.search(r"- Detay:\s*(.+?)(?=\n    - |\n  - `|\n##|\Z)", repo_content, re.DOTALL)
            if detail_match:
                repo["detail"] = detail_match.group(1).strip()

            entry["repos"].append(repo)

        entries.append(entry)

    return entries


def get_deployment_stats(entries):
    """Get summary stats from deployment entries."""
    if not entries:
        return {"total": 0, "repos": set(), "tasks": set()}

    repos = set()
    tasks = set()
    for e in entries:
        if e["task"]:
            tasks.add(e["task"])
        for r in e["repos"]:
            repos.add(r["name"])

    return {
        "total": len(entries),
        "repos": repos,
        "tasks": tasks,
        "latest_date": entries[0]["date"] if entries else None,
    }
