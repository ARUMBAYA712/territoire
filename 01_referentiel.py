"""
01_referentiel.py — Construction du référentiel de territoires
===============================================================

Première brique du portail. Récupère la liste officielle des communes
du périmètre et produit deux fichiers :

  data/referentiel-communes.json  → le fichier publié (contrat d'échange)
  data/referentiel-communes.csv   → la même chose, pour vérification à l'œil

Source : API Découpage administratif (geo.api.gouv.fr), qui s'appuie sur
le Code Officiel Géographique de l'INSEE et les données IGN.

Utilisation :
    python 01_referentiel.py
"""

import json
import csv
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# Numéro de version du script, affiché à l'exécution : il permet
# de vérifier d'un coup d'œil que le fichier installé est le bon.
VERSION_SCRIPT = 1

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION DU PÉRIMÈTRE
#
# C'est ici, et nulle part ailleurs, que se définit le territoire
# couvert. Pour étendre le portail (autre EPCI, département, région),
# on ajoute des lignes ici sans toucher au reste du code.
# ══════════════════════════════════════════════════════════════════

PERIMETRE = {
    "epci": ["200070431"],      # Saint-Marcellin Vercors Isère Communauté
    # "epci": ["200070431", "..."],     ← extension future
    # "departements": ["38"],           ← extension future
}

VERSION_CONTRAT = "1.0"
DOSSIER_SORTIE = Path("data")

API = "https://geo.api.gouv.fr"
CHAMPS = "nom,code,population,surface,centre,codesPostaux,codeEpci,codeDepartement,codeRegion"


# ══════════════════════════════════════════════════════════════════
# RÉCUPÉRATION
# ══════════════════════════════════════════════════════════════════

def appeler(url):
    """Interroge l'API et renvoie le résultat, avec un message clair en cas d'échec."""
    try:
        requete = urllib.request.Request(url, headers={"User-Agent": "portail-territorial/1.0"})
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"\n[ERREUR] L'API a répondu {e.code} pour :\n  {url}")
        print("  Vérifiez que le code du territoire est correct.")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[ERREUR] Impossible de joindre l'API : {e.reason}")
        print("  Vérifiez votre connexion internet.")
        sys.exit(1)


def recuperer_communes():
    """Récupère toutes les communes du périmètre configuré."""
    communes = {}

    for code_epci in PERIMETRE.get("epci", []):
        print(f"  Intercommunalité {code_epci}…", end=" ", flush=True)
        lot = appeler(f"{API}/epcis/{code_epci}/communes?fields={CHAMPS}")
        for c in lot:
            communes[c["code"]] = c
        print(f"{len(lot)} communes")

    for code_dep in PERIMETRE.get("departements", []):
        print(f"  Département {code_dep}…", end=" ", flush=True)
        lot = appeler(f"{API}/departements/{code_dep}/communes?fields={CHAMPS}")
        for c in lot:
            communes[c["code"]] = c
        print(f"{len(lot)} communes")

    return communes


# ══════════════════════════════════════════════════════════════════
# CONTRÔLES DE COHÉRENCE
#
# Ils bloquent la production du fichier en cas d'anomalie, plutôt
# que de publier des données fausses sans que personne ne le voie.
# ══════════════════════════════════════════════════════════════════

def controler(communes):
    anomalies = []

    if not communes:
        anomalies.append("Aucune commune récupérée.")

    for code, c in communes.items():
        if not c.get("nom"):
            anomalies.append(f"{code} : nom manquant")
        if len(code) != 5:
            anomalies.append(f"{code} : code INSEE de longueur inattendue")
        if not c.get("population"):
            anomalies.append(f"{code} ({c.get('nom')}) : population absente")
        if not c.get("centre"):
            anomalies.append(f"{code} ({c.get('nom')}) : coordonnées absentes")

    noms = [c["nom"] for c in communes.values()]
    for nom in set(noms):
        if noms.count(nom) > 1:
            anomalies.append(f"Nom en double : {nom}")

    return anomalies


# ══════════════════════════════════════════════════════════════════
# PRODUCTION DES FICHIERS
# ══════════════════════════════════════════════════════════════════

def construire_fichier(communes):
    """Met les données à la forme du contrat d'échange publié."""
    liste = []
    for code in sorted(communes):
        c = communes[code]
        centre = c.get("centre", {}).get("coordinates", [None, None])
        liste.append({
            "code": c["code"],
            "nom": c["nom"],
            "population": c.get("population"),
            "surface_ha": c.get("surface"),
            "longitude": centre[0],
            "latitude": centre[1],
            "codes_postaux": c.get("codesPostaux", []),
            "code_epci": c.get("codeEpci"),
            "code_departement": c.get("codeDepartement"),
            "code_region": c.get("codeRegion"),
            "code_canton": None,          # renseigné à l'étape suivante
            "commune_scindee": None,      # renseigné à l'étape suivante
        })

    return {
        "version_contrat": VERSION_CONTRAT,
        "genere_le": date.today().isoformat(),
        "source": "API Découpage administratif (geo.api.gouv.fr) — INSEE, IGN",
        "licence": "Licence Ouverte 2.0",
        "perimetre": PERIMETRE,
        "nombre_communes": len(liste),
        "population_totale": sum(c["population"] or 0 for c in liste),
        "communes": liste,
    }


def ecrire(donnees):
    DOSSIER_SORTIE.mkdir(exist_ok=True)

    chemin_json = DOSSIER_SORTIE / "referentiel-communes.json"
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)

    chemin_csv = DOSSIER_SORTIE / "referentiel-communes.csv"
    with open(chemin_csv, "w", encoding="utf-8-sig", newline="") as f:
        colonnes = ["code", "nom", "population", "surface_ha",
                    "longitude", "latitude", "code_epci", "code_departement"]
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore", delimiter=";")
        ecrivain.writeheader()
        for c in donnees["communes"]:
            ecrivain.writerow(c)

    return chemin_json, chemin_csv


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nConstruction du référentiel de territoires")
    print("─" * 46)
    print(f"  version {VERSION_SCRIPT} du script")

    communes = recuperer_communes()

    print("\nContrôles de cohérence…")
    anomalies = controler(communes)
    if anomalies:
        print(f"\n[BLOCAGE] {len(anomalies)} anomalie(s) détectée(s) :")
        for a in anomalies[:15]:
            print(f"  · {a}")
        print("\nAucun fichier n'a été produit.")
        sys.exit(1)
    print("  Tous les contrôles passent.")

    donnees = construire_fichier(communes)
    chemin_json, chemin_csv = ecrire(donnees)

    print(f"\nRésultat")
    print(f"  Communes        : {donnees['nombre_communes']}")
    print(f"  Population      : {donnees['population_totale']:,}".replace(",", " "))
    print(f"  Fichier publié  : {chemin_json}")
    print(f"  Fichier lisible : {chemin_csv}")

    plus_grandes = sorted(donnees["communes"],
                          key=lambda c: c["population"] or 0, reverse=True)[:5]
    print(f"\n  Communes les plus peuplées :")
    for c in plus_grandes:
        print(f"    {c['nom']:<32} {c['population']:>7,}".replace(",", " "))
    print()


if __name__ == "__main__":
    main()
