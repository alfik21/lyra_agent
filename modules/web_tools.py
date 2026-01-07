import json
import re
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
CACHE_PATH = BASE_DIR / "logs" / "web_cache.json"


def _load_config():
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _get_cache_ttl():
    cfg = _load_config()
    try:
        return int(cfg.get("web_cache_ttl_sec", 21600))
    except Exception:
        return 21600


def _get_whitelist():
    cfg = _load_config()
    whitelist = cfg.get("web_whitelist") or []
    if isinstance(whitelist, str):
        whitelist = [whitelist]
    return [w.lower().strip() for w in whitelist if str(w).strip()]


def _load_cache():
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(data):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _filter_results(results, whitelist):
    if not whitelist:
        return results
    out = []
    for r in results:
        url = (r.get("url") or "").lower()
        if any(w in url for w in whitelist):
            out.append(r)
    return out


def _ddg_api_search(query: str, limit: int = 5):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("Results", []):
            text = item.get("Text")
            u = item.get("FirstURL")
            if text and u:
                results.append({"title": text, "url": u, "snippet": ""})
                if len(results) >= limit:
                    return results

        def _walk_related(items):
            for it in items or []:
                if "Topics" in it:
                    for sub in _walk_related(it.get("Topics", [])):
                        yield sub
                else:
                    text = it.get("Text")
                    u = it.get("FirstURL")
                    if text and u:
                        yield (text, u)

        for text, u in _walk_related(data.get("RelatedTopics", [])):
            results.append({"title": text, "url": u, "snippet": ""})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


def _ddg_html_search(query: str, limit: int = 5):
    try:
        url = "https://duckduckgo.com/html/"
        r = requests.get(url, params={"q": query}, timeout=10)
        if r.status_code != 200:
            return []
        html = r.text
        titles = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html)
        results = []
        for idx, (href, title) in enumerate(titles):
            title = re.sub(r"<.*?>", "", title).strip()
            snippet = ""
            if idx < len(snippets):
                snippet = re.sub(r"<.*?>", "", snippets[idx]).strip()
            if title and href:
                results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []

def _brave_search(query: str, limit: int = 5):
    try:
        url = "https://search.brave.com/search"
        r = requests.get(url, params={"q": query}, timeout=10)
        if r.status_code != 200:
            return []
        html = r.text
        matches = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html)
        results = []
        for href, title in matches:
            if "brave.com" in href:
                continue
            title = re.sub(r"<.*?>", "", title).strip()
            if title and href:
                results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []

def _simplify_query(query: str):
    stop = {"najnowszy", "najnowsze", "wydanie", "model", "telefon", "informacje", "o", "na", "temat"}
    parts = [p for p in re.split(r"\s+", query.lower()) if p and p not in stop]
    return " ".join(parts).strip()


def _wiki_opensearch(query: str, limit: int = 5):
    try:
        api = "https://pl.wikipedia.org/w/api.php"
        params = {"action": "opensearch", "search": query, "limit": limit, "namespace": 0, "format": "json"}
        r = requests.get(api, params=params, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
        titles = data[1] if len(data) > 1 else []
        links = data[3] if len(data) > 3 else []
        results = []
        for t, u in zip(titles, links):
            results.append({"title": t, "url": u, "snippet": ""})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


def internet_search(query: str, limit: int = 5, use_cache: bool = True):
    if not query:
        return "ERROR: brak zapytania"
    query = query.strip()
    ttl = _get_cache_ttl()
    cache = _load_cache() if use_cache else {}
    key = query.lower()
    if key in cache and use_cache:
        try:
            entry = cache[key]
            if time.time() - float(entry.get("ts", 0)) <= ttl:
                return entry.get("results", [])
        except Exception:
            pass

    results = _ddg_html_search(query, limit=limit)
    if not results:
        results = _ddg_api_search(query, limit=limit)
    if not results:
        results = _wiki_opensearch(query, limit=limit)
    if not results:
        results = _brave_search(query, limit=limit)
    if not results:
        simplified = _simplify_query(query)
        if simplified and simplified != query.lower():
            results = _ddg_html_search(simplified, limit=limit)
            if not results:
                results = _ddg_api_search(simplified, limit=limit)
            if not results:
                results = _wiki_opensearch(simplified, limit=limit)
            if not results:
                results = _brave_search(simplified, limit=limit)

    whitelist = _get_whitelist()
    results = _filter_results(results, whitelist)

    if use_cache:
        cache[key] = {"ts": time.time(), "results": results}
        _save_cache(cache)
    return results or []


def fetch_url(url: str, max_chars: int = 8000):
    try:
        if url.startswith("https://"):
            target = url[len("https://"):]
        elif url.startswith("http://"):
            target = url[len("http://"):]
        else:
            target = url
        j_url = f"https://r.jina.ai/http://{target}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(j_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            return resp.text[:max_chars]
    except Exception:
        pass
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return ""
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


def build_adapter_block(results):
    lines = []
    for i, r in enumerate(results, start=1):
        title = r.get("title") or ""
        url = r.get("url") or ""
        snippet = r.get("snippet") or ""
        line = f"{i}) {title} - {url}"
        if snippet:
            line += f"\n   {snippet}"
        lines.append(line)
    return "\n".join(lines).strip()
