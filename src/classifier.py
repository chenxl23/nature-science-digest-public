"""
Keyword-rule based article classification with per-category summaries.

Each article is matched against the CATEGORY_KEYWORDS list (case-insensitive
substring match against title + abstract). One article can land in multiple
categories.
"""

import logging
import re
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = [
    ("生命科学 — 癌症/肿瘤", [
        "cancer", "tumor", "tumour", "oncolog", "carcinoma", "metasta",
        "leukemia", "leukaemia", "glioma", "melanoma", "lymphoma", "sarcoma",
    ]),
    ("生命科学 — 免疫学", [
        "immune", "immunolog", "antibod", "T cell", "B cell", "vaccine",
        "cytokine", "inflammat", "macrophage", "lymphocyte",
    ]),
    ("生命科学 — 神经科学", [
        "neuro", "brain", "cortex", "synap", "neural", "cognit", "memory",
        "axon", "dendri", "alzheimer", "parkinson",
    ]),
    ("生命科学 — 遗传/基因组学", [
        "genom", "genetic", "DNA", "RNA", "CRISPR", "transcript", "epigen",
        "chromatin", "gene expression", "gene regulat", "single-cell",
    ]),
    ("生命科学 — 微生物/病毒", [
        "virus", "viral", "bacteri", "microb", "pathogen", "infection",
        "coronavirus", "SARS", "antimicrob", "antibiotic",
    ]),
    ("生命科学 — 发育/细胞生物学", [
        "develop", "embryo", "stem cell", "organoid", "differentiation",
        "morphogen", "regeneration", "cell cycle", "mitochondri", "organelle",
    ]),
    ("地球与环境科学", [
        "climate", "ocean", "atmospher", "ecosystem", "biodivers",
        "carbon", "warming", "glacier", "ice", "rainforest", "deforestation",
        "pollution", "earthquake", "volcan", "geolog",
    ]),
    ("物理 — 量子/凝聚态", [
        "quantum", "superconduct", "qubit", "graphene", "magnon", "phonon",
        "ferromagn", "antiferromagn", "topolog", "exciton", "nanocrystal",
    ]),
    ("物理 — 天体/宇宙", [
        "cosmic", "galax", "stellar", "astrophys", "black hole", "exoplanet",
        "dark matter", "dark energy", "universe", "neutrino",
    ]),
    ("化学/材料", [
        "catalyst", "catalysis", "synthesis", "polymer", "perovskite",
        "battery", "solar cell", "photovoltaic", "electrolyt", "molecul",
        "metal-organic", "nanoparticle", "MOF", "COF",
    ]),
    ("纳米科技/二维材料", [
        "nano", "two-dimensional", "2D material", "MXene", "monolayer",
        "van der Waals", "heterostructure", "thin film",
    ]),
    ("传感/可穿戴/柔性电子", [
        "sensor", "wearable", "flexible", "biosensor", "electronic skin",
        "e-skin", "stretchable", "implantable",
    ]),
    ("人工智能/计算", [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "large language model", "transformer", "algorithm",
        "generative", "diffusion model",
    ]),
    ("考古/人类学/演化", [
        "fossil", "ancient", "evolution", "phylogen", "archaeolog",
        "anthropolog", "indigenous", "hominin", "neanderthal", "paleolithic",
    ]),
]

UNCATEGORIZED = "其他/跨学科"

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "this", "that", "these", "those",
    "we", "us", "our", "they", "their", "it", "its", "which", "who", "whom",
    "what", "where", "when", "why", "how", "here", "there", "show", "shows",
    "showed", "found", "find", "study", "studies", "result", "results",
    "however", "therefore", "thus", "also", "more", "most", "such", "some",
    "all", "both", "than", "then", "between", "into", "through", "using",
    "used", "use", "based", "new", "novel", "recent", "high", "low", "large",
    "small", "first", "second", "during", "while", "after", "before", "within",
    "across", "well", "much", "many", "few", "very", "still", "even", "only",
    "different", "similar", "associated", "increase", "decrease",
}


def _matches_category(text, keywords):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def classify_articles(articles):
    groups = defaultdict(list)
    for article in articles:
        haystack = f"{article.get('title', '')} {article.get('abstract', '')}"
        matched_any = False
        for category_name, keywords in CATEGORY_KEYWORDS:
            if _matches_category(haystack, keywords):
                groups[category_name].append(article)
                matched_any = True
        if not matched_any:
            groups[UNCATEGORIZED].append(article)
    return dict(groups)


def _extract_top_terms(articles, top_k=6):
    counter = Counter()
    for article in articles:
        text = f"{article.get('title', '')} {article.get('abstract', '')}"
        words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
        for w in words:
            wl = w.lower()
            if wl in STOP_WORDS:
                continue
            counter[wl] += 1
    return counter.most_common(top_k)


def summarize_category(category_name, articles):
    n = len(articles)
    if n == 0:
        return ""

    top_terms = _extract_top_terms(articles)
    term_str = "、".join(w for w, _ in top_terms) if top_terms else "—"

    journals = Counter(a.get("_journal") or a.get("journal", "") for a in articles)
    journal_str = "、".join(f"{j} {c} 篇" for j, c in journals.items() if j)

    summary = (
        f"本期 {category_name} 方向共收录 {n} 篇研究（{journal_str}）。"
        f"高频主题词包括:{term_str}。"
    )
    return summary


def build_classification_report(nature_articles, science_articles):
    """Classify combined corpus. Accepts the legacy (nature, science) signature
    but really just takes any two lists; both are merged before classification.
    """
    all_articles = (
        [{**a, "_journal": a.get("journal", "Nature")} for a in nature_articles]
        + [{**a, "_journal": a.get("journal", "Science")} for a in science_articles]
    )

    groups = classify_articles(all_articles)

    ordered = []
    for name, _ in CATEGORY_KEYWORDS:
        if groups.get(name):
            ordered.append(name)
    if groups.get(UNCATEGORIZED):
        ordered.append(UNCATEGORIZED)

    report = {
        "total_articles": len(all_articles),
        "categories": [
            {
                "name": cat,
                "articles": groups[cat],
                "summary": summarize_category(cat, groups[cat]),
            }
            for cat in ordered
        ],
    }
    logger.info(
        "Classified %d articles into %d categories",
        len(all_articles), len(report["categories"])
    )
    return report
