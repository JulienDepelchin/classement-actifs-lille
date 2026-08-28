"""
Telecharge les agregats DPE (ADEME, "DPE Logements existants depuis juillet 2021") pour
les departements 59 et 62, via l'API data-fair (agregation cote serveur, pas de dump 900k lignes).

Pour chaque departement : 1 requete "total par commune" (+ cout moyen, conso/m2 moyenne,
GES/m2 moyen) puis 1 requete par etiquette DPE (A..G) -> nombre de logements par commune.

agg_size API plafonne a 1000 ; le 62 compte 890 communes, le 59 en compte 648 -> une page suffit
par (departement x etiquette).

Sortie : data/raw/ademe/dpe_agg_5962.csv  (colonnes : code_insee, dpe_total, dpe_A..dpe_G,
         cout_moyen_eur, conso_ep_m2_moyen, ges_m2_moyen)
"""
from __future__ import annotations
import sys
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ademe" / "dpe_agg_5962.csv"
DS = "meg-83tjwtg8dyz4vv7h1dqe"
BASE = f"https://data.ademe.fr/data-fair/api/v1/datasets/{DS}/values_agg"
LETTERS = list("ABCDEFG")


def get(params: dict) -> dict:
    url = BASE + "?" + urllib.parse.urlencode(params, safe=':()"')
    for essai in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if essai == 3:
                raise
            print(f"  retry ({e})")
            time.sleep(5)


def main() -> None:
    rows: dict[str, dict] = {}
    for dep in ("59", "62"):
        # total + metriques par commune
        d = get({"field": "code_insee_ban", "agg_size": 1000,
                 "qs": f"code_departement_ban:{dep}",
                 "metric": "avg", "metric_field": "cout_total_5_usages"})
        for a in d["aggs"]:
            rows.setdefault(a["value"], {})["dpe_total"] = a["total"]
            rows[a["value"]]["cout_moyen_eur"] = a.get("metric")
        print(f"{dep} : {len(d['aggs'])} communes, total_other={d['total_other']}")

        for metric_field, key in [("conso_5_usages_par_m2_ep", "conso_ep_m2_moyen"),
                                  ("emission_ges_5_usages_par_m2", "ges_m2_moyen")]:
            d = get({"field": "code_insee_ban", "agg_size": 1000,
                     "qs": f"code_departement_ban:{dep}",
                     "metric": "avg", "metric_field": metric_field})
            for a in d["aggs"]:
                rows.setdefault(a["value"], {})[key] = a.get("metric")

        for L in LETTERS:
            d = get({"field": "code_insee_ban", "agg_size": 1000,
                     "qs": f'code_departement_ban:{dep} AND etiquette_dpe:"{L}"'})
            for a in d["aggs"]:
                rows.setdefault(a["value"], {})[f"dpe_{L}"] = a["total"]
            if d["total_other"]:
                print(f"  !! {dep} {L} : total_other={d['total_other']} (communes tronquees)")
            time.sleep(0.3)

    df = pd.DataFrame.from_dict(rows, orient="index").reset_index(names="code_insee")
    for L in LETTERS:
        df[f"dpe_{L}"] = df.get(f"dpe_{L}", 0)
    df = df.fillna({f"dpe_{L}": 0 for L in LETTERS})
    df = df[df["code_insee"].str.match(r"^(59|62)\d{3}$")]
    df = df.sort_values("code_insee")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n{len(df)} communes -> {OUT}")
    print(df[["code_insee", "dpe_total", "dpe_F", "dpe_G", "cout_moyen_eur"]].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
