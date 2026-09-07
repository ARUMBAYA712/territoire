"""
16_bio.py — Agriculture biologique (Agence Bio)
================================================

Publie, par commune, les surfaces engagées en agriculture biologique,
les surfaces en conversion, le nombre d'exploitations et la répartition
par groupe de cultures.

Source : Agence Bio, à partir des contrôles annuels des organismes
certificateurs. Publication annuelle, sans clé.

UNE RÉSERVE MAJEURE, ET ELLE CHANGE LA LECTURE.

Les parcelles d'une même exploitation peuvent être réparties sur
plusieurs communes, mais elles sont TOUTES déclarées dans la commune où
se situe le siège de l'exploitation. Une commune qui héberge le siège
d'un grand domaine affichera donc des surfaces cultivées ailleurs ; sa
voisine, qui porte ces terres, n'affichera rien.

Deux conséquences appliquées ici :

  · aucune part de la surface communale n'est calculée — elle pourrait
    dépasser 100 % et n'aurait aucun sens ;
  · la réserve est écrite sur la fiche, pas seulement dans ce fichier.

À l'échelle du canton, l'agrégation redevient fiable : les sièges et
les parcelles se compensent largement sur un territoire de cette taille.

Produit :
    data/mesures-bio.json   repris par 03_agregation.py

Utilisation :
    python 16_bio.py                collecte
    python 16_bio.py --ressources   liste les fichiers publiés
    python 16_bio.py --colonnes     affiche les colonnes reconnues
    python 16_bio.py --tout         force un nouveau téléchargement
"""

import csv
import io
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-bio.json"
CACHE = DONNEES / "cache-bio.csv"

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
JEU = "surfaces-cheptels-et-nombre-doperateurs-bio-a-la-commune"

SOURCE = "Agence Bio — organismes certificateurs"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "agriculture"
ANCRE = "agriculture-biologique"
DELAI = 180

# Groupes de cultures de la nomenclature Agence Bio.
CULTURES = {
    "SF": "Cultures fourragères et prairies",
    "GCU": "Grandes cultures",
    "FR": "Fruits et arboriculture",
    "LE": "Légumes frais et maraîchage",
    "VI": "Viticulture",
    "PP": "Plantes à parfum, aromatiques et médicinales",
    "AU": "Autres — jachères, engrais verts",
}

MOTIF_CODE = re.compile(r"^(code[_ ]?insee|codgeo|code[_ ]?commune)$", re.I)
MOTIF_ANNEE = re.compile(r"^(annee|année|an)$", re.I)


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


def choisir(ressources):
    """Fichier communal le plus récent, au format tabulaire."""
    candidates = [r for r in ressources
                  if str(r.get("format") or "").lower() in ("csv", "txt")
                  and "commune" in str(r.get("title") or "").lower()]
    if not candidates:
        candidates = [r for r in ressources
                      if str(r.get("format") or "").lower() in ("csv", "txt")]
    if not candidates:
        return None

    def millesime(r):
        annees = re.findall(r"20\d{2}", str(r.get("title") or ""))
        return max((int(a) for a in annees), default=0)

    return max(candidates, key=millesime)


def telecharger(ressource):
    DONNEES.mkdir(exist_ok=True)
    if CACHE.exists() and "--tout" not in sys.argv:
        return CACHE.read_text(encoding="utf-8")
    print("    téléchargement…", end=" ", flush=True)
    try:
        brut = lire(ressource.get("url"), binaire=True)
    except (urllib.error.URLError, OSError) as e:
        print(f"échec : {e}")
        return None
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            texte = brut.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    else:
        texte = brut.decode("utf-8", errors="replace")
    CACHE.write_text(texte, encoding="utf-8")
    print(f"{len(brut) / 1024:.0f} Ko")
    return texte


def lecteur(texte):
    premiere = texte.split("\n", 1)[0]
    separateur = max((";", "\t", ","), key=premiere.count)
    return csv.DictReader(io.StringIO(texte), delimiter=separateur)


def reconnaitre(colonnes):
    """Associe chaque rôle à sa colonne, par motif plutôt que par nom.

    Les intitulés de l'Agence Bio mêlent majuscules et minuscules selon
    les millésimes : SurfBIO, surfbio, SURF_BIO.
    """
    trouve = {"cultures": {}}
    for nom in (colonnes or []):
        propre = str(nom).strip()
        plat = propre.lower().replace("_", "").replace(" ", "")

        if MOTIF_CODE.match(propre) or plat in ("codeinsee", "codgeo"):
            trouve.setdefault("code", propre)
        elif MOTIF_ANNEE.match(propre):
            trouve.setdefault("annee", propre)
        elif plat == "surfbio":
            trouve.setdefault("surface_bio", propre)
        elif plat == "surfab":
            trouve.setdefault("surface_certifiee", propre)
        elif plat in ("surfc123", "surfconv"):
            trouve.setdefault("surface_conversion", propre)
        elif plat in ("nbexp", "nbexploitations", "nbexploitation"):
            trouve.setdefault("exploitations", propre)
        else:
            # colonnes de groupe de culture : SurfBIO_SF, surf_sf, SF…
            for code in CULTURES:
                if plat.endswith(code.lower()) and "surf" in plat:
                    trouve["cultures"].setdefault(code, propre)
    return trouve


def nombre(valeur):
    texte = str(valeur or "").strip().replace(",", ".").replace(" ", "")
    texte = texte.replace("\u00a0", "").replace("\u202f", "")
    if not texte or texte.lower() in ("na", "nd", "-", "s"):
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def hectares(valeur):
    if valeur is None:
        return None
    return round(valeur, 1) if valeur < 100 else round(valeur)


def espacer(n):
    return f"{n:,}".replace(",", "\u202f")


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


RESERVE = (
    "Les surfaces sont rattachées à la commune du siège de "
    "l'exploitation, non à celle où se trouvent les parcelles. Une "
    "commune peut donc afficher des terres cultivées ailleurs, et une "
    "autre ne rien afficher alors qu'elle en porte. À l'échelle du "
    "canton, ces écarts se compensent largement.")


def synthetiser(ligne, colonnes, millesime):
    """Indicateurs et bloc d'une commune."""
    surface = nombre(ligne.get(colonnes.get("surface_bio", ""), ""))
    certifiee = nombre(ligne.get(colonnes.get("surface_certifiee", ""), ""))
    conversion = nombre(ligne.get(colonnes.get("surface_conversion", ""), ""))
    exploitations = nombre(ligne.get(colonnes.get("exploitations", ""), ""))

    if not surface and not exploitations:
        return None

    mesures = {}
    if surface:
        mesures["AGR-01"] = mesure(
            hectares(surface), "ha", "Surface en agriculture biologique",
            rang=10, ancre=ANCRE, agregation="somme",
            explication=("Surfaces certifiées biologiques ou en cours de "
                         "conversion, déclarées par les exploitations dont "
                         "le siège est dans la commune."))
    if exploitations:
        mesures["AGR-02"] = mesure(
            int(exploitations),
            "exploitation" if exploitations == 1 else "exploitations",
            "Exploitations engagées en bio", rang=20, ancre=ANCRE,
            agregation="somme", unite_pluriel="exploitations",
            explication=("Exploitations engagées en agriculture biologique, "
                         "qu'elles disposent ou non de surfaces cultivées."))
    if conversion and surface:
        mesures["AGR-03"] = mesure(
            round(100 * conversion / surface, 1), "%",
            "Part en cours de conversion", obtention="recalculé", rang=30,
            repere=f"{espacer(hectares(conversion))} ha sur "
                   f"{espacer(hectares(surface))}",
            explication=("La conversion dure deux à trois ans selon les "
                         "cultures. Une part élevée signale un mouvement "
                         "récent vers le bio."))

    # ── répartition par groupe de cultures ──
    repartition = []
    for code, libelle in CULTURES.items():
        colonne = colonnes["cultures"].get(code)
        if not colonne:
            continue
        valeur = nombre(ligne.get(colonne, ""))
        if valeur:
            repartition.append((libelle, valeur))
    repartition.sort(key=lambda x: -x[1])

    items = []
    if certifiee or conversion:
        details = {}
        if certifiee:
            details["Certifiée"] = f"{espacer(hectares(certifiee))} ha"
        if conversion:
            details["En conversion"] = f"{espacer(hectares(conversion))} ha"
        items.append({"titre": "Surfaces engagées", "details": details})

    total = sum(v for _, v in repartition)
    for libelle, valeur in repartition:
        items.append({
            "titre": libelle,
            "details": {"Surface": f"{espacer(hectares(valeur))} ha",
                        "Part": f"{100 * valeur / total:.1f} %"} if total
            else {"Surface": f"{espacer(hectares(valeur))} ha"},
        })

    blocs = [{
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "id": ANCRE,
        "titre": (f"Agriculture biologique — {millesime}" if millesime
                  else "Agriculture biologique"),
        "items": items,
        "lien": {"url": "https://www.agencebio.org/",
                 "libelle": "Agence Bio"},
        "note": RESERVE,
    }] if items else []

    if not blocs:
        for m in mesures.values():
            m.pop("ancre", None)

    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def main():
    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    print("\nAgriculture biologique — Agence Bio")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    ressources = ressources_du_jeu()
    if ressources is None:
        sys.exit(1)

    if "--ressources" in sys.argv:
        print(f"\n  {len(ressources)} fichier(s) publié(s) :\n")
        for r in ressources:
            taille = r.get("filesize")
            poids = f"{taille / 1024:.0f} Ko" if taille else "?"
            print(f"    {str(r.get('title'))[:56]:<58} "
                  f"{str(r.get('format')):<6} {poids}")
        print()
        return

    ressource = choisir(ressources)
    if not ressource:
        print("\n[BLOCAGE] Aucun fichier communal trouvé.")
        print("  Lancez --ressources pour voir ce qui est publié.\n")
        sys.exit(1)
    print(f"  Fichier : {str(ressource.get('title'))[:52]}")

    texte = telecharger(ressource)
    if not texte:
        sys.exit(1)

    lecture = lecteur(texte)
    colonnes = reconnaitre(lecture.fieldnames)

    if "--colonnes" in sys.argv:
        print(f"\n  {len(lecture.fieldnames or [])} colonnes\n")
        for role in ("code", "annee", "surface_bio", "surface_certifiee",
                     "surface_conversion", "exploitations"):
            print(f"    {role:<20} {colonnes.get(role) or 'ABSENTE'}")
        print(f"    cultures             "
              f"{len(colonnes['cultures'])} groupe(s)")
        for code, colonne in colonnes["cultures"].items():
            print(f"      {code:<4} {CULTURES[code][:34]:<36} {colonne}")
        if not colonnes.get("code"):
            print(f"\n    [BLOCAGE] colonnes du fichier : "
                  f"{(lecture.fieldnames or [])[:12]}")
        print()
        return

    if not colonnes.get("code"):
        print("\n[BLOCAGE] Colonne de code commune introuvable.")
        print("  Lancez --colonnes pour voir le fichier.\n")
        sys.exit(1)

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    attendues = {c["code"]: c["nom"] for c in communes}

    # Le fichier couvre plusieurs millésimes : on ne retient que le plus
    # récent pour chaque commune.
    retenues, millesime = {}, None
    for ligne in lecture:
        code = str(ligne.get(colonnes["code"], "")).strip().zfill(5)
        if code not in attendues:
            continue
        annee = nombre(ligne.get(colonnes.get("annee", ""), "")) or 0
        if code not in retenues or annee >= retenues[code][0]:
            retenues[code] = (annee, ligne)
        if annee and (millesime is None or annee > millesime):
            millesime = annee

    etiquette = str(int(millesime)) if millesime else None
    resultat = {}
    for code, (_, ligne) in retenues.items():
        synthese = synthetiser(ligne, colonnes, etiquette)
        if synthese:
            resultat[code] = synthese

    if not resultat:
        print("\n[BLOCAGE] Aucune commune renseignée. Rien n'a été écrit.\n")
        sys.exit(1)

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
        "millesime": etiquette,
        "communes": resultat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    surfaces = sum(v["mesures"].get("AGR-01", {}).get("valeur", 0) or 0
                   for v in resultat.values())
    fermes = sum(v["mesures"].get("AGR-02", {}).get("valeur", 0) or 0
                 for v in resultat.values())
    print(f"\n  Millésime            : {etiquette or 'inconnu'}")
    print(f"  Communes renseignées : {len(resultat)}/{len(attendues)}")
    print(f"  Surface bio cumulée  : {espacer(round(surfaces))} ha")
    print(f"  Exploitations        : {fermes}")
    print(f"\n  Rappel : les surfaces sont rattachées au siège de")
    print(f"  l'exploitation, non à l'emplacement des parcelles.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
