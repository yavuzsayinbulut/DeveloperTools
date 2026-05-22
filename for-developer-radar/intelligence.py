import os
import re
from collections import Counter
from datetime import datetime, timedelta

from git_activity import get_tco_git_context, list_git_repos
from models import FutureDeployment, MdIndex, Task
from search_engine import search_md, trace_tco

TCO_PATTERN = re.compile(r"\b(TCO-\d+)\b", re.IGNORECASE)
CHANGE_ENTRY_PATTERN = re.compile(r"^-\s*(\d{4}-\d{2}-\d{2}):\s*(.+)$")

SMART_TYPE_TO_CATEGORY = {
    "decision": "degisiklik",
    "karar": "degisiklik",
    "deployment": "deployment",
    "deploy": "deployment",
    "task": "task",
    "doc": "dokuman",
    "docs": "dokuman",
    "guide": "rehber",
    "rehber": "rehber",
    "architecture": "mimari",
    "mimari": "mimari",
}

DOC_TYPE_ORDER = [
    "PLAN_AND_ANALYSIS",
    "DEVELOPMENT",
    "CODE_REVIEW",
    "MANUEL_TEST",
    "QA_TEST",
    "DEPLOYMENT",
]


def smart_search(query, category=None, limit=50):
    parsed = _parse_smart_query(query, category)
    summary = _build_smart_summary(parsed)
    suggestions = get_search_suggestions()

    if parsed["trace_tco"]:
        return {
            "results": [],
            "summary": summary,
            "tokens": parsed["tokens"],
            "trace_tco": parsed["trace_tco"],
            "suggestions": suggestions,
        }

    effective_category = parsed["category"] or category

    if parsed["free_text"]:
        results = search_md(parsed["free_text"], effective_category, limit=limit * 2)
    else:
        records = MdIndex.query
        if effective_category:
            records = records.filter(MdIndex.category == effective_category)
        records = records.order_by(MdIndex.last_modified.desc()).limit(limit * 2).all()
        results = [
            {
                "rel_path": rec.rel_path,
                "file_path": rec.file_path,
                "category": rec.category,
                "title": rec.title,
                "tco_numbers": rec.tco_numbers,
                "snippets": [],
            }
            for rec in records
        ]

    results = _apply_repo_filter(results, parsed["repo"])
    results = _apply_tco_filter(results, parsed["tco"])

    return {
        "results": results[:limit],
        "summary": summary,
        "tokens": parsed["tokens"],
        "trace_tco": "",
        "suggestions": suggestions,
    }


def get_search_suggestions():
    repo_defs = list_git_repos()
    repo_slugs = [repo["slug"] for repo in repo_defs[:4]]
    suggestions = [
        "tco:4176",
        "type:decision TCO-4176",
        "type:deployment denizbank",
        "repo:shire fix",
    ]
    for slug in repo_slugs:
        token = f"repo:{slug}"
        if token not in suggestions:
            suggestions.append(token)
    return suggestions[:8]


def build_follow_up_radar(limit=8):
    items = []
    active_tasks = (
        Task.query.filter(Task.status.in_(["TODO", "IN_PROGRESS", "IN_REVIEW"]))
        .order_by(Task.updated_at.asc())
        .all()
    )

    for task in active_tasks:
        tco = (task.tco_number or "").strip().upper()
        doc_types = set(_get_doc_types_for_tco(tco)) if tco else set()
        if tco and "PLAN_AND_ANALYSIS" not in doc_types:
            items.append(
                _radar_item(
                    "warning",
                    f"{tco} icin plan izi yok",
                    f"{task.title[:80]} task'inda PLAN_AND_ANALYSIS kaydi bulunamadi.",
                    f"/search?q={tco}",
                )
            )
        if tco and task.status in {"IN_PROGRESS", "IN_REVIEW"} and "DEVELOPMENT" not in doc_types:
            items.append(
                _radar_item(
                    "warning",
                    f"{tco} development kaydi eksik",
                    "Kod akisi ilerliyor ama DEVELOPMENT dokumani izlenmiyor.",
                    f"/search?q={tco}",
                )
            )
        if task.status == "IN_REVIEW" and not task.mr_url:
            items.append(
                _radar_item(
                    "info",
                    f"{task.title[:48]} review'da ama MR linki yok",
                    "Task board kartinda MR URL alanini doldurmak faydali olur.",
                    "/tasks",
                )
            )
        if task.updated_at and task.updated_at < datetime.utcnow() - timedelta(days=5):
            items.append(
                _radar_item(
                    "neutral",
                    f"{task.title[:48]} uzun suredir sessiz",
                    f"Task son {max((datetime.utcnow() - task.updated_at).days, 1)} gundur guncellenmedi.",
                    "/tasks",
                )
            )
        if tco and task.status in {"IN_PROGRESS", "IN_REVIEW"}:
            git_ctx = get_tco_git_context(tco)
            if git_ctx["commit_count_7d"] == 0:
                items.append(
                    _radar_item(
                        "neutral",
                        f"{tco} git tarafinda son 7 gunde hareket yok",
                        "Task aktif gorunuyor ama ilgili commit izi taze degil.",
                        f"/search?q={tco}",
                    )
                )

    pending_deployments = (
        FutureDeployment.query.filter_by(status="bekliyor")
        .order_by(FutureDeployment.date.asc())
        .all()
    )
    for deployment in pending_deployments:
        weak_repos = [
            repo.get("name", "?").split("/")[-1]
            for repo in deployment.repos
            if repo.get("test_merge") in {"Yapilmadi", "Bilinmiyor", "Teyit Bekliyor", ""}
        ]
        if weak_repos:
            items.append(
                _radar_item(
                    "warning",
                    f"{deployment.task or deployment.title[:28]} test merge teyidi bekliyor",
                    ", ".join(weak_repos[:4]) + " repo(su) icin teyit eksik.",
                    f"/deployment/{deployment.id}",
                )
            )

        try:
            deploy_date = datetime.fromisoformat(deployment.date)
            if deploy_date < datetime.utcnow() - timedelta(days=3):
                items.append(
                    _radar_item(
                        "info",
                        f"{deployment.task or deployment.title[:28]} bekleyen deploy eskidi",
                        f"{deployment.date} tarihli kayit hala bekliyor durumda.",
                        f"/deployment/{deployment.id}",
                    )
                )
        except Exception:
            continue

    items.sort(key=lambda item: (_severity_rank(item["severity"]), item["title"]))
    return items[:limit]


def build_decision_memory(limit=6, tcos=None, repos=None):
    entries = _parse_change_entries()
    focus_tcos = {item.upper() for item in (tcos or []) if item}
    focus_repos = {item.lower() for item in (repos or []) if item}

    if not focus_tcos and not focus_repos:
        active_tcos = {
            (task.tco_number or "").strip().upper()
            for task in Task.query.filter(Task.status.in_(["TODO", "IN_PROGRESS", "IN_REVIEW"])).all()
            if task.tco_number
        }
        deployment_tcos = {
            (fd.task or "").strip().upper()
            for fd in FutureDeployment.query.filter_by(status="bekliyor").all()
            if fd.task
        }
        focus_tcos = active_tcos | deployment_tcos

    filtered = []
    for entry in entries:
        has_tco_match = not focus_tcos or bool(focus_tcos & set(entry["tcos"]))
        has_repo_match = not focus_repos or any(repo in focus_repos for repo in entry["repos"])
        if (focus_tcos and has_tco_match) or (focus_repos and has_repo_match):
            filtered.append(entry)

    if not filtered:
        filtered = entries

    return filtered[:limit]


def build_tco_intelligence(tco_number):
    tco = (tco_number or "").strip().upper()
    trace = trace_tco(tco)
    doc_counter = Counter(item["doc_type"] for item in trace)
    git_ctx = get_tco_git_context(tco)

    task = (
        Task.query.filter_by(tco_number=tco)
        .order_by(Task.updated_at.desc())
        .first()
    )
    deployments = (
        FutureDeployment.query.filter_by(task=tco)
        .order_by(FutureDeployment.date.desc())
        .all()
    )

    related_repos = [repo["name"] for repo in git_ctx["top_repos"]]
    decisions = build_decision_memory(limit=5, tcos=[tco], repos=related_repos)
    followups = _build_tco_followups(tco, task, deployments, doc_counter, git_ctx)
    score = _score_tco_health(doc_counter, git_ctx, task, decisions)

    return {
        "tco": tco,
        "health": {
            "score": score,
            "label": _health_label(score),
        },
        "docs": [
            {"type": doc_type, "count": doc_counter.get(doc_type, 0)}
            for doc_type in DOC_TYPE_ORDER
        ],
        "task": {
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "jira_url": task.jira_url,
            "mr_url": task.mr_url,
            "updated_at": task.updated_at.isoformat() if task and task.updated_at else "",
        }
        if task
        else None,
        "deployments": [
            {
                "id": deployment.id,
                "date": deployment.date,
                "title": deployment.title,
                "status": deployment.status,
                "weak_repos": [
                    repo.get("name", "?").split("/")[-1]
                    for repo in deployment.repos
                    if repo.get("test_merge") in {"Yapilmadi", "Bilinmiyor", "Teyit Bekliyor", ""}
                ],
            }
            for deployment in deployments[:4]
        ],
        "git": git_ctx,
        "followups": followups,
        "decisions": decisions,
        "trace_count": len(trace),
    }


def _build_tco_followups(tco, task, deployments, doc_counter, git_ctx):
    items = []
    if doc_counter.get("PLAN_AND_ANALYSIS", 0) == 0:
        items.append(_radar_item("warning", f"{tco} plan izi zayif", "PLAN_AND_ANALYSIS kaydi bulunamadi.", f"/search?q={tco}"))
    if doc_counter.get("DEVELOPMENT", 0) == 0 and git_ctx["commit_count_30d"] > 0:
        items.append(_radar_item("warning", f"{tco} icin git hareketi var ama DEVELOPMENT yok", "Commitler gorunuyor ancak development dokumani izlenmiyor.", f"/search?q={tco}"))
    if deployments and doc_counter.get("MANUEL_TEST", 0) == 0:
        items.append(_radar_item("info", f"{tco} deploy izi var ama manuel test kaydi yok", "Davranis degisikliginde manuel test notu eklemek faydali olur.", f"/search?q={tco}"))
    if task and task.status == "IN_REVIEW" and not task.mr_url and git_ctx["mr_count"] == 0:
        items.append(_radar_item("info", f"{tco} review'da ama PR izi zayif", "Task kartinda MR linki veya merge izi gorunmuyor.", "/tasks"))
    if task and task.status == "TODO" and git_ctx["commit_count_7d"] > 0:
        items.append(_radar_item("neutral", f"{tco} gitte hareketli ama board TODO", "Kart statusu guncel olmayabilir.", "/tasks"))
    for deployment in deployments[:3]:
        weak_repos = [
            repo.get("name", "?").split("/")[-1]
            for repo in deployment.repos
            if repo.get("test_merge") in {"Yapilmadi", "Bilinmiyor", "Teyit Bekliyor", ""}
        ]
        if weak_repos:
            items.append(_radar_item("warning", f"{tco} deploy test merge teyidi bekliyor", ", ".join(weak_repos[:4]) + " icin teyit eksik.", f"/deployment/{deployment.id}"))

    items.sort(key=lambda item: (_severity_rank(item["severity"]), item["title"]))
    return items[:6]


def _parse_smart_query(query, category=None):
    repo_value = ""
    tco_value = ""
    smart_type = ""
    free_terms = []
    tokens = []

    for raw_token in (query or "").split():
        lower_token = raw_token.lower()
        if lower_token.startswith("repo:"):
            repo_value = raw_token.split(":", 1)[1].strip().lower()
            if repo_value:
                tokens.append({"kind": "repo", "label": f"Repo: {repo_value}"})
            continue
        if lower_token.startswith("type:"):
            smart_type = raw_token.split(":", 1)[1].strip().lower()
            if smart_type:
                tokens.append({"kind": "type", "label": f"Tip: {smart_type}"})
            continue
        if lower_token.startswith("tco:"):
            tco_value = _normalize_tco(raw_token.split(":", 1)[1].strip())
            if tco_value:
                tokens.append({"kind": "tco", "label": tco_value})
            continue
        free_terms.append(raw_token)

    lower_query = (query or "").lower()
    if not smart_type:
        for keyword, mapped in SMART_TYPE_TO_CATEGORY.items():
            if keyword in lower_query:
                smart_type = keyword
                tokens.append({"kind": "type", "label": f"Tip: {smart_type}"})
                break

    effective_category = category or SMART_TYPE_TO_CATEGORY.get(smart_type, "")
    free_text = " ".join(free_terms).strip()
    trace_tco = tco_value if (tco_value and not free_text and not effective_category) else ""

    return {
        "free_text": free_text,
        "repo": repo_value,
        "tco": tco_value,
        "type": smart_type,
        "category": effective_category,
        "trace_tco": trace_tco,
        "tokens": tokens,
    }


def _build_smart_summary(parsed):
    parts = []
    if parsed["repo"]:
        parts.append(f"repo filtresi `{parsed['repo']}`")
    if parsed["type"]:
        parts.append(f"akilli tip `{parsed['type']}`")
    if parsed["tco"]:
        parts.append(f"TCO odagi `{parsed['tco']}`")
    if not parts:
        return ""
    return "Smart Search 2.0 " + " + ".join(parts)


def _apply_repo_filter(results, repo_filter):
    if not repo_filter:
        return results
    filtered = []
    needle = repo_filter.lower()
    for item in results:
        rel_path = item["rel_path"].lower()
        title = item["title"].lower()
        if needle in rel_path or needle in title or f"/{needle}/" in rel_path:
            filtered.append(item)
    return filtered


def _apply_tco_filter(results, tco_value):
    if not tco_value:
        return results
    filtered = []
    for item in results:
        haystack = " ".join(
            [
                item.get("tco_numbers", ""),
                item.get("title", ""),
                item.get("rel_path", ""),
            ]
        ).upper()
        if tco_value in haystack:
            filtered.append(item)
    return filtered or results


def _parse_change_entries():
    repo_defs = list_git_repos()
    repo_names = [repo["name"].lower() for repo in repo_defs]
    entries = []

    records = (
        MdIndex.query.filter(MdIndex.rel_path.like("%AGENTS-CHANGES.md"))
        .order_by(MdIndex.last_modified.desc())
        .all()
    )
    for record in records:
        for line in record.content.splitlines():
            match = CHANGE_ENTRY_PATTERN.match(line.strip())
            if not match:
                continue
            entry_text = match.group(2).strip()
            entry_tcos = sorted({item.upper() for item in TCO_PATTERN.findall(entry_text)})
            entry_repos = [repo for repo in repo_names if repo in entry_text.lower()]
            entries.append(
                {
                    "date": match.group(1),
                    "text": entry_text,
                    "tcos": entry_tcos,
                    "repos": entry_repos,
                    "source_path": record.rel_path,
                    "source_name": os.path.basename(record.rel_path),
                }
            )

    entries.sort(key=lambda item: item["date"], reverse=True)
    return entries


def _get_doc_types_for_tco(tco):
    if not tco:
        return []
    return [item["doc_type"] for item in trace_tco(tco)]


def _score_tco_health(doc_counter, git_ctx, task, decisions):
    score = 0
    if doc_counter.get("PLAN_AND_ANALYSIS", 0):
        score += 18
    if doc_counter.get("DEVELOPMENT", 0):
        score += 18
    if doc_counter.get("MANUEL_TEST", 0):
        score += 14
    if doc_counter.get("DEPLOYMENT", 0):
        score += 16
    if git_ctx["commit_count_30d"] > 0:
        score += 12
    if git_ctx["mr_count"] > 0:
        score += 10
    if task:
        score += 6
    if decisions:
        score += 6
    return min(score, 100)


def _health_label(score):
    if score >= 75:
        return "Guclu"
    if score >= 50:
        return "Dengeli"
    return "Ince Iz"


def _normalize_tco(value):
    if not value:
        return ""
    value = value.upper()
    if value.startswith("TCO-"):
        return value
    if value.isdigit():
        return f"TCO-{value}"
    return value


def _radar_item(severity, title, text, href):
    return {
        "severity": severity,
        "title": title,
        "text": text,
        "href": href,
    }


def _severity_rank(value):
    order = {"warning": 0, "info": 1, "neutral": 2}
    return order.get(value, 9)
