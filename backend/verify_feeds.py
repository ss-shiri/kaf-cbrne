"""Feed health check.

    python -m backend.verify_feeds

Tests EVERY candidate endpoint in sources.py and prints which are alive, how
many entries they return, and the newest item date. Run this whenever the site
stops updating: it tells you in ten seconds which endpoint died, so you can
replace it in backend/sources.py instead of guessing.

Exit code is non-zero if any source has no working endpoint.
"""
from __future__ import annotations

import sys
import urllib.request
from datetime import datetime, timezone

from .sources import SOURCES

UA = "Mozilla/5.0 (compatible; cbrne-osint-reading-room/2.0)"
TIMEOUT = 20


def probe(url: str):
    """Return (ok, n_entries, newest_date, note)."""
    import feedparser
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            code = r.getcode()
            raw = r.read()
    except Exception as exc:
        return False, 0, "", f"{type(exc).__name__}"

    feed = feedparser.parse(raw)
    n = len(feed.entries)
    if n == 0:
        return False, 0, "", f"HTTP {code}, 0 entries"

    newest = ""
    for e in feed.entries:
        for k in ("published_parsed", "updated_parsed"):
            v = getattr(e, k, None)
            if v:
                try:
                    d = datetime(*v[:6], tzinfo=timezone.utc).date().isoformat()
                    newest = max(newest, d)
                except Exception:
                    pass
    return True, n, newest, f"HTTP {code}"


def main() -> int:
    print("Feed health check\n" + "=" * 74)
    dead_sources = []

    for src in SOURCES:
        print(f"\n{src['name']}")
        any_ok = False
        for url in src["urls"]:
            ok, n, newest, note = probe(url)
            mark = "OK  " if ok else "DEAD"
            extra = f"{n:>3} entries, newest {newest or 'unknown'}" if ok else note
            print(f"  [{mark}] {url}\n         {extra}")
            if ok and not any_ok:
                any_ok = True
                print(f"         ^ collector will use this one")
        if not any_ok:
            dead_sources.append(src["name"])

    print("\n" + "=" * 74)
    if dead_sources:
        print(f"NO WORKING ENDPOINT for: {', '.join(dead_sources)}")
        print("Find the current feed URL and add it to backend/sources.py")
        return 1
    print("All sources have at least one working endpoint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
