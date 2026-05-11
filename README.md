# Global Beverage News Monitor

Monitor automatizado de noticias del sector de bebidas. Recolecta candidatos desde fuentes directas y Google News, filtra por relevancia sectorial, extrae contenido publicable, prioriza los mejores artículos y genera un `index.html` navegable para GitHub Pages.

El foco es consumo masivo de bebidas: gaseosas, cerveza, vino, espirituosos, agua, energizantes, RTD, bebidas funcionales, ingredientes, envases, distribución, regulación, resultados financieros y movimientos corporativos.

## Monitor publicado

[Abrir monitor de noticias](https://msmassolo.github.io/Noticias-del-sector---Ult-momento/)

## Flujo del pipeline

```text
Config -> Discovery -> Filtering -> Ranking -> Balanced Queue -> Extraction -> Validation -> Selection -> HTML
```

1. Carga fuentes, empresas y keywords desde `config/`.
2. Descubre candidatos desde RSS, feeds detectados, secciones HTML y Google News RSS.
3. En Google News intenta usar la URL original del medio desde el HTML del RSS antes de guardar un redirect de `news.google.com`.
4. Normaliza URLs, remueve tracking params y deduplica por URL/título.
5. Filtra candidatos viejos, repetidos, ya publicados, de login/newsletter/suscripción o con match débil.
6. Rechaza notas de baja utilidad sectorial, como salud, recetas, clima o curiosidades, cuando no tienen ángulo de industria, negocio, mercado, regulación, marca o empresa.
7. Rankea por fuente, recencia, tema, empresa, prioridad estratégica y motivo de aceptación.
8. Construye una cola de extracción balanceada por región para que Regional y Local tengan intentos reales antes de completar con Global.
9. Extrae contenido desde JSON-LD, metadatos y párrafos del artículo.
10. Valida título, paywall, repetición y relevancia industrial post-extracción.
11. Selecciona hasta `target-count` artículos respetando cuota regional cuando hay disponibilidad. Ese valor es un máximo preferido, no una obligación de relleno.
12. Genera `index.html` y actualiza `published_urls.json` para evitar republicaciones durante 7 días.

## Cobertura configurada

El proyecto monitorea fuentes globales, argentinas y regionales LATAM.

### Global

Medios trade y de negocio como Just Drinks, FoodBev Media, The Drinks Business, The Spirits Business, Brewbound, VinePair, Wine Business, Beverage Industry, Beverage Daily, Harpers Wine & Spirit, Food Navigator, Reuters Business, Bloomberg y Financial Times.

### Argentina

Infobae, La Nación, Clarín, Ámbito, Cronista, iProfesional, Los Andes, MDZ, La Voz, Mercado, El Economista, Forbes Argentina, BAE Negocios, Perfil, Wines of Argentina, Coviar, Vinos y Bodegas, Planeta Joy, Ciudadano News y Vinetur Argentina.

### Regional LATAM

Valor Econômico, Exame, Infomoney, DFSud, América Economía, America Retail, Diario Financiero, La Tercera, El Mostrador, Gestión, El Comercio Perú, Portafolio, La República Colombia, El Financiero México, Expansión México, El Observador y BN Americas.

## Temas monitoreados

- `financial_results`
- `product_innovation`
- `ma_and_strategy`
- `marketing_innovation`
- `distribution_execution`
- `regulation_tax_policy`
- `risk_crisis_reputation`
- `non_alcoholic_beverages`
- `packaging_sustainability`
- `alternative_ingredients`
- `consumer_market_trends`
- `supply_chain_commodities`

## Estructura

```text
Noticias del sector/
├── main.py                    # CLI del pipeline
├── publish_github.py          # Publicación opcional vía GitHub Contents API
├── index.html                 # Salida generada; no editar a mano
├── published_urls.json        # Historial rolling de URLs/títulos publicados
├── requirements.txt
├── beverage_news/
│   ├── config.py              # Carga y valida JSON de configuración
│   ├── discovery.py           # RSS, secciones HTML y Google News RSS
│   ├── filtering.py           # Reglas de aceptación/rechazo
│   ├── ranking.py             # Scoring, cola balanceada y selección final
│   ├── extraction.py          # Extracción de título, resumen, fecha y body
│   ├── validation.py          # Depuración post-extracción
│   ├── web.py                 # Generación del HTML
│   ├── http.py                # Cliente HTTP
│   ├── text.py                # Limpieza, normalización y matching
│   ├── urls.py                # Normalización de URLs
│   └── models.py              # Dataclasses
├── config/
│   ├── sources.json
│   ├── companies.json
│   └── keywords.json
├── data/                      # Diagnósticos e intermedios generados
└── tests/
    └── test_core.py
```

## Ejecución local

```powershell
pip install -r requirements.txt
python main.py
```

Opciones útiles:

```powershell
python main.py --target-count 60 --limit 120 --max-search-queries 90
python main.py --min-per-region 10
python main.py --no-search
python main.py --debug
python main.py --min-body-length 80
```

## Automatización

GitHub Actions ejecuta `.github/workflows/update-news.yml` 6 veces por día:

- 06:00 ART
- 08:00 ART
- 11:00 ART
- 14:00 ART
- 17:00 ART
- 20:00 ART

El workflow instala dependencias, corre `python main.py`, agrega `index.html` y `published_urls.json`, commitea si hubo cambios y hace `git push`.

## Diagnósticos

Cada ejecución escribe JSON intermedios en `data/`:

- `candidates.json`: candidatos descubiertos.
- `accepted_candidates.json`: candidatos aceptados y enviados a extracción.
- `articles.json`: artículos finales seleccionados.
- `diagnostics.json`: métricas de discovery, filtering, queue, extraction, validation y selection.

Los diagnósticos incluyen conteos por fuente, región, motivo de aceptación, motivo de descarte, errores de extracción y rechazos de validación. Esto permite detectar si un problema viene de fuentes rotas, filtros demasiado estrictos, mala extractabilidad o falta de candidatos regionales.

`--target-count` funciona como un máximo editorial flexible. Si hay menos noticias buenas, el monitor publica menos; si el día viene cargado, se puede subir el valor sin tocar el resto del pipeline.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Los tests cubren normalización de URLs, matching accent-insensitive, deduplicación, filtros de baja calidad, extracción, resolución de enlaces originales de Google News, cola regional balanceada y validación post-extracción.
