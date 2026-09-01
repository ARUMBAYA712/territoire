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
TOLERANCE = 0.0003

LARGEUR, HAUTEUR, MARGE = 640, 440, 12


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
    """Algorithme de Douglas-Peucker : retire les points superflus
    sans déformer visiblement le tracé."""
    if len(points) < 3:
        return points

    debut, fin = points[0], points[-1]
    dx, dy = fin[0] - debut[0], fin[1] - debut[1]
    longueur = math.hypot(dx, dy)

    ecart_max, indice = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        if longueur == 0:
            ecart = math.hypot(px - debut[0], py - debut[1])
        else:
            ecart = abs(dy * px - dx * py + fin[0] * debut[1]
                        - fin[1] * debut[0]) / longueur
        if ecart > ecart_max:
            ecart_max, indice = ecart, i

    if ecart_max <= tolerance:
        return [debut, fin]

    gauche = simplifier(points[:indice + 1], tolerance)
    droite = simplifier(points[indice:], tolerance)
    return gauche[:-1] + droite


def anneaux(geometrie):
    """Extrait la liste des anneaux, quel que soit le type de géométrie."""
    t = geometrie.get("type")
    coords = geometrie.get("coordinates", [])
    if t == "Polygon":
        return coords
    if t == "MultiPolygon":
        return [anneau for polygone in coords for anneau in polygone]
    return []


def cadrage(geometries):
    """Calcule l'emprise et la fonction de projection."""
    lons = [p[0] for g in geometries for a in anneaux(g) for p in a]
    lats = [p[1] for g in geometries for a in anneaux(g) for p in a]
    if not lons:
        return None

    lat_moy = (min(lats) + max(lats)) / 2
    k = math.cos(math.radians(lat_moy))   # corrige l'étirement en longitude

    x0, x1 = min(lons) * k, max(lons) * k
    y0, y1 = -max(lats), -min(lats)
    largeur, hauteur = (x1 - x0) or 1e-9, (y1 - y0) or 1e-9

    echelle = min((LARGEUR - 2 * MARGE) / largeur, (HAUTEUR - 2 * MARGE) / hauteur)
    dx = (LARGEUR - largeur * echelle) / 2
    dy = (HAUTEUR - hauteur * echelle) / 2

    def projeter(point):
        return (round((point[0] * k - x0) * echelle + dx, 1),
                round((-point[1] - y0) * echelle + dy, 1))

    return projeter


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

def carte(contours, codes_fond, code_evidence, titre):
    """Dessine les communes du fond, celle mise en évidence par-dessus."""
    geometries = [contours[c]["contour"] for c in codes_fond if c in contours]
    if not geometries:
        return None
    projeter = cadrage(geometries)
    if not projeter:
        return None

    fond = []
    for code in codes_fond:
        if code not in contours or code == code_evidence:
            continue
        d = tracer(contours[code]["contour"], projeter, TOLERANCE)
        if d:
            fond.append(f'<path class="c-voisine" d="{d}"/>')

    evidence = ""
    if code_evidence and code_evidence in contours:
        d = tracer(contours[code_evidence]["contour"], projeter, TOLERANCE / 3)
        if d:
            evidence = f'<path class="c-ici" d="{d}"/>'

    return (f'<svg class="carte" viewBox="0 0 {LARGEUR} {HAUTEUR}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{titre}">'
            f'{"".join(fond)}{evidence}</svg>')


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
        svg = carte(contours, fond, c["code"],
                    f"Situation de {c['nom']} dans son territoire")
        if svg:
            chemin = SORTIE / "commune" / f"{c['code']}.svg"
            chemin.write_text(svg, encoding="utf-8")
            total += chemin.stat().st_size
            produites += 1

    if canton:
        svg = carte(contours, du_canton, None,
                    f"Carte du canton {canton['nom']}")
        if svg:
            (SORTIE / "canton" / f"{canton['code']}.svg").write_text(
                svg, encoding="utf-8")
            produites += 1

    svg = carte(contours, de_l_epci, None, "Carte de l'intercommunalité")
    if svg:
        (SORTIE / "epci" / f"{codes_epci[0]}.svg").write_text(svg, encoding="utf-8")
        produites += 1

    moyenne = (total / max(1, len(communes))) / 1024
    print(f"\n  Cartes produites : {produites}")
    print(f"  Poids moyen      : {moyenne:.1f} Ko par commune")
    if moyenne > 40:
        print(f"  [attention] Cartes lourdes. Augmentez TOLERANCE "
              f"(actuellement {TOLERANCE}) pour les alléger.")
    print(f"  Dossier          : {SORTIE}\n")


if __name__ == "__main__":
    main()
