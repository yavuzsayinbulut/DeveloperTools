import os
import re
import subprocess
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from git_activity import list_git_repos
from models import FutureDeployment, Task

JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b", re.IGNORECASE)
MR_PATTERN = re.compile(r"See merge request\s+([^\s!]+/[^\s!]+)!([0-9]+)", re.IGNORECASE)
MERGE_PATTERN = re.compile(r"Merge branch '([^']+)' into '?([^'\n]+)'?", re.IGNORECASE)
IGNORED_JIRA_PREFIXES = {"SPRINT", "RELEASE", "HOTFIX", "STAGE", "TEST", "DEV"}

TEST_FILE_HINTS = (
    "/test/",
    "/tests/",
    "src/test/",
    ".spec.",
    ".test.",
    "_test.",
    "test_",
)

RISKY_FILE_HINTS = (
    "migration",
    "liquibase",
    "flyway",
    "schema",
    "application.yml",
    "application.yaml",
    "application.properties",
    ".gitlab-ci",
    "jenkinsfile",
    "dockerfile",
    "pom.xml",
    "build.gradle",
    "package-lock.json",
)

PIPELINE_SIGNAL_PATTERNS = (
    re.compile(r"\bpipeline\s+(failed|error|red|kirdi|kirildi)\b", re.IGNORECASE),
    re.compile(r"\b(job|build|test|deploy)\s+(failed|error|kirdi|kirildi)\b", re.IGNORECASE),
    re.compile(r"\b(maven|gradle|npm|yarn)\s+(failed|error)\b", re.IGNORECASE),
    re.compile(r"\bci\s+(failed|error|red)\b", re.IGNORECASE),
)

_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_cache_state = {"key": None, "generated_at": None, "snapshot": None}


def build_delivery_radar(days=60, query="", force=False):
    days = _coerce_days(days)
    query = (query or "").strip()
    snapshot = _get_snapshot(days, force=force)
    return _filter_snapshot(snapshot, query)


def _get_snapshot(days, force=False):
    now = datetime.utcnow()
    cache_key = f"days:{days}"
    with _cache_lock:
        cached_at = _cache_state["generated_at"]
        if (
            not force
            and _cache_state["key"] == cache_key
            and cached_at
            and _cache_state["snapshot"]
            and (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS
        ):
            return _cache_state["snapshot"]

    snapshot = _collect_snapshot(days, now)

    with _cache_lock:
        _cache_state["key"] = cache_key
        _cache_state["generated_at"] = now
        _cache_state["snapshot"] = snapshot
    return snapshot


def _collect_snapshot(days, now):
    deployments = _load_deployments()
    tasks_by_key = _load_tasks_by_key()
    prs = []

    for repo_def in list_git_repos():
        prs.extend(_collect_repo_prs(repo_def, days, now))

    deployments_by_key = defaultdict(list)
    for deployment in deployments:
        if deployment["task"]:
            deployments_by_key[deployment["task"].upper()].append(deployment)

    for pr in prs:
        matched = _match_deployments(pr, deployments, deployments_by_key)
        pr["deployments"] = matched[:5]
        pr["task"] = _match_task(pr, tasks_by_key)
        pr["test_branch_state"] = _classify_test_branch(pr, matched)
        pr["risk"] = _score_pr(pr)

    prs.sort(key=lambda item: item.get("merged_at") or "", reverse=True)
    deployment_days = _build_deployment_days(deployments, prs)
    path_hotspots = _build_path_hotspots(prs)
    pipeline_items = _build_pipeline_items(prs, deployment_days)

    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "summary": {
            "repo_count": len(list_git_repos()),
            "deployment_count": len(deployments),
            "matched_pr_count": len([item for item in prs if item["deployments"]]),
            "jira_linked_pr_count": len([item for item in prs if item["jira_keys"]]),
            "test_pending_count": len([item for item in prs if item["test_branch_state"]["state"] in {"pending", "unknown"} and item["deployments"]]),
            "pipeline_signal_count": len([item for item in prs if item["pipeline_signals"]]),
            "high_risk_pr_count": len([item for item in prs if item["risk"]["severity"] == "high"]),
        },
        "deployment_days": deployment_days[:12],
        "prs": prs[:80],
        "path_hotspots": path_hotspots[:30],
        "pipeline_items": pipeline_items[:30],
    }


def _load_deployments():
    rows = FutureDeployment.query.order_by(FutureDeployment.date.desc()).all()
    deployments = []
    for row in rows:
        repos = row.repos
        deployments.append(
            {
                "id": row.id,
                "date": row.date,
                "title": row.title,
                "task": (row.task or "").upper(),
                "jira_url": row.jira_url,
                "status": row.status,
                "repos": repos,
                "repo_slugs": [_slugify_repo(repo.get("name", "")) for repo in repos if repo.get("name")],
                "test_pending_repos": [
                    repo.get("name", "")
                    for repo in repos
                    if _normalize_test_merge(repo.get("test_merge", "")) in {"pending", "missing", "unknown"}
                ],
            }
        )
    return deployments


def _load_tasks_by_key():
    rows = Task.query.filter(Task.tco_number != "").all()
    return {
        row.tco_number.upper(): {
            "id": row.id,
            "title": row.title,
            "status": row.status,
            "priority": row.priority,
            "jira_url": row.jira_url,
            "mr_url": row.mr_url,
        }
        for row in rows
        if row.tco_number
    }


def _collect_repo_prs(repo_def, days, now):
    repo_path = repo_def["path"]
    repo_name = repo_def["name"]
    repo_slug = repo_def["slug"]
    remote_url = _run_git(repo_path, ["remote", "get-url", "origin"]).strip()
    web_url = _to_web_url(remote_url)
    raw = _run_git(
        repo_path,
        [
            "log",
            "--all",
            "--merges",
            f"--since={days} days ago",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%P%x1f%ad%x1f%an%x1f%ae%x1f%s%x1f%b%x1e",
        ],
        timeout=30,
    )

    prs = []
    for commit in _parse_git_records(raw):
        if len(commit["parents"]) < 2:
            continue

        source_branch, target_branch = _parse_merge_branches(commit["subject"])
        mr_match = MR_PATTERN.search(commit["body"] or "")
        if not mr_match and not source_branch:
            continue

        changed_files = _collect_changed_files(repo_path, commit["parents"][0], commit["parents"][1])
        jira_keys = _extract_jira_keys(commit["subject"], commit["body"], source_branch, target_branch)
        mr_iid = mr_match.group(2) if mr_match else ""
        merged_at = _parse_git_datetime(commit["authored_at"])

        additions = sum(item["additions"] for item in changed_files)
        deletions = sum(item["deletions"] for item in changed_files)

        prs.append(
            {
                "repo": repo_name,
                "repo_slug": repo_slug,
                "web_url": web_url,
                "hash": commit["hash"],
                "short_hash": commit["hash"][:7],
                "title": commit["subject"],
                "source_branch": source_branch,
                "target_branch": target_branch,
                "mr_iid": mr_iid,
                "mr_url": f"{web_url}/-/merge_requests/{mr_iid}" if web_url and mr_iid else "",
                "merged_at": merged_at.isoformat() if merged_at else "",
                "merged_at_label": _format_relative(merged_at, now) if merged_at else "-",
                "merge_author_name": commit["author_name"],
                "merge_author_email": commit["author_email"],
                "jira_keys": jira_keys,
                "changed_files": changed_files[:80],
                "file_count": len(changed_files),
                "additions": additions,
                "deletions": deletions,
                "has_tests": any(_looks_like_test_file(item["path"]) for item in changed_files),
                "risky_files": [
                    item["path"]
                    for item in changed_files
                    if _looks_like_risky_file(item["path"])
                ][:8],
                "pipeline_signals": _extract_pipeline_signals(commit["subject"], commit["body"]),
            }
        )
    return prs


def _collect_changed_files(repo_path, base_hash, head_hash):
    status_by_path = {}
    status_raw = _run_git(repo_path, ["diff", "--name-status", base_hash, head_hash], timeout=20)
    for line in status_raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status_by_path[parts[-1]] = parts[0]

    files = []
    numstat_raw = _run_git(repo_path, ["diff", "--numstat", base_hash, head_hash], timeout=20)
    for line in numstat_raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = parts[-1]
        files.append(
            {
                "path": path,
                "status": status_by_path.get(path, ""),
                "additions": _to_int(parts[0]),
                "deletions": _to_int(parts[1]),
            }
        )

    if files:
        return files

    return [
        {"path": path, "status": status, "additions": 0, "deletions": 0}
        for path, status in status_by_path.items()
    ]


def _match_deployments(pr, deployments, deployments_by_key):
    matched = []
    seen = set()

    for key in pr["jira_keys"]:
        for deployment in deployments_by_key.get(key.upper(), []):
            if deployment["id"] not in seen:
                matched.append(deployment)
                seen.add(deployment["id"])

    if pr.get("mr_url"):
        for deployment in deployments:
            for repo in deployment["repos"]:
                if repo.get("mr_url") and repo.get("mr_url") == pr["mr_url"] and deployment["id"] not in seen:
                    matched.append(deployment)
                    seen.add(deployment["id"])

    return matched


def _match_task(pr, tasks_by_key):
    for key in pr["jira_keys"]:
        if key.upper() in tasks_by_key:
            return tasks_by_key[key.upper()]
    return None


def _classify_test_branch(pr, deployments):
    statuses = []
    repo_slug = pr.get("repo_slug", "")
    for deployment in deployments:
        for repo in deployment["repos"]:
            if _slugify_repo(repo.get("name", "")) != repo_slug:
                continue
            status = _normalize_test_merge(repo.get("test_merge", ""))
            if status:
                statuses.append(status)

    if "done" in statuses:
        return {"state": "done", "label": "Test branch basildi"}
    if "pending" in statuses:
        return {"state": "pending", "label": "Teyit bekliyor"}
    if "missing" in statuses:
        return {"state": "missing", "label": "Test branch eksik"}
    if "test" in (pr.get("target_branch") or "").lower():
        return {"state": "done", "label": "Target test branch"}
    return {"state": "unknown", "label": "Test branch izi yok"}


def _score_pr(pr):
    score = 0
    reasons = []

    if not pr["jira_keys"]:
        score += 25
        reasons.append("Jira/TCO key yok")
    if pr["file_count"] >= 15 or (pr["additions"] + pr["deletions"]) >= 700:
        score += 20
        reasons.append("Buyuk degisiklik")
    if pr["risky_files"]:
        score += 20
        reasons.append("Konfigurasyon/migration/pipeline dosyasi degismis")
    if pr["deployments"] and pr["test_branch_state"]["state"] in {"pending", "missing", "unknown"}:
        score += 25
        reasons.append("Deployment var ama test branch teyidi zayif")
    if not pr["has_tests"] and pr["file_count"] >= 4:
        score += 15
        reasons.append("Test dosyasi degisikligi yok")
    if pr["pipeline_signals"]:
        score += 30
        reasons.append("Pipeline hata sinyali var")

    if score >= 55:
        severity = "high"
    elif score >= 25:
        severity = "medium"
    else:
        severity = "low"

    return {"score": min(score, 100), "severity": severity, "reasons": reasons[:5]}


def _build_deployment_days(deployments, prs):
    prs_by_deployment = defaultdict(list)
    for pr in prs:
        for deployment in pr["deployments"]:
            prs_by_deployment[deployment["id"]].append(pr)

    day_map = {}
    for deployment in deployments:
        day = day_map.setdefault(
            deployment["date"] or "Tarihsiz",
            {
                "date": deployment["date"] or "Tarihsiz",
                "deployment_count": 0,
                "matched_pr_count": 0,
                "pending_test_count": 0,
                "pipeline_signal_count": 0,
                "items": [],
            },
        )
        matched_prs = prs_by_deployment.get(deployment["id"], [])
        day["deployment_count"] += 1
        day["matched_pr_count"] += len(matched_prs)
        day["pending_test_count"] += len(deployment["test_pending_repos"])
        day["pipeline_signal_count"] += len([pr for pr in matched_prs if pr["pipeline_signals"]])
        day["items"].append(
            {
                "id": deployment["id"],
                "task": deployment["task"],
                "title": deployment["title"],
                "status": deployment["status"],
                "matched_pr_count": len(matched_prs),
                "pending_test_repos": deployment["test_pending_repos"][:4],
            }
        )

    return sorted(day_map.values(), key=lambda item: item["date"], reverse=True)


def _build_path_hotspots(prs):
    counter = Counter()
    repo_by_path = {}
    risk_by_path = defaultdict(int)
    keys_by_path = defaultdict(set)

    for pr in prs:
        for changed in pr["changed_files"]:
            path = changed["path"]
            counter[path] += 1
            repo_by_path[path] = pr["repo_slug"]
            for key in pr["jira_keys"]:
                keys_by_path[path].add(key)
            if changed["path"] in pr["risky_files"]:
                risk_by_path[path] += 1

    return [
        {
            "path": path,
            "repo": repo_by_path.get(path, ""),
            "touch_count": count,
            "jira_keys": sorted(keys_by_path[path])[:5],
            "risk_count": risk_by_path[path],
        }
        for path, count in counter.most_common()
    ]


def _build_pipeline_items(prs, deployment_days):
    items = []
    for pr in prs:
        if pr["pipeline_signals"]:
            items.append(
                {
                    "kind": "pipeline",
                    "severity": "high",
                    "title": f"{pr['repo_slug']} pipeline sinyali",
                    "text": "; ".join(pr["pipeline_signals"]),
                    "href": pr["mr_url"] or "",
                }
            )
        if pr["deployments"] and pr["test_branch_state"]["state"] in {"pending", "missing", "unknown"}:
            items.append(
                {
                    "kind": "test_branch",
                    "severity": "medium",
                    "title": f"{pr['repo_slug']} test branch teyidi zayif",
                    "text": pr["test_branch_state"]["label"],
                    "href": pr["mr_url"] or "",
                }
            )
    return items


def _filter_snapshot(snapshot, query):
    if not query:
        return snapshot

    needle = query.lower()

    def pr_matches(pr):
        haystack = " ".join(
            [
                pr.get("repo", ""),
                pr.get("repo_slug", ""),
                pr.get("title", ""),
                pr.get("source_branch", ""),
                pr.get("target_branch", ""),
                " ".join(pr.get("jira_keys", [])),
                " ".join(item["path"] for item in pr.get("changed_files", [])),
            ]
        ).lower()
        return needle in haystack

    prs = [pr for pr in snapshot["prs"] if pr_matches(pr)]
    deployment_ids = {deployment["id"] for pr in prs for deployment in pr["deployments"]}
    deployment_days = []
    for day in snapshot["deployment_days"]:
        items = [item for item in day["items"] if item["id"] in deployment_ids or needle in (item["task"] or "").lower() or needle in item["title"].lower()]
        if items:
            cloned = dict(day)
            cloned["items"] = items
            deployment_days.append(cloned)

    path_hotspots = [
        item
        for item in snapshot["path_hotspots"]
        if needle in item["path"].lower() or needle in item["repo"].lower() or needle in " ".join(item["jira_keys"]).lower()
    ]
    pipeline_items = [
        item
        for item in snapshot["pipeline_items"]
        if needle in item["title"].lower() or needle in item["text"].lower()
    ]

    return {
        **snapshot,
        "query": query,
        "summary": {
            **snapshot["summary"],
            "filtered_pr_count": len(prs),
        },
        "deployment_days": deployment_days,
        "prs": prs,
        "path_hotspots": path_hotspots,
        "pipeline_items": pipeline_items,
    }


def _parse_git_records(raw_output):
    records = []
    for record in [item for item in raw_output.split("\x1e") if item.strip()]:
        parts = record.rstrip("\n").split("\x1f")
        if len(parts) < 7:
            continue
        records.append(
            {
                "hash": parts[0],
                "parents": [item for item in parts[1].split() if item],
                "authored_at": parts[2],
                "author_name": parts[3],
                "author_email": parts[4],
                "subject": parts[5].strip(),
                "body": parts[6].strip(),
            }
        )
    return records


def _parse_merge_branches(subject):
    match = MERGE_PATTERN.search(subject or "")
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2).strip()


def _extract_jira_keys(*texts):
    keys = set()
    for text in texts:
        if not text:
            continue
        for match in JIRA_KEY_PATTERN.findall(text):
            key = match.upper()
            prefix = key.split("-", 1)[0]
            if prefix not in IGNORED_JIRA_PREFIXES:
                keys.add(key)
    return sorted(keys)


def _extract_pipeline_signals(*texts):
    signals = []
    haystack = "\n".join(text for text in texts if text)
    for pattern in PIPELINE_SIGNAL_PATTERNS:
        match = pattern.search(haystack)
        if match:
            signals.append(match.group(0))
    return signals[:4]


def _normalize_test_merge(value):
    text = (value or "").strip().lower()
    if not text:
        return "unknown"
    if text in {"yapildi", "yapıldı", "done", "yes", "true", "basildi", "basıldı"}:
        return "done"
    if text in {"teyit bekliyor", "pending", "wait", "waiting"}:
        return "pending"
    if text in {"yapilmadi", "yapılmadı", "no", "false", "missing"}:
        return "missing"
    if text in {"bilinmiyor", "unknown"}:
        return "unknown"
    return "unknown"


def _looks_like_test_file(path):
    value = "/" + (path or "").replace("\\", "/").lower()
    return any(hint in value for hint in TEST_FILE_HINTS)


def _looks_like_risky_file(path):
    value = (path or "").replace("\\", "/").lower()
    return any(hint in value for hint in RISKY_FILE_HINTS)


def _slugify_repo(value):
    if not value:
        return ""
    cleaned = value.replace("\\", "/").strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    return os.path.basename(cleaned).lower()


def _run_git(repo_path, args, timeout=20):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except Exception:
        return ""


def _to_web_url(remote_url):
    if not remote_url:
        return ""
    remote_url = remote_url.strip()
    if remote_url.startswith("http://") or remote_url.startswith("https://"):
        return remote_url[:-4] if remote_url.endswith(".git") else remote_url
    if remote_url.startswith("git@") and ":" in remote_url:
        host_part, path_part = remote_url.split("@", 1)[1].split(":", 1)
        path_part = path_part[:-4] if path_part.endswith(".git") else path_part
        return f"https://{host_part}/{path_part}"
    return ""


def _parse_git_datetime(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _format_relative(dt_value, now):
    if not dt_value:
        return "-"
    delta = now - dt_value
    if delta < timedelta(minutes=1):
        return "simdi"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)} dk"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)} sa"
    if delta < timedelta(days=7):
        return f"{delta.days} g"
    return dt_value.strftime("%d %b")


def _coerce_days(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 60
    return max(7, min(days, 180))


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
