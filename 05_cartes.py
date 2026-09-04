"""
05_cartes.py — Cartes de situation en SVG
==========================================

Produit une carte par territoire, sous forme de SVG sans dépendance :
ni fond de carte externe, ni bibliothèque, ni JavaScript.

Le principe retenu : montrer la commune **en situation** dans son canton,
plutôt qu'un contour isolé. Un contour seul ne dit rien à personne ;
une forme mise en évidence au milieu de ses voisines répond tout de suite
à la question « où est-ce ? ».

    assets/cartes/commune/38416.svg     commune en évidence dans le canton
    assets/cartes/canton/3823.svg       canton entier, communes détourées
    assets/cartes/epci/200070431.svg    idem pour l'intercommunalité

Les couleurs ne sont pas écrites dans les SVG : ils utilisent des classes
reprises par assets/style.css. Le thème reste donc pilotable d'un seul endroit.

Utilisation :
    python 05_cartes.py
"""

import json
import math
import sys
import shutil
import urllib.request
import urllib.error
from pathlib import Path

RACINE = Path(".")
DONNEES = RACINE / "data"
CONTOURS = DONNEES / "contours.json"
SORTIE = RACINE / "assets" / "cartes"

API = "https://geo.api.gouv.fr"

# Tolérance de simplification, en degrés (~0.0002 ≈ 20 m).
# Plus la valeur est élevée, plus les fichiers sont légers et les
# contours anguleux. 0.0003 est un bon compromis à cette échelle.
# Relevé sur les contours réels du Sud Grésivaudan : à 0.0003, chaque
# carte pesait 45 Ko, soit autant ajouté à chacune des 381 pages. À
# 0.0009 le tracé reste fidèle à l'échelle d'affichage, pour un poids
# divisé par trois environ. La commune mise en évidence conserve un
# tracé plus fin, elle seule justifie le détail.
TOLERANCE = 0.0009

TAILLE_TUILE = 256        # pixels, standard des tuiles cartographiques
LARGEUR_CIBLE = 1400      # largeur maximale du dessin, en pixels
HAUTEUR_CIBLE = 1000
MARGE_RELATIVE = 0.06     # respiration autour du territoire
TAILLE_NOM = 12           # taille des noms de communes, en unités du dessin
SURFACE_MINIMALE = 500    # aire minimale pour mériter un nom, en pixels²
SERRAGE = 0.86            # tolérance de chevauchement entre étiquettes


# ══════════════════════════════════════════════════════════════════
# RÉCUPÉRATION DES CONTOURS
# ══════════════════════════════════════════════════════════════════

def telecharger_contours(codes_epci):
    """Récupère les géométries, une seule fois, et les met en cache."""
    if CONTOURS.exists():
        print(f"  Contours déjà en cache : {CONTOURS}")
        return json.loads(CONTOURS.read_text(encoding="utf-8"))

    tout = {}
    for code in codes_epci:
        url = f"{API}/epcis/{code}/communes?fields=nom,code,contour"
        print(f"  Téléchargement des contours de {code}…", end=" ", flush=True)
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0"})
            with urllib.request.urlopen(requete, timeout=120) as reponse:
                lot = json.loads(reponse.read().decode("utf-8"))
        except urllib.error.URLError as e:
            print(f"\n[ERREUR] Impossible de joindre l'API : {e}")
            sys.exit(1)
        for c in lot:
            if c.get("contour"):
                tout[c["code"]] = {"nom": c["nom"], "contour": c["contour"]}
        print(f"{len(lot)} communes")

    DONNEES.mkdir(exist_ok=True)
    CONTOURS.write_text(json.dumps(tout), encoding="utf-8")
    taille = CONTOURS.stat().st_size / 1024
    print(f"  Contours enregistrés ({taille:.0f} Ko)")
    return tout


# ══════════════════════════════════════════════════════════════════
# SIMPLIFICATION ET PROJECTION
# ══════════════════════════════════════════════════════════════════

def simplifier(points, tolerance):
    """Algorithme de Douglas-Peucker, en version itérative.

    La version récursive dépasse la pile d'appels de Python sur un
    contour très découpé — plusieurs milliers de points, ce qui arrive
    en montagne. La pile est donc gérée explicitement.
    """
    if len(points) < 3:
        return points

    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    pile = [(0, len(points) - 1)]

    while pile:
        debut_i, fin_i = pile.pop()
        if fin_i <= debut_i + 1:
            continue
        debut, fin = points[debut_i], points[fin_i]
        dx, dy = fin[0] - debut[0], fin[1] - debut[1]
        longueur = math.hypot(dx, dy)

        ecart_max, indice = 0.0, -1
        for i in range(debut_i + 1, fin_i):
            px, py = points[i]
            if longueur == 0:
                ecart = math.hypot(px - debut[0], py - debut[1])
            else:
                ecart = abs(dy * px - dx * py + fin[0] * debut[1]
                            - fin[1] * debut[0]) / longueur
            if ecart > ecart_max:
                ecart_max, indice = ecart, i

        if indice != -1 and ecart_max > tolerance:
            garder[indice] = True
            pile.append((debut_i, indice))
            pile.append((indice, fin_i))

    return [point for point, g in zip(points, garder) if g]


def anneaux(geometrie):
    """Extrait la liste des anneaux, quel que soit le type de géométrie."""
    t = geometrie.get("type")
    coords = geometrie.get("coordinates", [])
    if t == "Polygon":
        return coords
    if t == "MultiPolygon":
        return [anneau for polygone in coords for anneau in polygone]
    return []


def merca(lon, lat, zoom):
    """Coordonnées en pixels dans la projection Web Mercator.

    C'est la projection des tuiles cartographiques. En l'adoptant, le
    dessin s'aligne exactement sur un fond de plan sans aucun calcul
    côté navigateur.
    """
    n = TAILLE_TUILE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    phi = math.radians(max(-85.05, min(85.05, lat)))
    y = (1.0 - math.log(math.tan(phi) + 1.0 / math.cos(phi)) / math.pi) / 2.0 * n
    return x, y


def choisir_zoom(lon_min, lat_min, lon_max, lat_max):
    """Plus grand niveau de zoom tenant dans la largeur visée."""
    for zoom in range(18, 3, -1):
        x0, y0 = merca(lon_min, lat_max, zoom)
        x1, y1 = merca(lon_max, lat_min, zoom)
        if (x1 - x0) <= LARGEUR_CIBLE and (y1 - y0) <= HAUTEUR_CIBLE:
            return zoom
    return 4


def cadrage(geometries):
    """Emprise, projection et grille de tuiles correspondante."""
    lons = [p[0] for g in geometries for a in anneaux(g) for p in a]
    lats = [p[1] for g in geometries for a in anneaux(g) for p in a]
    if not lons:
        return None

    marge_lon = (max(lons) - min(lons)) * MARGE_RELATIVE
    marge_lat = (max(lats) - min(lats)) * MARGE_RELATIVE
    lon_min, lon_max = min(lons) - marge_lon, max(lons) + marge_lon
    lat_min, lat_max = min(lats) - marge_lat, max(lats) + marge_lat

    zoom = choisir_zoom(lon_min, lat_min, lon_max, lat_max)
    x0, y0 = merca(lon_min, lat_max, zoom)
    x1, y1 = merca(lon_max, lat_min, zoom)
    largeur, hauteur = max(x1 - x0, 1.0), max(y1 - y0, 1.0)

    def projeter(point):
        x, y = merca(point[0], point[1], zoom)
        return (round(x - x0, 1), round(y - y0, 1))

    # tuiles couvrant l'emprise, repérées en pourcentage du cadre pour
    # que le fond se redimensionne avec lui, sans JavaScript
    tuiles = []
    for tx in range(int(x0 // TAILLE_TUILE), int(x1 // TAILLE_TUILE) + 1):
        for ty in range(int(y0 // TAILLE_TUILE), int(y1 // TAILLE_TUILE) + 1):
            tuiles.append({
                "x": tx, "y": ty,
                "gauche": round((tx * TAILLE_TUILE - x0) / largeur * 100, 4),
                "haut": round((ty * TAILLE_TUILE - y0) / hauteur * 100, 4),
                "l": round(TAILLE_TUILE / largeur * 100, 4),
                "h": round(TAILLE_TUILE / hauteur * 100, 4),
            })

    return projeter, {"zoom": zoom,
                      "largeur": round(largeur),
                      "hauteur": round(hauteur),
                      "tuiles": tuiles}


def aire(points):
    """Aire algébrique d'un anneau (formule des lacets)."""
    total = 0.0
    for i in range(len(points) - 1):
        total += points[i][0] * points[i + 1][1] - points[i + 1][0] * points[i][1]
    return total / 2.0


def dedans(point, anneau):
    """Le point est-il à l'intérieur de l'anneau ?"""
    x, y = point
    interieur = False
    for i in range(len(anneau) - 1):
        x1, y1 = anneau[i]
        x2, y2 = anneau[i + 1]
        if (y1 > y) != (y2 > y):
            coupe = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < coupe:
                interieur = not interieur
    return interieur


def centre_visuel(anneau):
    """Point d'ancrage du nom, garanti à l'intérieur de la forme.

    Le centre de gravité suffit pour une forme compacte, mais tombe
    hors du territoire pour une commune en croissant — fréquent dans
    les vallées. Dans ce cas on retient le milieu du plus long segment
    horizontal intérieur, qui reste toujours dans la forme.
    """
    a = aire(anneau)
    if abs(a) > 1e-9:
        cx = sum((anneau[i][0] + anneau[i + 1][0]) *
                 (anneau[i][0] * anneau[i + 1][1] - anneau[i + 1][0] * anneau[i][1])
                 for i in range(len(anneau) - 1)) / (6 * a)
        cy = sum((anneau[i][1] + anneau[i + 1][1]) *
                 (anneau[i][0] * anneau[i + 1][1] - anneau[i + 1][0] * anneau[i][1])
                 for i in range(len(anneau) - 1)) / (6 * a)
        if dedans((cx, cy), anneau):
            return cx, cy
    else:
        cy = sum(p[1] for p in anneau) / len(anneau)
        cx = sum(p[0] for p in anneau) / len(anneau)

    # repli : plus long segment horizontal intérieur, à hauteur du centre
    coupes = []
    for i in range(len(anneau) - 1):
        x1, y1 = anneau[i]
        x2, y2 = anneau[i + 1]
        if (y1 > cy) != (y2 > cy):
            coupes.append(x1 + (cy - y1) / (y2 - y1) * (x2 - x1))
    coupes.sort()
    meilleur, largeur = (cx, cy), -1
    for i in range(0, len(coupes) - 1, 2):
        if coupes[i + 1] - coupes[i] > largeur:
            largeur = coupes[i + 1] - coupes[i]
            meilleur = ((coupes[i] + coupes[i + 1]) / 2, cy)
    return meilleur


def tracer(geometrie, projeter, tolerance):
    """Convertit une géométrie en attribut « d » de chemin SVG."""
    morceaux = []
    for anneau in anneaux(geometrie):
        points = simplifier(anneau, tolerance)
        if len(points) < 3:
            continue
        projetes = [projeter(p) for p in points]
        segments = " ".join(f"{x},{y}" for x, y in projetes[1:])
        morceaux.append(f"M{projetes[0][0]},{projetes[0][1]} L{segments} Z")
    return " ".join(morceaux)


# ══════════════════════════════════════════════════════════════════
# PRODUCTION DES SVG
# ══════════════════════════════════════════════════════════════════

def echapper(texte):
    return (texte.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def etiquettes(contours, codes, code_evidence, projeter, grille):
    """Place les noms de communes en évitant les chevauchements.

    Les plus grandes formes sont servies en premier — un nom placé sur
    un grand territoire gêne moins qu'un nom flottant sur un hameau.
    La commune mise en évidence est prioritaire dans tous les cas.
    """
    echelle = grille["largeur"] / 700.0
    taille = round(TAILLE_NOM * echelle, 1)
    hauteur_boite = taille * 1.2

    candidats = []
    for code in codes:
        if code not in contours:
            continue
        anneaux_px = []
        for anneau in anneaux(contours[code]["contour"]):
            if len(anneau) < 4:
                continue
            anneaux_px.append([projeter(p) for p in anneau])
        if not anneaux_px:
            continue
        principal = max(anneaux_px, key=lambda a: abs(aire(a)))
        surface = abs(aire(principal))
        if surface < SURFACE_MINIMALE * echelle * echelle and code != code_evidence:
            continue
        x, y = centre_visuel(principal)
        candidats.append({"code": code, "nom": contours[code]["nom"],
                          "x": x, "y": y, "surface": surface})

    candidats.sort(key=lambda c: (c["code"] != code_evidence, -c["surface"]))

    posees, sorties = [], []
    for c in candidats:
        # Les boîtes sont légèrement resserrées : une étiquette occupe
        # moins de place que son rectangle théorique, et l'estimation
        # large faisait sacrifier des noms qui tenaient en réalité.
        largeur_boite = len(c["nom"]) * taille * 0.5 * SERRAGE
        boite = (c["x"] - largeur_boite / 2, c["y"] - hauteur_boite / 2,
                 c["x"] + largeur_boite / 2, c["y"] + hauteur_boite / 2)
        if boite[0] < -taille or boite[2] > grille["largeur"] + taille:
            continue
        if any(not (boite[2] < a[0] or boite[0] > a[2] or
                    boite[3] < a[1] or boite[1] > a[3]) for a in posees):
            continue
        posees.append(boite)
        classe = "c-nom principal" if c["code"] == code_evidence else "c-nom"
        sorties.append(
            f'<text class="{classe}" x="{c["x"]:.1f}" y="{c["y"]:.1f}" '
            f'font-size="{taille}" text-anchor="middle" '
            f'dominant-baseline="middle">{echapper(c["nom"])}</text>')
    return "".join(sorties), len(sorties), len(candidats)


def carte(contours, codes_fond, code_evidence, titre):
    """Dessine les communes du fond, celle mise en évidence par-dessus.

    Chaque forme porte son nom dans une balise <title> et son code INSEE
    en attribut. Le générateur de pages s'appuie sur ce code pour
    transformer les formes en liens vers les fiches correspondantes.
    """
    geometries = [contours[c]["contour"] for c in codes_fond if c in contours]
    if not geometries:
        return None, None
    resultat = cadrage(geometries)
    if not resultat:
        return None, None
    projeter, grille = resultat

    fond = []
    for code in codes_fond:
        if code not in contours or code == code_evidence:
            continue
        d = tracer(contours[code]["contour"], projeter, TOLERANCE)
        if d:
            nom = echapper(contours[code]["nom"])
            fond.append(f'<path class="c-voisine" data-code="{code}" '
                        f'd="{d}"><title>{nom}</title></path>')

    evidence = ""
    if code_evidence and code_evidence in contours:
        d = tracer(contours[code_evidence]["contour"], projeter, TOLERANCE / 5)
        if d:
            nom = echapper(contours[code_evidence]["nom"])
            evidence = (f'<path class="c-ici" data-code="{code_evidence}" '
                        f'd="{d}"><title>{nom}</title></path>')

    noms, poses, proposes = etiquettes(contours, codes_fond, code_evidence,
                                       projeter, grille)
    grille["noms_poses"] = poses
    grille["noms_proposes"] = proposes

    svg = (f'<svg class="carte" viewBox="0 0 {grille["largeur"]} '
           f'{grille["hauteur"]}" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-label="{titre}" preserveAspectRatio="none">'
           f'<g class="c-formes">{"".join(fond)}{evidence}</g>'
           f'<g class="c-noms">{noms}</g></svg>')
    return svg, grille


def main():
    print("\nGénération des cartes")
    print("─" * 46)

    referentiel = DONNEES / "referentiel-communes.json"
    if not referentiel.exists():
        print(f"\n[ERREUR] {referentiel} introuvable.")
        print("  Lancez d'abord 01_referentiel.py et 02_canton.py")
        sys.exit(1)

    ref = json.loads(referentiel.read_text(encoding="utf-8"))
    communes = ref["communes"]
    codes_epci = ref["perimetre"]["epci"]
    canton = ref["cantons"][0] if ref.get("cantons") else None

    contours = telecharger_contours(codes_epci)

    absents = [c["nom"] for c in communes if c["code"] not in contours]
    if absents:
        print(f"\n[ATTENTION] {len(absents)} commune(s) sans contour : "
              f"{', '.join(absents[:5])}")

    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    for sous in ("commune", "canton", "epci"):
        (SORTIE / sous).mkdir(parents=True)

    du_canton = [c["code"] for c in communes
                 if canton and c["code_canton"] == canton["code"]]
    de_l_epci = [c["code"] for c in communes]

    total, produites = 0, 0

    # Une commune est située dans son canton quand elle en fait partie,
    # dans l'intercommunalité sinon.
    for c in communes:
        fond = du_canton if c["code"] in du_canton else de_l_epci
        svg, grille = carte(contours, fond, c["code"],
                            f"Situation de {c['nom']} dans son territoire")
        if svg:
            chemin = SORTIE / "commune" / f"{c['code']}.svg"
            chemin.write_text(svg, encoding="utf-8")
            chemin.with_suffix(".json").write_text(
                json.dumps(grille), encoding="utf-8")
            total += chemin.stat().st_size
            produites += 1

    if canton:
        svg, grille = carte(contours, du_canton, None,
                            f"Carte du canton {canton['nom']}")
        if svg:
            base = SORTIE / "canton" / canton["code"]
            base.with_suffix(".svg").write_text(svg, encoding="utf-8")
            base.with_suffix(".json").write_text(json.dumps(grille),
                                                 encoding="utf-8")
            produites += 1

    svg, grille = carte(contours, de_l_epci, None,
                        "Carte de l'intercommunalité")
    if svg:
        base = SORTIE / "epci" / codes_epci[0]
        base.with_suffix(".svg").write_text(svg, encoding="utf-8")
        base.with_suffix(".json").write_text(json.dumps(grille),
                                             encoding="utf-8")
        produites += 1

    moyenne = (total / max(1, len(communes))) / 1024
    print(f"\n  Cartes produites : {produites}")
    if canton:
        grille_canton = json.loads(
            (SORTIE / "canton" / f"{canton['code']}.json").read_text(
                encoding="utf-8"))
        print(f"  Noms sur le canton : {grille_canton['noms_poses']} placés "
              f"sur {grille_canton['noms_proposes']} proposés")
    print(f"  Poids moyen      : {moyenne:.1f} Ko par commune")
    if moyenne > 40:
        print(f"  [attention] Cartes lourdes. Augmentez TOLERANCE "
              f"(actuellement {TOLERANCE}) pour les alléger.")
    print(f"  Dossier          : {SORTIE}\n")


if __name__ == "__main__":
    main()
