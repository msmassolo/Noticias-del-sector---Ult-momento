from dataclasses import asdict
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo


TOPIC_LABELS = {
    "product_innovation": "Innovación de producto",
    "marketing_innovation": "Marketing e innovación",
    "financial_results": "Resultados financieros",
    "ma_and_strategy": "M&A / estrategia",
    "distribution_execution": "Distribución y ejecución",
    "regulation_tax_policy": "Regulación y política",
    "packaging_sustainability": "Packaging y sustentabilidad",
    "consumer_market_trends": "Tendencias de consumo",
    "supply_chain_commodities": "Cadena de suministro",
    "risk_crisis_reputation": "Riesgo y reputación",
    "non_alcoholic_beverages": "Bebidas sin alcohol",
    "alternative_ingredients": "Ingredientes alternativos",
    "company_news": "Noticias de empresas",
}

TOPIC_ORDER = {topic: index for index, topic in enumerate(TOPIC_LABELS)}
REGION_ORDER = {"Local": 0, "Regional": 1, "Mundial": 2}


def _uniq(values):
    return sorted(dict.fromkeys(value for value in values if value))


def _label_topic(value):
    return TOPIC_LABELS.get(value, value.replace("_", " ").title())


def _sort_topics(values):
    return sorted(values, key=lambda value: (TOPIC_ORDER.get(value, len(TOPIC_ORDER)), value))


def _sort_regions(values):
    return sorted(values, key=lambda value: (REGION_ORDER.get(value, len(REGION_ORDER)), value))


def _article_dict(article):
    data = asdict(article) if hasattr(article, "__dataclass_fields__") else dict(article)
    data["segments"] = _sort_topics(_uniq(data.get("segments") or []))
    data["companies"] = _uniq(data.get("companies") or [])
    data["keyword_categories"] = _uniq(data.get("keyword_categories") or [])
    data["region"] = data.get("region") or "Mundial"
    return data


def _chips(values, css_class="chip"):
    return "".join(f'<span class="{css_class}">{escape(str(value))}</span>' for value in values)


def _filter_buttons(name, values, labels=None):
    buttons = [f'<button class="filter active" type="button" data-filter="{name}" data-value="ALL">All</button>']
    for value in values:
        label = labels.get(value, value) if labels else value
        buttons.append(
            f'<button class="filter" type="button" data-filter="{name}" data-value="{escape(value, quote=True)}">{escape(label)}</button>'
        )
    return "".join(buttons)


def _article_html(article):
    segments = article["segments"]
    companies = article["companies"]
    keywords = article["keyword_categories"]
    search = " ".join(
        [
            article["title"],
            article["summary"],
            article["body"],
            article["source"],
            article["country"],
            article["region"],
            article["language"],
            " ".join(companies),
            " ".join(segments),
            " ".join(keywords),
        ]
    )

    meta = " · ".join(item for item in [article["region"], article["source"], article["country"], article["language"], article["published"]] if item)
    body_html = escape(article["body"]).replace("\n", "<br>")
    summary = article["summary"] or "No source summary available."

    translate_url = f"https://translate.google.com/translate?sl=auto&tl=es&u={escape(article['url'], quote=True)}"
    return f"""
        <article class="news-card"
            data-search="{escape(search, quote=True)}"
            data-segments="{escape('|'.join(segments), quote=True)}"
            data-companies="{escape('|'.join(companies), quote=True)}"
            data-region="{escape(article['region'], quote=True)}"
            data-country="{escape(article['country'], quote=True)}"
            data-source="{escape(article['source'], quote=True)}"
            data-language="{escape(article['language'], quote=True)}">
            <div class="card-topline">
                <span>{escape(meta)}</span>
            </div>
            <h2>{escape(article["title"])}</h2>
            <p class="summary">{escape(summary)}</p>
            <div class="card-actions">
                <a class="original-btn" href="{escape(article['url'], quote=True)}" target="_blank" rel="noopener noreferrer">Leer nota original</a>
                <a class="translate-btn" href="{translate_url}" target="_blank" rel="noopener noreferrer">Traducir al español</a>
            </div>
            <details>
                <summary>Texto completo del artículo</summary>
                <div class="body-text">{body_html}</div>
            </details>
        </article>
    """


def _sections_html(article_dicts):
    if not article_dicts:
        return '<p class="empty-state">No articles passed the current filters or extraction rules.</p>'

    grouped = {}
    for article in article_dicts:
        primary = article["segments"][0] if article["segments"] else "company_news"
        grouped.setdefault(primary, []).append(article)

    sections = []
    for topic in _sort_topics(grouped):
        items = grouped[topic]
        cards = "\n".join(_article_html(article) for article in items)
        sections.append(
            f"""
            <section class="topic-section" data-topic="{escape(topic, quote=True)}">
                <div class="section-heading">
                    <h2>{escape(_label_topic(topic))}</h2>
                    <span>{len(items)} articles</span>
                </div>
                <div class="grid">
                    {cards}
                </div>
            </section>
            """
        )
    return "\n".join(sections)


def generate_web(articles, diagnostics=None, output_path="index.html"):
    article_dicts = [_article_dict(article) for article in articles]
    now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

    segments = _sort_topics(_uniq(segment for article in article_dicts for segment in article["segments"]))
    companies = _uniq(company for article in article_dicts for company in article["companies"])
    regions = _sort_regions(_uniq(article["region"] for article in article_dicts))
    countries = _uniq(article["country"] for article in article_dicts)
    sources = _uniq(article["source"] for article in article_dicts)
    languages = _uniq(article["language"] for article in article_dicts)

    sections_html = _sections_html(article_dicts)

    diagnostics = diagnostics or {}
    discovery_count = diagnostics.get("discovery", {}).get("candidates_found", 0)
    accepted_count = diagnostics.get("filtering", {}).get("accepted", 0)
    extracted_count = diagnostics.get("extraction", {}).get("extracted", len(article_dicts))
    selected_by_region = diagnostics.get("selection", {}).get("selected_by_region", {})
    region_stats = " · ".join(f"{region}: {selected_by_region.get(region, 0)}" for region in ("Local", "Regional", "Mundial"))

    html = f"""<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Monitor de Noticias — Sector Bebidas</title>
    <style>
        * {{ box-sizing: border-box; }}
        :root {{
            --bg: #f5f6f4;
            --surface: #ffffff;
            --surface-soft: #eef1ef;
            --text: #1d2328;
            --muted: #5d6770;
            --border: #d8ddd9;
            --accent: #0e5f57;
            --accent-soft: #dcebe7;
            --amber: #8b5e12;
        }}
        body {{
            margin: 0;
            color: var(--text);
            background: var(--bg);
            font-family: Arial, Helvetica, sans-serif;
            letter-spacing: 0;
        }}
        header, main {{
            max-width: 1280px;
            margin: 0 auto;
            padding: 22px 18px;
        }}
        header {{
            padding-bottom: 10px;
        }}
        .eyebrow {{
            margin: 0 0 7px;
            color: var(--accent);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        h1 {{
            margin: 0;
            font-size: 34px;
            line-height: 1.08;
        }}
        .intro {{
            max-width: 860px;
            margin: 10px 0 0;
            color: var(--muted);
            font-size: 15px;
            line-height: 1.5;
        }}
        .timestamp {{
            margin: 6px 0 0;
            color: var(--muted);
            font-size: 12px;
        }}
        .stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }}
        .stat {{
            min-height: 34px;
            padding: 8px 10px;
            border: 1px solid var(--border);
            border-radius: 7px;
            background: var(--surface);
            color: var(--muted);
            font-size: 12px;
        }}
        .stat strong {{
            color: var(--text);
            font-size: 15px;
        }}
        .toolbar {{
            display: grid;
            grid-template-columns: minmax(240px, 1fr) auto;
            gap: 8px;
            margin-top: 14px;
        }}
        input[type="search"] {{
            width: 100%;
            min-height: 38px;
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 0 12px;
            background: var(--surface);
            color: var(--text);
            font-size: 14px;
        }}
        .clear-btn {{
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 0 12px;
            background: var(--surface);
            cursor: pointer;
            font-weight: 700;
        }}
        .filter-panel {{
            margin-top: 16px;
            padding: 14px 16px;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--surface);
        }}
        .filter-panel-title {{
            margin: 0 0 12px;
            font-size: 14px;
            font-weight: 700;
            color: var(--text);
        }}
        .filter-row {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            margin-top: 8px;
        }}
        .filter-row:first-of-type {{
            margin-top: 0;
        }}
        .filter-row-label {{
            min-width: 80px;
            padding-top: 5px;
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            flex-shrink: 0;
        }}
        .filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .filter {{
            min-height: 29px;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0 9px;
            background: var(--bg);
            color: var(--muted);
            cursor: pointer;
            font-size: 12px;
            font-weight: 700;
        }}
        .filter.active {{
            border-color: var(--accent);
            background: var(--accent-soft);
            color: var(--accent);
        }}
        .result-count {{
            margin: 14px 0 8px;
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .topic-section {{
            margin-top: 18px;
        }}
        .section-heading {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 6px;
        }}
        .section-heading h2 {{
            margin: 0;
            font-size: 22px;
            line-height: 1.15;
        }}
        .section-heading span {{
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }}
        .news-card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            background: var(--surface);
        }}
        .card-topline {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 8px;
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .card-topline a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .news-card h2 {{
            margin: 0 0 8px;
            font-size: 19px;
            line-height: 1.22;
        }}
        .summary {{
            margin: 0 0 12px;
            color: var(--muted);
            font-size: 14px;
            line-height: 1.45;
        }}
        .card-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 10px;
        }}
        .original-btn, .translate-btn {{
            display: inline-flex;
            align-items: center;
            min-height: 31px;
            border-radius: 6px;
            padding: 0 10px;
            font-size: 12px;
            font-weight: 700;
            text-decoration: none;
        }}
        .original-btn {{
            border: 1px solid var(--accent);
            color: var(--accent);
            background: var(--accent-soft);
        }}
        .translate-btn {{
            border: 1px solid var(--border);
            color: var(--muted);
            background: var(--surface-soft);
        }}
        .original-btn:hover, .translate-btn:hover {{
            filter: brightness(0.97);
        }}
        details {{
            border-top: 1px solid var(--border);
            padding-top: 9px;
        }}
        details summary {{
            cursor: pointer;
            color: var(--accent);
            font-size: 13px;
            font-weight: 700;
        }}
        .body-text {{
            margin-top: 10px;
            color: var(--text);
            font-size: 14px;
            line-height: 1.55;
            white-space: normal;
        }}
        .empty-state {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 18px;
            background: var(--surface);
            color: var(--muted);
            text-align: center;
        }}
        @media (max-width: 860px) {{
            h1 {{ font-size: 28px; }}
            .toolbar {{ grid-template-columns: 1fr; }}
            .grid {{ grid-template-columns: 1fr; }}
            .filter-row {{ flex-direction: column; gap: 6px; }}
            .filter-row-label {{ min-width: unset; padding-top: 0; }}
        }}
    </style>
</head>
<body>
    <header>
        <p class="eyebrow">Monitor privado · Sector bebidas</p>
        <h1>Noticias del sector</h1>
        <p class="intro">Este resumen recopila las noticias de último momento del sector global de bebidas —&nbsp;desde innovación de producto y movimientos corporativos hasta tendencias de consumo y cambios regulatorios&nbsp;— para mantenerse al tanto de lo que ocurre en la industria, desarrollar los mejores productos, ofrecer los mejores servicios y obtener las mejores rentabilidades.</p>
        <p class="timestamp">Actualizado el {escape(now.strftime("%d/%m/%Y a las %H:%M"))} (hora Buenos Aires) · {len(article_dicts)} artículos · {escape(region_stats)}</p>
        <div class="toolbar">
            <input type="search" id="search" placeholder="Buscar por título, empresa, fuente o país…" aria-label="Buscar artículos">
            <button class="clear-btn" type="button" id="clear">Limpiar</button>
        </div>
        <div class="filter-panel">
            <p class="filter-panel-title">¿Cómo querés filtrar las noticias?</p>
            <div class="filter-row">
                <span class="filter-row-label">Geografía</span>
                <div class="filters">{_filter_buttons("region", regions)}</div>
            </div>
            <div class="filter-row">
                <span class="filter-row-label">Área</span>
                <div class="filters">{_filter_buttons("segments", segments, TOPIC_LABELS)}</div>
            </div>
        </div>
    </header>
    <main>
        <p class="result-count" id="count"></p>
        <div id="sections">
            {sections_html}
        </div>
        <p class="empty-state" id="empty" hidden>No articles match the current filters.</p>
    </main>
    <script>
        const search = document.querySelector("#search");
        const clear = document.querySelector("#clear");
        const count = document.querySelector("#count");
        const empty = document.querySelector("#empty");
        const cards = Array.from(document.querySelectorAll(".news-card"));
        const sections = Array.from(document.querySelectorAll(".topic-section"));
        const activeFilters = new Map();

        function normalize(text) {{
            return (text || "").toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, "");
        }}

        function cardHas(card, filter, value) {{
            if (value === "ALL") return true;
            const raw = card.dataset[filter] || "";
            if (filter === "segments" || filter === "companies") {{
                return raw.split("|").includes(value);
            }}
            return raw === value;
        }}

        function applyFilters() {{
            const terms = normalize(search.value).split(/\\s+/).filter((term) => term.length >= 2);
            let visible = 0;
            cards.forEach((card) => {{
                const text = normalize(card.dataset.search || "");
                const matchesSearch = terms.every((term) => text.includes(term));
                const matchesFilters = Array.from(activeFilters.entries()).every(([filter, value]) => cardHas(card, filter, value));
                const show = matchesSearch && matchesFilters;
                card.hidden = !show;
                if (show) visible += 1;
            }});
            sections.forEach((section) => {{
                const sectionCards = Array.from(section.querySelectorAll(".news-card"));
                section.hidden = sectionCards.every((card) => card.hidden);
            }});
            count.textContent = `${{visible}} visible articles`;
            empty.hidden = visible !== 0;
        }}

        document.querySelectorAll(".filter").forEach((button) => {{
            button.addEventListener("click", () => {{
                const filter = button.dataset.filter;
                const value = button.dataset.value;
                document.querySelectorAll(`.filter[data-filter="${{filter}}"]`).forEach((item) => item.classList.remove("active"));
                button.classList.add("active");
                if (value === "ALL") activeFilters.delete(filter);
                else activeFilters.set(filter, value);
                applyFilters();
            }});
        }});
        search.addEventListener("input", applyFilters);
        clear.addEventListener("click", () => {{
            search.value = "";
            activeFilters.clear();
            document.querySelectorAll(".filter").forEach((button) => button.classList.toggle("active", button.dataset.value === "ALL"));
            applyFilters();
        }});
        applyFilters();
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)
