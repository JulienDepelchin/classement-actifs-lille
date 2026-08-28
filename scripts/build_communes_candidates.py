"""
Liste des communes candidates du classement "Ou vivre quand on travaille a Lille".

Geographie de reference : communes au 1er janvier 2026 (Code officiel geographique 2026).
Les donnees Insee sources (flux 2021, populations legales 2021) sont en geographie 2024 :
elles sont re-agregees vers la geo 2026 via la table des mouvements de communes
(fusions 2025 : Bermeries -> L'Oree de Mormal ; Huby-Saint-Leu / Marconne /
Sainte-Austreberthe -> Hesdin-la-Foret).

Methode (3 filtres) :
  1. Residence dans le Nord (59) ou le Pas-de-Calais (62).
  2. Lien domicile-travail avec la Metropole Europeenne de Lille (MEL, EPCI 200093201) :
     flux_vers_MEL >= 100 navetteurs  OU  part_vers_MEL >= 5 % des actifs occupes residents.
     Source : Insee, base des flux de mobilite domicile - lieu de travail, millesime 2021,
     geo 01/01/2024 (table deja agregee commune a commune).
     NB Insee : les flux < 200 sont des ordres de grandeur (sondage) -> seuil 100 = garde-fou.
  3. Population municipale >= 1 000 habitants (Insee, populations legales 2021, geo 2024,
     re-agregee geo 2026).

Lille et les communes de la MEL sont conservees (elles passent trivialement le filtre 2).

Sortie : data/output/communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
INSEE = ROOT / "data" / "raw" / "insee"
OUT = ROOT / "data" / "output" / "communes_candidates.csv"

FLUX = INSEE / "flux_mobilite_2021" / "base-flux-mobilite-domicile-lieu-travail-2021.csv"
APPARTENANCE = INSEE / "table_appartenance_2026" / "table-appartenance-geo-communes-2026.xlsx"
POP = INSEE / "pop_legales_2021" / "donnees_communes.csv"
MVT = INSEE / "v_mvt_commune_2026.csv"

EPCI_MEL = "200093201"
DEP_RESIDENCE = {"59", "62"}
SEUIL_FLUX = 100.0
SEUIL_PART = 0.05
SEUIL_POP = 1000


def build_passage(mvt_path: Path) -> dict[str, str]:
    """commune (geo <= 2024) -> commune (geo 2026), d'apres les fusions post-2024."""
    m = pd.read_csv(mvt_path, dtype=str)
    merges = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM")
               & (m.COM_AV != m.COM_AP) & (m.DATE_EFF >= "2024-06-01")]
    mapping = dict(zip(merges.COM_AV, merges.COM_AP))
    # resolution des chaines eventuelles
    for _ in range(5):
        mapping = {k: mapping.get(v, v) for k, v in mapping.items()}
    return mapping


def remap(codes: pd.Series, passage: dict[str, str]) -> pd.Series:
    return codes.map(lambda c: passage.get(c, c))


def main() -> None:
    passage = build_passage(MVT)
    print(f"fusions geo 2024 -> 2026 prises en compte : {passage}")

    # --- appartenance 2026 : commune -> dep / epci / zonages ---
    appart = pd.read_excel(APPARTENANCE, sheet_name="COM", engine="calamine", dtype=str, header=5)
    appart = appart[["CODGEO", "LIBGEO", "DEP", "EPCI", "ZE2020", "AAV2020", "BV2022"]]
    univers = appart[appart["DEP"].isin(DEP_RESIDENCE)].copy()
    mel = set(appart.loc[appart["EPCI"] == EPCI_MEL, "CODGEO"])
    print(f"communes 59+62 (geo 2026) : {len(univers)} | communes MEL : {len(mel)}")

    # --- flux domicile-travail 2021, re-agrege en geo 2026 ---
    flux = pd.read_csv(FLUX, sep=";", dtype={"CODGEO": str, "DCLT": str},
                       usecols=["CODGEO", "DCLT", "NBFLUX_C21_ACTOCC15P"])
    flux["n"] = pd.to_numeric(flux["NBFLUX_C21_ACTOCC15P"], errors="coerce")
    flux["res"] = remap(flux["CODGEO"], passage)
    flux["clt"] = remap(flux["DCLT"], passage)
    flux = flux[flux["res"].isin(set(univers["CODGEO"]))]

    tot = flux.groupby("res")["n"].sum().rename("actifs_occ_residents")
    vers_mel = (flux[flux["clt"].isin(mel)].groupby("res")["n"].sum()
                .rename("navetteurs_MEL").reindex(tot.index, fill_value=0.0))
    g = pd.concat([tot, vers_mel], axis=1)
    g["part_MEL"] = g["navetteurs_MEL"] / g["actifs_occ_residents"]

    # --- population 2021, re-agregee en geo 2026 ---
    pop = pd.read_csv(POP, sep=";", dtype={"COM": str})[["COM", "PMUN"]]
    pop["PMUN"] = pd.to_numeric(pop["PMUN"], errors="coerce")
    pop["CODGEO"] = remap(pop["COM"], passage)
    pop = pop.groupby("CODGEO", as_index=False)["PMUN"].sum()

    # --- assemblage + filtres ---
    df = (univers
          .merge(g, left_on="CODGEO", right_index=True, how="left")
          .merge(pop, on="CODGEO", how="left"))
    df["navetteurs_MEL"] = df["navetteurs_MEL"].fillna(0.0)
    df["dans_MEL"] = df["CODGEO"].isin(mel)

    f_lien = (df["navetteurs_MEL"] >= SEUIL_FLUX) | (df["part_MEL"] >= SEUIL_PART)
    f_pop = df["PMUN"] >= SEUIL_POP
    cand = df[f_lien & f_pop].copy()

    cand = cand.rename(columns={"CODGEO": "code_insee", "LIBGEO": "commune", "DEP": "dep"})
    cand["navetteurs_MEL"] = cand["navetteurs_MEL"].round().astype(int)
    cand["actifs_occ_residents"] = cand["actifs_occ_residents"].round().astype(int)
    cand["part_MEL"] = (cand["part_MEL"] * 100).round(1)
    cand["PMUN"] = cand["PMUN"].astype(int)
    cand = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL",
                 "navetteurs_MEL", "actifs_occ_residents", "part_MEL",
                 "EPCI", "ZE2020", "AAV2020", "BV2022"]].sort_values(["dep", "commune"], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cand.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"\ncommunes 59+62 (geo 2026)              : {len(univers)}")
    print(f"  passent le filtre lien MEL           : {int(f_lien.sum())}")
    print(f"  passent le filtre population >= {SEUIL_POP}  : {int(f_pop.sum())}")
    print(f"  RETENUES (lien ET population)        : {len(cand)}")
    print(f"    dont MEL / hors MEL                : {int(cand['dans_MEL'].sum())} / {int((~cand['dans_MEL']).sum())}")
    print(f"  population cumulee retenue           : {cand['PMUN'].sum():,}")
    only_flux = cand[(cand.navetteurs_MEL >= SEUIL_FLUX) & (cand.part_MEL < SEUIL_PART * 100)]
    only_part = cand[(cand.navetteurs_MEL < SEUIL_FLUX) & (cand.part_MEL >= SEUIL_PART * 100)]
    print(f"  entrees via flux seul (>=100, <5%)   : {len(only_flux)}  ({', '.join(only_flux.commune)})")
    print(f"  entrees via part seule (>=5%, <100)  : {len(only_part)}")
    mel_out = df[df.CODGEO.isin(mel) & ~(f_lien & f_pop)]
    print(f"\nMEL non retenues (pop < {SEUIL_POP}) : "
          + ", ".join(f"{r.LIBGEO} ({int(r.PMUN)})" for r in mel_out.itertuples()))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
