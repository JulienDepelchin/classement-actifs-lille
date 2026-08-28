"""
Genere la liste des gares a suivre dans le poller GTFS-RT :
  - les 2 gares de Lille (Flandres, Europe)
  - les gares "utiles" de chaque commune candidate (desserte directe reguliere vers Lille)

Sortie : data/rt/gares_suivies.csv  (uic, nom, role)   -- a versionner
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = ROOT / "data" / "output" / "transport_communes_candidates.csv"
GARES = ROOT / "data" / "interim" / "gares_ter_communes.csv"
OUT = ROOT / "data" / "rt" / "gares_suivies.csv"

LILLE = {"87286005": "Lille Flandres", "87223263": "Lille Europe"}


def main() -> None:
    tr = pd.read_csv(TRANSPORT, dtype={"gare_utile_uic": str})
    g = pd.read_csv(GARES, dtype={"uic": str}).drop_duplicates("uic").set_index("uic")["stop_name"]

    rows = [{"uic": u, "nom": n, "role": "lille"} for u, n in LILLE.items()]
    for u in sorted(tr["gare_utile_uic"].dropna().unique()):
        if u in LILLE:
            continue
        rows.append({"uic": u, "nom": g.get(u, "?"), "role": "gare_utile"})

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{len(df)} gares suivies ({(df.role=='gare_utile').sum()} utiles + {(df.role=='lille').sum()} Lille)")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
