"""
Premiere lecture (exploratoire) de l'echantillon TomTom departementales avant la coupure
du 11 septembre : 29 aout -> 11 septembre inclus (13 jours complets + 1 partiel).

Sortie console + data/output/autoroutes_tomtom_v0.csv
"""
from __future__ import annotations
import sys
import glob
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "rt" / "autoroutes"
BONS_JOURS = [f"202608{d:02d}" for d in range(29, 32)] + [f"202609{d:02d}" for d in range(1, 12)]


def main() -> None:
    frames = []
    for day in BONS_JOURS:
        p = SRC / f"{day}.csv"
        if not p.exists():
            continue
        try:
            d = pd.read_csv(p)
        except Exception as e:
            print(f"  {day} illisible : {e}"); continue
        d["jour"] = day
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["poll_utc"]).dt.date
    df["heure"] = pd.to_datetime(df["poll_utc"]).dt.hour
    df["dow"] = pd.to_datetime(df["poll_utc"]).dt.dayofweek  # 0=lundi
    print(f"{len(df):,} lignes | {df['jour'].nunique()} jours ({df['jour'].min()} -> {df['jour'].max()}) | "
          f"{df['poll_utc'].nunique()} relevés distincts")
    print(f"repartition jour de semaine : {df.groupby('dow')['jour'].nunique().to_dict()} (0=lundi..6=dimanche)")

    pts = df[(df.categorie == "point") & (df.sens == "vers_lille")].copy()
    print(f"\n{pts.libelle.nunique()} points, {len(pts):,} observations 'vers_lille'")
    print(f"observations/point : min {pts.groupby('libelle').size().min()} | "
          f"max {pts.groupby('libelle').size().max()} | med {int(pts.groupby('libelle').size().median())}")

    g = pts.groupby(["libelle", "zone_axe", "type"]).agg(
        n=("temps_live_min", "size"),
        libre=("temps_libre_min", "median"),
        med=("temps_live_min", "median"),
        p90=("temps_live_min", lambda s: s.quantile(0.9)),
        retard_med=("retard_min", "median"),
        retard_p90=("retard_min", lambda s: s.quantile(0.9)),
    ).reset_index()
    g["tampon"] = (g["p90"] - g["med"]).round(1)  # dispersion propre au trajet, hors effet pointe/creux
    g["pct_galere"] = pts.groupby("libelle")["retard_min"].apply(
        lambda s: (s > 2 * s.median()).mean() * 100 if s.median() > 0 else 0).values
    g = g.round(1).sort_values("tampon", ascending=False)

    print("\n=== 12 trajets les MOINS previsibles (plus gros tampon p90-mediane) ===")
    print(g.head(12)[["libelle", "zone_axe", "n", "med", "tampon", "retard_med", "pct_galere"]].to_string(index=False))
    print("\n=== 12 trajets les PLUS previsibles ===")
    print(g.tail(12)[["libelle", "zone_axe", "n", "med", "tampon", "retard_med", "pct_galere"]].to_string(index=False))

    print("\n=== semaine (lun-ven) vs week-end : retard median tous points confondus ===")
    sem = pts[pts.dow < 5]["retard_min"]
    we = pts[pts.dow >= 5]["retard_min"]
    print(f"  semaine (n={len(sem):,}) : retard median {sem.median():.1f} min | p90 {sem.quantile(.9):.1f}")
    print(f"  week-end (n={len(we):,}) : retard median {we.median():.1f} min | p90 {we.quantile(.9):.1f}")

    print("\n=== courbe horaire (retard median tous points, jours ouvres) ===")
    h = pts[pts.dow < 5].groupby("heure")["retard_min"].median().round(1)
    print(h.to_string())

    out = ROOT / "data" / "output" / "autoroutes_tomtom_v0.csv"
    g.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n-> {out}")

    print("\n=== troncons (points noirs identifies) ===")
    tr = df[df.categorie == "troncon"].groupby("libelle").agg(
        n=("temps_live_min", "size"), med=("temps_live_min", "median"),
        retard_med=("retard_min", "median"), retard_p90=("retard_min", lambda s: s.quantile(.9))
    ).round(1).sort_values("retard_p90", ascending=False)
    print(tr.to_string())


if __name__ == "__main__":
    main()
