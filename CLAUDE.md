# CLAUDE.md

Guía técnica para trabajar en este repositorio.

## Propósito

Este proyecto es un monitor automatizado de noticias del sector de bebidas. Genera un dashboard HTML estático con artículos relevantes para consumo masivo de bebidas en cobertura Local, Regional y Mundial.

No hay backend ni base de datos. El estado operativo está en archivos:

- `config/*.json`: fuentes, empresas y keywords.
- `published_urls.json`: deduplicación rolling de URLs y títulos publicados.
- `data/*.json`: intermedios y diagnósticos de cada corrida.
- `index.html`: salida web generada.

## Entrada principal

```powershell
python main.py
```

Argumentos:

- `--output`: ruta del HTML generado. Default: `index.html`.
- `--limit`: máximo de candidatos que se intentan extraer. Default: `80`.
- `--target-count`: máximo editorial flexible de artículos finales. Default: `60`.
- `--min-per-region`: cuota mínima por Local/Regional/Mundial si hay disponibilidad. Default: `7`.
- `--max-search-queries`: límite de búsquedas globales por empresa en Google News. Default: `55`.
- `--no-search`: desactiva Google News RSS.
- `--min-body-length`: mínimo de caracteres de body para publicar. Default: `80`.
- `--debug`: logging debug.

## Pipeline

La orquestación está en `beverage_news/pipeline.py`:

1. Carga `sources`, `companies` y `keywords`.
2. Descubre candidatos con `discover_candidates`.
3. Escribe `data/candidates.json`.
4. Filtra con `filter_candidates`.
5. Rankea con `rank_items`.
6. Crea una cola balanceada con `build_extraction_queue`.
7. Extrae artículos en paralelo con `extract_article_item`.
8. Valida con `validate_articles`.
9. Selecciona con `select_balanced_articles`.
10. Escribe `data/articles.json` y `data/diagnostics.json`.
11. Actualiza `published_urls.json`.
12. Genera `index.html` con `generate_web`.

## Módulos clave

### `discovery.py`

Canales de discovery:

- RSS explícitos de `sources.json`.
- RSS detectados desde `<link rel="alternate">`.
- Secciones HTML configuradas, recorriendo links `<a>`.
- Google News RSS con queries globales, locales, regionales ES y regionales PT/BR.

Mejora importante: para Google News se parsea el HTML de la descripción RSS y se prefiere el primer enlace del medio original antes que el redirect de `news.google.com`.

### `filtering.py`

Filtra antes de gastar extracción:

- Deduplicación por URL y título normalizados.
- Rechazo de URLs ya publicadas.
- Rechazo de login, registro, newsletter, subscriber y suscripción.
- Ventanas de antigüedad por región.
- Límite por fuente para evitar que una sola fuente domine la cola.
- Aceptación por empresa, keywords fuertes, título específico, fuente trade o contexto local/regional.
- Rechazo de contextos de baja utilidad: salud, recetas, clima, curiosidades y lifestyle cuando no hay señales de industria.

El diagnóstico incluye `by_source`, motivos de descarte y motivos de aceptación.

### `ranking.py`

Calcula score por:

- Fuente.
- Recencia.
- Tópicos.
- Empresas encontradas.
- Empresas prioritarias.
- Motivo de aceptación.
- Penalización a redirects de Google News si todavía aparecen.

`build_extraction_queue` reserva intentos por región antes de completar por score. Esto evita que la extracción quede monopolizada por fuentes globales cuando hay candidatos regionales disponibles.

### `extraction.py`

Extrae:

- URL final, con resolución básica de Google News si todavía llega una URL de `news.google.com`.
- Título, resumen, fecha y body desde JSON-LD.
- Metadatos OpenGraph/Twitter.
- Párrafos dentro de `<article>`, `<main>` o el documento.
- Summary del candidato como fallback si el body no alcanza el mínimo.

El body se recorta a `MAX_BODY_CHARS = 12000` y se remueve boilerplate conocido.

### `validation.py`

Valida después de extraer:

- Título vacío, corto, demasiado largo, genérico o truncado.
- Body de paywall, login o newsletter.
- Body repetitivo.
- Relevancia industrial sobre título, resumen y body.

La validación permite publicar notas con empresa o fuente trade, pero exige señales de negocio/industria para notas generalistas.

### `web.py`

Genera un HTML estático con:

- Búsqueda client-side.
- Filtros por cobertura y tópico.
- Agrupación por tópico principal.
- Enlaces a original y traducción.
- Body expandible.

No editar `index.html` a mano.

## Configuración

### `config/sources.json`

Campos:

- `name`
- `url`
- `rss`
- `sections`
- `country`
- `region`: `Local`, `Regional` o `Mundial`
- `language`
- `trade`
- `require_section` opcional

Para mejorar cobertura regional conviene priorizar fuentes con RSS confiable o secciones estables de negocios, consumo, empresas, bebidas, alimentos y retail.

### `config/companies.json`

Campos:

- `name`
- `country`
- `segments`
- `aliases`

Los aliases son críticos para Brasil/LATAM. Agregar nombres legales, marcas, embotelladoras, traducciones y variantes sin acentos.

### `config/keywords.json`

Diccionario de categorías a términos. El matching es accent-insensitive y basado en límites de palabra.

Evitar términos demasiado genéricos si no vienen acompañados por señales de industria. Si se agregan términos amplios, reforzar tests de falsos positivos.

## Diagnóstico operativo

`target-count` no es una cuota fija. El objetivo es publicar todas las noticias relevantes dentro de un dashboard razonable: una corrida puede tener 40, 50 o 60 artículos según la actividad real del día. No rellenar con baja calidad solo para alcanzar un número.

Después de cada corrida revisar:

- `discovery.source_errors` y `discovery.section_errors`: fuentes rotas o bloqueadas.
- `filtering.discarded`: filtros demasiado estrictos o candidatos de baja calidad.
- `filtering.by_source`: fuentes que aportan basura o buenas señales.
- `queue.queued_by_region`: distribución antes de extracción.
- `extraction.by_source` y `extraction.by_region`: extractabilidad real.
- `validation.by_reason`: paywalls, títulos genéricos o baja relevancia.
- `selection.selected_by_region`: balance final.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Agregar tests cuando se cambien:

- Reglas de aceptación/rechazo.
- Keywords genéricas o aliases ambiguos.
- Resolución de Google News.
- Cola regional.
- Extractores o validación post-extracción.

## Convenciones

- No editar `index.html` manualmente.
- No commitear `data/`.
- Mantener UTF-8.
- No hardcodear tokens.
- Limpiar `__pycache__` después de correr pruebas si se generan.
- Preservar diagnósticos porque son la herramienta principal para mejorar cobertura y calidad.
