import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from pipeline.http import cached_json

API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "the-actual-ballon-dor/0.1 (https://ballondor.anas.link)"}


def page_html(title: str) -> str | None:
    data = cached_json(
        "wikipedia",
        f"page_{title}",
        API,
        headers=WIKI_HEADERS,
        params={"action": "parse", "page": title, "format": "json", "prop": "text", "formatversion": 2, "redirects": 1},
        delay=0.5,
    )
    if not data or "parse" not in data:
        return None
    return data["parse"]["text"]


def expand_table(table) -> list[list]:
    """Return the table as a grid of cells with rowspan/colspan expanded."""
    grid: list[list] = []
    pending: dict[int, tuple[int, object]] = {}
    for tr in table.find_all("tr"):
        row = []
        cells = iter(tr.find_all(["td", "th"], recursive=False))
        col = 0
        while True:
            if col in pending:
                left, cell = pending[col]
                row.append(cell)
                if left > 1:
                    pending[col] = (left - 1, cell)
                else:
                    del pending[col]
                col += 1
                continue
            cell = next(cells, None)
            if cell is None:
                break
            span = int(re.sub(r"\D", "", cell.get("colspan", "1")) or 1)
            rspan = int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1)
            for _ in range(span):
                row.append(cell)
                if rspan > 1:
                    pending[col] = (rspan - 1, cell)
                col += 1
        while col in pending:
            left, cell = pending[col]
            row.append(cell)
            if left > 1:
                pending[col] = (left - 1, cell)
            else:
                del pending[col]
            col += 1
        grid.append(row)
    return grid


def _player_link(cell) -> str | None:
    for a in cell.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/wiki/") and ":" not in href[6:] and not a.find("img") and a.get_text(strip=True):
            return unquote(href[6:]).replace("_", " ")
    return None


def _number(text: str) -> float | None:
    text = text.replace(",", ".").strip()
    m = re.search(r"\d+(\.\d+)?", text)
    return float(m.group()) if m else None


def ballon_dor_votes(year: int) -> list[dict]:
    titles = [f"{year} FIFA Ballon d'Or", f"{year} Ballon d'Or"] if 2010 <= year <= 2015 else [f"{year} Ballon d'Or"]
    html = None
    for t in titles:
        html = page_html(t)
        if html:
            break
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table", class_="wikitable"):
        grid = expand_table(table)
        if not grid:
            continue
        header = [c.get_text(" ", strip=True).lower() for c in grid[0]]
        pts_col = next((i for i, h in enumerate(header) if h.startswith(("points", "votes", "percent", "%"))), None)
        player_col = next((i for i, h in enumerate(header) if h in ("player", "name") or h.startswith("player")), None)
        rank_col = next((i for i, h in enumerate(header) if h.startswith(("rank", "pos", "place"))), 0)
        if pts_col is None or player_col is None:
            continue
        rows = []
        for r in grid[1:]:
            if len(r) <= max(pts_col, player_col):
                continue
            link = _player_link(r[player_col])
            pts = _number(r[pts_col].get_text(" ", strip=True))
            rank = _number(r[rank_col].get_text(" ", strip=True)) if rank_col < len(r) else None
            if link and rank:
                rows.append({"year": year, "rank": int(rank), "wiki": link,
                             "name": re.sub(r"\s*\[[^\]]*\]", "", r[player_col].get_text(" ", strip=True)), "points": pts})
        if not rows:
            continue
        # FIFA-era pages split the men's ranking over several tables; a restart at rank 1 is the women's award.
        if out and rows[0]["rank"] <= out[-1]["rank"]:
            break
        out.extend(rows)
    return out
