"""
18_carburants.py — Prix des carburants à la pompe
==================================================

Publie, commune par commune puis à l'échelle du territoire, le prix des
carburants relevé dans les stations-service, et la fraîcheur de chaque
relevé.

CE QUE CETTE RUBRIQUE APPORTE, ET QUI N'EXISTE PAS AILLEURS
-----------------------------------------------------------
Les comparateurs nationaux répondent à la question « où est le moins
cher autour de moi ». Ils ne répondent pas à « qu'est-ce que cela coûte
d'habiter ici », qui est la question d'un territoire. L'écart relevé le
8 septembre 2026 entre Vinay et Saint-Marcellin — dix centimes au
litre, cinq euros sur un plein — n'est publié nulle part, et il ne se
voit qu'en regardant les stations d'un même bassin de vie côte à côte.

DEUX JEUX DE DONNÉES, DEUX RÔLES
---------------------------------
Le portail data.economie.gouv.fr en publie deux sur le sujet. Ils ne
disent pas la même chose, et ce script se sert des deux :

  · « flux instantané » — une ligne par station, un champ par
    carburant, le relevé le plus récent. Il n'a PAS de code INSEE ;
  · « prix carburants quotidien » — une ligne par station ET par
    carburant, environ un jour de retard, des lignes en double, mais
    il porte « com_arm_code », le code INSEE de la commune, écrit par
    le producteur lui-même.

Le rattachement d'une station à une commune était la seule vraie
inconnue de ce collecteur. Elle est levée : le producteur publie
lui-même le code INSEE, et un « group_by » sur l'identifiant efface les
doublons dans la requête. Aucun calcul géométrique n'est nécessaire, et
nous ne nous substituons pas au producteur pour dire où se trouve une
station.

Les prix, eux, viennent du flux instantané : la fraîcheur est tout le
sujet, et publier sur un site statique des prix qui ont déjà un jour
serait ajouter un retard à un retard.

CE QUI EST REFUSÉ, ET POURQUOI
-------------------------------
Quatre filets, chacun capable d'empêcher la publication :

  · un prix hors des bornes du plausible est écarté — c'est la leçon
    de la Bourne, où des valeurs dix fois trop faibles racontaient une
    histoire fausse avec des données vraies ;
  · un relevé plus vieux que PERIME_JOURS n'est pas publié : un prix
    périmé affiché sans réserve est pire qu'une absence de prix ;
  · une station dont les coordonnées sont très loin du centre de la
    commune que le producteur lui attribue est écartée : les deux
    sources se contredisent, et nous n'avons pas à choisir ;
  · si plus rien ne reste après ces trois filets, le fichier de sortie
    est écrit VIDE. Ne rien écrire laisserait en place la collecte
    précédente, et le site continuerait d'afficher des prix d'un autre
    mois.

Produit :
    data/mesures-carburants.json   repris par 03_agregation.py

Utilisation :
    python 18_carburants.py
    python 18_carburants.py --exemple     enregistre la collecte brute
    python 18_carburants.py --rejouer F   rejoue une collecte enregistrée
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

VERSION_SCRIPT = 4

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-carburants.json"
EXEMPLE = DONNEES / "cache-carburants-exemple.json"

API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
FLUX = "prix-des-carburants-en-france-flux-instantane-v2"
QUOTIDIEN = "prix-carburants-quotidien"

SOURCE = ("Prix des carburants — flux instantané, "
          "ministère de l'Économie (data.economie.gouv.fr)")
LICENCE = "Licence Ouverte 2.0"

# ── Les enseignes ────────────────────────────────────────────────────
# AUCUN des deux jeux officiels ne porte le nom commercial de la
# station. Ce n'est pas un oubli : l'arrêté du 12 décembre 2006 oblige
# les stations à déclarer leurs PRIX, pas leur enseigne.
#
# Or « Leclerc » ou « Avia » est ce qu'un habitant reconnaît, bien plus
# que « 2 avenue de Romans ». Deux sources complémentaires y pourvoient,
# dans cet ordre de priorité :
#
#   1. le fichier de saisie ci-dessous, tenu à la main. Il fait toujours
#      foi : c'est une vérification humaine ;
#   2. OpenStreetMap, interrogé par Overpass, où seize des dix-huit
#      stations du secteur portent une étiquette « brand ».
#
# Relevé le 9 septembre 2026, en rapprochant les stations officielles
# des nœuds OSM les plus proches :
#
#     Chatte                45 m → E.Leclerc
#     Vinay (Grenoble)      65 m → Total
#     Vinay (Europe)        77 m → Super U
#     Saint-Just-de-Claix   11 m → Comptoir Énergie
#     Saint-Sauveur      1 278 m → AUCUN APPARIEMENT FIABLE
#     Saint-Marcellin      734 m → AUCUN APPARIEMENT FIABLE
#
# D'où le seuil : au-delà de ENSEIGNE_DISTANCE_MAXIMUM_M, on ne nomme
# rien. Un nœud à sept cents mètres est une AUTRE station, et lui
# emprunter son enseigne afficherait « Avia » sur une station qui n'en
# est pas une. Mieux vaut pas d'enseigne qu'une fausse enseigne.
#
# OpenStreetMap est sous ODbL : le fichier produit déclare donc DEUX
# licences, et le générateur, depuis la version 37, sait les afficher
# toutes les deux.
OSM_API = "https://overpass-api.de/api/interpreter"
LICENCE_OSM = "ODbL 1.0"
SOURCE_OSM = "OpenStreetMap — enseignes des stations (contributeurs OSM)"
ENSEIGNE_DISTANCE_MAXIMUM_M = 150
REFERENCE_ENSEIGNES = DONNEES / "reference-enseignes-carburants.json"

VERSION = 1
RUBRIQUE = "carburants"
ANCRE = "stations-service"

DELAI = 30
TENTATIVES = 4

# ── Réglages arbitrables ────────────────────────────────────────────
# Ces quatre nombres décident de ce que la rubrique montre. Ils sont
# groupés ici pour être discutés, pas cherchés.

# Marge autour du territoire pour la COLLECTE, en kilomètres. Ce n'est
# pas une règle d'affichage : c'est l'enveloppe dans laquelle on va
# chercher, et elle doit être large pour qu'une commune de bordure
# trouve ses voisines. Ce qui s'affiche est décidé page par page, plus
# bas.
MARGE_KM = 15

# Rayon dans lequel une page de COMMUNE va chercher des stations hors
# du territoire, et nombre maximal qu'elle en retient.
#
# La première collecte réelle a montré pourquoi cette distinction est
# nécessaire. Une simple marge de dix kilomètres autour du territoire
# ramenait quarante-neuf stations, dont quarante-trois hors territoire :
# Voiron, Moirans, Échirolles, Romans-sur-Isère. Le territoire est une
# bande étroite entre le Voironnais et la plaine de Romans, et un
# rectangle autour de lui attrape deux agglomérations qui ne sont
# proches d'aucune de ses communes. La page du canton se serait mise à
# parler de Grenoble.
#
# La règle retenue : une page de canton ne montre QUE les stations du
# territoire — c'est la comparaison entre elles qui fait le sujet. Une
# page de commune montre les siennes, puis les plus proches d'où
# qu'elles viennent — c'est la question qu'on se pose depuis un village.
VOISINES_KM = 15
VOISINES_MAXI = 3

# Un relevé plus vieux que cela n'est pas publié du tout.
PERIME_JOURS = 8

# Entre ce seuil et le précédent, le prix est publié mais sa date est
# écrite en toutes lettres. Seuil repris du cahier des charges Carbu.
SIGNALE_JOURS = 3

# Écart toléré entre les coordonnées d'une station et le centre de la
# commune que le producteur lui attribue. Un nombre fixe ne convient
# pas : six kilomètres seraient trop peu pour une commune étendue et
# beaucoup trop pour un village. Le seuil se déduit donc de la surface
# de la commune concernée — trois fois le rayon du disque de même
# aire — avec un plancher pour les plus petites.
#
# Sur ce territoire, la commune la plus vaste (Saint-Antoine-l'Abbaye,
# 3 603 ha) a un rayon équivalent de 3,4 km : son seuil vaut 10 km,
# quand une station réellement située sur son sol s'écarte rarement de
# plus de deux rayons de son centre. Le filet est donc large, et il
# attrape quand même un rattachement franchement faux.
ECART_FACTEUR = 3.0
ECART_PLANCHER_KM = 6.0

# Bornes du plausible, en euros par litre. L'E85 tourne autour de
# 0,84 € et le gazole autour de 2,30 € : ces bornes n'écartent aucun
# prix réel, mais attrapent un changement d'unité ou une virgule
# déplacée.
PRIX_MINIMUM = 0.30
PRIX_MAXIMUM = 5.00

# ── Carburants publiés, dans l'ordre d'affichage ────────────────────
# Le gazole en tête : c'est le carburant majoritaire, et celui sur
# lequel un habitant compare. L'ordre suivant est celui de la
# fréquentation, non celui de l'alphabet.
CARBURANTS = [
    ("gazole", "Gazole"),
    ("e10", "SP95-E10"),
    ("sp95", "SP95"),
    ("sp98", "SP98"),
    ("e85", "E85"),
    ("gplc", "GPLc"),
]


# ══════════════════════════════════════════════════════════════════
# APPEL DE L'API
# ══════════════════════════════════════════════════════════════════

def appeler(jeu, silencieux=False, **params):
    """Une requête sur l'API Explore, avec reprise sur erreur passagère.

    Renvoie la liste des enregistrements, [] si le jeu ne répond rien,
    et None si la requête a échoué — un appelant qui reçoit None doit
    renoncer, pas publier une liste vide.
    """
    url = f"{API}/{jeu}/records?" + urllib.parse.urlencode(params)
    attente = 3
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0",
                              "Accept": "application/json"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                corps = reponse.read()
            if not corps.strip():
                return []
            return json.loads(corps.decode("utf-8")).get("results", [])
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            detail = ""
            try:
                donnees = json.loads(e.read().decode("utf-8", "replace"))
                detail = str(donnees.get("message") or donnees)[:200]
            except Exception:
                pass
            if not silencieux:
                print(f"\n  [ERREUR] L'API a répondu {e.code}")
                if detail:
                    print(f"  {detail}")
                print(f"  {url}")
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if tentative < TENTATIVES:
                time.sleep(attente)
                attente *= 2
                continue
            if not silencieux:
                print(f"\n  [ERREUR] {type(e).__name__} : {e}")
            return None
    return None


# ══════════════════════════════════════════════════════════════════
# GÉOGRAPHIE
# ══════════════════════════════════════════════════════════════════

def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau. Formule de haversine, rayon moyen."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def ecart_tolere(commune):
    """Seuil de contradiction pour une commune, en kilomètres."""
    surface = float(commune.get("surface_ha") or 0)
    rayon = math.sqrt(surface * 10000 / math.pi) / 1000 if surface > 0 else 0
    return max(ECART_PLANCHER_KM, ECART_FACTEUR * rayon)


def emprise(communes, marge_km):
    """Rectangle englobant le territoire, élargi de marge_km.

    Un rayon unique autour d'un centre conviendrait mal : le territoire
    s'étend sur une quarantaine de kilomètres d'est en ouest, et le
    cercle qui le couvrirait entièrement déborderait très au sud.
    """
    lats = [c["latitude"] for c in communes]
    lons = [c["longitude"] for c in communes]
    # Un degré de latitude vaut 111 km ; un degré de longitude vaut
    # moins, d'autant plus qu'on monte vers le nord.
    dlat = marge_km / 111.0
    milieu = math.radians((min(lats) + max(lats)) / 2)
    dlon = marge_km / (111.0 * max(0.1, math.cos(milieu)))
    return (min(lons) - dlon, min(lats) - dlat,
            max(lons) + dlon, max(lats) + dlat)


# ══════════════════════════════════════════════════════════════════
# COLLECTE
# ══════════════════════════════════════════════════════════════════

def stations_candidates(boite):
    """Identifiants et commune de rattachement, dans l'emprise.

    C'est le jeu quotidien qui répond, pour son seul champ utile : le
    code INSEE. Le « group_by » est ce qui rend ce jeu exploitable —
    sans lui, une station apparaît autant de fois qu'elle vend de
    carburants, et le décompte des stations serait faux.
    """
    lonmin, latmin, lonmax, latmax = boite
    # ATTENTION à l'ordre : l'API Explore attend in_bbox(champ, lat_min,
    # lon_min, lat_max, lon_max) — la LATITUDE d'abord. Donné dans
    # l'autre sens, le filtre est syntaxiquement valable, la requête
    # répond 200, et elle renvoie zéro ligne. C'est l'erreur qui a fait
    # publier « aucune station dans l'emprise » à la première collecte
    # réelle du 9 septembre 2026, sur un territoire qui en compte six.
    filtre = (f"in_bbox(geom, {latmin:.5f}, {lonmin:.5f}, "
              f"{latmax:.5f}, {lonmax:.5f})")

    # L'API plafonne une réponse à cent lignes : au-delà, il faut
    # pagineriser. Avec une marge de quinze kilomètres autour d'un
    # territoire bordé par le Voironnais et la plaine de Romans, ce
    # plafond est atteint.
    candidates = {}
    for depart in range(0, 1000, 100):
        lignes = appeler(QUOTIDIEN, where=filtre, limit=100, offset=depart,
                         select="id,com_arm_code,com_arm_name",
                         group_by="id,com_arm_code,com_arm_name")
        if lignes is None:
            return None
        for l in lignes:
            ident = str(l.get("id") or "").strip()
            code = str(l.get("com_arm_code") or "").strip()
            if ident and code:
                candidates[ident] = (code,
                                     str(l.get("com_arm_name") or "").strip())
        if len(lignes) < 100:
            break
    return candidates


def prix_des_stations(identifiants):
    """Le relevé le plus récent de chaque station nommée.

    Les identifiants sont donnés au flux instantané tels quels : c'est
    le même identifiant dans les deux jeux, à ceci près qu'il y est
    numérique et ici textuel. La liste est découpée si elle est longue,
    pour ne pas construire une adresse démesurée.
    """
    champs = ["id", "ville", "cp", "adresse", "pop", "geom",
              "carburants_indisponibles", "carburants_rupture_definitive",
              "horaires_automate_24_24"]
    for cle, _ in CARBURANTS:
        champs += [f"{cle}_prix", f"{cle}_maj"]

    resultats = []
    liste = sorted(identifiants)
    for debut in range(0, len(liste), 40):
        tranche = liste[debut:debut + 40]
        valeurs = ", ".join(str(int(i)) for i in tranche if str(i).isdigit())
        if not valeurs:
            continue
        lignes = appeler(FLUX, where=f"id in ({valeurs})", limit=100,
                         select=",".join(champs))
        if lignes is None:
            return None
        resultats.extend(lignes)
    return resultats


# ══════════════════════════════════════════════════════════════════
# ENSEIGNES
# ══════════════════════════════════════════════════════════════════

MODELE_ENSEIGNES = {
    "_lisez_moi": (
        "Enseignes saisies à la main, par identifiant de station tel "
        "qu'il figure dans le flux officiel. Ce fichier fait toujours "
        "foi sur OpenStreetMap : une vérification humaine l'emporte sur "
        "une étiquette contributive. Laissez une entrée vide pour "
        "effacer une enseigne qu'OSM propose à tort."),
    "saisi_le": "",
    "enseignes": {
        "38160007": "",
        "38160003": "",
    },
}


def enseignes_saisies():
    """Enseignes vérifiées à la main, par identifiant de station."""
    if not REFERENCE_ENSEIGNES.exists():
        return {}, None
    try:
        contenu = json.loads(REFERENCE_ENSEIGNES.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"  [attention] {REFERENCE_ENSEIGNES} est illisible, ignoré.")
        return {}, None
    saisies = {str(k): str(v).strip()
               for k, v in (contenu.get("enseignes") or {}).items()}
    return saisies, contenu.get("saisi_le")


def enseignes_osm(boite):
    """Enseignes trouvées dans OpenStreetMap, avec leur position.

    Renvoie une liste de (latitude, longitude, enseigne), ou None si
    Overpass n'a pas répondu. Une absence de réponse n'est PAS une
    erreur : les prix sont publiés sans enseigne, et la sortie le dit.
    Overpass est un service bénévole, souvent saturé ; en faire une
    dépendance dure serait déraisonnable.
    """
    lonmin, latmin, lonmax, latmax = boite
    requete = (f'[out:json][timeout:60];'
               f'(node["amenity"="fuel"]({latmin:.4f},{lonmin:.4f},'
               f'{latmax:.4f},{lonmax:.4f});'
               f'way["amenity"="fuel"]({latmin:.4f},{lonmin:.4f},'
               f'{latmax:.4f},{lonmax:.4f}););out center tags;')
    url = OSM_API + "?" + urllib.parse.urlencode({"data": requete})
    try:
        demande = urllib.request.Request(
            url, headers={"User-Agent": "portail-territorial/1.0",
                          "Accept": "application/json"})
        with urllib.request.urlopen(demande, timeout=90) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
    except Exception as e:
        print(f"  [attention] OpenStreetMap n'a pas répondu "
              f"({type(e).__name__}) : les enseignes automatiques sont "
              f"sautées.")
        return None

    trouvees = []
    for e in donnees.get("elements", []):
        centre = e.get("center") or {}
        lat = e.get("lat", centre.get("lat"))
        lon = e.get("lon", centre.get("lon"))
        etiquettes = e.get("tags") or {}
        nom = (etiquettes.get("brand") or etiquettes.get("operator")
               or etiquettes.get("name") or "").strip()
        if lat is None or lon is None or not nom:
            continue
        trouvees.append((float(lat), float(lon), nom))
    return trouvees


def apparier_enseigne(station, noeuds):
    """(enseigne, distance en mètres) du nœud OSM le plus proche, ou None.

    Le seuil est ce qui fait la sûreté de ce rapprochement. Sur la
    collecte du 9 septembre, quatre stations sur six tombaient à moins
    de quatre-vingts mètres d'un nœud, et les deux autres à plus de sept
    cents — c'est-à-dire sur une station différente. Sans seuil, elles
    auraient hérité d'une enseigne qui n'est pas la leur.
    """
    if not noeuds or station.get("latitude") is None:
        return None
    meilleur, distance = None, None
    for lat, lon, nom in noeuds:
        d = distance_km(station["latitude"], station["longitude"], lat, lon) * 1000
        if distance is None or d < distance:
            meilleur, distance = nom, d
    if distance is None or distance > ENSEIGNE_DISTANCE_MAXIMUM_M:
        return None
    return meilleur, distance


# ══════════════════════════════════════════════════════════════════
# FILTRES
# ══════════════════════════════════════════════════════════════════

def age_en_jours(horodatage, maintenant=None):
    """Âge d'un relevé, en jours. None si la date est illisible."""
    if not horodatage:
        return None
    texte = str(horodatage).strip().replace("Z", "+00:00")
    try:
        quand = datetime.fromisoformat(texte)
    except ValueError:
        return None
    if quand.tzinfo is None:
        quand = quand.replace(tzinfo=timezone.utc)
    maintenant = maintenant or datetime.now(timezone.utc)
    return (maintenant - quand).total_seconds() / 86400.0


def prix_publiable(valeur, horodatage, maintenant=None):
    """(prix, âge en jours) si le relevé est publiable, sinon None.

    Un prix hors bornes est écarté sans discussion : mieux vaut une
    case vide qu'un chiffre qui ferait douter de toute la page.
    """
    try:
        prix = float(valeur)
    except (TypeError, ValueError):
        return None
    if not (PRIX_MINIMUM <= prix <= PRIX_MAXIMUM):
        return None
    age = age_en_jours(horodatage, maintenant)
    if age is None or age > PERIME_JOURS or age < -1:
        return None
    return prix, max(0.0, age)


def liste_de(champ):
    """Les deux formes servies par le flux, ramenées à une liste.

    « carburants_indisponibles » arrive en tableau, mais
    « carburants_rupture_definitive » arrive en chaîne séparée par des
    points-virgules. Une seule lecture pour les deux.
    """
    if isinstance(champ, list):
        return [str(x).strip() for x in champ if str(x).strip()]
    return [m.strip() for m in str(champ or "").split(";") if m.strip()]


# ══════════════════════════════════════════════════════════════════
# MISE EN FORME
# ══════════════════════════════════════════════════════════════════

def euros(prix):
    """2.219 → « 2,219 ». Trois décimales : c'est l'affichage à la pompe."""
    return f"{prix:.3f}".replace(".", ",")


def date_fr(horodatage):
    texte = str(horodatage or "").strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(texte).strftime("%d/%m/%Y")
    except ValueError:
        return "date inconnue"


def dire_age(age):
    if age < 1:
        return "aujourd'hui"
    if age < 2:
        return "hier"
    return f"il y a {int(age)} jours"


def station_lisible(station, anomalies=None):
    """Une station réduite à ce que la page en montre.

    « anomalies » recueille les prix hors bornes. Un relevé trop vieux
    est une situation ordinaire et n'y figure pas ; un prix hors bornes
    ne l'est pas — c'est le signe que la source a changé quelque chose,
    et cela doit être dit à l'exécution plutôt que passé sous silence.
    """
    lu = {
        "id": str(station.get("id") or ""),
        "ville": str(station.get("ville") or "").strip(),
        "adresse": str(station.get("adresse") or "").strip(),
        "autoroute": str(station.get("pop") or "").upper() == "A",
        "jour_et_nuit": str(
            station.get("horaires_automate_24_24") or "").lower() == "oui",
        "prix": {},
        "ages": {},
        "dates": {},
        "absents": [],
        "enseigne": "",
        "enseigne_origine": "",
    }
    geom = station.get("geom") or {}
    lu["latitude"] = geom.get("lat")
    lu["longitude"] = geom.get("lon")

    for cle, libelle in CARBURANTS:
        brut = station.get(f"{cle}_prix")
        if brut is not None and anomalies is not None:
            try:
                valeur = float(brut)
            except (TypeError, ValueError):
                anomalies.append((lu["ville"], libelle, f"illisible ({brut!r})"))
            else:
                if not (PRIX_MINIMUM <= valeur <= PRIX_MAXIMUM):
                    anomalies.append((lu["ville"], libelle,
                                      f"{valeur} hors des bornes "
                                      f"{PRIX_MINIMUM}–{PRIX_MAXIMUM} €/L"))
        retenu = prix_publiable(brut, station.get(f"{cle}_maj"))
        if retenu:
            lu["prix"][cle], lu["ages"][cle] = retenu
            lu["dates"][cle] = station.get(f"{cle}_maj")

    definitives = set(liste_de(station.get("carburants_rupture_definitive")))
    for nom in liste_de(station.get("carburants_indisponibles")):
        # « Définitivement » n'est pas une nuance : une station qui ne
        # vendra plus de GPL ne se retrouve pas en repassant demain.
        lu["absents"].append(
            (nom, "définitivement" if nom in definitives else "pour l'instant"))
    return lu


def item_station(st, chez_nous):
    """Un item de bloc décrivant une station."""
    details = {}
    for cle, libelle in CARBURANTS:
        if cle not in st["prix"]:
            continue
        valeur = f"{euros(st['prix'][cle])} €/L"
        if st["ages"][cle] >= SIGNALE_JOURS:
            valeur += f" — relevé le {date_fr(st['dates'][cle])}"
        details[libelle] = valeur

    if st["adresse"]:
        details["Adresse"] = f"{st['adresse']}, {st['ville']}"
    else:
        details["Commune"] = st["ville"]
    if st["jour_et_nuit"]:
        details["Accès"] = "Automate ouvert 24 h/24"
    if st["absents"]:
        details["Non distribué"] = ", ".join(
            f"{nom} ({quand})" for nom, quand in st["absents"])
    if st["autoroute"]:
        details["Situation"] = "Aire d'autoroute"

    frais = min(st["ages"].values()) if st["ages"] else None
    if frais is None:
        etat = ["Aucun prix récent", "attention"]
    elif frais >= SIGNALE_JOURS:
        etat = [f"Relevé {dire_age(frais)}", "attention"]
    else:
        etat = [f"Relevé {dire_age(frais)}", "neutre"]

    # L'enseigne passe en tête du titre : « Super U — Vinay » se
    # reconnaît d'un coup d'œil, « Vinay » ne distingue pas les deux
    # stations de la commune. Sans enseigne connue, le titre reste la
    # commune, et rien n'est inventé.
    lieu = st["ville"] if chez_nous else f"{st['ville']} (hors territoire)"
    titre = f"{st['enseigne']} — {lieu}" if st.get("enseigne") else lieu
    if st.get("enseigne"):
        details["Enseigne"] = st["enseigne"]
    return {"titre": titre, "details": details, "etat": etat,
            "texte": ("Prix déclarés par le distributeur. Le prix affiché "
                      "à la pompe fait seul foi.")}


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE}
    base.update(habillage)
    return base


def note_commune(nb_stations, nb_voisines):
    morceaux = [
        "Prix déclarés par les distributeurs sur le portail national, "
        "et repris tels quels.",
    ]
    if nb_voisines:
        morceaux.append(
            f"Les stations qui ne sont pas sur la commune, à moins de "
            f"{VOISINES_KM} km, sont signalées comme telles avec leur "
            f"distance : elles sont là pour la comparaison, pas pour "
            f"gonfler le décompte.")
    morceaux.append(
        f"Un relevé de plus de {PERIME_JOURS} jours n'est pas publié ; "
        f"au-delà de {SIGNALE_JOURS} jours, sa date est écrite.")
    return " ".join(morceaux)


# ══════════════════════════════════════════════════════════════════
# SYNTHÈSE
# ══════════════════════════════════════════════════════════════════

def moins_cher(stations, cle):
    """La station la moins chère pour un carburant, hors autoroute.

    Les aires d'autoroute sont écartées de la comparaison, non par
    principe mais parce qu'elles ne jouent pas le même jeu : les deux
    aires de l'A49 relevées le 8 septembre 2026 affichaient dix-sept
    centimes de plus que la station la moins chère du territoire. Les
    inclure ferait dire à la page « le plein le moins cher est ici »
    sur une comparaison faussée. Elles restent listées, avec leur
    situation écrite.
    """
    candidates = [s for s in stations if not s["autoroute"] and cle in s["prix"]]
    if not candidates:
        return None
    return min(candidates, key=lambda s: s["prix"][cle])


def synthese_territoire(stations, nb_chez_nous, nb_voisines):
    """Mesures et bloc d'une Ã©chelle qui englobe plusieurs communes.

    Ne montre QUE les stations du territoire. Une page de canton
    rÃ©pond Ã  Â« qu'est-ce que le carburant coÃ»te ici Â», et la rÃ©ponse
    est la comparaison de nos stations entre elles. Les voisines
    n'ont leur place que sur une page de commune, oÃ¹ la question
    devient Â« oÃ¹ vais-je faire le plein depuis ce village Â».
    """
    mesures, items = {}, []
    a_nous = [s for s in stations if not s.get("_voisine")]

    bas = moins_cher(a_nous, "gazole")
    if bas:
        chez_nous = [s for s in a_nous
                     if not s["autoroute"] and "gazole" in s["prix"]]
        haut = max(chez_nous, key=lambda s: s["prix"]["gazole"])
        ecart = haut["prix"]["gazole"] - bas["prix"]["gazole"]
        mesures["CAR-01"] = mesure(
            euros(bas["prix"]["gazole"]), "€/L",
            "Gazole le moins cher", rang=10, ancre=ANCRE,
            repere=((f"{bas['enseigne']} à {bas['ville']}"
                     if bas.get("enseigne") else bas["ville"])
                    + f" · relevé {dire_age(bas['ages']['gazole'])}"),
            explication=("Prix le plus bas relevé dans les stations du "
                         "territoire, hors aires d'autoroute."),
            # Le carburant intéresse aussi qui consulte les transports.
            # Le détail reste ici : la page Transports n'en porte qu'un
            # renvoi. Voir le mécanisme d'écho, version 31.
            aussi={"rubrique": "transports"})

        if ecart >= 0.02:
            mesures["CAR-02"] = mesure(
                euros(ecart), "€/L",
                "Écart entre stations du territoire", rang=20, ancre=ANCRE,
                repere=(f"de {bas['ville']} à {haut['ville']} · "
                        f"{ecart * 50:.0f} € sur un plein de 50 litres"),
                explication=("Différence entre la station la moins chère et "
                             "la plus chère du territoire, pour le gazole. "
                             "C'est ce que coûte le fait de prendre l'une "
                             "plutôt que l'autre."))

    mesures["CAR-03"] = mesure(
        str(nb_chez_nous), "", "Stations sur le territoire", rang=30,
        ancre=ANCRE,
        explication=("Stations-service déclarant leurs prix au portail "
                     "national. Une station qui ne les déclare pas n'y "
                     "figure pas. Les stations voisines sont nommées sur "
                     "la page de chaque commune, non ici."))

    ordre = sorted(a_nous, key=lambda s: (s["autoroute"],
                                          s["prix"].get("gazole", 9.99),
                                          s["ville"]))
    items = [item_station(st, True) for st in ordre]

    blocs = [{
        "rubrique": RUBRIQUE,
        "id": ANCRE,
        "titre": "Stations-service et prix relevés",
        "items": items,
        "lien": {"url": f"https://data.economie.gouv.fr/explore/dataset/{FLUX}/",
                 "libelle": "Consulter la source"},
        "note": note_commune(nb_chez_nous, 0),
    }] if items else []

    return {"mesures": mesures, "blocs": blocs}


def voisines_de(commune, toutes, exclure_codes):
    """Les stations les plus proches d'une commune, hors les siennes.

    Mesurées depuis le centre de la commune. Les aires d'autoroute en
    sont exclues : la plus proche à vol d'oiseau peut être
    inaccessible sans dix kilomètres jusqu'à l'échangeur.
    """
    candidates = []
    for st in toutes:
        if st.get("code_commune") in exclure_codes or st["autoroute"]:
            continue
        if st.get("latitude") is None or "gazole" not in st["prix"]:
            continue
        km = distance_km(commune["latitude"], commune["longitude"],
                         st["latitude"], st["longitude"])
        if km <= VOISINES_KM:
            candidates.append((km, st))
    candidates.sort(key=lambda c: (c[0], c[1]["ville"]))
    return candidates[:VOISINES_MAXI]


def synthese_commune(commune, siennes, toutes):
    """Mesures et bloc d'une commune.

    Une commune sans station n'est pas une commune sans information :
    savoir où est la pompe la plus proche, et à quel prix, est
    précisément ce qu'un habitant d'un village cherche. C'est même la
    seule page du site où l'absence de la chose vaut d'être écrite.

    D'où qu'elles viennent, les stations voisines sont ici légitimes :
    la question posée depuis un village est « où vais-je faire le
    plein », et elle ne s'arrête pas à la limite du canton. C'est
    l'inverse de la page du canton, qui ne montre que les siennes.
    """
    proches = voisines_de(commune, toutes, {commune["code"]})
    items = [item_station(s, True) for s in siennes]
    for km, st in proches:
        # « hors territoire » qualifie la station, pas la page : Chatte
        # vue depuis Saint-Marcellin est une commune voisine du même
        # canton, et l'annoncer « hors territoire » serait faux. Seule
        # une station réellement extérieure porte la mention ; pour les
        # autres, la distance suffit à dire qu'elle est ailleurs.
        item = item_station(st, not st.get("_voisine"))
        item["details"]["Distance"] = f"{km:.0f} km du centre de la commune"
        items.append(item)

    mesures = {}
    if siennes:
        bas = moins_cher(siennes, "gazole") or siennes[0]
        if "gazole" in bas["prix"]:
            mesures["CAR-01"] = mesure(
                euros(bas["prix"]["gazole"]), "€/L", "Gazole", rang=10,
                ancre=ANCRE,
                repere=((f"{bas['enseigne']} · " if bas.get("enseigne") else "")
                        + f"{bas['adresse'] or bas['ville']} · relevé "
                        + dire_age(bas["ages"]["gazole"])),
                explication=("Prix déclaré par le distributeur. Le prix "
                             "affiché à la pompe fait seul foi."),
                aussi={"rubrique": "transports"})
        mesures["CAR-03"] = mesure(
            str(len(siennes)), "",
            "Station sur la commune" if len(siennes) == 1
            else "Stations sur la commune",
            rang=30, ancre=ANCRE)
    elif proches:
        km, proche = proches[0]
        mesures["CAR-04"] = mesure(
            f"{proche['ville']}, à {km:.0f} km", "",
            "Station la plus proche", rang=15, ancre=ANCRE,
            repere=((f"{proche['enseigne']} · " if proche.get("enseigne")
                     else "")
                    + f"Gazole {euros(proche['prix']['gazole'])} €/L · "
                    + f"relevé {dire_age(proche['ages']['gazole'])}"),
            explication=("Aucune station-service ne déclare de prix sur "
                         "cette commune. La distance est mesurée à vol "
                         "d'oiseau depuis le centre de la commune."),
            aussi={"rubrique": "transports"})
    else:
        return None

    blocs = [{
        "rubrique": RUBRIQUE,
        "id": ANCRE,
        "titre": ("Stations-service de la commune" if siennes
                  else "Stations-service les plus proches"),
        "items": items,
        "lien": {"url": f"https://data.economie.gouv.fr/explore/dataset/{FLUX}/",
                 "libelle": "Consulter la source"},
        "note": note_commune(len(siennes), len(proches)),
    }] if items else []

    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def ecrire_vide(motif):
    """Publie un fichier vide plutôt que de laisser la collecte d'hier.

    C'est le même choix que pour l'arrêté hivernal périmé : une page
    sans prix se comprend, une page qui affiche les prix de la semaine
    dernière sans le dire trompe son lecteur.
    """
    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION, "source": SOURCE, "licence": LICENCE,
        "frequence": "quotidienne", "motif_absence": motif,
        "communes": {}, "territoires": {},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Aucun prix publié — {motif}")
    print(f"  Fichier écrit vide : {SORTIE}\n")


def main():
    print("\nPrix des carburants — stations-service")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    reference = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = reference["communes"]
    par_code = {c["code"]: c for c in communes}
    codes_epci = {c.get("code_epci") for c in communes if c.get("code_epci")}
    cantons = {c.get("code_canton") for c in communes if c.get("code_canton")}

    if "--modele-enseignes" in sys.argv:
        DONNEES.mkdir(exist_ok=True)
        if REFERENCE_ENSEIGNES.exists():
            print(f"\n  {REFERENCE_ENSEIGNES} existe déjà — rien écrasé.\n")
        else:
            modele = json.loads(json.dumps(MODELE_ENSEIGNES))
            modele["saisi_le"] = date.today().isoformat()
            REFERENCE_ENSEIGNES.write_text(
                json.dumps(modele, ensure_ascii=False, indent=1),
                encoding="utf-8")
            print(f"\n  Modèle créé : {REFERENCE_ENSEIGNES}")
            print("  Complétez-le avec les identifiants affichés par une")
            print("  collecte ordinaire, puis relancez.\n")
        return

    rejeu = None
    if "--rejouer" in sys.argv:
        i = sys.argv.index("--rejouer")
        if i + 1 >= len(sys.argv):
            print("\n[ERREUR] --rejouer attend un nom de fichier.\n")
            sys.exit(1)
        rejeu = json.loads(Path(sys.argv[i + 1]).read_text(encoding="utf-8"))

    if rejeu:
        candidates = {str(k): tuple(v) for k, v in rejeu["candidates"].items()}
        brutes = rejeu["stations"]
        print(f"  collecte rejouée depuis {sys.argv[i + 1]}")
    else:
        boite = emprise(communes, MARGE_KM)
        print(f"  Emprise : {boite[0]:.3f},{boite[1]:.3f} → "
              f"{boite[2]:.3f},{boite[3]:.3f}  (marge {MARGE_KM} km)")

        candidates = stations_candidates(boite)
        if candidates is None:
            ecrire_vide("le jeu de rattachement n'a pas répondu")
            return
        if not candidates:
            ecrire_vide("aucune station dans l'emprise")
            return
        print(f"  Stations dans l'emprise : {len(candidates)}")

        brutes = prix_des_stations(candidates)
        if brutes is None:
            ecrire_vide("le flux instantané n'a pas répondu")
            return

    if not brutes:
        ecrire_vide("le flux instantané n'a renvoyé aucune station")
        return

    # ── enseignes : la saisie d'abord, OSM ensuite ───────────────────
    saisies, saisi_le = enseignes_saisies()
    noeuds = None
    if rejeu is not None:
        noeuds = [tuple(n) for n in (rejeu.get("osm") or [])]
    elif "--sans-osm" not in sys.argv:
        noeuds = enseignes_osm(emprise(communes, MARGE_KM))

    if "--exemple" in sys.argv:
        DONNEES.mkdir(exist_ok=True)
        EXEMPLE.write_text(json.dumps(
            {"candidates": {k: list(v) for k, v in candidates.items()},
             "stations": brutes}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"  Collecte enregistrée : {EXEMPLE}")

    # ── rattachement, et le filet qui le contrôle ────────────────────
    stations, ecartees, anomalies = [], [], []
    enseignes_par_origine = {"saisie": 0, "OpenStreetMap": 0}
    for brute in brutes:
        st = station_lisible(brute, anomalies)
        # La saisie l'emporte, toujours : une chaîne vide dans le
        # fichier de référence est une décision — « cette station n'a
        # pas d'enseigne » — et non une absence de valeur.
        if st["id"] in saisies:
            st["enseigne"] = saisies[st["id"]]
            st["enseigne_origine"] = "saisie"
            if st["enseigne"]:
                enseignes_par_origine["saisie"] += 1
        else:
            trouve = apparier_enseigne(st, noeuds)
            if trouve:
                st["enseigne"], _distance = trouve
                st["enseigne_origine"] = "OpenStreetMap"
                enseignes_par_origine["OpenStreetMap"] += 1
        rattachement = candidates.get(st["id"])
        if not rattachement:
            ecartees.append((st["ville"], "sans code INSEE dans le jeu "
                                          "quotidien"))
            continue
        code, nom_producteur = rattachement
        st["code_commune"] = code
        st["_voisine"] = code not in par_code

        # Les deux sources se contrôlent l'une l'autre : le producteur
        # dit dans quelle commune se trouve la station, et le flux dit
        # où elle est. Si les deux s'éloignent de plus de vingt
        # kilomètres, l'une des deux se trompe et nous n'avons pas à
        # choisir laquelle.
        if not st["_voisine"] and st["latitude"] is not None:
            c = par_code[code]
            ecart = distance_km(c["latitude"], c["longitude"],
                                st["latitude"], st["longitude"])
            seuil = ecart_tolere(c)
            if ecart > seuil:
                ecartees.append(
                    (st["ville"],
                     f"rattachée à {c['nom']} mais située à {ecart:.0f} km "
                     f"de son centre, pour un seuil de {seuil:.0f} km — "
                     f"les deux sources se contredisent"))
                continue

        if not st["prix"]:
            ecartees.append((st["ville"], "aucun relevé de moins de "
                                          f"{PERIME_JOURS} jours"))
            continue
        stations.append(st)

    # Seules les stations DU TERRITOIRE sont détaillées. L'enveloppe de
    # collecte en ramène nonante et quelques, dont la quasi-totalité ne
    # sera jamais citée : les énumérer noierait les cinq lignes que
    # cette sortie existe pour faire lire. Les voisines réellement
    # retenues sont récapitulées plus bas, une fois les pages
    # construites — c'est à ce moment seulement qu'on sait lesquelles.
    a_nous_vue = [s for s in stations if not s["_voisine"]]
    print(f"\n  Stations du territoire : {len(a_nous_vue)}")
    for st in sorted(a_nous_vue, key=lambda s: s["ville"]):
        prix = st["prix"].get("gazole")
        autoroute = " · autoroute" if st["autoroute"] else ""
        detail = (f"gazole {euros(prix)} €/L, relevé "
                  f"{dire_age(st['ages']['gazole'])}" if prix
                  else "pas de gazole publiable")
        print(f"    {st['ville']}{autoroute} — {detail}")
    for ville, motif in ecartees:
        print(f"    [écartée] {ville or '?'} — {motif}")

    if anomalies:
        # Un prix hors bornes n'est jamais anodin : c'est ainsi que la
        # Bourne avait failli publier une hausse spectaculaire du débit
        # avec des données parfaitement vraies. On l'écrit, toujours.
        print(f"\n  [ATTENTION] {len(anomalies)} prix hors des bornes du "
              f"plausible, écarté(s) :")
        for ville, libelle, motif in anomalies[:10]:
            print(f"    {ville} — {libelle} : {motif}")
        if len(anomalies) > 10:
            print(f"    … et {len(anomalies) - 10} autre(s)")
        print("    Si la liste est longue, la source a probablement changé")
        print("    d'unité : vérifiez avant de publier.")

    if not stations:
        ecrire_vide("aucune station ne passe les contrôles")
        return

    a_nous = [s for s in stations if not s["_voisine"]]
    voisines = [s for s in stations if s["_voisine"]]
    if not a_nous:
        ecrire_vide("aucune station sur le territoire lui-même")
        return

    # ── communes ─────────────────────────────────────────────────────
    resultat = {}
    for code, commune in par_code.items():
        siennes = [s for s in a_nous if s["code_commune"] == code]
        bloc = synthese_commune(commune, siennes, stations)
        if bloc:
            resultat[code] = bloc

    # ── canton et intercommunalité ───────────────────────────────────
    synthese = synthese_territoire(stations, len(a_nous), len(voisines))
    territoires = {}
    for canton in cantons:
        territoires[f"canton:{canton}"] = synthese
    for epci in codes_epci:
        territoires[f"epci:{epci}"] = synthese

    DONNEES.mkdir(exist_ok=True)
    # Le fichier déclare DEUX licences dès qu'une enseigne vient d'OSM :
    # les prix restent sous Licence Ouverte, l'enseigne est sous ODbL.
    # Ne déclarer que la première serait inexact, et déclarer l'ODbL
    # sur tout serait inexact dans l'autre sens.
    licences = [LICENCE]
    sources = [SOURCE]
    if any(s.get("enseigne") and s["enseigne_origine"] == "OpenStreetMap"
           for s in stations):
        licences.append(LICENCE_OSM)
        sources.append(SOURCE_OSM)

    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": " · ".join(sources),
        "licence": licences if len(licences) > 1 else LICENCE,
        "frequence": "quotidienne",
        "releve_le": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "communes": resultat,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    avec = sum(1 for v in resultat.values()
               if any(k in v["mesures"] for k in ("CAR-01", "CAR-03")))
    # Quelles voisines ont réellement servi, et sur combien de pages.
    # C'est le seul chiffre qui dise si le rayon est bien réglé : une
    # ville qui apparaît sur quarante pages est trop dominante, une
    # enveloppe dont rien ne ressort est trop large pour rien.
    citees = {}
    for bloc in resultat.values():
        for b in bloc["blocs"]:
            for item in b["items"]:
                if "(hors territoire)" in item["titre"]:
                    ville = item["titre"].replace(" (hors territoire)", "")
                    citees[ville] = citees.get(ville, 0) + 1

    # Comptées sur les stations RETENUES, pas sur toutes celles qu'on a
    # regardées : une enseigne trouvée pour une station écartée plus loin
    # ne figure nulle part, et la faire apparaître au décompte donnerait
    # deux nombres qui ne s'additionnent pas.
    par_saisie = sum(1 for s in stations
                     if s.get("enseigne") and s["enseigne_origine"] == "saisie")
    par_osm = sum(1 for s in stations
                  if s.get("enseigne")
                  and s["enseigne_origine"] == "OpenStreetMap")
    print(f"\n  Enseignes nommées  : {par_saisie + par_osm} sur "
          f"{len(stations)} ({par_saisie} par saisie, "
          f"{par_osm} par OpenStreetMap)")
    if noeuds is None:
        print(f"                       OpenStreetMap n'a pas été interrogé : "
              f"seule la saisie a servi.")
    anonymes = [s for s in a_nous if not s.get("enseigne")]
    if anonymes:
        print(f"  Sans enseigne sur le territoire ({len(anonymes)}) — "
              f"identifiants à saisir dans")
        print(f"  {REFERENCE_ENSEIGNES} :")
        for s in anonymes:
            print(f"    {s['id']}  {s['ville']} — {s['adresse']}")

    print(f"\n  Sur le territoire  : {len(a_nous)} station(s)")
    print(f"  Enveloppe          : {len(voisines)} station(s) hors "
          f"territoire collectée(s), {len(citees)} ville(s) citée(s)")
    for ville, n in sorted(citees.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {ville} — sur {n} page(s) de commune")
    print(f"  Communes servies   : {len(resultat)} sur {len(par_code)} "
          f"({avec} avec une station, "
          f"{len(resultat) - avec} avec la plus proche)")
    # Le même chiffre que celui publié en tête de rubrique : la sortie
    # du script doit dire ce que le site va dire, pas autre chose.
    bas = moins_cher(a_nous, "gazole")
    if bas:
        print(f"  Gazole le moins cher : {euros(bas['prix']['gazole'])} €/L "
              f"à {bas['ville']} (territoire)")
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
