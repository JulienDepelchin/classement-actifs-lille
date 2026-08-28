"""
Volet "reste a vivre" : ce qui reste au menage apres le logement et le trajet domicile-travail.

Indicateur inedit : synthese de tout le pipeline (revenu local + prix immo + cout trajet reel
avec trafic). Objectif editorial : montrer que l'avantage apparent des communes "pas cheres et
loin" fond une fois le revenu local (plus bas) et le cout du trajet (plus eleve) pris en compte.

Menage de reference : niveau de vie MEDIAN local, 1,5 unite de consommation (= un couple sans
enfant, convention Insee). Tous les montants sont MENSUELS.

Sources :
  - Insee FiLoSoFi 2021 (dernier millesime ; 2022 annule pour qualite) : Q221 = niveau de vie
    median annuel par UC ; TP6021 = taux de pauvrete.       data/raw/insee/filosofi_2021/
  - cadre_urbain_communes_candidates.csv : prix_maison_m2, loyers_maison_m2 (avril 2026).
  - transport_communes_candidates.csv : cout_mensuel_meilleur_mode_eur, voiture_cout_mensuel_est_eur.

Scenario LOGEMENT (cout d'ACCES, celui d'un nouvel arrivant, pas d'un proprietaire installe) :
  - maison de 95 m2 (mediane du parc Nord/Pas-de-Calais)
  - ACHAT : apport 10 %, pret 25 ans a 3,6 % -> mensualite d'annuite constante
  - LOCATION : loyer_maison_m2 x 95

Scenario TRANSPORT : cout du mode le plus rapide (cout_mensuel_meilleur_mode_eur, deja net du
remboursement employeur 50 % pour les abonnements). Fallback : cout voiture estime.

LIMITE : ce n'est pas un indicateur mesure mais une CONSTRUCTION a hypotheses. Ordres de
grandeur, pour l'analyse comparative entre communes, pas une verite sur un menage precis.

Sortie : data/output/reste_a_vivre_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
FILO = ROOT / "data" / "raw" / "insee" / "filosofi_2021"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
CU = ROOT / "data" / "output" / "cadre_urbain_communes_candidates.csv"
TR = ROOT / "data" / "output" / "transport_communes_candidates.csv"
OUT = ROOT / "data" / "output" / "reste_a_vivre_communes_candidates.csv"

UC_REF = 1.5
# FiLoSoFi = revenus 2021 ; prix immo = avril 2026. On rehausse les revenus de la croissance
# nominale du revenu disponible des menages 2021->2026 (~+13 %, Insee comptes nationaux) pour
# rendre les deux comparables. Facteur approximatif, applique uniformement (n'affecte pas le
# classement relatif entre communes, seulement les montants absolus).
FACTEUR_REVENU_2021_2026 = 1.13
SURFACE_M2 = 95
APPORT = 0.10
TAUX_ANNUEL = 0.036
DUREE_MOIS = 300


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def mensualite_pret(capital: pd.Series) -> pd.Series:
    r = TAUX_ANNUEL / 12
    return capital * r / (1 - (1 + r) ** -DUREE_MOIS)


def main() -> None:
    passage = passage_map()
    remap = lambda c: passage.get(c, c)

    disp = pd.read_csv(FILO / "FILO2021_DISP_COM.csv", sep=";", dtype=str, usecols=["CODGEO", "Q221"])
    pauv = pd.read_csv(FILO / "FILO2021_DISP_PAUVRES_COM.csv", sep=";", dtype=str, usecols=["CODGEO", "TP6021"])
    filo = disp.merge(pauv, on="CODGEO", how="left")
    filo["code_insee"] = filo["CODGEO"].map(remap)
    for c in ["Q221", "TP6021"]:
        filo[c] = pd.to_numeric(filo[c].astype(str).str.replace(",", ".").replace("s", None),
                                errors="coerce")
    # communes fusionnees : moyenne simple (rare, faute de ponderation menages ici)
    filo = filo.groupby("code_insee", as_index=False)[["Q221", "TP6021"]].mean()

    cand = pd.read_csv(CAND, dtype={"code_insee": str})[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]]
    cu = pd.read_csv(CU, dtype={"code_insee": str})[["code_insee", "prix_maison_m2", "loyers_maison_m2"]]
    tr = pd.read_csv(TR, dtype={"code_insee": str})[
        ["code_insee", "cout_sans_voiture_eur", "voiture_cout_mensuel_est_eur",
         "temps_sans_voiture_min", "mode_sans_voiture"]]

    d = cand.merge(filo, on="code_insee", how="left").merge(cu, on="code_insee", how="left").merge(tr, on="code_insee", how="left")

    d["revenu_dispo_ref_mois_eur"] = (d["Q221"] * FACTEUR_REVENU_2021_2026 * UC_REF / 12).round(0)
    d["taux_pauvrete_pct"] = d["TP6021"].round(1)

    d["cout_achat_maison_mois_eur"] = mensualite_pret(
        d["prix_maison_m2"] * SURFACE_M2 * (1 - APPORT)).round(0)
    d["cout_location_maison_mois_eur"] = (d["loyers_maison_m2"] * SURFACE_M2).round(0)

    # cout retenu = le trajet sans voiture s'il existe (arbitrage budgetaire), sinon la voiture
    d["cout_transport_mois_eur"] = d["cout_sans_voiture_eur"].fillna(
        d["voiture_cout_mensuel_est_eur"]).round(0)
    d["transport_contraint_voiture"] = d["cout_sans_voiture_eur"].isna()

    for mode in ("achat", "location"):
        logt = d[f"cout_{mode}_maison_mois_eur"]
        d[f"reste_a_vivre_{mode}_eur"] = (
            d["revenu_dispo_ref_mois_eur"] - logt - d["cout_transport_mois_eur"]).round(0)
        d[f"taux_effort_{mode}_pct"] = (
            (logt + d["cout_transport_mois_eur"]) / d["revenu_dispo_ref_mois_eur"] * 100).round(1)

    cols = ["code_insee", "commune", "dep", "PMUN", "dans_MEL",
            "revenu_dispo_ref_mois_eur", "taux_pauvrete_pct",
            "cout_achat_maison_mois_eur", "cout_location_maison_mois_eur", "cout_transport_mois_eur",
            "transport_contraint_voiture",
            "reste_a_vivre_achat_eur", "taux_effort_achat_pct",
            "reste_a_vivre_location_eur", "taux_effort_location_pct"]
    d[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(d)} | hypotheses : {SURFACE_M2} m2, apport {APPORT:.0%}, "
          f"pret {DUREE_MOIS//12} ans @ {TAUX_ANNUEL:.1%}, menage {UC_REF} UC")
    for c in ["revenu_dispo_ref_mois_eur", "cout_achat_maison_mois_eur", "cout_location_maison_mois_eur",
              "cout_transport_mois_eur", "reste_a_vivre_achat_eur", "reste_a_vivre_location_eur",
              "taux_effort_achat_pct"]:
        v = d[c]
        print(f"  {c:30s}: med {v.median():8.0f} | p10 {v.quantile(.1):8.0f} | p90 {v.quantile(.9):8.0f} | NaN {v.isna().sum()}")

    print("\n--- correlations ---")
    print(f"  prix_maison_m2 ~ revenu_dispo   : {d['prix_maison_m2'].corr(d['revenu_dispo_ref_mois_eur']):+.2f}")
    print(f"  prix_maison_m2 ~ reste_a_vivre_achat : {d['prix_maison_m2'].corr(d['reste_a_vivre_achat_eur']):+.2f}")

    print("\n--- 12 communes : MEILLEUR reste a vivre (achat), hors MEL ---")
    hm = d[~d["dans_MEL"]]
    show = ["commune", "dep", "revenu_dispo_ref_mois_eur", "cout_achat_maison_mois_eur",
            "cout_transport_mois_eur", "reste_a_vivre_achat_eur", "taux_effort_achat_pct"]
    print(hm.nlargest(12, "reste_a_vivre_achat_eur")[show].to_string(index=False))
    print("\n--- 12 communes : PIRE reste a vivre (achat), hors MEL ---")
    print(hm.nsmallest(12, "reste_a_vivre_achat_eur")[show].to_string(index=False))

    print("\n--- effet de re-classement : maisons pas cheres MAIS reste a vivre faible ---")
    pas_cher = d.nsmallest(60, "prix_maison_m2")
    piege = pas_cher.nsmallest(12, "reste_a_vivre_achat_eur")
    print(piege[["commune", "dep", "prix_maison_m2", "revenu_dispo_ref_mois_eur",
                 "cout_transport_mois_eur", "reste_a_vivre_achat_eur"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
