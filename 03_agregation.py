"""
03_agregation.py — Moteur d'agrégation et génération des fichiers publiés
=========================================================================

Produit les fichiers que consommeront le site et, plus tard, les sites tiers.
Un fichier par territoire, sous des adresses versionnées :

    data/publie/v1/commune/38416.json
    data/publie/v1/canton/3823.json
    data/publie/v1/epci/200070431.json
    data/publie/v1/index.json

Le moteur applique les trois modes d'obtention définis au catalogue :

    natif       la source publie la valeur à ce niveau, aucun calcul
    somme       effectif, la somme des communes est exacte
    ratio       taux ou densité, recalculé sur les agrégats

Utilisation :
    python 03_agregation.py
"""

import json
import sys
import shutil
from datetime import date
from pathlib import Path

DOSSIER = Path("data")
SOURCE = DOSSIER / "referentiel-communes.json"
PUBLIE = DOSSIER / "publie" / "v1"

VERSION_CONTRAT = "1.0"


# ══════════════════════════════════════════════════════════════════
# DÉFINITION DES INDICATEURS
#
# Chaque entrée reprend une ligne du catalogue. Ajouter un indicateur
# consiste à ajouter une entrée ici, sans toucher au moteur.
# ══════════════════════════════════════════════════════════════════

INDICATEURS = [
    {
        "id": "POP-01",
        "nom": "Population municipale",
        "unite": "habitants",
        "champ": "population",
        "mode": "somme",
        "source": "INSEE — recensement de la population",
        "licence": "Licence Ouverte 2.0",
        "format": "texte",
    },
    {
        "id": "GEO-13",
        "nom": "Superficie",
        "unite": "km²",
        "champ": "surface_ha",
        "mode": "somme",
        "facteur": 0.01,          # hectares → km²
        "decimales": 1,
        "source": "IGN — Admin Express",
        "licence": "Licence Ouverte 2.0",
        "format": "texte",
    },
    {
        "id": "POP-10",
        "nom": "Densité de population",
        "unite": "hab./km²",
        "mode": "ratio",
        "numerateur": "POP-01",
        "denominateur": "GEO-13",
        "decimales": 1,
        "source": "Calculé — INSEE et IGN",
        "licence": "Licence Ouverte 2.0",
        "format": "carte",
    },
]


# ══════════════════════════════════════════════════════════════════
# MOTEUR
# ══════════════════════════════════════════════════════════════════

def calculer(indicateur, communes):
    """Calcule un indicateur pour un ensemble de communes."""
    mode = indicateur["mode"]

    if mode == "somme":
        valeurs = [c.get(indicateur["champ"]) for c in communes]
        if any(v is None for v in valeurs):
            return None
        total = sum(valeurs) * indicateur.get("facteur", 1)
        return round(total, indicateur["decimales"]) if "decimales" in indicateur else total

    if mode == "ratio":
        return None   # calculé après coup, voir appliquer_ratios

    raise ValueError(f"Mode inconnu : {mode}")


def appliquer_ratios(mesures):
    """Recalcule les ratios à partir des agrégats, jamais en moyennant."""
    for ind in INDICATEURS:
        if ind["mode"] != "ratio":
            continue
        num = mesures.get(ind["numerateur"], {}).get("valeur")
        den = mesures.get(ind["denominateur"], {}).get("valeur")
        valeur = round(num / den, ind["decimales"]) if num and den else None
        mesures[ind["id"]] = {
            "valeur": valeur,
            "unite": ind["unite"],
            "obtention": "recalculé",
            "source": ind["source"],
            "licence": ind["licence"],
            "format": ind["format"],
            "nom": ind["nom"],
        }


def mesurer(communes, niveau):
    """Produit le bloc de mesures d'un territoire."""
    mesures = {}
    for ind in INDICATEURS:
        if ind["mode"] == "ratio":
            continue
        mesures[ind["id"]] = {
            "valeur": calculer(ind, communes),
            "unite": ind["unite"],
            "obtention": "natif" if niveau == "commune" else "agrégé",
            "source": ind["source"],
            "licence": ind["licence"],
            "format": ind["format"],
            "nom": ind["nom"],
        }
    appliquer_ratios(mesures)
    return mesures


def charger_complements():
    """Reprend les mesures produites par les collecteurs spécialisés.

    Chaque collecteur (eau, nappes, élections…) écrit un fichier
    data/mesures-*.json. Le moteur les intègre sans les connaître :
    ajouter une source ne demande donc aucune modification ici.

    Ces mesures portent un champ « niveaux » qui restreint les échelles
    où elles ont un sens. La qualité de l'eau, rattachée à des réseaux
    qui ne suivent pas les limites administratives, reste communale.
    """
    complements = {}
    for fichier in sorted(DOSSIER.glob("mesures-*.json")):
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        for code, bloc in contenu.get("communes", {}).items():
            entree = complements.setdefault(code, {"mesures": {}, "blocs": []})
            entree["mesures"].update(bloc.get("mesures", {}))
            entree["blocs"].extend(bloc.get("blocs", []))
        print(f"  Complément repris : {fichier.name} "
              f"({len(contenu.get('communes', {}))} communes)")
    return complements


def enveloppe(territoire, mesures, rattachements, blocs=None):
    """Forme commune à tous les fichiers publiés — le contrat d'échange."""
    return {
        "version_contrat": VERSION_CONTRAT,
        "genere_le": date.today().isoformat(),
        "territoire": territoire,
        "rattachements": rattachements,
        "mesures": mesures,
        "blocs": blocs or [],
    }


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nGénération des fichiers publiés")
    print("─" * 46)

    if not SOURCE.exists():
        print(f"\n[ERREUR] {SOURCE} introuvable.")
        print("  Lancez d'abord 01_referentiel.py puis 02_canton.py")
        sys.exit(1)

    donnees = json.loads(SOURCE.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    complements = charger_complements()

    if not donnees.get("cantons"):
        print("\n[ERREUR] Rattachement cantonal absent.")
        print("  Lancez d'abord : python 02_canton.py")
        sys.exit(1)

    canton = donnees["cantons"][0]
    code_epci = donnees["perimetre"]["epci"][0]

    du_canton = [c for c in communes if c["code_canton"] == canton["code"]]
    de_l_epci = [c for c in communes if c["code_epci"] == code_epci]

    # ── contrôles bloquants ──────────────────────────────────────
    anomalies = []
    if len(du_canton) != 44:
        anomalies.append(f"Canton : {len(du_canton)} communes au lieu de 44")
    if not de_l_epci:
        anomalies.append("Aucune commune rattachée à l'intercommunalité")
    hors = [c["nom"] for c in du_canton if c not in de_l_epci]
    if hors:
        anomalies.append(f"Communes cantonales hors intercommunalité : {hors}")
    if anomalies:
        print("\n[BLOCAGE] Anomalies détectées :")
        for a in anomalies:
            print(f"  · {a}")
        print("\nAucun fichier n'a été produit.")
        sys.exit(1)

    # ── génération ───────────────────────────────────────────────
    if PUBLIE.exists():
        shutil.rmtree(PUBLIE)
    for sous in ("commune", "canton", "epci"):
        (PUBLIE / sous).mkdir(parents=True)

    index = {"version_contrat": VERSION_CONTRAT,
             "genere_le": date.today().isoformat(),
             "territoires": []}

    # communes
    for c in communes:
        rattachements = {
            "au_dessus": [
                {"niveau": "canton", "code": canton["code"], "nom": canton["nom"]}
            ] if c["code_canton"] else [],
            "en_dessous": [],
        }
        rattachements["au_dessus"].append(
            {"niveau": "epci", "code": c["code_epci"], "nom": "Saint-Marcellin Vercors Isère"})

        extra = complements.get(c["code"], {})
        mesures = mesurer([c], "commune")
        mesures.update(extra.get("mesures", {}))

        fichier = enveloppe(
            {"niveau": "commune", "code": c["code"], "nom": c["nom"],
             "longitude": c["longitude"], "latitude": c["latitude"],
             "codes_postaux": c["codes_postaux"]},
            mesures,
            rattachements,
            extra.get("blocs", []))
        (PUBLIE / "commune" / f"{c['code']}.json").write_text(
            json.dumps(fichier, ensure_ascii=False, indent=2), encoding="utf-8")
        index["territoires"].append(
            {"niveau": "commune", "code": c["code"], "nom": c["nom"]})

    # canton
    membres = [{"niveau": "commune", "code": c["code"], "nom": c["nom"]}
               for c in sorted(du_canton, key=lambda x: x["nom"])]
    fichier = enveloppe(
        {"niveau": "canton", "code": canton["code"], "nom": canton["nom"],
         "bureau_centralisateur": canton["bureau_centralisateur"],
         "communes_scindees": canton["communes_scindees"],
         "nombre_communes": len(du_canton)},
        mesurer(du_canton, "canton"),
        {"au_dessus": [{"niveau": "departement", "code": "38", "nom": "Isère"}],
         "en_dessous": membres})
    (PUBLIE / "canton" / f"{canton['code']}.json").write_text(
        json.dumps(fichier, ensure_ascii=False, indent=2), encoding="utf-8")
    index["territoires"].append(
        {"niveau": "canton", "code": canton["code"], "nom": canton["nom"]})

    # epci
    membres = [{"niveau": "commune", "code": c["code"], "nom": c["nom"]}
               for c in sorted(de_l_epci, key=lambda x: x["nom"])]
    fichier = enveloppe(
        {"niveau": "epci", "code": code_epci,
         "nom": "Saint-Marcellin Vercors Isère Communauté",
         "nombre_communes": len(de_l_epci)},
        mesurer(de_l_epci, "epci"),
        {"au_dessus": [{"niveau": "departement", "code": "38", "nom": "Isère"}],
         "en_dessous": membres})
    (PUBLIE / "epci" / f"{code_epci}.json").write_text(
        json.dumps(fichier, ensure_ascii=False, indent=2), encoding="utf-8")
    index["territoires"].append(
        {"niveau": "epci", "code": code_epci,
         "nom": "Saint-Marcellin Vercors Isère Communauté"})

    (PUBLIE / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── restitution ──────────────────────────────────────────────
    def lire(chemin, ident):
        d = json.loads((PUBLIE / chemin).read_text(encoding="utf-8"))
        return d["mesures"][ident]["valeur"]

    print(f"\n  Fichiers produits : {len(communes) + 2}")
    print(f"  Dossier           : {PUBLIE}")
    print(f"\n  Vérification des trois niveaux :")
    print(f"    {'Territoire':<26} {'Habitants':>10} {'km²':>8} {'hab./km²':>10}")
    for libelle, chemin in (
        ("Saint-Marcellin", "commune/38416.json"),
        ("Canton Sud Grésivaudan", f"canton/{canton['code']}.json"),
        ("Intercommunalité", f"epci/{code_epci}.json"),
    ):
        print(f"    {libelle:<26} {lire(chemin,'POP-01'):>10,}"
              f" {lire(chemin,'GEO-13'):>8}"
              f" {lire(chemin,'POP-10'):>10}".replace(",", " "))

    print(f"\n  La densité du canton n'est pas la moyenne des densités")
    print(f"  communales : elle est recalculée sur les totaux agrégés.\n")


if __name__ == "__main__":
    main()
