"""
14_vigilance.py — Vigilance météorologique (Météo-France)
==========================================================

Publie le niveau de vigilance en cours et les phénomènes concernés :
vent violent, pluie-inondation, orages, neige-verglas, canicule, grand
froid, avalanches.

DEUX PARTICULARITÉS À CONNAÎTRE.

**Une clé est nécessaire.** L'API Bulletin Vigilance est gratuite mais
suppose un compte sur le portail des API de Météo-France et un jeton.
Voir la section « Obtenir une clé » en bas de ce fichier.

**La vigilance est départementale.** Elle vaut pour l'Isère entière, pas
pour une commune. Elle est donc rattachée au canton et à
l'intercommunalité, comme les nappes et les rivières.

**Et une réserve de fond.** Un site statique ne peut pas être un canal
d'alerte : entre deux régénérations, l'information vieillit. Le
collecteur affiche donc toujours l'heure d'émission du bulletin, et
au-delà d'un délai il cesse de présenter le niveau comme actuel et
renvoie vers Météo-France. Publier une vigilance périmée serait pire
que de n'en publier aucune.

Produit :
    data/mesures-vigilance.json   repris par 03_agregation.py

Utilisation :
    python 14_vigilance.py
    python 14_vigilance.py --inspecter   éprouve la clé et l'API
    python 14_vigilance.py --modele      crée le fichier de clé
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

VERSION_SCRIPT = 2

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
CLE = DONNEES / "cle-meteofrance.json"
SORTIE = DONNEES / "mesures-vigilance.json"

SOURCE = "Météo-France — vigilance météorologique"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "environnement"
SOUS_RUBRIQUE = "vigilance"
ANCRE = "phenomenes-vigilance"

DEPARTEMENT = "38"
DELAI = 60
TENTATIVES = 3

# Au-delà, le bulletin n'est plus présenté comme l'état courant.
PEREMPTION_HEURES = 12

# Points d'entrée possibles. Le premier qui répond est retenu : la
# documentation a changé de forme au fil des versions du portail.
CHEMINS = [
    "https://public-api.meteofrance.fr/public/DPVigilance/v1/"
    "cartevigilance/encours",
    "https://public-api.meteofrance.fr/public/DPVigilance/v1/"
    "textesvigilance/encours",
]

JETON = "https://portail-api.meteofrance.fr/token?grant_type=client_credentials"

NIVEAUX = {
    "1": ("Vert", None, "Pas de vigilance particulière."),
    "2": ("Jaune", "attention",
          "Soyez attentif si vous pratiquez des activités sensibles au "
          "risque météorologique."),
    "3": ("Orange", "attention",
          "Soyez très vigilant : des phénomènes dangereux sont prévus."),
    "4": ("Rouge", "alerte",
          "Une vigilance absolue s'impose : des phénomènes dangereux "
          "d'intensité exceptionnelle sont prévus."),
}

PHENOMENES = {
    "1": "Vent violent", "2": "Pluie-inondation", "3": "Orages",
    "4": "Crues", "5": "Neige-verglas", "6": "Canicule",
    "7": "Grand froid", "8": "Avalanches", "9": "Vagues-submersion",
}

MODELE_CLE = {
    "_lisez_moi": (
        "Clé de l'API Météo-France. Deux formes possibles : « apikey » "
        "pour une clé permanente, ou « application_id » pour un "
        "identifiant d'application dont le script tirera un jeton. "
        "Ce fichier ne doit jamais être publié : il figure au .gitignore. "
        "Pour une exécution par GitHub Actions, placez la valeur dans un "
        "secret nommé METEOFRANCE_APIKEY plutôt que dans ce fichier."),
    "apikey": "",
    "application_id": "",
}


# ══════════════════════════════════════════════════════════════════

def lire_cle():
    """Clé d'accès, depuis l'environnement ou le fichier local.

    L'environnement est prioritaire : c'est ainsi qu'une exécution
    automatisée fournira la clé, sans qu'elle figure dans le dépôt.
    """
    depuis_env = os.environ.get("METEOFRANCE_APIKEY", "").strip()
    if depuis_env:
        return {"apikey": depuis_env, "origine": "variable d'environnement"}

    identifiant = os.environ.get("METEOFRANCE_APPLICATION_ID", "").strip()
    if identifiant:
        return {"application_id": identifiant,
                "origine": "variable d'environnement"}

    if CLE.exists():
        contenu = json.loads(CLE.read_text(encoding="utf-8"))
        for champ in ("apikey", "application_id"):
            if str(contenu.get(champ) or "").strip():
                return {champ: contenu[champ].strip(),
                        "origine": str(CLE)}
    return None


def obtenir_jeton(application_id):
    """Échange un identifiant d'application contre un jeton temporaire."""
    requete = urllib.request.Request(
        JETON, data=b"", method="POST",
        headers={"Authorization": f"Basic {application_id}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
        return corps.get("access_token")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n  [ERREUR] Impossible d'obtenir un jeton : {e}")
        return None


def entetes(cle):
    if cle.get("apikey"):
        return {"apikey": cle["apikey"], "Accept": "application/json"}
    jeton = obtenir_jeton(cle["application_id"])
    if not jeton:
        return None
    return {"Authorization": f"Bearer {jeton}", "Accept": "application/json"}


def appeler(url, en_tetes, silencieux=False):
    requete = urllib.request.Request(
        url, headers={**en_tetes, "User-Agent": "portail-territorial/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            corps = reponse.read()
        if not corps.strip():
            return []
        return json.loads(corps.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        if not silencieux:
            print(f"\n  [ERREUR] Météo-France a répondu {e.code}")
            if e.code == 401:
                print("  Clé refusée. Vérifiez qu'elle est valide et que")
                print("  l'abonnement à l'API Bulletin Vigilance est actif.")
            elif e.code == 429:
                print("  Quota dépassé — 60 requêtes par minute.")
            if detail:
                print(f"  {detail}")
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        if not silencieux:
            print(f"\n  [ERREUR] {e}")
        return None


# ══════════════════════════════════════════════════════════════════

def chercher(objet, *fragments):
    """Première valeur d'un champ dont le nom contient l'un des fragments.

    La structure du bulletin a varié d'une version à l'autre : on
    cherche par fragment plutôt que par nom exact.
    """
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            if isinstance(valeur, (dict, list)):
                trouve = chercher(valeur, *fragments)
                if trouve is not None:
                    return trouve
            elif any(f in str(cle).lower() for f in fragments):
                if valeur not in (None, "", []):
                    return valeur
    elif isinstance(objet, list):
        for element in objet:
            trouve = chercher(element, *fragments)
            if trouve is not None:
                return trouve
    return None


def elements_du_departement(charge, departement):
    """Entrées du bulletin concernant le département visé."""
    trouvees = []

    def visiter(objet):
        if isinstance(objet, dict):
            domaine = str(objet.get("domain_id") or objet.get("domain")
                          or objet.get("departement") or "")
            if domaine == departement:
                trouvees.append(objet)
            for valeur in objet.values():
                visiter(valeur)
        elif isinstance(objet, list):
            for element in objet:
                visiter(element)

    visiter(charge)
    return trouvees


def phenomenes_de(entrees):
    """Niveau par phénomène, du plus grave au moins grave."""
    releves = {}
    for entree in entrees:
        liste = (entree.get("phenomenon_items")
                 or entree.get("phenomenons_items")
                 or entree.get("phenomenon_max_color_id") or [])
        if isinstance(liste, dict):
            liste = [liste]
        if not isinstance(liste, list):
            continue
        for p in liste:
            if not isinstance(p, dict):
                continue
            code = str(p.get("phenomenon_id") or p.get("phenomenon")
                       or p.get("phenomenon_max_color_id") or "")
            niveau = str(p.get("phenomenon_max_color_id")
                         or p.get("color_id") or p.get("niveau") or "")
            if code in PHENOMENES and niveau in NIVEAUX:
                if releves.get(code, "0") < niveau:
                    releves[code] = niveau
    return releves


def _heure_fr(iso):
    if not iso:
        return "inconnue"
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return moment.strftime("%d/%m/%Y à %Hh%M")
    except ValueError:
        return str(iso)


def anciennete_heures(iso):
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - moment).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def synthetiser(charge, departement):
    """Indicateurs et bloc de la vigilance départementale."""
    entrees = elements_du_departement(charge, departement)
    if not entrees:
        return None

    releves = phenomenes_de(entrees)
    emission = chercher(charge, "update_time", "date_emission", "emission")
    age = anciennete_heures(emission)
    perime = age is not None and age > PEREMPTION_HEURES

    pire = max(releves.values(), default="1")
    libelle, ton, conseil = NIVEAUX.get(pire, ("Inconnu", None, ""))

    concernes = sorted(
        ((PHENOMENES[c], n) for c, n in releves.items() if n != "1"),
        key=lambda x: (-int(x[1]), x[0]))

    repere = f"Bulletin du {_heure_fr(emission)}"
    if perime:
        repere += " — non actualisé depuis"

    mesures = {
        "MET-01": mesure(
            libelle if not perime else f"{libelle} (bulletin ancien)",
            "", "Vigilance météorologique", rang=10, ancre=ANCRE,
            repere=repere,
            explication=("Niveau de vigilance publié par Météo-France pour "
                         "l'ensemble du département. " + conseil),
            **({"mise_en_avant": True, "ton": ton}
               if ton and not perime else {})),
    }
    if concernes:
        mesures["MET-02"] = mesure(
            len(concernes),
            "phénomène" if len(concernes) == 1 else "phénomènes",
            "Phénomènes signalés", rang=20, ancre=ANCRE,
            repere=", ".join(nom for nom, _ in concernes))

    items = []
    for nom, niveau in concernes:
        etat, teinte, texte = NIVEAUX[niveau]
        items.append({
            "titre": nom,
            "details": {"Niveau": etat, "Département": "Isère"},
            "etat": [etat, teinte or "neutre"],
            "texte": texte,
        })
    if not items:
        items.append({
            "titre": "Aucun phénomène signalé",
            "details": {"Niveau": "Vert", "Département": "Isère"},
            "etat": ["Vert", "neutre"],
            "texte": NIVEAUX["1"][2],
        })

    blocs = [{
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "id": ANCRE,
        "titre": "Vigilance météorologique",
        "items": items,
        "lien": {"url": "https://vigilance.meteofrance.fr/fr",
                 "libelle": "Consulter la vigilance en direct"},
        "note": (f"Bulletin émis le {_heure_fr(emission)}, pour l'ensemble "
                 "du département de l'Isère. Ce site est régénéré "
                 "périodiquement : il ne constitue pas un canal d'alerte. "
                 "En cas de phénomène en cours, consultez Météo-France, "
                 "qui fait seule référence."
                 + (" Ce bulletin n'a pas été actualisé depuis plus de "
                    f"{PEREMPTION_HEURES} heures : ne le considérez pas "
                    "comme l'état courant." if perime else "")),
    }]

    return {"mesures": mesures, "blocs": blocs,
            "_emission": emission, "_perime": perime}


# ══════════════════════════════════════════════════════════════════

def ecrire_modele():
    DONNEES.mkdir(exist_ok=True)
    if CLE.exists():
        print(f"\n  {CLE} existe déjà — rien n'a été écrasé.\n")
        return
    CLE.write_text(json.dumps(MODELE_CLE, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n  Modèle créé : {CLE}")
    print("  Renseignez « apikey » ou « application_id ».")
    print("  Ce fichier ne doit jamais être publié.\n")


def inspecter():
    print("\nInspection — vigilance météorologique")
    print("─" * 60)
    cle = lire_cle()
    if not cle:
        print("  Aucune clé trouvée.")
        print("  Créez le fichier avec : python 14_vigilance.py --modele\n")
        return
    print(f"  Clé lue depuis : {cle['origine']}")
    print(f"  Forme          : "
          f"{'apikey' if cle.get('apikey') else 'application_id'}")

    en_tetes = entetes(cle)
    if not en_tetes:
        print("\n  Impossible de constituer l'en-tête d'authentification.\n")
        return

    for url in CHEMINS:
        charge = appeler(url, en_tetes, silencieux=True)
        etat = ("refusé" if charge is None else
                "vide" if not charge else "réponse obtenue")
        print(f"\n  {url.rsplit('/', 2)[-2]}/{url.rsplit('/', 1)[-1]} → {etat}")
        if not charge:
            continue
        entrees = elements_du_departement(charge, DEPARTEMENT)
        print(f"    entrées pour le département {DEPARTEMENT} : {len(entrees)}")
        if entrees:
            print(f"    champs de la première :")
            for c, v in list(entrees[0].items())[:14]:
                print(f"      {c:<32} {str(v)[:46]}")
            releves = phenomenes_de(entrees)
            print(f"    phénomènes reconnus : "
                  f"{ {PHENOMENES[c]: NIVEAUX[n][0] for c, n in releves.items()} }")
        emission = chercher(charge, "update_time", "date_emission", "emission")
        print(f"    émission : {_heure_fr(emission)}")
        break
    print()


def main():
    if "--modele" in sys.argv:
        ecrire_modele()
        return
    if "--inspecter" in sys.argv:
        inspecter()
        return

    print("\nVigilance météorologique — Météo-France")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    cle = lire_cle()
    if not cle:
        # Clé absente : configuration incomplète, pas une panne. On rend
        # la main sans interrompre la chaîne.
        print("\n  Aucune clé d'accès — rien à publier.")
        print("  L'API Bulletin Vigilance est gratuite mais suppose un")
        print("  compte sur portail-api.meteofrance.fr.")
        print("  Créez le fichier de clé : python 14_vigilance.py --modele\n")
        return

    en_tetes = entetes(cle)
    if not en_tetes:
        print("\n  Authentification impossible — rien à publier.\n")
        return

    charge, retenue = None, None
    for url in CHEMINS:
        charge = appeler(url, en_tetes, silencieux=True)
        if charge:
            retenue = url
            break
    if not charge:
        print("\n[BLOCAGE] Aucun point d'entrée n'a répondu.")
        print("  Lancez --inspecter pour un diagnostic détaillé.\n")
        sys.exit(1)

    synthese = synthetiser(charge, DEPARTEMENT)
    if not synthese:
        print(f"\n  Aucune entrée pour le département {DEPARTEMENT}.")
        print("  Rien n'a été écrit.\n")
        sys.exit(1)

    donnees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    canton = (donnees.get("cantons") or [None])[0]
    code_epci = donnees["perimetre"]["epci"][0]

    emission = synthese.pop("_emission", None)
    perime = synthese.pop("_perime", False)

    territoires = {}
    if canton:
        territoires[f"canton:{canton['code']}"] = synthese
    territoires[f"epci:{code_epci}"] = synthese

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "quotidienne",
        "emission": emission,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    m = synthese["mesures"]
    print(f"  Point d'entrée : {retenue.rsplit('/', 1)[-1]}")
    print(f"  Bulletin émis  : {_heure_fr(emission)}")
    print(f"  Niveau         : {m['MET-01']['valeur']}")
    if "MET-02" in m:
        print(f"  Phénomènes     : {m['MET-02']['repere']}")
    if perime:
        print(f"\n  [ATTENTION] Bulletin non actualisé depuis plus de "
              f"{PEREMPTION_HEURES} h.")
        print("  Il n'est pas présenté comme l'état courant.")
    print(f"  Fichier : {SORTIE}\n")


# ══════════════════════════════════════════════════════════════════
# OBTENIR UNE CLÉ
#
# 1. Créez un compte sur portail-api.meteofrance.fr
# 2. Souscrivez gratuitement à l'API « Bulletin Vigilance »
# 3. Générez une clé depuis la page d'utilisation de l'API
# 4. python 14_vigilance.py --modele, puis renseignez le fichier
# 5. python 14_vigilance.py --inspecter pour éprouver l'accès
#
# Quota : 60 requêtes par minute, largement suffisant — ce collecteur
# n'en fait qu'une par exécution.
#
# Pour une exécution automatisée, placez la clé dans un secret GitHub
# nommé METEOFRANCE_APIKEY plutôt que dans le fichier local.
# ══════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
