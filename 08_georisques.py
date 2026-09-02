"""
08_georisques.py — Risques naturels et technologiques (Géorisques)
===================================================================

Récupère, commune par commune, les risques recensés, les arrêtés de
catastrophe naturelle, le potentiel radon, le zonage sismique et
l'exposition au retrait-gonflement des argiles.

Source : API Géorisques (BRGM / ministère de la Transition écologique).

Toutes ces données sont publiées à la maille communale : aucune
agrégation douteuse ici, contrairement à l'eau potable.

Produit :
    data/mesures-risques.json   repris par 03_agregation.py

Utilisation :
    python 08_georisques.py                collecte, avec reprise
    python 08_georisques.py --tout         recollecte intégrale
    python 08_georisques.py --habillage    réapplique la présentation
    python 08_georisques.py --inspecter 38416
                                           affiche les champs bruts d'une
                                           commune, pour calibrer le script
"""

import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter
from datetime import date
from pathlib import Path

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-risques.json"

API = "https://georisques.gouv.fr/api/v1"
SOURCE = "Géorisques — BRGM et ministère de la Transition écologique"
LICENCE = "Licence Ouverte 2.0"

VERSION = 2

RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "risques"
RANGS = {"ENV-02": 10, "ENV-01": 20, "ENV-06": 30,
         "ENV-05": 40, "ENV-03": 50, "ENV-04": 60}
PAUSE = 0.25
DELAI = 90
TENTATIVES = 4

ANCRE_CATNAT = "catastrophes-naturelles"
ANCRE_RISQUES = "risques-recenses"

# Le potentiel radon est publié en trois catégories réglementaires.
RADON = {
    "1": ("Faible", None),
    "2": ("Faible, avec facteurs géologiques locaux", "attention"),
    "3": ("Significatif", "attention"),
}

# Le zonage sismique va de 1 (très faible) à 5 (fort).
SISMIQUE = {
    "1": ("Très faible", None),
    "2": ("Faible", None),
    "3": ("Modérée", "attention"),
    "4": ("Moyenne", "attention"),
    "5": ("Forte", "alerte"),
}


# ══════════════════════════════════════════════════════════════════
# ACCÈS À L'API
# ══════════════════════════════════════════════════════════════════

def appeler(chemin, **params):
    """Interroge Géorisques. Renvoie une liste, [] si vide, None si échec."""
    url = f"{API}/{chemin}?" + urllib.parse.urlencode(params)
    attente = 2
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0",
                              "Accept": "application/json"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                statut = getattr(reponse, "status", 200)
                corps = reponse.read()

            # Géorisques répond « 204 : pas de contenu » avec un corps vide
            # quand la commune n'a rien sur ce point d'entrée. Ce n'est pas
            # une erreur : c'est une absence de donnée.
            if statut == 204 or not corps.strip():
                return []
            try:
                brut = json.loads(corps.decode("utf-8"))
            except json.JSONDecodeError:
                print("[réponse illisible] ", end="", flush=True)
                return None
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return []
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            return None
        except (urllib.error.URLError, OSError):
            if tentative < TENTATIVES:
                print("[lenteur] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            return None

        if isinstance(brut, list):
            return brut
        if isinstance(brut, dict):
            return brut.get("data") or brut.get("results") or []
        return []
    return None


def champ(enregistrement, *candidats):
    """Première valeur trouvée parmi plusieurs noms de champ possibles.

    Les intitulés de l'API varient d'un point d'entrée à l'autre.
    Chercher plusieurs noms évite de dépendre d'un seul.
    """
    for nom in candidats:
        valeur = enregistrement.get(nom)
        if valeur not in (None, "", []):
            return valeur
    return None


# ══════════════════════════════════════════════════════════════════
# MESURES
# ══════════════════════════════════════════════════════════════════

# Unités des indicateurs de comptage, au singulier et au pluriel.
# Centralisées ici pour que la collecte et le réhabillage accordent
# de la même façon.
UNITES = {
    "ENV-01": ("risque recensé", "risques recensés"),
    "ENV-02": ("arrêté", "arrêtés"),
    "ENV-06": ("document", "documents"),
}


def unite_de(ident, nombre):
    formes = UNITES.get(ident)
    if not formes:
        return ""
    return formes[0] if nombre <= 1 else formes[1]


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "niveaux": ["commune"],
            "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


EXPLICATIONS = {
    "ENV-01": ("Types de risques identifiés par l'État sur le territoire "
               "communal, qu'ils soient naturels ou technologiques."),
    "ENV-02": ("Depuis 1982. Un arrêté ouvre la voie à l'indemnisation des "
               "dommages par les assurances."),
    "ENV-03": ("Le radon est un gaz radioactif naturel issu du sous-sol. "
               "Son accumulation dans les bâtiments mal ventilés présente "
               "un risque pour la santé."),
    "ENV-04": ("Classement réglementaire déterminant les règles de "
               "construction parasismique applicables."),
    "ENV-05": ("Les sols argileux gonflent et se rétractent selon leur "
               "teneur en eau, ce qui peut fissurer les constructions. "
               "Les sécheresses répétées aggravent le phénomène."),
    "ENV-06": ("Documents qui délimitent les zones exposées et fixent les "
               "règles d'urbanisme et de construction qui s'y appliquent."),
}


def habiller(ident, m):
    m["rubrique"] = RUBRIQUE
    m["sous_rubrique"] = SOUS_RUBRIQUE
    if ident in RANGS:
        m["rang"] = RANGS[ident]
    if ident in EXPLICATIONS:
        m["explication"] = EXPLICATIONS[ident]
    valeur = m.get("valeur")
    if ident in UNITES and isinstance(valeur, int):
        m["unite"] = unite_de(ident, valeur)
    return m


def sans_ancre_orpheline(mesures, blocs):
    presentes = {b.get("id") for b in (blocs or []) if b.get("id")}
    for m in mesures.values():
        if m.get("ancre") and m["ancre"] not in presentes:
            m.pop("ancre")
    return mesures


def _annee(valeur):
    texte = str(valeur or "")[:4]
    return texte if texte.isdigit() else None


# ══════════════════════════════════════════════════════════════════

def collecter(commune):
    """Interroge les six points d'entrée pour une commune."""
    code = commune["code"]
    lon, lat = commune.get("longitude"), commune.get("latitude")

    lots = {}
    for cle, chemin, params in (
        ("risques", "gaspar/risques", {"code_insee": code}),
        ("catnat", "gaspar/catnat", {"code_insee": code, "page_size": 200}),
        ("ppr", "gaspar/ppr", {"code_insee": code, "page_size": 100}),
        ("radon", "radon", {"code_insee": code}),
        ("sismique", "zonage_sismique", {"code_insee": code}),
    ):
        lots[cle] = appeler(chemin, **params)
        time.sleep(PAUSE)

    # Le retrait-gonflement des argiles s'interroge par coordonnées.
    if lon is not None and lat is not None:
        lots["rga"] = appeler("rga", latlon=f"{lon:.5f},{lat:.5f}")
        time.sleep(PAUSE)
    else:
        lots["rga"] = []

    return lots


def synthetiser(lots):
    """Construit indicateurs et blocs à partir des réponses de l'API."""
    if lots.get("risques") is None and lots.get("catnat") is None:
        return None

    risques = lots.get("risques") or []
    catnat = lots.get("catnat") or []
    ppr = lots.get("ppr") or []
    radon = lots.get("radon") or []
    sismique = lots.get("sismique") or []
    rga = lots.get("rga") or []

    mesures, blocs = {}, []

    # ── risques recensés ─────────────────────────────────────────
    libelles = []
    for r in risques:
        libelle = champ(r, "libelle_risque_long", "libelle_risque",
                        "num_risque_jo", "libelle")
        if libelle and libelle not in libelles:
            libelles.append(str(libelle))

    mesures["ENV-01"] = mesure(len(libelles),
                               unite_de("ENV-01", len(libelles)),
                               "Risques identifiés sur la commune",
                               ancre=ANCRE_RISQUES)
    if libelles:
        blocs.append({
            "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE,
            "id": ANCRE_RISQUES,
            "titre": "Risques identifiés sur la commune",
            "items": [{"titre": lib, "details": {}} for lib in sorted(libelles)],
            "note": ("Recensement établi par les services de l'État. La "
                     "présence d'un risque ne signifie pas que l'ensemble "
                     "de la commune y est exposé : consultez le document "
                     "d'information communal en mairie."),
        })

    # ── arrêtés de catastrophe naturelle ─────────────────────────
    mesures["ENV-02"] = mesure(len(catnat),
                               unite_de("ENV-02", len(catnat)),
                               "Arrêtés de catastrophe naturelle",
                               ancre=ANCRE_CATNAT)
    if catnat:
        par_type = Counter()
        for a in catnat:
            libelle = champ(a, "libelle_risque_jo", "libelle_risque",
                            "libelle") or "Non précisé"
            par_type[str(libelle)] += 1

        recents = sorted(
            catnat,
            key=lambda a: str(champ(a, "date_debut_evt", "date_publication_arrete",
                                    "date_debut_evenement") or ""),
            reverse=True)[:6]

        items = []
        for libelle, nombre in par_type.most_common():
            annees = sorted({_annee(champ(a, "date_debut_evt",
                                          "date_publication_arrete"))
                             for a in catnat
                             if str(champ(a, "libelle_risque_jo",
                                          "libelle_risque", "libelle")) == libelle}
                            - {None}, reverse=True)
            details = {"Nombre d'arrêtés": nombre}
            if annees:
                details["Années concernées"] = ", ".join(annees[:8]) + (
                    "…" if len(annees) > 8 else "")
            items.append({"titre": libelle, "details": details})

        dernier = recents[0] if recents else None
        derniere_date = _annee(champ(dernier, "date_debut_evt",
                                     "date_publication_arrete")) if dernier else None

        blocs.append({
            "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE,
            "id": ANCRE_CATNAT,
            "titre": "Catastrophes naturelles reconnues depuis 1982",
            "items": items,
            "note": ("Un arrêté de catastrophe naturelle ouvre la voie à "
                     "l'indemnisation des dommages par les assurances. "
                     + (f"Dernier arrêté recensé : {derniere_date}. "
                        if derniere_date else "")
                     + "Les données de l'API peuvent accuser un léger retard "
                       "sur le site Géorisques ; en cas d'écart, ce dernier "
                       "fait référence."),
        })

    # ── potentiel radon ──────────────────────────────────────────
    if radon:
        classe = str(champ(radon[0], "classe_potentiel", "classe_potentiel_radon",
                           "classe", "potentiel") or "")
        libelle, ton = RADON.get(classe, (None, None))
        if libelle:
            mesures["ENV-03"] = mesure(libelle, "", "Potentiel radon",
                                       repere=f"Catégorie {classe} sur 3",
                                       **({"ton": ton} if ton else {}))

    # ── zonage sismique ──────────────────────────────────────────
    if sismique:
        zone = str(champ(sismique[0], "zone_sismicite", "code_zone",
                         "zonage_sismique", "libelle") or "")
        chiffre = "".join(c for c in zone if c.isdigit())[:1]
        libelle, ton = SISMIQUE.get(chiffre, (None, None))
        if libelle:
            mesures["ENV-04"] = mesure(libelle, "", "Sismicité",
                                       repere=f"Zone {chiffre} sur 5",
                                       **({"ton": ton} if ton else {}))

    # ── retrait-gonflement des argiles ───────────────────────────
    if rga:
        niveau = champ(rga[0], "exposition", "alea", "niveau_alea",
                       "codeExposition", "libelle")
        if niveau is not None:
            texte = str(niveau).capitalize()
            ton = "attention" if texte.lower().startswith(("moyen", "fort")) else None
            mesures["ENV-05"] = mesure(texte, "",
                                       "Retrait-gonflement des argiles",
                                       repere="Exposition : nulle, faible, "
                                              "moyenne ou forte",
                                       **({"ton": ton} if ton else {}))

    # ── plans de prévention ──────────────────────────────────────
    if ppr:
        mesures["ENV-06"] = mesure(len(ppr), unite_de("ENV-06", len(ppr)),
                                   "Plans de prévention des risques")

    mesures = {k: habiller(k, v) for k, v in mesures.items()}
    mesures = sans_ancre_orpheline(mesures, blocs)
    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def inspecter(code):
    """Affiche les champs bruts renvoyés pour une commune."""
    print(f"\nInspection de la commune {code}")
    print("─" * 46)
    for cle, chemin, params in (
        ("risques", "gaspar/risques", {"code_insee": code}),
        ("catnat", "gaspar/catnat", {"code_insee": code, "page_size": 3}),
        ("ppr", "gaspar/ppr", {"code_insee": code, "page_size": 3}),
        ("radon", "radon", {"code_insee": code}),
        ("sismique", "zonage_sismique", {"code_insee": code}),
    ):
        lot = appeler(chemin, **params)
        print(f"\n  ── {cle} ──")
        if lot is None:
            print("     échec de l'appel")
        elif not lot:
            print("     aucune donnée")
        else:
            print(f"     {len(lot)} enregistrement(s), champs du premier :")
            for k, v in list(lot[0].items())[:20]:
                apercu = str(v)[:60]
                print(f"       {k:<34} {apercu}")
        time.sleep(PAUSE)
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
    message = f"  {len(contenu.get('communes', {}))} commune(s) remises au format courant."
    print(message if silencieux else f"\nRéhabillage — Géorisques\n{'─' * 46}\n{message}\n")


def main():
    if "--inspecter" in sys.argv:
        i = sys.argv.index("--inspecter")
        if i + 1 >= len(sys.argv):
            print("\n  Précisez un code INSEE : python 08_georisques.py "
                  "--inspecter 38416\n")
            sys.exit(1)
        inspecter(sys.argv[i + 1])
        return

    if "--habillage" in sys.argv:
        rehabiller()
        return

    print("\nRisques naturels et technologiques — Géorisques")
    print("─" * 46)

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.")
        print("  Lancez d'abord 01_referentiel.py et 02_canton.py")
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
        acquis = json.loads(SORTIE.read_text(encoding="utf-8")).get("communes", {})
        if acquis:
            print(f"  Reprise : {len(acquis)} commune(s) déjà collectée(s).\n")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    resultat = dict(acquis)
    en_erreur, sans_donnee = [], []

    def sauver():
        DONNEES.mkdir(exist_ok=True)
        SORTIE.write_text(json.dumps({
            "genere_le": date.today().isoformat(),
            "version": VERSION,
            "source": SOURCE, "licence": LICENCE, "frequence": "trimestrielle",
            "communes": resultat,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    for i, c in enumerate(communes, start=1):
        if c["code"] in acquis:
            continue
        print(f"  [{i:>2}/{len(communes)}] {c['nom'][:30]:<30}", end=" ", flush=True)

        try:
            synthese = synthetiser(collecter(c))
        except Exception as erreur:
            en_erreur.append(f"{c['nom']} ({type(erreur).__name__}: {erreur})")
            print("erreur de traitement")
            continue

        if not synthese:
            sans_donnee.append(c["nom"])
            print("aucune donnée")
            continue

        resultat[c["code"]] = synthese
        sauver()
        m = synthese["mesures"]
        print(f"{m['ENV-01']['valeur']} risque(s), "
              f"{m['ENV-02']['valeur']} arrêté(s) CatNat")

    sauver()

    print(f"\n  Communes renseignées : {len(resultat)}/{len(communes)}")
    if resultat:
        total = sum(v["mesures"]["ENV-02"]["valeur"] for v in resultat.values()
                    if "ENV-02" in v["mesures"])
        print(f"  Arrêtés CatNat cumulés : {total}")
    if sans_donnee:
        print(f"  Sans donnée ({len(sans_donnee)}) : {', '.join(sans_donnee[:6])}")
    if en_erreur:
        print(f"  [attention] En erreur ({len(en_erreur)}) :")
        for ligne in en_erreur[:6]:
            print(f"    · {ligne}")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Relancez pour continuer :  "
              "python 08_georisques.py\n")
        sys.exit(130)
