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

VERSION_SCRIPT = 1

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

VERSION = 1
RUBRIQUE = "carburants"
ANCRE = "stations-service"

DELAI = 30
TENTATIVES = 4

# ── Réglages arbitrables ────────────────────────────────────────────
# Ces quatre nombres décident de ce que la rubrique montre. Ils sont
# groupés ici pour être discutés, pas cherchés.

# Marge autour du territoire, en kilomètres. Six stations sur
# quarante-sept communes ne font pas une page utile : sans les voisines
# immédiates, le lecteur n'a rien à comparer. Au-delà d'une dizaine de
# kilomètres en revanche, la page cesse de parler du territoire.
MARGE_KM = 10

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
    filtre = (f"in_bbox(geom, {lonmin:.5f}, {latmin:.5f}, "
              f"{lonmax:.5f}, {latmax:.5f})")
    lignes = appeler(QUOTIDIEN, where=filtre, limit=100,
                     select="id,com_arm_code,com_arm_name",
                     group_by="id,com_arm_code,com_arm_name")
    if lignes is None:
        return None
    candidates = {}
    for l in lignes:
        ident = str(l.get("id") or "").strip()
        code = str(l.get("com_arm_code") or "").strip()
        if ident and code:
            candidates[ident] = (code, str(l.get("com_arm_name") or "").strip())
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

    titre = st["ville"] if chez_nous else f"{st['ville']} (hors territoire)"
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
            f"Les stations situées hors du territoire, à moins de "
            f"{MARGE_KM} km, sont signalées comme telles : elles sont "
            f"là pour la comparaison, pas pour gonfler le décompte.")
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
    """Mesures et bloc pour une échelle qui englobe plusieurs communes."""
    mesures, items = {}, []

    # Le chiffre mis en avant est celui du TERRITOIRE. Les stations
    # voisines servent à comparer, pas à fournir le titre : une page du
    # Sud Grésivaudan qui annonce en tête le prix d'une station de la
    # Drôme ne parle plus de son territoire.
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
            repere=f"{bas['ville']} · relevé {dire_age(bas['ages']['gazole'])}",
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

        # Une station voisine nettement moins chère est une information
        # que le lecteur cherche et qu'aucune page nationale ne lui
        # donne : elle ne raisonne pas par territoire.
        dehors = moins_cher([s for s in stations if s.get("_voisine")], "gazole")
        if dehors and bas["prix"]["gazole"] - dehors["prix"]["gazole"] >= 0.02:
            gain = bas["prix"]["gazole"] - dehors["prix"]["gazole"]
            mesures["CAR-05"] = mesure(
                euros(dehors["prix"]["gazole"]), "€/L",
                "Moins cher juste à côté", rang=25, ancre=ANCRE,
                repere=(f"{dehors['ville']}, hors territoire · "
                        f"{gain * 50:.0f} € de moins sur un plein"),
                explication=("Station située hors du territoire, à moins de "
                             f"{MARGE_KM} km de l'une de ses communes."))

    mesures["CAR-03"] = mesure(
        str(nb_chez_nous), "", "Stations sur le territoire", rang=30,
        ancre=ANCRE,
        repere=(f"et {nb_voisines} à moins de {MARGE_KM} km"
                if nb_voisines else None),
        explication=("Stations-service déclarant leurs prix au portail "
                     "national. Une station qui ne les déclare pas n'y "
                     "figure pas."))

    # Les stations du territoire d'abord, du moins cher au plus cher ;
    # puis les voisines ; les aires d'autoroute en dernier. Trier sur le
    # seul prix mettrait une station de la Drôme en tête d'une page du
    # Sud Grésivaudan, ce qui n'est pas ce que la page raconte.
    ordre = sorted(
        stations,
        key=lambda s: (s.get("_voisine", False),
                       s["autoroute"],
                       s["prix"].get("gazole", 9.99),
                       s["ville"]))
    for st in ordre:
        items.append(item_station(st, not st.get("_voisine")))

    blocs = [{
        "rubrique": RUBRIQUE,
        "id": ANCRE,
        "titre": "Stations-service et prix relevés",
        "items": items,
        "lien": {"url": f"https://data.economie.gouv.fr/explore/dataset/{FLUX}/",
                 "libelle": "Consulter la source"},
        "note": note_commune(nb_chez_nous, nb_voisines),
    }] if items else []

    return {"mesures": mesures, "blocs": blocs}


def synthese_commune(commune, siennes, toutes):
    """Mesures et bloc d'une commune.

    Une commune sans station n'est pas une commune sans information :
    savoir où est la pompe la plus proche, et à quel prix, est
    précisément ce qu'un habitant d'un village cherche. C'est même la
    seule page du site où l'absence de la chose vaut d'être écrite.
    """
    if siennes:
        bas = moins_cher(siennes, "gazole") or siennes[0]
        mesures = {}
        if "gazole" in bas["prix"]:
            mesures["CAR-01"] = mesure(
                euros(bas["prix"]["gazole"]), "€/L", "Gazole", rang=10,
                ancre=ANCRE,
                repere=(f"{bas['adresse'] or bas['ville']} · relevé "
                        f"{dire_age(bas['ages']['gazole'])}"),
                explication=("Prix déclaré par le distributeur. Le prix "
                             "affiché à la pompe fait seul foi."),
                aussi={"rubrique": "transports"})
        mesures["CAR-03"] = mesure(
            str(len(siennes)), "",
            "Station sur la commune" if len(siennes) == 1
            else "Stations sur la commune",
            rang=30, ancre=ANCRE)
        blocs = [{
            "rubrique": RUBRIQUE,
            "id": ANCRE,
            "titre": "Stations-service de la commune",
            "items": [item_station(s, True) for s in siennes],
            "lien": {"url": f"https://data.economie.gouv.fr/explore/dataset/{FLUX}/",
                     "libelle": "Consulter la source"},
            "note": note_commune(len(siennes), 0),
        }]
        return {"mesures": mesures, "blocs": blocs}

    # Aucune station ici : on nomme la plus proche.
    # Les aires d'autoroute sont exclues : la plus proche à vol d'oiseau
    # peut être inaccessible sans faire dix kilomètres jusqu'à l'échangeur.
    avec_position = [s for s in toutes
                     if not s["autoroute"]
                     and s.get("latitude") is not None
                     and s.get("longitude") is not None
                     and "gazole" in s["prix"]]
    if not avec_position:
        return None
    proche = min(avec_position,
                 key=lambda s: distance_km(commune["latitude"],
                                           commune["longitude"],
                                           s["latitude"], s["longitude"]))
    km = distance_km(commune["latitude"], commune["longitude"],
                     proche["latitude"], proche["longitude"])
    return {
        "mesures": {
            "CAR-04": mesure(
                f"{proche['ville']}, à {km:.0f} km", "",
                "Station la plus proche", rang=15,
                repere=(f"Gazole {euros(proche['prix']['gazole'])} €/L · "
                        f"relevé {dire_age(proche['ages']['gazole'])}"),
                explication=("Aucune station-service ne déclare de prix sur "
                             "cette commune. La distance est mesurée à vol "
                             "d'oiseau depuis le centre de la commune."),
                aussi={"rubrique": "transports"}),
        },
        "blocs": [],
    }


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

    if "--exemple" in sys.argv:
        DONNEES.mkdir(exist_ok=True)
        EXEMPLE.write_text(json.dumps(
            {"candidates": {k: list(v) for k, v in candidates.items()},
             "stations": brutes}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"  Collecte enregistrée : {EXEMPLE}")

    # ── rattachement, et le filet qui le contrôle ────────────────────
    stations, ecartees, anomalies = [], [], []
    for brute in brutes:
        st = station_lisible(brute, anomalies)
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

    print(f"\n  Stations retenues : {len(stations)}")
    for st in sorted(stations, key=lambda s: (s["_voisine"], s["ville"])):
        prix = st["prix"].get("gazole")
        marque = " (hors territoire)" if st["_voisine"] else ""
        autoroute = " · autoroute" if st["autoroute"] else ""
        detail = (f"gazole {euros(prix)} €/L, relevé "
                  f"{dire_age(st['ages']['gazole'])}" if prix
                  else "pas de gazole publiable")
        print(f"    {st['ville']}{marque}{autoroute} — {detail}")
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
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "quotidienne",
        "releve_le": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "communes": resultat,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    avec = sum(1 for v in resultat.values()
               if any(k in v["mesures"] for k in ("CAR-01", "CAR-03")))
    print(f"\n  Sur le territoire  : {len(a_nous)} station(s)")
    print(f"  Aux abords         : {len(voisines)} station(s) à moins de "
          f"{MARGE_KM} km")
    print(f"  Communes servies   : {len(resultat)} sur {len(par_code)} "
          f"({avec} avec une station, "
          f"{len(resultat) - avec} avec la plus proche)")
    # Le même chiffre que celui publié en tête de rubrique : la sortie
    # du script doit dire ce que le site va dire, pas autre chose.
    bas = moins_cher(a_nous, "gazole")
    if bas:
        print(f"  Gazole le moins cher : {euros(bas['prix']['gazole'])} €/L "
              f"à {bas['ville']} (territoire)")
    dehors = moins_cher(voisines, "gazole")
    if dehors and bas and dehors["prix"]["gazole"] < bas["prix"]["gazole"]:
        print(f"  Moins cher à côté    : "
              f"{euros(dehors['prix']['gazole'])} €/L à {dehors['ville']}")
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
