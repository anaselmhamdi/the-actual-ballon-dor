"""Collect real Ballon d'Or votes and the candidate pool, keyed by Transfermarkt ID."""
import json
from pathlib import Path

from pipeline.sources import wikidata, wikipedia

OUT = Path(__file__).resolve().parent.parent / "data" / "out"
YEARS = [y for y in range(1956, 2027) if y != 2020]

# Players the award structurally excluded (non-Europeans before 1995, non-European clubs before 2007).
EXTRA_WIKI = [
    "Pelé", "Garrincha", "Didi (footballer, born 1928)", "Nílton Santos", "Djalma Santos", "Vavá",
    "Zico (footballer)", "Sócrates", "Paulo Roberto Falcão", "Diego Maradona", "Mario Kempes",
    "Daniel Passarella", "Romário", "Bebeto", "Careca", "Hugo Sánchez", "Enzo Francescoli", "Elías Figueroa",
    "Teófilo Cubillas", "Rivellino", "Tostão", "Jairzinho", "Carlos Alberto Torres", "Gérson",
    "Ricardo Bochini", "Alberto Spencer", "Jorge Valdano", "Claudio Caniggia", "Roger Milla", "Abedi Pele",
    "Rabah Madjer", "Carlos Valderrama", "Dunga", "Jorginho (footballer, born 1964)", "Branco (footballer)",
    "Raí", "Juan Román Riquelme", "Ronaldinho", "Ronaldo (Brazilian footballer)", "Rivaldo", "Cafu",
    "Roberto Carlos", "Gabriel Batistuta", "Juan Sebastián Verón", "Hernán Crespo", "Javier Zanetti",
    "Iván Zamorano", "Marcelo Salas", "Enzo Scifo", "Héctor Chumpitaz", "Ubaldo Fillol", "Ladislao Mazurkiewicz",
    "Ademir da Guia", "Sándor Kocsis", "Ferenc Puskás", "Lev Yashin",
]


def main():
    votes = []
    for y in YEARS:
        rows = wikipedia.ballon_dor_votes(y)
        print(y, len(rows))
        votes.extend(rows)
    titles = {v["wiki"] for v in votes} | set(EXTRA_WIKI)
    tm = wikidata.transfermarkt_ids(sorted(titles))
    missing = sorted(t for t, i in tm.items() if not i)
    for v in votes:
        v["tm_id"] = tm.get(v["wiki"])
    pool = {i: t for t, i in tm.items() if i}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "votes.json").write_text(json.dumps(votes, ensure_ascii=False, indent=1))
    (OUT / "pool_wiki.json").write_text(json.dumps(pool, ensure_ascii=False, indent=1))
    print(f"{len(votes)} vote rows, {len(titles)} players, {len(pool)} with TM id, missing: {missing}")


if __name__ == "__main__":
    main()
