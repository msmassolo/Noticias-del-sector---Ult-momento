import json
import logging
from pathlib import Path

from .models import Company, Source

CONFIG_DIR = Path("config")
logger = logging.getLogger(__name__)


def _read_json(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _validate_source(item, index):
    for field in ("name", "url"):
        if not item.get(field):
            raise ValueError(f"sources.json[{index}] missing required field '{field}': {item}")
    region = item.get("region", "Mundial")
    if region not in {"Local", "Regional", "Mundial"}:
        raise ValueError(f"sources.json[{index}] invalid region '{region}' (must be Local/Regional/Mundial)")


def _validate_company(item, index):
    for field in ("name", "country", "segments"):
        if not item.get(field) and item.get(field) != []:
            raise ValueError(f"companies.json[{index}] missing required field '{field}': {item}")
    if not isinstance(item.get("segments", []), list):
        raise ValueError(f"companies.json[{index}] 'segments' must be a list")


def load_sources(path=CONFIG_DIR / "sources.json"):
    items = _read_json(path)
    if not isinstance(items, list):
        raise ValueError(f"{path} must be a JSON array")
    for i, item in enumerate(items):
        _validate_source(item, i)
    sources = [Source(**item) for item in items]
    logger.debug("Config: loaded %d sources from %s", len(sources), path)
    return sources


def load_companies(path=CONFIG_DIR / "companies.json"):
    items = _read_json(path)
    if not isinstance(items, list):
        raise ValueError(f"{path} must be a JSON array")
    for i, item in enumerate(items):
        _validate_company(item, i)
    companies = [Company(**item) for item in items]
    logger.debug("Config: loaded %d companies from %s", len(companies), path)
    return companies


def load_keywords(path=CONFIG_DIR / "keywords.json"):
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    keywords = {str(category): [str(term) for term in terms] for category, terms in data.items()}
    logger.debug("Config: loaded %d keyword categories from %s", len(keywords), path)
    return keywords
