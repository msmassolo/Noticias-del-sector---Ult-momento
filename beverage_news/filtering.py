import logging
import re
from datetime import datetime, timezone, timedelta

from .models import Candidate
from .text import normalize_text, term_in_text
from .urls import domain_of, normalize_url

# Segmentos de path que indican página de login / paywall / suscripción
_LOGIN_PATH_RE = re.compile(
    r'/(login|signin|sign-in|signup|sign-up|subscribe|subscription|subscriber|register|account/login|auth|newsletter)(/|\?|$)',
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)

MAX_AGE_HOURS_MUNDIAL = 24 * 7
MAX_AGE_HOURS_LOCAL = 24 * 14
MAX_AGE_HOURS_REGIONAL = 24 * 14
MAX_PER_SOURCE = 18


def _is_too_old(published_str, region=None):
    if not published_str:
        return False
    try:
        parsed = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if region == "Regional":
            max_hours = MAX_AGE_HOURS_REGIONAL
        elif region == "Local":
            max_hours = MAX_AGE_HOURS_LOCAL
        else:
            max_hours = MAX_AGE_HOURS_MUNDIAL
        return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)) > timedelta(hours=max_hours)
    except (ValueError, TypeError):
        return False


GENERIC_KEYWORDS = {
    "beverage",
    "beverages",
    "drinks",
    "beer",
    "brewer",
    "brewery",
    "spirits",
    "wine",
    "winery",
    "soft drinks",
    "soda",
    "bottled water",
    "bottler",
    "bottling",
    "coffee",
    "tea",
    "grape must",
    "must",
    "cerveza",
    "cervecera",
    "vino",
    "bodega",
    "gaseosas",
    "refrescos",
    "bebidas",
    "mosto",
    "cerveja",
    "vinho",
    "refrigerantes",
    "engarrafadora",
    "engarrafamento",
}
GENERIC_KEYWORDS_NORMALIZED = {normalize_text(item) for item in GENERIC_KEYWORDS}
BEVERAGE_FOCUSED_SOURCES = {"Just Drinks", "Beverage Daily", "The Drinks Business"}
INDUSTRY_INTENT_TERMS = {
    "resultados",
    "ventas",
    "ingresos",
    "ganancias",
    "facturacion",
    "mercado",
    "negocio",
    "empresa",
    "compania",
    "compañia",
    "industria",
    "inversion",
    "adquisicion",
    "fusion",
    "planta",
    "produccion",
    "distribucion",
    "lanzamiento",
    "marca",
    "consumo",
    "precios",
    "exportaciones",
    "retail",
    "canal",
    "category",
    "earnings",
    "sales",
    "revenue",
    "profit",
    "market",
    "business",
    "company",
    "industry",
    "investment",
    "invests",
    "investing",
    "acquisition",
    "merger",
    "plant",
    "production",
    "distribution",
    "launch",
    "brand",
    "consumer",
    "pricing",
    "regulation",
    "tax",
    "labeling",
    "share",
    "volume",
    "volumes",
    "margins",
    "retailer",
}
STRONG_INDUSTRY_INTENT_TERMS = INDUSTRY_INTENT_TERMS - {"consumo", "consumer"}
LOW_VALUE_CONTEXT_TERMS = {
    "receta",
    "recetas",
    "salud",
    "hidratacion",
    "hidratan",
    "ciencia",
    "nutricion",
    "dieta",
    "medicos",
    "medico",
    "beneficios",
    "riñones",
    "rinones",
    "oxalatos",
    "higado",
    "hígado",
    "como preparar",
    "que pasa si",
    "viral",
    "ranking de",
    "curiosidad",
    "curiosidades",
    "lifestyle",
    "horoscopo",
    "clima",
    "pronostico",
    "health",
    "wellness tips",
    "recipe",
    "recipes",
    "nutrition",
    "diet",
    "doctor",
    "doctors",
    "benefits",
    "how to make",
}
CHANNEL_CONTEXT_TERMS = {
    "supermercado",
    "supermercados",
    "hipermercado",
    "mayorista",
    "mayoristas",
    "distribuidor",
    "distribuidora",
    "distribuidores",
    "transportadora",
    "retail",
    "varejo",
    "atacarejo",
    "franquia",
    "franquias",
    "restaurante",
    "restaurantes",
    "bar",
    "bares",
    "hotel",
    "hoteles",
    "horeca",
    "foodservice",
    "on premise",
    "on-premise",
    "off premise",
    "off-premise",
    "delivery",
    "domicilios",
    "ecommerce",
    "e-commerce",
    "marketplace",
    "conveniencia",
    "tienda de conveniencia",
    "loja de conveniencia",
}
BUSINESS_CONTEXT_TERMS = {
    "resultados",
    "ventas",
    "ingresos",
    "ganancias",
    "facturacion",
    "mercado",
    "negocio",
    "empresa",
    "compania",
    "compañia",
    "industria",
    "inversion",
    "adquisicion",
    "fusion",
    "planta",
    "produccion",
    "distribucion",
    "lanzamiento",
    "marca",
    "consumo",
    "precios",
    "exportaciones",
    "sales",
    "revenue",
    "profit",
    "market",
    "business",
    "company",
    "industry",
    "investment",
    "acquisition",
    "merger",
    "plant",
    "production",
    "distribution",
    "launch",
    "brand",
    "consumer",
    "pricing",
}


def match_companies(text, companies):
    matches = []
    for company in companies:
        names = [company.name, *company.aliases]
        if any(term_in_text(name, text) for name in names):
            matches.append(company)
    return matches


def match_keyword_categories(text, keywords):
    matches = {}
    for category, terms in keywords.items():
        found = [term for term in terms if term_in_text(term, text)]
        if found:
            matches[category] = found
    return matches


def segments_for(companies, keyword_matches):
    topics = sorted(dict.fromkeys(keyword_matches.keys()))
    if topics:
        return topics
    if companies:
        return ["company_news"]
    return []


def _candidate_text(candidate):
    return " ".join([candidate.title, candidate.summary, candidate.source])


def _candidate_title_text(candidate):
    return " ".join([candidate.title, candidate.source])


def _non_generic_keyword_count(keyword_matches):
    return sum(
        1
        for terms in keyword_matches.values()
        for term in terms
        if normalize_text(term) not in GENERIC_KEYWORDS_NORMALIZED
    )


def _has_beverage_context(text):
    return any(term_in_text(term, text) for term in GENERIC_KEYWORDS)


def _has_business_context(text):
    return any(term_in_text(term, text) for term in BUSINESS_CONTEXT_TERMS)


def _has_industry_intent(text):
    return any(term_in_text(term, text) for term in INDUSTRY_INTENT_TERMS)


def _has_strong_industry_intent(text):
    return any(term_in_text(term, text) for term in STRONG_INDUSTRY_INTENT_TERMS)


def _has_low_value_context(text):
    return any(term_in_text(term, text) for term in LOW_VALUE_CONTEXT_TERMS)


def _has_channel_context(text):
    return any(term_in_text(term, text) for term in CHANNEL_CONTEXT_TERMS)


def filter_candidates(candidates, companies, keywords, published_urls=None):
    published_urls = published_urls or {}
    diagnostics = {
        "input_candidates": len(candidates),
        "accepted": 0,
        "duplicates": 0,
        "already_published": 0,
        "too_old": 0,
        "discarded": {},
        "accepted_reasons": {},
        "by_source": {},
    }
    accepted = []
    seen_urls = set()
    seen_titles = set()
    source_counts = {}

    published_title_keys = {key for key in published_urls if key.startswith("title:")}

    for candidate in candidates:
        url = normalize_url(candidate.url, candidate.url)
        title_key = normalize_text(candidate.title)
        if (url and url in published_urls) or (f"title:{title_key}" in published_title_keys):
            diagnostics["already_published"] += 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue
        if not url or url in seen_urls or title_key in seen_titles:
            diagnostics["duplicates"] += 1
            continue
        if _LOGIN_PATH_RE.search(url):
            diagnostics["discarded"]["login_url"] = diagnostics["discarded"].get("login_url", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue
        if _is_too_old(candidate.published, candidate.region):
            diagnostics["too_old"] += 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue
        if candidate.require_section and not candidate.discovery.startswith("section:"):
            diagnostics["discarded"]["require_section"] = diagnostics["discarded"].get("require_section", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue
        source_key = candidate.source if candidate.source != "Google News" else (domain_of(candidate.url) or "Google News")
        source_stats = diagnostics["by_source"].setdefault(
            source_key,
            {"input": 0, "accepted": 0, "discarded": {}, "region": candidate.region},
        )
        source_stats["input"] += 1
        source_limit = MAX_PER_SOURCE * 4 if source_key == "news.google.com" else MAX_PER_SOURCE
        if source_counts.get(source_key, 0) >= source_limit:
            diagnostics["discarded"]["source_limit"] = diagnostics["discarded"].get("source_limit", 0) + 1
            source_stats["discarded"]["source_limit"] = source_stats["discarded"].get("source_limit", 0) + 1
            continue

        text = _candidate_text(candidate)
        title_text = _candidate_title_text(candidate)
        company_matches = match_companies(text, companies)
        keyword_matches = match_keyword_categories(text, keywords)
        title_keyword_matches = match_keyword_categories(title_text, keywords)
        keyword_hit_count = sum(len(terms) for terms in keyword_matches.values())
        non_generic_keyword_hit_count = _non_generic_keyword_count(keyword_matches)
        title_non_generic_count = _non_generic_keyword_count(title_keyword_matches)
        beverage_context = _has_beverage_context(text) or candidate.source in BEVERAGE_FOCUSED_SOURCES
        title_beverage_context = _has_beverage_context(title_text) or candidate.source in BEVERAGE_FOCUSED_SOURCES
        business_context = _has_business_context(text)
        industry_intent = _has_industry_intent(text)
        low_value_context = _has_low_value_context(text)
        channel_context = _has_channel_context(text)

        strategic_categories = {
            "financial_results",
            "ma_and_strategy",
            "distribution_execution",
            "regulation_tax_policy",
            "risk_crisis_reputation",
            "packaging_sustainability",
            "supply_chain_commodities",
        }
        has_strategic_category = bool(set(keyword_matches) & strategic_categories)
        if (
            low_value_context
            and not candidate.trade_source
            and not has_strategic_category
            and not channel_context
            and not _has_strong_industry_intent(text)
        ):
            diagnostics["discarded"]["low_value_context"] = diagnostics["discarded"].get("low_value_context", 0) + 1
            source_stats["discarded"]["low_value_context"] = source_stats["discarded"].get("low_value_context", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue

        reason = ""
        if company_matches and (beverage_context or candidate.trade_source or industry_intent or channel_context):
            reason = "company_match"
        elif (
            keyword_hit_count >= 2
            and non_generic_keyword_hit_count >= 1
            and beverage_context
            and industry_intent
        ):
            reason = "strong_keyword_match"
        elif (
            title_non_generic_count >= 1
            and title_beverage_context
            and industry_intent
        ):
            # Título suficientemente específico aunque el body sea corto
            reason = "title_keyword_match"
        elif candidate.trade_source and non_generic_keyword_hit_count >= 1 and beverage_context:
            reason = "trade_source_keyword_match"
        elif (
            candidate.region in {"Local", "Regional"}
            and (candidate.discovery.startswith("section:") or candidate.discovery.startswith("google_news:"))
            and beverage_context
            and business_context
        ):
            reason = "local_regional_beverage_section"
        elif (
            candidate.region in {"Local", "Regional"}
            and (candidate.discovery.startswith("section:") or candidate.discovery.startswith("google_news:"))
            and channel_context
            and (beverage_context or business_context)
        ):
            reason = "local_regional_channel_context"

        if not reason:
            diagnostics["discarded"]["weak_match"] = diagnostics["discarded"].get("weak_match", 0) + 1
            source_stats["discarded"]["weak_match"] = source_stats["discarded"].get("weak_match", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue

        segments = segments_for(company_matches, keyword_matches)
        keyword_categories = sorted(keyword_matches.keys())
        if reason == "local_regional_channel_context" and not segments:
            segments = ["distribution_execution"]
            keyword_categories = ["distribution_execution"]

        accepted.append(
            {
                "candidate": Candidate(**{**candidate.__dict__, "url": url}),
                "companies": [company.name for company in company_matches],
                "segments": segments,
                "keyword_categories": keyword_categories,
                "reason": reason,
            }
        )
        diagnostics["accepted"] += 1
        diagnostics["accepted_reasons"][reason] = diagnostics["accepted_reasons"].get(reason, 0) + 1
        source_stats["accepted"] += 1
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        seen_urls.add(url)
        seen_titles.add(title_key)

    logger.info(
        "Filtering: %d accepted / %d input (already_published=%d, too_old=%d, duplicates=%d, weak=%d)",
        diagnostics["accepted"],
        diagnostics["input_candidates"],
        diagnostics["already_published"],
        diagnostics["too_old"],
        diagnostics["duplicates"],
        diagnostics["discarded"].get("weak_match", 0),
    )
    return accepted, diagnostics
