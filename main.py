import argparse
import shutil
from pathlib import Path

from dotenv import load_dotenv

from beverage_news.pipeline import run_pipeline


def _clear_pycache():
    for cache_dir in Path(".").rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build a private global beverage news monitor.")
    parser.add_argument("--output", default="index.html", help="HTML output path.")
    parser.add_argument("--limit", type=int, default=80, help="Maximum ranked candidates to attempt extracting.")
    parser.add_argument("--target-count", type=int, default=40, help="Target number of articles to publish.")
    parser.add_argument("--min-per-region", type=int, default=7, help="Minimum target per Local/Regional/Mundial when available.")
    parser.add_argument("--max-search-queries", type=int, default=55, help="Maximum global company/search queries for Google News RSS.")
    parser.add_argument("--no-search", action="store_true", help="Disable Google News RSS discovery and use configured RSS only.")
    args = parser.parse_args()

    articles, diagnostics = run_pipeline(
        output_path=args.output,
        enable_search=not args.no_search,
        limit=args.limit,
        target_count=args.target_count,
        min_per_region=args.min_per_region,
        max_search_queries=args.max_search_queries,
    )
    _clear_pycache()
    print(f"Generated {args.output} with {len(articles)} articles.")
    print(f"Diagnostics written to data/diagnostics.json.")


if __name__ == "__main__":
    main()
