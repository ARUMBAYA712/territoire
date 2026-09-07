"""
15_elus.py — Élus locaux (Répertoire national des élus)
========================================================

Publie, pour chaque commune, son maire et son conseil municipal ; pour
le canton, ses conseillers départementaux ; pour l'intercommunalité,
ses conseillers communautaires.

Source : Répertoire national des élus, ministère de l'Intérieur, tenu
par les préfectures. Publication trimestrielle, sans clé.

CHOIX ÉDITORIAL — ce que l'on publie et ce que l'on tait.

Le répertoire contient la date de naissance et la profession déclarée
de chaque élu. Ces informations sont publiques, mais les republier
n'apporte rien au visiteur et démultiplie leur exposition. Le
collecteur retient donc le nom, la fonction et la date de début du
mandat, et rien d'autre. Le sexe n'est utilisé que pour calculer une
part agrégée, jamais affiché individuellement.

Ce choix se règle par PUBLIER_PROFESSION et PUBLIER_NAISSANCE, laissés
à faux. Les passer à vrai republierait des données personnelles sans
nécessité : à ne faire qu'avec un motif clair.

Produit :
    data/mesures-elus.json   repris par 03_agregation.py

Utilisation :
    python 15_elus.py                collecte
    python 15_elus.py --ressources   liste les fichiers du répertoire
    python 15_elus.py --colonnes     affiche les colonnes reconnues
    python 15_elus.py --tout         force un nouveau téléchargement
"""

import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-elus.json"
CACHE = DONNEES / "cache-elus"

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
JEU = "repertoire-national-des-elus-1"

SOURCE = "Répertoire national des élus — ministère de l'Intérieur"
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "elections"
SOUS_RUBRIQUE = "elus"
DELAI = 180

# Données personnelles republiées ou non. Voir l'en-tête du fichier.
PUBLIER_PROFESSION = False
PUBLIER_NAISSANCE = False

# Fichiers recherchés dans le jeu de données, par fragment de titre.
MANDATS = [
    ("municipaux", ["conseillers-municipaux", "conseillers municipaux"],
     "commune"),
    ("maires", ["maires"], "commune"),
    ("departementaux", ["conseillers-departementaux",
                        "conseillers départementaux"], "canton"),
    ("communautaires", ["conseillers-communautaires",
                        "conseillers communautaires"], "epci"),
]

# Reconnaissance des colonnes par fragment de nom : les intitulés
# varient d'une publication à l'autre.
CHAMPS = {
    "code_commune": ["code de la commune", "code commune", "codgeo"],
    "code_canton": ["code du canton", "code canton"],
    "code_epci": ["code de l'epci", "code epci", "n° siren de l'epci",
                  "siren de l'epci"],
    "nom": ["nom de l'élu", "nom de l elu", "nom"],
    "prenom": ["prénom de l'élu", "prenom de l elu", "prénom", "prenom"],
    "sexe": ["code sexe", "sexe"],
    "fonction": ["libellé de la fonction", "libelle de la fonction",
                 "fonction"],
    "debut_mandat": ["date de début du mandat", "date de debut du mandat",
                     "début du mandat"],
    "naissance": ["date de naissance"],
    "profession": ["libellé de la catégorie socio-professionnelle",
                   "catégorie socio-professionnelle", "profession"],
}


# ══════════════════════════════════════════════════════════════════

def lire(url, binaire=False):
    requete = urllib.request.Request(
        url, headers={"User-Agent": "portail-territorial/1.0"})
    with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
        corps = reponse.read()
    return corps if binaire else corps.decode("utf-8", errors="replace")


def ressources_du_jeu():
    """Fichiers publiés dans le jeu de données du répertoire."""
    try:
        contenu = json.loads(lire(DATAGOUV + JEU + "/"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"\n[ERREUR] data.gouv.fr injoignable : {e}\n")
        return None
    return contenu.get("resources", [])


def choisir(ressources, fragments):
    """Ressource dont le titre correspond, en préférant le CSV."""
    candidates = []
    for r in ressources:
        titre = str(r.get("title") or "").lower()
        if any(f in titre for f in fragments):
            candidates.append(r)
    if not candidates:
        return None
    csvs = [r for r in candidates
            if str(r.get("format") or "").lower() in ("csv", "txt")]
    return (csvs or candidates)[0]


def telecharger(ressource, nom):
    """Télécharge un fichier du répertoire, avec mise en cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    chemin = CACHE / f"{nom}.csv"
    if chemin.exists() and "--tout" not in sys.argv:
        return chemin.read_text(encoding="utf-8")

    url = ressource.get("url")
    print(f"    téléchargement…", end=" ", flush=True)
    try:
        brut = lire(url, binaire=True)
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
    chemin.write_text(texte, encoding="utf-8")
    print(f"{len(brut) / 1024:.0f} Ko")
    return texte


def lecteur(texte):
    premiere = texte.split("\n", 1)[0]
    separateur = max((";", "\t", ","), key=premiere.count)
    return csv.DictReader(io.StringIO(texte), delimiter=separateur)


def reconnaitre(colonnes):
    """Associe chaque rôle à la colonne correspondante."""
    trouve = {}
    normalisees = {c: str(c).strip().lower() for c in (colonnes or [])}
    for role, fragments in CHAMPS.items():
        for colonne, propre in normalisees.items():
            if any(propre == f for f in fragments):
                trouve[role] = colonne
                break
        if role in trouve:
            continue
        for colonne, propre in normalisees.items():
            if any(f in propre for f in fragments):
                trouve[role] = colonne
                break
    return trouve


# ══════════════════════════════════════════════════════════════════

def nom_affiche(ligne, colonnes):
    prenom = str(ligne.get(colonnes.get("prenom", ""), "") or "").strip()
    nom = str(ligne.get(colonnes.get("nom", ""), "") or "").strip()
    if nom.isupper():
        nom = nom.title()
    if prenom.isupper():
        prenom = prenom.title()
    return " ".join(x for x in (prenom, nom) if x)


def _date_fr(valeur):
    texte = str(valeur or "").strip()
    for forme in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(texte[:10], forme).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texte or None


def elu_lisible(ligne, colonnes):
    """Fiche d'un élu, réduite à ce qui est utile au visiteur."""
    details = {}
    fonction = str(ligne.get(colonnes.get("fonction", ""), "") or "").strip()
    if fonction:
        details["Fonction"] = fonction.capitalize()
    debut = _date_fr(ligne.get(colonnes.get("debut_mandat", ""), ""))
    if debut:
        details["Mandat depuis le"] = debut
    if PUBLIER_PROFESSION and colonnes.get("profession"):
        metier = str(ligne.get(colonnes["profession"], "") or "").strip()
        if metier:
            details["Profession déclarée"] = metier
    if PUBLIER_NAISSANCE and colonnes.get("naissance"):
        naissance = _date_fr(ligne.get(colonnes["naissance"], ""))
        if naissance:
            details["Né(e) le"] = naissance
    return {"titre": nom_affiche(ligne, colonnes), "details": details}


def rang_fonction(item):
    """Le maire d'abord, puis les adjoints, puis les conseillers."""
    fonction = str(item["details"].get("Fonction", "")).lower()
    if "maire" in fonction and "adjoint" not in fonction:
        return (0, item["titre"])
    if "adjoint" in fonction:
        nombre = re.search(r"(\d+)", fonction)
        return (1, int(nombre.group(1)) if nombre else 99, item["titre"])
    if "président" in fonction:
        return (0, item["titre"])
    return (2, item["titre"])


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


def part_de_femmes(lignes, colonnes):
    """Part des femmes dans une assemblée, en pourcentage."""
    cle = colonnes.get("sexe")
    if not cle:
        return None, 0, 0
    femmes = hommes = 0
    for ligne in lignes:
        code = str(ligne.get(cle, "") or "").strip().upper()[:1]
        if code == "F":
            femmes += 1
        elif code == "M":
            hommes += 1
    total = femmes + hommes
    if not total:
        return None, 0, 0
    return round(100 * femmes / total, 1), femmes, hommes


def synthetiser_assemblee(lignes, colonnes, libelle, ancre, titre_bloc,
                          identifiants, note):
    """Indicateurs et bloc d'une assemblée délibérante."""
    if not lignes:
        return None

    items = sorted((elu_lisible(l, colonnes) for l in lignes),
                   key=rang_fonction)

    mesures = {}
    tete = next((i for i in items
                 if "maire" in str(i["details"].get("Fonction", "")).lower()
                 and "adjoint" not in str(i["details"].get("Fonction", "")).lower()
                 or "président" in str(i["details"].get("Fonction", "")).lower()),
                None)
    if tete and identifiants.get("tete"):
        mesures[identifiants["tete"]] = mesure(
            tete["titre"], "", libelle["tete"], rang=10, ancre=ancre,
            repere=tete["details"].get("Mandat depuis le")
                   and f"En fonction depuis le {tete['details']['Mandat depuis le']}")
        if not mesures[identifiants["tete"]].get("repere"):
            mesures[identifiants["tete"]].pop("repere", None)

    mesures[identifiants["effectif"]] = mesure(
        len(items), libelle["unite"], libelle["effectif"],
        rang=20, ancre=ancre, agregation=identifiants.get("agregation"))
    if not identifiants.get("agregation"):
        mesures[identifiants["effectif"]].pop("agregation", None)

    part, femmes, hommes = part_de_femmes(lignes, colonnes)
    if part is not None and identifiants.get("parite"):
        mesures[identifiants["parite"]] = mesure(
            part, "%", libelle["parite"], obtention="recalculé", rang=30,
            repere=f"{femmes} femmes, {hommes} hommes",
            explication=("Part des femmes dans l'assemblée. Le sexe est "
                         "utilisé pour ce seul calcul et n'est pas publié "
                         "individuellement."))

    blocs = [{
        "rubrique": RUBRIQUE,
        "sous_rubrique": SOUS_RUBRIQUE,
        "id": ancre,
        "titre": titre_bloc,
        "items": items,
        "note": note,
    }]
    return {"mesures": mesures, "blocs": blocs}


NOTE_COMMUNE = (
    "Répertoire national des élus, tenu par les préfectures et publié "
    "chaque trimestre. Une élection récente peut ne pas encore y figurer. "
    "Seuls le nom, la fonction et la date de début de mandat sont repris : "
    "la date de naissance et la profession déclarée, présentes dans la "
    "source, ne sont pas republiées ici.")

NOTE_CANTON = (
    "Depuis 2015, chaque canton élit un binôme composé d'une femme et d'un "
    "homme, pour six ans. " + NOTE_COMMUNE)


# ══════════════════════════════════════════════════════════════════

def main():
    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    print("\nÉlus locaux — Répertoire national des élus")
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

    donnees = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = donnees["communes"]
    canton = (donnees.get("cantons") or [None])[0]
    code_epci = donnees["perimetre"]["epci"][0]
    attendues = {c["code"]: c["nom"] for c in communes}

    lots = {}
    for nom, fragments, _ in MANDATS:
        ressource = choisir(ressources, fragments)
        print(f"\n  {nom:<16}", end=" ")
        if not ressource:
            print("fichier introuvable dans le jeu de données")
            continue
        print(f"{str(ressource.get('title'))[:44]}")
        texte = telecharger(ressource, nom)
        if texte:
            lots[nom] = texte

    if "--colonnes" in sys.argv:
        for nom, texte in lots.items():
            lecture = lecteur(texte)
            colonnes = reconnaitre(lecture.fieldnames)
            print(f"\n  ── {nom} ──")
            print(f"    {len(lecture.fieldnames or [])} colonnes")
            for role in CHAMPS:
                print(f"    {role:<14} {colonnes.get(role) or 'ABSENTE'}")
        print()
        return

    resultat_communes, resultat_territoires = {}, {}

    # ── conseils municipaux ──
    if "municipaux" in lots:
        lecture = lecteur(lots["municipaux"])
        colonnes = reconnaitre(lecture.fieldnames)
        if not colonnes.get("code_commune"):
            print("\n[BLOCAGE] Colonne de code commune introuvable.")
            print("  Lancez --colonnes pour voir le fichier.\n")
            sys.exit(1)
        par_commune = {}
        for ligne in lecture:
            code = str(ligne.get(colonnes["code_commune"], "")).strip()
            if code in attendues:
                par_commune.setdefault(code, []).append(ligne)

        for code, lignes in par_commune.items():
            synthese = synthetiser_assemblee(
                lignes, colonnes,
                {"tete": "Maire", "effectif": "Conseil municipal",
                 "unite": "élus", "parite": "Part de femmes au conseil"},
                "conseil-municipal", "Conseil municipal",
                {"tete": "POL-01", "effectif": "POL-02",
                 "parite": "POL-03", "agregation": "somme"},
                NOTE_COMMUNE)
            if synthese:
                resultat_communes[code] = synthese

    # ── conseillers départementaux du canton ──
    if "departementaux" in lots and canton:
        lecture = lecteur(lots["departementaux"])
        colonnes = reconnaitre(lecture.fieldnames)
        cible = str(canton["code"])
        lignes = []
        for ligne in lecture:
            code = str(ligne.get(colonnes.get("code_canton", ""), "")).strip()
            if code.lstrip("0") == cible.lstrip("0") or code == cible:
                lignes.append(ligne)
        synthese = synthetiser_assemblee(
            lignes, colonnes,
            {"tete": "Conseiller départemental",
             "effectif": "Conseillers départementaux", "unite": "élus",
             "parite": "Part de femmes"},
            "conseillers-departementaux",
            "Conseillers départementaux du canton",
            {"effectif": "POL-10", "parite": None},
            NOTE_CANTON)
        if synthese:
            resultat_territoires[f"canton:{canton['code']}"] = synthese

    # ── conseil communautaire ──
    if "communautaires" in lots:
        lecture = lecteur(lots["communautaires"])
        colonnes = reconnaitre(lecture.fieldnames)
        lignes = []
        for ligne in lecture:
            code = str(ligne.get(colonnes.get("code_epci", ""), "")).strip()
            if code == str(code_epci):
                lignes.append(ligne)
        synthese = synthetiser_assemblee(
            lignes, colonnes,
            {"tete": "Président", "effectif": "Conseil communautaire",
             "unite": "élus", "parite": "Part de femmes au conseil"},
            "conseil-communautaire", "Conseil communautaire",
            {"tete": "POL-20", "effectif": "POL-21", "parite": "POL-22"},
            NOTE_COMMUNE)
        if synthese:
            resultat_territoires[f"epci:{code_epci}"] = synthese

    if not resultat_communes and not resultat_territoires:
        print("\n[BLOCAGE] Aucun élu retrouvé. Rien n'a été écrit.")
        print("  Lancez --colonnes pour vérifier la lecture des fichiers.\n")
        sys.exit(1)

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "trimestrielle",
        "communes": resultat_communes,
        "territoires": resultat_territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    manquantes = sorted(set(attendues) - set(resultat_communes))
    total = sum(v["mesures"]["POL-02"]["valeur"]
                for v in resultat_communes.values() if "POL-02" in v["mesures"])
    print(f"\n  Communes renseignées : "
          f"{len(resultat_communes)}/{len(attendues)}")
    print(f"  Élus municipaux      : {total}")
    for cle, synthese in resultat_territoires.items():
        effectif = next((m["valeur"] for i, m in synthese["mesures"].items()
                         if i in ("POL-10", "POL-21")), "?")
        print(f"  {cle:<22} {effectif} élu(s)")
    if manquantes:
        print(f"  [attention] Sans élus ({len(manquantes)}) : "
              f"{', '.join(attendues[c] for c in manquantes[:6])}")
    print(f"\n  Données personnelles : nom, fonction et date de mandat "
          f"seulement.")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
