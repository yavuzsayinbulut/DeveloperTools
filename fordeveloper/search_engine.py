import re
import os
from models import db, MdIndex
from md_browser import scan_md_files
from config import PROJECTS_ROOT


def rebuild_index():
    """Rebuild the full-text search index from md files."""
    files = scan_md_files()
    existing = {m.file_path: m for m in MdIndex.query.all()}
    seen = set()
    updated = 0
    added = 0

    for f in files:
        seen.add(f["path"])
        try:
            with open(f["path"], "r", encoding="utf-8") as fh:
                content = fh.read()
        except Exception:
            content = ""

        mtime = f["last_modified"]
        if f["path"] in existing:
            rec = existing[f["path"]]
            if rec.last_modified >= mtime:
                continue
            rec.rel_path = f["rel_path"]
            rec.category = f["category"]
            rec.title = f["title"]
            rec.content = content
            rec.tco_numbers = f["tco_numbers"]
            rec.last_modified = mtime
            updated += 1
        else:
            rec = MdIndex(
                file_path=f["path"],
                rel_path=f["rel_path"],
                category=f["category"],
                title=f["title"],
                content=content,
                tco_numbers=f["tco_numbers"],
                last_modified=mtime,
            )
            db.session.add(rec)
            added += 1

    removed = 0
    for path, rec in existing.items():
        if path not in seen:
            db.session.delete(rec)
            removed += 1

    db.session.commit()
    return {
        "indexed": len(files),
        "updated": updated,
        "added": added,
        "removed": removed,
        "sample_files": [f["rel_path"] for f in files[:8]],
    }


def search_md(query, category=None, limit=50):
    """Search md files by keyword."""
    if not query:
        return []

    q = MdIndex.query
    if category:
        q = q.filter(MdIndex.category == category)

    results = q.all()
    query_lower = query.lower()
    matches = []

    for rec in results:
        content_lower = rec.content.lower()
        if query_lower not in content_lower and query_lower not in rec.title.lower():
            continue

        snippets = _extract_snippets(rec.content, query, max_snippets=3)
        matches.append({
            "rel_path": rec.rel_path,
            "file_path": rec.file_path,
            "category": rec.category,
            "title": rec.title,
            "tco_numbers": rec.tco_numbers,
            "snippets": snippets,
        })

    matches.sort(key=lambda x: _relevance_score(x, query), reverse=True)
    return matches[:limit]


def trace_tco(tco_number):
    """Find all records related to a TCO number, sorted chronologically."""
    tco = tco_number.upper()
    results = MdIndex.query.filter(MdIndex.tco_numbers.contains(tco)).all()

    records = []
    for rec in results:
        date = _extract_date(rec.rel_path, rec.content)
        doc_type = _detect_doc_type(rec.rel_path)
        snippets = _extract_snippets(rec.content, tco, max_snippets=2)

        content_preview = rec.content.strip()
        if len(content_preview) > 5000:
            content_preview = content_preview[:5000] + "\n\n... (devami icin dosyayi ac)"

        records.append({
            "rel_path": rec.rel_path,
            "file_path": rec.file_path,
            "category": rec.category,
            "title": rec.title,
            "doc_type": doc_type,
            "date": date,
            "snippets": snippets,
            "content": content_preview,
        })

    type_order = {
        "PLAN_AND_ANALYSIS": 1,
        "DEVELOPMENT": 2,
        "CODE_REVIEW": 3,
        "MANUEL_TEST": 4,
        "QA_TEST": 5,
        "DEPLOYMENT": 6,
        "OTHER": 7,
    }
    records.sort(key=lambda x: (x["date"] or "0000", type_order.get(x["doc_type"], 99)))
    return records


def _extract_snippets(content, query, max_snippets=3):
    """Extract text snippets around query matches."""
    snippets = []
    lines = content.split("\n")
    query_lower = query.lower()

    for i, line in enumerate(lines):
        if query_lower in line.lower():
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            snippet = "\n".join(lines[start:end]).strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                break

    return snippets


def _relevance_score(match, query):
    """Simple relevance scoring."""
    score = 0
    ql = query.lower()
    if ql in match["title"].lower():
        score += 10
    score += len(match["snippets"]) * 2
    if match["category"] == "task":
        score += 3
    if match["category"] == "deployment":
        score += 2
    return score


def _extract_date(rel_path, content):
    """Try to extract a date from filename or content."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", rel_path)
    if m:
        return m.group(1)
    m = re.search(r"\*\*Tarih:\*\*\s*(\d{4}-\d{2}-\d{2})", content)
    if m:
        return m.group(1)
    return None


def _detect_doc_type(rel_path):
    """Detect document type from path."""
    upper = rel_path.upper()
    if "PLAN_AND_ANALYSIS" in upper or "PLAN & ANALYSIS" in upper:
        return "PLAN_AND_ANALYSIS"
    if "DEVELOPMENT" in upper:
        return "DEVELOPMENT"
    if "CODE_REVIEW" in upper:
        return "CODE_REVIEW"
    if "MANUEL_TEST" in upper or "MANUAL_TEST" in upper:
        return "MANUEL_TEST"
    if "QA_TEST" in upper:
        return "QA_TEST"
    if "DEPLOYMENT" in upper:
        return "DEPLOYMENT"
    return "OTHER"
