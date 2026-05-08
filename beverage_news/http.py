import logging
import time
import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.8,es;q=0.7,pt;q=0.6",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

logger = logging.getLogger(__name__)


def fetch_text(url, timeout=4, retries=2):
    last_status = ""
    for attempt in range(retries + 1):
        try:
            response = SESSION.get(url, timeout=timeout)
            if response.status_code != 200:
                return "", f"http_{response.status_code}"
            if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
                response.encoding = response.apparent_encoding or "utf-8"
            return response.text, "ok"
        except requests.exceptions.Timeout:
            last_status = "timeout"
            logger.debug("Timeout on attempt %d/%d: %s", attempt + 1, retries + 1, url)
        except requests.exceptions.RequestException as exc:
            return "", f"request_error:{exc.__class__.__name__}"
        if attempt < retries:
            delay = 2 ** attempt  # 1s, 2s, 4s…
            time.sleep(delay)
    return "", last_status
