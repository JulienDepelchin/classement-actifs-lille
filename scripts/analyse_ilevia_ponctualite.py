"""
Premier classement de fiabilite des lignes ilevia a partir de dsp_ilevia:ponctualite
(indices mensuels par ligne : retards, avances, services non effectues).

Sortie console + data/output/ilevia_ponctualite_lignes.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "ilevia" / "ponctualite.csv"
OUT = ROOT / "data" / "output" / "ilevia_ponctualite_lignes.csv"

IND = {
    "Indice mensuel de retards par ligne": "retards",
    "Indice mensuel d'avances par ligne": "avances",
    "Indice mensuel de services non effectués par lignes": "non_effectues",
}


def famille(code: str) -> str:
    c = str(code).strip()
    if c.startswith("L"):
        return "Liane"
    if c.upper().startswith("CIT"):
        return "Citadine"
    if c.startswith("CO"):
        return "Corolle"
    if c.startswith("C") and c[1:].isdigit():
        return "Ligne C"
    if c.startswith("Z"):
        return "Ligne Z"
    if c.isdigit():
        return "Ligne urbaine"
    return "Autre"


def main() -> None:
    d = pd.read_csv(SRC, dtype=str)
    d["ind"] = d["libelle_indicateur"].map(IND)
    d = d.dropna(subset=["ind"])
    d["val"] = pd.to_numeric(d["valeur_mensuelle"].str.replace(",", ".", regex=False), errors="coerce")
    d["date"] = pd.to_datetime(d["annee_mois"].str.replace("Z", "", regex=False), errors="coerce")
    d = d.dropna(subset=["val", "date"])

    dmax = d["date"].max()
    d12 = d[d["date"] > dmax - pd.DateOffset(months=12)]
    print(f"periode complete : {d['date'].min():%Y-%m} -> {dmax:%Y-%m}  |  "
          f"fenetre 12 mois : {d12['date'].min():%Y-%m} -> {dmax:%Y-%m}\n")

    piv = (d12.pivot_table(index="code_ligne", columns="ind", values="val", aggfunc="mean")
           .rename_axis(None, axis=1))
    piv["famille"] = piv.index.map(famille)
    n_mois = d12.groupby("code_ligne")["date"].nunique().rename("n_mois")
    piv = piv.join(n_mois)

    # tendance : moyenne retards 12 derniers mois vs 12 mois precedents
    dprev = d[(d["date"] <= dmax - pd.DateOffset(months=12)) &
              (d["date"] > dmax - pd.DateOffset(months=24)) & (d["ind"] == "retards")]
    prev = dprev.groupby("code_ligne")["val"].mean().rename("retards_prev")
    piv = piv.join(prev)
    piv["retards_evol"] = (piv["retards"] - piv["retards_prev"]).round(1)

    for c in ("retards", "avances", "non_effectues"):
        if c in piv:
            piv[c] = piv[c].round(1)
    piv = piv.sort_values("retards")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    piv.to_csv(OUT, encoding="utf-8-sig")

    show = ["famille", "retards", "non_effectues", "avances", "retards_evol", "n_mois"]
    print("=== 12 lignes les PLUS ponctuelles (indice de retards le plus bas, 12 mois) ===")
    print(piv.head(12)[show].to_string())
    print("\n=== 12 lignes les MOINS ponctuelles ===")
    print(piv.tail(12)[show].iloc[::-1].to_string())
    print("\n=== par famille (moyenne des indices) ===")
    print(piv.groupby("famille")[["retards", "non_effectues", "avances"]].mean().round(1)
          .sort_values("retards").to_string())

    liane = piv[piv["famille"] == "Liane"].sort_values("retards")
    print("\n=== les Lianes, dans le detail ===")
    print(liane[show].to_string())

    print("\n=== degradation la plus forte (retards 12 mois vs 12 mois precedents) ===")
    print(piv.dropna(subset=["retards_evol"]).sort_values("retards_evol", ascending=False)
          .head(8)[["famille", "retards", "retards_prev", "retards_evol"]].to_string())
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
