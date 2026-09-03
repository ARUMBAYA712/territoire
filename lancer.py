"""
lancer.py — enchaîne les traitements dans le bon ordre
=======================================================

La numérotation des scripts n'est pas leur ordre d'exécution : les
collecteurs passent avant l'agrégation, et la génération des pages en
dernier. Ce lanceur applique la séquence correcte et s'arrête au premier
blocage, sans rien publier de douteux.

Utilisation :
    python lancer.py              applique le plan de la dernière livraison
    python lancer.py --complet    séquence entière, avec reprises
    python lancer.py --tout       séquence entière, en recollectant tout
    python lancer.py --collecte   collecteurs, puis agrégation et site
    python lancer.py --site       régénère le site sans rien collecter
    python lancer.py --liste      affiche ce qui serait lancé, sans le lancer
"""

import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# ══════════════════════════════════════════════════════════════════
# PLAN DE LA DERNIÈRE LIVRAISON
#
# Mis à jour à chaque envoi de fichiers modifiés. C'est ce que lance
# « python lancer.py » sans option : le strict nécessaire pour que les
# corrections livrées prennent effet.
#
# Livraison cumulée — en attente d'installation
#   · 04_generation.py bandeaux d'alerte compacts, renvois vers la page
#                      portant le bloc, rubrique Éducation
#   · 06_eau.py        réseaux classés du contrôle le plus récent au plus ancien
#   · 07_vigieau.py    zones classées de la plus grave à la moins grave
#   · 08_georisques.py dates des arrêtés, liens Légifrance par NOR,
#                      bandeau de reconnaissance récente
#   · 03_agregation.py les mesures des collecteurs peuvent remonter au
#                      canton et à l'intercommunalité si elles le déclarent
#   · 10_ecoles.py     NOUVEAU — établissements scolaires
#   · durée mesurée de la chaîne complète : environ 8 min 30, plus les
#     écoles, encore inconnues
# ══════════════════════════════════════════════════════════════════
# PLAN DE LA DERNIÈRE LIVRAISON
#
# Mis à jour à chaque envoi de fichiers modifiés. C'est ce que lance
# « python lancer.py » sans option : le strict nécessaire pour que les
# corrections livrées prennent effet.
#
# Livraison du 3 septembre 2026 — arrêtés de catastrophe naturelle
#   · 08_georisques.py détaille chaque arrêté et cherche son lien officiel
#   · la structure des blocs change : recollecte complète nécessaire,
#     le réhabillage ne suffirait pas
# ══════════════════════════════════════════════════════════════════

PLAN_LIVRAISON = [
    ("06_eau.py", ["--tout"]),
    ("07_vigieau.py", ["--tout"]),
    ("08_georisques.py", ["--tout"]),
    ("10_ecoles.py", []),
    ("03_agregation.py", []),
    ("04_generation.py", []),
]

# ══════════════════════════════════════════════════════════════════
# SÉQUENCES DE RÉFÉRENCE
# ══════════════════════════════════════════════════════════════════

REFERENTIEL = [
    ("01_referentiel.py", []),
    ("02_canton.py", []),
]

COLLECTEURS = [
    ("06_eau.py", []),
    ("07_vigieau.py", []),
    ("08_georisques.py", []),
    ("09_nappes.py", []),
    ("10_ecoles.py", []),
]

PUBLICATION = [
    ("03_agregation.py", []),
    ("05_cartes.py", []),
    ("04_generation.py", []),
]

COMPLET = REFERENTIEL + COLLECTEURS + PUBLICATION


def avec_option(etapes, option):
    """Ajoute une option aux seuls scripts qui la comprennent."""
    return [(script, args + [option]) for script, args in etapes]


PLANS = {
    "--complet": ("séquence entière", COMPLET),
    "--tout": ("séquence entière, recollecte intégrale",
               REFERENTIEL + avec_option(COLLECTEURS, "--tout") + PUBLICATION),
    "--collecte": ("collecte puis publication", COLLECTEURS + PUBLICATION),
    "--site": ("régénération du site seul", PUBLICATION),
}


# ══════════════════════════════════════════════════════════════════

def duree(secondes):
    if secondes < 60:
        return f"{secondes:.0f} s"
    return f"{int(secondes // 60)} min {int(secondes % 60):02d} s"


def lancer(etapes, libelle):
    print()
    print("═" * 62)
    print(f"  Lancement : {libelle}")
    print(f"  {len(etapes)} étape(s)")
    print("═" * 62)

    manquants = [s for s, _ in etapes if not (RACINE / s).exists()]
    if manquants:
        print(f"\n[ARRÊT] Script(s) introuvable(s) : {', '.join(manquants)}")
        print(f"  Dossier examiné : {RACINE}")
        return 1

    depart = time.monotonic()
    chronos = []

    for numero, (script, args) in enumerate(etapes, start=1):
        commande = [sys.executable, script] + args
        titre = script + ("  " + " ".join(args) if args else "")
        print(f"\n{'─' * 62}")
        print(f"  [{numero}/{len(etapes)}] {titre}")
        print("─" * 62)

        debut = time.monotonic()
        resultat = subprocess.run(commande, cwd=RACINE)
        ecoule = time.monotonic() - debut
        chronos.append((titre, ecoule, resultat.returncode))

        if resultat.returncode != 0:
            print()
            print("═" * 62)
            print(f"  ARRÊT à l'étape {numero} : {script}")
            print(f"  Code de sortie {resultat.returncode}")
            print()
            print("  Rien n'a été publié au-delà de ce point. Le site")
            print("  conserve ses données précédentes.")
            print()
            print("  Reprenez après correction :")
            restantes = [s for s, _ in etapes[numero - 1:]]
            print(f"      {'  puis  '.join(restantes)}")
            print("═" * 62)
            return resultat.returncode

    total = time.monotonic() - depart
    print()
    print("═" * 62)
    print("  Terminé sans blocage")
    print("═" * 62)
    for titre, ecoule, _ in chronos:
        print(f"    {titre:<42} {duree(ecoule):>10}")
    print(f"    {'total':<42} {duree(total):>10}")
    print()
    print("  Étape suivante : envoyer les fichiers sur GitHub.")
    print("  Contrôlez d'abord la ligne « Cartes : n/n portent les noms ».")
    print()
    return 0


def main():
    options = [a for a in sys.argv[1:] if a.startswith("--")]
    liste_seule = "--liste" in options
    options = [o for o in options if o != "--liste"]

    inconnues = [o for o in options if o not in PLANS]
    if inconnues:
        print(f"\n[ERREUR] Option inconnue : {', '.join(inconnues)}")
        print(f"  Options acceptées : {', '.join(sorted(PLANS))}, --liste\n")
        sys.exit(2)

    if not options:
        libelle, etapes = "plan de la dernière livraison", PLAN_LIVRAISON
    else:
        libelle, etapes = PLANS[options[0]]

    if liste_seule:
        print(f"\n  {libelle} — {len(etapes)} étape(s) :\n")
        for numero, (script, args) in enumerate(etapes, start=1):
            suffixe = "  " + " ".join(args) if args else ""
            etat = "" if (RACINE / script).exists() else "   [INTROUVABLE]"
            print(f"    {numero}. {script}{suffixe}{etat}")
        print()
        return

    sys.exit(lancer(etapes, libelle))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Relancez pour reprendre.\n")
        sys.exit(130)
