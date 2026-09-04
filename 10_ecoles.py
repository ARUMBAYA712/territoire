"""
10_ecoles.py — Établissements scolaires (annuaire de l'éducation)
==================================================================

Récupère, commune par commune, les écoles, collèges et lycées recensés
par le ministère de l'Éducation nationale.

Source : annuaire de l'éducation, publié sur data.education.gouv.fr.
API sans clé, du même type que celle des prix des carburants.

Maille : la commune est la maille native. Les effectifs et le nombre
d'établissements remontent au canton et à l'intercommunalité par simple
somme — un établissement appartient à une seule commune, sans ambiguïté.

Produit :
    data/mesures-ecoles.json   repris par 03_agregation.py

Utilisation :
    python 10_ecoles.py                  collecte, avec reprise
    python 10_ecoles.py --tout           recollecte intégrale
    python 10_ecoles.py --habillage      réapplique la présentation seule
    python 10_ecoles.py --inspecter 38416
                                         affiche les champs bruts d'une commune
"""

import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-ecoles.json"

API = ("https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "fr-en-annuaire-education/records")
SOURCE = "Annuaire de l'éducation — ministère de l'Éducation nationale"
LICENCE = "Licence Ouverte 2.0"

VERSION = 5
RUBRIQUE = "education"
SOUS_RUBRIQUE = None
ANCRE = "etablissements-scolaires"

PAUSE = 0.25
DELAI = 60
TENTATIVES = 4
TAILLE_PAGE = 100          # plafond de l'API

RANGS = {"EDU-01": 10, "EDU-02": 20, "EDU-03": 30, "EDU-04": 40}

EXPLICATIONS = {
    "EDU-01": ("Écoles, collèges et lycées en activité, publics et privés "
               "confondus, implantés sur le territoire."),
    "EDU-02": ("Établissements proposant un service de restauration, "
               "d'après l'annuaire de l'éducation."),
    "EDU-03": ("Nombre d'écoles maternelles et élémentaires, premier degré."),
    "EDU-04": ("Collèges et lycées, second degré. Leur absence sur une "
               "commune ne signifie pas que les élèves n'en fréquentent pas : "
               "la sectorisation dépasse les limites communales."),
}


# ══════════════════════════════════════════════════════════════════

def appeler(**params):
    """Interroge l'annuaire. Renvoie une liste, [] si vide, None si échec."""
    url = f"{API}?" + urllib.parse.urlencode(params)
    attente = 2
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
                return json.loads(corps.decode("utf-8")).get("results", [])
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
            print(f"[HTTP {e.code}] ", end="", flush=True)
            return None
        except (urllib.error.URLError, OSError):
            if tentative < TENTATIVES:
                print("[lenteur] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            return None
    return None


def etablissements_de(code_commune):
    """Tous les établissements d'une commune, pagination comprise."""
    tout, depart = [], 0
    while True:
        lot = appeler(where=f'code_commune="{code_commune}"',
                      limit=TAILLE_PAGE, offset=depart)
        if lot is None:
            return None
        tout.extend(lot)
        if len(lot) < TAILLE_PAGE:
            return tout
        depart += TAILLE_PAGE
        if depart >= 1000:          # garde-fou
            return tout
        time.sleep(PAUSE)


def champ(enregistrement, *noms):
    for nom in noms:
        valeur = enregistrement.get(nom)
        if valeur not in (None, "", []):
            return valeur
    return None


def effectif(enregistrement):
    """Nombre d'élèves, quel que soit le nom du champ.

    L'annuaire ne nomme pas ce champ de la même façon selon les
    millésimes. On retient le premier champ dont le nom évoque un
    effectif et dont la valeur est un nombre plausible.
    """
    for cle, valeur in enregistrement.items():
        nom = str(cle).lower()
        if "eleve" not in nom and "élève" not in nom and "effectif" not in nom:
            continue
        n = entier(valeur)
        if n and 0 < n < 20000:
            return n
    return None


def entier(valeur):
    try:
        return int(float(str(valeur).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE}
    if SOUS_RUBRIQUE:
        base["sous_rubrique"] = SOUS_RUBRIQUE
    base.update(habillage)
    return base


def habiller(ident, m):
    m["rubrique"] = RUBRIQUE
    if ident in RANGS:
        m["rang"] = RANGS[ident]
    if ident in EXPLICATIONS:
        m["explication"] = EXPLICATIONS[ident]
    return m


def sans_ancre_orpheline(mesures, blocs):
    presentes = {b.get("id") for b in (blocs or []) if b.get("id")}
    for m in mesures.values():
        if m.get("ancre") and m["ancre"] not in presentes:
            m.pop("ancre")
    return mesures


def pluriel(nombre, singulier, plur=None):
    return singulier if nombre <= 1 else (plur or singulier + "s")


# ══════════════════════════════════════════════════════════════════

PREMIER_DEGRE = ("ecole", "école", "maternelle", "elementaire", "élémentaire",
                 "primaire")
SECOND_DEGRE = ("college", "collège", "lycee", "lycée")


def vrai(valeur):
    """L'annuaire code ses indicateurs en 1 ou 0, parfois en texte."""
    return str(valeur or "").strip().lower() in ("1", "true", "oui")


def degre(etablissement):
    """Premier ou second degré, d'après les indicateurs de l'annuaire.

    Les champs voie_generale, voie_technologique et voie_professionnelle
    ne sont renseignés que pour le second degré ; ecole_maternelle et
    ecole_elementaire pour le premier. C'est plus sûr que d'interpréter
    un libellé de type.
    """
    if any(vrai(etablissement.get(c)) for c in
           ("voie_generale", "voie_technologique", "voie_professionnelle")):
        return "second"
    if any(vrai(etablissement.get(c)) for c in
           ("ecole_maternelle", "ecole_elementaire")):
        return "premier"

    texte = str(champ(etablissement, "libelle_nature",
                      "type_etablissement") or "").lower()
    if any(mot in texte for mot in SECOND_DEGRE):
        return "second"
    if any(mot in texte for mot in PREMIER_DEGRE):
        return "premier"
    return "autre"


def synthetiser(lot):
    """Construit indicateurs et bloc détaillé pour une commune."""
    if lot is None:
        return None

    # L'annuaire conserve les établissements fermés : les publier
    # ferait croire à une offre qui n'existe plus.
    lot = [e for e in (lot or [])
           if str(champ(e, "etat") or "OUVERT").upper().startswith("OUVERT")]
    if not lot:
        return {"mesures": {}, "blocs": []}

    premier = sum(1 for e in lot
                  if degre(e) == "premier")
    second = sum(1 for e in lot
                 if degre(e) == "second")

    restauration = sum(1 for e in lot if vrai(e.get("restauration")))

    mesures = {
        "EDU-01": mesure(len(lot), pluriel(len(lot), "établissement"),
                         "Établissements scolaires",
                         agregation="somme", ancre=ANCRE,
                         unite_pluriel="établissements"),
    }
    if restauration:
        mesures["EDU-02"] = mesure(
            restauration, pluriel(restauration, "établissement"),
            "Restauration scolaire", agregation="somme", ancre=ANCRE,
            unite_pluriel="établissements",
            repere=(f"sur {len(lot)} "
                    f"{pluriel(len(lot), 'établissement')} de la commune"))
    if premier:
        mesures["EDU-03"] = mesure(premier, pluriel(premier, "école"),
                                   "Premier degré", agregation="somme",
                                   unite_pluriel="écoles")
    if second:
        mesures["EDU-04"] = mesure(
            second, pluriel(second, "établissement"), "Second degré",
            agregation="somme", unite_pluriel="établissements")

    # ── bloc détaillé, par degré puis par nom ──
    def rang_degre(e):
        return {"second": 0, "premier": 1, "autre": 2}[
            degre(e)]

    items = []
    for e in sorted(lot, key=lambda x: (rang_degre(x),
                                        str(champ(x, "nom_etablissement") or ""))):
        nom = str(champ(e, "nom_etablissement") or "Établissement")
        details = {}
        type_etab = champ(e, "libelle_nature", "type_etablissement")
        if type_etab:
            details["Type"] = str(type_etab).capitalize()
        statut = champ(e, "statut_public_prive")
        if statut:
            details["Statut"] = str(statut)
        adresse = champ(e, "adresse_1", "adresse_uai")
        if adresse:
            details["Adresse"] = str(adresse)
        telephone = champ(e, "telephone")
        if telephone:
            details["Téléphone"] = str(telephone)

        services = [libelle for cle, libelle in
                    (("restauration", "restauration"),
                     ("hebergement", "internat"),
                     ("ulis", "dispositif ULIS"),
                     ("segpa", "SEGPA"),
                     ("apprentissage", "apprentissage"))
                    if vrai(e.get(cle))]
        if services:
            details["Services"] = ", ".join(services)

        item = {"titre": nom, "details": details}
        site = str(champ(e, "web") or "")
        if site.lower().startswith(("http://", "https://")):
            item["lien"] = {"url": site, "libelle": "Site de l'établissement"}
        items.append(item)

    # Coordonnées de chaque établissement : le générateur en fait des
    # points sur la carte du territoire.
    points = []
    for e in lot:
        lat = champ(e, "latitude")
        lon = champ(e, "longitude")
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        eleves = effectif(e)
        details = str(champ(e, "type_etablissement") or "")
        if eleves:
            details += f" — {eleves} élèves"
        points.append({
            "nom": str(champ(e, "nom_etablissement") or "Établissement"),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "info": details.strip(" —"),
            "categorie": degre(e),
        })

    blocs = [{
        "rubrique": RUBRIQUE,
        "id": ANCRE,
        "titre": "Établissements de la commune",
        "items": items,
        "points": points,
        "note": ("Recensement du ministère de l'Éducation nationale. La "
                 "sectorisation ne suit pas les limites communales : les "
                 "élèves d'une commune sans collège en fréquentent un "
                 "ailleurs. Les effectifs ne sont pas renseignés par tous "
                 "les établissements."),
    }] if items else []

    mesures = {k: habiller(k, v) for k, v in mesures.items()}
    mesures = sans_ancre_orpheline(mesures, blocs)
    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def inspecter(code):
    print(f"\nInspection — annuaire de l'éducation, commune {code}")
    print("─" * 46)
    lot = appeler(where=f'code_commune="{code}"', limit=3)
    if lot is None:
        print("  échec de l'appel\n")
        return
    if not lot:
        print("  aucun établissement recensé\n")
        return
    print(f"  {len(lot)} établissement(s), champs du premier :\n")
    for cle, valeur in lot[0].items():
        print(f"    {cle:<34} {str(valeur)[:56]}")
    print(f"\n  → degré déduit     : "
          f"{degre(lot[0])}")
    print(f"  → coordonnées      : "
          f"{champ(lot[0], 'latitude')}, {champ(lot[0], 'longitude')}")
    print()


def rehabiller(silencieux=False):
    if not SORTIE.exists():
        print(f"\n[ERREUR] {SORTIE} introuvable.")
        sys.exit(1)
    contenu = json.loads(SORTIE.read_text(encoding="utf-8"))
    for bloc in contenu.get("communes", {}).values():
        bloc["mesures"] = {k: habiller(k, v)
                           for k, v in bloc.get("mesures", {}).items()}
        bloc["mesures"] = sans_ancre_orpheline(bloc["mesures"],
                                               bloc.get("blocs"))
    contenu["version"] = VERSION
    SORTIE.write_text(json.dumps(contenu, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    message = (f"  {len(contenu.get('communes', {}))} commune(s) remises "
               f"au format courant.")
    print(message if silencieux
          else f"\nRéhabillage — écoles\n{'─' * 46}\n{message}\n")


def main():
    if "--inspecter" in sys.argv:
        i = sys.argv.index("--inspecter")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez un code INSEE : "
                  "python 10_ecoles.py --inspecter 38416\n")
            sys.exit(1)
        inspecter(sys.argv[i + 1])
        return

    if "--habillage" in sys.argv:
        rehabiller()
        return

    print("\nÉtablissements scolaires — annuaire de l'éducation")
    print("─" * 46)

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.")
        sys.exit(1)

    reprise = "--tout" not in sys.argv
    if reprise and SORTIE.exists():
        precedent = json.loads(SORTIE.read_text(encoding="utf-8"))
        if precedent.get("version") != VERSION:
            print("  Collecte précédente à un format antérieur : "
                  "réhabillage automatique.")
            rehabiller(silencieux=True)

    acquis = {}
    if reprise and SORTIE.exists():
        acquis = json.loads(SORTIE.read_text(encoding="utf-8")).get(
            "communes", {})
        if acquis:
            print(f"  Reprise : {len(acquis)} commune(s) déjà collectée(s).\n")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    resultat = dict(acquis)
    en_erreur, sans_etablissement = [], []

    def sauver():
        DONNEES.mkdir(exist_ok=True)
        SORTIE.write_text(json.dumps({
            "genere_le": date.today().isoformat(),
            "version": VERSION,
            "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
            "communes": resultat,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    for i, c in enumerate(communes, start=1):
        if c["code"] in acquis:
            continue
        print(f"  [{i:>2}/{len(communes)}] {c['nom'][:30]:<30}",
              end=" ", flush=True)

        lot = etablissements_de(c["code"])
        time.sleep(PAUSE)

        synthese = synthetiser(lot)
        if synthese is None:
            en_erreur.append(c["nom"])
            print("échec")
            continue

        resultat[c["code"]] = synthese
        sauver()

        nombre = synthese["mesures"].get("EDU-01", {}).get("valeur", 0)
        if not nombre:
            sans_etablissement.append(c["nom"])
            print("aucun établissement")
        else:
            cantines = synthese["mesures"].get("EDU-02", {}).get("valeur")
            print(f"{nombre} établissement(s)"
                  + (f", dont {cantines} avec restauration" if cantines else ""))

    sauver()

    total_etab = sum(v["mesures"].get("EDU-01", {}).get("valeur", 0)
                     for v in resultat.values())
    total_cantines = sum(v["mesures"].get("EDU-02", {}).get("valeur", 0) or 0
                         for v in resultat.values())
    print(f"\n  Communes renseignées : {len(resultat)}/{len(communes)}")
    print(f"  Établissements       : {total_etab}")
    print(f"  Avec restauration    : {total_cantines}")
    print(f"  Les effectifs d'élèves ne sont pas publiés par cette source.")
    if sans_etablissement:
        print(f"  Sans établissement ({len(sans_etablissement)}) : "
              f"{', '.join(sans_etablissement[:6])}"
              + ("…" if len(sans_etablissement) > 6 else ""))
    if en_erreur:
        print(f"  [attention] En erreur ({len(en_erreur)}) : "
              f"{', '.join(en_erreur[:6])}")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Relancez pour reprendre : "
              "python 10_ecoles.py\n")
        sys.exit(130)
