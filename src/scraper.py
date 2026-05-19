"""
Multi-journal article scraper.

Supports 8 journals across 3 publisher families, each with its own filtering
strategy to keep only original research articles (excluding News & Views,
Reviews, Editorials, Corrections, etc).

Data flow per journal:
  1. List all journal-article items in time window from Crossref API
  2. Coarse filter: DOI prefix + title prefix exclusion
  3. Fine filter (publisher-specific):
       - Nature family: scrape nature.com page -> check `prism.section` meta tag
                        (keep OriginalPaper + BriefCommunication, drop the rest)
       - Science:       require abstract length >= 100 chars
       - Wiley:         query Semantic Scholar API -> check `publicationTypes`
                        (drop if it contains Review/Editorial/etc)
  4. Nature-family abstracts are recovered from the page in step 3
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape

import requests

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1/paper"

USER_AGENT_API = "NatureScienceDigest/1.0 (mailto:noreply@example.com)"
USER_AGENT_BROWSER = "Mozilla/5.0 (compatible; ResearchDigest/1.0)"

# Polite delays (seconds) between successive page fetches
NATURE_FETCH_DELAY_SEC = 0.6
SS_FETCH_DELAY_SEC = 0.4

# ---- Per-journal configuration -----------------------------------------------
# Add/remove journals by editing this list.
#
# Fields:
#   name              : human-readable journal name (used in headings)
#   issn              : ISSN passed to Crossref `filter=issn:...`
#   doi_prefix        : substring that must be in DOI (None = no DOI check)
#   filter_strategy   : "nature_family" | "science" | "wiley"
#   display_short     : abbreviation shown in narrow contexts

JOURNAL_CONFIG = [
    {
        "name": "Nature",
        "issn": "0028-0836",
        "doi_prefix": "s41586-",
        "filter_strategy": "nature_family",
        "display_short": "Nature",
    },
    {
        "name": "Science",
        "issn": "0036-8075",
        "doi_prefix": None,
        "filter_strategy": "science",
        "display_short": "Science",
    },
    {
        "name": "Nature Materials",
        "issn": "1476-1122",
        "doi_prefix": "s41563-",
        "filter_strategy": "nature_family",
        "display_short": "Nat. Mater.",
    },
    {
        "name": "Nature Nanotechnology",
        "issn": "1748-3387",
        "doi_prefix": "s41565-",
        "filter_strategy": "nature_family",
        "display_short": "Nat. Nanotechnol.",
    },
    {
        "name": "Nature Machine Intelligence",
        "issn": "2522-5839",
        "doi_prefix": "s42256-",
        "filter_strategy": "nature_family",
        "display_short": "Nat. Mach. Intell.",
    },
    {
        "name": "Nature Sensors",
        "issn": "3059-4499",
        "doi_prefix": "s44460-",
        "filter_strategy": "nature_family",
        "display_short": "Nat. Sensors",
    },
    {
        "name": "Advanced Materials",
        "issn": "0935-9648",
        "doi_prefix": "10.1002/adma.",
        "filter_strategy": "wiley",
        "display_short": "Adv. Mater.",
    },
    {
        "name": "Advanced Functional Materials",
        "issn": "1616-301X",
        "doi_prefix": "10.1002/adfm.",
        "filter_strategy": "wiley",
        "display_short": "Adv. Funct. Mater.",
    },
]

# Title prefixes excluded across all journals.
# Match is case-insensitive AND tested as `startswith` — order does not matter,
# but include enough variations to catch real-world title formatting.
EXCLUDE_TITLE_PREFIXES = (
    "editorial", "news:", "news &", "perspective:", "comment:", "comment on",
    "correspondence:",
    "correction:", "correction to", "corrigendum",
    "author correction:", "author correction to",
    "publisher correction:", "publisher correction to",
    "retraction", "erratum", "addendum",
    "in this issue", "research highlight",
    "editorial expression of concern", "expression of concern",
    "matters arising", "reply to", "reply:",
    "issue information", "front matter", "back matter",
    "cover image", "masthead", "table of contents",
    "in other journals", "this week in science",
    "introduction to",  # often Special Issue intros
)

# For Nature family: prism.section values we accept (after also passing the
# category whitelist below). "BriefCommunication" alone is NOT enough — Nature
# sub-journals mark News & Views, Research Briefings, Research Highlights,
# Comments and Obituaries all with prism.section="BriefCommunication" too.
NATURE_RESEARCH_SECTIONS = {"OriginalPaper", "BriefCommunication"}

# The visible article-category (from the page header) that we whitelist as
# original research. Anything else (News & Views, Research Briefing, Comment,
# Perspective, Review Article, Editorial, Correspondence, Obituary, Matters
# Arising, Research Highlight, Author Correction, etc.) is filtered out.
NATURE_RESEARCH_CATEGORIES = {
    "Article",
    "Brief Communication",
    "Letter",          # used by Nature Physics, Nature Chemistry for short papers
    "Resource",        # used by Nature Methods, Nature Biotech for datasets/tools
    "Analysis",        # rare but legitimate research type
    "Registered Report",
}

# For Wiley via Semantic Scholar: publicationTypes that disqualify an item.
SS_NON_RESEARCH_TYPES = {
    "Review", "Editorial", "LettersAndComments",
    "Conference", "Book", "BookSection",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean_abstract(text):
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^Abstract[:\s]*", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _format_authors(authors_list, max_shown=5):
    if not authors_list:
        return "N/A"
    names = []
    for a in authors_list[:max_shown]:
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        full = f"{given} {family}".strip()
        if full:
            names.append(full)
    if len(authors_list) > max_shown:
        names.append("et al.")
    return ", ".join(names) if names else "N/A"


def _format_date(item):
    for key in ("published-print", "published-online", "issued"):
        parts = item.get(key, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0] is not None:
            parts_str = [str(p).zfill(2) for p in parts[0]]
            while len(parts_str) < 3:
                parts_str.append("01")
            return "-".join(parts_str[:3])
    return ""


def _title_is_non_research(title):
    title_lower = (title or "").lower().strip()
    return any(title_lower.startswith(p) for p in EXCLUDE_TITLE_PREFIXES)


# ---- Publisher-specific helpers ----------------------------------------------

def _fetch_nature_page_data(doi):
    """Fetch abstract + prism.section + article-category from a Nature page.

    Returns (abstract, section, category). Any field may be None on failure.

    Why we need both `section` and `category`: in Nature sub-journals, the
    `prism.section` tag lumps News & Views, Research Briefing, Comment, etc.
    under "BriefCommunication". The visible `article-category` (e.g.
    "News & Views", "Article", "Review Article") gives the correct distinction.
    """
    article_id = doi.split("/")[-1]
    url = f"https://www.nature.com/articles/{article_id}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT_BROWSER},
            timeout=30,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("nature.com returned %d for %s", resp.status_code, doi)
            return None, None, None

        # Abstract
        m_abs = re.search(
            r'<meta\s+name="dc\.description"\s+content="([^"]+)"', resp.text
        )
        abstract = unescape(m_abs.group(1)).strip() if m_abs else None

        # Technical section type (Crossref-style)
        m_sec = re.search(
            r'<meta\s+name="prism\.section"\s+content="([^"]+)"', resp.text
        )
        section = m_sec.group(1).strip() if m_sec else None

        # User-visible category (the badge on the article page header)
        m_cat = re.search(
            r'<li[^>]*data-test="article-category"[^>]*>([^<]+)</li>',
            resp.text,
        )
        category = unescape(m_cat.group(1)).strip() if m_cat else None

        return abstract, section, category
    except Exception as e:
        logger.warning("Nature page fetch failed for %s: %s", doi, e)
        return None, None, None


def _check_wiley_is_research(doi):
    """Use Semantic Scholar publicationTypes to decide if a Wiley item is research.

    Returns True if research (or if SS doesn't know yet - keep by default).
    Returns False only when SS explicitly tags the item as Review/Editorial/etc.
    """
    try:
        r = requests.get(
            f"{SEMANTIC_SCHOLAR_BASE}/DOI:{doi}",
            params={"fields": "publicationTypes"},
            headers={"User-Agent": USER_AGENT_API},
            timeout=15,
        )
        if r.status_code == 404:
            return True
        if r.status_code != 200:
            return True
        ptypes = r.json().get("publicationTypes") or []
        if not ptypes:
            return True
        return not any(t in SS_NON_RESEARCH_TYPES for t in ptypes)
    except Exception as e:
        logger.warning("Semantic Scholar check failed for %s: %s", doi, e)
        return True


# ---- Main per-journal fetch --------------------------------------------------

def _build_article_dict(item, journal_name, override_abstract=None):
    doi = item.get("DOI", "")
    title = ((item.get("title") or [""])[0] or "").strip()
    if override_abstract is not None:
        abstract = override_abstract
    else:
        abstract = _clean_abstract(item.get("abstract", ""))
    return {
        "title": title,
        "authors": _format_authors(item.get("author", [])),
        "abstract": abstract,
        "doi": doi,
        "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
        "pub_date": _format_date(item),
        "journal": journal_name,
    }


def fetch_journal_articles(config, days_back=8, max_results=500):
    """Fetch research articles from one configured journal."""
    name = config["name"]
    issn = config["issn"]
    doi_prefix = config["doi_prefix"]
    strategy = config["filter_strategy"]

    cutoff = (_utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    today = _utcnow().strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("Fetching: %s (ISSN=%s, %s..%s)", name, issn, cutoff, today)

    params = {
        "filter": (
            f"issn:{issn},from-pub-date:{cutoff},"
            f"until-pub-date:{today},type:journal-article"
        ),
        "rows": str(max_results),
        "sort": "published",
        "order": "desc",
        "select": (
            "DOI,title,author,abstract,published-print,published-online,"
            "issued,URL,type,container-title"
        ),
    }

    resp = requests.get(
        CROSSREF_BASE, params=params,
        headers={"User-Agent": USER_AGENT_API}, timeout=60,
    )
    resp.raise_for_status()
    items = resp.json().get("message", {}).get("items", [])
    logger.info("  Crossref returned %d items", len(items))

    # Coarse filter: DOI prefix + title prefix
    candidates = []
    for item in items:
        doi = item.get("DOI", "").lower()
        title = (item.get("title") or [""])[0] or ""
        if doi_prefix and doi_prefix.lower() not in doi:
            continue
        if _title_is_non_research(title):
            continue
        candidates.append(item)
    logger.info("  After DOI/title filter: %d candidates", len(candidates))

    # Fine filter, strategy-dependent
    articles = []

    if strategy == "nature_family":
        for idx, item in enumerate(candidates, 1):
            doi = item.get("DOI", "")
            page_abstract, page_section, page_category = _fetch_nature_page_data(doi)
            time.sleep(NATURE_FETCH_DELAY_SEC)

            # Two-stage filter:
            # 1. prism.section must be in our research whitelist
            # 2. article-category must ALSO be in the research whitelist
            #    (this catches News & Views items that share prism.section
            #     with real Brief Communications in Nature sub-journals)
            if page_section is not None and page_section not in NATURE_RESEARCH_SECTIONS:
                logger.info("  [%d/%d] SKIP %s (section=%s)",
                            idx, len(candidates), doi, page_section)
                continue

            if page_category is not None and page_category not in NATURE_RESEARCH_CATEGORIES:
                logger.info("  [%d/%d] SKIP %s (category=%s)",
                            idx, len(candidates), doi, page_category)
                continue

            # If section is BriefCommunication but category unknown, drop it —
            # in sub-journals this combination is overwhelmingly News & Views.
            if page_section == "BriefCommunication" and page_category is None:
                logger.info("  [%d/%d] SKIP %s (BriefCommunication + unknown category)",
                            idx, len(candidates), doi)
                continue

            crossref_abs = _clean_abstract(item.get("abstract", ""))
            final_abs = crossref_abs or (page_abstract or "")
            articles.append(_build_article_dict(item, name, override_abstract=final_abs))

    elif strategy == "science":
        for item in candidates:
            abstract = _clean_abstract(item.get("abstract", ""))
            if len(abstract) < 100:
                continue
            articles.append(_build_article_dict(item, name, override_abstract=abstract))

    elif strategy == "wiley":
        for idx, item in enumerate(candidates, 1):
            doi = item.get("DOI", "")
            if not _check_wiley_is_research(doi):
                logger.info("  [%d/%d] SKIP %s (Review/Editorial per SS)",
                            idx, len(candidates), doi)
                time.sleep(SS_FETCH_DELAY_SEC)
                continue
            articles.append(_build_article_dict(item, name))
            time.sleep(SS_FETCH_DELAY_SEC)

    else:
        logger.error("Unknown filter strategy for %s: %s", name, strategy)

    logger.info("  Final: %d research articles for %s", len(articles), name)
    return articles


def fetch_all_journals(days_back=8):
    """Fetch articles from all journals in JOURNAL_CONFIG.

    Returns {journal_name: [article, ...]}. Failed journals get an empty list
    so a single bad fetch doesn't kill the whole digest.
    """
    results = {}
    for config in JOURNAL_CONFIG:
        try:
            results[config["name"]] = fetch_journal_articles(config, days_back)
        except Exception as e:
            logger.exception("Failed to fetch %s: %s", config["name"], e)
            results[config["name"]] = []
    return results


# Back-compat shims (in case other modules import the old names)
def fetch_nature_articles(days_back=8):
    cfg = next(c for c in JOURNAL_CONFIG if c["name"] == "Nature")
    return fetch_journal_articles(cfg, days_back)


def fetch_science_articles(days_back=8):
    cfg = next(c for c in JOURNAL_CONFIG if c["name"] == "Science")
    return fetch_journal_articles(cfg, days_back)
