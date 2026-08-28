"""
Table transport consolidee par commune candidate : ferroviaire (TER) + urbain (Ilevia, MEL).

Fusionne :
  data/output/transport_communes_candidates.csv   (TER : gare utile + desserte + porte-a-porte)
  data/output/ilevia_lille_communes.csv           (Ilevia : trajet TC vers Lille-centre, MEL)

Ajoute :
  meilleur_temps_vers_lille_min = min(porte_a_porte_median_min [TER], tc_trajet_median_min [Ilevia])
  meilleur_mode_vers_lille      = 'TER' | 'TC urbain' | 'TER ~ TC' (ecart <= 5 min)

Sortie : data/output/transport_communes_candidates.csv  (mise a jour, colonnes tc_* + meilleur_*)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TER = ROOT / "data" / "output" / "transport_communes_candidates.csv"
ILEVIA = ROOT / "data" / "output" / "ilevia_lille_communes.csv"

TC_COLS = ["tc_trajets_jour", "tc_arr_lille_matin", "tc_trajet_median_min", "tc_trajet_min_min",
           "tc_trajet_realiste_min", "tc_premier_arr_lille", "tc_dernier_dep", "tc_part_direct",
           "tc_metro_sur_place"]


def main() -> None:
    t = pd.read_csv(TER, dtype={"code_insee": str})
    il = pd.read_csv(ILEVIA, dtype={"code_insee": str})

    t = t.drop(columns=[c for c in TC_COLS + ["meilleur_temps_vers_lille_min", "meilleur_mode_vers_lille"]
                        if c in t.columns], errors="ignore")
    m = t.merge(il[["code_insee"] + TC_COLS], on="code_insee", how="left")

    ter_t = m["trajet_ter_realiste_min"]
    tc_t = m["tc_trajet_realiste_min"]
    m["meilleur_temps_vers_lille_min"] = np.fmin(ter_t.fillna(np.inf), tc_t.fillna(np.inf)).replace(np.inf, np.nan)

    def mode(r):
        a, b = r["trajet_ter_realiste_min"], r["tc_trajet_realiste_min"]
        if pd.isna(a) and pd.isna(b):
            return None
        if pd.isna(b):
            return "TER"
        if pd.isna(a):
            return "TC urbain"
        if abs(a - b) <= 5:
            return "TER ~ TC"
        return "TER" if a < b else "TC urbain"

    m["meilleur_mode_vers_lille"] = m.apply(mode, axis=1)
    m.to_csv(TER, index=False, encoding="utf-8-sig")

    print(f"communes : {len(m)}")
    print(f"  avec desserte Ilevia -> Lille       : {m['tc_trajet_median_min'].notna().sum()}")
    print(f"  meilleur mode = TER                 : {(m['meilleur_mode_vers_lille'] == 'TER').sum()}")
    print(f"  meilleur mode = TC urbain           : {(m['meilleur_mode_vers_lille'] == 'TC urbain').sum()}")
    print(f"  TER ~ TC (<=5 min)                  : {(m['meilleur_mode_vers_lille'] == 'TER ~ TC').sum()}")
    print(f"\n  meilleur temps vers Lille : <=20min {int((m['meilleur_temps_vers_lille_min'] <= 20).sum())}"
          f" | <=30 {int((m['meilleur_temps_vers_lille_min'] <= 30).sum())}"
          f" | <=45 {int((m['meilleur_temps_vers_lille_min'] <= 45).sum())}"
          f" | >60 {int((m['meilleur_temps_vers_lille_min'] > 60).sum())}")
    top = m.nsmallest(15, "meilleur_temps_vers_lille_min")
    print("\n--- 15 communes les mieux connectees a Lille (tous modes) ---")
    print(top[["commune", "dans_MEL", "meilleur_mode_vers_lille", "meilleur_temps_vers_lille_min",
               "trajet_ter_realiste_min", "tc_trajet_realiste_min"]].to_string(index=False))
    worst = m[~m["dans_MEL"]].nlargest(10, "meilleur_temps_vers_lille_min")
    print("\n--- 10 communes hors MEL les moins bien connectees ---")
    print(worst[["commune", "dep", "meilleur_temps_vers_lille_min", "gare_utile", "acces_gare_utile_min",
                 "trains_directs_jour"]].to_string(index=False))
    print(f"\n-> {TER}")


if __name__ == "__main__":
    main()
