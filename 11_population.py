"""
11_population.py — Population, logement et équipements (dossier complet INSEE)
==============================================================================

Un seul fichier de l'INSEE, la Base du dossier complet, alimente trois
rubriques du site :

  · Population   répartition par âge et par sexe, ménages, familles
  · Urbanisme    parc de logements, vacance, résidences secondaires
  · Équipements  commerces, santé, sport et culture, services

Chaque indicateur déclare sa rubrique : le fichier n'est lu qu'une fois.

Voie retenue : passer par data.gouv.fr pour obtenir l'adresse du fichier
le plus récent, plutôt que de figer une adresse insee.fr qui change à
chaque millésime. Aucune clé, aucune inscription.

Maille : la commune est native ; tous les effectifs remontent au canton
et à l'intercommunalité par somme.

Marche à suivre la première fois :

    python 11_population.py --chercher
        liste les jeux de données candidats sur data.gouv.fr

    python 11_population.py --insee
        liste les jeux publiés par l'INSEE, ce qui écarte les jeux locaux

    python 11_population.py --ressources <identifiant>
        liste les fichiers d'un jeu de données

    python 11_population.py --source <adresse>
        mémorise le fichier à utiliser et l'analyse

    python 11_population.py --colonnes
        affiche les colonnes reconnues dans le fichier mémorisé

    python 11_population.py --equipements 38416
        détaille les types d'équipement recensés pour une commune

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

# Numéro de version du script, affiché à l'exécution : il permet
# de vérifier d'un coup d'œil que le fichier installé est le bon.
VERSION_SCRIPT = 5

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-population.json"
CONFIG = DONNEES / "source-population.json"
ARCHIVE = DONNEES / "dossier-complet.zip"
CACHE = DONNEES / "cache-population.csv"

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"

# Base du dossier complet de l'INSEE, version au 31/12/2025 : environ
# 700 indicateurs communaux et supracommunaux, en colonnes larges.
#
# La version parue en juillet 2026 adopte une structure en lignes
# (GEO, TAB_MEASURE, OBS_VALUE) et pèse 7 Go décompressée. Elle n'est pas
# encore prise en charge : le format retenu ici est celui, plus compact,
# de la version précédente, qui reste diffusé.
SOURCE_DEFAUT = ("https://www.insee.fr/fr/statistiques/fichier/5359146/"
                 "dossier_complet_31_12_2025.zip")
SOURCE = "INSEE — recensement de la population"
LICENCE = "Licence Ouverte 2.0"

VERSION = 5
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

# ── logement ──
LOGEMENT = {
    "logements": re.compile(r"^P(\d{2})_LOG$", re.I),
    "principales": re.compile(r"^P(\d{2})_RP$", re.I),
    "secondaires": re.compile(r"^P(\d{2})_RSECOCC$", re.I),
    "vacants": re.compile(r"^P(\d{2})_LOGVAC$", re.I),
    "maisons": re.compile(r"^P(\d{2})_MAISON$", re.I),
    "appartements": re.compile(r"^P(\d{2})_APPART$", re.I),
    "proprietaires": re.compile(r"^P(\d{2})_RP_PROP$", re.I),
    "locataires": re.compile(r"^P(\d{2})_RP_LOC$", re.I),
}

# ── équipements ──
# La base permanente des équipements classe ses types par lettre :
# A services aux particuliers, B commerces, C enseignement, D santé,
# E transports, F sport, loisir et culture. On additionne par domaine
# plutôt que de dépendre du code exact de chaque équipement, qui évolue.
# Deux graphies coexistent selon les millésimes du fichier :
#   BPE_2024_A501   millésime dans le nom de colonne
#   NB_A501         graphie plus ancienne, sans millésime
# La lettre initiale du code désigne le domaine.
MOTIF_EQUIPEMENT = re.compile(
    r"^(?:BPE_(\d{4})_|NB_)([A-G])\d{3}$", re.I)

DOMAINES = {
    "A": ("Services aux particuliers", 40),
    "B": ("Commerces", 10),
    "C": ("Enseignement", 50),
    "D": ("Santé et action sociale", 20),
    "E": ("Transports et déplacements", 60),
    "F": ("Sport, loisir et culture", 30),
    "G": ("Tourisme", 70),
}


MOTIF_MILLESIME = re.compile(r"^[A-Z](\d{2})_")

# Découpage retenu pour la pyramide des âges : sept tranches contiguës
# qui couvrent toute la population sans se chevaucher. Le fichier en
# propose beaucoup d'autres, imbriquées les unes dans les autres — les
# additionner donnerait plusieurs fois la même personne.
TRANCHES_RETENUES = [(0, 14), (15, 29), (30, 44), (45, 59),
                     (60, 74), (75, 89), (90, 120)]


def millesime_de(nom):
    """Année du recensement portée par le nom de colonne, ou -1."""
    trouve = MOTIF_MILLESIME.match(nom)
    return int(trouve.group(1)) if trouve else -1


def reconnaitre(colonnes):
    """Associe chaque rôle à la colonne correspondante du fichier.

    Le fichier contient plusieurs millésimes côte à côte : P06, P11,
    P16, P22. Retenir la première colonne rencontrée reviendrait à
    publier les chiffres de 2006. On collecte donc toutes les
    candidates et on garde systématiquement la plus récente.
    """
    candidats = {}
    ages = []
    equipements = {}

    for nom in colonnes:
        propre = nom.strip()
        annee = millesime_de(propre)

        for cle, motif in (("code", MOTIF_CODE), ("total", MOTIF_TOTAL),
                           ("hommes", MOTIF_HOMMES), ("femmes", MOTIF_FEMMES),
                           ("menages", MOTIF_MENAGES),
                           ("familles", MOTIF_FAMILLES)):
            if motif.match(propre):
                candidats.setdefault(cle, []).append((annee, propre))

        for cle, motif in LOGEMENT.items():
            if motif.match(propre):
                candidats.setdefault("log:" + cle, []).append((annee, propre))

        m = MOTIF_EQUIPEMENT.match(propre)
        if m:
            annee = int(m.group(1)) if m.group(1) else 0
            equipements.setdefault(annee, {}).setdefault(
                m.group(2).upper(), []).append(propre)

        m = MOTIF_AGE.match(propre)
        if m:
            ages.append((annee, int(m.group(2)), int(m.group(3)), propre))
            continue
        m = MOTIF_AGE_HAUT.match(propre)
        if m:
            ages.append((annee, int(m.group(2)), 120, propre))

    def plus_recente(cle):
        lot = candidats.get(cle)
        return max(lot)[1] if lot else None

    # Un seul millésime d'équipements : le plus récent. Additionner
    # deux années compterait deux fois les mêmes boulangeries.
    if equipements:
        recent_bpe = max(equipements)
        trouve_equipements = equipements[recent_bpe]
        millesime_bpe = recent_bpe or None
    else:
        trouve_equipements, millesime_bpe = {}, None

    trouve = {"age": [], "millesime": None, "logement": {},
              "equipements": trouve_equipements,
              "millesime_equipements": millesime_bpe}

    for cle in ("code", "total", "hommes", "femmes", "menages", "familles"):
        colonne = plus_recente(cle)
        if colonne:
            trouve[cle] = colonne

    for cle in LOGEMENT:
        colonne = plus_recente("log:" + cle)
        if colonne:
            trouve["logement"][cle] = colonne

    # Millésime de référence : le plus récent parmi les tranches d'âge.
    if ages:
        recent = max(a[0] for a in ages)
        trouve["millesime"] = f"{recent:02d}"
        retenues = {(d, f): nom for annee, d, f, nom in ages if annee == recent}
        trouve["age"] = sorted(
            (d, f, retenues[(d, f)]) for d, f in TRANCHES_RETENUES
            if (d, f) in retenues)

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


# Plusieurs formulations sont essayées : la recherche de data.gouv.fr est
# sensible aux termes employés, et un jeu peut être intitulé « base des
# chiffres clés » comme « évolution et structure de la population ».
RECHERCHES = [
    "évolution structure population communes",
    "base chiffres clés évolution structure population",
    "recensement population commune csv",
    "population par tranche d'âge commune",
    "recensement",
]


def chercher(termes=None):
    """Liste les jeux de données candidats sur data.gouv.fr."""
    print("\nRecherche sur data.gouv.fr")
    print("─" * 60)

    essais = [termes] if termes else RECHERCHES
    vus, resultats = set(), []

    for requete in essais:
        url = DATAGOUV + "?" + urllib.parse.urlencode(
            {"q": requete, "page_size": 8})
        try:
            lot = json.loads(lire(url)).get("data", [])
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            print(f"\n[ERREUR] data.gouv.fr injoignable : {e}\n")
            sys.exit(1)

        print(f"\n  « {requete} » → {len(lot)} résultat(s)")
        for d in lot:
            if d.get("id") in vus:
                continue
            vus.add(d.get("id"))
            resultats.append(d)
        if len(resultats) >= 12 and not termes:
            break

    if not resultats:
        print("\n  Aucun jeu trouvé. Essayez vos propres termes :")
        print('      python 11_population.py --chercher "vos mots"\n')
        return

    print("\n  Si ces résultats sont locaux plutôt que nationaux, "
          "cherchez côté INSEE :")
    print("      python 11_population.py --insee")

    print("\n" + "─" * 60)
    for d in resultats[:12]:
        organisation = (d.get("organization") or {}).get("name", "—")
        fichiers = [r.get("format", "") for r in d.get("resources", [])]
        formats = ", ".join(sorted({f.lower() for f in fichiers if f})[:5])
        print(f"\n  {d.get('title', '')[:70]}")
        print(f"    organisation : {organisation[:52]}")
        print(f"    identifiant  : {d.get('id')}")
        print(f"    ressources   : {len(fichiers)}  ({formats or 'aucune'})")

    print("\n  Étape suivante :")
    print("      python 11_population.py --ressources <identifiant>")
    print("\n  Vous pouvez aussi passer directement l'adresse d'un fichier :")
    print("      python 11_population.py --source <adresse>\n")


ORGANISATIONS = "https://www.data.gouv.fr/api/1/organizations/"


def chercher_insee(termes=None):
    """Liste les jeux de données publiés par l'INSEE.

    La recherche libre remonte surtout des jeux locaux : une même
    formulation désigne un fichier national de l'INSEE et le tableau
    d'une intercommunalité. Passer par l'organisation lève l'ambiguïté.
    """
    print("\nJeux de données publiés par l'INSEE")
    print("─" * 60)

    try:
        lot = json.loads(lire(ORGANISATIONS + "?" + urllib.parse.urlencode(
            {"q": "INSEE", "page_size": 5}))).get("data", [])
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] data.gouv.fr injoignable : {e}\n")
        sys.exit(1)

    organisation = None
    for o in lot:
        nom = (o.get("name") or "").lower()
        if "statistique" in nom or nom.strip() == "insee":
            organisation = o
            break
    if not organisation and lot:
        organisation = lot[0]
    if not organisation:
        print("\n  Organisation INSEE introuvable sur data.gouv.fr.\n")
        return

    print(f"  {organisation.get('name')}")
    print(f"  {organisation.get('metrics', {}).get('datasets', '?')} jeu(x) publié(s)\n")

    params = {"organization": organisation.get("id"), "page_size": 20}
    if termes:
        params["q"] = termes
    try:
        jeux = json.loads(lire(DATAGOUV + "?" + urllib.parse.urlencode(
            params))).get("data", [])
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] {e}\n")
        sys.exit(1)

    if not jeux:
        print("  Aucun jeu ne correspond. Essayez sans terme, ou d'autres mots :")
        print('      python 11_population.py --insee "population"\n')
        return

    for d in jeux:
        fichiers = [r.get("format", "") for r in d.get("resources", [])]
        formats = ", ".join(sorted({f.lower() for f in fichiers if f})[:5])
        print(f"  {d.get('title', '')[:66]}")
        print(f"    {d.get('id')}   {len(fichiers)} ressource(s)  "
              f"({formats or 'aucune'})")

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


def telecharger_archive(url):
    """Télécharge le fichier sur le disque, jamais en mémoire.

    L'archive pèse près de 200 Mo et le CSV qu'elle contient plus d'un
    gigaoctet : tout charger en mémoire mettrait la machine à genoux.
    Elle est conservée, pour permettre de relire sans retélécharger.
    """
    DONNEES.mkdir(exist_ok=True)
    if ARCHIVE.exists():
        poids = ARCHIVE.stat().st_size / 1048576
        print(f"  Archive déjà présente : {ARCHIVE} ({poids:.0f} Mo)")
        return ARCHIVE

    print(f"  Téléchargement depuis insee.fr…")
    print(f"  Environ 200 Mo, comptez quelques minutes.")
    requete = urllib.request.Request(
        url, headers={"User-Agent": "portail-territorial/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse, \
                open(ARCHIVE, "wb") as sortie:
            recu = 0
            while True:
                morceau = reponse.read(1 << 20)
                if not morceau:
                    break
                sortie.write(morceau)
                recu += len(morceau)
                print(f"\r  {recu / 1048576:.0f} Mo reçus", end="", flush=True)
    except (urllib.error.URLError, OSError) as e:
        if ARCHIVE.exists():
            ARCHIVE.unlink()
        print(f"\n\n[ERREUR] Téléchargement interrompu : {e}\n")
        sys.exit(1)
    print()
    return ARCHIVE


def fichier_de_donnees(archive):
    """Nom du CSV principal dans l'archive : le plus volumineux."""
    with zipfile.ZipFile(archive) as z:
        candidats = [n for n in z.namelist()
                     if n.lower().endswith((".csv", ".txt"))
                     and "meta" not in n.lower()]
        if not candidats:
            candidats = [n for n in z.namelist()
                         if n.lower().endswith((".csv", ".txt"))]
        if not candidats:
            print(f"\n[ERREUR] Aucun CSV dans l'archive : {z.namelist()[:6]}\n")
            sys.exit(1)
        return max(candidats, key=lambda n: z.getinfo(n).file_size)


def libelles_variables(archive):
    """Libellé de chaque variable, lu dans les métadonnées de l'archive.

    Le fichier meta_dossier_complet.csv associe à chaque code de colonne
    son intitulé en clair. C'est la source à utiliser plutôt que de
    deviner ce que désigne « BPE_2024_B207 » : elle est fournie par
    l'INSEE et suit automatiquement les changements de nomenclature.
    """
    with zipfile.ZipFile(archive) as z:
        metas = [n for n in z.namelist()
                 if "meta" in n.lower() and n.lower().endswith((".csv", ".txt"))]
        if not metas:
            return {}
        brut = z.read(metas[0])

    for encodage in ("utf-8-sig", "latin-1"):
        try:
            texte = brut.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {}

    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    lecture = csv.DictReader(io.StringIO(texte), delimiter=separateur)

    colonnes = lecture.fieldnames or []
    cle_code = next((c for c in colonnes if c.strip().upper() == "COD_VAR"), None)
    cle_libelle = next((c for c in colonnes
                        if c.strip().upper() in ("LIB_VAR", "LIB_VAR_LONG")), None)
    if not cle_code or not cle_libelle:
        return {}

    dictionnaire = {}
    for ligne in lecture:
        code = str(ligne.get(cle_code, "")).strip()
        libelle = str(ligne.get(cle_libelle, "")).strip()
        if code and libelle:
            dictionnaire.setdefault(code, libelle)
    return dictionnaire


def parcourir(archive, nom_fichier):
    """Ouvre le CSV en flux, sans jamais le charger entièrement."""
    z = zipfile.ZipFile(archive)
    flux = io.TextIOWrapper(z.open(nom_fichier), encoding="utf-8-sig",
                            errors="replace", newline="")
    premiere = flux.readline()
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    colonnes = next(csv.reader([premiere], delimiter=separateur))
    return z, flux, csv.DictReader(flux, fieldnames=colonnes,
                                   delimiter=separateur), colonnes


def lecteur(texte):
    """Ouvre le CSV en devinant son séparateur."""
    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    return csv.DictReader(io.StringIO(texte), delimiter=separateur)


# ══════════════════════════════════════════════════════════════════
# CONSTRUCTION DES INDICATEURS
# ══════════════════════════════════════════════════════════════════

RANGS = {"POP-20": 10, "POP-24": 15, "POP-21": 20, "POP-22": 30,
         "POP-23": 40,
         "LOG-01": 10, "LOG-02": 20, "LOG-03": 30, "LOG-04": 40,
         "LOG-05": 50,
         "EQU-01": 10, "EQU-02": 20, "EQU-03": 30, "EQU-04": 40}

# Chaque famille d'indicateurs alimente sa propre rubrique du site.
RUBRIQUES_PAR_FAMILLE = {"POP": "population", "LOG": "urbanisme",
                         "EQU": "equipements"}

ANCRE_LOGEMENT = "composition-parc-logements"
ANCRE_EQUIPEMENTS = "equipements-par-domaine"

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
    "LOG-01": ("Ensemble des logements recensés : résidences principales, "
               "secondaires et logements vacants."),
    "LOG-02": ("Part des logements inoccupés. Une vacance élevée peut "
               "signaler un parc ancien ou un marché détendu ; quelques "
               "pour cent sont normaux et traduisent la rotation."),
    "LOG-03": ("Part des résidences secondaires et logements occasionnels. "
               "Un indicateur de pression touristique sur le logement."),
    "LOG-04": ("Part des maisons individuelles dans le parc, par opposition "
               "aux appartements."),
    "LOG-05": ("Part des résidences principales occupées par leur "
               "propriétaire."),
    "EQU-01": ("Commerces recensés par la base permanente des équipements. "
               "Ce fichier n'en retient qu'une sélection de types : le "
               "décompte est un ordre de grandeur, non un inventaire."),
    "EQU-02": ("Équipements de santé et d'action sociale, pour la sélection "
               "de types retenue dans ce fichier."),
    "EQU-03": ("Équipements sportifs, de loisir et de culture, pour la "
               "sélection de types retenue dans ce fichier."),
    "EQU-04": ("Services aux particuliers, pour la sélection de types "
               "retenue dans ce fichier."),
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
    m["rubrique"] = RUBRIQUES_PAR_FAMILLE.get(ident[:3], RUBRIQUE)
    if ident in RANGS:
        m["rang"] = RANGS[ident]
    if ident in EXPLICATIONS:
        m["explication"] = EXPLICATIONS[ident]
    return m


def nettoyer_libelle(texte):
    """Rend lisible un intitulé de variable INSEE.

    Les libellés sont du type « Nombre de boulangeries en 2024 » : on
    retire le préfixe de dénombrement et le millésime, qui figurent déjà
    ailleurs sur la page.
    """
    propre = str(texte or "").strip()
    for prefixe in ("Nombre d'", "Nombre de ", "Nombre des ", "Nb "):
        if propre.lower().startswith(prefixe.lower()):
            propre = propre[len(prefixe):]
            break
    propre = re.sub(r"\s+en\s+\d{4}\s*$", "", propre)
    return propre[:1].upper() + propre[1:] if propre else ""


def synthetiser(ligne, colonnes, millesime, dictionnaire=None):
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
        habillage["unite_pluriel"] = "ménages"
        mesures["POP-22"] = mesure(menages, "ménages", "Ménages", **habillage)

    familles = nombre(ligne.get(colonnes.get("familles", ""), ""))
    if familles:
        mesures["POP-23"] = mesure(familles, "familles", "Familles",
                                   agregation="somme",
                                   unite_pluriel="familles")

    # ── logement ──
    cols = colonnes.get("logement") or {}
    lu = {cle: nombre(ligne.get(col, "")) for cle, col in cols.items()}
    total_log = lu.get("logements")

    if total_log:
        mesures["LOG-01"] = mesure(total_log, "logements",
                                   "Logements", agregation="somme",
                                   ancre=ANCRE_LOGEMENT,
                                   unite_pluriel="logements")
        for ident, cle, nom in (("LOG-02", "vacants", "Logements vacants"),
                                ("LOG-03", "secondaires",
                                 "Résidences secondaires")):
            effectif = lu.get(cle)
            if effectif is not None:
                mesures[ident] = mesure(
                    round(100 * effectif / total_log, 1), "%", nom,
                    obtention="recalculé", ancre=ANCRE_LOGEMENT,
                    repere=f"{espacer(effectif)} sur {espacer(total_log)}")
        maisons = lu.get("maisons")
        if maisons is not None:
            mesures["LOG-04"] = mesure(
                round(100 * maisons / total_log, 1), "%", "Maisons",
                obtention="recalculé",
                repere=f"{espacer(maisons)} sur {espacer(total_log)}")

    principales = lu.get("principales")
    proprietaires = lu.get("proprietaires")
    if principales and proprietaires is not None:
        mesures["LOG-05"] = mesure(
            round(100 * proprietaires / principales, 1), "%",
            "Propriétaires occupants", obtention="recalculé",
            repere=f"{espacer(proprietaires)} résidences principales "
                   f"sur {espacer(principales)}")

    # ── équipements ──
    dictionnaire = dictionnaire or {}
    par_domaine, detail_equipements = {}, []
    for lettre, colonnes_domaine in (colonnes.get("equipements") or {}).items():
        total = 0
        vu = False
        for col in colonnes_domaine:
            valeur = nombre(ligne.get(col, ""))
            if valeur is None:
                continue
            total += valeur
            vu = True
            if valeur:
                libelle = nettoyer_libelle(dictionnaire.get(col, ""))
                detail_equipements.append(
                    (lettre, libelle or col.split("_")[-1], valeur))
        if vu and total:
            par_domaine[lettre] = total

    for ident, lettre, nom in (("EQU-01", "B", "Commerces"),
                               ("EQU-02", "D", "Santé et action sociale"),
                               ("EQU-03", "F", "Sport, loisir et culture"),
                               ("EQU-04", "A", "Services aux particuliers")):
        if par_domaine.get(lettre):
            mesures[ident] = mesure(
                par_domaine[lettre], "équipements", nom,
                agregation="somme", unite_pluriel="équipements",
                **({"ancre": ANCRE_EQUIPEMENTS} if detail_equipements else {}))

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

    # ── blocs détaillés ──
    if total_log:
        composition = [("Résidences principales", lu.get("principales")),
                       ("Résidences secondaires", lu.get("secondaires")),
                       ("Logements vacants", lu.get("vacants")),
                       ("Maisons", lu.get("maisons")),
                       ("Appartements", lu.get("appartements"))]
        entrees = [{"titre": nom,
                    "details": {"Logements": espacer(effectif),
                                "Part": f"{100 * effectif / total_log:.1f} %"}}
                   for nom, effectif in composition if effectif]
        if entrees:
            blocs.append({
                "rubrique": "urbanisme",
                "id": ANCRE_LOGEMENT,
                "titre": "Composition du parc de logements",
                "items": entrees,
                "note": ("Maisons et appartements se recoupent avec les "
                         "catégories d'occupation : un même logement est "
                         "compté dans les deux ensembles."),
            })

    if detail_equipements:
        detail_equipements.sort(
            key=lambda x: (DOMAINES.get(x[0], ("", 99))[1], -x[2], x[1]))
        blocs.append({
            "rubrique": "equipements",
            "id": ANCRE_EQUIPEMENTS,
            "titre": ("Équipements recensés"
                      + (f" — {colonnes.get('millesime_equipements')}"
                         if colonnes.get("millesime_equipements") else "")),
            "items": [{"titre": libelle,
                       "details": {"Domaine": DOMAINES.get(
                                       lettre, ("Autre", 99))[0],
                                   "Nombre": espacer(valeur)}}
                      for lettre, libelle, valeur in detail_equipements],
            "note": ("Base permanente des équipements. Ce fichier n'en "
                     "retient qu'une sélection de types : d'autres "
                     "équipements existent sans figurer ici. Un équipement "
                     "absent d'une commune ne signifie pas que ses habitants "
                     "n'y ont pas accès, la plupart des services se "
                     "fréquentant au-delà des limites communales."),
        })

    mesures = {k: habiller(k, v) for k, v in mesures.items()}
    presentes = {b.get("id") for b in blocs}
    for m in mesures.values():
        if m.get("ancre") and m["ancre"] not in presentes:
            m.pop("ancre")
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


def analyser(colonnes_fichier):
    """Décrit ce que le fichier contient, sans rien produire."""
    colonnes = reconnaitre(colonnes_fichier)
    print("\nColonnes reconnues")
    print("─" * 60)
    for cle in ("code", "total", "hommes", "femmes", "menages", "familles"):
        print(f"  {cle:<12} {colonnes.get(cle) or 'ABSENTE'}")
    print(f"  millésime    20{colonnes['millesime']}"
          if colonnes.get("millesime") else "  millésime    inconnu")
    print(f"  âge          {len(colonnes['age'])} tranche(s) retenue(s) "
          f"sur le millésime le plus récent")
    for debut, fin_age, nom in colonnes["age"]:
        print(f"                 {libelle_tranche(debut, fin_age):<18} {nom}")
    if not colonnes.get("code"):
        print("\n  [BLOCAGE] Aucune colonne de code commune reconnue.")
        print(f"  Colonnes du fichier : {colonnes_fichier[:12]}")
    log = colonnes.get("logement") or {}
    print(f"\n  logement     {len(log)} colonne(s) reconnue(s)")
    for cle, col in sorted(log.items()):
        print(f"                 {cle:<16} {col}")

    equ = colonnes.get("equipements") or {}
    annee = colonnes.get("millesime_equipements")
    print(f"\n  équipements  {sum(len(v) for v in equ.values())} colonne(s) "
          f"sur {len(equ)} domaine(s)"
          + (f", millésime {annee}" if annee else ""))
    for lettre in sorted(equ):
        nom = DOMAINES.get(lettre, ("domaine inconnu",))[0]
        print(f"                 {lettre}  {nom:<32} "
              f"{len(equ[lettre])} type(s)")

    if not equ:
        prefixes = {}
        for nom in colonnes_fichier:
            racine = re.split(r"\d", str(nom), 1)[0].rstrip("_")
            if racine:
                prefixes[racine] = prefixes.get(racine, 0) + 1
        frequents = sorted(prefixes.items(), key=lambda x: -x[1])[:24]
        print("\n  Aucune colonne d'équipement reconnue.")
        print("  Préfixes les plus fréquents du fichier, pour identifier")
        print("  celui des équipements :")
        for racine, nombre in frequents:
            print(f"                 {racine:<24} {nombre:>4} colonne(s)")

    print(f"\n  {len(colonnes_fichier)} colonnes au total dans le fichier.")
    print()
    return colonnes


def inspecter_equipements(code_commune):
    """Liste chaque type d'équipement recensé pour une commune.

    Le fichier ne retient qu'une sélection de types de la base permanente
    des équipements, et ne donne que leur code. Cette commande affiche le
    code et l'effectif de chacun : c'est ce qui permettra de leur associer
    un libellé lisible, et de détailler la rubrique.
    """
    url = source_memorisee() or SOURCE_DEFAUT
    archive = telecharger_archive(url)
    nom = fichier_de_donnees(archive)
    dictionnaire = libelles_variables(archive)
    z, flux, lecture, colonnes_fichier = parcourir(archive, nom)
    colonnes = reconnaitre(colonnes_fichier)

    equipements = colonnes.get("equipements") or {}
    toutes = sorted(c for lot in equipements.values() for c in lot)
    if not toutes:
        flux.close(); z.close()
        print("\n  Aucune colonne d'équipement reconnue.\n")
        return

    cible = None
    for ligne in lecture:
        if str(ligne.get(colonnes["code"], "")).strip() == code_commune:
            cible = ligne
            break
    flux.close(); z.close()

    print(f"\nÉquipements recensés — commune {code_commune}")
    print("─" * 60)
    print(f"  {len(toutes)} type(s) d'équipement dans le fichier, "
          f"millésime {colonnes.get('millesime_equipements')}\n")

    for lettre in sorted(equipements):
        libelle = DOMAINES.get(lettre, ("domaine inconnu", 99))[0]
        print(f"  ── {lettre} · {libelle} ──")
        for colonne in sorted(equipements[lettre]):
            code_type = colonne.split("_")[-1]
            valeur = nombre(cible.get(colonne, "")) if cible else None
            marque = f"{valeur:>4}" if valeur else "   ·"
            libelle = nettoyer_libelle(dictionnaire.get(colonne, ""))
            print(f"     {code_type:<8} {marque}   {libelle}")
    if not dictionnaire:
        print("\n  [attention] Métadonnées introuvables dans l'archive :")
        print("  les libellés ne peuvent pas être associés aux codes.")
    print()


def main():
    if "--chercher" in sys.argv:
        i = sys.argv.index("--chercher")
        termes = (sys.argv[i + 1]
                  if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--")
                  else None)
        chercher(termes)
        return

    if "--insee" in sys.argv:
        i = sys.argv.index("--insee")
        termes = (sys.argv[i + 1]
                  if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--")
                  else None)
        chercher_insee(termes)
        return

    if "--ressources" in sys.argv:
        i = sys.argv.index("--ressources")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez un identifiant de jeu de données.\n")
            sys.exit(1)
        ressources(sys.argv[i + 1])
        return

    url = source_memorisee() or SOURCE_DEFAUT

    if "--source" in sys.argv:
        i = sys.argv.index("--source")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez l'adresse du fichier.\n")
            sys.exit(1)
        url = sys.argv[i + 1]
        memoriser(url)
        if ARCHIVE.exists():
            ARCHIVE.unlink()
        print(f"\nSource mémorisée : {url}")

    if "--equipements" in sys.argv:
        i = sys.argv.index("--equipements")
        code = (sys.argv[i + 1]
                if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--")
                else "38416")
        inspecter_equipements(code)
        return

    if "--colonnes" in sys.argv:
        archive = telecharger_archive(url)
        nom = fichier_de_donnees(archive)
        print(f"  Fichier de données : {nom}")
        z, flux, _, colonnes_fichier = parcourir(archive, nom)
        analyser(colonnes_fichier)
        flux.close(); z.close()
        return

    print("\nPopulation détaillée — recensement INSEE")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    archive = telecharger_archive(url)
    nom = fichier_de_donnees(archive)
    print(f"  Fichier de données : {nom}")

    dictionnaire = libelles_variables(archive)
    print(f"  Dictionnaire des variables : "
          f"{len(dictionnaire)} libellé(s)" if dictionnaire
          else "  [attention] Métadonnées absentes : les équipements "
               "resteront sans libellé.")

    z, flux, lecture, colonnes_fichier = parcourir(archive, nom)
    colonnes = reconnaitre(colonnes_fichier)
    if not colonnes.get("code"):
        flux.close(); z.close()
        print("\n[BLOCAGE] Colonne de code commune introuvable.")
        print("  Lancez --colonnes pour voir ce que contient le fichier.\n")
        sys.exit(1)
    if not colonnes["age"]:
        print("  [attention] Aucune tranche d'âge reconnue.")
    if not colonnes.get("logement"):
        print("  [attention] Aucune colonne de logement reconnue.")
    if not colonnes.get("equipements"):
        print("  [attention] Aucune colonne d'équipement reconnue.")
        pistes = [c for c in colonnes_fichier
                  if c.upper().startswith(("NB_", "EQU", "BPE"))][:12]
        print(f"               Colonnes commençant par NB_, EQU ou BPE : "
              f"{pistes or 'aucune'}")
        print(f"               Lancez --colonnes et transmettez la sortie.")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    attendues = {c["code"]: c["nom"] for c in communes}
    resultat, lignes_lues = {}, 0

    for ligne in lecture:
        lignes_lues += 1
        if lignes_lues % 5000 == 0:
            print(f"\r  {espacer(lignes_lues)} lignes parcourues, "
                  f"{len(resultat)}/{len(attendues)} communes trouvées",
                  end="", flush=True)
        code = str(ligne.get(colonnes["code"], "")).strip()
        if code not in attendues or code in resultat:
            continue
        synthese = synthetiser(ligne, colonnes, colonnes.get("millesime"),
                               dictionnaire)
        if synthese["mesures"]:
            resultat[code] = synthese
        if len(resultat) == len(attendues):
            break

    flux.close(); z.close()

    manquantes = sorted(set(attendues) - set(resultat))
    print(f"\r  Lignes parcourues    : {espacer(lignes_lues)}"
          f"{' ' * 30}")
    print(f"  Communes renseignées : {len(resultat)}/{len(attendues)}")
    if colonnes.get("millesime"):
        print(f"  Millésime            : 20{colonnes['millesime']}")
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
    print(f"  Fichier : {SORTIE}")
    print(f"\n  L'archive est conservée dans {ARCHIVE}.")
    print(f"  Supprimez-la pour forcer un nouveau téléchargement.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
