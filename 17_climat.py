"""
17_climat.py — Climat mensuel (Météo-France)
=============================================

Publie, pour le territoire, la température, la pluie et surtout les
COMPTAGES de jours remarquables — jours à 30 °C ou plus, jours de gel —
avec leur historique depuis l'ouverture du poste.

Source : « Données climatologiques de base — mensuelles », Météo-France,
publiées sur data.gouv.fr en Licence Ouverte. **Aucune clé d'API n'est
nécessaire** : la clé du portail Météo-France ne sert qu'à la vigilance
et au temps réel, pas à ces fichiers.

PARTICULARITÉ : le climat se mesure en POSTES, pas en communes. Comme
les nappes et les rivières, la donnée est rattachée au canton et à
l'intercommunalité, avec le poste nommé, son altitude et sa distance.
Annoncer une température « à Chatte » quand le poste est à Rencurel,
six cent mètres plus haut, serait faux de plusieurs degrés.

POURQUOI DES COMPTAGES PLUTÔT QUE DES MOYENNES. Une température moyenne
annuelle bouge d'un ou deux dixièmes de degré par décennie : sur un
graphique, cela ne se voit pas, et cela ne se raconte pas. Le nombre de
jours à plus de 30 °C, lui, peut tripler sur la même période. Les deux
disent la même chose ; un seul se lit.

Produit :
    data/mesures-climat.json   repris par 03_agregation.py

Utilisation :
    python 17_climat.py
    python 17_climat.py --tout          ignore le cache et retélécharge
    python 17_climat.py --ressources    liste les fichiers publiés
    python 17_climat.py --postes        liste les postes de l'emprise
"""

import gzip
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-climat.json"

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
JEU = "donnees-climatologiques-de-base-mensuelles"

SOURCE = "Météo-France — données climatologiques de base"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "climat"
ANCRE = "postes-climatiques"
DELAI = 300

# Marge autour du territoire, en degrés. Un poste un peu à l'extérieur
# reste utile ; sa distance est affichée.
MARGE = 0.12
SEUIL_ELOIGNEMENT = 20        # km au-delà desquels le poste devient indicatif

# Un mois de température ne compte que s'il a été mesuré presque en
# entier. Le fichier donne « NBTM », le nombre de jours réellement
# relevés : un mois calculé sur cinq jours ne vaut pas un mois calculé
# sur trente et un, et rien ne le distinguerait sans ce champ.
JOURS_MINIMUM = 25

# Une année ne compte que si presque tous ses mois comptent. Onze sur
# douze : un mois manquant ne doit pas effacer l'année, deux si.
MOIS_PAR_AN = 11

# Normale de référence, au sens de l'Organisation météorologique
# mondiale. C'est l'écart à cette normale qui donne son sens à une
# température, jamais la valeur brute.
NORMALE = (1991, 2020)
NORMALE_MINIMUM = 20          # années présentes exigées pour la calculer

ANNEES_MINIMUM = 15           # en deçà, pas d'historique publié

# Un poste fermé ne décrit plus le climat d'aujourd'hui. Le poste de
# Saint-Marcellin, à cinq kilomètres du centre, a vingt-quatre années
# complètes — et s'est arrêté en 1985. Retenu pour sa proximité, il
# faisait publier « Jours à 30 °C en 1985 » sur un portail qui parle du
# présent. La proximité ne vaut donc qu'à service égal.
ANNEES_FRAICHEUR = 3          # années d'ancienneté tolérées


# ══════════════════════════════════════════════════════════════════
# COLONNES
#
# Le fichier mensuel porte plus de deux cents colonnes. Six suffisent,
# et chacune est là pour une raison.
# ══════════════════════════════════════════════════════════════════

COLONNES = {
    "poste": "NUM_POSTE",
    "nom": "NOM_USUEL",
    "lat": "LAT",
    "lon": "LON",
    "altitude": "ALTI",
    "mois": "AAAAMM",
    "temperature": "TM",        # moyenne des températures moyennes du mois
    "jours_mesures": "NBTM",    # jours réellement relevés — le garde-fou
    "pluie": "RR",              # cumul du mois
    "gel": "NBJGELEE",          # jours où le minimum est passé sous 0 °C
    "chauds": "NBJTX30",        # jours où le maximum a atteint 30 °C
    "tres_chauds": "NBJTX35",
}


# ══════════════════════════════════════════════════════════════════

def lire(url, binaire=False):
    requete = urllib.request.Request(
        url, headers={"User-Agent": "portail-territorial/1.0"})
    with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
        corps = reponse.read()
    return corps if binaire else corps.decode("utf-8", errors="replace")


def ressources_du_jeu():
    try:
        contenu = json.loads(lire(DATAGOUV + JEU + "/"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] data.gouv.fr injoignable : {e}\n")
        return None
    return contenu.get("resources", [])


def departements(communes):
    """Départements réellement présents dans le référentiel.

    Deux chiffres suffisent ici ; la Corse et l'outre-mer ne sont pas
    concernés par ce périmètre, et le jour où ils le seraient, cette
    ligne est le seul endroit à revoir.
    """
    return sorted({c["code"][:2] for c in communes})


def fichiers_du_departement(ressources, codes):
    """Fichiers mensuels du ou des départements du territoire.

    Le jeu publie un fichier par département et par tranche d'années —
    avant 1949, la longue période intermédiaire, et les deux dernières
    années mises à jour quotidiennement. On les prend tous : leur somme
    fait trois mégaoctets, et c'est la seule façon d'avoir à la fois la
    profondeur et l'année en cours.

    Les noms sont reconnus par motif plutôt que codés en dur : la
    tranche courante change de nom chaque année.
    """
    retenus = []
    for r in ressources:
        titre = str(r.get("title") or "")
        url = str(r.get("url") or "")
        if not url or "MENS" not in titre.upper():
            continue
        if not any(f"_{code}_" in titre or f"MENSQ_{code}_" in url
                   for code in codes):
            continue
        retenus.append(r)
    retenus.sort(key=lambda r: str(r.get("title")))
    return retenus


def cache_de(url):
    empreinte = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return DONNEES / f"cache-climat-{empreinte}.csv"


def telecharger(ressource):
    """Rend le contenu décompressé, en s'appuyant sur un cache local."""
    DONNEES.mkdir(exist_ok=True)
    url = ressource.get("url")
    cache = cache_de(url)
    if cache.exists() and "--tout" not in sys.argv:
        print(f"    déjà en cache : {cache.name} "
              f"({cache.stat().st_size / 1048576:.1f} Mo)")
        return cache.read_text(encoding="utf-8")

    print("    téléchargement…", end=" ", flush=True)
    try:
        brut = lire(url, binaire=True)
    except (urllib.error.URLError, OSError) as e:
        print(f"échec : {e}")
        return None

    # Le fichier est servi compressé. On accepte aussi qu'il ne le soit
    # pas : le format publié a déjà changé une fois sur d'autres jeux.
    if brut[:2] == b"\x1f\x8b":
        try:
            brut = gzip.decompress(brut)
        except OSError as e:
            print(f"échec de décompression : {e}")
            return None

    texte = None
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            texte = brut.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    if texte is None:
        print("échec : encodage non reconnu")
        return None

    print(f"{len(brut) / 1048576:.1f} Mo")
    cache.write_text(texte, encoding="utf-8")
    return texte


# Particules qui restent en minuscules dans un nom de lieu français.
PARTICULES = ("de", "du", "des", "la", "le", "les", "en", "sur", "sous",
              "aux", "et", "d", "l")


def joli_nom(brut):
    """Nom de poste lisible, à partir du libellé de Météo-France.

    Les libellés sont en capitales et portent parfois un suffixe
    technique : « CHATTE_SAPC », « SERRE-NERPOL_SAPC ». Passer
    simplement par « title() » donnerait « Chatte_Sapc » et
    « Saint-Jean-En-Royans » — les particules prennent la majuscule, ce
    qu'aucun nom de lieu français ne fait.
    """
    texte = str(brut or "").strip()
    # Suffixe de type de station, collé au nom par un souligné.
    if "_" in texte:
        tete, _, queue = texte.rpartition("_")
        if tete and len(queue) <= 5 and queue.isalpha():
            texte = tete
    texte = texte.replace("_", " ")

    sortie, premier = [], True
    for morceau in texte.replace("-", " - ").split(" "):
        if not morceau:
            continue
        if morceau == "-":
            sortie.append("-")
            continue
        bas = morceau.lower()
        mot = bas if (bas in PARTICULES and not premier) else bas.capitalize()
        sortie.append(mot)
        premier = False
    return " ".join(sortie).replace(" - ", "-")


def nombre(valeur):
    texte = str(valeur or "").strip().replace(",", ".")
    if not texte or texte.lower() in ("na", "nd", "-", "s"):
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def emprise(communes):
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    if not lats or not lons:
        return None
    return (min(lons) - MARGE, min(lats) - MARGE,
            max(lons) + MARGE, max(lats) + MARGE)


def centre(communes):
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    if not lats or not lons:
        return None
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def distance_km(a, b):
    """Distance approchée entre deux points, suffisante à cette échelle."""
    import math
    (x1, y1), (x2, y2) = a, b
    moyenne = math.radians((y1 + y2) / 2)
    dx = (x2 - x1) * 111.32 * math.cos(moyenne)
    dy = (y2 - y1) * 110.57
    return math.hypot(dx, dy)


def lignes(texte):
    """Lecteur CSV tolérant au séparateur.

    Le fichier de Météo-France est en points-virgules, mais la
    convention varie d'un jeu à l'autre chez le même producteur.
    """
    import csv
    premiere = texte.split("\n", 1)[0]
    separateur = max((";", ",", "\t"), key=premiere.count)
    return csv.DictReader(io.StringIO(texte), delimiter=separateur)


def relever(textes, boite, repere):
    """Postes de l'emprise, et leurs relevés mensuels.

    Renvoie un dictionnaire poste → {"identite": …, "mois": {(a, m): …}}.
    Une seule traversée par fichier : ces fichiers font plusieurs
    dizaines de milliers de lignes, et il n'y a pas de raison de les
    parcourir deux fois.
    """
    xmin, ymin, xmax, ymax = boite
    postes = {}
    lues = 0
    for texte in textes:
        for ligne in lignes(texte):
            lues += 1
            code = str(ligne.get(COLONNES["poste"], "")).strip()
            lat = nombre(ligne.get(COLONNES["lat"]))
            lon = nombre(ligne.get(COLONNES["lon"]))
            if not code or lat is None or lon is None:
                continue
            if not (xmin <= lon <= xmax and ymin <= lat <= ymax):
                continue

            aaaamm = str(ligne.get(COLONNES["mois"], "")).strip()
            if len(aaaamm) != 6 or not aaaamm.isdigit():
                continue
            an, mois = int(aaaamm[:4]), int(aaaamm[4:])

            poste = postes.setdefault(code, {
                "code": code,
                "nom": str(ligne.get(COLONNES["nom"], "") or code).strip(),
                "latitude": lat, "longitude": lon,
                "altitude": nombre(ligne.get(COLONNES["altitude"])),
                "distance": (distance_km(repere, (lon, lat))
                             if repere else None),
                "mois": {},
            })
            poste["mois"][(an, mois)] = {
                "temperature": nombre(ligne.get(COLONNES["temperature"])),
                "jours": nombre(ligne.get(COLONNES["jours_mesures"])) or 0,
                "pluie": nombre(ligne.get(COLONNES["pluie"])),
                "gel": nombre(ligne.get(COLONNES["gel"])),
                "chauds": nombre(ligne.get(COLONNES["chauds"])),
                "tres_chauds": nombre(ligne.get(COLONNES["tres_chauds"])),
            }
    return postes, lues


# ══════════════════════════════════════════════════════════════════
# AGRÉGATION ANNUELLE
#
# Deux règles, et elles ne sont pas symétriques.
#
# La TEMPÉRATURE est une moyenne : elle exige que le mois ait été
# mesuré presque en entier, sans quoi la moyenne annuelle penche vers
# les mois les mieux suivis. Le champ « NBTM » le dit.
#
# Les COMPTAGES — jours de gel, jours chauds — sont des sommes. Un mois
# incomplet les sous-estime mécaniquement, et le manque ne se voit pas.
# On applique donc la même exigence, pour la même raison.
# ══════════════════════════════════════════════════════════════════

def moyenne(valeurs):
    reels = [v for v in valeurs if v is not None]
    return sum(reels) / len(reels) if reels else None


def par_annee(poste):
    """Valeurs annuelles d'un poste, années incomplètes écartées."""
    groupes = {}
    for (an, mois), m in poste["mois"].items():
        groupes.setdefault(an, []).append(m)

    annuel = {}
    for an, mois in sorted(groupes.items()):
        complets = [m for m in mois if m["jours"] >= JOURS_MINIMUM]
        if len(complets) < MOIS_PAR_AN:
            continue
        temperature = moyenne([m["temperature"] for m in complets])
        if temperature is None:
            continue
        entree = {"temperature": round(temperature, 2), "mois": len(complets)}
        for cle in ("gel", "chauds", "tres_chauds"):
            suite = [m[cle] for m in complets if m[cle] is not None]
            entree[cle] = int(sum(suite)) if len(suite) >= MOIS_PAR_AN else None
        pluie = [m["pluie"] for m in complets if m["pluie"] is not None]
        entree["pluie"] = (round(sum(pluie)) if len(pluie) >= MOIS_PAR_AN
                           else None)
        annuel[an] = entree
    return annuel


def normale_de(annuel):
    """Température moyenne de la période de référence, ou rien.

    Une « normale » calculée sur douze années n'en est pas une : on
    exige la plus grande partie de la trentaine, faute de quoi l'écart
    affiché n'aurait pas de sens et ne serait pas comparable à ce que
    publie Météo-France.
    """
    debut, fin = NORMALE
    retenues = [v["temperature"] for a, v in annuel.items() if debut <= a <= fin]
    if len(retenues) < NORMALE_MINIMUM:
        return None, len(retenues)
    return sum(retenues) / len(retenues), len(retenues)


def poste_de_reference(postes, aujourdhui=None):
    """Le poste qui portera les indicateurs et les graphiques.

    Trois critères, dans cet ordre, et l'ordre est ce qui compte :

    1. **le poste mesure encore.** Un poste fermé raconte le climat
       d'une autre époque ; sur une fiche qui annonce « en 2025 », il
       annoncerait « en 1985 » ;
    2. **il a une histoire suffisante** — quinze années complètes ;
    3. **il est proche.** Ce n'est qu'alors que la distance départage.

    Sans le premier critère, le poste de Saint-Marcellin l'emportait
    avec ses vingt-quatre années arrêtées en 1985.
    """
    aujourdhui = aujourdhui or date.today()
    limite = aujourdhui.year - ANNEES_FRAICHEUR

    candidats, fermes = [], []
    for poste in postes.values():
        annuel = par_annee(poste)
        if len(annuel) < ANNEES_MINIMUM:
            continue
        if max(annuel) < limite:
            fermes.append((poste, annuel))
            continue
        candidats.append((poste, annuel))

    if not candidats:
        return None, None, fermes
    retenu = min(candidats,
                 key=lambda x: (x[0]["distance"] is None,
                                x[0]["distance"] or 0))
    return retenu[0], retenu[1], fermes


# ══════════════════════════════════════════════════════════════════
# PUBLICATION
# ══════════════════════════════════════════════════════════════════

def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def signe(ecart):
    return f"+{ecart:.1f}".replace(".", ",") if ecart >= 0 else \
        f"{ecart:.1f}".replace(".", ",")


def synthetiser(poste, annuel):
    derniere = max(annuel)
    valeurs = annuel[derniere]
    normale, annees_normale = normale_de(annuel)
    repere_poste = (f"Poste de {joli_nom(poste['nom'])}"
                    + (f", {poste['altitude']:.0f} m" if poste["altitude"]
                       else "")
                    + (f" · à {poste['distance']:.0f} km"
                       if poste["distance"] is not None else ""))

    mesures = {}
    ecart = None
    if normale is not None:
        ecart = valeurs["temperature"] - normale
    mesures["MET-10"] = mesure(
        valeurs["temperature"], "°C",
        f"Température moyenne en {derniere}", rang=10, ancre=ANCRE,
        repere=(f"{signe(ecart)} °C par rapport à la normale "
                f"{NORMALE[0]}-{NORMALE[1]}" if ecart is not None
                else repere_poste),
        explication=("Moyenne des températures moyennes mensuelles du "
                     "poste. Une température ne se lit pas dans l'absolu : "
                     "c'est son écart à la normale de trente ans qui "
                     "renseigne."))

    if valeurs.get("chauds") is not None:
        mesures["MET-11"] = mesure(
            valeurs["chauds"], "jours",
            f"Jours à 30 °C ou plus en {derniere}", rang=20, ancre=ANCRE,
            explication=("Nombre de jours où la température maximale a "
                         "atteint 30 °C. Un comptage se compare d'une année "
                         "sur l'autre sans précaution particulière, ce qui "
                         "n'est pas le cas d'une moyenne."))
    if valeurs.get("gel") is not None:
        mesures["MET-12"] = mesure(
            valeurs["gel"], "jours",
            f"Jours de gel en {derniere}", rang=30, ancre=ANCRE,
            explication=("Nombre de jours où la température minimale est "
                         "passée sous zéro."))
    if valeurs.get("pluie") is not None:
        mesures["MET-13"] = mesure(
            valeurs["pluie"], "mm",
            f"Précipitations en {derniere}", rang=40, ancre=ANCRE,
            explication="Cumul annuel relevé au poste.")

    reserve = ("Le climat se mesure en postes, non en communes. Ces "
               "valeurs sont celles du poste nommé ci-dessus ; sur un "
               "territoire qui va de deux cents à quinze cents mètres, "
               "l'écart entre la vallée et le plateau se compte en "
               "degrés."
               + (" Ce poste est éloigné du territoire : ses valeurs n'en "
                  "sont qu'une indication approchée."
                  if (poste["distance"] or 0) > SEUIL_ELOIGNEMENT else ""))

    annees = sorted(annuel)
    details = {
        "Poste": joli_nom(poste["nom"]),
        "Numéro": poste["code"],
        "Période couverte": f"{annees[0]}-{annees[-1]}",
        "Années complètes": str(len(annuel)),
    }
    if poste["altitude"] is not None:
        details["Altitude"] = f"{poste['altitude']:.0f} m"
    if poste["distance"] is not None:
        details["Distance au centre"] = f"{poste['distance']:.0f} km"
    if normale is not None:
        details[f"Normale {NORMALE[0]}-{NORMALE[1]}"] = (
            f"{normale:.1f} °C".replace(".", ","))
    else:
        details[f"Normale {NORMALE[0]}-{NORMALE[1]}"] = (
            f"non calculable — {annees_normale} années disponibles sur "
            f"{NORMALE_MINIMUM} exigées")

    blocs = [{
        "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE, "id": ANCRE,
        "titre": "Poste de mesure climatique",
        "items": [{"titre": joli_nom(poste["nom"]), "details": details}],
        "lien": {"url": "https://meteo.data.gouv.fr/",
                 "libelle": "Données climatologiques de Météo-France"},
        "note": reserve,
    }]

    return {"mesures": mesures, "blocs": blocs,
            "chroniques": chroniques(poste, annuel, normale)}


def chroniques(poste, annuel, normale):
    """Les séries publiées, et l'ordre dans lequel elles se lisent.

    Les comptages d'abord : ce sont eux qui montrent l'évolution. Les
    bandes ensuite, qui la font voir d'un coup d'œil. La température
    moyenne en dernier, parce qu'elle bouge peu et se lit mal.
    """
    annees = sorted(annuel)
    nom = joli_nom(poste["nom"])
    altitude = f" ({poste['altitude']:.0f} m)" if poste["altitude"] else ""
    source = f"{SOURCE} · poste {poste['code']} · {annees[0]}-{annees[-1]}"
    commun = {"rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
              "pas": "an", "debut": str(annees[0]), "source": source}

    def suite(cle):
        return [annuel[a].get(cle) for a in annees]

    series = []
    def utile(cle):
        """Série de comptage qui dit quelque chose.

        Trente-huit barres à zéro occupent un écran sans rien
        apprendre. C'est la même règle que pour l'agriculture
        biologique, pour la même raison.
        """
        valeurs = suite(cle)
        return any(v for v in valeurs if v is not None)

    if utile("chauds"):
        series.append(dict(
            commun, id="climat-jours-chauds", forme="barres", rang=10,
            titre=f"Jours à 30 °C ou plus, poste de {nom}{altitude}",
            unite="jours", decimales=0, valeurs=suite("chauds"),
            note=("Un comptage, non une moyenne : aucune précaution "
                  "statistique n'est nécessaire pour le comparer d'une "
                  "année sur l'autre. Les années incomplètes sont "
                  "absentes de la série.")))
    if utile("gel"):
        series.append(dict(
            commun, id="climat-jours-gel", forme="barres", rang=20,
            titre=f"Jours de gel, poste de {nom}{altitude}",
            unite="jours", decimales=0, valeurs=suite("gel")))

    if normale is not None:
        ecarts = [round(annuel[a]["temperature"] - normale, 2) for a in annees]
        series.append(dict(
            commun, id="climat-bandes", forme="bandes", rang=30,
            unite="°C", decimales=1, valeurs=ecarts,
            libelle_serie=f"Écart à la normale {NORMALE[0]}-{NORMALE[1]}",
            titre=f"Écart de la température annuelle à la normale, {nom}",
            note=("Une bande par année, du bleu au rouge. Cette image ne "
                  "permet de vérifier aucune valeur : c'est le tableau "
                  "ci-dessous qui les porte, et le graphique des jours "
                  "chauds qui les chiffre.")))

    series.append(dict(
        commun, id="climat-temperature", forme="barres", rang=40,
        titre=f"Température moyenne annuelle, poste de {nom}{altitude}",
        unite="°C", decimales=1,
        valeurs=[annuel[a]["temperature"] for a in annees],
        note=("Une moyenne annuelle bouge de quelques dixièmes de degré "
              "par décennie : l'évolution s'y voit mal, et c'est pour "
              "cela que les comptages de jours la précèdent.")))
    return series


# ══════════════════════════════════════════════════════════════════

def main():
    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    print("\nClimat mensuel — Météo-France")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    donnees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    canton = (donnees.get("cantons") or [None])[0]
    code_epci = donnees["perimetre"]["epci"][0]

    ressources = ressources_du_jeu()
    if ressources is None:
        sys.exit(1)

    codes = departements(communes)
    fichiers = fichiers_du_departement(ressources, codes)

    if "--ressources" in sys.argv:
        print(f"\n  Départements du territoire : {', '.join(codes)}")
        print(f"  {len(fichiers)} fichier(s) retenu(s) sur "
              f"{len(ressources)} publié(s) :\n")
        for r in fichiers:
            taille = r.get("filesize") or 0
            print(f"    {str(r.get('title'))[:56]:<58} {taille / 1024:.0f} Ko")
        print()
        return

    if not fichiers:
        print(f"\n[BLOCAGE] Aucun fichier mensuel pour le(s) département(s) "
              f"{', '.join(codes)}.")
        print("  Le jeu de données a peut-être changé de nomenclature.")
        print("  Vérifiez : python 17_climat.py --ressources\n")
        sys.exit(1)

    print(f"  Département(s) : {', '.join(codes)}")
    print(f"  Fichiers       : {len(fichiers)}")
    textes = []
    for r in fichiers:
        print(f"    {str(r.get('title'))[:52]:<54}", end=" ", flush=True)
        texte = telecharger(r)
        if texte:
            textes.append(texte)
    if not textes:
        print("\n[BLOCAGE] Aucun fichier n'a pu être lu. Rien n'a été "
              "écrit.\n")
        sys.exit(1)

    boite = emprise(communes)
    repere = centre(communes)
    if not boite:
        print("\n[ERREUR] Coordonnées absentes du référentiel.\n")
        sys.exit(1)

    postes, lues = relever(textes, boite, repere)
    print(f"\n  Lignes parcourues : {lues}")
    print(f"  Postes dans l'emprise : {len(postes)}")

    if "--postes" in sys.argv or not postes:
        ordonnes = sorted(postes.values(),
                          key=lambda x: (x["distance"] is None,
                                         x["distance"] or 0))
        for p in ordonnes:
            annuel = par_annee(p)
            annees = sorted(annuel)
            etendue = f"{annees[0]}-{annees[-1]}" if annees else "—"
            altitude = f"{p['altitude']:.0f} m" if p["altitude"] else ""
            eloignement = (f"{p['distance']:.0f} km"
                           if p["distance"] is not None else "")
            print(f"    {p['code']:<10} {p['nom'][:24]:<26} "
                  f"{altitude:<8}{eloignement:<8}"
                  f"{len(annuel):>3} années complètes {etendue}")
        if not postes:
            print("\n  Aucun poste sur ce territoire. Rien n'a été écrit — "
                  "c'est un résultat, pas une erreur.\n")
        if "--postes" in sys.argv:
            print()
            return

    poste, annuel, fermes = poste_de_reference(postes)
    if fermes:
        print(f"  Postes écartés car sans mesure récente : {len(fermes)}")
        for p, a in sorted(fermes, key=lambda x: (x[0]["distance"] or 0))[:3]:
            print(f"    {joli_nom(p['nom'])[:24]:<26} "
                  f"{len(a):>3} années, arrêté en {max(a)}")
    if poste is None:
        print(f"\n  Aucun poste ne réunit {ANNEES_MINIMUM} années complètes "
              f"et des mesures récentes.")
        print("  Rien n'a été écrit — c'est un résultat, pas une erreur.\n")
        return

    synthese = synthetiser(poste, annuel)
    territoires = {}
    if canton:
        territoires[f"canton:{canton['code']}"] = synthese
    territoires[f"epci:{code_epci}"] = synthese

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "mensuelle",
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    annees = sorted(annuel)
    normale, _ = normale_de(annuel)
    derniere = annees[-1]
    print(f"\n  Poste retenu   : {joli_nom(poste['nom'])} ({poste['code']})"
          + (f", {poste['altitude']:.0f} m" if poste["altitude"] else "")
          + (f", à {poste['distance']:.0f} km" if poste["distance"] is not None
             else ""))
    print(f"  Années complètes : {len(annuel)}  ({annees[0]}-{annees[-1]})")
    print(f"  Dernière année complète : {annees[-1]}")
    if normale is not None:
        ecart = annuel[derniere]["temperature"] - normale
        print(f"  Normale {NORMALE[0]}-{NORMALE[1]} : {normale:.1f} °C")
        print(f"  {derniere} : {annuel[derniere]['temperature']:.1f} °C "
              f"({signe(ecart)} °C)")
    else:
        print(f"  Normale {NORMALE[0]}-{NORMALE[1]} : non calculable")
    if annuel[derniere].get("chauds") is not None:
        print(f"  Jours à 30 °C en {derniere} : "
              f"{annuel[derniere]['chauds']}")
    print(f"  Séries publiées : {len(synthese['chroniques'])}")
    print("  Rattaché au canton et à l'intercommunalité, pas aux communes.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
