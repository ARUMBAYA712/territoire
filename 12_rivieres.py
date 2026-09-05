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
import statistics
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path

VERSION_SCRIPT = 2

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
STATIONS_MAX = 8
HISTORIQUE = 5            # années de chronique interrogées
FRAICHEUR_JOURS = 30      # ancienneté maximale pour servir de référence
DELAI = 120
TENTATIVES = 4
PAUSE = 0.4


# ══════════════════════════════════════════════════════════════════

def appeler(operation, **params):
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

        stations.append({
            "code": code,
            "nom": str(champ(s, "libelle_station") or code),
            "cours_eau": str(champ(s, "libelle_cours_eau",
                                   "libelle_entite_hydrographique") or ""),
            "commune": str(champ(s, "libelle_commune") or ""),
            "distance": eloignement,
        })

    stations.sort(key=lambda s: (s["distance"] is None, s["distance"] or 0))
    return stations, len(lot)


def chronique(code_station):
    """Débits journaliers des dernières années, du plus récent au plus ancien.

    Les observations élaborées fournissent un débit moyen journalier,
    plus représentatif qu'une mesure instantanée pour comparer d'une
    année sur l'autre.
    """
    depuis = (date.today() - timedelta(days=365 * HISTORIQUE)).isoformat()

    # Les paramètres acceptés varient d'une version de l'API à l'autre.
    # Plutôt que d'en supposer un jeu, on essaie les combinaisons par
    # ordre de préférence et on retient la première qui répond.
    tentatives = [
        {"code_entite": code_station, "grandeur_hydro_elab": "QmJ",
         "date_debut_obs_elab": depuis, "size": 5000},
        {"code_entite": code_station, "grandeur_hydro_elab": "QmJ",
         "date_debut_obs_elab": depuis, "size": 2000},
        {"code_entite": code_station, "grandeur_hydro_elab": "QmJ",
         "size": 2000},
        {"code_entite": code_station, "grandeur_hydro_elab": "QmJ"},
    ]
    lot = None
    for params in tentatives:
        lot = appeler("obs_elab", **params)
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

    limite = (date.today() - timedelta(days=FRAICHEUR_JOURS)).isoformat()
    recentes = [s for s in exploitables if fraicheur(s) >= limite]
    candidates = recentes or exploitables
    proches = [s for s in candidates if eloignement(s) <= SEUIL_ELOIGNEMENT]
    reference = min(proches or candidates, key=eloignement)

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
        "Stations hydrométriques suivies", ancre=ANCRE, rang=30)

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
        if s["code"] == reference["code"]:
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
                 "par rapport aux valeurs habituelles de la même saison."
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
    lot = appeler("referentiel/stations",
                  bbox=",".join(str(v) for v in boite), size=5, format="json")
    if not lot:
        print("  Aucune station trouvée sur cette emprise.\n")
        return
    print(f"\n  {len(lot)} station(s), champs de la première :")
    for cle, valeur in lot[0].items():
        print(f"    {cle:<36} {str(valeur)[:52]}")

    code = champ(lot[0], "code_station")
    if not code:
        print()
        return

    depuis = (date.today() - timedelta(days=90)).isoformat()
    variantes = [
        ("date + taille", {"code_entite": code, "grandeur_hydro_elab": "QmJ",
                           "date_debut_obs_elab": depuis, "size": 5}),
        ("taille seule", {"code_entite": code, "grandeur_hydro_elab": "QmJ",
                          "size": 5}),
        ("minimale", {"code_entite": code, "grandeur_hydro_elab": "QmJ"}),
        ("avec tri", {"code_entite": code, "grandeur_hydro_elab": "QmJ",
                      "size": 5, "sort": "desc"}),
    ]
    print(f"\n  Observations de {code} — recherche du bon appel :")
    for libelle, params in variantes:
        obs = appeler("obs_elab", **params)
        etat = ("aucune donnée" if obs == [] else
                "échec" if obs is None else f"{len(obs)} enregistrement(s)")
        print(f"    {libelle:<18} {etat}")
        if obs:
            print(f"\n    Champs du premier :")
            for cle, valeur in obs[0].items():
                print(f"      {cle:<34} {str(valeur)[:50]}")
            break
        time.sleep(PAUSE)
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
    print(f"  Stations recensées : {recensees}, dont {len(stations)} en service")
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
