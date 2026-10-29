import gzip
import hashlib
import json
import os
import time
from pathlib import Path

import httpx

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

_client = httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True)
_last_call: dict[str, float] = {}


def _offline(source: str) -> bool:
    """OFFLINE=1 serves only cached data; OFFLINE=a,b does so for those sources."""
    flag = os.environ.get("OFFLINE", "")
    return flag == "1" or source in flag.split(",")


def _path(source: str, key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    if len(safe) > 120:
        safe = safe[:80] + "_" + hashlib.sha1(key.encode()).hexdigest()[:12]
    return RAW / source / f"{safe}.json.gz"


def cached_json(source: str, key: str, url: str, *, headers=None, params=None, delay=1.0, retries=4):
    """Fetch JSON once and keep the raw response under data/raw/<source>/ forever."""
    path = _path(source, key)
    if path.exists():
        with gzip.open(path, "rt") as f:
            return json.load(f)
    if _offline(source):
        return None
    for attempt in range(retries):
        wait = delay - (time.time() - _last_call.get(source, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[source] = time.time()
        try:
            r = _client.get(url, headers=headers, params=params)
        except httpx.HTTPError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            data = r.json()
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wt") as f:
                json.dump(data, f)
            return data
        if r.status_code == 404:
            return None
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"failed {url} after {retries} attempts")


def cached_text(source: str, key: str, url: str, *, params=None, delay=1.0) -> str | None:
    path = _path(source, key).with_suffix("").with_suffix(".html.gz")
    if path.exists():
        with gzip.open(path, "rt") as f:
            return f.read()
    if _offline(source):
        return None
    wait = delay - (time.time() - _last_call.get(source, 0))
    if wait > 0:
        time.sleep(wait)
    _last_call[source] = time.time()
    r = _client.get(url, params=params)
    if r.status_code != 200:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write(r.text)
    return r.text
