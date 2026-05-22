import os
import re
import subprocess
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from config import PROJECTS_ROOT, get_workspace_root

TCO_PATTERN = re.compile(r"\b(TCO-\d+)\b", re.IGNORECASE)
MR_PATTERN = re.compile(r"See merge request\s+([^\s!]+/[^\s!]+)!([0-9]+)", re.IGNORECASE)
MERGE_PATTERN = re.compile(r"Merge branch '([^']+)' into '?([^'\n]+)'?", re.IGNORECASE)

INTEGRATION_BRANCH_HINTS = (
    "main",
    "master",
    "develop",
    "stage",
    "sprint",
    "test",
    "release",
)

SKIP_DIRS = {
    ".git",
    ".idea",
    ".vs",
    ".claude",
    "node_modules",
    "bin",
    "obj",
    "target",
    "build",
    "dist",
    "coverage",
    "vendor",
    ".gradle",
    ".mvn",
    ".venv",
    "venv",
    "__pycache__",
}

_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_cache_state = {"generated_at": None, "snapshot": None}


def list_git_repos(root=None):
    root = root or get_workspace_root()
    repos = []

    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if ".git" in os.listdir(dirpath):
            rel_path = os.path.relpath(dirpath, root)
            repos.append(
                {
                    "path": dirpath,
                    "name": rel_path,
                    "slug": rel_path.split(os.sep)[-1],
                }
            )
            dirnames[:] = []

    repos.sort(key=lambda item: item["name"].lower())
    return repos


def get_git_activity(force=False):
    now = datetime.utcnow()
    with _cache_lock:
        cached_at = _cache_state["generated_at"]
        if not force and cached_at and _cache_state["snapshot"]:
            if (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
                return _cache_state["snapshot"]

        snapshot = _collect_git_activity()
        _cache_state["generated_at"] = now
        _cache_state["snapshot"] = snapshot
        return snapshot


def warm_git_activity_cache(force=False):
    return get_git_activity(force=force)


def build_sidebar_payload(force=False):
    snapshot = get_git_activity(force=force)
    return {
        "summary": snapshot["summary"],
        "top_people": snapshot["contributors"][:4],
        "top_repos": snapshot["repos"][:4],
        "generated_at": snapshot["generated_at"],
    }


def build_team_payload(force=False):
    snapshot = get_git_activity(force=force)
    return {
        "summary": snapshot["summary"],
        "contributors": snapshot["contributors"][:12],
        "repos": snapshot["repos"][:10],
        "recent_prs": snapshot["recent_prs"][:12],
        "recent_commits": snapshot["recent_commits"][:16],
        "generated_at": snapshot["generated_at"],
    }


def get_tco_git_context(tco_number, force=False):
    tco = (tco_number or "").upper()
    if not tco:
        return _empty_tco_context()

    snapshot = get_git_activity(force=force)
    commit_matches = [
        item
        for item in snapshot["recent_commits_all"]
        if tco in item.get("tcos", [])
    ]
    pr_matches = [
        item
        for item in snapshot["recent_prs_all"]
        if tco in item.get("tcos", [])
    ]

    repo_counter = Counter(item["repo"] for item in commit_matches + pr_matches)
    contributor_counter = Counter(item["author_email"] for item in commit_matches)
    contributor_counter.update(item["owner_email"] for item in pr_matches if item.get("owner_email"))

    contributors = []
    contributor_lookup = {
        item["email"]: item
        for item in snapshot["contributors"]
    }
    for email, count in contributor_counter.most_common():
        base = contributor_lookup.get(email)
        if not base:
            continue
        contributors.append(
            {
                "name": base["name"],
                "email": base["email"],
                "commit_count": base["commit_count"],
                "merge_count": base["merge_count"],
                "mr_count": base["mr_count"],
                "score": count,
            }
        )

    top_repos = []
    repo_lookup = {
        item["name"]: item
        for item in snapshot["repos"]
    }
    for repo_name, count in repo_counter.most_common():
        repo = repo_lookup.get(repo_name)
        if not repo:
            continue
        top_repos.append(
            {
                "name": repo["name"],
                "slug": repo["slug"],
                "commit_count_7d": repo["commit_count_7d"],
                "commit_count_30d": repo["commit_count_30d"],
                "merge_count": repo["merge_count"],
                "mr_count": repo["mr_count"],
                "score": count,
            }
        )

    commit_count_7d = sum(1 for item in commit_matches if _is_within_days(item["authored_at"], 7))

    return {
        "tco": tco,
        "commit_count_7d": commit_count_7d,
        "commit_count_30d": len(commit_matches),
        "merge_count": len(pr_matches),
        "mr_count": len([item for item in pr_matches if item.get("mr_iid")]),
        "recent_commits": commit_matches[:8],
        "recent_prs": pr_matches[:8],
        "top_repos": top_repos[:5],
        "top_contributors": contributors[:5],
    }


def _collect_git_activity():
    repo_defs = list_git_repos()
    contributor_commits = defaultdict(lambda: _new_person_bucket())
    contributor_merges = defaultdict(lambda: _new_person_bucket())
    all_recent_commits = []
    all_pr_events = []
    repo_metrics = []

    for repo_def in repo_defs:
        repo_data = _collect_repo_activity(repo_def)
        repo_metrics.append(repo_data["repo"])

        for email, bucket in repo_data["commit_people"].items():
            person = contributor_commits[email]
            person["email"] = email
            person["names"].update(bucket["names"])
            person["commit_count"] += bucket["commit_count"]
            person["repos"].update(bucket["repos"])
            person["last_activity"] = _max_dt(person["last_activity"], bucket["last_activity"])

        for email, bucket in repo_data["merge_people"].items():
            person = contributor_merges[email]
            person["email"] = email
            person["names"].update(bucket["names"])
            person["merge_count"] += bucket["merge_count"]
            person["mr_count"] += bucket["mr_count"]
            person["repos"].update(bucket["repos"])
            person["last_activity"] = _max_dt(person["last_activity"], bucket["last_activity"])

        all_recent_commits.extend(repo_data["recent_commits"])
        all_pr_events.extend(repo_data["pr_events"])

    contributors = _merge_people(contributor_commits, contributor_merges)
    repo_metrics.sort(key=lambda item: (-item["activity_score"], item["name"].lower()))
    all_recent_commits.sort(key=lambda item: item["authored_at"] or datetime.min, reverse=True)
    all_pr_events.sort(key=lambda item: item["merged_at"] or datetime.min, reverse=True)

    commits_24h = sum(repo["commit_count_24h"] for repo in repo_metrics)
    commits_7d = sum(repo["commit_count_7d"] for repo in repo_metrics)
    commits_30d = sum(repo["commit_count_30d"] for repo in repo_metrics)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "repo_count": len(repo_metrics),
            "active_repos": len([repo for repo in repo_metrics if repo["commit_count_7d"] > 0]),
            "active_people": len([person for person in contributors if person["commit_count"] > 0 or person["merge_count"] > 0]),
            "commits_24h": commits_24h,
            "commits_7d": commits_7d,
            "commits_30d": commits_30d,
            "merge_count": len(all_pr_events),
            "mr_count": len([item for item in all_pr_events if item.get("mr_iid")]),
        },
        "contributors": contributors,
        "repos": repo_metrics,
        "recent_prs": all_pr_events[:20],
        "recent_prs_all": all_pr_events,
        "recent_commits": all_recent_commits[:20],
        "recent_commits_all": all_recent_commits,
    }


def _collect_repo_activity(repo_def):
    repo_path = repo_def["path"]
    repo_name = repo_def["name"]
    slug = repo_def["slug"]

    raw_log = _run_git(
        repo_path,
        [
            "log",
            "--all",
            "--since=30 days ago",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%P%x1f%ad%x1f%an%x1f%ae%x1f%s%x1f%b%x1e",
        ],
    )

    commits = _parse_log(raw_log)
    remote_url = _run_git(repo_path, ["remote", "get-url", "origin"]).strip()
    web_url = _to_web_url(remote_url)

    commit_people = defaultdict(lambda: _new_person_bucket())
    merge_people = defaultdict(lambda: _new_person_bucket())
    recent_commits = []
    pr_events = []
    trend = [0] * 7

    now = datetime.utcnow()
    repo_summary = {
        "name": repo_name,
        "slug": slug,
        "web_url": web_url,
        "commit_count_24h": 0,
        "commit_count_7d": 0,
        "commit_count_30d": 0,
        "merge_count": 0,
        "mr_count": 0,
        "contributors": 0,
        "last_activity": None,
        "trend": trend,
        "activity_score": 0,
    }

    for commit in commits:
        authored_at = commit["authored_at"]
        if not authored_at:
            continue

        repo_summary["commit_count_30d"] += 1
        repo_summary["last_activity"] = _max_dt(repo_summary["last_activity"], authored_at)

        if (now - authored_at) <= timedelta(hours=24):
            repo_summary["commit_count_24h"] += 1
        if (now - authored_at) <= timedelta(days=7):
            repo_summary["commit_count_7d"] += 1
            trend_index = 6 - (now.date() - authored_at.date()).days
            if 0 <= trend_index < 7:
                trend[trend_index] += 1

        person = commit_people[commit["author_email"]]
        person["email"] = commit["author_email"]
        person["names"][commit["author_name"]] += 1
        person["commit_count"] += 1
        person["repos"].add(repo_name)
        person["last_activity"] = _max_dt(person["last_activity"], authored_at)

        recent_commits.append(
            {
                "repo": repo_name,
                "repo_slug": slug,
                "hash": commit["hash"],
                "short_hash": commit["hash"][:7],
                "subject": commit["subject"],
                "author_name": commit["author_name"],
                "author_email": commit["author_email"],
                "authored_at": authored_at.isoformat(),
                "authored_at_label": _format_relative(authored_at, now),
                "tcos": commit["tcos"],
            }
        )

        merge_event = _build_merge_event(repo_path, repo_name, slug, web_url, commit, now)
        if not merge_event:
            continue

        repo_summary["merge_count"] += 1
        if merge_event.get("mr_iid"):
            repo_summary["mr_count"] += 1

        owner_email = merge_event["owner_email"]
        owner_name = merge_event["owner_name"]
        merge_person = merge_people[owner_email]
        merge_person["email"] = owner_email
        merge_person["names"][owner_name] += 1
        merge_person["merge_count"] += 1
        merge_person["mr_count"] += 1 if merge_event.get("mr_iid") else 0
        merge_person["repos"].add(repo_name)
        merge_person["last_activity"] = _max_dt(merge_person["last_activity"], authored_at)

        pr_events.append(merge_event)

    repo_summary["contributors"] = len(commit_people)
    repo_summary["activity_score"] = (
        repo_summary["commit_count_7d"]
        + (repo_summary["merge_count"] * 3)
        + (repo_summary["mr_count"] * 2)
    )
    repo_summary["last_activity"] = repo_summary["last_activity"].isoformat() if repo_summary["last_activity"] else None
    repo_summary["trend"] = trend

    recent_commits.sort(key=lambda item: item["authored_at"], reverse=True)
    pr_events.sort(key=lambda item: item["merged_at"], reverse=True)

    return {
        "repo": repo_summary,
        "commit_people": commit_people,
        "merge_people": merge_people,
        "recent_commits": recent_commits,
        "pr_events": pr_events,
    }


def _build_merge_event(repo_path, repo_name, slug, web_url, commit, now):
    if len(commit["parents"]) < 2:
        return None

    subject = commit["subject"]
    body = commit["body"]
    merge_match = MERGE_PATTERN.search(subject)
    mr_match = MR_PATTERN.search(body)

    source_branch = ""
    target_branch = ""
    if merge_match:
        source_branch = merge_match.group(1).strip()
        target_branch = merge_match.group(2).strip()

    if not mr_match and not _looks_like_merge_event(source_branch, target_branch, subject):
        return None

    owner_name, owner_email = _guess_merge_owner(repo_path, commit)
    mr_iid = mr_match.group(2) if mr_match else ""
    mr_url = f"{web_url}/-/merge_requests/{mr_iid}" if (web_url and mr_iid) else ""

    return {
        "repo": repo_name,
        "repo_slug": slug,
        "hash": commit["hash"],
        "short_hash": commit["hash"][:7],
        "title": subject,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "mr_iid": mr_iid,
        "mr_url": mr_url,
        "merged_at": commit["authored_at"].isoformat(),
        "merged_at_label": _format_relative(commit["authored_at"], now),
        "merge_author_name": commit["author_name"],
        "merge_author_email": commit["author_email"],
        "owner_name": owner_name,
        "owner_email": owner_email,
        "tcos": sorted(set(commit["tcos"] + _extract_tcos(source_branch, target_branch))),
    }


def _looks_like_merge_event(source_branch, target_branch, subject):
    if not source_branch or not target_branch:
        return False
    if subject.lower().startswith("merge remote-tracking branch"):
        return False
    source_lower = source_branch.lower()
    target_lower = target_branch.lower()
    if source_lower in {"main", "master"} or source_lower.startswith("origin/main"):
        return False
    return any(hint in target_lower for hint in INTEGRATION_BRANCH_HINTS)


def _guess_merge_owner(repo_path, commit):
    parents = commit["parents"]
    if len(parents) < 2:
        return commit["author_name"], commit["author_email"]

    branch_raw = _run_git(
        repo_path,
        [
            "log",
            "--format=%an%x1f%ae%x1e",
            f"{parents[0]}..{parents[1]}",
        ],
        timeout=12,
    )
    entries = [item for item in branch_raw.split("\x1e") if item.strip()]
    if not entries:
        return commit["author_name"], commit["author_email"]

    counts = Counter()
    names = defaultdict(Counter)
    for entry in entries:
        parts = entry.strip().split("\x1f")
        if len(parts) != 2:
            continue
        name, email = parts
        counts[email] += 1
        names[email][name] += 1

    if not counts:
        return commit["author_name"], commit["author_email"]

    owner_email, _count = counts.most_common(1)[0]
    owner_name = _pick_name(names[owner_email], owner_email)
    return owner_name, owner_email


def _merge_people(commit_people, merge_people):
    emails = set(commit_people.keys()) | set(merge_people.keys())
    people = []
    for email in emails:
        commit_bucket = commit_people.get(email, _new_person_bucket())
        merge_bucket = merge_people.get(email, _new_person_bucket())
        names = Counter()
        names.update(commit_bucket["names"])
        names.update(merge_bucket["names"])
        last_activity = _max_dt(commit_bucket["last_activity"], merge_bucket["last_activity"])

        people.append(
            {
                "name": _pick_name(names, email),
                "email": email,
                "commit_count": commit_bucket["commit_count"],
                "merge_count": merge_bucket["merge_count"],
                "mr_count": merge_bucket["mr_count"],
                "repo_count": len(commit_bucket["repos"] | merge_bucket["repos"]),
                "last_activity": last_activity.isoformat() if last_activity else "",
                "last_activity_label": _format_relative(last_activity) if last_activity else "-",
            }
        )

    people.sort(
        key=lambda item: (
            -item["mr_count"],
            -item["merge_count"],
            -item["commit_count"],
            item["name"].lower(),
        )
    )
    return people


def _parse_log(raw_output):
    commits = []
    records = [item for item in raw_output.split("\x1e") if item.strip()]
    for record in records:
        parts = record.rstrip("\n").split("\x1f")
        if len(parts) < 7:
            continue
        hash_value, parent_text, authored_at, author_name, author_email, subject, body = parts[:7]
        authored_dt = _parse_git_datetime(authored_at)
        commits.append(
            {
                "hash": hash_value,
                "parents": [item for item in parent_text.split() if item],
                "authored_at": authored_dt,
                "author_name": author_name,
                "author_email": author_email,
                "subject": subject.strip(),
                "body": body.strip(),
                "tcos": _extract_tcos(subject, body),
            }
        )
    return commits


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
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _extract_tcos(*texts):
    items = set()
    for text in texts:
        if not text:
            continue
        for match in TCO_PATTERN.findall(text):
            items.add(match.upper())
    return sorted(items)


def _format_relative(dt_value, now=None):
    if not dt_value:
        return "-"
    now = now or datetime.utcnow()
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


def _pick_name(counter, fallback_email):
    if not counter:
        return fallback_email.split("@")[0]
    name, _count = counter.most_common(1)[0]
    if "@" in name and "." in name:
        return fallback_email.split("@")[0]
    return name


def _new_person_bucket():
    return {
        "email": "",
        "names": Counter(),
        "commit_count": 0,
        "merge_count": 0,
        "mr_count": 0,
        "repos": set(),
        "last_activity": None,
    }


def _max_dt(left, right):
    if left and right:
        return max(left, right)
    return left or right


def _is_within_days(value, days):
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except Exception:
        return False
    return (datetime.utcnow() - parsed) <= timedelta(days=days)


def _empty_tco_context():
    return {
        "tco": "",
        "commit_count_7d": 0,
        "commit_count_30d": 0,
        "merge_count": 0,
        "mr_count": 0,
        "recent_commits": [],
        "recent_prs": [],
        "top_repos": [],
        "top_contributors": [],
    }
