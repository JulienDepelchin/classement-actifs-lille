"""
Volet "navetteurs vers la MEL" pour les communes candidates.

Question de lecteur : "des actifs comme moi font-ils deja ce trajet ?".
Indicateur inedit : parmi les actifs occupes qui resident dans la commune, quelle part
travaille dans la Metropole europeenne de Lille (et, en particulier, a Lille).

Source : Insee, base flux mobilite domicile - lieu de travail 2021 (deja telechargee).
  data/raw/insee/flux_mobilite_2021/base-flux-mobilite-domicile-lieu-travail-2021.csv
  colonnes : CODGEO (residence), DCLT (lieu de travail), NBFLUX_C21_ACTOCC15P (nb d'actifs).
Geo 2021 -> remap 2026 pour l'origine ET la destination.

Rappel methodo Insee : les flux < 200 sont des ordres de grandeur (arrondi aleatoire).
Les PARTS restent fiables ; les effectifs commune->commune fins, moins.

Sortie : data/output/navetteurs_mel_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
FLUX = ROOT / "data" / "raw" / "insee" / "flux_mobilite_2021" / "base-flux-mobilite-domicile-lieu-travail-2021.csv"
APP = ROOT / "data" / "raw" / "insee" / "table_appartenance_2026" / "table-appartenance-geo-communes-2026.xlsx"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "navetteurs_mel_communes_candidates.csv"

LILLE = "59350"
EPCI_MEL = "200093201"


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def main() -> None:
    passage = passage_map()
    remap = lambda c: passage.get(c, c)

    app = pd.read_excel(APP, engine="calamine", dtype=str, skiprows=5)
    mel = set(app.loc[app["EPCI"] == EPCI_MEL, "CODGEO"].map(remap))

    f = pd.read_csv(FLUX, sep=";", dtype=str,
                    usecols=["CODGEO", "DCLT", "NBFLUX_C21_ACTOCC15P"])
    f["nb"] = pd.to_numeric(f["NBFLUX_C21_ACTOCC15P"], errors="coerce")
    f["res"] = f["CODGEO"].map(remap)
    f["trav"] = f["DCLT"].map(remap)
    f = f[f["res"].str.startswith(("59", "62"))]

    g = f.groupby("res")
    tot = g["nb"].sum()
    vers_mel = f[f["trav"].isin(mel)].groupby("res")["nb"].sum()
    vers_lille = f[f["trav"] == LILLE].groupby("res")["nb"].sum()
    sur_place = f[f["res"] == f["trav"]].groupby("res")["nb"].sum()

    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy().set_index("code_insee")

    res["actifs_occupes"] = tot.round(0)
    res["navetteurs_mel_nb"] = vers_mel.reindex(res.index).fillna(0).round(0)
    res["navetteurs_lille_nb"] = vers_lille.reindex(res.index).fillna(0).round(0)
    res["part_actifs_vers_mel_pct"] = (vers_mel / tot * 100).reindex(res.index).round(1)
    res["part_actifs_vers_lille_pct"] = (vers_lille / tot * 100).reindex(res.index).round(1)
    res["part_actifs_travail_sur_place_pct"] = (sur_place / tot * 100).reindex(res.index).round(1)
    # part travaillant hors de la commune ET hors MEL (navette "ailleurs" : Douaisis, bassin
    # minier, littoral, Belgique proche...). Pour les communes hors MEL, sur_place et vers_mel
    # sont disjoints ; le reste part ailleurs.
    p_mel = (vers_mel / tot * 100).reindex(res.index).fillna(0)
    res["part_actifs_navette_hors_mel_pct"] = (
        100 - res["part_actifs_travail_sur_place_pct"].fillna(0) - p_mel).round(1)
    res = res.reset_index()

    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    hors = res[~res["dans_MEL"]]
    print(f"communes : {len(res)} (dont hors MEL : {len(hors)})")
    for c in ["part_actifs_vers_mel_pct", "part_actifs_vers_lille_pct",
              "part_actifs_travail_sur_place_pct"]:
        v = hors[c]
        print(f"  [hors MEL] {c:34s}: med {v.median():5.1f} | p10 {v.quantile(.1):5.1f} | "
              f"p90 {v.quantile(.9):5.1f} | max {v.max():5.1f}")

    print("\n--- 15 communes HORS MEL les plus tournees vers la MEL (part) ---")
    print(hors.nlargest(15, "part_actifs_vers_mel_pct")[
        ["commune", "dep", "PMUN", "actifs_occupes", "navetteurs_mel_nb",
         "part_actifs_vers_mel_pct", "part_actifs_vers_lille_pct"]].to_string(index=False))

    print("\n--- 15 communes HORS MEL les moins tournees vers la MEL ---")
    print(hors.nsmallest(15, "part_actifs_vers_mel_pct")[
        ["commune", "dep", "PMUN", "part_actifs_vers_mel_pct", "part_actifs_travail_sur_place_pct"]].to_string(index=False))

    print("\n--- 10 plus gros contingents (nb absolu de navetteurs MEL, hors MEL) ---")
    print(hors.nlargest(10, "navetteurs_mel_nb")[
        ["commune", "dep", "PMUN", "navetteurs_mel_nb", "part_actifs_vers_mel_pct"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
