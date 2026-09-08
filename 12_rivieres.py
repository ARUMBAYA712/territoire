"""
12_rivieres.py — Débit des cours d'eau (Hub'Eau hydrométrie)
=============================================================

Récupère les débits mesurés par les stations hydrométriques du
territoire, et publie une synthèse **au niveau du canton**.

Même principe que les nappes : une rivière ne s'arrête pas aux limites
communales, et les stations sont rares. La donnée est rattachée au
canton et à l'intercommunalité, avec la station de référence nommée et
sa distance affichée.

Source : API Hydrométrie de Hub'Eau, données des services de l'État.

Produit :
    data/mesures-rivieres.json   repris par 03_agregation.py

Utilisation :
    python 12_rivieres.py
    python 12_rivieres.py --tout        recollecte intégrale
    python 12_rivieres.py --inspecter   affiche les champs bruts de l'API
"""

import json
import math
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path

VERSION_SCRIPT = 6

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-rivieres.json"

API = "https://hubeau.eaufrance.fr/api/v2/hydrometrie"
SOURCE = "Hub'Eau — hydrométrie, services de l'État"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "rivieres"
ANCRE = "stations-hydrometriques"

MARGE = 0.10              # degrés ajoutés autour du territoire
SEUIL_ELOIGNEMENT = 20    # km au-delà desquels la station devient indicative
STATIONS_MAX = 12

# Nombre de stations conservées par site hydrométrique. Deux, parce
# qu'un site en porte rarement plus, et parce qu'il faut les
# interroger pour savoir laquelle fait référence.
STATIONS_PAR_SITE = 2
HISTORIQUE = 5            # années de chronique interrogées

# Codes de grandeur des observations élaborées. La nomenclature a varié
# selon les versions de l'API : on essaie les formes connues.
GRANDEURS = ("QmJ", "QmnJ", "QJM")
FRAICHEUR_JOURS = 30      # ancienneté maximale pour servir de référence
DELAI = 120
TENTATIVES = 4
PAUSE = 0.4


# ══════════════════════════════════════════════════════════════════

def appeler(operation, silencieux=False, **params):
    url = f"{API}/{operation}?" + urllib.parse.urlencode(params)
    attente = 3
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0",
                              "Accept": "application/json"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                statut = getattr(reponse, "status", 200)
                corps = reponse.read()
            if statut == 204 or not corps.strip():
                return []
            try:
                return json.loads(corps.decode("utf-8")).get("data", [])
            except json.JSONDecodeError:
                return None
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return []
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            # Le corps de la réponse porte souvent le motif exact du
            # refus : « paramètre inconnu », « valeur hors bornes »…
            detail = ""
            try:
                corps = e.read().decode("utf-8", errors="replace")
                donnees = json.loads(corps)
                detail = str(donnees.get("api_message")
                             or donnees.get("message") or corps)[:200]
            except Exception:
                pass
            if not silencieux:
                print(f"\n  [ERREUR] Hub'Eau a répondu {e.code}")
                if detail:
                    print(f"  {detail}")
                print(f"  {url}")
            return None
        except (urllib.error.URLError, OSError) as e:
            if tentative < TENTATIVES:
                print("[lenteur] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            print(f"\n  [ERREUR] Hub'Eau injoignable : {e}")
            return None
    return None


def champ(enregistrement, *noms):
    for nom in noms:
        valeur = enregistrement.get(nom)
        if valeur not in (None, "", []):
            return valeur
    return None


def emprise(communes, marge=MARGE):
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    if not lons:
        return None
    return (round(min(lons) - marge, 4), round(min(lats) - marge, 4),
            round(max(lons) + marge, 4), round(max(lats) + marge, 4))


def centre(communes):
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    if not lons:
        return None
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def distance_km(a, b):
    lat_moy = math.radians((a[1] + b[1]) / 2)
    dx = (a[0] - b[0]) * 111.32 * math.cos(lat_moy)
    dy = (a[1] - b[1]) * 110.57
    return math.hypot(dx, dy)


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def _date_fr(iso):
    if not iso:
        return "inconnue"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def debit_lisible(metres_cubes):
    """Un débit se lit en m³/s au-dessus de 1, en L/s en dessous."""
    if metres_cubes is None:
        return None, ""
    if metres_cubes >= 1:
        return round(metres_cubes, 2), "m³/s"
    return round(metres_cubes * 1000), "L/s"


# ══════════════════════════════════════════════════════════════════

def sites_du_territoire(boite, repere):
    """Sites hydrométriques déclarés par l'API elle-même.

    **N'est plus utilisée par le traitement**, et conservée pour
    mémoire. Interroger les observations par site paraissait plus sûr :
    un site regroupe les stations qui se sont succédé au même point du
    cours d'eau, et l'API répond à un code de site.

    C'est faux quand deux stations y sont simultanées. Sur la
    Vernaisson, l'interrogation par site renvoyait 1 454 valeurs
    mensuelles pour une chronique de soixante-deux ans — soit deux fois
    trop : deux stations différentes empilées dans la même suite, sans
    que rien ne le signale. Voir « stations_du_territoire », qui la
    remplace.
    """
    lot = appeler("referentiel/sites",
                  bbox=",".join(str(v) for v in boite),
                  size=200, format="json")
    if lot is None:
        return None

    sites = []
    for s in lot:
        code = champ(s, "code_site")
        if not code:
            continue
        x = champ(s, "longitude_site", "longitude")
        y = champ(s, "latitude_site", "latitude")
        eloignement = None
        if repere and x is not None and y is not None:
            try:
                eloignement = distance_km(repere, (float(x), float(y)))
            except (TypeError, ValueError):
                eloignement = None
        sites.append({
            "code": code,
            "site": str(code),
            "nom": str(champ(s, "libelle_site") or code),
            "cours_eau": str(champ(s, "libelle_cours_eau") or ""),
            "commune": str(champ(s, "libelle_commune") or ""),
            "distance": eloignement,
        })

    sites.sort(key=lambda s: (s["distance"] is None, s["distance"] or 0))
    return sites, len(lot)


def stations_du_territoire(boite, repere):
    """Stations hydrométriques de l'emprise, les plus proches d'abord."""
    lot = appeler("referentiel/stations",
                  bbox=",".join(str(v) for v in boite),
                  size=200, format="json")
    if lot is None:
        return None

    stations = []
    for s in lot:
        code = champ(s, "code_station")
        if not code:
            continue
        en_service = champ(s, "en_service")
        if en_service is False:
            continue

        x = champ(s, "longitude_station", "longitude")
        y = champ(s, "latitude_station", "latitude")
        eloignement = None
        if repere and x is not None and y is not None:
            try:
                eloignement = distance_km(repere, (float(x), float(y)))
            except (TypeError, ValueError):
                eloignement = None

        # Les observations élaborées s'interrogent par code de SITE et
        # non de station : un site regroupe plusieurs stations de mesure
        # successives sur le même point du cours d'eau.
        site = champ(s, "code_site")
        if not site:
            continue

        stations.append({
            "code": code,
            "site": str(site),
            "nom": str(champ(s, "libelle_site", "libelle_station") or code),
            "cours_eau": str(champ(s, "libelle_cours_eau",
                                   "libelle_entite_hydrographique") or ""),
            "commune": str(champ(s, "libelle_commune") or ""),
            "distance": eloignement,
        })

    stations.sort(key=lambda s: (s["distance"] is None, s["distance"] or 0))

    # Plusieurs stations partagent parfois un même site. Tant que les
    # observations étaient demandées par site, elles renvoyaient la
    # même chronique et n'en garder qu'une allait de soi.
    #
    # Ce n'est plus le cas : deux stations d'un même site peuvent être
    # simultanées et mesurer des grandeurs différentes — sur la Bourne,
    # l'une annonce 0,9 m³/s quand l'autre en annonce 20,5. Choisir
    # « la plus proche » n'a alors aucun sens : elles sont au même
    # endroit, et le tri retiendrait l'une ou l'autre au hasard.
    #
    # On en garde donc deux par site, et c'est la densité réelle des
    # mesures — connue seulement après interrogation — qui départagera.
    par_site, uniques = {}, []
    for s in stations:
        garde = par_site.setdefault(s["site"], 0)
        if garde >= STATIONS_PAR_SITE:
            continue
        par_site[s["site"]] = garde + 1
        uniques.append(s)
    return uniques, len(lot)


def chronique(code_station):
    """Débits journaliers des dernières années, du plus récent au plus ancien.

    Les observations élaborées fournissent un débit moyen journalier,
    plus représentatif qu'une mesure instantanée pour comparer d'une
    année sur l'autre.

    **Interrogation par station, non par site.** Ce script demandait
    auparavant les observations d'un SITE, en supposant qu'un site
    regroupe des stations qui se succèdent dans le temps. C'est vrai
    souvent, faux ici : le site de la Bourne à Saint-Just-de-Claix
    porte deux stations simultanées, une EDF et une DREAL, qui
    n'annoncent pas la même chose — 0,9 m³/s contre 20,5 m³/s pour le
    même mois de janvier 2003. Les mélanger revenait à calculer une
    médiane sur deux grandeurs différentes.
    """
    depuis = (date.today() - timedelta(days=365 * HISTORIQUE)).isoformat()

    # Les paramètres acceptés varient d'une version de l'API à l'autre.
    # Plutôt que d'en supposer un jeu, on essaie les combinaisons par
    # ordre de préférence et on retient la première qui répond.
    tentatives = []
    for grandeur in GRANDEURS:
        tentatives.append({"code_entite": code_station,
                           "grandeur_hydro_elab": grandeur,
                           "date_debut_obs_elab": depuis, "size": 5000})
    lot = None
    for params in tentatives:
        lot = appeler("obs_elab", silencieux=True, **params)
        if lot:
            break
    if not lot:
        lot = []

    mesures = []
    for o in lot:
        jour = champ(o, "date_obs_elab", "date_obs")
        brut = champ(o, "resultat_obs_elab", "resultat_obs")
        if jour is None or brut is None:
            continue
        try:
            # Hub'Eau exprime les débits en litres par seconde.
            mesures.append({"date": str(jour)[:10],
                            "debit": float(brut) / 1000.0})
        except (TypeError, ValueError):
            continue

    mesures.sort(key=lambda m: m["date"], reverse=True)
    return mesures



# ══════════════════════════════════════════════════════════════════
# SÉRIE HISTORIQUE — débits moyens mensuels
#
# Hub'Eau calcule lui-même le débit moyen mensuel (grandeur « QmM ») et
# le sert avec sa qualification. Sur ce territoire, certaines stations
# remontent à 1967 : il y a de quoi montrer une évolution.
#
# ── Ce qui a failli être publié de travers ───────────────────────
#
# La station EDF de la Bourne à Saint-Just-de-Claix annonce 708 valeurs
# mensuelles depuis janvier 1967. Vérification faite :
#
#     janvier 1967 :    947 L/s  ·  qualification « Non qualifiée »
#     janvier 1990 :  1 542 L/s  ·  qualification « Bonne »
#     janvier 2020 :  8 536 L/s  ·  qualification « Bonne »
#
# Les valeurs les plus anciennes sont environ dix fois trop faibles,
# et ce sont exactement celles que la source déclare non qualifiées.
# Tracées telles quelles, elles auraient dessiné une hausse
# spectaculaire du débit de la Bourne depuis cinquante ans — une
# impression fausse appuyée sur des données vraies, c'est-à-dire
# précisément ce que ce site s'interdit.
#
# ── Les deux filets, et pourquoi il en faut deux ─────────────────
#
# 1. **La qualification, qui vient de la source.** On ne retient que
#    les mois qualifiés. « Non qualifiée » veut dire que le producteur
#    n'a pas expertisé la valeur : ce n'est pas à nous de le faire à sa
#    place.
#
# 2. **Un contrôle d'homogénéité, qui ne vient de personne.** On
#    compare la médiane des premières années à celle des dernières. Un
#    rapport supérieur à trois n'est pas une tendance hydrologique,
#    c'est une rupture de méthode ou d'unité. La série entière est
#    alors refusée, et le motif écrit dans la sortie du script.
#
# Le second filet existe parce que le premier repose sur un champ que
# le producteur remplit — et qu'un champ peut être rempli à tort.
#
# ── Une interrogation par station, non par site ──────────────────
#
# Le reste de ce script interroge les observations par code de SITE,
# ce qui convient à des stations qui se succèdent dans le temps. Mais
# un même site porte parfois deux stations simultanées — ici une EDF
# et une DREAL — qui ne mesurent pas la même chose : sur la Bourne en
# 2003, l'une donne 0,9 m³/s quand l'autre en donne 20,5. Pour une
# chronique, on interroge donc la STATION, dont on sait quoi dire.
# ══════════════════════════════════════════════════════════════════

GRANDEUR_MENSUELLE = "QmM"

# Qualifications retenues. « Non qualifiée » signifie que le producteur
# n'a pas expertisé la valeur : elle ne sert ni de courbe ni de repère.
QUALIFICATIONS = ("bonne", "douteuse", "correcte")

MOIS_MINIMUM = 120          # dix ans : en deçà, une « évolution » n'en est pas une
ANNEES_TEMOIN = 5           # fenêtres comparées pour le contrôle d'homogénéité
ECART_MAXIMUM = 3.0         # au-delà, rupture de méthode plutôt que tendance

# Cours d'eau dont le débit mesuré traduit autant la gestion des
# ouvrages que la pluie. Leur courbe reste publiable — c'est le débit
# réel de la rivière — mais elle ne raconte pas le climat, et la fiche
# doit le dire.
COURS_EAU_AMENAGES = ("isère", "romanche", "drac")

RESERVE_AMENAGE = (
    "Cette rivière est fortement aménagée : le débit mesuré traduit "
    "autant la gestion des ouvrages hydroélectriques que la pluie et la "
    "fonte des neiges. La courbe décrit la rivière telle qu'elle coule, "
    "non le climat du bassin.")


def mediane(valeurs):
    suite = sorted(v for v in valeurs if v is not None)
    if not suite:
        return None
    n = len(suite)
    return suite[n // 2] if n % 2 else (suite[n // 2 - 1] + suite[n // 2]) / 2


def chronique_mensuelle(code_station):
    """Débits moyens mensuels qualifiés d'une station, du plus ancien.

    Renvoie une liste de (année, mois, débit en m³/s) ; les mois sans
    valeur retenue sont absents, les trous seront rendus visibles au
    moment de construire la série.
    """
    lot = appeler("obs_elab", silencieux=True,
                  code_entite=code_station,
                  grandeur_hydro_elab=GRANDEUR_MENSUELLE,
                  size=5000)
    if not lot:
        return [], 0

    retenus, ecartes = [], 0
    for o in lot:
        jour = champ(o, "date_obs_elab", "date_obs")
        brut = champ(o, "resultat_obs_elab", "resultat_obs")
        if jour is None or brut is None:
            continue
        qualification = str(champ(o, "libelle_qualification") or "").lower()
        if qualification and not any(q in qualification for q in QUALIFICATIONS):
            ecartes += 1
            continue
        try:
            texte = str(jour)[:10]
            retenus.append((int(texte[:4]), int(texte[5:7]),
                            float(brut) / 1000.0))
        except (TypeError, ValueError):
            continue
    retenus.sort()
    return retenus, ecartes


def doublons_mensuels(points):
    """Nombre de mois apparaissant plus d'une fois dans la suite.

    Un mois ne peut être mesuré qu'une fois par une station donnée. En
    voir deux signifie que la réponse empile plusieurs stations — ce qui
    arrivait tant que les observations étaient demandées par site.
    C'est le contrôle qui aurait dû exister dès le premier jour : il
    détecte l'erreur au lieu de la laisser produire une courbe
    plausible.
    """
    vus, doubles = set(), 0
    for a, m, _ in points:
        if (a, m) in vus:
            doubles += 1
        vus.add((a, m))
    return doubles


def homogene(points):
    """La série décrit-elle la même chose d'un bout à l'autre ?

    Renvoie (True, None) ou (False, motif). Le contrôle ne juge pas la
    vraisemblance hydrologique : il détecte un changement d'échelle,
    qu'aucune rivière ne produit d'elle-même.
    """
    doubles = doublons_mensuels(points)
    if doubles:
        return False, (f"{doubles} mois apparaissent plusieurs fois — la "
                       f"réponse empile plusieurs stations, la suite n'a "
                       f"pas de sens")
    if len(points) < MOIS_MINIMUM:
        return False, f"{len(points)} mois qualifiés, moins que les {MOIS_MINIMUM} requis"
    premiere = points[0][0]
    derniere = points[-1][0]
    if derniere - premiere < 2 * ANNEES_TEMOIN:
        return True, None            # trop courte pour comparer deux fenêtres

    debut = [v for (a, _, v) in points if a < premiere + ANNEES_TEMOIN]
    fin = [v for (a, _, v) in points if a > derniere - ANNEES_TEMOIN]
    m1, m2 = mediane(debut), mediane(fin)
    if not m1 or not m2:
        return True, None
    rapport = max(m1, m2) / min(m1, m2)
    if rapport > ECART_MAXIMUM:
        return False, (f"médiane {m1:.2f} m³/s au début contre {m2:.2f} à la "
                       f"fin, soit un rapport de {rapport:.0f} — rupture "
                       f"d'échelle, pas une tendance")
    return True, None


def serie_continue(points):
    """Suite mensuelle régulière, du premier au dernier mois retenu.

    Les mois absents deviennent des trous explicites : c'est le
    générateur qui les affichera comme tels, et il ne les interpolera
    pas.
    """
    valeurs = {(a, m): v for a, m, v in points}
    a0, m0, _ = points[0]
    a1, m1, _ = points[-1]
    suite, a, m = [], a0, m0
    while (a, m) <= (a1, m1):
        v = valeurs.get((a, m))
        suite.append(round(v, 2) if v is not None else None)
        m += 1
        if m > 12:
            a, m = a + 1, 1
    return suite, f"{a0}-{m0:02d}"


def accord_avec_le_journalier(points, journalier):
    """La chronique mensuelle mesure-t-elle la même chose que le reste ?

    Le script interroge déjà, pour chaque station, un débit moyen
    JOURNALIER sur cinq ans : c'est lui qui alimente l'indicateur
    « proche des valeurs habituelles ». La chronique mensuelle vient de
    la même station et devrait donc s'accorder avec lui.

    Si les deux médianes divergent d'un facteur deux sur la période
    commune, c'est que l'une des deux grandeurs ne décrit pas ce que
    l'on croit — un débit dérivé, un débit réservé, une autre unité. Le
    contrôle ne coûte rien : les deux séries sont déjà en mémoire.
    """
    if not journalier:
        return True, None
    debut = min(m["date"][:7] for m in journalier)
    communs = [v for (a, m, v) in points if f"{a}-{m:02d}" >= debut]
    if len(communs) < 12:
        return True, None
    m1 = mediane(communs)
    m2 = mediane([m["debit"] for m in journalier])
    if not m1 or not m2:
        return True, None
    rapport = max(m1, m2) / min(m1, m2)
    if rapport > 2:
        return False, (f"médiane mensuelle {m1:.2f} m³/s contre {m2:.2f} en "
                       f"journalier sur la même période — les deux grandeurs "
                       f"ne décrivent pas la même chose")
    return True, None


def chroniques_debit(stations, mensuelles, journalieres=None):
    """Graphiques de débit du territoire, et le journal de ce qui a été écarté.

    Une seule station porte les graphiques : celle dont la série
    qualifiée est la plus longue. En publier plusieurs multiplierait
    les courbes sans ajouter de sens — le visiteur n'a pas à arbitrer
    entre deux stations dont il ignore tout.
    """
    journal, candidates = [], []
    for st in stations:
        points = mensuelles.get(st["code"]) or []
        if not points:
            continue
        bon, motif = homogene(points)
        if not bon:
            journal.append((st, motif))
            continue
        bon, motif = accord_avec_le_journalier(
            points, (journalieres or {}).get(st["code"]))
        if not bon:
            journal.append((st, motif))
            continue
        candidates.append((st, points))

    if not candidates:
        return [], journal

    st, points = max(candidates, key=lambda x: len(x[1]))
    valeurs, depart = serie_continue(points)
    # Le libellé du producteur est le bon : « La Bourne à
    # Saint-Just-de-Claix ». Le reconstruire à partir du nom de commune
    # donnerait « Saint-Just-De-Claix », les particules prenant la
    # majuscule. On se contente d'en retirer la précision technique
    # entre crochets, qui ne dit rien au visiteur.
    nom = re.sub(r"\s*\[[^\]]*\]", "", st["nom"]).strip() or st["code"]
    amenage = any(x in st["cours_eau"].lower() for x in COURS_EAU_AMENAGES)
    source = (f"{SOURCE} · station {st['code']} · "
              f"{points[0][0]}-{points[-1][0]}")

    commun = {"rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
              "unite": "m³/s", "decimales": 1,
              "debut": depart, "pas": "mois", "valeurs": valeurs,
              "source": source}
    series = [
        dict(commun, id="debit-saison", forme="saison", rang=10,
             titre=f"Débit mensuel — {nom}, l'année en cours",
             note=("La bande montre tout ce qui a été observé chaque mois "
                   "depuis le début de la chronique. "
                   + (RESERVE_AMENAGE if amenage else ""))),
        dict(commun, id="debit-chronique", forme="courbe", rang=20,
             libelle_serie="Débit moyen mensuel",
             titre=f"Débit mensuel — {nom}, toute la chronique",
             note=("Seuls les mois qualifiés par le producteur sont tracés ; "
                   "les périodes grisées n'en portent aucun. "
                   + (RESERVE_AMENAGE if amenage else ""))),
    ]
    return series, journal


def situer(mesures):
    """Compare le dernier débit aux valeurs habituelles du même mois.

    Un débit brut ne dit rien : dix mètres cubes par seconde sont
    considérables sur un torrent et dérisoires sur l'Isère. Seule la
    comparaison à la même période des années précédentes a un sens.
    """
    if not mesures:
        return None, None
    derniere = mesures[0]
    mois = derniere["date"][5:7]
    historique = [m["debit"] for m in mesures[1:] if m["date"][5:7] == mois]
    if len(historique) < 30:
        return derniere, None

    mediane = statistics.median(historique)
    if not mediane:
        return derniere, None
    rapport = derniere["debit"] / mediane

    if rapport >= 1.5:
        appreciation = ("Nettement au-dessus des valeurs habituelles", None)
    elif rapport >= 1.15:
        appreciation = ("Au-dessus des valeurs habituelles", None)
    elif rapport >= 0.85:
        appreciation = ("Proche des valeurs habituelles", None)
    elif rapport >= 0.5:
        appreciation = ("Sous les valeurs habituelles", "attention")
    else:
        appreciation = ("Nettement sous les valeurs habituelles", "alerte")

    return derniere, {"appreciation": appreciation, "mediane": mediane,
                      "rapport": rapport, "effectif": len(historique)}


def synthetiser(stations, mesures_par_station):
    exploitables = [s for s in stations if mesures_par_station.get(s["code"])]
    if not exploitables:
        return None

    def fraicheur(s):
        return mesures_par_station[s["code"]][0]["date"]

    def eloignement(s):
        return s.get("distance") if s.get("distance") is not None else 999

    def densite(s):
        return len(mesures_par_station[s["code"]])

    limite = (date.today() - timedelta(days=FRAICHEUR_JOURS)).isoformat()
    recentes = [s for s in exploitables if fraicheur(s) >= limite]
    candidates = recentes or exploitables
    proches = [s for s in candidates if eloignement(s) <= SEUIL_ELOIGNEMENT]
    # À distance égale — deux stations au même endroit — la mieux
    # fournie l'emporte : c'est le seul signal disponible pour
    # distinguer la station de référence du dispositif d'un exploitant.
    reference = min(proches or candidates,
                    key=lambda s: (eloignement(s), -densite(s)))

    derniere, situation = situer(mesures_par_station[reference["code"]])
    valeur, unite = debit_lisible(derniere["debit"]) if derniere else (None, "")

    mesures = {
        "EAU-30": mesure(
            situation["appreciation"][0] if situation else "Non comparable",
            "", "Débit des cours d'eau",
            mise_en_avant=True, ancre=ANCRE, rang=10,
            explication=("Comparaison du dernier débit journalier aux "
                         "valeurs relevées le même mois les années "
                         "précédentes, sur la station de référence."),
            **({"ton": situation["appreciation"][1]}
               if situation and situation["appreciation"][1] else {})),
    }
    if valeur is not None:
        mesures["EAU-31"] = mesure(
            valeur, unite, "Débit mesuré", rang=20,
            repere=(f"{reference['cours_eau'] or reference['nom']} · "
                    f"{_date_fr(derniere['date'])}"
                    + (f" · à {reference['distance']:.0f} km"
                       if reference.get("distance") is not None else "")),
            explication=("Débit moyen du jour, exprimé en volume d'eau "
                         "passant chaque seconde."))
    mesures["EAU-32"] = mesure(
        len(exploitables), "station" if len(exploitables) == 1 else "stations",
        "Stations hydrométriques suivies", ancre=ANCRE, rang=30,
        repere=", ".join(sorted({s["cours_eau"] for s in exploitables
                                 if s["cours_eau"]})) or None)
    if mesures["EAU-32"].get("repere") is None:
        mesures["EAU-32"].pop("repere")

    # Si un affluent est nettement plus bas que la station de référence,
    # le signaler : c'est lui qui traduit la sécheresse locale.
    plus_bas = None
    for s in exploitables:
        if s["site"] == reference["site"]:
            continue
        _, sit = situer(mesures_par_station[s["code"]])
        if sit and sit["rapport"] < 0.6:
            if plus_bas is None or sit["rapport"] < plus_bas[1]["rapport"]:
                plus_bas = (s, sit)
    if plus_bas and (not situation or situation["rapport"] >= 0.85):
        mesures["EAU-33"] = mesure(
            f"{plus_bas[0]['cours_eau'] or plus_bas[0]['nom']}", "",
            "Affluent le plus bas", rang=25, ancre=ANCRE, ton="attention",
            repere=f"à {plus_bas[1]['rapport'] * 100:.0f} % de son débit "
                   f"habituel de saison",
            explication=("Un affluent nettement plus bas que le cours d'eau "
                         "principal traduit une sécheresse locale que le "
                         "grand cours d'eau, soutenu par la montagne et les "
                         "barrages, ne laisse pas voir."))

    items = []
    for s in sorted(exploitables, key=fraicheur, reverse=True):
        lot = mesures_par_station[s["code"]]
        dern, sit = situer(lot)
        v, u = debit_lisible(dern["debit"])
        details = {}
        if s["cours_eau"]:
            details["Cours d'eau"] = s["cours_eau"]
        if s["commune"]:
            details["Commune"] = s["commune"]
        if s.get("distance") is not None:
            details["Distance du centre du territoire"] = \
                f"{s['distance']:.0f} km"
        details["Débit"] = f"{v} {u}"
        details["Dernière mesure"] = _date_fr(dern["date"])
        details["Mesures sur 5 ans"] = len(lot)

        item = {"titre": s["nom"], "details": details}
        if sit:
            item["etat"] = [sit["appreciation"][0],
                            sit["appreciation"][1] or "neutre"]
            mv, mu = debit_lisible(sit["mediane"])
            item["texte"] = (
                f"Médiane des mois comparables : {mv} {mu} "
                f"sur {sit['effectif']} relevés. "
                f"Débit actuel à {sit['rapport'] * 100:.0f} % de cette valeur.")
        if s["site"] == reference["site"]:
            item["titre"] += " — station de référence"
        items.append(item)

    blocs = [{
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "id": ANCRE,
        "titre": "Stations de mesure des débits",
        "items": items,
        "note": ("Les cours d'eau traversent le territoire sans s'arrêter à "
                 "ses limites : ces mesures valent pour l'ensemble, pas pour "
                 "une commune en particulier. Un débit ne s'interprète que "
                 "par rapport aux valeurs habituelles de la même saison. "
                 "Un grand cours d'eau alimenté par la montagne et régulé "
                 "par des barrages peut afficher un débit normal alors que "
                 "des restrictions sécheresse sont en vigueur : ce sont les "
                 "petits affluents qui traduisent le mieux la situation "
                 "locale."
                 + (" La station de référence est éloignée du territoire : "
                    "son débit n'en est qu'une indication approchée."
                    if (reference.get("distance") or 0) > SEUIL_ELOIGNEMENT
                    else "")),
    }]

    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def inspecter(boite):
    print("\nInspection — hydrométrie")
    print("─" * 60)
    print(f"  Emprise interrogée : {boite}")

    sites = appeler("referentiel/sites",
                    bbox=",".join(str(v) for v in boite), size=5, format="json")
    if not sites:
        print("\n  Aucun site trouvé sur cette emprise.")
        print("  Le point d'entrée referentiel/sites répond-il ?\n")
        return

    print(f"\n  {len(sites)} site(s), champs du premier :")
    for cle, valeur in sites[0].items():
        print(f"    {cle:<36} {str(valeur)[:52]}")

    code = champ(sites[0], "code_site")
    if not code:
        print()
        return

    depuis = (date.today() - timedelta(days=120)).isoformat()
    print(f"\n  Observations élaborées du site {code} :")
    for grandeur in GRANDEURS:
        for libelle, params in (
            ("avec date", {"code_entite": code,
                           "grandeur_hydro_elab": grandeur,
                           "date_debut_obs_elab": depuis, "size": 5}),
            ("sans date", {"code_entite": code,
                           "grandeur_hydro_elab": grandeur, "size": 5}),
        ):
            obs = appeler("obs_elab", silencieux=True, **params)
            etat = ("aucune donnée" if obs == [] else
                    "refusé" if obs is None else f"{len(obs)} enregistrement(s)")
            print(f"    {grandeur:<6} {libelle:<12} {etat}")
            if obs:
                print("\n    Champs du premier :")
                for cle, valeur in obs[0].items():
                    print(f"      {cle:<34} {str(valeur)[:50]}")
                print()
                return
            time.sleep(PAUSE)

    # dernier recours : les observations temps réel, par station
    stations = appeler("referentiel/stations",
                       bbox=",".join(str(v) for v in boite), size=3,
                       format="json")
    if stations:
        code_station = champ(stations[0], "code_station")
        print(f"\n  Observations temps réel de la station {code_station} :")
        obs = appeler("observations_tr", silencieux=True,
                      code_entite=code_station, grandeur_hydro="Q", size=3,
                      sort="desc")
        etat = ("aucune donnée" if obs == [] else
                "refusé" if obs is None else f"{len(obs)} enregistrement(s)")
        print(f"    {etat}")
        if obs:
            for cle, valeur in obs[0].items():
                print(f"      {cle:<34} {str(valeur)[:50]}")
    print()


def main():
    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    donnees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    canton = (donnees.get("cantons") or [None])[0]
    code_epci = donnees["perimetre"]["epci"][0]

    boite = emprise(communes)
    if not boite:
        print("\n[ERREUR] Coordonnées absentes du référentiel.\n")
        sys.exit(1)

    if "--inspecter" in sys.argv:
        inspecter(boite)
        return

    print("\nDébit des cours d'eau — Hub'Eau")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")
    print(f"  Emprise : {boite[0]}, {boite[1]} → {boite[2]}, {boite[3]}")

    repere = centre(communes)
    resultat_stations = stations_du_territoire(boite, repere)
    if resultat_stations is None:
        print("\n[BLOCAGE] Impossible d'interroger Hub'Eau.\n")
        sys.exit(1)

    stations, recensees = resultat_stations
    print(f"  Sites hydrométriques recensés : {recensees}")
    if not stations:
        print("\n  Aucune station hydrométrique sur ce territoire.")
        print("  Rien n'a été écrit — c'est un résultat, pas une erreur.\n")
        return

    stations = stations[:STATIONS_MAX]
    mesures_par_station = {}
    for i, st in enumerate(stations, start=1):
        eloigne = (f" ({st['distance']:.0f} km)"
                   if st.get("distance") is not None else "")
        etiquette = (st["cours_eau"] + " — " + st["nom"]
                     if st["cours_eau"] else st["nom"])
        print(f"  [{i:>2}/{len(stations)}] {(etiquette + eloigne)[:46]:<46}",
              end=" ", flush=True)
        lot = chronique(st["code"])
        time.sleep(PAUSE)
        mesures_par_station[st["code"]] = lot
        print(f"{len(lot)} mesure(s)" if lot else "aucune mesure")

    synthese = synthetiser(stations, mesures_par_station)
    if not synthese:
        print("\n  Aucune station exploitable. Rien n'a été écrit.\n")
        return

    # ── série historique ─────────────────────────────────────────
    print("\n  Chroniques mensuelles :")
    mensuelles = {}
    for st in stations:
        points, ecartes = chronique_mensuelle(st["code"])
        time.sleep(PAUSE)
        if points or ecartes:
            mensuelles[st["code"]] = points
            etendue = (f"{points[0][0]}-{points[-1][0]}" if points else "—")
            libelle = (st["cours_eau"] or st["nom"])[:22]
            print(f"    {st['code']:<12} {libelle:<24} {len(points):>4} mois "
                  f"{etendue:<10}"
                  + (f" ({ecartes} non qualifié(s))" if ecartes else ""))

    series, journal = chroniques_debit(stations, mensuelles,
                                       mesures_par_station)
    for st, motif in journal:
        print(f"    [écartée] {st['code']} — {motif}")
    if series:
        synthese["chroniques"] = series
        print(f"    → série retenue : {series[0]['source']}")
    else:
        print("    → aucune série publiable ; les indicateurs restent seuls.")

    territoires = {}
    if canton:
        territoires[f"canton:{canton['code']}"] = synthese
    territoires[f"epci:{code_epci}"] = synthese

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "quotidienne",
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    m = synthese["mesures"]
    print(f"\n  Débit : {m['EAU-30']['valeur']}")
    if "EAU-31" in m:
        print(f"  Mesure : {m['EAU-31']['valeur']} {m['EAU-31']['unite']} "
              f"({m['EAU-31']['repere']})")
    print(f"  Stations exploitables : {m['EAU-32']['valeur']}")
    print(f"  Rattaché au canton et à l'intercommunalité, pas aux communes.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
