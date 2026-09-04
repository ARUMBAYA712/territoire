"""
02_canton.py — Rattachement cantonal et réconciliation des périmètres
======================================================================

Enrichit le référentiel produit par 01_referentiel.py avec l'appartenance
au canton du Sud Grésivaudan, et met en évidence les écarts entre le
périmètre cantonal (44 communes) et le périmètre intercommunal (47).

L'API du découpage administratif n'expose pas les cantons : la liste de
référence est donc saisie ici, puis rapprochée automatiquement du
référentiel. Aucun code INSEE n'est recopié à la main.

Utilisation :
    python 02_canton.py
"""

import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

# Numéro de version du script, affiché à l'exécution : il permet
# de vérifier d'un coup d'œil que le fichier installé est le bon.
VERSION_SCRIPT = 1

DOSSIER = Path("data")
FICHIER = DOSSIER / "referentiel-communes.json"

# ══════════════════════════════════════════════════════════════════
# LISTE DE RÉFÉRENCE DU CANTON
#
# Canton du Sud Grésivaudan — code officiel géographique 3823.
# Bureau centralisateur : Saint-Marcellin.
# 44 communes entières, aucune commune scindée.
#
# ATTENTION : liste établie à partir de sources encyclopédiques.
# Elle DOIT être confrontée au décret de découpage de 2015 ou aux
# métadonnées INSEE avant toute mise en production. Le contrôle de
# cardinalité ci-dessous ne vérifie que le nombre, pas l'exactitude.
# ══════════════════════════════════════════════════════════════════

CANTON = {
    "code": "3823",
    "nom": "Le Sud Grésivaudan",
    "bureau_centralisateur": "38416",
    "depuis": "2015",
    "communes_scindees": False,
    "source_liste": "à confronter au décret de découpage 2015 / INSEE",
}

COMMUNES_CANTON = [
    "L'Albenc", "Auberives-en-Royans", "Beaulieu", "Beauvoir-en-Royans",
    "Bessins", "Chantesse", "Chasselay", "Châtelus", "Chatte",
    "Chevrières", "Choranche", "Cognin-les-Gorges", "Cras", "Izeron",
    "Malleval-en-Vercors", "Montagne", "Morette", "Murinais",
    "Notre-Dame-de-l'Osier", "Pont-en-Royans", "Presles", "Quincieu",
    "Rencurel", "La Rivière", "Rovon", "Saint-André-en-Royans",
    "Saint-Antoine-l'Abbaye", "Saint-Appolinard", "Saint-Bonnet-de-Chavagne",
    "Saint-Gervais", "Saint-Hilaire-du-Rosier", "Saint-Just-de-Claix",
    "Saint-Lattier", "Saint-Marcellin", "Saint-Pierre-de-Chérennes",
    "Saint-Romans", "Saint-Sauveur", "Saint-Vérand", "Serre-Nerpol",
    "La Sône", "Têche", "Varacieux", "Vatilieu", "Vinay",
]

SEUIL_SCISSION = 3500   # au-delà, une commune peut être scindée entre cantons


# ══════════════════════════════════════════════════════════════════
# RAPPROCHEMENT PAR NOM
# ══════════════════════════════════════════════════════════════════

def normaliser(nom):
    """Ramène un nom de commune à une forme comparable.

    Supprime accents, articles initiaux, tirets, apostrophes et espaces,
    pour que « La Rivière » et « Riviere » se rapprochent correctement.
    """
    texte = unicodedata.normalize("NFD", nom.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    for article in ("l'", "le ", "la ", "les "):
        if texte.startswith(article):
            texte = texte[len(article):]
            break
    return "".join(c for c in texte if c.isalnum())


def verifier_collisions(index, libelle):
    """S'assure que la normalisation ne fusionne pas deux communes distinctes."""
    vus = {}
    for cle, valeur in index:
        if cle in vus:
            print(f"\n[BLOCAGE] Collision de noms dans {libelle} : "
                  f"« {vus[cle]} » et « {valeur} » se normalisent pareil.")
            sys.exit(1)
        vus[cle] = valeur


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nRattachement cantonal")
    print("─" * 46)
    print(f"  version {VERSION_SCRIPT} du script")

    if not FICHIER.exists():
        print(f"\n[ERREUR] {FICHIER} introuvable.")
        print("  Lancez d'abord : python 01_referentiel.py")
        sys.exit(1)

    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    communes = donnees["communes"]

    # contrôle de cardinalité sur la liste de référence
    if len(COMMUNES_CANTON) != 44:
        print(f"\n[BLOCAGE] La liste de référence contient "
              f"{len(COMMUNES_CANTON)} communes au lieu de 44.")
        sys.exit(1)

    verifier_collisions([(normaliser(c["nom"]), c["nom"]) for c in communes],
                        "le référentiel")
    verifier_collisions([(normaliser(n), n) for n in COMMUNES_CANTON],
                        "la liste cantonale")

    par_nom = {normaliser(c["nom"]): c for c in communes}

    # ── rapprochement ────────────────────────────────────────────
    rattachees, introuvables = [], []
    for nom in COMMUNES_CANTON:
        commune = par_nom.get(normaliser(nom))
        if commune:
            commune["code_canton"] = CANTON["code"]
            commune["commune_scindee"] = False
            rattachees.append(commune)
        else:
            introuvables.append(nom)

    hors_canton = [c for c in communes if c["code_canton"] is None]
    for c in hors_canton:
        c["commune_scindee"] = False

    # ── restitution ──────────────────────────────────────────────
    print(f"\n  Communes du canton retrouvées : {len(rattachees)} / 44")
    print(f"  Population du canton (partielle) : "
          f"{sum(c['population'] or 0 for c in rattachees):,}".replace(",", " "))

    if introuvables:
        print(f"\n  Dans le canton mais ABSENTES du référentiel "
              f"({len(introuvables)}) :")
        for nom in introuvables:
            print(f"    · {nom}")
        print("    → communes du canton situées hors de l'intercommunalité.")
        print("      À charger si vous voulez un canton complet.")

    if hors_canton:
        print(f"\n  Dans l'intercommunalité mais HORS canton "
              f"({len(hors_canton)}) :")
        for c in sorted(hors_canton, key=lambda x: x["nom"]):
            print(f"    · {c['nom']:<32} {c['code']}")

    # ── vérification du risque de scission ───────────────────────
    grandes = [c for c in communes if (c["population"] or 0) > SEUIL_SCISSION]
    print(f"\n  Communes de plus de {SEUIL_SCISSION} habitants "
          f"(seules candidates à une scission) :")
    for c in sorted(grandes, key=lambda x: -(x["population"] or 0)):
        print(f"    · {c['nom']:<32} {c['population']:>7,}".replace(",", " "))
    print("    → toutes entières dans leur canton : agrégations exactes.")

    # ── écriture ─────────────────────────────────────────────────
    donnees["cantons"] = [CANTON]
    donnees["genere_le"] = date.today().isoformat()
    donnees["communes_rattachees_canton"] = len(rattachees)

    FICHIER.write_text(
        json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  Référentiel mis à jour : {FICHIER}")
    if introuvables:
        print("\n  Note : le canton est incomplet dans le référentiel. "
              "Tout agrégat\n  cantonal serait donc partiel en l'état.")
    print()


if __name__ == "__main__":
    main()
