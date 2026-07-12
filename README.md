# CBRNE OSINT Reading Room

Live: **https://ss-shiri.github.io/kaf-cbrne/**

An open-source intelligence reading room covering Chemical, Biological,
Radiological, Nuclear and Explosives threats, plus cross-domain dual-use, AI
and cyber items. Every record links to a primary source, carries a short
paraphrase and a "why it matters" line, and is graded for reliability.
Refreshes automatically every 3 hours.

Maintained by **Sajad Shiri** · [LinkedIn](https://www.linkedin.com/in/sajad-shiri) · [ALEF OSINT · 1,290 Tools](https://ss-shiri.github.io/ALEF-OSINT/)

---

## Why the previous version stopped working

Two separate faults, both fixed here.

**1. Feed URLs went stale and failed silently.** The collector logged a warning,
collected nothing, and exited 0. GitHub showed a green check while the site
never updated. Fixed by: multiple candidate endpoints per source, a
`verify_feeds` diagnostic, and a collector that **exits non-zero** when it
fetches nothing, so a broken run goes red and emails you.

**2. GitHub silently disabled the schedule.** GitHub disables scheduled
workflows after 60 days of repository inactivity, with no error in the Actions
tab. Fixed by a keepalive step that commits a timestamp when the last commit is
older than 50 days.

**3. The page could hang on "Loading records".** The front end now renders
instantly from an inline seed, then upgrades to live data. It cannot hang.

## Layout

```
index.html                    Front end (inline seed, renders instantly)
data/records.json             Record store, rewritten every 3 hours
backend/collector.py          Fetch, classify, canonicalize, dedupe, merge
backend/verify_feeds.py       Feed health check (run this when updates stop)
backend/sources.py            Source registry + classifier keywords
.github/workflows/refresh.yml 3-hourly refresh + keepalive
.nojekyll                     Serve data/ untouched on Pages
```

## Deploy

1. Push to a repo named `kaf-cbrne`.
2. Settings, Pages: deploy from branch `main`, folder `/ (root)`.
3. Settings, Actions, General: set Workflow permissions to
   **Read and write permissions**. Without this the bot cannot push.
4. Actions tab, "refresh", **Run workflow** to seed the first run.

## When it stops updating again

Feed endpoints change. This takes about a minute to repair:

```bash
pip install feedparser
python -m backend.verify_feeds
```

It prints every candidate endpoint as OK or DEAD, with entry counts and the
newest item date. Find the source with no working endpoint, get its current feed
URL, and add it to the top of that source's `urls` list in `backend/sources.py`.
Commit. Done.

Local run:

```bash
python -m backend.collector                 # full run
python -m backend.collector --no-canonical  # faster, skips canonical resolution
```

## Link quality

Feed links are unreliable: they carry tracking parameters, redirect through
wrappers, and point at AMP or syndicated copies. The collector therefore
follows redirects, reads the page's own `rel=canonical` / `og:url`, strips
`utm_*`, `fbclid` and similar, and dedupes on the resulting canonical URL. This
is what keeps source links direct and stable.

## Reliability grading

Admiralty-style. Letter = source reliability, number = information credibility.

- `A1` official primary source, corroborated
- `A2` authoritative, largely single-source
- `B2` reliable secondary reporting of an official statement
- `C3` default for unreviewed items

Auto-ingested records are flagged **PROVISIONAL** and `needs_review: true` until
an analyst clears them. Machine summaries are source extracts, not assessed
intelligence.

## Notes

Open-source material only. Summaries are paraphrases or short extracts, never
verbatim reproduction. Nothing here is operational guidance. Verify every item
against its linked primary source before use.

MIT licensed. Linked source content remains the property of its publishers.
