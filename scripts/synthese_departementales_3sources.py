"""
Vue de synthese finale : classement des departementales lentes, croise avec les DEUX
reperes independants de TomTom -- campagnes de comptage MEL (V85) et tags OSM (part
de troncons en zone 30 autour du centre-village).
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"


def main() -> None:
    dep = pd.read_csv(OUT / "departementales_vs_v85.csv").set_index("libelle")
    osm = pd.read_csv(OUT / "osm_zone30_villages.csv").set_index("libelle")
    s = dep.join(osm)
    s = s.sort_values("vitesse_pointe_kmh")[
        ["zone_axe", "vitesse_libre_kmh", "vitesse_pointe_kmh", "v85_kmh", "pct_zone30", "n_troncons_tagges"]]
    print(s.to_string())
    out = OUT / "departementales_synthese_3sources.csv"
    s.to_csv(out, encoding="utf-8-sig")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
