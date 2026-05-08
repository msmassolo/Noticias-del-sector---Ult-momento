import json
from pathlib import Path

from .models import Company, Source


CONFIG_DIR = Path("config")


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_sources(path=CONFIG_DIR / "sources.json"):
    return [Source(**item) for item in _read_json(path)]


def load_companies(path=CONFIG_DIR / "companies.json"):
    return [Company(**item) for item in _read_json(path)]


def load_keywords(path=CONFIG_DIR / "keywords.json"):
    data = _read_json(path)
    return {str(category): [str(term) for term in terms] for category, terms in data.items()}
