import re
from collections import Counter
from datetime import datetime, timezone

from .text import normalize_text

CLICKBAIT_TITLE_PATTERNS = (
    re.compile(r"^(como|cómo)\s", re.IGNORECASE),
    re.compile(r"^(por que|por qué|porque)\s", re.IGNORECASE),
    re.compile(r"^(que|qué)\s+(es|pasa|significa|hace)\s", re.IGNORECASE),
    re.compile(r"^(guia|guía)\s+(para|de|completa)", re.IGNORECASE),
    re.compile(r"\blas?\s+\d+\s+(claves|consejos|secretos|razones|tips|cosas|maneras)\b", re.IGNORECASE),
    re.compile(r"\blos?\s+\d+\s+(mejores|peores|errores|trucos)\b", re.IGNORECASE),
    re.compile(r"^(top|ranking)\s+\d+", re.IGNORECASE),
    re.compile(r"\b(esto|esta|estos)\s+es\s+lo\s+que\b", re.IGNORECASE),
    re.compile(r"\b(te contamos|asi es como|así es como)\b", re.IGNORECASE),
)

GENERALIST_AR_SOURCES = {"Infobae", "Clarin", "La Nacion", "Ambito", "Cronista", "Perfil"}


REGION_ORDER = {"Local": 0, "Regional": 1, "Mundial": 2}
MIN_REGION_QUOTA = {"Local": 7, "Regional": 7, "Mundial": 7}

PRIORITY_COMPANIES = {
    "Red Bull",
    "Monster Beverage",
    "Celsius Holdings",
    "Olipop",
    "Poppi",
    "Fevertree Drinks",
    "AB InBev",
    "Diageo",
    "Campari Group",
    "Constellation Brands",
    "The Coca-Cola Company",
    "PepsiCo",
    "Coca-Cola FEMSA",
    "Arca Continental",
}

TOPIC_WEIGHTS = {
    "financial_results": 32,
    "product_innovation": 28,
    "ma_and_strategy": 26,
    "marketing_innovation": 24,
    "distribution_execution": 22,
    "regulation_tax_policy": 21,
    "risk_crisis_reputation": 20,
    "non_alcoholic_beverages": 19,
    "packaging_sustainability": 18,
    "alternative_ingredients": 17,
    "consumer_market_trends": 16,
    "supply_chain_commodities": 14,
    "company_news": 10,
}

SOURCE_WEIGHTS = {
    "Just Drinks": 18,
    "Beverage Daily": 18,
    "The Drinks Business": 17,
    "Brewbound": 17,
    "The Spirits Business": 17,
    "Wine Business": 16,
    "VinePair": 16,
    "SevenFifty Daily": 15,
    "Financial Times": 16,
    "Bloomberg": 16,
    "Reuters Business": 15,
    "Infobae": 10,
    "La Nacion": 10,
    "Clarin": 9,
    "Ambito": 9,
    "Cronista": 9,
    "Valor Economico": 10,
    "Diario Financiero": 9,
    "Gestion": 8,
    "Portafolio": 8,
}


def _parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def recency_score(value):
    parsed = _parse_date(value)
    if not parsed:
        return 0
    age_days = max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days, 0)
    if age_days <= 1:
        return 12
    if age_days <= 3:
        return 8
    if age_days <= 7:
        return 4
    return 0


def score_item(item):
    candidate = item["candidate"]
    score = 0
    score += SOURCE_WEIGHTS.get(candidate.source, 4)
    score += recency_score(candidate.published)

    topics = item.get("segments") or []
    if topics:
        score += max(TOPIC_WEIGHTS.get(topic, 0) for topic in topics)
        score += min(len(topics), 3) * 3

    companies = set(item.get("companies") or [])
    if companies:
        score += 28
        score += sum(10 for company in companies if company in PRIORITY_COMPANIES)

    if item.get("reason") == "company_match":
        score += 8
    elif item.get("reason") == "strong_keyword_match":
        score += 5
    elif item.get("reason") == "local_regional_beverage_section":
        score += 3

    if candidate.discovery.startswith("google_news"):
        # Google News redirect URLs fail extraction; deprioritize vs direct sources
        score -= 20

    # Penalización: títulos listicle / clickbait / explainer son menos
    # accionables para un dashboard de actualidad sectorial.
    title_norm = candidate.title or ""
    if any(pattern.search(title_norm) for pattern in CLICKBAIT_TITLE_PATTERNS):
        score -= 18

    # Penalización suave para diarios generalistas argentinos cuando NO hay
    # match de empresa: tienden a aportar notas tangenciales (curiosidades,
    # eventos sociales) que pasan los filtros pero no son negocio puro.
    if candidate.source in GENERALIST_AR_SOURCES and not companies:
        score -= 6

    return score


def rank_items(items):
    for item in items:
        item["score"] = score_item(item)
    return sorted(
        items,
        key=lambda item: (
            -item["score"],
            REGION_ORDER.get(item["candidate"].region, 9),
            item["candidate"].published or "",
            item["candidate"].title,
        ),
    )


def build_extraction_queue(items, limit=80, target_count=40, min_per_region=7):
    """
    Build an extraction queue that preserves ranking but reserves attempts by region.

    Selection already balances the final output, but doing it only after extraction
    lets global sources consume the whole extraction budget. This queue gives each
    region enough first-pass attempts when candidates exist, then fills by score.
    """
    by_region = {"Local": [], "Regional": [], "Mundial": []}
    for item in items:
        by_region.setdefault(item["candidate"].region or "Mundial", []).append(item)

    selected = []
    used_urls = set()

    def add(item):
        url = item["candidate"].url
        if url in used_urls or len(selected) >= limit:
            return False
        selected.append(item)
        used_urls.add(url)
        return True

    regional_attempts = max(min_per_region * 3, min(target_count // 2, 20))
    local_attempts = max(min_per_region * 2, min(target_count // 3, 14))
    mundial_attempts = max(min_per_region * 2, min(target_count // 3, 14))
    quotas = {
        "Regional": regional_attempts,
        "Local": local_attempts,
        "Mundial": mundial_attempts,
    }

    for region in ("Regional", "Local", "Mundial"):
        for item in by_region.get(region, [])[: quotas[region]]:
            add(item)

    for item in items:
        if len(selected) >= limit:
            break
        add(item)

    counts = Counter(item["candidate"].region or "Mundial" for item in selected)
    available = Counter(item["candidate"].region or "Mundial" for item in items)
    return selected, {
        "queued_by_region": dict(counts),
        "accepted_by_region": dict(available),
        "limit": limit,
        "regional_attempt_quota": regional_attempts,
        "local_attempt_quota": local_attempts,
        "mundial_attempt_quota": mundial_attempts,
    }


def select_balanced_articles(articles, target_count=40, min_per_region=7, region_targets=None):
    """
    Select balanced articles by region.

    region_targets: optional dict like {"Local": 5, "Regional": 5, "Mundial": 10}.
    When provided, each region is capped at exactly that many articles (acts as both
    min and max). Remaining slots after per-region caps are filled by score order.
    When absent, falls back to min_per_region behaviour (minimum per region, fill rest by score).
    """
    by_region = {"Local": [], "Regional": [], "Mundial": []}
    for article in articles:
        by_region.setdefault(article.region or "Mundial", []).append(article)

    selected = []
    used_urls = set()

    if region_targets:
        # Fill each region up to its specific target (cap)
        for region in ("Local", "Regional", "Mundial"):
            cap = region_targets.get(region, 0)
            for article in by_region.get(region, [])[:cap]:
                if article.url not in used_urls:
                    selected.append(article)
                    used_urls.add(article.url)
        # Fill remaining slots with best-scored articles of any region
        for article in articles:
            if len(selected) >= target_count:
                break
            if article.url not in used_urls:
                selected.append(article)
                used_urls.add(article.url)
    else:
        # Original behaviour: guarantee min per region, then fill by score
        for region in ("Local", "Regional", "Mundial"):
            quota = min_per_region if isinstance(min_per_region, int) else MIN_REGION_QUOTA.get(region, 7)
            for article in by_region.get(region, [])[:quota]:
                if article.url not in used_urls:
                    selected.append(article)
                    used_urls.add(article.url)
        for article in articles:
            if len(selected) >= target_count:
                break
            if article.url not in used_urls:
                selected.append(article)
                used_urls.add(article.url)

    counts = Counter(article.region or "Mundial" for article in selected)
    available = Counter(article.region or "Mundial" for article in articles)
    return selected[:target_count], {"selected_by_region": dict(counts), "available_by_region": dict(available)}
