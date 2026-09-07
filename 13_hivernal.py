"""
13_hivernal.py — Obligation d'équipements hivernaux
====================================================

Publie, commune par commune, l'obligation de détenir chaînes ou pneus
hiver du 1er novembre au 31 mars, instituée par la loi Montagne.

PARTICULARITÉ : cette donnée n'est pas collectée mais SAISIE. La liste
des communes est fixée par arrêté préfectoral, publié en PDF, et aucune
source lisible par une machine n'existe. Le fichier de référence est
donc tenu à la main, et ce script se charge de le contrôler, de le
dater et de signaler sa péremption.

Trois règles en découlent, appliquées ici :

  · le texte source est cité sur chaque fiche, avec un lien ;
  · tant que la saisie est déclarée incomplète, seules les communes
    listées reçoivent l'information — les autres n'affichent RIEN,
    plutôt qu'un « non concernée » qui serait peut-être faux ;
  · l'arrêté porte une échéance : passée celle-ci, le script réclame
    une vérification et cesse de publier.

Fichier de référence :
    data/reference-equipements-hivernaux.json

Produit :
    data/mesures-hivernal.json   repris par 03_agregation.py

Utilisation :
    python 13_hivernal.py
    python 13_hivernal.py --modele   crée un fichier de référence vierge
"""

import json
import sys
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 2

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
REFERENCE = DONNEES / "reference-equipements-hivernaux.json"
SORTIE = DONNEES / "mesures-hivernal.json"

SOURCE = "Arrêté préfectoral — obligation d'équipements hivernaux"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "transports"
ANCRE = "equipements-hivernaux"

# Période d'application, identique chaque année.
DEBUT = (11, 1)
FIN = (3, 31)


MODELE = {
    "_lisez_moi": (
        "Référentiel saisi à la main depuis l'arrêté préfectoral. "
        "Complétez « communes » à partir de la liste annexée à l'arrêté, "
        "puis passez « saisie_complete » à true. Tant qu'elle est false, "
        "les communes absentes de la liste n'affichent aucune information "
        "plutôt qu'un « non concernée » qui pourrait être faux."),
    "texte": "Arrêté préfectoral du 12 janvier 2026",
    "autorite": "Préfecture de l'Isère",
    "lien": ("https://www.isere.gouv.fr/Actions-de-l-Etat/Securites/"
             "Securite-routiere/Equipement-obligatoire-en-periode-hivernale"),
    "saisi_le": date.today().isoformat(),
    "valable_jusqu_au": "2026-10-31",
    "saisie_complete": False,
    "communes": {
        # Désignez les communes par leur NOM, tel qu'il figure dans
        # l'arrêté : le script les rapproche du référentiel. Un code
        # INSEE est également accepté.
        #
        #   "Nom de la commune": {"portee": "totale"}
        #   "Nom de la commune": {"portee": "partielle",
        #                         "precision": "axes concernés"}
        "Cognin-les-Gorges": {"portee": "totale"},
        "Saint-Gervais": {"portee": "totale"},
        "Rovon": {"portee": "totale"},
    },
}


def normaliser(texte):
    """Nom de commune réduit à sa forme comparable."""
    import unicodedata
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", str(texte or ""))
        if unicodedata.category(c) != "Mn")
    return "".join(c for c in sans_accent.lower() if c.isalnum())


# ══════════════════════════════════════════════════════════════════

def en_periode(jour=None):
    """La période hivernale court du 1er novembre au 31 mars."""
    jour = jour or date.today()
    debut = date(jour.year, *DEBUT)
    fin = date(jour.year, *FIN)
    return jour >= debut or jour <= fin


def _date_fr(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso or "inconnue")


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "saisi", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE}
    base.update(habillage)
    return base


def synthetiser(entree, reference, hiver):
    """Indicateurs et bloc d'une commune concernée."""
    partielle = str(entree.get("portee", "totale")).lower().startswith("part")
    precision = str(entree.get("precision") or "").strip()

    if partielle:
        valeur = "Sur une partie de la commune"
        explication = ("L'obligation ne s'applique qu'à certains axes de "
                       "cette commune, signalés par des panneaux. Hors de "
                       "ces sections, elle ne s'applique pas.")
    else:
        valeur = "Sur toute la commune"
        explication = ("L'obligation s'applique à l'ensemble du territoire "
                       "communal, du 1er novembre au 31 mars.")

    mesures = {
        "TRA-01": mesure(
            valeur, "", "Équipements hivernaux obligatoires",
            rang=10, ancre=ANCRE, explication=explication,
            repere=f"Du 1er novembre au 31 mars · {reference['texte']}",
            **({"mise_en_avant": True, "ton": "attention"} if hiver else {})),
    }

    details = {
        "Portée": ("Une partie de la commune, sur les axes signalés"
                   if partielle else "Toute la commune"),
        "Période": "Du 1er novembre au 31 mars",
        "Texte de référence": reference["texte"],
        "Autorité": reference.get("autorite", ""),
    }
    if precision:
        details["Axes concernés"] = precision

    items = [{
        "titre": ("Obligation sur une partie de la commune" if partielle
                  else "Obligation sur toute la commune"),
        "details": details,
        "etat": ["En vigueur" if hiver else "Hors période",
                 "attention" if hiver else "neutre"],
        "texte": ("Au choix : détenir des dispositifs antidérapants "
                  "amovibles — chaînes ou chaussettes — permettant "
                  "d'équiper au moins deux roues motrices, ou être équipé "
                  "de quatre pneus hiver portant le marquage 3PMSF. Les "
                  "véhicules à pneus à clous en sont dispensés."),
    }]

    blocs = [{
        "rubrique": RUBRIQUE,
        "id": ANCRE,
        "titre": "Équipements hivernaux obligatoires",
        "items": items,
        "lien": ({"url": reference["lien"],
                  "libelle": "Consulter l'arrêté préfectoral"}
                 if reference.get("lien") else None),
        "note": (f"Information transcrite depuis {reference['texte']}, "
                 f"saisie le {_date_fr(reference.get('saisi_le'))}. "
                 "L'arrêté fait seul foi, et la signalisation sur place "
                 "détermine l'opposabilité de la mesure. "
                 + ("La liste des communes n'est pas encore intégralement "
                    "reprise : l'absence d'information sur une commune ne "
                    "signifie pas qu'elle n'est pas concernée."
                    if not reference.get("saisie_complete") else "")),
    }]

    return {"mesures": mesures, "blocs": blocs}


# ══════════════════════════════════════════════════════════════════

def ecrire_modele():
    DONNEES.mkdir(exist_ok=True)
    if REFERENCE.exists():
        print(f"\n  {REFERENCE} existe déjà — rien n'a été écrasé.\n")
        return
    REFERENCE.write_text(json.dumps(MODELE, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print(f"\n  Modèle créé : {REFERENCE}")
    print("  Complétez la liste des communes depuis l'arrêté, puis")
    print("  passez « saisie_complete » à true.\n")


def main():
    if "--modele" in sys.argv:
        ecrire_modele()
        return

    print("\nÉquipements hivernaux obligatoires — arrêté préfectoral")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    if not REFERENCE.exists():
        # Configuration absente : ce n'est pas une panne. On le signale
        # et on rend la main, pour ne pas interrompre la chaîne.
        print(f"\n  Aucun fichier de référence — rien à publier.")
        print(f"  Créez-le avec : python 13_hivernal.py --modele\n")
        return

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))

    # ── contrôle de péremption ──
    echeance = reference.get("valable_jusqu_au")
    if echeance:
        try:
            limite = date.fromisoformat(echeance)
        except ValueError:
            print(f"\n[BLOCAGE] Échéance illisible : {echeance!r}\n")
            sys.exit(1)
        if date.today() > limite:
            # Périmé : on publie un fichier VIDE plutôt que rien. Ne rien
            # écrire laisserait en place la collecte précédente, et le
            # site continuerait d'afficher une obligation légale périmée.
            DONNEES.mkdir(exist_ok=True)
            SORTIE.write_text(json.dumps({
                "genere_le": date.today().isoformat(),
                "version": VERSION, "source": SOURCE, "licence": LICENCE,
                "frequence": "annuelle", "texte": reference.get("texte"),
                "valable_jusqu_au": echeance, "perime": True,
                "communes": {},
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n[ATTENTION] Le référentiel a expiré le "
                  f"{_date_fr(echeance)}.")
            print("  Un nouvel arrêté a probablement été publié.")
            print(f"  Vérifiez sur {reference.get('lien', 'la préfecture')}")
            print("  puis mettez à jour le fichier de référence.")
            print("\n  L'information a été RETIRÉE du site : mieux vaut")
            print("  aucune donnée qu'une obligation légale périmée.\n")
            return
        reste = (limite - date.today()).days
        if reste < 45:
            print(f"  [attention] Référentiel valable encore {reste} jour(s).")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    connues = {c["code"]: c["nom"] for c in communes}
    par_nom = {normaliser(c["nom"]): c["code"] for c in communes}

    # La clé peut être un nom ou un code INSEE : on ramène tout au code.
    listees, inconnues = {}, []
    for cle, entree in (reference.get("communes") or {}).items():
        code = cle if cle in connues else par_nom.get(normaliser(cle))
        if code:
            listees[code] = entree
        else:
            inconnues.append(cle)
    if inconnues:
        print(f"  [attention] {len(inconnues)} commune(s) hors du périmètre, "
              f"ignorée(s) : {', '.join(inconnues[:6])}")

    hiver = en_periode()
    resultat = {}
    for code, entree in listees.items():
        if code not in connues:
            continue
        resultat[code] = synthetiser(entree, reference, hiver)

    complete = bool(reference.get("saisie_complete"))
    if complete:
        # La saisie est déclarée exhaustive : on peut affirmer qu'une
        # commune absente de la liste n'est pas concernée.
        for code, nom in connues.items():
            if code in resultat:
                continue
            resultat[code] = {
                "mesures": {"TRA-01": mesure(
                    "Non concernée", "", "Équipements hivernaux obligatoires",
                    rang=10,
                    explication=("Cette commune ne figure pas dans la liste "
                                 "annexée à l'arrêté préfectoral."),
                    repere=reference["texte"])},
                "blocs": [],
            }

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
        "texte": reference.get("texte"),
        "saisi_le": reference.get("saisi_le"),
        "valable_jusqu_au": echeance,
        "saisie_complete": complete,
        "communes": resultat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    concernees = sum(1 for v in resultat.values()
                     if v["mesures"]["TRA-01"]["valeur"] != "Non concernée")
    partielles = sum(1 for v in resultat.values()
                     if v["mesures"]["TRA-01"]["valeur"].startswith("Sur une"))

    print(f"\n  Texte de référence   : {reference.get('texte')}")
    print(f"  Saisi le             : {_date_fr(reference.get('saisi_le'))}")
    print(f"  Valable jusqu'au     : {_date_fr(echeance)}")
    print(f"  Communes concernées  : {concernees}"
          + (f", dont {partielles} partiellement" if partielles else ""))
    print(f"  Période en cours     : {'oui' if hiver else 'non'}")
    if not complete:
        print(f"\n  [ATTENTION] Saisie déclarée incomplète.")
        print(f"  Les {len(connues) - len(resultat)} commune(s) non listées "
              f"n'affichent rien,")
        print(f"  plutôt qu'un « non concernée » qui pourrait être faux.")
        print(f"  Complétez la liste depuis l'arrêté, puis passez")
        print(f"  « saisie_complete » à true.")
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
