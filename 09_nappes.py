"""
09_nappes.py — Niveau des nappes souterraines (Hub'Eau)
========================================================

Récupère les mesures piézométriques des stations situées sur le
territoire, et publie une synthèse **au niveau du canton**.

Pourquoi pas à la commune : une nappe ne s'arrête pas aux limites
administratives, et les stations de mesure sont rares — quelques-unes
pour tout un canton. Afficher un niveau de nappe sur la fiche d'une
commune qui n'a aucune station reviendrait à inventer une précision
qui n'existe pas. La donnée est donc rattachée au canton et à
l'intercommunalité, avec la station de référence nommée explicitement.

Source : API « Niveaux nappes » de Hub'Eau, données BRGM (réseau ADES).

Produit :
    data/mesures-nappes.json   repris par 03_agregation.py

Utilisation :
    python 09_nappes.py
    python 09_nappes.py --tout         recollecte intégrale
    python 09_nappes.py --inspecter    affiche les champs bruts de l'API
"""

import json
import statistics
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-nappes.json"

API = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes"
SOURCE = "Hub'Eau — niveaux des nappes (BRGM, réseau ADES)"
LICENCE = "Licence Ouverte 2.0"

VERSION = 2

RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "nappes"
MARGE = 0.08          # degrés ajoutés autour du territoire pour la recherche
SEUIL_ELOIGNEMENT = 15    # km au-delà desquels la station devient indicative
FRAICHEUR_JOURS = 120     # ancienneté maximale pour servir de référence
STATIONS_MAX = 8          # nombre de stations interrogées, les plus proches
HISTORIQUE = 5        # années de chronique interrogées
DELAI = 120
TENTATIVES = 4
PAUSE = 0.4

ANCRE = "stations-piezometriques"


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
            # une réponse vide signale une absence de donnée, pas une panne
            if statut == 204 or not corps.strip():
                return []
            try:
                return json.loads(corps.decode("utf-8")).get("data", [])
            except json.JSONDecodeError:
                return None
        except urllib.error.HTTPError as e:
            if e.code in (206,):          # réponse partielle : exploitable
                return []
            if e.code == 404:
                return []
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            print(f"\n  [ERREUR] Hub'Eau a répondu {e.code}\n  {url}")
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


def champ(enr, *noms):
    for nom in noms:
        v = enr.get(nom)
        if v not in (None, "", []):
            return v
    return None


def emprise(communes, marge=MARGE):
    """Rectangle englobant le territoire, élargi d'une marge."""
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    if not lons:
        return None
    return (round(min(lons) - marge, 4), round(min(lats) - marge, 4),
            round(max(lons) + marge, 4), round(max(lats) + marge, 4))


def nettoyer_libelle(brut, commune):
    """Rend lisible un libellé de station.

    L'API renvoie des intitulés de terrain :
    « PUITS - FONTCHAUDE (SAINT-BONNET-DE-CHAVAGNE - BRGM 38) - BSH ».
    On retire les mentions techniques entre parenthèses et en suffixe,
    et on rétablit une casse normale.
    """
    texte = str(brut or "").split("(")[0]
    texte = texte.split(" - BSH")[0].strip(" -\t")
    if not texte:
        return f"Station de {commune}" if commune else "Station"
    if texte.isupper():
        texte = texte.title()
    texte = texte.replace(" - ", " de ", 1) if " - " in texte else texte
    if commune and commune.lower() not in texte.lower():
        texte = f"{texte} — {commune.title() if commune.isupper() else commune}"
    return texte


def centre(communes):
    lons = [c["longitude"] for c in communes if c.get("longitude") is not None]
    lats = [c["latitude"] for c in communes if c.get("latitude") is not None]
    if not lons:
        return None
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def distance_km(a, b):
    """Distance approchée entre deux points, suffisante à cette échelle."""
    import math
    lat_moy = math.radians((a[1] + b[1]) / 2)
    dx = (a[0] - b[0]) * 111.32 * math.cos(lat_moy)
    dy = (a[1] - b[1]) * 110.57
    return math.hypot(dx, dy)


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte",
            "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def _date_fr(iso):
    if not iso:
        return "inconnue"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


# ══════════════════════════════════════════════════════════════════

def stations_du_territoire(boite, repere):
    """Stations de l'emprise, écartant celles qui n'ont aucune mesure.

    Le champ nb_mesures_piezo évite d'interroger inutilement des stations
    déclarées mais jamais relevées : l'API en recense plusieurs.
    """
    lot = appeler("stations",
                  bbox=",".join(str(v) for v in boite),
                  size=200)
    if lot is None:
        return None

    stations = []
    for s in lot:
        code = champ(s, "code_bss", "codeBSS")
        if not code:
            continue

        nombre = champ(s, "nb_mesures_piezo") or 0
        try:
            nombre = int(nombre)
        except (TypeError, ValueError):
            nombre = 0

        commune = str(champ(s, "nom_commune", "libelle_commune") or "")
        libelle = champ(s, "libelle_pe")
        nom = (nettoyer_libelle(libelle, commune) if libelle
               else (f"Piézomètre de {commune}" if commune else code))

        nappes = champ(s, "noms_masse_eau_edl", "nom_masse_eau_edl") or []
        if isinstance(nappes, str):
            nappes = [nappes]

        x, y = champ(s, "x"), champ(s, "y")
        eloignement = None
        if repere and x is not None and y is not None:
            eloignement = distance_km(repere, (float(x), float(y)))

        stations.append({
            "code": code,
            "nom": nom,
            "commune": commune,
            "nappe": ", ".join(str(n) for n in nappes if n),
            "mesures_declarees": nombre,
            "fin": str(champ(s, "date_fin_mesure") or "")[:10],
            "distance": eloignement,
        })

    exploitables = [s for s in stations if s["mesures_declarees"] > 0]
    exploitables.sort(key=lambda s: (s["distance"] is None, s["distance"] or 0))
    return exploitables, len(stations)


def chronique(code_bss):
    """Mesures des dernières années pour une station."""
    depuis = (date.today() - timedelta(days=365 * HISTORIQUE)).isoformat()
    lot = appeler("chroniques", code_bss=code_bss,
                  date_debut_mesure=depuis, size=5000, sort="desc")
    if not lot:
        return []
    mesures = []
    for m in lot:
        jour = champ(m, "date_mesure")
        profondeur = champ(m, "profondeur_nappe")
        niveau = champ(m, "niveau_nappe_eau")
        if jour is None:
            continue
        mesures.append({"date": str(jour)[:10],
                        "profondeur": profondeur,
                        "niveau": niveau})
    # Le tri est demandé à l'API, mais le code ne doit pas en dépendre :
    # toute la lecture suppose la mesure la plus récente en tête.
    mesures.sort(key=lambda m: m["date"], reverse=True)
    return mesures


def situer(mesures):
    """Compare la dernière mesure aux valeurs habituelles du même mois.

    Une profondeur brute ne dit rien : trois mètres peuvent être hauts
    ou bas selon la nappe et la saison. La comparaison au même mois des
    années précédentes est la seule lecture honnête à cette échelle.
    """
    if not mesures:
        return None, None
    derniere = mesures[0]
    if derniere.get("profondeur") is None:
        return derniere, None

    mois = derniere["date"][5:7]
    historique = [m["profondeur"] for m in mesures[1:]
                  if m["date"][5:7] == mois and m.get("profondeur") is not None]
    if len(historique) < 4:
        return derniere, None

    mediane = statistics.median(historique)
    ecart = derniere["profondeur"] - mediane      # positif = nappe plus basse
    if ecart <= -0.5:
        appreciation = ("Au-dessus des valeurs habituelles", None)
    elif ecart >= 1.5:
        appreciation = ("Nettement sous les valeurs habituelles", "alerte")
    elif ecart >= 0.5:
        appreciation = ("Sous les valeurs habituelles", "attention")
    else:
        appreciation = ("Proche des valeurs habituelles", None)

    return derniere, {"appreciation": appreciation, "mediane": mediane,
                      "ecart": ecart, "effectif": len(historique)}


def synthetiser(stations, mesures_par_station):
    """Construit les indicateurs de territoire et le bloc des stations."""
    exploitables = [s for s in stations
                    if mesures_par_station.get(s["code"])]
    if not exploitables:
        return None

    def fraicheur(s):
        return mesures_par_station[s["code"]][0]["date"]

    def eloignement(s):
        return s.get("distance") if s.get("distance") is not None else 999

    # Station de référence : la plus proche parmi celles relevées
    # récemment. Privilégier la seule fraîcheur ferait basculer la
    # référence sur une station lointaine au gré des mises à jour ;
    # la proximité donne un repère stable et géographiquement pertinent.
    limite = (date.today() - timedelta(days=FRAICHEUR_JOURS)).isoformat()
    recentes = [s for s in exploitables if fraicheur(s) >= limite]
    candidates = recentes or exploitables
    proches = [s for s in candidates if eloignement(s) <= SEUIL_ELOIGNEMENT]
    reference = min(proches or candidates, key=eloignement)
    derniere, situation = situer(mesures_par_station[reference["code"]])

    mesures = {
        "EAU-20": mesure(
            situation["appreciation"][0] if situation else "Non comparable",
            "", "Niveau des nappes souterraines",
            mise_en_avant=True, ancre=ANCRE, rang=10,
            explication=("Comparaison de la dernière mesure aux valeurs "
                         "relevées le même mois les années précédentes, "
                         "sur la station de référence du territoire."),
            **({"ton": situation["appreciation"][1]}
               if situation and situation["appreciation"][1] else {})),
        "EAU-21": mesure(len(exploitables),
                         "station" if len(exploitables) == 1 else "stations",
                         "Stations piézométriques suivies", ancre=ANCRE, rang=30),
    }

    if derniere and derniere.get("profondeur") is not None:
        mesures["EAU-22"] = mesure(
            round(float(derniere["profondeur"]), 2), "m",
            "Profondeur de la nappe", rang=20,
            repere=(f"Mesure du {_date_fr(derniere['date'])} · "
                    f"{reference['nom']}"
                    + (f" · à {reference['distance']:.0f} km"
                       if reference.get("distance") is not None else "")),
            explication=("Distance entre le sol et la surface de la nappe. "
                         "Plus la valeur est élevée, plus la nappe est basse."))

    items = []
    for s in sorted(exploitables, key=fraicheur, reverse=True):
        lot = mesures_par_station[s["code"]]
        dern, sit = situer(lot)
        details = {"Code BSS": s["code"]}
        if s["commune"]:
            details["Commune"] = s["commune"]
        if s.get("distance") is not None:
            details["Distance du centre du territoire"] = \
                f"{s['distance']:.0f} km"
        if s.get("nappe"):
            details["Masse d'eau"] = s["nappe"]
        if dern.get("profondeur") is not None:
            details["Profondeur"] = f"{float(dern['profondeur']):.2f} m"
        if dern.get("niveau") is not None:
            details["Altitude de la nappe"] = f"{float(dern['niveau']):.2f} m NGF"
        details["Dernière mesure"] = _date_fr(dern["date"])
        details["Mesures sur 5 ans"] = len(lot)

        item = {"titre": s["nom"], "details": details}
        if sit:
            item["etat"] = [sit["appreciation"][0],
                            sit["appreciation"][1] or "neutre"]
            item["texte"] = (
                f"Médiane des mois comparables : {sit['mediane']:.2f} m "
                f"sur {sit['effectif']} relevés. "
                f"Écart : {sit['ecart']:+.2f} m.")
        if s["code"] == reference["code"]:
            item["titre"] += " — station de référence"
        items.append(item)

    blocs = [{
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "id": ANCRE,
        "titre": "Stations de mesure des nappes",
        "items": items,
        "note": ("Les nappes ne suivent pas les limites administratives : "
                 "ces mesures valent pour le territoire dans son ensemble, "
                 "pas pour une commune en particulier. Une profondeur "
                 "s'interprète toujours par rapport aux valeurs habituelles "
                 "de la même saison, jamais dans l'absolu."
                 + (" La station de référence est éloignée du territoire : "
                    "son niveau n'en est qu'une indication approchée."
                    if (reference.get("distance") or 0) > SEUIL_ELOIGNEMENT
                    else "")),
    }]

    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def inspecter(boite):
    print("\nInspection — niveaux des nappes")
    print("─" * 46)
    print(f"  Emprise interrogée : {boite}")
    lot = appeler("stations", bbox=",".join(str(v) for v in boite), size=5)
    if not lot:
        print("  Aucune station trouvée sur cette emprise.\n")
        return
    print(f"\n  {len(lot)} station(s), champs de la première :")
    for k, v in list(lot[0].items())[:25]:
        print(f"    {k:<34} {str(v)[:56]}")

    code = lot[0].get("code_bss")
    if code:
        chron = appeler("chroniques", code_bss=code, size=2, sort="desc")
        print(f"\n  Chronique de {code} — champs :")
        if chron:
            for k, v in list(chron[0].items())[:20]:
                print(f"    {k:<34} {str(v)[:56]}")
        else:
            print("    aucune mesure")
    print()


def main():
    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.")
        sys.exit(1)

    donnees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    canton = (donnees.get("cantons") or [None])[0]
    code_epci = donnees["perimetre"]["epci"][0]

    boite = emprise(communes)
    if not boite:
        print("\n[ERREUR] Coordonnées absentes du référentiel.")
        sys.exit(1)

    if "--inspecter" in sys.argv:
        inspecter(boite)
        return

    print("\nNiveau des nappes souterraines — Hub'Eau")
    print("─" * 46)
    print(f"  Emprise : {boite[0]}, {boite[1]} → {boite[2]}, {boite[3]}")

    repere = centre(communes)
    resultat_stations = stations_du_territoire(boite, repere)
    if resultat_stations is None:
        print("\n[BLOCAGE] Impossible d'interroger Hub'Eau.")
        sys.exit(1)

    stations, recensees = resultat_stations
    print(f"  Stations recensées : {recensees}")
    print(f"  Dont pourvues de mesures : {len(stations)}")
    if not stations:
        print("\n  Aucune station piézométrique exploitable sur ce "
              "territoire.")
        print("  Rien n'a été écrit — c'est un résultat, pas une erreur.")
        print("  Vous pouvez élargir MARGE en haut du script pour "
              "chercher plus loin.\n")
        return

    stations = stations[:STATIONS_MAX]
    mesures_par_station = {}
    for i, st in enumerate(stations, start=1):
        eloignement = (f" ({st['distance']:.0f} km)"
                       if st.get("distance") is not None else "")
        print(f"  [{i:>2}/{len(stations)}] "
              f"{(st['nom'] + eloignement)[:40]:<40}", end=" ", flush=True)
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
        "source": SOURCE, "licence": LICENCE, "frequence": "hebdomadaire",
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    m = synthese["mesures"]
    print(f"\n  Niveau : {m['EAU-20']['valeur']}")
    if "EAU-22" in m:
        print(f"  Profondeur : {m['EAU-22']['valeur']} m "
              f"({m['EAU-22']['repere']})")
    print(f"  Stations exploitables : {m['EAU-21']['valeur']}")
    if "EAU-22" in m:
        pass
    print(f"  Rattaché au canton et à l'intercommunalité, pas aux communes.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
