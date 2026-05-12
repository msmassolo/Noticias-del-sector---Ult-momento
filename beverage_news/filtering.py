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

MAX_AGE_HOURS_MUNDIAL = 36
MAX_AGE_HOURS_LOCAL = 36
MAX_AGE_HOURS_REGIONAL = 36
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
RETAIL_OPS_NOISE_TERMS = {
    # Cambios operativos de retail genericos: horarios, aperturas/cierres
    # puntuales, calendarios de tiendas. Aunque la cadena (Walmart, Sam's Club,
    # Carrefour) este en companies, una nota de horarios no es relevante para
    # noticias del sector de bebidas.
    "cambia su horario", "cambian su horario", "modifica su horario",
    "modifican su horario", "nuevos horarios", "nuevo horario",
    "operara a partir", "operaran a partir", "abriran a partir",
    "abrira a partir", "horario de atencion", "horario especial",
    "horario extendido", "horario reducido", "atencion al publico",
    "estaran cerrados", "estara cerrado", "permanecera cerrado",
    "permaneceran cerrados", "feriado bancario",
    "promocion del dia", "promociones del dia", "ofertas del dia",
    "que tiendas abren", "que tiendas estan abiertas",
    "changes its hours", "store hours", "holiday hours",
}

OFF_TOPIC_TERMS = {
    # Automotor / repuestos / movilidad (caso "líderes mayoristas de repuestos")
    "repuestos", "autopartes", "autoparte", "automotor", "automotriz",
    "concesionaria", "concesionarias", "neumaticos", "neumático",
    "lubricantes", "motos", "motocicleta", "motocicletas", "camiones",
    "camionetas", "scooter", "scooters",
    # Otros rubros que pueden compartir vocabulario (mayorista/distribución/marca)
    "ferreteria", "electrodomesticos", "indumentaria", "calzado", "moda",
    "juguetes", "cosmetica", "perfumeria", "farmacia", "farmacias",
    "construccion", "inmobiliaria", "inmuebles", "muebles",
    # Tecnología de consumo
    "smartphone", "smartphones", "celulares", "videojuegos", "gaming",
    "criptomonedas", "cripto", "bitcoin",
    # Deportes / espectáculos
    "futbol", "fútbol", "tenis", "boxeo", "automovilismo", "formula 1",
    "espectaculo", "espectáculos", "farandula", "farándula",
}

HISTORICAL_CLICKBAIT_TITLE_TERMS = {
    "sabias que", "sabías que", "asi nacio", "así nació", "así nacio",
    "como nacio", "cómo nació", "como nació",
    "la historia de", "la historia detras", "la historia detrás",
    "el origen de", "el origen fronterizo", "el verdadero origen",
    "conoce la historia", "conocé la historia", "conoce el origen",
    "te contamos la historia", "te contamos como",
    "hace anos", "hace años",  # plantillas tipo "hace 50 años..."
    "efemerides", "efemérides", "un dia como hoy", "un día como hoy",
    "remember when", "back in", "the story behind", "the origin of",
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


def _has_off_topic_rubro(text):
    return any(term_in_text(term, text) for term in OFF_TOPIC_TERMS)


def _has_retail_ops_noise(text):
    normalized = normalize_text(text)
    return any(term in normalized for term in (normalize_text(t) for t in RETAIL_OPS_NOISE_TERMS))


def _is_historical_clickbait_title(title):
    normalized = normalize_text(title)
    return any(term in normalized for term in HISTORICAL_CLICKBAIT_TITLE_TERMS)


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

        # Rechazo por ruido operativo de retail: cambios de horario, aperturas
        # puntuales, feriados, ofertas del dia, etc. No son noticias del sector
        # de bebidas aun si la cadena (Walmart, Sam's Club, Carrefour) figura
        # en companies.json. Se aplica antes del check de empresa.
        if _has_retail_ops_noise(text):
            diagnostics["discarded"]["retail_ops_noise"] = diagnostics["discarded"].get("retail_ops_noise", 0) + 1
            source_stats["discarded"]["retail_ops_noise"] = source_stats["discarded"].get("retail_ops_noise", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue

        # Rechazo por rubro off-topic: la nota habla de otro rubro que comparte
        # vocabulario (repuestos automotrices, ferretería, electrodomésticos, etc.)
        # aun si el matcher disparó por "mayorista", "distribución" o "marca".
        if _has_off_topic_rubro(text) and not company_matches and not candidate.trade_source:
            diagnostics["discarded"]["off_topic_rubro"] = diagnostics["discarded"].get("off_topic_rubro", 0) + 1
            source_stats["discarded"]["off_topic_rubro"] = source_stats["discarded"].get("off_topic_rubro", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue

        # Rechazo de títulos histórico/clickbait ("¿Sabías que...?", "La historia de...",
        # "El origen de..."): no son noticias actuales, son curiosidades/efemérides.
        if _is_historical_clickbait_title(candidate.title) and not candidate.trade_source:
            diagnostics["discarded"]["historical_clickbait"] = diagnostics["discarded"].get("historical_clickbait", 0) + 1
            source_stats["discarded"]["historical_clickbait"] = source_stats["discarded"].get("historical_clickbait", 0) + 1
            seen_urls.add(url)
            seen_titles.add(title_key)
            continue

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

        # Si TODAS las empresas matcheadas requieren contexto de industria
        # explicito (alias ambiguo) y no hay industry_intent fuerte ni canal,
        # tratar el match como no efectivo.
        if (
            company_matches
            and all(getattr(c, "requires_industry_context", False) for c in company_matches)
            and not _has_strong_industry_intent(text)
            and not channel_context
        ):
            diagnostics["discarded"]["company_needs_context"] = diagnostics["discarded"].get("company_needs_context", 0) + 1
            source_stats["discarded"]["company_needs_context"] = source_stats["discarded"].get("company_needs_context", 0) + 1
            company_matches = []

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

    # Deduplicación semántica: misma noticia tomada por varios medios suele
    # compartir 6-8 palabras significativas iniciales del título. Quedarse con
    # la primera ocurrencia (la mejor rankeada llegará desde rank_items igual,
    # pero acá ya se reduce ruido temprano).
    STOP = {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
        "en", "y", "o", "a", "para", "por", "con", "sin", "que", "es", "se",
        "su", "sus", "al", "lo", "the", "a", "an", "of", "in", "on", "for",
        "and", "or", "to", "is", "as", "at",
    }
    def _semantic_key(title):
        words = [w for w in normalize_text(title).split() if w and w not in STOP]
        return " ".join(words[:7])
    seen_semantic = {}
    deduped = []
    for entry in accepted:
        key = _semantic_key(entry["candidate"].title)
        if not key:
            deduped.append(entry)
            continue
        if key in seen_semantic:
            diagnostics["discarded"]["semantic_duplicate"] = diagnostics["discarded"].get("semantic_duplicate", 0) + 1
            diagnostics["accepted"] -= 1
            reason = entry["reason"]
            diagnostics["accepted_reasons"][reason] = max(0, diagnostics["accepted_reasons"].get(reason, 0) - 1)
            continue
        seen_semantic[key] = True
        deduped.append(entry)
    accepted = deduped

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
