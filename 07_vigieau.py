"""
07_vigieau.py — Restrictions sécheresse (VigiEau)
==================================================

Récupère, commune par commune, les restrictions d'usage de l'eau en
vigueur : niveau de gravité, période, usages concernés et lien vers
l'arrêté préfectoral.

Source : API VigiEau (ministère de la Transition écologique), alimentée
par les arrêtés préfectoraux. Mise à jour quotidienne.

Particularité : cette donnée change tous les jours et peut être vide.
« Aucune restriction en vigueur » est une information à part entière,
et non une absence de donnée — le script la publie explicitement.

Produit :
    data/mesures-secheresse.json   repris par 03_agregation.py

Utilisation :
    python 07_vigieau.py
    python 07_vigieau.py --tout    (ignore la collecte précédente)
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
SORTIE = DONNEES / "mesures-secheresse.json"

API = "https://api.vigieau.gouv.fr/api/zones"
SOURCE = "VigiEau — ministère de la Transition écologique"

# À incrémenter dès que la forme des données produites change.
# Une collecte réalisée avec une version antérieure est ignorée : sans
# cela, la reprise conserverait indéfiniment un format périmé.
VERSION = 2
LICENCE = "Licence Ouverte 2.0"

PAUSE = 0.3
DELAI = 60
TENTATIVES = 4

# Niveaux réglementaires, du plus faible au plus sévère.
# rang, libellé, ton d'affichage
NIVEAUX = {
    "vigilance": (1, "Vigilance", "attention"),
    "alerte": (2, "Alerte", "attention"),
    "alerte_renforcee": (3, "Alerte renforcée", "alerte"),
    "crise": (4, "Crise", "alerte"),
}

ANCRE = "restrictions-usages-eau"

TYPES_EAU = {
    "SUP": "Eaux superficielles (rivières)",
    "SOU": "Eaux souterraines (nappes)",
    "AEP": "Eau potable (réseau)",
}


# ══════════════════════════════════════════════════════════════════

def appeler(code_commune, longitude, latitude):
    """Interroge VigiEau pour une commune.

    Les coordonnées sont transmises systématiquement : une commune
    traversée par plusieurs zones d'alerte est refusée sans elles.

    Renvoie la liste des zones, [] si aucune restriction n'est en
    vigueur, ou None en cas d'échec technique — trois cas qu'il ne faut
    surtout pas confondre.
    """
    params = {"commune": code_commune}
    if longitude is not None and latitude is not None:
        params["lon"] = f"{longitude:.5f}"
        params["lat"] = f"{latitude:.5f}"
    url = f"{API}?" + urllib.parse.urlencode(params)

    attente = 2
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0",
                              "Accept": "application/json"})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
            return donnees if isinstance(donnees, list) else [donnees]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []          # aucune zone en vigueur : c'est une réponse
            if e.code == 409:
                print("[plusieurs zones, coordonnées refusées] ",
                      end="", flush=True)
                return None
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                print(f"[{e.code}, essai {tentative + 1}/{TENTATIVES}] ",
                      end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            print(f"[HTTP {e.code}] ", end="", flush=True)
            return None
        except (urllib.error.URLError, OSError):
            if tentative < TENTATIVES:
                print(f"[lenteur, essai {tentative + 1}/{TENTATIVES}] ",
                      end="", flush=True)
                time.sleep(attente)
                attente *= 2
                continue
            return None
    return None


def mesure(valeur, unite, nom, **habillage):
    """Indicateur communal.

    « habillage » transporte les consignes d'affichage facultatives —
    mise en avant, ton, ancre — que le générateur de pages sait lire.
    """
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "niveaux": ["commune"]}
    base.update(habillage)
    return base


def _date_fr(iso):
    if not iso:
        return "non précisée"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def synthetiser(zones):
    """Construit les indicateurs et le bloc à partir des zones d'alerte."""
    if not zones:
        return {
            "mesures": {
                "EAU-10": mesure("Aucune restriction en vigueur", "",
                                 "Restrictions sécheresse",
                                 mise_en_avant=True),
                "EAU-11": mesure(0, "zones d'alerte",
                                 "Zones d'alerte concernant la commune"),
            },
            "blocs": [],
        }

    pires = max(NIVEAUX.get(z.get("niveauGravite"), (0, "Inconnu", "neutre"))
                for z in zones)
    items = []

    for z in sorted(zones, key=lambda x: TYPES_EAU.get(x.get("type"), "zzz")):
        rang, libelle, ton = NIVEAUX.get(
            z.get("niveauGravite"), (0, "Niveau non précisé", "neutre"))
        arrete = z.get("arrete") or {}

        details = {
            "Type d'eau": TYPES_EAU.get(z.get("type"), z.get("type") or "—"),
            "Zone d'alerte": z.get("nom") or z.get("code") or "—",
            "En vigueur depuis": _date_fr(arrete.get("dateDebutValidite")),
        }
        if arrete.get("dateFinValidite"):
            details["Jusqu'au"] = _date_fr(arrete["dateFinValidite"])

        usages = z.get("usages") or []
        if usages:
            thematiques = []
            for u in usages:
                t = (u.get("thematique") or u.get("nom") or "").strip()
                if t and t not in thematiques:
                    thematiques.append(t)
            details["Usages concernés"] = len(usages)
            texte = "Restrictions portant sur : " + ", ".join(
                thematiques[:8]).lower() + ("…" if len(thematiques) > 8 else ".")
        else:
            texte = None

        item = {"titre": libelle + " — " + TYPES_EAU.get(
                    z.get("type"), z.get("type") or "zone"),
                "etat": [libelle, ton],
                "details": details}
        if texte:
            item["texte"] = texte
        if arrete.get("cheminFichier"):
            item["lien"] = {"url": arrete["cheminFichier"],
                            "libelle": "Lire l'arrêté préfectoral"}
        items.append(item)

    return {
        "mesures": {
            "EAU-10": mesure(pires[1], "", "Restrictions sécheresse",
                             mise_en_avant=True, ton=pires[2], ancre=ANCRE),
            "EAU-11": mesure(len(zones), "zones d'alerte",
                             "Zones d'alerte concernant la commune",
                             ancre=ANCRE),
        },
        "blocs": [{
            "rubrique": "environnement",
            "id": ANCRE,
            "titre": "Restrictions des usages de l'eau",
            "items": items,
            "note": ("Situation au " + date.today().strftime("%d/%m/%Y")
                     + ". Les arrêtés préfectoraux évoluent rapidement : "
                     "en cas de doute, l'arrêté publié et affiché en mairie "
                     "fait seul référence. Une commune peut relever de "
                     "plusieurs zones d'alerte selon l'origine de l'eau."),
        }],
    }


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nRestrictions sécheresse — VigiEau")
    print("─" * 46)

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.")
        print("  Lancez d'abord 01_referentiel.py et 02_canton.py")
        sys.exit(1)

    reprise = "--tout" not in sys.argv
    acquis = {}
    if reprise and SORTIE.exists():
        precedent = json.loads(SORTIE.read_text(encoding="utf-8"))
        # Une collecte de la veille est périmée : cette donnée est quotidienne.
        if precedent.get("version") != VERSION:
            print(f"  Collecte précédente produite par une version "
                  f"antérieure du script : elle est ignorée.\n")
        elif precedent.get("genere_le") == date.today().isoformat():
            acquis = precedent.get("communes", {})
            if acquis:
                print(f"  Reprise du jour : {len(acquis)} commune(s) déjà "
                      f"collectée(s).\n")
        else:
            print("  Collecte précédente antérieure à aujourd'hui : "
                  "elle est ignorée.\n")

    communes = json.loads(REFERENTIEL.read_text(encoding="utf-8"))["communes"]
    resultat = dict(acquis)
    en_erreur, sous_restriction = [], []

    def sauver():
        DONNEES.mkdir(exist_ok=True)
        SORTIE.write_text(json.dumps({
            "genere_le": date.today().isoformat(),
            "version": VERSION,
            "source": SOURCE, "licence": LICENCE, "frequence": "quotidienne",
            "communes": resultat,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    for i, c in enumerate(communes, start=1):
        code, nom = c["code"], c["nom"]
        if code in acquis:
            continue
        print(f"  [{i:>2}/{len(communes)}] {nom[:30]:<30}", end=" ", flush=True)

        zones = appeler(code, c.get("longitude"), c.get("latitude"))
        time.sleep(PAUSE)

        if zones is None:
            en_erreur.append(nom)
            print("échec")
            continue

        resultat[code] = synthetiser(zones)
        sauver()

        niveau = resultat[code]["mesures"]["EAU-10"]["valeur"]
        if zones:
            sous_restriction.append(f"{nom} ({niveau.lower()})")
        print(niveau)

    sauver()

    print(f"\n  Communes renseignées : {len(resultat)}/{len(communes)}")
    if sous_restriction:
        print(f"  Sous restriction ({len(sous_restriction)}) :")
        for ligne in sous_restriction[:10]:
            print(f"    · {ligne}")
    else:
        print("  Aucune commune sous restriction à cette date.")
    if en_erreur:
        print(f"  [attention] En erreur ({len(en_erreur)}) : "
              f"{', '.join(en_erreur[:6])}")
    print(f"  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Relancez pour continuer :  python 07_vigieau.py\n")
        sys.exit(130)
