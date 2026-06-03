import argparse
import logging
import shutil
import sys
from pathlib import Path

# Bibliotecas instaladas localmente (no en el intérprete del sistema)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "Bibliotecas" / "Bibliotecas py"))

from dotenv import load_dotenv

from beverage_news.pipeline import run_pipeline


def _clear_pycache():
    for cache_dir in Path(".").rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)


def _setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build a private global beverage news monitor.")
    parser.add_argument("--output", default="index.html", help="HTML output path.")
    parser.add_argument("--limit", type=int, default=40,
                        help="Maximum ranked candidates to attempt extracting. "
                             "Use 120 for production, 40 for testing.")
    parser.add_argument("--target-count", type=int, default=20,
                        help="Total articles target. Testing default: 20. Production: 50.")
    parser.add_argument("--local-count", type=int, default=5,
                        help="Target number of Local (Argentina) articles.")
    parser.add_argument("--regional-count", type=int, default=5,
                        help="Target number of Regional (LATAM) articles.")
    parser.add_argument("--mundial-count", type=int, default=10,
                        help="Target number of Mundial (Global) articles.")
    parser.add_argument("--min-per-region", type=int, default=3,
                        help="Fallback minimum per region (used only if per-region counts not set).")
    parser.add_argument("--max-search-queries", type=int, default=30,
                        help="Maximum global company/search queries for Google News RSS. "
                             "Use 90 for production, 30 for testing.")
    parser.add_argument("--no-search", action="store_true",
                        help="Disable Google News RSS discovery and use configured RSS only.")
    parser.add_argument("--min-body-length", type=int, default=80,
                        help="Minimum body characters required to publish an article.")
    parser.add_argument("--production", action="store_true",
                        help="Run with production defaults: limit=120, target=50, "
                             "local=8, regional=8, mundial=34, max-search-queries=90.")
    parser.add_argument("--debug", action="store_true", help="Enable debug-level logging.")
    args = parser.parse_args()

    # --production overrides all count/limit defaults
    if args.production:
        limit = 120
        target_count = 50
        local_count = 8
        regional_count = 8
        mundial_count = 34
        max_search_queries = 90
    else:
        limit = args.limit
        target_count = args.target_count
        local_count = args.local_count
        regional_count = args.regional_count
        mundial_count = args.mundial_count
        max_search_queries = args.max_search_queries

    region_targets = {
        "Local": local_count,
        "Regional": regional_count,
        "Mundial": mundial_count,
    }

    _setup_logging(level=logging.DEBUG if args.debug else logging.INFO)

    articles, diagnostics = run_pipeline(
        output_path=args.output,
        enable_search=not args.no_search,
        limit=limit,
        target_count=target_count,
        min_per_region=args.min_per_region,
        max_search_queries=max_search_queries,
        min_body_chars=args.min_body_length,
        region_targets=region_targets,
    )
    _clear_pycache()
    print(f"Generated {args.output} with {len(articles)} articles.")
    print(f"Diagnostics written to data/diagnostics.json.")


if __name__ == "__main__":
    main()
