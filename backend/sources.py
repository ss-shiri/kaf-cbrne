"""Source registry.

Each source lists SEVERAL candidate endpoints. The collector tries them in
order and keeps the first that returns entries. This is the direct fix for the
previous failure, where a single hard-coded URL went stale and the whole source
silently produced nothing.

Run `python -m backend.verify_feeds` to test every candidate and see exactly
which endpoints are alive before you trust a deployment.
"""

SOURCES = [
    {
        "name": "IAEA",
        "urls": [
            "https://www.iaea.org/feeds/topnews",          # confirmed pattern
            "https://www.iaea.org/feeds/pressalerts",
            "https://www.iaea.org/feeds/dgstatements",
        ],
        "domains": ["Nuclear"],
        "reliability": "A2",
    },
    {
        "name": "OPCW",
        "urls": [
            "https://www.opcw.org/rss.xml",
            "https://www.opcw.org/media-centre/news/feed",
            "https://www.opcw.org/media-centre/news.xml",
        ],
        "domains": ["Chemical"],
        "reliability": "A2",
    },
    {
        "name": "WHO Outbreak News",
        "urls": [
            "https://www.who.int/rss-feeds/news-outbreaks.xml",
            "https://www.who.int/feeds/entity/csr/don/en/rss.xml",
            "https://www.who.int/rss-feeds/news-english.xml",
        ],
        "domains": ["Biological"],
        "reliability": "A2",
    },
    {
        "name": "UN News",
        "urls": [
            "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml",
            "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        ],
        "domains": ["Multi"],
        "reliability": "B2",
    },
    {
        "name": "ECDC",
        "urls": [
            "https://www.ecdc.europa.eu/en/all-news/rss",
            "https://www.ecdc.europa.eu/en/rss",
        ],
        "domains": ["Biological"],
        "reliability": "A2",
    },
    {
        "name": "CISA Advisories",
        "urls": [
            "https://www.cisa.gov/cybersecurity-advisories/all.xml",
            "https://www.cisa.gov/news.xml",
        ],
        "domains": ["Multi"],
        "reliability": "A2",
    },
    {
        "name": "CDC Newsroom",
        "urls": [
            "https://tools.cdc.gov/api/v2/resources/media/403372.rss",
            "https://tools.cdc.gov/api/v2/resources/media/132608.rss",
        ],
        "domains": ["Biological"],
        "reliability": "A2",
    },
]

# Domain classifier: lowercase substring match on title + summary.
DOMAIN_KEYWORDS = {
    "Nuclear": [
        "nuclear", "npt", "safeguard", "enrichment", "uranium", "plutonium",
        "reactor", "nonproliferation", "non-proliferation", "fissile",
        "centrifuge", "iaea", "warhead",
    ],
    "Chemical": [
        "chemical weapon", "opcw", "nerve agent", "sarin", "novichok",
        "chlorine", "toxic chemical", "chemical warfare", "sulfur mustard",
        "chemical precursor", "cwc",
    ],
    "Biological": [
        "outbreak", "ebola", "nipah", "pathogen", "virus", "bioweapon",
        "biological weapon", "biosecurity", "biosurveillance", "pandemic",
        "anthrax", "influenza", "cholera", "mpox", "measles", "zoonotic",
        "epidemic", "synthesis screening", "select agent", "biosafety",
    ],
    "Radiological": [
        "radioactive", "radiological", "orphan source", "sealed source",
        "caesium", "cesium", "cobalt-60", "iridium-192", "dirty bomb",
        "radiation source", "radiation exposure",
    ],
    "Explosives": [
        "explosive", " ied", "improvised explosive", "detonat", "tatp",
        "ammonium nitrate", "hmtd", "bomb disposal", "unexploded ordnance",
    ],
}

# Tracking parameters stripped during URL normalization.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "s",
    "spm", "yclid", "_hsenc", "_hsmi",
}

DOC_TYPE_HINTS = {
    "outbreak news": ["outbreak", "disease outbreak news"],
    "advisory": ["advisory", "alert", "vulnerability"],
    "policy": ["regulation", "directive", "policy", "resolution"],
    "safeguards report": ["safeguards", "board of governors"],
    "statement": ["statement", "remarks", "briefing"],
    "press release": ["press release"],
}
