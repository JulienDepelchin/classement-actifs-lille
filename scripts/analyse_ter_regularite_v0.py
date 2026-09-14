"""
Premiere lecture (non definitive) de la regularite TER NPDC a partir des snapshots
data/rt/ter_npdc/<date>/<poll>.csv.gz collectes depuis le 31 aout.

Methode : pour chaque passage (date_service, trip_id, uic), on garde le DERNIER etat connu
(dernier poll ou ce passage apparait) -- comme prevu pour build_regularite_reelle.py, en plus
simple (pas encore de jointure GTFS statique pour le nom de ligne : on raisonne par gare).

C'est un premier passage exploratoire, pas le classement final des lignes.
"""
from __future__ import annotations
import sys
import gzip
import glob
import csv
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "rt" / "ter_npdc"
GARES = ROOT / "data" / "rt" / "gares_npdc.csv"


def main() -> None:
    files = sorted(glob.glob(str(SRC / "*" / "*.csv.gz")))
    print(f"{len(files)} fichiers de poll a lire ({files[0][-27:-20]} -> {files[-1][-27:-20]})")

    last: dict[tuple, dict] = {}
    for n, p in enumerate(files, 1):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (r["date_service"], r["trip_id"], r["uic"])
                last[key] = r
        if n % 1000 == 0:
            print(f"  {n}/{len(files)} fichiers | {len(last):,} passages distincts")

    print(f"\n{len(last):,} passages (date_service x trip x gare) au dernier etat connu")
    df = pd.DataFrame(last.values())
    df["arr_delay_s"] = pd.to_numeric(df["arr_delay_s"], errors="coerce")
    df["trip_annule"] = pd.to_numeric(df["trip_annule"], errors="coerce").fillna(0)
    df["stop_saute"] = pd.to_numeric(df["stop_saute"], errors="coerce").fillna(0)

    n_dates = df["date_service"].nunique()
    print(f"dates de service couvertes : {n_dates} ({df['date_service'].min()} -> {df['date_service'].max()})")

    trips = df.drop_duplicates(["date_service", "trip_id"])
    print(f"\ntrains distincts (date x trip_id) : {len(trips):,}")
    print(f"  annules (trip_annule=1 sur au moins 1 passage) : "
          f"{df[df.trip_annule==1]['trip_id'].nunique():,} trip_id distincts")

    obs = df[df["arr_delay_s"].notna()]
    print(f"\npassages avec un retard d'arrivee connu : {len(obs):,} / {len(df):,} "
          f"({len(obs)/len(df)*100:.0f} %)")
    if len(obs):
        retard5 = (obs["arr_delay_s"] > 300).mean() * 100
        retard2 = (obs["arr_delay_s"] > 120).mean() * 100
        print(f"  retard > 5 min : {retard5:.1f} % | retard > 2 min : {retard2:.1f} % | "
              f"retard median {obs['arr_delay_s'].median():.0f}s | p90 {obs['arr_delay_s'].quantile(.9):.0f}s")

    print("\n=== par role (lille = gares de Lille, npdc = reste 59/62) ===")
    for role, g in df.groupby("role"):
        o = g[g["arr_delay_s"].notna()]
        r5 = (o["arr_delay_s"] > 300).mean() * 100 if len(o) else float("nan")
        print(f"  {role:6s} : {len(g):8,} passages | {g.trip_id.nunique():5,} trains | "
              f"retard>5min {r5:.1f} %")

    gares = pd.read_csv(GARES, dtype=str).set_index("uic")["nom"]
    df["nom_gare"] = df["uic"].map(gares)
    print("\n=== 15 gares les moins ponctuelles (>=100 passages observes) ===")
    g = df[df["arr_delay_s"].notna()].groupby("nom_gare").agg(
        n=("arr_delay_s", "size"),
        retard5=("arr_delay_s", lambda s: (s > 300).mean() * 100),
        med_s=("arr_delay_s", "median"),
    )
    g = g[g.n >= 100].sort_values("retard5", ascending=False)
    print(g.head(15).round(1).to_string())
    print("\n=== 15 gares les plus ponctuelles (>=100 passages observes) ===")
    print(g.tail(15).sort_values("retard5").round(1).to_string())

    out = ROOT / "data" / "output" / "ter_regularite_v0_par_gare.csv"
    g.to_csv(out, encoding="utf-8-sig")
    print(f"\n-> {out}  (premiere lecture -- a refaire proprement avec jointure GTFS par ligne)")


if __name__ == "__main__":
    main()
