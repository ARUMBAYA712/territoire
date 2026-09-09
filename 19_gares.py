"""
19_gares.py — Gares de voyageurs et fréquentation ferroviaire
==============================================================

Publie les gares du territoire, leur fréquentation annuelle depuis
2015, et — pour les communes qui n'en ont pas — la gare la plus proche
avec sa distance.

CE QUE CETTE RUBRIQUE APPORTE
------------------------------
La ligne Valence–Grenoble traverse le territoire, et ses quatre points
d'arrêt ont vu leur fréquentation croître très fortement en dix ans.
Relevé sur la collecte du 9 septembre 2026 :

    Saint-Marcellin              479 187 → 601 317   (+25 %)
    Vinay                        123 108 → 206 591   (+68 %)
    Saint-Hilaire–Saint-Nazaire   57 959 → 110 057   (+90 %)
    Poliénas                      23 765 →  42 133   (+77 %)

Ce n'est publié nulle part à cette échelle, et le creux de 2020 rend la
série immédiatement lisible pour n'importe quel visiteur.

LA LICENCE N'EST PAS CELLE DU RESTE DU SITE
--------------------------------------------
Les deux jeux employés ici sont publiés sous **ODbL**, et non sous
Licence Ouverte 2.0 comme la plupart des sources du portail. L'ODbL
ajoute à l'attribution une obligation de PARTAGE À L'IDENTIQUE : une
base dérivée que l'on republie doit l'être sous la même licence.

Le site publie ses fiches en téléchargement : ces mesures sont donc
bien concernées. C'est pourquoi ce collecteur écrit « ODbL 1.0 » dans
le champ « licence » de chacune de ses mesures, et pourquoi le
générateur, à partir de la version 36, affiche les licences source par
source au lieu d'en annoncer une seule.

DEUX JEUX, ET LEUR JOINTURE
----------------------------
  · « liste-des-gares » (SNCF Réseau) — où sont les gares, et
    lesquelles reçoivent des voyageurs ;
  · « frequentation-gares » (SNCF Voyageurs) — combien de voyageurs
    par an, de 2015 à 2024.

La jointure se fait sur le code UIC, présent des deux côtés sous des
noms différents : « code_uic » d'un côté, « code_uic_complet » de
l'autre. Les deux portent la même valeur à huit chiffres.

TROIS PIÈGES, ET CE QUI LES ATTRAPE
------------------------------------
  · **Le premier jeu contient des doublons.** Moirans, Valence-TGV et
    Gières apparaissent deux fois, avec le même code UIC et des
    coordonnées différentes de quelques dizaines de mètres. Compter les
    lignes donnerait un nombre de gares faux ;
  · **une colonne casse le motif.** Toutes s'appellent
    « total_voyageurs_2015 », « total_voyageurs_2016 »… sauf une :
    « totalvoyageurs2017 », sans les tirets bas. Un collecteur qui
    construirait les noms par formule perdrait 2017 en silence, au
    milieu de la chronique. Le contrôle est explicite plus bas ;
  · **deux totaux cohabitent.** Le jeu donne les voyageurs, et les
    voyageurs PLUS les accompagnants estimés. Pour Saint-Marcellin,
    601 317 contre 751 646, soit 25 % d'écart. On publie le premier, et
    la note le dit.

Produit :
    data/mesures-gares.json   repris par 03_agregation.py

Utilisation :
    python 19_gares.py
    python 19_gares.py --exemple     enregistre la collecte brute
    python 19_gares.py --rejouer F   rejoue une collecte enregistrée
"""

import json
import math
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-gares.json"
EXEMPLE = DONNEES / "cache-gares-exemple.json"

API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets"
JEU_GARES = "liste-des-gares"
JEU_FREQUENTATION = "frequentation-gares"

SOURCE = ("SNCF — gares de voyageurs et fréquentation "
          "(ressources.data.sncf.com)")
LICENCE = "ODbL 1.0"

VERSION = 1
RUBRIQUE = "transports"
SOUS_RUBRIQUE = "train"
ANCRE = "gares"

DELAI = 30
TENTATIVES = 4

# ── Réglages arbitrables ────────────────────────────────────────────

# Départements interrogés. La Drôme est là pour les communes du sud du
# territoire, plus proches de Romans que de Saint-Marcellin.
DEPARTEMENTS = ("ISERE", "DROME")

# Au-delà, on ne nomme pas de gare : à quarante kilomètres, « la gare
# la plus proche » n'est plus une information de proximité.
GARE_PROCHE_MAXIMUM_KM = 40

# Années de la chronique. Écrites une à une, et non déduites d'un
# intervalle : c'est ce qui rend visible le nom de colonne irrégulier
# de 2017, au lieu de le laisser se perdre dans une formule.
ANNEES = (2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024)
COLONNES = {a: (f"total_voyageurs_{a}" if a != 2017 else "totalvoyageurs2017")
            for a in ANNEES}

# En dessous, aucune chronique : trois points ne font pas une évolution.
ANNEES_MINIMUM = 5

# Contrôle de cohérence entre le nom de commune donné par la SNCF et la
# position de la gare. Même principe que pour les stations-service :
# trois fois le rayon du disque de même surface, avec un plancher.
ECART_FACTEUR = 3.0
ECART_PLANCHER_KM = 6.0


# ══════════════════════════════════════════════════════════════════
# OUTILS
# ══════════════════════════════════════════════════════════════════

def normaliser(texte):
    """Nom de commune réduit à sa forme comparable."""
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", str(texte or ""))
        if unicodedata.category(c) != "Mn")
    return "".join(c for c in sans_accent.lower() if c.isalnum())


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2)
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def ecart_tolere(commune):
    surface = float(commune.get("surface_ha") or 0)
    rayon = math.sqrt(surface * 10000 / math.pi) / 1000 if surface > 0 else 0
    return max(ECART_PLANCHER_KM, ECART_FACTEUR * rayon)


PARTICULES = ("de", "du", "des", "le", "la", "les", "l", "d", "en", "sur",
              "sous", "lès", "les", "au", "aux", "et")


def joli_nom(texte):
    """« SAINT-HILAIRE-DU-ROSIER » → « Saint-Hilaire-du-Rosier »."""
    morceaux = []
    for i, mot in enumerate(str(texte or "").replace("_", " ").split("-")):
        petit = mot.strip().lower()
        morceaux.append(petit if i and petit in PARTICULES
                        else petit.capitalize())
    return "-".join(m for m in morceaux if m)


def nombre(valeur):
    """123456 → « 123 456 ». L'espace fine insécable est volontaire."""
    try:
        return f"{int(valeur):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(valeur)


def appeler(jeu, **params):
    """Une requête sur l'API Explore, avec reprise sur erreur passagère."""
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
            print(f"\n  [ERREUR] L'API SNCF a répondu {e.code}")
            if detail:
                print(f"  {detail}")
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if tentative < TENTATIVES:
                time.sleep(attente)
                attente *= 2
                continue
            print(f"\n  [ERREUR] {type(e).__name__} : {e}")
            return None
    return None


# ══════════════════════════════════════════════════════════════════
# COLLECTE
# ══════════════════════════════════════════════════════════════════

def gares_voyageurs():
    """Gares recevant des voyageurs dans les départements interrogés.

    Dédoublonnées par code UIC : le référentiel contient plusieurs
    enregistrements pour une même gare — Moirans, Valence-TGV, Gières —
    avec des coordonnées distantes de quelques dizaines de mètres. Le
    premier enregistrement fait foi ; l'écart est sans conséquence à
    l'échelle où nous travaillons, mais le décompte, lui, serait faux.
    """
    liste = ", ".join(f'"{d}"' for d in DEPARTEMENTS)
    filtre = f'departemen in ({liste}) and voyageurs="O"'
    retenues, doublons = {}, 0
    for depart in range(0, 1000, 100):
        lignes = appeler(JEU_GARES, where=filtre, limit=100, offset=depart,
                         select="code_uic,libelle,commune,departemen,"
                                "code_ligne,x_wgs84,y_wgs84")
        if lignes is None:
            return None, 0
        for g in lignes:
            code = str(g.get("code_uic") or "").strip()
            if not code:
                continue
            if code in retenues:
                doublons += 1
                continue
            if g.get("x_wgs84") is None or g.get("y_wgs84") is None:
                continue
            retenues[code] = {
                "code_uic": code,
                "nom": str(g.get("libelle") or "").strip(),
                "commune_sncf": str(g.get("commune") or "").strip(),
                "departement": str(g.get("departemen") or "").strip(),
                "longitude": float(g["x_wgs84"]),
                "latitude": float(g["y_wgs84"]),
            }
        if len(lignes) < 100:
            break
    return retenues, doublons


def frequentation(codes):
    """Fréquentation annuelle des gares nommées, par code UIC."""
    resultats = {}
    codes = sorted(codes)
    colonnes = ",".join(COLONNES[a] for a in ANNEES)
    for debut in range(0, len(codes), 40):
        tranche = codes[debut:debut + 40]
        liste = ", ".join(f'"{c}"' for c in tranche)
        lignes = appeler(JEU_FREQUENTATION,
                         where=f"code_uic_complet in ({liste})", limit=100,
                         select=f"nom_gare,code_uic_complet,"
                                f"segmentation_marketing,{colonnes}")
        if lignes is None:
            return None
        for f in lignes:
            code = str(f.get("code_uic_complet") or "").strip()
            if code:
                resultats[code] = f
    return resultats


def serie_de(ligne):
    """(valeurs, années couvertes) pour une gare, ou (None, 0).

    Une année manquante devient une lacune — None — et non un zéro :
    zéro voyageur et absence de comptage ne se racontent pas pareil.
    """
    if not ligne:
        return None, 0
    valeurs, connues = [], 0
    for annee in ANNEES:
        brut = ligne.get(COLONNES[annee])
        try:
            valeurs.append(int(brut))
            connues += 1
        except (TypeError, ValueError):
            valeurs.append(None)
    if connues < ANNEES_MINIMUM:
        return None, connues
    return valeurs, connues


def rattacher(gares, par_code, par_nom):
    """Associe chaque gare à une commune du territoire, si elle en est une.

    Le rapprochement se fait sur le NOM de commune donné par la SNCF, et
    il est CONTRÔLÉ par la position : une gare rattachée à une commune
    du territoire mais située très loin de son centre est refusée. C'est
    ce qui protège d'une homonymie — il existe plusieurs Saint-Sauveur
    et plusieurs Saint-Hilaire en France, et rien n'interdit à un
    référentiel d'en confondre deux.
    """
    a_nous, ecartees = {}, []
    for code, g in gares.items():
        commune_code = par_nom.get(normaliser(g["commune_sncf"]))
        if not commune_code:
            continue
        c = par_code[commune_code]
        ecart = distance_km(c["latitude"], c["longitude"],
                            g["latitude"], g["longitude"])
        seuil = ecart_tolere(c)
        if ecart > seuil:
            ecartees.append((g["nom"], c["nom"], ecart, seuil))
            continue
        g["code_commune"] = commune_code
        a_nous.setdefault(commune_code, []).append(g)
    return a_nous, ecartees


# ══════════════════════════════════════════════════════════════════
# MISE EN FORME
# ══════════════════════════════════════════════════════════════════

def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def chronique(identifiant, titre, valeurs, note, titre_agrege=None):
    """Une série annuelle de fréquentation.

    « titre_agrege » est le titre que prendra la série une fois sommée
    au canton et à l'intercommunalité. Sans lui, la page du canton
    afficherait « Voyageurs à la gare de Poliénas » au-dessus d'un
    graphique qui additionne quatre gares. Mécanisme livré avec la
    version 5 de 03_agregation.py.
    """
    return {
        "id": identifiant,
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "forme": "barres",
        "titre": titre,
        "source": SOURCE,
        "licence": LICENCE,
        "unite": "voyageurs",
        "decimales": 0,
        "rang": 10,
        "note": note,
        "debut": ANNEES[0],
        "pas": "an",
        "valeurs": valeurs,
        "agregation": "somme",
        "titre_agrege": titre_agrege or "Voyageurs dans les gares du territoire",
        "note_agregee": (NOTE_COMPTAGE + " Cette série additionne toutes les "
                         "gares du territoire."),
    }


NOTE_COMPTAGE = (
    "Comptage annuel des voyageurs publié par SNCF Voyageurs. Les "
    "accompagnants, que la source estime séparément, ne sont pas "
    "comptés ici. Le creux de 2020 correspond aux périodes de "
    "confinement.")


def item_gare(gare, ligne, valeurs, distance=None, commune=None):
    # La SNCF écrit ses communes en capitales : « SAINT-HILAIRE-DU-ROSIER ».
    # Un simple title() rendrait « Saint-Hilaire-Du-Rosier », avec une
    # particule majuscule. Quand la commune est du territoire, son nom
    # propre est déjà dans notre référentiel : c'est lui qui fait foi.
    # Sinon on remet en casse en laissant les particules en bas.
    details = {"Commune": commune or joli_nom(gare["commune_sncf"])}
    if ligne:
        recente = next((valeurs[i] for i in range(len(ANNEES) - 1, -1, -1)
                        if valeurs and valeurs[i] is not None), None)
        if recente is not None:
            details[f"Voyageurs en {ANNEES[-1]}"] = nombre(recente)
        if ligne.get("segmentation_marketing"):
            details["Catégorie"] = str(ligne["segmentation_marketing"])
    if distance is not None:
        details["Distance"] = f"{distance:.0f} km du centre de la commune"

    etat = ["Desservie", "neutre"] if ligne else ["Fréquentation inconnue",
                                                  "attention"]
    return {"titre": gare["nom"], "details": details, "etat": etat,
            "texte": ("Gare ou halte du réseau ferré national. Les horaires "
                      "et l'état du trafic se consultent auprès du "
                      "transporteur.")}


# ══════════════════════════════════════════════════════════════════

def ecrire_vide(motif):
    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION, "source": SOURCE, "licence": LICENCE,
        "frequence": "annuelle", "motif_absence": motif,
        "communes": {}, "territoires": {},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Rien publié — {motif}")
    print(f"  Fichier écrit vide : {SORTIE}\n")


def main():
    print("\nGares de voyageurs et fréquentation — SNCF")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")
    print(f"  licence de la source : {LICENCE}")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    reference = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = reference["communes"]
    par_code = {c["code"]: c for c in communes}
    par_nom = {normaliser(c["nom"]): c["code"] for c in communes}
    cantons = {c.get("code_canton") for c in communes if c.get("code_canton")}
    codes_epci = {c.get("code_epci") for c in communes if c.get("code_epci")}

    rejeu, fichier_rejeu = None, None
    if "--rejouer" in sys.argv:
        i = sys.argv.index("--rejouer")
        if i + 1 >= len(sys.argv):
            print("\n[ERREUR] --rejouer attend un nom de fichier.\n")
            sys.exit(1)
        fichier_rejeu = sys.argv[i + 1]
        rejeu = json.loads(Path(fichier_rejeu).read_text(encoding="utf-8"))

    if rejeu:
        gares = {k: dict(v) for k, v in rejeu["gares"].items()}
        doublons = rejeu.get("doublons", 0)
        freq = rejeu["frequentation"]
        print(f"  collecte rejouée depuis {fichier_rejeu}")
    else:
        gares, doublons = gares_voyageurs()
        if gares is None:
            ecrire_vide("le référentiel des gares n'a pas répondu")
            return
        if not gares:
            ecrire_vide("aucune gare voyageurs dans les départements visés")
            return
        freq = frequentation(gares.keys())
        if freq is None:
            ecrire_vide("le jeu de fréquentation n'a pas répondu")
            return

    print(f"  Gares voyageurs recensées : {len(gares)}"
          + (f"  ({doublons} doublon(s) de code UIC écarté(s))"
             if doublons else ""))
    print(f"  Gares pourvues d'un comptage : {len(freq)}")

    if "--exemple" in sys.argv:
        DONNEES.mkdir(exist_ok=True)
        EXEMPLE.write_text(json.dumps(
            {"gares": gares, "doublons": doublons, "frequentation": freq},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  Collecte enregistrée : {EXEMPLE}")

    # ── contrôle du nom de colonne irrégulier ────────────────────────
    # 2017 s'appelle « totalvoyageurs2017 » et non « total_voyageurs_2017 ».
    # Si la SNCF régularisait un jour ce nom, la colonne deviendrait
    # introuvable et l'année disparaîtrait des chroniques sans un mot.
    # Le contrôle ne coûte rien et rendrait la panne immédiate.
    lues_2017 = sum(1 for f in freq.values()
                    if f.get(COLONNES[2017]) not in (None, ""))
    if freq and not lues_2017:
        print("\n  [ATTENTION] Aucune valeur lue pour 2017.")
        print(f"  La colonne attendue est « {COLONNES[2017]} », dont le nom")
        print("  ne suit pas celui des autres années. Elle a peut-être été")
        print("  régularisée à la source : vérifiez avant de publier une")
        print("  chronique amputée de son année centrale.")

    a_nous, ecartees = rattacher(gares, par_code, par_nom)
    for nom, commune, ecart, seuil in ecartees:
        print(f"    [écartée] {nom} — donnée à {commune} mais à "
              f"{ecart:.0f} km de son centre, pour un seuil de "
              f"{seuil:.0f} km")

    print(f"\n  Gares du territoire : {sum(len(v) for v in a_nous.values())}")
    for code in sorted(a_nous):
        for g in a_nous[code]:
            valeurs, connues = serie_de(freq.get(g["code_uic"]))
            if valeurs:
                debut = next((v for v in valeurs if v is not None), None)
                fin = next((v for v in reversed(valeurs) if v is not None), None)
                evolution = (f" — {nombre(debut)} → {nombre(fin)} voyageurs"
                             if debut and fin else "")
            else:
                evolution = f" — pas de chronique ({connues} année(s) connue(s))"
            print(f"    {g['nom']} ({par_code[code]['nom']}){evolution}")

    if not a_nous:
        ecrire_vide("aucune gare sur le territoire")
        return

    # ── communes ─────────────────────────────────────────────────────
    resultat = {}
    for code, commune in par_code.items():
        siennes = a_nous.get(code, [])
        mesures, blocs, chroniques = {}, [], []

        if siennes:
            principale = siennes[0]
            ligne = freq.get(principale["code_uic"])
            valeurs, _connues = serie_de(ligne)
            recente = next((v for v in reversed(valeurs or []) if v is not None),
                           None)
            mesures["TRA-10"] = mesure(
                principale["nom"], "", "Gare", rang=10, ancre=ANCRE,
                repere=(f"{nombre(recente)} voyageurs en {ANNEES[-1]}"
                        if recente else None),
                explication=("Gare ou halte du réseau ferré national située "
                             "sur la commune."))
            if len(siennes) > 1:
                mesures["TRA-12"] = mesure(
                    str(len(siennes)), "", "Points d'arrêt ferroviaires",
                    rang=20, ancre=ANCRE)
            if valeurs:
                chroniques.append(chronique(
                    "gare-frequentation",
                    f"Voyageurs à la gare de {principale['nom']}",
                    valeurs, NOTE_COMPTAGE))
            blocs.append({
                "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                "id": ANCRE, "titre": "Desserte ferroviaire",
                "items": [item_gare(g, freq.get(g["code_uic"]),
                                    serie_de(freq.get(g["code_uic"]))[0],
                                    commune=commune["nom"])
                          for g in siennes],
                "lien": {"url": "https://ressources.data.sncf.com/",
                         "libelle": "Consulter la source"},
                "note": NOTE_COMPTAGE,
            })
        else:
            proche, km = None, None
            for g in gares.values():
                d = distance_km(commune["latitude"], commune["longitude"],
                                g["latitude"], g["longitude"])
                if km is None or d < km:
                    proche, km = g, d
            if not proche or km > GARE_PROCHE_MAXIMUM_KM:
                continue
            ligne = freq.get(proche["code_uic"])
            valeurs, _c = serie_de(ligne)
            mesures["TRA-11"] = mesure(
                f"{proche['nom']}, à {km:.0f} km", "", "Gare la plus proche",
                rang=15, ancre=ANCRE,
                explication=("Aucune gare sur la commune. La distance est "
                             "mesurée à vol d'oiseau depuis le centre de la "
                             "commune, non par la route."))
            blocs.append({
                "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                "id": ANCRE, "titre": "Gare la plus proche",
                "items": [item_gare(
                    proche, ligne, valeurs, km,
                    commune=(par_code[proche["code_commune"]]["nom"]
                             if proche.get("code_commune") else None))],
                "lien": {"url": "https://ressources.data.sncf.com/",
                         "libelle": "Consulter la source"},
                "note": NOTE_COMPTAGE,
            })

        if mesures:
            entree = {"mesures": mesures, "blocs": blocs}
            if chroniques:
                entree["chroniques"] = chroniques
            resultat[code] = entree

    # ── canton et intercommunalité ───────────────────────────────────
    # La chronique agrégée est laissée à 03_agregation.py : les séries
    # communales déclarent « agregation: somme » et portent les mêmes
    # bornes, il n'y a donc rien à additionner ici. Ce qui suit ne
    # concerne que ce qu'une échelle large sait dire d'elle-même.
    territoires = {}
    for niveau, codes in (("canton", cantons), ("epci", codes_epci)):
        for identifiant in codes:
            if niveau == "canton":
                membres = [c for c in communes
                           if c.get("code_canton") == identifiant]
            else:
                membres = [c for c in communes
                           if c.get("code_epci") == identifiant]
            leurs = [g for c in membres for g in a_nous.get(c["code"], [])]
            if not leurs:
                continue
            total = 0
            for g in leurs:
                valeurs, _c = serie_de(freq.get(g["code_uic"]))
                dernier = next((v for v in reversed(valeurs or [])
                                if v is not None), None)
                total += dernier or 0
            mesures = {
                "TRA-13": mesure(
                    str(len(leurs)), "", "Gares et haltes", rang=10,
                    ancre=ANCRE,
                    repere=(f"{nombre(total)} voyageurs en {ANNEES[-1]}"
                            if total else None),
                    explication=("Points d'arrêt du réseau ferré national "
                                 "situés sur le territoire.")),
            }
            territoires[f"{niveau}:{identifiant}"] = {
                "mesures": mesures,
                "blocs": [{
                    "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                    "id": ANCRE, "titre": "Desserte ferroviaire du territoire",
                    "items": [item_gare(
                        g, freq.get(g["code_uic"]),
                        serie_de(freq.get(g["code_uic"]))[0],
                        commune=par_code[g["code_commune"]]["nom"])
                        for g in sorted(leurs, key=lambda x: x["nom"])],
                    "lien": {"url": "https://ressources.data.sncf.com/",
                             "libelle": "Consulter la source"},
                    "note": NOTE_COMPTAGE,
                }],
            }

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
        "millesime": str(ANNEES[-1]),
        "communes": resultat,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    avec = sum(1 for v in resultat.values() if "TRA-10" in v["mesures"])
    print(f"\n  Communes avec une gare  : {avec}")
    print(f"  Communes servies        : {len(resultat)} sur {len(par_code)}")
    print(f"  Chroniques publiées     : "
          f"{sum(len(v.get('chroniques', [])) for v in resultat.values())}")
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
