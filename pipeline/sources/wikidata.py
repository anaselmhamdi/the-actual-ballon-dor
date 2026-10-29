import hashlib

from pipeline.http import cached_json
from pipeline.sources.wikipedia import API as WIKI_API
from pipeline.sources.wikipedia import WIKI_HEADERS

API = "https://www.wikidata.org/w/api.php"
TM_PLAYER_ID = "P2446"


def _key(items: list[str]) -> str:
    return hashlib.sha1("|".join(items).encode()).hexdigest()[:16]


def _qids(titles: list[str]) -> dict[str, str]:
    """Resolve Wikipedia titles (following redirects) to Wikidata QIDs."""
    data = cached_json("wikipedia", f"qids_{_key(titles)}", WIKI_API, headers=WIKI_HEADERS, delay=0.5,
                       params={"action": "query", "titles": "|".join(titles), "redirects": 1,
                               "prop": "pageprops", "ppprop": "wikibase_item", "format": "json", "formatversion": 2}) or {}
    q = data.get("query", {})
    alias: dict[str, str] = {t: t for t in titles}
    for step in q.get("normalized", []) + q.get("redirects", []):
        for src, dst in list(alias.items()):
            if dst == step["from"]:
                alias[src] = step["to"]
    by_title = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in q.get("pages", [])}
    return {t: by_title.get(alias[t]) for t in titles if by_title.get(alias[t])}


def transfermarkt_ids(titles: list[str]) -> dict[str, str | None]:
    """Map English Wikipedia titles to Transfermarkt player IDs."""
    titles = sorted(set(titles))
    qid_of: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        qid_of.update(_qids(titles[i : i + 50]))
    qids = sorted(set(qid_of.values()))
    tm_of: dict[str, str | None] = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        data = cached_json("wikidata", f"ents_{_key(chunk)}", API, headers=WIKI_HEADERS, delay=0.5,
                           params={"action": "wbgetentities", "ids": "|".join(chunk), "props": "claims", "format": "json"}) or {}
        for qid, ent in data.get("entities", {}).items():
            claims = ent.get("claims", {}).get(TM_PLAYER_ID, [])
            tm_of[qid] = claims[0]["mainsnak"].get("datavalue", {}).get("value") if claims else None
    return {t: tm_of.get(qid_of.get(t, ""), None) for t in titles}
