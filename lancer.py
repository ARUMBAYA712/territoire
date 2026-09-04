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
    python lancer.py --initial    remise à niveau après installation, une fois
    python lancer.py --liste      affiche ce qui serait lancé, sans le lancer
    python lancer.py --forcer     passe outre un contrôle de version

Pour éprouver un changement d'affichage, préférez --site : il ne sollicite
aucun serveur public et régénère les pages en une seconde.
"""

import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# ══════════════════════════════════════════════════════════════════
# VERSIONS ATTENDUES
#
# Mises à jour à chaque livraison. Le lanceur compare avec ce que
# déclarent les fichiers présents et signale ceux qui n'ont pas été
# remplacés — un script oublié produit des résultats incohérents sans
# le moindre message d'erreur.
# ══════════════════════════════════════════════════════════════════

VERSIONS_ATTENDUES = {
    "01_referentiel.py": 1,
    "02_canton.py": 1,
    "03_agregation.py": 3,
    "04_generation.py": 6,
    "05_cartes.py": 3,
    "06_eau.py": 4,
    "07_vigieau.py": 4,
    "08_georisques.py": 7,
    "09_nappes.py": 2,
    "10_ecoles.py": 5,
    "11_population.py": 4,
}


def version_installee(script):
    """Numéro déclaré par le fichier présent, ou None."""
    chemin = RACINE / script
    if not chemin.exists():
        return None
    for ligne in chemin.read_text(encoding="utf-8").split("\n")[:80]:
        if ligne.startswith("VERSION_SCRIPT"):
            try:
                return int(ligne.split("=")[1].strip())
            except (IndexError, ValueError):
                return None
    return None


def controler_versions():
    """Signale les scripts qui n'ont pas été remplacés."""
    retard = []
    for script, attendue in sorted(VERSIONS_ATTENDUES.items()):
        installee = version_installee(script)
        if installee is None or installee < attendue:
            retard.append((script, installee, attendue))
    if not retard:
        return True
    print()
    print("═" * 62)
    print("  ATTENTION — fichiers non remplacés")
    print("═" * 62)
    for script, installee, attendue in retard:
        etat = "absent" if installee is None else f"version {installee}"
        print(f"    {script:<24} {etat:<14} attendu : version {attendue}")
    print()
    print("  Ces scripts produiront des résultats incohérents avec les")
    print("  autres. Installez-les avant de relancer.")
    print("═" * 62)
    return False

# ══════════════════════════════════════════════════════════════════
# PLAN DE LA DERNIÈRE LIVRAISON
#
# Mis à jour à chaque envoi de fichiers modifiés. C'est ce que lance
# « python lancer.py » sans option : le strict nécessaire pour que les
# corrections livrées prennent effet.
#
# Livraison cumulée — en attente d'installation
#   · TOUS les scripts portent désormais un numéro de version, affiché à
#     l'exécution. Le lanceur vérifie qu'ils sont bien tous remplacés et
#     refuse de partir sinon : un fichier oublié produisait jusqu'ici des
#     résultats incohérents sans le moindre message.
#   · 03_agregation.py le repère d'une commune n'est plus repris au
#                      niveau agrégé, et la forme plurielle est rétablie
#   · 10_ecoles.py     formes plurielles déclarées
#   · 11_population.py équipements reconnus, formes plurielles déclarées
#
#   Installez les onze scripts et le lanceur, puis « python lancer.py ».
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

# Usage courant : aucune option de recollecte. Chaque collecteur décide
# lui-même de ce qu'il refait, grâce à son numéro de version. Solliciter
# les serveurs publics sans nécessité n'a aucun intérêt.
PLAN_LIVRAISON = [
    ("10_ecoles.py", ["--tout"]),
    ("11_population.py", []),
    ("03_agregation.py", []),
    ("04_generation.py", []),
]

# À ne lancer qu'une seule fois après l'installation de cette livraison :
# la structure des blocs a changé dans 06, 07 et 08, et seul un nouveau
# passage complet la reconstruit. Ensuite, revenez au plan courant.
PLAN_INITIAL = [
    ("06_eau.py", ["--tout"]),
    ("07_vigieau.py", ["--tout"]),
    ("08_georisques.py", ["--tout"]),
    ("10_ecoles.py", []),
    ("11_population.py", []),
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
    ("11_population.py", []),
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
    "--initial": ("remise à niveau après installation, une seule fois",
                  PLAN_INITIAL),
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

    if not controler_versions() and "--forcer" not in sys.argv:
        print("\n  Relancez avec --forcer pour passer outre.\n")
        return 1

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

    options = [o for o in options if o != "--forcer"]
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
