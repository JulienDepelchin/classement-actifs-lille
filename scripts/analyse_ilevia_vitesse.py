"""
Vitesse commerciale des bus ilevia (dsp_ilevia:vitesse_moyenne_bus) : ou les bus rampent,
et ou une voie propre paie (vitesse jour ouvre ~ vitesse dimanche = trafic sans effet).

Sorties :
  data/output/ilevia_vitesse_lignes.csv     par ligne : vitesse, ecart ouvre/dimanche
  data/output/ilevia_vitesse_segments.csv   par troncon inter-arret : vitesse ouvre, deficit
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "ilevia" / "vitesse_moyenne_bus.csv"
PONCTU = ROOT / "data" / "output" / "ilevia_ponctualite_lignes.csv"
STOPS = ROOT / "data" / "raw" / "ilevia" / "sept" / "stops.txt"
OUTDIR = ROOT / "data" / "output"


def noms_arrets() -> dict[str, str]:
    if not STOPS.exists():
        return {}
    s = pd.read_csv(STOPS, dtype=str)
    return dict(zip(s["stop_id"], s["stop_name"]))


def wmean(v, w):
    w = w.fillna(0)
    return np.average(v, weights=w) if w.sum() else np.nan


def main() -> None:
    d = pd.read_csv(SRC, dtype={"code_ligne": str, "code_arret_depart": str, "code_arret_fin": str})
    d["vitesse_moyenne"] = pd.to_numeric(d["vitesse_moyenne"], errors="coerce")
    d["nombre_passage"] = pd.to_numeric(d["nombre_passage"], errors="coerce").fillna(0)
    d = d[(d["vitesse_moyenne"] > 0) & (d["vitesse_moyenne"] < 80)]

    print(f"{len(d):,} obs | {d['mois'].nunique()} mois ({d['mois'].min()}->{d['mois'].max()}) | "
          f"types de jour : {sorted(d['type_jour'].dropna().unique())}")
    ouvre = d["type_jour"].str.contains("uvr", case=False, na=False) | \
        d["nom_jour"].isin(["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"])
    dim = d["nom_jour"].eq("Dimanche") | d["type_jour"].str.contains("imanche", case=False, na=False)
    d["creneau"] = np.where(ouvre, "ouvre", np.where(dim, "dimanche", "samedi"))

    # ---- par ligne ----
    def agg_ligne(g):
        o = g[g.creneau == "ouvre"]; s = g[g.creneau == "dimanche"]
        vo = wmean(o.vitesse_moyenne, o.nombre_passage) if len(o) else np.nan
        vs = wmean(s.vitesse_moyenne, s.nombre_passage) if len(s) else np.nan
        return pd.Series({"v_ouvre": vo, "v_dimanche": vs,
                          "deficit_trafic_pct": (vs - vo) / vs * 100 if vs else np.nan,
                          "passages": g.nombre_passage.sum()})

    lig = d.groupby("code_ligne").apply(agg_ligne, include_groups=False).round(1)
    lig = lig.sort_values("v_ouvre")

    if PONCTU.exists():
        p = pd.read_csv(PONCTU, dtype={"code_ligne": str}).set_index("code_ligne")["retards"]
        lig = lig.join(p.rename("indice_retards"))

    lig.to_csv(OUTDIR / "ilevia_vitesse_lignes.csv", encoding="utf-8-sig")

    print("\n=== 12 lignes les plus LENTES (jour ouvre, km/h) ===")
    print(lig.head(12).to_string())
    print("\n=== 12 lignes les plus touchees par le TRAFIC (perte ouvre vs dimanche) ===")
    print(lig.sort_values("deficit_trafic_pct", ascending=False).head(12).to_string())
    print("\n=== lignes quasi INSENSIBLES au trafic (voie propre probable) ===")
    print(lig[lig.passages > lig.passages.median()].sort_values("deficit_trafic_pct").head(10).to_string())

    if "indice_retards" in lig:
        c = lig[["v_ouvre", "deficit_trafic_pct", "indice_retards"]].dropna()
        print(f"\ncorrelations (n={len(c)}) : vitesse~retards {c.v_ouvre.corr(c.indice_retards):+.2f} | "
              f"deficit_trafic~retards {c.deficit_trafic_pct.corr(c.indice_retards):+.2f}")

    # ---- par troncon ----
    seg = d.groupby(["code_ligne", "code_arret_depart", "code_arret_fin", "creneau"]).apply(
        lambda g: wmean(g.vitesse_moyenne, g.nombre_passage), include_groups=False
    ).unstack("creneau")
    pas = d.groupby(["code_ligne", "code_arret_depart", "code_arret_fin"])["nombre_passage"].sum()
    seg = seg.join(pas.rename("passages"))
    seg["deficit_pct"] = ((seg.get("dimanche") - seg.get("ouvre")) / seg.get("dimanche") * 100)
    seg = seg[seg["passages"] >= 200].round(1).reset_index()
    nm = noms_arrets()
    seg["troncon"] = (seg["code_arret_depart"].map(nm).fillna(seg["code_arret_depart"]) + " -> "
                      + seg["code_arret_fin"].map(nm).fillna(seg["code_arret_fin"]))
    seg = seg.sort_values("ouvre")
    seg.to_csv(OUTDIR / "ilevia_vitesse_segments.csv", index=False, encoding="utf-8-sig")

    print("\n=== 18 troncons les plus lents (jour ouvre, >=200 passages) ===")
    print(seg.head(18)[["code_ligne", "troncon", "ouvre", "dimanche", "deficit_pct", "passages"]].to_string(index=False))
    print(f"\n-> {OUTDIR/'ilevia_vitesse_lignes.csv'} + ilevia_vitesse_segments.csv")


if __name__ == "__main__":
    main()
