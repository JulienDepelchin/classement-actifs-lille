"""
Parmi les 14 points 'departementale' du poller TomTom (Weppes, Pevele, Melantois,
rocade NO/M652, Ferrain, Lys), lesquels sont les plus LENTS -- pas les moins previsibles
(cf analyse_autoroutes_tomtom_v0.py) mais ceux ou on roule vraiment au pas, surtout
aux heures de pointe. Meme echantillon : 29 aout -> 11 sept, 14 jours.
"""
from __future__ import annotations
import sys
import glob
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "rt" / "autoroutes"
PTS = ROOT / "data" / "rt" / "points_routes.csv"
BONS_JOURS = [f"202608{d:02d}" for d in range(29, 32)] + [f"202609{d:02d}" for d in range(1, 12)]
POINTE_MATIN = (5, 7)   # heures UTC pleines incluses dans la fenetre 04:45-07:15
POINTE_SOIR = (14, 17)  # 14:15-17:15


def main() -> None:
    types = pd.read_csv(PTS)[["libelle", "type"]].set_index("libelle")["type"]

    frames = []
    for day in BONS_JOURS:
        p = SRC / f"{day}.csv"
        if p.exists():
            try:
                frames.append(pd.read_csv(p))
            except Exception:
                pass
    df = pd.concat(frames, ignore_index=True)
    df["heure"] = pd.to_datetime(df["poll_utc"]).dt.hour
    df["vitesse_live_kmh"] = df["distance_km"] / (df["temps_live_min"] / 60)
    df["vitesse_libre_kmh"] = df["distance_km"] / (df["temps_libre_min"] / 60)

    dep = df[(df.categorie == "point") & (df.sens == "vers_lille")
             & (df.libelle.map(types) == "départementale")].copy()
    dep["pointe"] = dep["heure"].between(*POINTE_MATIN) | dep["heure"].between(*POINTE_SOIR)

    print(f"{dep.libelle.nunique()} points departementaux | {len(dep):,} observations "
          f"({dep.pointe.sum():,} en heure de pointe)")

    g = dep.groupby(["libelle", "zone_axe"]).apply(lambda s: pd.Series({
        "distance_km": s["distance_km"].median(),
        "vitesse_pointe_kmh": s.loc[s.pointe, "vitesse_live_kmh"].median(),
        "vitesse_creux_kmh": s.loc[~s.pointe, "vitesse_live_kmh"].median(),
        "vitesse_libre_kmh": s["vitesse_libre_kmh"].median(),
        "retard_pointe_min": s.loc[s.pointe, "retard_min"].median(),
        "pct_ralenti_pointe": (s.loc[s.pointe, "retard_min"] / s.loc[s.pointe, "temps_libre_min"] * 100).median(),
    }), include_groups=False).round(1)
    g["ecart_pointe_creux_kmh"] = (g["vitesse_creux_kmh"] - g["vitesse_pointe_kmh"]).round(1)
    g = g.sort_values("vitesse_pointe_kmh")

    print("\n=== departementales classees de la plus LENTE a la plus FLUIDE en heure de pointe ===")
    print("    (vitesse implicite = distance / temps de trajet reel, donc capte le vrai ralentissement,")
    print("     pas juste 'c'est loin')")
    print(g[["distance_km", "vitesse_pointe_kmh", "vitesse_libre_kmh", "ecart_pointe_creux_kmh",
             "retard_pointe_min", "pct_ralenti_pointe"]].to_string())

    out = ROOT / "data" / "output" / "departementales_lentes_v0.csv"
    g.to_csv(out, encoding="utf-8-sig")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
