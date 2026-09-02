"""
06_eau.py — Qualité de l'eau potable (Hub'Eau)
===============================================

Récupère, commune par commune, les réseaux de distribution qui la
desservent et les résultats du contrôle sanitaire.

Source : API « Qualité de l'eau potable » de Hub'Eau, qui diffuse les
données du Ministère chargé de la Santé. Mise à jour mensuelle.

Point important sur la maille : les données sont publiées commune par
commune, mais l'objet réel est l'unité de distribution — le réseau.
Une commune peut être desservie par plusieurs réseaux, et un réseau
alimente plusieurs communes. Les réseaux ne suivent donc ni les cantons
ni les intercommunalités : ces indicateurs restent communaux.

Produit :
    data/mesures-eau.json   repris par 03_agregation.py

Utilisation :
    python 06_eau.py               collecte, en reprenant là où on s'est arrêté
    python 06_eau.py --tout        recollecte intégrale
    python 06_eau.py --habillage   réapplique seulement libellés et repères,
                                   sans aucun appel réseau
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-eau.json"

API = "https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable"
LICENCE = "Licence Ouverte 2.0"
SOURCE = "Hub'Eau — contrôle sanitaire (ministère de la Santé)"

# Les statistiques portent sur 12 mois glissants : deux ans d'historique
# suffisent largement et divisent par trois le volume transféré, principale
# cause des dépassements de délai.
PROFONDEUR_ANNEES = 2
TAILLE_PAGE = 2000         # résultats les plus récents d'abord
PAUSE = 0.4                # respiration entre deux appels
DELAI = 180                # secondes avant abandon d'un appel
TENTATIVES = 5             # essais successifs, avec attente croissante

# Paramètres mis en avant, repérés par leur libellé plutôt que par leur
# code : les libellés sont stables et lisibles dans la réponse.
SUIVIS = [
    ("Nitrates", ["nitrate"], "NO₃"),
    ("Dureté", ["durete", "hydrotimetrique"], "°f"),
    ("pH", ["ph"], ""),
    ("Chlore libre", ["chlore libre"], "mg/L"),
]


# ══════════════════════════════════════════════════════════════════

def appeler(operation, **params):
    """Interroge Hub'Eau, avec nouvelles tentatives en cas de coupure.

    Un dépassement de délai remonte comme OSError, qui n'est pas une
    URLError : il faut donc l'attraper explicitement, sans quoi une
    seule commune lente interrompt les quarante-six autres.
    """
    params.setdefault("size", TAILLE_PAGE)
    url = f"{API}/{operation}?" + urllib.parse.urlencode(params)
    if len(url) > 2000:
        print(f"\n[ERREUR] URL trop longue ({len(url)} caractères).")
        return None

    attente = 3
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                return json.loads(reponse.read().decode("utf-8")).get("data", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}, essai {tentative + 1}/{TENTATIVES} "
                      f"dans {attente}s] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            print(f"\n  [ERREUR] Hub'Eau a répondu {e.code}")
            return None
        except (urllib.error.URLError, OSError) as e:
            if tentative < TENTATIVES:
                print(f"[lenteur, essai {tentative + 1}/{TENTATIVES} "
                      f"dans {attente}s] ", end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            print(f"\n  [ERREUR] Hub'Eau injoignable : {e}")
            return None
    return None


def sans_accents(texte):
    import unicodedata
    t = unicodedata.normalize("NFD", (texte or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def en_liste(valeur):
    """Hub'Eau renvoie certains champs en liste, d'autres en valeur simple.

    Un prélèvement peut être rattaché à plusieurs réseaux : code_reseau
    arrive alors sous forme de tableau. On ramène tout à une liste de
    chaînes pour traiter les deux cas de la même façon.
    """
    if valeur is None:
        return []
    if isinstance(valeur, list):
        return [str(v) for v in valeur if v not in (None, "")]
    return [str(valeur)]


def en_texte(valeur):
    """Première valeur d'un champ éventuellement multiple."""
    liste = en_liste(valeur)
    return liste[0] if liste else ""


ANCRE = "reseaux-eau-potable"

# ══════════════════════════════════════════════════════════════════
# REPÈRES DE LECTURE
#
# Une valeur brute ne dit rien à un visiteur : « 24 °f » n'a de sens
# qu'accompagné de ce qu'est la dureté et de ce qui est habituel.
#
# Attention à la nature des seuils. Une LIMITE de qualité est
# réglementaire et sanitaire ; une RÉFÉRENCE de qualité est un
# indicateur de bon fonctionnement sans effet direct sur la santé ;
# et certains paramètres, comme la dureté, n'ont aucun seuil
# réglementaire. Les confondre induirait le lecteur en erreur.
# ══════════════════════════════════════════════════════════════════

REPERES = {
    "EAU-01": {
        "nom": "Conformité des prélèvements sur 12 mois",
        "explication": ("Part des contrôles sanitaires jugés conformes aux "
                        "limites de qualité réglementaires."),
        "ancre": ANCRE,
    },
    "EAU-02": {
        "nom": "Contrôles sanitaires sur 12 mois",
        "explication": ("Nombre de prélèvements réalisés par l'agence "
                        "régionale de santé. Leur fréquence dépend de la "
                        "taille du réseau."),
    },
    "EAU-03": {
        "nom": "Réseaux desservant la commune",
        "explication": ("Une commune peut être alimentée par plusieurs "
                        "unités de distribution, selon les secteurs."),
        "ancre": ANCRE,
    },
    "EAU-04": {
        "nom": "Nitrates",
        "explication": ("Composé azoté d'origine surtout agricole et "
                        "domestique. Sa présence signale une influence des "
                        "activités humaines sur la ressource."),
        "repere": "Limite de qualité : 50 mg/L",
        "seuil_alerte": 50,
        "seuil_attention": 40,
    },
    "EAU-05": {
        "nom": "Dureté",
        "explication": ("Teneur en calcium et magnésium, exprimée en degrés "
                        "français. Une eau dure entartre les appareils, une "
                        "eau douce est plus agressive pour les canalisations. "
                        "Sans effet sanitaire connu."),
        "repere": ("Aucun seuil réglementaire · douce sous 15 °f, "
                   "moyennement dure de 15 à 30, dure au-delà"),
    },
    "EAU-06": {
        "nom": "pH",
        "explication": ("Mesure l'acidité de l'eau. Une valeur trop basse "
                        "favorise la dissolution des métaux des "
                        "canalisations."),
        "repere": "Référence de qualité : entre 6,5 et 9",
    },
    "EAU-07": {
        "nom": "Chlore libre",
        "explication": ("Résiduel du traitement de désinfection, qui protège "
                        "l'eau jusqu'au robinet. C'est lui que l'on sent "
                        "parfois au goût ou à l'odeur."),
        "repere": ("Aucune limite sanitaire · le goût devient perceptible "
                   "vers 0,3 mg/L"),
    },
    "EAU-08": {
        "nom": "Prélèvements non conformes sur 12 mois",
        "explication": ("Un écart ponctuel est le plus souvent transitoire "
                        "et suivi de mesures correctives par le "
                        "distributeur."),
        "ancre": ANCRE,
    },
}


def habiller(ident, m):
    """Applique à une mesure son libellé et ses repères de lecture."""
    repere = REPERES.get(ident)
    if not repere:
        return m
    m["nom"] = repere["nom"]
    for champ in ("explication", "repere", "ancre"):
        if repere.get(champ):
            m[champ] = repere[champ]

    valeur = m.get("valeur")
    if isinstance(valeur, (int, float)):
        if repere.get("seuil_alerte") and valeur >= repere["seuil_alerte"]:
            m["ton"] = "alerte"
        elif repere.get("seuil_attention") and valeur >= repere["seuil_attention"]:
            m["ton"] = "attention"
    return m


def mesure(valeur, unite, nom, ident_source=SOURCE, obtention="natif",
           **habillage):
    """Indicateur communal.

    « habillage » transporte les consignes d'affichage facultatives —
    ancre vers un bloc détaillé, mise en avant, ton — lues par le
    générateur de pages.
    """
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": obtention, "source": ident_source,
            "licence": LICENCE, "format": "texte",
            "niveaux": ["commune"]}
    base.update(habillage)
    return base


# ══════════════════════════════════════════════════════════════════

def reseaux_de(code_commune):
    """Réseaux desservant la commune, pour l'année la plus récente connue."""
    lignes = appeler("communes_udi", code_commune=code_commune)
    if not lignes:
        return []
    derniere = max(int(l.get("annee") or 0) for l in lignes)
    vus, sortie = set(), []
    for l in lignes:
        if int(l.get("annee") or 0) != derniere:
            continue
        code = en_texte(l.get("code_reseau"))
        if not code or code in vus:
            continue
        vus.add(code)
        sortie.append({
            "code": code,
            "nom": en_texte(l.get("nom_reseau")) or "Réseau sans nom",
            "quartier": en_texte(l.get("nom_quartier")),
            "annee": derniere,
        })
    return sortie


def analyses_de(code_commune, depuis):
    """Résultats d'analyses des dernières années pour la commune."""
    return appeler(
        "resultats_dis",
        code_commune=code_commune,
        date_min_prelevement=depuis,
        sort="desc",
        fields=("code_prelevement,date_prelevement,code_reseau,nom_reseau,"
                "libelle_parametre,resultat_numerique,libelle_unite,"
                "conclusion_conformite_prelevement,"
                "conformite_limites_bact_prelevement,"
                "conformite_limites_pc_prelevement"))


def synthetiser(commune, reseaux, analyses):
    """Construit les indicateurs et le bloc « réseaux » de la commune."""
    if analyses is None:
        return None

    # Un prélèvement porte plusieurs analyses : on regroupe pour compter juste.
    prelevements = {}
    for a in analyses:
        cle = a.get("code_prelevement")
        if not cle:
            continue
        prelevements.setdefault(cle, {
            "date": en_texte(a.get("date_prelevement")),
            "reseaux": en_liste(a.get("code_reseau")),
            "conclusion": en_texte(a.get("conclusion_conformite_prelevement")),
            "bact": en_texte(a.get("conformite_limites_bact_prelevement")),
            "pc": en_texte(a.get("conformite_limites_pc_prelevement")),
            "analyses": [],
        })
        prelevements[cle]["analyses"].append(a)

    if not prelevements:
        return None

    tous = sorted(prelevements.values(), key=lambda p: p["date"] or "",
                  reverse=True)
    dernier = tous[0]

    limite = (date.today() - timedelta(days=365)).isoformat()
    recents = [p for p in tous if (p["date"] or "") >= limite]

    # Le taux ne porte que sur les prélèvements dont la conformité est
    # renseignée. Les indéterminés sont exclus du numérateur ET du
    # dénominateur, plutôt que comptés comme non conformes.
    juges = [p for p in recents if _etat(p)[1] in ("ok", "alerte")]
    conformes = sum(1 for p in juges if _etat(p)[1] == "ok")
    taux = round(100 * conformes / len(juges), 1) if juges else None
    indetermines = len(recents) - len(juges)

    mesures = {
        "EAU-01": mesure(taux, "%", "Conformité des prélèvements sur 12 mois",
                         obtention="recalculé"),
        "EAU-02": mesure(len(recents), "prélèvements",
                         "Contrôles sanitaires sur 12 mois"),
        "EAU-03": mesure(len(reseaux), "réseaux",
                         "Réseaux desservant la commune", ancre=ANCRE),
        "EAU-08": mesure(len(juges) - conformes, "prélèvements",
                         "Prélèvements non conformes sur 12 mois"),
    }

    # paramètres suivis : dernière valeur mesurée
    for i, (nom, motifs, unite_defaut) in enumerate(SUIVIS, start=4):
        trouve = None
        for p in tous:
            for a in p["analyses"]:
                lib = sans_accents(en_texte(a.get("libelle_parametre")))
                if any(m in lib for m in motifs) and a.get("resultat_numerique") is not None:
                    trouve = a
                    break
            if trouve:
                break
        if trouve:
            mesures[f"EAU-{i:02d}"] = mesure(
                round(float(en_texte(trouve["resultat_numerique"])), 2),
                en_texte(trouve.get("libelle_unite")) or unite_defaut, nom)

    # bloc détaillé : un encart par réseau
    par_reseau = defaultdict(list)
    for p in tous:
        for code in p["reseaux"]:
            par_reseau[code].append(p)

    items = []
    for r in reseaux:
        lot = par_reseau.get(r["code"], [])
        recent = lot[0] if lot else None
        details = {"Code réseau": r["code"]}
        if r["quartier"]:
            details["Secteur desservi"] = r["quartier"]
        if recent:
            details["Dernier prélèvement"] = _date_fr(recent["date"])
            details["Analyses réalisées"] = len(recent["analyses"])
            etat = _etat(recent)
            ecarts = [p for p in lot
                      if (p["date"] or "") >= limite
                      and _etat(p)[1] == "alerte"]
            if ecarts:
                details["Non-conformités sur 12 mois"] = ", ".join(
                    f"{_date_fr(p['date'])} ({_dimension(p)})"
                    for p in ecarts[:3])
        else:
            details["Dernier prélèvement"] = "aucun sur la période"
            etat = ("Sans donnée", "neutre")
        items.append({"titre": r["nom"], "etat": etat, "details": details})

    blocs = [{
        "rubrique": "environnement",
        "id": ANCRE,
        "titre": "Réseaux d'eau potable desservant la commune",
        "items": items,
        "note": ("Un réseau de distribution dessert souvent plusieurs communes, "
                 "et une commune peut être alimentée par plusieurs réseaux : "
                 "ces informations ne sont pas transposables au canton ni à "
                 "l'intercommunalité. Une non-conformité ponctuelle est le plus "
                 "souvent transitoire et suivie de mesures correctives ; elle ne "
                 "signifie pas que l'eau est impropre en permanence. Pour toute "
                 "question sanitaire, l'agence régionale de santé et votre "
                 "distributeur d'eau font référence. Dernier contrôle pris en "
                 "compte : " + _date_fr(dernier["date"]) + "."),
    }] if items else []

    mesures = {k: habiller(k, v) for k, v in mesures.items()}

    return {"mesures": mesures, "blocs": blocs,
            "_diagnostic": {"juges": len(juges),
                            "indetermines": indetermines,
                            "non_conformes": len(juges) - conformes}}


def _date_fr(iso):
    if not iso:
        return "inconnue"
    try:
        return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _conforme(valeur):
    """Vrai, faux, ou indéterminé.

    Distinction essentielle : un champ vide ou d'une valeur inattendue
    ne signifie PAS « non conforme ». Annoncer à tort une eau non
    conforme serait la faute la plus grave que ce site puisse commettre.
    Dans le doute, le prélèvement est écarté du calcul.
    """
    v = (valeur or "").strip().upper()
    if not v:
        return None
    if v.startswith("C"):          # C, Conforme, "Conforme aux limites"
        return True
    if v.startswith(("N", "D")):   # N, Non conforme, D(épassement)
        return False
    return None


# Repère la formule qui porte sur les LIMITES ou les EXIGENCES de qualité,
# en capturant la négation qui la précède immédiatement.
FORMULE = re.compile(
    r"(non\s+)?conformes?\s+(?:aux?|a\s+l[a\u2019\']?)\s*"
    r"(limites|exigences)", re.IGNORECASE)


def _lire_conclusion(texte):
    """Interprète la phrase de conclusion sanitaire.

    Piège central : une conclusion peut dire « conforme aux limites de
    qualité mais non conforme aux références de qualité ». Cette eau est
    sanitairement conforme — les références de qualité sont des
    indicateurs de bon fonctionnement (turbidité, fer, coloration) sans
    effet direct sur la santé.

    Chercher « non conforme » dans la phrase entière classerait donc en
    alerte une eau parfaitement potable. On repère la formule qui porte
    explicitement sur les limites ou les exigences, avec la négation qui
    la précède, et on ignore le reste.

    Si la conclusion ne parle que des références, elle ne dit rien du plan
    sanitaire : le prélèvement reste indéterminé plutôt que jugé.
    """
    t = (texte or "").strip().lower().replace("-", " ")
    for accentue, simple in (("é", "e"), ("è", "e"), ("ê", "e")):
        t = t.replace(accentue, simple)
    if not t:
        return None

    trouve = FORMULE.search(t)
    if trouve:
        return trouve.group(1) is None

    if "references" in t:
        return None          # rien sur le plan sanitaire

    if "non conforme" in t:
        return False
    if "conforme" in t:
        return True
    return None


def _etat(prelevement):
    """État sanitaire d'un prélèvement.

    Les champs de conformité aux LIMITES font foi : ils sont codés, donc
    sans ambiguïté. La phrase de conclusion ne sert qu'en dernier recours,
    quand aucun de ces champs n'est renseigné.

    Un prélèvement portant seulement sur la bactériologie n'a pas de
    volet physico-chimique : l'absence de ce second champ ne vaut pas
    non-conformité.
    """
    bact = _conforme(prelevement["bact"])
    pc = _conforme(prelevement["pc"])
    if bact is False or pc is False:
        return ("Non conforme", "alerte")
    if bact is True or pc is True:
        return ("Conforme", "ok")

    lecture = _lire_conclusion(prelevement.get("conclusion"))
    if lecture is True:
        return ("Conforme", "ok")
    if lecture is False:
        return ("Non conforme", "alerte")
    return ("Non renseigné", "neutre")


def _dimension(prelevement):
    """Volet mis en cause par une non-conformité."""
    volets = []
    if _conforme(prelevement["bact"]) is False:
        volets.append("bactériologie")
    if _conforme(prelevement["pc"]) is False:
        volets.append("physico-chimie")
    return " et ".join(volets) or "non précisé"


# ══════════════════════════════════════════════════════════════════

def rehabiller():
    """Réapplique libellés, explications et ancres au fichier existant.

    Utile quand seule la présentation change : aucune interrogation de
    Hub'Eau, donc aucune attente. Les valeurs collectées ne bougent pas.
    """
    if not SORTIE.exists():
        print(f"\n[ERREUR] {SORTIE} introuvable : rien à réhabiller.")
        sys.exit(1)

    contenu = json.loads(SORTIE.read_text(encoding="utf-8"))
    communes = contenu.get("communes", {})
    touchees = 0

    for code, bloc in communes.items():
        bloc["mesures"] = {k: habiller(k, v)
                           for k, v in bloc.get("mesures", {}).items()}
        for b in bloc.get("blocs", []):
            b.setdefault("id", ANCRE)
        touchees += 1

    SORTIE.write_text(json.dumps(contenu, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"\nRéhabillage — Hub'Eau")
    print("─" * 46)
    print(f"  {touchees} commune(s) mises à jour sans nouvel appel réseau.")
    print(f"  Fichier : {SORTIE}\n")


def main():
    if "--habillage" in sys.argv:
        rehabiller()
        return

    print("\nQualité de l'eau potable — Hub'Eau")
    print("─" * 46)

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.")
        print("  Lancez d'abord 01_referentiel.py et 02_canton.py")
        sys.exit(1)

    reprise = "--tout" not in sys.argv
    acquis = {}
    if reprise and SORTIE.exists():
        acquis = json.loads(SORTIE.read_text(encoding="utf-8")).get("communes", {})
        if acquis:
            print(f"  Reprise : {len(acquis)} commune(s) déjà collectée(s).")
            print("  Utilisez --tout pour tout recollecter.\n")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    depuis = (date.today()
              - timedelta(days=365 * PROFONDEUR_ANNEES)).isoformat()

    resultat, sans_donnee, en_erreur = dict(acquis), [], []
    vus = {"juges": 0, "indetermines": 0, "non_conformes": 0}

    def sauver():
        DONNEES.mkdir(exist_ok=True)
        SORTIE.write_text(json.dumps({
            "genere_le": date.today().isoformat(),
            "source": SOURCE, "licence": LICENCE, "frequence": "mensuelle",
            "communes": {k: {ck: cv for ck, cv in v.items()
                             if not ck.startswith("_")}
                         for k, v in resultat.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    for i, c in enumerate(communes, start=1):
        code, nom = c["code"], c["nom"]
        if code in acquis:
            continue
        print(f"  [{i:>2}/{len(communes)}] {nom[:30]:<30}", end=" ", flush=True)

        reseaux = reseaux_de(code)
        time.sleep(PAUSE)
        analyses = analyses_de(code, depuis)
        time.sleep(PAUSE)

        if analyses is None:
            en_erreur.append(f"{nom} (service indisponible)")
            print("échec, commune ignorée")
            continue

        try:
            synthese = synthetiser(c, reseaux, analyses)
        except Exception as erreur:
            en_erreur.append(f"{nom} ({type(erreur).__name__}: {erreur})")
            print("erreur de traitement")
            continue

        if not synthese:
            sans_donnee.append(nom)
            print("aucune donnée")
            continue

        resultat[code] = synthese
        for k in vus:
            vus[k] += synthese.get("_diagnostic", {}).get(k, 0)
        sauver()   # sauvegarde au fil de l'eau : une coupure ne perd rien

        diag = synthese.get("_diagnostic", {})
        taux = synthese["mesures"]["EAU-01"]["valeur"]
        suffixe = (f", {diag['indetermines']} indéterminé(s)"
                   if diag.get("indetermines") else "")
        print(f"{len(reseaux)} réseau(x), conformité "
              f"{taux if taux is not None else '—'} %{suffixe}")

    if not resultat:
        print("\n[BLOCAGE] Aucune donnée récupérée. Rien n'a été écrit.")
        sys.exit(1)

    sauver()

    print(f"\n  Communes renseignées : {len(resultat)}/{len(communes)}")
    if vus["juges"]:
        print(f"  Prélèvements jugés   : {vus['juges']} "
              f"dont {vus['non_conformes']} non conforme(s)")
        print(f"  Indéterminés écartés : {vus['indetermines']}")
    if sans_donnee:
        print(f"  Sans donnée ({len(sans_donnee)}) : "
              f"{', '.join(sans_donnee[:6])}")
    if en_erreur:
        print(f"  [attention] En erreur ({len(en_erreur)}) :")
        for ligne in en_erreur[:8]:
            print(f"    · {ligne}")
        print("  Les autres communes ont bien été traitées.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Les communes déjà collectées sont "
              "enregistrées dans")
        print(f"  {SORTIE}. Relancez sans option pour continuer "
              "là où vous en étiez :")
        print("      python 06_eau.py\n")
        sys.exit(130)
