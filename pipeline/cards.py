"""Per-year share cards (1200x630 PNG) and share pages carrying their Open Graph tags."""
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "web" / "public"
FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
SITE = "https://ballondor.anas.link"
W, H = 1200, 630
PAD = 72

# Must match DEFAULTS in web/src/model.ts.
WEIGHTS = {"output": 50, "big": 25, "trophy": 25, "consistency": 0}
FAIRNESS = 0.7


def oklch(l: float, c: float, h: float) -> tuple[int, int, int]:
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_, m_, s_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3, (l - 0.1055613458 * a - 0.0638541728 * b) ** 3, (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    def gamma(x):
        x = min(max(x, 0.0), 1.0)
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return tuple(round(gamma(x) * 255) for x in rgb)


# The site's tokens (web/tokens.css).
PAPER = oklch(0.17, 0.030, 262)
SHEET = oklch(0.21, 0.032, 262)
INK = oklch(0.94, 0.014, 85)
INK2 = oklch(0.86, 0.014, 85)
MUTED = oklch(0.70, 0.018, 255)
RULE = oklch(0.31, 0.028, 262)
GOLD = oklch(0.81, 0.135, 84)


def font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    if weight:
        f.set_variation_by_axes([weight] if "opsz" not in name else [weight, min(max(size, 6), 72)])
    return f


def display(size): return font("HankenGrotesk[wght].ttf", size, 600)
def body(size): return font("Newsreader[opsz,wght].ttf", size, 400)
def mono(size): return font("IBMPlexMono-Medium.ttf", size)


def fit(draw, text, maker, size, max_w):
    while size > 24:
        f = maker(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return maker(size)


def score(c: dict) -> float:
    total = sum(WEIGHTS.values())
    blend = lambda p, a: FAIRNESS * (p if p is not None else -1) + (1 - FAIRNESS) * (a if a is not None else -1)
    return (WEIGHTS["output"] * blend(c["o"], c["oa"]) + WEIGHTS["big"] * blend(c["b"], c["ba"])
            + WEIGHTS["trophy"] * (c["t"] if c["t"] is not None else -1)
            + WEIGHTS["consistency"] * (c["k"] if c["k"] is not None else -1)) / total


def eligible(c: dict, rule: str) -> bool:
    if rule == "open":
        return True
    if rule == "european_clubs":
        return c["eclub"] is not False
    return c["euro"] is not False and c["eclub"] is not False


def verdict(y: dict, players: dict) -> dict:
    ranked = sorted((c for c in y["c"] if eligible(c, y["rule"])), key=score, reverse=True)
    model = ranked[0]
    real = next((r for r in y["real"] if r["rank"] == 1), None)
    order = [c["id"] for c in ranked]
    real_rank = order.index(real["id"]) + 1 if real and real["id"] in order else None
    real_score = score(ranked[real_rank - 1]) if real_rank else None
    return {
        "year": y["year"],
        "model": players[model["id"]]["n"],
        "real": (players.get(real["id"], {}).get("n") if real and real["id"] else None) or (real["name"] if real else None),
        "same": bool(real and real["id"] == model["id"]),
        "real_rank": real_rank,
        "margin": None if real_score is None else score(model) - real_score,
    }


def draw_card(v: dict, out: Path):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 6], fill=INK)
    d.text((PAD, 52), "The actual Ballon d’Or", font=display(30), fill=INK)
    d.text((W - PAD, 52), str(v["year"]), font=mono(30), fill=MUTED, anchor="ra")
    d.line([PAD, 112, W - PAD, 112], fill=RULE, width=1)

    max_w = W - 2 * PAD
    if v["real"] is None:
        d.text((PAD, 160), "Not awarded that year. The count says:", font=body(36), fill=INK2)
        f = fit(d, v["model"], display, 112, max_w)
        d.text((PAD, 220), v["model"], font=f, fill=GOLD)
    elif v["same"]:
        d.text((PAD, 160), "The vote and the count agree:", font=body(36), fill=INK2)
        f = fit(d, v["model"], display, 112, max_w)
        d.text((PAD, 220), v["model"], font=f, fill=GOLD)
    else:
        d.text((PAD, 150), "Won it", font=body(30), fill=MUTED)
        f = fit(d, v["real"], display, 60, max_w)
        d.text((PAD, 188), v["real"], font=f, fill=INK2)
        x0, y0, x1, y1 = d.textbbox((PAD, 188), v["real"], font=f)
        d.line([x0, (y0 + y1) // 2 + 4, x1, (y0 + y1) // 2 + 4], fill=MUTED, width=4)
        d.text((PAD, 292), "Should have", font=body(30), fill=MUTED)
        f = fit(d, v["model"], display, 112, max_w)
        d.text((PAD, 326), v["model"], font=f, fill=GOLD)

    d.line([PAD, 520, W - PAD, 520], fill=RULE, width=1)
    facts = []
    if not v["same"] and v["real_rank"]:
        facts.append(f"Real winner ranks {v['real_rank']} on the count")
    if v["margin"]:
        facts.append(f"margin +{v['margin']:.2f}")
    d.text((PAD, 548), ", ".join(facts) if facts else "Scored from match data, default weights", font=body(28), fill=MUTED)
    d.text((W - PAD, 548), "ballondor.anas.link", font=mono(26), fill=INK2, anchor="ra")
    im.save(out, optimize=True)


def share_page(v: dict) -> str:
    y = v["year"]
    if v["real"] is None:
        title = f"{y}: not awarded. The count says {v['model']}"
    elif v["same"]:
        title = f"{y}: {v['model']} deserved it"
    else:
        title = f"{y}: {v['real']} won it. {v['model']} should have"
    t = html.escape(title)
    desc = html.escape("The Ballon d’Or re-scored from match data, expected goals, big games and trophies.")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{t}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}/y/{y}/">
<meta property="og:image" content="{SITE}/cards/{y}.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/cards/{y}.png">
<link rel="canonical" href="{SITE}/?y={y}">
<meta http-equiv="refresh" content="0; url=/?y={y}#explorer">
</head><body><p><a href="/?y={y}#explorer">{t}</a></p></body></html>
"""


def overview_card(vs: list[dict], out: Path):
    awarded = [v for v in vs if v["real"] is not None]
    changed = sum(not v["same"] for v in awarded)
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 6], fill=INK)
    d.text((PAD, 52), "The actual Ballon d’Or", font=display(30), fill=INK)
    d.line([PAD, 112, W - PAD, 112], fill=RULE, width=1)
    d.text((PAD, 150), str(changed), font=mono(220), fill=GOLD)
    w = d.textlength(str(changed), font=mono(220))
    d.text((PAD + w + 32, 300), f"of {len(awarded)} awards", font=display(56), fill=INK)
    d.text((PAD + w + 32, 372), "change hands on the count.", font=body(40), fill=INK2)
    d.line([PAD, 520, W - PAD, 520], fill=RULE, width=1)
    d.text((PAD, 548), "1956 to 2026, scored from match data", font=body(28), fill=MUTED)
    d.text((W - PAD, 548), "ballondor.anas.link", font=mono(26), fill=INK2, anchor="ra")
    im.save(out, optimize=True)


def main():
    data = json.loads((PUBLIC / "data.json").read_text())
    (PUBLIC / "cards").mkdir(exist_ok=True)
    vs = [verdict(y, data["players"]) for y in data["years"]]
    for v in vs:
        draw_card(v, PUBLIC / "cards" / f"{v['year']}.png")
        page = PUBLIC / "y" / str(v["year"])
        page.mkdir(parents=True, exist_ok=True)
        (page / "index.html").write_text(share_page(v))
    overview_card(vs, PUBLIC / "cards" / "og.png")
    print(f"{len(vs)} cards and share pages written")


if __name__ == "__main__":
    main()
