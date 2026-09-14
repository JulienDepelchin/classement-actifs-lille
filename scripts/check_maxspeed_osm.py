"""
Verifie les limitations de vitesse (tag maxspeed) autour des centres-villages des points
TomTom "departementale", via l'extrait Geofabrik local (memes pbf que les espaces verts --
Overpass est inaccessible depuis le reseau pro).

Sortie : imprime, par commune, les troncons de voirie avec leur maxspeed/zone tagges dans OSM.
"""
from __future__ import annotations
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PBF = ROOT / "data" / "raw" / "geo" / "nord-pas-de-calais.osm.pbf"

# libelle -> (lat, lon) des points TomTom (centre du village vise)
CENTRES = {
    "Bouvines": (50.58182, 3.19275),
    "Péronne-en-Mélantois": (50.56434, 3.17077),
    "Cysoing": (50.56454, 3.21419),
    "Templeuve-en-Pévèle": (50.53261, 3.17346),
    "Cappelle-en-Pévèle": (50.50478, 3.17443),
    "Bourghelles": (50.56340, 3.24691),
}
DEMI_LARGEUR_DEG = 0.006  # ~650 m


def maxspeed_de(other_tags) -> tuple[str, str]:
    ot = other_tags if isinstance(other_tags, str) else ""
    m = re.search(r'"maxspeed"=>"([^"]+)"', ot)
    z = re.search(r'"zone:?maxspeed"=>"([^"]+)"', ot) or re.search(r'"zone:traffic"=>"([^"]+)"', ot)
    return (m.group(1) if m else ""), (z.group(1) if z else "")


def main() -> None:
    synth = []
    for libelle, (lat, lon) in CENTRES.items():
        bbox = (lon - DEMI_LARGEUR_DEG, lat - DEMI_LARGEUR_DEG,
                lon + DEMI_LARGEUR_DEG, lat + DEMI_LARGEUR_DEG)
        try:
            d = gpd.read_file(PBF, layer="lines", engine="pyogrio", bbox=bbox,
                              where="highway IS NOT NULL",
                              columns=["osm_id", "name", "highway", "other_tags"])
        except Exception as e:
            print(f"{libelle} : erreur lecture -- {e}"); continue

        d["maxspeed"], d["zone"] = zip(*d["other_tags"].map(maxspeed_de)) if len(d) else ([], [])
        d = d[d.highway.isin(["primary", "secondary", "tertiary", "unclassified", "residential",
                              "primary_link", "secondary_link"])]

        print(f"\n=== {libelle} ({len(d)} troncons de voirie principale/residentielle dans ~1,3 km) ===")
        vu = d[(d.maxspeed != "") | (d.zone != "")]
        if vu.empty:
            print("  aucun tag maxspeed/zone trouve dans OSM pour ce perimetre")
        else:
            for _, r in vu.sort_values("name").iterrows():
                print(f"  {str(r['name'] or '(sans nom)'):32s} [{r.highway:12s}] "
                      f"maxspeed={r.maxspeed or '-':5s} zone={r.zone or '-'}")
        # distribution generale des maxspeed trouves (y compris rues sans nom)
        vals = [v for v in d.maxspeed if v]
        if vals:
            print(f"  distribution maxspeed : {dict(Counter(vals))}")
        n30 = sum(1 for v in vals if v == "30")
        synth.append({"libelle": libelle, "n_troncons_tagges": len(vals),
                      "pct_zone30": round(n30 / len(vals) * 100, 0) if vals else None})

    s = pd.DataFrame(synth).set_index("libelle")
    out = ROOT / "data" / "output" / "osm_zone30_villages.csv"
    s.to_csv(out, encoding="utf-8-sig")
    print(f"\n=== synthese : part des troncons taggés en zone 30 (OSM) ===")
    print(s.sort_values("pct_zone30", ascending=False).to_string())
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
