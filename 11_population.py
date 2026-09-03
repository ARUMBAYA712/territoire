"""
11_population.py — Population détaillée (recensement INSEE)
============================================================

Répartition par âge, par sexe, ménages et familles, à partir des fichiers
du recensement publiés par l'INSEE.

Voie retenue : passer par data.gouv.fr pour obtenir l'adresse du fichier
le plus récent, plutôt que de figer une adresse insee.fr qui change à
chaque millésime. Aucune clé, aucune inscription.

Maille : la commune est native ; tous les effectifs remontent au canton
et à l'intercommunalité par somme.

Marche à suivre la première fois :

    python 11_population.py --chercher
        liste les jeux de données candidats sur data.gouv.fr

    python 11_population.py --ressources <identifiant>
        liste les fichiers d'un jeu de données

    python 11_population.py --source <adresse>
        mémorise le fichier à utiliser et l'analyse

    python 11_population.py --colonnes
        affiche les colonnes reconnues dans le fichier mémorisé

    python 11_population.py
        collecte, en réutilisant le fichier mémorisé

Produit :
    data/mesures-population.json   repris par 03_agregation.py
"""

import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
import zipfile
from datetime import date
from pathlib import Path

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-population.json"
CONFIG = DONNEES / "source-population.json"
CACHE = DONNEES / "cache-population.csv"

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
RECHERCHE = "recensement population structure communes"
SOURCE = "INSEE — recensement de la population"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "population"
ANCRE = "repartition-age"
DELAI = 300


# ══════════════════════════════════════════════════════════════════
# RECONNAISSANCE DES COLONNES
#
# Les fichiers du recensement nomment leurs colonnes selon une
# convention stable : une lettre de famille, le millésime sur deux
# chiffres, puis l'indicateur. « P21_POP0014 » se lit population 2021,
# tranche 0 à 14 ans. On reconnaît donc par motif plutôt que par nom
# exact, ce qui rend le collecteur insensible au changement d'année.
# ══════════════════════════════════════════════════════════════════

MOTIF_CODE = re.compile(r"^(CODGEO|COM|CODE_COMMUNE|CODE_INSEE)$", re.I)
MOTIF_TOTAL = re.compile(r"^P(\d{2})_POP$", re.I)
MOTIF_AGE = re.compile(r"^P(\d{2})_POP(\d{2})(\d{2})$", re.I)
MOTIF_AGE_HAUT = re.compile(r"^P(\d{2})_POP(\d{2})P$", re.I)
MOTIF_HOMMES = re.compile(r"^P(\d{2})_POPH$", re.I)
MOTIF_FEMMES = re.compile(r"^P(\d{2})_POPF$", re.I)
MOTIF_MENAGES = re.compile(r"^[CP](\d{2})_MEN$", re.I)
MOTIF_FAMILLES = re.compile(r"^[CP](\d{2})_FAM$", re.I)


def reconnaitre(colonnes):
    """Associe chaque rôle à la colonne correspondante du fichier."""
    trouve = {"age": [], "millesime": None}
    for nom in colonnes:
        propre = nom.strip()
        for cle, motif in (("code", MOTIF_CODE), ("total", MOTIF_TOTAL),
                           ("hommes", MOTIF_HOMMES), ("femmes", MOTIF_FEMMES),
                           ("menages", MOTIF_MENAGES),
                           ("familles", MOTIF_FAMILLES)):
            if motif.match(propre) and cle not in trouve:
                trouve[cle] = propre
                m = motif.match(propre)
                if m.groups() and m.group(1).isdigit():
                    trouve["millesime"] = m.group(1)

        m = MOTIF_AGE.match(propre)
        if m:
            trouve["age"].append((int(m.group(2)), int(m.group(3)), propre))
            continue
        m = MOTIF_AGE_HAUT.match(propre)
        if m:
            trouve["age"].append((int(m.group(2)), 120, propre))

    trouve["age"].sort()
    return trouve


def libelle_tranche(debut, fin):
    return f"{debut} ans et plus" if fin >= 120 else f"{debut} à {fin} ans"


# ══════════════════════════════════════════════════════════════════
# ACCÈS AUX FICHIERS
# ══════════════════════════════════════════════════════════════════

def lire(url, binaire=False):
    requete = urllib.request.Request(
        url, headers={"User-Agent": "portail-territorial/1.0"})
    with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
        corps = reponse.read()
    return corps if binaire else corps.decode("utf-8", errors="replace")


def chercher():
    """Liste les jeux de données candidats sur data.gouv.fr."""
    print("\nRecherche sur data.gouv.fr")
    print("─" * 60)
    url = DATAGOUV + "?" + urllib.parse.urlencode(
        {"q": RECHERCHE, "page_size": 12})
    try:
        lot = json.loads(lire(url)).get("data", [])
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] data.gouv.fr injoignable : {e}\n")
        sys.exit(1)

    if not lot:
        print("  Aucun résultat. Modifiez RECHERCHE en tête du script.\n")
        return
    for d in lot:
        organisation = (d.get("organization") or {}).get("name", "—")
        print(f"\n  {d.get('title', '')[:72]}")
        print(f"    organisation : {organisation}")
        print(f"    identifiant  : {d.get('id')}")
        print(f"    ressources   : {len(d.get('resources', []))}")
    print("\n  Étape suivante :")
    print("      python 11_population.py --ressources <identifiant>\n")


def ressources(identifiant):
    """Liste les fichiers d'un jeu de données."""
    print(f"\nRessources du jeu de données {identifiant}")
    print("─" * 60)
    try:
        d = json.loads(lire(DATAGOUV + identifiant + "/"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] {e}\n")
        sys.exit(1)

    for r in d.get("resources", []):
        taille = r.get("filesize")
        poids = f"{taille / 1048576:.1f} Mo" if taille else "taille inconnue"
        print(f"\n  {r.get('title', '')[:70]}")
        print(f"    format : {r.get('format', '—')}   {poids}")
        print(f"    {r.get('url', '')}")
    print("\n  Étape suivante :")
    print("      python 11_population.py --source <adresse>\n")


def extraire_csv(contenu, url):
    """Renvoie le texte du CSV, qu'il soit brut ou dans une archive."""
    if url.lower().endswith(".zip") or contenu[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            candidats = [n for n in archive.namelist()
                         if n.lower().endswith((".csv", ".txt"))]
            if not candidats:
                print(f"\n[ERREUR] Aucun CSV dans l'archive : "
                      f"{archive.namelist()[:5]}\n")
                sys.exit(1)
            # le plus volumineux est le fichier de données
            choisi = max(candidats, key=lambda n: archive.getinfo(n).file_size)
            print(f"  Fichier retenu dans l'archive : {choisi}")
            brut = archive.read(choisi)
    else:
        brut = contenu

    for encodage in ("utf-8-sig", "latin-1"):
        try:
            return brut.decode(encodage)
        except UnicodeDecodeError:
            continue
    return brut.decode("utf-8", errors="replace")


def telecharger(url):
    print(f"\n  Téléchargement…", end=" ", flush=True)
    try:
        contenu = lire(url, binaire=True)
    except (urllib.error.URLError, OSError) as e:
        print(f"\n\n[ERREUR] Téléchargement impossible : {e}\n")
        sys.exit(1)
    print(f"{len(contenu) / 1048576:.1f} Mo")
    texte = extraire_csv(contenu, url)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(texte, encoding="utf-8")
    print(f"  Mis en cache : {CACHE}")
    return texte


def lecteur(texte):
    """Ouvre le CSV en devinant son séparateur."""
    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    return csv.DictReader(io.StringIO(texte), delimiter=separateur)


# ══════════════════════════════════════════════════════════════════
# CONSTRUCTION DES INDICATEURS
# ══════════════════════════════════════════════════════════════════

RANGS = {"POP-20": 10, "POP-24": 15, "POP-21": 20, "POP-22": 30,
         "POP-23": 40}

EXPLICATIONS = {
    "POP-20": ("Part des moins de 15 ans. Un indicateur de renouvellement : "
               "il traduit la présence de familles avec enfants."),
    "POP-24": ("Part des 75 ans et plus. Un indicateur de vieillissement, "
               "utile pour dimensionner services et équipements."),
    "POP-21": "Part des femmes dans la population municipale.",
    "POP-22": ("Un ménage désigne l'ensemble des personnes occupant un même "
               "logement, qu'elles aient ou non un lien de parenté."),
    "POP-23": ("Une famille comprend au moins deux personnes : un couple avec "
               "ou sans enfant, ou un parent avec ses enfants."),
}


def nombre(valeur):
    texte = str(valeur or "").strip().replace(",", ".").replace(" ", "")
    if not texte:
        return None
    try:
        return round(float(texte))
    except ValueError:
        return None


def espacer(n):
    """Nombre au format français, espace fine pour les milliers."""
    return f"{n:,}".replace(",", "\u202f")


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE}
    base.update(habillage)
    return base


def habiller(ident, m):
    m["rubrique"] = RUBRIQUE
    if ident in RANGS:
        m["rang"] = RANGS[ident]
    if ident in EXPLICATIONS:
        m["explication"] = EXPLICATIONS[ident]
    return m


def synthetiser(ligne, colonnes, millesime):
    """Indicateurs et bloc d'une commune, à partir d'une ligne du fichier."""
    mesures, tranches = {}, []

    total = nombre(ligne.get(colonnes.get("total", ""), ""))
    for debut, fin, colonne in colonnes["age"]:
        effectif = nombre(ligne.get(colonne, ""))
        if effectif is not None:
            tranches.append((libelle_tranche(debut, fin), effectif))

    # Une part parle au visiteur ; un décompte de tranches ne dit rien.
    # Deux indicateurs comparables entre communes, et cartographiables :
    # la jeunesse et le grand âge.
    if tranches:
        somme = sum(e for _, e in tranches)
        detail = {(debut, fin): effectif
                  for (debut, fin, _), (_, effectif)
                  in zip(colonnes["age"], tranches)}
        if somme:
            jeunes = sum(e for (debut, _), e in detail.items() if debut < 15)
            ages = sum(e for (debut, _), e in detail.items() if debut >= 75)
            mesures["POP-20"] = mesure(
                round(100 * jeunes / somme, 1), "%", "Moins de 15 ans",
                obtention="recalculé", ancre=ANCRE,
                repere=f"{espacer(jeunes)} habitants sur {espacer(somme)}")
            mesures["POP-24"] = mesure(
                round(100 * ages / somme, 1), "%", "75 ans et plus",
                obtention="recalculé", ancre=ANCRE,
                repere=f"{espacer(ages)} habitants sur {espacer(somme)}")

    femmes = nombre(ligne.get(colonnes.get("femmes", ""), ""))
    hommes = nombre(ligne.get(colonnes.get("hommes", ""), ""))
    if femmes is not None and hommes is not None and (femmes + hommes):
        part = round(100 * femmes / (femmes + hommes), 1)
        mesures["POP-21"] = mesure(part, "%", "Part des femmes",
                                   obtention="recalculé",
                                   repere=(f"{espacer(femmes)} femmes, "
                                           f"{espacer(hommes)} hommes"))

    menages = nombre(ligne.get(colonnes.get("menages", ""), ""))
    if menages:
        habillage = {"agregation": "somme"}
        if total:
            habillage["repere"] = (
                f"{total / menages:.1f} personnes par ménage en moyenne")
        mesures["POP-22"] = mesure(menages, "ménages", "Ménages", **habillage)

    familles = nombre(ligne.get(colonnes.get("familles", ""), ""))
    if familles:
        mesures["POP-23"] = mesure(familles, "familles", "Familles",
                                   agregation="somme")

    blocs = []
    if tranches:
        somme = sum(e for _, e in tranches) or 1
        blocs = [{
            "rubrique": RUBRIQUE,
            "id": ANCRE,
            "titre": f"Population par tranche d'âge — recensement 20{millesime}"
                     if millesime else "Population par tranche d'âge",
            "items": [{"titre": libelle,
                       "details": {"Habitants": espacer(effectif),
                                   "Part": f"{100 * effectif / somme:.1f} %"}}
                      for libelle, effectif in tranches],
            "note": ("Les tranches d'âge sont celles publiées par l'INSEE. "
                     "Leur somme peut différer légèrement de la population "
                     "municipale, les deux chiffres ne relevant pas du même "
                     "traitement."),
        }]

    mesures = {k: habiller(k, v) for k, v in mesures.items()}
    if not blocs:
        for m in mesures.values():
            m.pop("ancre", None)
    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def source_memorisee():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("url")
    return None


def memoriser(url):
    DONNEES.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps({"url": url,
                                  "memorise_le": date.today().isoformat()},
                                 ensure_ascii=False, indent=1),
                      encoding="utf-8")


def analyser(texte):
    """Décrit ce que le fichier contient, sans rien produire."""
    lecture = lecteur(texte)
    colonnes = reconnaitre(lecture.fieldnames or [])
    print("\nColonnes reconnues")
    print("─" * 60)
    for cle in ("code", "total", "hommes", "femmes", "menages", "familles"):
        print(f"  {cle:<12} {colonnes.get(cle) or 'ABSENTE'}")
    print(f"  millésime    20{colonnes['millesime']}"
          if colonnes.get("millesime") else "  millésime    inconnu")
    print(f"  âge          {len(colonnes['age'])} tranche(s)")
    for debut, fin, nom in colonnes["age"]:
        print(f"                 {libelle_tranche(debut, fin):<18} {nom}")
    if not colonnes.get("code"):
        print("\n  [BLOCAGE] Aucune colonne de code commune reconnue.")
        print(f"  Colonnes du fichier : {(lecture.fieldnames or [])[:12]}")
    print()
    return colonnes


def main():
    if "--chercher" in sys.argv:
        chercher()
        return

    if "--ressources" in sys.argv:
        i = sys.argv.index("--ressources")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez un identifiant de jeu de données.\n")
            sys.exit(1)
        ressources(sys.argv[i + 1])
        return

    url = source_memorisee()
    if "--source" in sys.argv:
        i = sys.argv.index("--source")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez l'adresse du fichier.\n")
            sys.exit(1)
        url = sys.argv[i + 1]
        memoriser(url)
        print(f"\nSource mémorisée : {url}")
        analyser(telecharger(url))
        return

    if "--colonnes" in sys.argv:
        if not CACHE.exists():
            print("\n  Aucun fichier en cache. Utilisez --source d'abord.\n")
            sys.exit(1)
        analyser(CACHE.read_text(encoding="utf-8"))
        return

    print("\nPopulation détaillée — recensement INSEE")
    print("─" * 60)

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)
    if not url:
        print("\n  Aucune source mémorisée. Commencez par :")
        print("      python 11_population.py --chercher\n")
        sys.exit(1)

    texte = (CACHE.read_text(encoding="utf-8")
             if CACHE.exists() and "--tout" not in sys.argv
             else telecharger(url))

    lecture = lecteur(texte)
    colonnes = reconnaitre(lecture.fieldnames or [])
    if not colonnes.get("code"):
        print("\n[BLOCAGE] Colonne de code commune introuvable.")
        print("  Lancez --colonnes pour voir ce que contient le fichier.\n")
        sys.exit(1)

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    attendues = {c["code"]: c["nom"] for c in communes}
    resultat, lignes_lues = {}, 0

    for ligne in lecture:
        lignes_lues += 1
        code = str(ligne.get(colonnes["code"], "")).strip()
        if code not in attendues:
            continue
        synthese = synthetiser(ligne, colonnes, colonnes.get("millesime"))
        if synthese["mesures"]:
            resultat[code] = synthese

    manquantes = sorted(set(attendues) - set(resultat))
    print(f"\n  Lignes parcourues    : {espacer(lignes_lues)}")
    print(f"  Communes renseignées : {len(resultat)}/{len(attendues)}")
    if manquantes:
        print(f"  [attention] Absentes du fichier ({len(manquantes)}) : "
              f"{', '.join(attendues[c] for c in manquantes[:6])}")

    if not resultat:
        print("\n[BLOCAGE] Aucune commune trouvée. Rien n'a été écrit.")
        print("  Vérifiez que le fichier couvre bien la France entière.\n")
        sys.exit(1)

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
        "millesime": f"20{colonnes['millesime']}" if colonnes.get("millesime")
                     else None,
        "communes": resultat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
