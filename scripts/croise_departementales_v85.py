"""
Croise le classement des departementales lentes (vitesse live TomTom, echantillon
29 aout - 11 sept) avec les campagnes de comptage officielles de la MEL
(mel_mobilite_et_transport:tmjo_par_sens_v85, 2012-2026, vitesse V85 mesuree sur site) :
un repere independant de TomTom pour la vitesse "normale" de chaque secteur.

Appariement par COMMUNE (pas par troncon precis -- limite assumee, cf print de fin).

Sortie : data/output/departementales_vs_v85.csv
"""
from __future__ import annotations
import sys
import json
import urllib.request
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
URL = ("https://data.lillemetropole.fr/geoserver/ogc/features/v1/collections/"
       "mel_mobilite_et_transport:tmjo_par_sens_v85/items?f=application/json&limit=6000")

# libelle du point TomTom -> code_insee de la commune (v. communes_candidates.csv + recherche INSEE)
COMMUNES = {
    "Wavrin": "59653", "Sainghin-en-Weppes": "59524", "Herlies": "59303", "Fromelles": "59257",
    "Templeuve-en-Pévèle": "59586", "Cappelle-en-Pévèle": "59129", "Cysoing": "59168",
    "Bourghelles": "59096", "Péronne-en-Mélantois": "59458", "Bouvines": "59106",
    "Pérenchies": "59457", "Prémesques": "59470", "Neuville-en-Ferrain": "59426",
    "Sailly-sur-la-Lys": "62736",
}


def main() -> None:
    fc = json.loads(urllib.request.urlopen(
        urllib.request.Request(URL, headers={"User-Agent": "vdn/1.0"}), timeout=90).read())
    v85 = pd.DataFrame(f["properties"] for f in fc["features"])
    v85["vitesse_v85_kmh"] = pd.to_numeric(
        v85["vm_tmjo_par_sens_v85"].astype(str).str.replace(" km/h", "", regex=False), errors="coerce")
    v85["annee"] = pd.to_datetime(v85["date_mesure"], errors="coerce").dt.year
    v85["debit_total"] = pd.to_numeric(v85["total_vl"], errors="coerce").fillna(0) + \
        pd.to_numeric(v85["total_pl"], errors="coerce").fillna(0)
    print(f"{len(v85)} campagnes de comptage MEL chargees ({v85.annee.min():.0f}-{v85.annee.max():.0f})")

    # pour chaque commune : derniere campagne par troncon, puis mediane des troncons
    rows = []
    for libelle, insee in COMMUNES.items():
        sub = v85[v85.code_insee == insee].dropna(subset=["vitesse_v85_kmh"])
        if sub.empty:
            rows.append({"libelle": libelle, "code_insee": insee, "n_troncons": 0})
            continue
        dernier = sub.sort_values("date_mesure").groupby("troncon").tail(1)
        rows.append({
            "libelle": libelle, "code_insee": insee, "n_troncons": dernier.troncon.nunique(),
            "v85_kmh": dernier.vitesse_v85_kmh.median(),
            "v85_annee_recente": int(dernier.annee.max()),
            "v85_debit_veh_j": int(dernier.debit_total.median()),
        })
    v85_com = pd.DataFrame(rows).set_index("libelle")

    dep = pd.read_csv(ROOT / "data" / "output" / "departementales_lentes_v0.csv").set_index("libelle")
    croise = dep.join(v85_com[["n_troncons", "v85_kmh", "v85_annee_recente", "v85_debit_veh_j"]])
    croise["ecart_pointe_vs_v85"] = (croise["vitesse_pointe_kmh"] - croise["v85_kmh"]).round(1)
    croise = croise.round(1).sort_values("ecart_pointe_vs_v85")

    print(f"\n{(croise.n_troncons > 0).sum()}/{len(croise)} communes avec au moins une campagne MEL")
    show = ["zone_axe", "vitesse_libre_kmh", "vitesse_pointe_kmh", "v85_kmh", "v85_annee_recente",
            "ecart_pointe_vs_v85", "n_troncons"]
    print("\n=== vitesse mesuree en pointe (TomTom) vs vitesse normale mesuree sur site (MEL, V85) ===")
    print(croise[show].to_string())

    out = ROOT / "data" / "output" / "departementales_vs_v85.csv"
    croise.to_csv(out, encoding="utf-8-sig")
    print(f"\n-> {out}")
    print("\nLimite assumee : appariement par COMMUNE (pas par troncon exact) -- une commune peut "
          "avoir plusieurs types de voirie a des vitesses tres differentes. A lire comme un repere, "
          "pas une mesure au metre pres du meme troncon.")


if __name__ == "__main__":
    main()
