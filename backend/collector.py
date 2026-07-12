"""CBRNE feed collector.

  python -m backend.collector                    # normal run
  python -m backend.collector --no-canonical     # skip canonical resolution (faster)
  python -m backend.collector --min-entries 5    # tune the failure threshold

Behaviour that matters:

  * Each source has SEVERAL candidate endpoints; the first that yields entries
    wins. A single stale URL no longer silently kills a source.
  * If the whole run yields fewer than --min-entries entries, the process EXITS
    NON-ZERO. The previous version exited 0 on a total failure, so the GitHub
    Action went green while collecting nothing. It now fails loudly and emails.
  * Links are resolved to the publisher's canonical URL (rel=canonical / og:url),
    redirects followed, tracking parameters stripped, then deduped.
  * Every auto-ingested record is needs_review=True. Machine summaries are raw
    source extracts, never assessed intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .sources import (DOC_TYPE_HINTS, DOMAIN_KEYWORDS, SOURCES, TRACKING_PARAMS)

UA = "Mozilla/5.0 (compatible; cbrne-osint-reading-room/2.0; +https://ss-shiri.github.io/kaf-cbrne/)"
TIMEOUT = 25
MAX_AUTO = 120
EXCERPT = 300

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(ROOT, "data", "records.json")

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_CANON = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I)
_CANON_ALT = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', re.I)
_OG = re.compile(
    r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.I)


# --- text helpers ---------------------------------------------------------
def clean(raw: str) -> str:
    if not raw:
        return ""
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", raw))).strip()


def excerpt(raw: str, n: int = EXCERPT) -> str:
    t = clean(raw)
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " ..."


# --- URL hygiene ----------------------------------------------------------
def strip_tracking(url: str) -> str:
    try:
        p = urlparse(url)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
        return urlunparse((p.scheme, p.netloc.lower(), p.path,
                           p.params, urlencode(q), ""))
    except Exception:
        return url


def canonical_url(url: str) -> str:
    """Follow redirects, then prefer the page's own rel=canonical / og:url.

    Best effort: any failure returns the tracking-stripped input unchanged.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            final = r.geturl()
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "html" not in ctype:
                return strip_tracking(final)
            body = r.read(200_000).decode("utf-8", "ignore")
    except Exception:
        return strip_tracking(url)

    for rx in (_CANON, _CANON_ALT, _OG):
        m = rx.search(body)
        if m:
            href = html.unescape(m.group(1)).strip()
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("http"):
                return strip_tracking(href)
    return strip_tracking(final)


# --- classification -------------------------------------------------------
def classify(text: str, fallback):
    low = (text or "").lower()
    hits = [d for d, kws in DOMAIN_KEYWORDS.items() if any(k in low for k in kws)]
    if not hits:
        return list(fallback) or ["Multi"]
    if len(hits) > 2:          # very broad item, mark cross-domain
        hits = hits[:2] + ["Multi"]
    return hits


def doc_type(text: str) -> str:
    low = (text or "").lower()
    for label, hints in DOC_TYPE_HINTS.items():
        if any(h in low for h in hints):
            return label
    return "news"


def rid(url: str, title: str) -> str:
    b = (url or "").strip().lower() + "|" + (title or "").strip().lower()
    return "a-" + hashlib.sha1(b.encode()).hexdigest()[:12]


def entry_date(e) -> str:
    for k in ("published_parsed", "updated_parsed"):
        v = getattr(e, k, None)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc).date().isoformat()
            except Exception:
                pass
    return ""


# --- fetching -------------------------------------------------------------
def fetch(src, resolve: bool):
    """Try each candidate endpoint; return records from the first that works."""
    import feedparser

    for url in src["urls"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
            parsed = feedparser.parse(raw)
        except Exception as exc:
            print(f"    x {url}  ({type(exc).__name__})")
            continue

        if not parsed.entries:
            print(f"    x {url}  (0 entries)")
            continue

        print(f"    > {url}  ({len(parsed.entries)} entries)")
        out = []
        for e in parsed.entries:
            title = clean(getattr(e, "title", ""))
            link = (getattr(e, "link", "") or "").strip()
            if not title or not link:
                continue
            body = getattr(e, "summary", "") or getattr(e, "description", "") or ""
            blob = title + " " + clean(body)
            final = canonical_url(link) if resolve else strip_tracking(link)
            out.append({
                "id": rid(final, title),
                "title": title,
                "source_name": src["name"],
                "source_url": final,
                "published_date": entry_date(e),
                "doc_type": doc_type(blob),
                "domain_tags": classify(blob, src["domains"]),
                "topic_tags": [],
                "reliability": src["reliability"],
                "needs_review": True,
                "summary": excerpt(body) or "Open the source for details.",
                "why_it_matters": "",
                "ingested_at": datetime.now(timezone.utc).replace(
                    microsecond=0).isoformat(),
            })
        return out

    print(f"    ! {src['name']}: ALL endpoints failed")
    return []


# --- merge / store --------------------------------------------------------
def merge(existing, fresh):
    curated = [r for r in existing if not r.get("needs_review")]
    autos = [r for r in existing if r.get("needs_review")]

    seen_id = {r.get("id") for r in existing}
    seen_url = {(r.get("source_url") or "").lower() for r in existing}

    new = 0
    for r in fresh:
        if r["id"] in seen_id or r["source_url"].lower() in seen_url:
            continue
        autos.append(r)
        seen_id.add(r["id"])
        seen_url.add(r["source_url"].lower())
        new += 1

    autos.sort(key=lambda r: (r.get("published_date") or "",
                              r.get("ingested_at") or ""), reverse=True)
    autos = autos[:MAX_AUTO]

    combined = curated + autos
    combined.sort(key=lambda r: (r.get("published_date") or ""), reverse=True)
    return combined, new, len(curated)


def save(data, path):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


# --- main -----------------------------------------------------------------
def run(path=RECORDS, resolve=True, min_entries=1) -> int:
    print(f"collector start {datetime.now(timezone.utc).isoformat()}")

    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except Exception:
        store = {"records": []}
    store.setdefault("records", [])

    fresh, ok_sources = [], 0
    for src in SOURCES:
        print(f"  {src['name']}")
        got = fetch(src, resolve)
        if got:
            ok_sources += 1
        fresh.extend(got)

    print(f"\n  fetched {len(fresh)} entries from {ok_sources}/{len(SOURCES)} sources")

    # Loud failure. This is the guard the previous build was missing.
    if len(fresh) < min_entries:
        print(f"\nFAIL: only {len(fresh)} entries (min {min_entries}). "
              f"Every source endpoint appears dead.\n"
              f"Run: python -m backend.verify_feeds  to find working URLs, "
              f"then fix backend/sources.py")
        return 1

    records, new, curated = merge(store["records"], fresh)
    store["records"] = records
    store["compiled"] = datetime.now(timezone.utc).date().isoformat()
    store["updated_at"] = datetime.now(timezone.utc).replace(
        microsecond=0).isoformat()
    store["source"] = "curated + auto"
    store["sources_ok"] = f"{ok_sources}/{len(SOURCES)}"

    save(store, path)
    print(f"  merged: {curated} curated + {len(records)-curated} auto (+{new} new)")
    print(f"done. {len(records)} records -> {path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=RECORDS)
    ap.add_argument("--no-canonical", action="store_true",
                    help="skip canonical URL resolution")
    ap.add_argument("--min-entries", type=int, default=1,
                    help="fail the run below this many fetched entries")
    a = ap.parse_args(argv)
    return run(a.path, not a.no_canonical, a.min_entries)


if __name__ == "__main__":
    sys.exit(main())
