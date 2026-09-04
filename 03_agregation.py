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

# Numéro de version du script, affiché à l'exécution : il permet
# de vérifier d'un coup d'œil que le fichier installé est le bon.
VERSION_SCRIPT = 3

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
    communes, territoires = {}, {}

    for fichier in sorted(DOSSIER.glob("mesures-*.json")):
        contenu = json.loads(fichier.read_text(encoding="utf-8"))

        for code, bloc in contenu.get("communes", {}).items():
            entree = communes.setdefault(code, {"mesures": {}, "blocs": []})
            entree["mesures"].update(bloc.get("mesures", {}))
            entree["blocs"].extend(bloc.get("blocs", []))

        # Certaines données n'ont de sens qu'à une échelle large : le
        # niveau d'une nappe, le débit d'une rivière se mesurent en
        # stations, et une valeur communale serait trompeuse. Ces
        # mesures sont rattachées directement au territoire, sous une
        # clé « niveau:code ».
        for cle, bloc in contenu.get("territoires", {}).items():
            entree = territoires.setdefault(cle, {"mesures": {}, "blocs": []})
            entree["mesures"].update(bloc.get("mesures", {}))
            entree["blocs"].extend(bloc.get("blocs", []))

        detail = []
        if contenu.get("communes"):
            detail.append(f"{len(contenu['communes'])} communes")
        if contenu.get("territoires"):
            detail.append(f"{len(contenu['territoires'])} territoires")
        print(f"  Complément repris : {fichier.name} "
              f"({', '.join(detail) or 'vide'})")

    return communes, territoires


def agreger_complements(communes_membres, complements):
    """Somme, au niveau du territoire, les mesures qui s'y prêtent.

    Une mesure venue d'un collecteur ne remonte que si elle le déclare
    explicitement, par le champ « agregation ». La qualité de l'eau ne
    remonte pas — les réseaux ne suivent pas les limites administratives —
    mais un nombre d'écoles, lui, s'additionne sans ambiguïté.
    """
    totaux, modeles, references = {}, {}, {}
    for commune in communes_membres:
        bloc = complements.get(commune["code"], {})
        for ident, mesure in bloc.get("mesures", {}).items():
            if mesure.get("agregation") != "somme":
                continue
            valeur = mesure.get("valeur")
            if not isinstance(valeur, (int, float)):
                continue
            totaux[ident] = totaux.get(ident, 0) + valeur
            # On retient la commune à la plus forte valeur comme modèle :
            # ses libellés sont ceux d'un effectif pluriel, ce qui évite
            # d'hériter du singulier d'une commune à un seul élément.
            if valeur >= references.get(ident, -1):
                references[ident] = valeur
                modeles[ident] = mesure

    agregees = {}
    for ident, total in totaux.items():
        modele = dict(modeles[ident])
        modele["valeur"] = round(total, 2) if isinstance(total, float) else total
        modele["obtention"] = "agrégé"

        # Le repère décrit une commune précise — « sur 1 établissement » —
        # et devient faux dès qu'on additionne. Il est écarté.
        modele.pop("repere", None)

        # Le renvoi vers un bloc détaillé n'a de sens qu'à la commune :
        # le bloc n'existe pas au niveau agrégé.
        modele.pop("ancre", None)
        modele.pop("mise_en_avant", None)
        modele.pop("ton", None)

        # Forme plurielle si le collecteur l'a déclarée.
        if modele.get("unite_pluriel") and total > 1:
            modele["unite"] = modele["unite_pluriel"]
        modele.pop("unite_pluriel", None)
        agregees[ident] = modele
    return agregees


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
    print(f"  version {VERSION_SCRIPT} du script")

    if not SOURCE.exists():
        print(f"\n[ERREUR] {SOURCE} introuvable.")
        print("  Lancez d'abord 01_referentiel.py puis 02_canton.py")
        sys.exit(1)

    donnees = json.loads(SOURCE.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    complements, complements_territoires = charger_complements()

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
    extra = complements_territoires.get(f"canton:{canton['code']}", {})
    mesures_canton = mesurer(du_canton, "canton")
    mesures_canton.update(agreger_complements(du_canton, complements))
    mesures_canton.update(extra.get("mesures", {}))

    fichier = enveloppe(
        {"niveau": "canton", "code": canton["code"], "nom": canton["nom"],
         "bureau_centralisateur": canton["bureau_centralisateur"],
         "communes_scindees": canton["communes_scindees"],
         "nombre_communes": len(du_canton)},
        mesures_canton,
        {"au_dessus": [{"niveau": "departement", "code": "38", "nom": "Isère"}],
         "en_dessous": membres},
        extra.get("blocs", []))
    (PUBLIE / "canton" / f"{canton['code']}.json").write_text(
        json.dumps(fichier, ensure_ascii=False, indent=2), encoding="utf-8")
    index["territoires"].append(
        {"niveau": "canton", "code": canton["code"], "nom": canton["nom"]})

    # epci
    membres = [{"niveau": "commune", "code": c["code"], "nom": c["nom"]}
               for c in sorted(de_l_epci, key=lambda x: x["nom"])]
    extra = complements_territoires.get(f"epci:{code_epci}", {})
    mesures_epci = mesurer(de_l_epci, "epci")
    mesures_epci.update(agreger_complements(de_l_epci, complements))
    mesures_epci.update(extra.get("mesures", {}))

    fichier = enveloppe(
        {"niveau": "epci", "code": code_epci,
         "nom": "Saint-Marcellin Vercors Isère Communauté",
         "nombre_communes": len(de_l_epci)},
        mesures_epci,
        {"au_dessus": [{"niveau": "departement", "code": "38", "nom": "Isère"}],
         "en_dessous": membres},
        extra.get("blocs", []))
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
