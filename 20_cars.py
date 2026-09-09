"""
20_cars.py — Desserte en autocar, depuis le GTFS
=================================================

Publie, commune par commune, les arrêts d'autocar, les lignes qui les
desservent et le nombre de passages un jour de référence.

CE QUE CETTE RUBRIQUE APPORTE
------------------------------
« Combien de cars par jour ? » est la question qu'on se pose depuis un
village, et personne n'y répond commune par commune. Les calculateurs
d'itinéraire répondent « d'où à où » ; ils ne disent pas ce que vaut la
desserte d'un lieu. C'est pourtant ce chiffre qui décide si l'on peut
vivre là sans voiture.

LA LICENCE N'EST PAS CELLE DU RESTE DU SITE
--------------------------------------------
Le GTFS de cars Région Isère est publié sous **ODbL**, comme les
données SNCF et à la différence de la Licence Ouverte qui couvre les
autres sources du portail. L'ODbL impose, au-delà de l'attribution, le
**partage à l'identique** des bases dérivées. Ce collecteur écrit donc
« ODbL 1.0 » dans chacune de ses mesures ; le générateur, depuis la
version 36, affiche les licences source par source.

LE JOUR DE RÉFÉRENCE — LA DÉCISION QUI FAIT TOUT
-------------------------------------------------
Un GTFS ne décrit pas « la desserte », il décrit un calendrier. Compter
les passages sans dire de quel jour on parle produirait un nombre qui
ne veut rien dire : sur ces réseaux, un mardi de période scolaire et un
dimanche d'août n'ont pas de commune mesure.

Deux jours sont donc comptés et publiés séparément :

  · un **mardi** de période scolaire — la desserte ordinaire ;
  · un **samedi** — ce qui reste quand les cars scolaires ne roulent
    pas.

Les deux dates retenues sont écrites sur la page. C'est la seule façon
honnête de publier ce chiffre.

LE TRANSPORT SCOLAIRE — CE QUE JE N'AI PAS TRANCHÉ
---------------------------------------------------
Une partie des 495 lignes du réseau sont des services scolaires. Les
compter comme des cars ouverts à tous gonflerait la desserte des
petites communes d'un facteur deux ou trois. Or **le GTFS ne porte
aucun champ normalisé qui les distingue**.

Plutôt que d'inventer un critère que je n'ai pas vérifié, ce script
**inventorie les lignes et le dit**. À la première exécution, il écrit
les familles de noms de lignes rencontrées, avec leur nombre de
courses. C'est à la lecture de cet inventaire que se règle
MOTIFS_SCOLAIRES, plus bas — pas avant.

Tant que cette liste est vide, la desserte publiée est la desserte
TOTALE, et la note de la page le dit franchement.

Produit :
    data/mesures-cars.json   repris par 03_agregation.py

Utilisation :
    python 20_cars.py
    python 20_cars.py --inventaire   n'écrit rien, décrit le réseau
    python 20_cars.py --archive F    lit une archive GTFS déjà présente
"""

import csv
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
CONTOURS = DONNEES / "contours.json"
SORTIE = DONNEES / "mesures-cars.json"
CACHE = DONNEES / "cache-cars-gtfs.zip"

# Ressource « cars Région Isère — offre théorique au format GTFS »,
# publiée sur transport.data.gouv.fr et servie par data.gouv.fr.
# L'adresse est celle de la RESSOURCE, non du fichier : data.gouv.fr
# redirige vers l'archive courante, dont le nom porte un horodatage.
# Écrire le nom du fichier en dur nous ferait collecter une version
# figée sans que rien ne le signale.
GTFS_URL = ("https://www.data.gouv.fr/api/1/datasets/r/"
            "40ee9d6c-3bb9-409e-b670-986212de63f2")

SOURCE = ("cars Région Isère — offre théorique GTFS "
          "(transport.data.gouv.fr)")
LICENCE = "ODbL 1.0"

VERSION = 1
RUBRIQUE = "transports"
SOUS_RUBRIQUE = "autocar"
ANCRE = "arrets-de-car"

DELAI = 180
TENTATIVES = 3

# ── Réglages arbitrables ────────────────────────────────────────────

# Motifs, en minuscules, reconnaissant une ligne scolaire dans son nom
# ou son numéro. VIDE À DESSEIN : voir l'en-tête. À remplir après
# lecture de « python 20_cars.py --inventaire », jamais avant.
MOTIFS_SCOLAIRES = ()

# Un arrêt dont aucune course ne part le jour de référence n'est pas
# publié comme desservi. Il peut exister sur le terrain — poteau, abri —
# sans qu'aucun car s'y arrête ce jour-là.
PASSAGES_MINIMUM = 1

# Décalage à partir d'aujourd'hui pour choisir les jours de référence.
# Une semaine : assez loin pour éviter un jour férié isolé ou une
# perturbation ponctuelle, assez près pour décrire l'offre courante.
JOURS_D_AVANCE = 7


# ══════════════════════════════════════════════════════════════════
# GÉOMÉTRIE
# ══════════════════════════════════════════════════════════════════

def dans_anneau(lon, lat, anneau):
    """Point dans un anneau fermé, par lancer de rayon."""
    dedans = False
    n = len(anneau)
    for i in range(n):
        x1, y1 = anneau[i][0], anneau[i][1]
        x2, y2 = anneau[(i + 1) % n][0], anneau[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            if y2 != y1 and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                dedans = not dedans
    return dedans


def dans_contour(lon, lat, geometrie):
    """Point dans un contour GeoJSON, Polygon ou MultiPolygon.

    Les anneaux intérieurs — les trous — sont pris en compte : une
    commune enclavant une autre ne doit pas s'attribuer ses arrêts.
    """
    if not isinstance(geometrie, dict):
        return False
    forme = geometrie.get("type")
    coords = geometrie.get("coordinates") or []
    polygones = coords if forme == "MultiPolygon" else [coords]
    for polygone in polygones:
        if not polygone:
            continue
        if not dans_anneau(lon, lat, polygone[0]):
            continue
        if any(dans_anneau(lon, lat, trou) for trou in polygone[1:]):
            continue
        return True
    return False


def boite_de(geometrie):
    """Rectangle englobant d'un contour : filtre grossier avant le test fin."""
    lons, lats = [], []
    coords = geometrie.get("coordinates") or []
    forme = geometrie.get("type")
    polygones = coords if forme == "MultiPolygon" else [coords]
    for polygone in polygones:
        for anneau in polygone:
            for point in anneau:
                lons.append(point[0])
                lats.append(point[1])
    if not lons:
        return None
    return min(lons), min(lats), max(lons), max(lats)


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2)
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ══════════════════════════════════════════════════════════════════
# TÉLÉCHARGEMENT
# ══════════════════════════════════════════════════════════════════

def telecharger(destination):
    """Récupère l'archive GTFS. Vrai si le fichier est utilisable."""
    attente = 5
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                GTFS_URL, headers={"User-Agent": "portail-territorial/1.0"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                total = int(reponse.headers.get("Content-Length") or 0)
                recu = 0
                provisoire = destination.with_suffix(".partiel")
                with provisoire.open("wb") as sortie:
                    while True:
                        morceau = reponse.read(1 << 20)
                        if not morceau:
                            break
                        sortie.write(morceau)
                        recu += len(morceau)
                        if total:
                            print(f"\r    téléchargement… "
                                  f"{recu / 1048576:.0f}/{total / 1048576:.0f} Mo",
                                  end="", flush=True)
                print()
            # L'archive n'est mise en place qu'une fois complète : une
            # coupure en cours de route ne doit pas laisser un fichier
            # tronqué que la collecte suivante prendrait pour bon.
            provisoire.replace(destination)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError) as e:
            print(f"\n  [{type(e).__name__}] {e}")
            if tentative < TENTATIVES:
                time.sleep(attente)
                attente *= 2
                continue
            return False
    return False


def lire_table(archive, nom, colonnes=None):
    """Lit un fichier du GTFS en flux, sans le charger entièrement.

    stop_times.txt pèse à lui seul l'essentiel de l'archive : le lire
    ligne à ligne est ce qui permet de travailler sur un poste modeste.
    """
    membres = {Path(n).name: n for n in archive.namelist()}
    if nom not in membres:
        return
    with archive.open(membres[nom]) as brut:
        flux = io.TextIOWrapper(brut, encoding="utf-8-sig", newline="")
        for ligne in csv.DictReader(flux):
            if colonnes is None:
                yield ligne
            else:
                yield {c: ligne.get(c) for c in colonnes}


# ══════════════════════════════════════════════════════════════════
# CALENDRIER
# ══════════════════════════════════════════════════════════════════

JOURS = ("monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday")


def jour_gtfs(texte):
    try:
        return date(int(texte[:4]), int(texte[4:6]), int(texte[6:8]))
    except (TypeError, ValueError, IndexError):
        return None


def services_actifs(archive, jour):
    """Identifiants de service circulant à une date donnée.

    calendar.txt donne la règle hebdomadaire, calendar_dates.txt les
    exceptions — un jour férié retiré, un samedi ajouté. Les deux sont
    lus : ne lire que le premier ferait circuler des cars le 25
    décembre.
    """
    colonne = JOURS[jour.weekday()]
    actifs = set()
    for ligne in lire_table(archive, "calendar.txt"):
        debut = jour_gtfs(ligne.get("start_date"))
        fin = jour_gtfs(ligne.get("end_date"))
        if not debut or not fin or not (debut <= jour <= fin):
            continue
        if str(ligne.get(colonne) or "0").strip() == "1":
            actifs.add(ligne.get("service_id"))

    for ligne in lire_table(archive, "calendar_dates.txt"):
        if jour_gtfs(ligne.get("date")) != jour:
            continue
        exception = str(ligne.get("exception_type") or "").strip()
        if exception == "1":
            actifs.add(ligne.get("service_id"))
        elif exception == "2":
            actifs.discard(ligne.get("service_id"))
    return actifs


def bornes_du_service(archive):
    """Première et dernière date couverte par l'archive."""
    debuts, fins = [], []
    for ligne in lire_table(archive, "calendar.txt"):
        d, f = jour_gtfs(ligne.get("start_date")), jour_gtfs(ligne.get("end_date"))
        if d:
            debuts.append(d)
        if f:
            fins.append(f)
    for ligne in lire_table(archive, "calendar_dates.txt"):
        d = jour_gtfs(ligne.get("date"))
        if d:
            debuts.append(d)
            fins.append(d)
    if not debuts or not fins:
        return None, None
    return min(debuts), max(fins)


def choisir_jour(debut, fin, cible, depuis=None):
    """Prochain jour de semaine « cible » utilisable, ou None.

    cible suit la convention de weekday() : 1 pour mardi, 5 pour samedi.
    On part d'une semaine après aujourd'hui, et l'on se replie dans la
    période couverte si celle-ci est déjà commencée ou déjà finie.
    """
    depuis = (depuis or date.today()) + timedelta(days=JOURS_D_AVANCE)
    if debut and depuis < debut:
        depuis = debut
    for saut in range(0, 14):
        jour = depuis + timedelta(days=saut)
        if jour.weekday() == cible and (not fin or jour <= fin):
            return jour
    # La période est terminée : on regarde en arrière plutôt que de ne
    # rien publier. Une offre passée vaut mieux qu'aucune offre, tant
    # que la date est écrite.
    if fin:
        jour = fin
        for _ in range(14):
            if jour.weekday() == cible and (not debut or jour >= debut):
                return jour
            jour -= timedelta(days=1)
    return None


# ══════════════════════════════════════════════════════════════════
# LECTURE DU RÉSEAU
# ══════════════════════════════════════════════════════════════════

def rattacher_arrets(archive, contours, par_code):
    """Arrêts situés sur une commune du territoire, par code INSEE.

    Deux filtres successifs : le rectangle englobant du territoire,
    puis le contour exact de chaque commune. Le premier écarte en une
    comparaison les milliers d'arrêts du reste du département.
    """
    boites = {}
    for code, contour in contours.items():
        boite = boite_de(contour["contour"])
        if boite:
            boites[code] = boite
    if not boites:
        return {}, 0
    lon_min = min(b[0] for b in boites.values())
    lat_min = min(b[1] for b in boites.values())
    lon_max = max(b[2] for b in boites.values())
    lat_max = max(b[3] for b in boites.values())

    arrets, examines = {}, 0
    for ligne in lire_table(archive, "stops.txt"):
        examines += 1
        try:
            lat = float(ligne.get("stop_lat"))
            lon = float(ligne.get("stop_lon"))
        except (TypeError, ValueError):
            continue
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            continue
        # location_type 1 désigne une STATION, qui regroupe des quais :
        # la compter reviendrait à compter deux fois le même lieu.
        if str(ligne.get("location_type") or "0").strip() == "1":
            continue
        for code, (bl, bb, br, bh) in boites.items():
            if not (bl <= lon <= br and bb <= lat <= bh):
                continue
            if dans_contour(lon, lat, contours[code]["contour"]):
                arrets[ligne["stop_id"]] = {
                    "nom": (ligne.get("stop_name") or "").strip(),
                    "code_commune": code,
                    "latitude": lat, "longitude": lon,
                }
                break
    return arrets, examines


def desserte(archive, arrets, services, scolaires_exclues):
    """Passages et lignes par commune, un jour donné.

    Un « passage » est un arrêt marqué par une course. C'est la mesure
    que cherche un habitant : combien de fois un car s'arrête ici dans
    la journée, tous sens confondus.
    """
    lignes_par_id = {}
    for r in lire_table(archive, "routes.txt"):
        lignes_par_id[r.get("route_id")] = {
            "court": (r.get("route_short_name") or "").strip(),
            "long": (r.get("route_long_name") or "").strip(),
        }

    courses = {}
    for t in lire_table(archive, "trips.txt"):
        if t.get("service_id") not in services:
            continue
        route = t.get("route_id")
        if route in scolaires_exclues:
            continue
        courses[t.get("trip_id")] = route

    passages, lignes_vues = {}, {}
    for st in lire_table(archive, "stop_times.txt",
                         ("trip_id", "stop_id")):
        arret = arrets.get(st.get("stop_id"))
        if not arret:
            continue
        route = courses.get(st.get("trip_id"))
        if route is None:
            continue
        code = arret["code_commune"]
        passages[code] = passages.get(code, 0) + 1
        passages[("arret", st["stop_id"])] = \
            passages.get(("arret", st["stop_id"]), 0) + 1
        lignes_vues.setdefault(code, set()).add(route)
    return passages, lignes_vues, lignes_par_id


def inventaire_des_lignes(archive, services):
    """Nombre de courses par ligne, pour régler MOTIFS_SCOLAIRES.

    C'est l'outil qui remplace une supposition par une observation :
    tant que personne n'a regardé comment ce réseau nomme ses services
    scolaires, aucun filtre ne doit être écrit.
    """
    noms = {}
    for r in lire_table(archive, "routes.txt"):
        noms[r.get("route_id")] = (
            (r.get("route_short_name") or "").strip(),
            (r.get("route_long_name") or "").strip())
    compte = {}
    for t in lire_table(archive, "trips.txt"):
        if services and t.get("service_id") not in services:
            continue
        compte[t.get("route_id")] = compte.get(t.get("route_id"), 0) + 1
    return [(noms.get(rid, ("", ""))[0], noms.get(rid, ("", ""))[1], n)
            for rid, n in compte.items()]


def est_scolaire(court, long_):
    texte = f"{court} {long_}".lower()
    return any(motif in texte for motif in MOTIFS_SCOLAIRES)


# ══════════════════════════════════════════════════════════════════
# MISE EN FORME
# ══════════════════════════════════════════════════════════════════

def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "recalculé", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def note_desserte(mardi, samedi, filtre_actif):
    note = (f"Passages comptés sur l'offre théorique publiée par le "
            f"réseau : le mardi {mardi.strftime('%d/%m/%Y')} et le samedi "
            f"{samedi.strftime('%d/%m/%Y')}. Un passage est un arrêt "
            f"marqué par un car, tous sens confondus.")
    if not filtre_actif:
        note += (" Les services scolaires ne sont pas distingués des "
                 "lignes ouvertes à tous : le chiffre du mardi les "
                 "comprend.")
    else:
        note += " Les services scolaires sont exclus du décompte."
    return note


def ecrire_vide(motif):
    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION, "source": SOURCE, "licence": LICENCE,
        "frequence": "mensuelle", "motif_absence": motif,
        "communes": {}, "territoires": {},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Rien publié — {motif}")
    print(f"  Fichier écrit vide : {SORTIE}\n")


def main():
    print("\nDesserte en autocar — GTFS")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")
    print(f"  licence de la source : {LICENCE}")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    # Les contours viennent de 05_cartes.py, qui s'exécute APRÈS les
    # collecteurs dans la séquence. Sur une machine neuve, ce fichier
    # n'existe donc pas encore au premier passage. Ce n'est pas une
    # panne : on le dit, on écrit un fichier vide, et la collecte
    # suivante trouvera les contours en place. Bloquer ici arrêterait
    # toute la chaîne pour une dépendance qui se résout d'elle-même.
    if not CONTOURS.exists():
        print(f"\n  {CONTOURS} n'existe pas encore.")
        print("  Il est produit par 05_cartes.py, qui passe après les")
        print("  collecteurs. Relancez après une séquence complète.")
        ecrire_vide("les contours communaux ne sont pas encore disponibles")
        return

    reference = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = reference["communes"]
    par_code = {c["code"]: c for c in communes}
    cantons = {c.get("code_canton") for c in communes if c.get("code_canton")}
    codes_epci = {c.get("code_epci") for c in communes if c.get("code_epci")}
    contours = json.loads(CONTOURS.read_text(encoding="utf-8"))

    archive_chemin = CACHE
    if "--archive" in sys.argv:
        i = sys.argv.index("--archive")
        if i + 1 >= len(sys.argv):
            print("\n[ERREUR] --archive attend un nom de fichier.\n")
            sys.exit(1)
        archive_chemin = Path(sys.argv[i + 1])
    elif not CACHE.exists() or "--tout" in sys.argv:
        DONNEES.mkdir(exist_ok=True)
        print(f"  Téléchargement de l'offre théorique…")
        if not telecharger(CACHE):
            ecrire_vide("l'archive GTFS n'a pas pu être téléchargée")
            return
    else:
        print(f"  Archive déjà présente : {CACHE} "
              f"({CACHE.stat().st_size / 1048576:.0f} Mo)")

    if not archive_chemin.exists():
        ecrire_vide(f"{archive_chemin} introuvable")
        return

    try:
        archive = zipfile.ZipFile(archive_chemin)
    except zipfile.BadZipFile:
        ecrire_vide("l'archive GTFS est illisible")
        return

    with archive:
        debut, fin = bornes_du_service(archive)
        if not debut:
            ecrire_vide("l'archive ne porte aucun calendrier de service")
            return
        print(f"  Service couvert : {debut.strftime('%d/%m/%Y')} → "
              f"{fin.strftime('%d/%m/%Y')}")

        mardi = choisir_jour(debut, fin, 1)
        samedi = choisir_jour(debut, fin, 5)
        if not mardi or not samedi:
            ecrire_vide("aucun jour de référence dans la période couverte")
            return
        print(f"  Jours de référence : mardi {mardi.strftime('%d/%m/%Y')} "
              f"· samedi {samedi.strftime('%d/%m/%Y')}")

        services_mardi = services_actifs(archive, mardi)
        services_samedi = services_actifs(archive, samedi)
        print(f"  Services actifs : {len(services_mardi)} le mardi, "
              f"{len(services_samedi)} le samedi")

        # ── inventaire : on décrit, on ne publie pas ─────────────────
        inventaire = inventaire_des_lignes(archive, services_mardi)
        inventaire.sort(key=lambda x: -x[2])
        scolaires = {court for court, long_, _n in inventaire
                     if est_scolaire(court, long_)}
        if "--inventaire" in sys.argv:
            print(f"\n  {len(inventaire)} ligne(s) circulent ce mardi.")
            print("  Les vingt plus fournies :\n")
            for court, long_, n in inventaire[:20]:
                marque = "  [scolaire]" if est_scolaire(court, long_) else ""
                print(f"    {n:5} course(s)  {court:12} {long_[:48]}{marque}")
            print("\n  Réglez MOTIFS_SCOLAIRES à partir de cette liste, "
                  "puis relancez sans --inventaire.\n")
            return

        if not MOTIFS_SCOLAIRES:
            print("\n  [ATTENTION] MOTIFS_SCOLAIRES est vide : les services")
            print("  scolaires ne sont pas distingués des lignes ouvertes à")
            print("  tous. Le chiffre publié les comprend, et la note de la")
            print("  page le dit. Lancez « python 20_cars.py --inventaire »")
            print("  pour voir comment ce réseau nomme ses lignes.")

        arrets, examines = rattacher_arrets(archive, contours, par_code)
        print(f"\n  Arrêts examinés : {examines}")
        print(f"  Arrêts sur le territoire : {len(arrets)}")
        if not arrets:
            ecrire_vide("aucun arrêt sur le territoire")
            return

        exclues = set()
        if MOTIFS_SCOLAIRES:
            for r in lire_table(archive, "routes.txt"):
                if est_scolaire((r.get("route_short_name") or ""),
                                (r.get("route_long_name") or "")):
                    exclues.add(r.get("route_id"))
            print(f"  Lignes scolaires écartées : {len(exclues)}")

        passages_mardi, lignes_mardi, noms_lignes = desserte(
            archive, arrets, services_mardi, exclues)
        passages_samedi, _lg, _nl = desserte(
            archive, arrets, services_samedi, exclues)

    # ── communes ─────────────────────────────────────────────────────
    resultat = {}
    for code, commune in par_code.items():
        siens = [a for a in arrets.values() if a["code_commune"] == code]
        mardi_n = passages_mardi.get(code, 0)
        samedi_n = passages_samedi.get(code, 0)
        if not siens:
            continue

        mesures = {}
        if mardi_n >= PASSAGES_MINIMUM:
            mesures["TRA-20"] = mesure(
                str(mardi_n), "passages", "Cars un mardi", rang=10,
                ancre=ANCRE,
                repere=(f"{samedi_n} le samedi" if samedi_n
                        else "aucun le samedi"),
                explication=("Nombre d'arrêts marqués par un car sur la "
                             "commune, tous sens confondus, sur l'offre "
                             f"théorique du {mardi.strftime('%d/%m/%Y')}."))
        else:
            # Une commune pourvue d'arrêts mais sans passage ce jour-là
            # est une information, et pas une absence de donnée.
            mesures["TRA-20"] = mesure(
                "Aucun car ce jour-là", "", "Desserte en autocar", rang=10,
                ancre=ANCRE, ton="attention",
                explication=("La commune compte des points d'arrêt, mais "
                             "aucune course n'y est prévue le jour de "
                             "référence."))
        mesures["TRA-21"] = mesure(
            str(len(siens)), "", "Points d'arrêt", rang=20, ancre=ANCRE)
        lignes = sorted(
            {noms_lignes.get(r, {}).get("court") or
             noms_lignes.get(r, {}).get("long") or r
             for r in lignes_mardi.get(code, set())})
        if lignes:
            mesures["TRA-22"] = mesure(
                ", ".join(lignes[:6]) + ("…" if len(lignes) > 6 else ""),
                "", "Lignes desservantes", rang=30, ancre=ANCRE)

        # Les arrêts sont listés du mieux desservi au moins desservi :
        # un habitant cherche d'abord celui où il y a des cars, pas le
        # premier dans l'ordre alphabétique.
        items = []
        for identifiant, a in sorted(
                ((i, a) for i, a in arrets.items()
                 if a["code_commune"] == code),
                key=lambda ia: (-passages_mardi.get(("arret", ia[0]), 0),
                                ia[1]["nom"])):
            n_mardi = passages_mardi.get(("arret", identifiant), 0)
            n_samedi = passages_samedi.get(("arret", identifiant), 0)
            details = {"Passages le mardi": str(n_mardi)}
            if n_samedi:
                details["Passages le samedi"] = str(n_samedi)
            items.append({
                "titre": a["nom"] or "Arrêt sans nom",
                "details": details,
                "etat": (["Desservi", "neutre"] if n_mardi
                         else ["Aucun car ce jour-là", "attention"]),
                "texte": ""})

        resultat[code] = {
            "mesures": mesures,
            "blocs": [{
                "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                "id": ANCRE, "titre": "Arrêts d'autocar",
                "items": items[:40],
                "lien": {"url": "https://transport.data.gouv.fr/datasets/"
                                "reseau-interurbain-isere-38",
                         "libelle": "Consulter la source"},
                "note": note_desserte(mardi, samedi, bool(MOTIFS_SCOLAIRES)),
            }],
        }

    # ── canton et intercommunalité ───────────────────────────────────
    territoires = {}
    for niveau, codes in (("canton", cantons), ("epci", codes_epci)):
        for identifiant in codes:
            if niveau == "canton":
                membres = [c for c in communes
                           if c.get("code_canton") == identifiant]
            else:
                membres = [c for c in communes
                           if c.get("code_epci") == identifiant]
            leurs = [c["code"] for c in membres if c["code"] in resultat]
            if not leurs:
                continue
            total_arrets = sum(1 for a in arrets.values()
                               if a["code_commune"] in leurs)
            total_passages = sum(passages_mardi.get(c, 0) for c in leurs)
            servies = sum(1 for c in leurs if passages_mardi.get(c, 0))
            toutes_lignes = set()
            for c in leurs:
                toutes_lignes |= lignes_mardi.get(c, set())
            territoires[f"{niveau}:{identifiant}"] = {
                "mesures": {
                    # « Pourvue d'un arrêt » et « desservie » ne sont pas
                    # la même chose : une commune peut avoir un poteau où
                    # aucun car ne s'arrête le jour de référence. Les deux
                    # chiffres sont donnés, et nommés pour ce qu'ils sont.
                    "TRA-23": mesure(
                        f"{servies} sur {len(membres)}", "",
                        "Communes desservies un mardi", rang=10, ancre=ANCRE,
                        repere=(f"{len(leurs)} pourvues d'un arrêt · "
                                f"{total_arrets} points d'arrêt"),
                        explication=("Communes où au moins un car marque "
                                     "l'arrêt le jour de référence. Une "
                                     "commune peut compter un point d'arrêt "
                                     "sans être desservie ce jour-là.")),
                    "TRA-24": mesure(
                        str(total_passages), "passages",
                        "Cars un mardi sur le territoire", rang=20,
                        ancre=ANCRE,
                        repere=f"{len(toutes_lignes)} ligne(s)"),
                },
                "blocs": [],
            }

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "mensuelle",
        "jour_de_reference": mardi.isoformat(),
        "jour_de_reference_samedi": samedi.isoformat(),
        "scolaire_distingue": bool(MOTIFS_SCOLAIRES),
        "communes": resultat,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    desservies = len(resultat)
    print(f"\n  Communes desservies : {desservies} sur {len(par_code)}")
    for code in sorted(resultat,
                       key=lambda c: -passages_mardi.get(c, 0))[:8]:
        print(f"    {par_code[code]['nom']:28} "
              f"{passages_mardi.get(code, 0):4} passages le mardi, "
              f"{passages_samedi.get(code, 0):3} le samedi")
    sans = [par_code[c]["nom"] for c in par_code if c not in resultat]
    if sans:
        print(f"  Sans aucun arrêt ({len(sans)}) : "
              f"{', '.join(sans[:6])}"
              + ("…" if len(sans) > 6 else ""))
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
