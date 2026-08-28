"""
Coût du TER vers Lille pour un actif pendulaire, par commune candidate.

Source : "Tarifs TER Hauts-de-France" (SNCF / data.gouv.fr, en vigueur au 28/02/2025) — matrice
origine-destination des prix 2nde classe, trois tarifs :
  - Tarif Normal                          (billet a l'unite)
  - Mon Abo TER Hauts-de-France Hebdo      (abonnement hebdomadaire)
  - Mon Abo TER Hauts-de-France Mensuel    (abonnement mensuel, illimite sur le trajet)

On retient l'ABONNEMENT MENSUEL : c'est le vrai cout d'un pendulaire (reduction ~75 % vs
40 billets/mois). On fournit aussi le reste a charge apres remboursement employeur (50 % legal).

Recuperation du fichier : le dataset SNCF `tarifs-ter-hdf` a ete retire ; on utilise le miroir
parquet conserve par data.gouv.fr (hydra-parquet, ressource 2e006c20-...).

Fusionne les colonnes ter_* dans data/output/transport_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "raw" / "tarifs_ter" / "tarifs_ter_hdf.parquet"
TRANSPORT = ROOT / "data" / "output" / "transport_communes_candidates.csv"

LILLE_UIC = ("87286005", "87223263")          # Flandres, Europe
RATIO_MENSUEL_NORMAL = 9.9                     # observe sur la grille (moyenne, sd 0.5)
PLANCHER_MENSUEL = 24.0                        # prix mensuel minimum constate
PART_EMPLOYEUR = 0.50                          # prise en charge legale minimale

TER_COLS = ["ter_billet_normal_eur", "ter_abo_hebdo_eur", "ter_abo_mensuel_eur",
            "ter_abo_mensuel_estime", "ter_abo_mensuel_reste_a_charge_eur"]


def main() -> None:
    con = duckdb.connect()
    t = con.execute(f"""
        SELECT CAST("Origine - code UIC" AS VARCHAR)      AS uic_o,
               CAST("Destination - code UIC" AS VARCHAR)  AS uic_d,
               "Libellé tarif"                            AS lib,
               Prix
        FROM read_parquet('{PARQUET.as_posix()}')
    """).df()
    t["tarif"] = t["lib"].str.extract(r"(Normal|Hebdo|Mensuel)")

    # normalise chaque ligne en (uic_gare, uic_lille) puis garde le trajet impliquant Lille
    m = t[t["uic_o"].isin(LILLE_UIC) | t["uic_d"].isin(LILLE_UIC)].copy()
    m["uic_gare"] = np.where(m["uic_o"].isin(LILLE_UIC), m["uic_d"], m["uic_o"])
    m = m[~m["uic_gare"].isin(LILLE_UIC)]
    # prix mini par (gare, tarif) : Flandres/Europe confondus, sens confondus
    grid = (m.groupby(["uic_gare", "tarif"])["Prix"].min()
            .unstack("tarif").reset_index()
            .rename(columns={"Normal": "normal", "Hebdo": "hebdo", "Mensuel": "mensuel"}))
    print(f"gares avec un tarif TER vers Lille : {len(grid)}")

    tr = pd.read_csv(TRANSPORT, dtype={"code_insee": str, "gare_utile_uic": str})
    tr = tr.drop(columns=[c for c in TER_COLS if c in tr.columns], errors="ignore")
    tr = tr.merge(grid.rename(columns={"uic_gare": "gare_utile_uic"}), on="gare_utile_uic", how="left")

    tr["ter_billet_normal_eur"] = tr["normal"].round(2)
    tr["ter_abo_hebdo_eur"] = tr["hebdo"].round(2)
    mensuel = tr["mensuel"].copy()
    estime = mensuel.isna() & tr["normal"].notna()
    mensuel = mensuel.where(~estime,
                            np.maximum(RATIO_MENSUEL_NORMAL * tr["normal"], PLANCHER_MENSUEL))
    tr["ter_abo_mensuel_eur"] = mensuel.round(0)
    tr["ter_abo_mensuel_estime"] = estime
    tr["ter_abo_mensuel_reste_a_charge_eur"] = (mensuel * (1 - PART_EMPLOYEUR)).round(0)
    tr = tr.drop(columns=["normal", "hebdo", "mensuel"])
    tr.to_csv(TRANSPORT, index=False, encoding="utf-8-sig")

    # --- recap ---
    ok = tr["ter_abo_mensuel_eur"].notna()
    print(f"\ncommunes : {len(tr)}")
    print(f"  avec cout abo mensuel     : {int(ok.sum())} (dont estime : {int(tr['ter_abo_mensuel_estime'].sum())})")
    print(f"  sans (gare hors grille HdF): {int((~ok).sum())} -> {tr.loc[~ok, 'gare_utile'].dropna().unique().tolist()}")
    print(f"\n  abo mensuel (€)  : min {tr['ter_abo_mensuel_eur'].min():.0f} / "
          f"med {tr['ter_abo_mensuel_eur'].median():.0f} / max {tr['ter_abo_mensuel_eur'].max():.0f}")
    print(f"  reste a charge 50%: min {tr['ter_abo_mensuel_reste_a_charge_eur'].min():.0f} / "
          f"med {tr['ter_abo_mensuel_reste_a_charge_eur'].median():.0f} / max {tr['ter_abo_mensuel_reste_a_charge_eur'].max():.0f}")
    print("\n--- exemples ---")
    ex = tr[tr["gare_utile"].isin(["Douai", "Lens", "Arras", "Hazebrouck", "Orchies", "Templeuve",
                                   "Béthune", "Valenciennes", "Dunkerque", "Seclin", "Libercourt",
                                   "Cambrai", "Calais - Fréthun"])]
    ex = ex.drop_duplicates("gare_utile").sort_values("ter_abo_mensuel_eur")
    print(ex[["commune", "gare_utile", "ter_billet_normal_eur", "ter_abo_mensuel_eur",
              "ter_abo_mensuel_reste_a_charge_eur", "trajet_ter_realiste_min"]].to_string(index=False))
    print(f"\n-> {TRANSPORT}")


if __name__ == "__main__":
    main()
