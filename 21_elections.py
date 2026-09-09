"""
21_elections.py — Résultats électoraux par commune
===================================================

Publie, commune par commune, la participation aux derniers scrutins et
le détail des listes aux municipales.

CE QUE CETTE RUBRIQUE APPORTE
------------------------------
La participation d'un village se compare à celle de ses voisins, et
personne ne la publie à cette échelle. Sur les municipales de mars 2026 :
Saint-Marcellin 58,57 %, Rencurel 57,54 %, Vinay 57,18 %. Trois communes
que tout oppose par la taille, et trois chiffres à trois points d'écart.

LE PROBLÈME, ET SA SOLUTION
----------------------------
Les fichiers communaux du ministère de l'Intérieur sont **énormes** :
124 Mo pour les européennes de 2024, 75 Mo pour les législatives, 14 Mo
pour les municipales. Huit scrutins représenteraient plusieurs centaines
de mégaoctets à chaque collecte, pour quarante-sept communes.

Mais **ils sont triés par code de département**, et le serveur de
data.gouv.fr accepte les requêtes partielles. Le bloc de l'Isère se
trouve par dichotomie, en une quinzaine de requêtes de quatre kilooctets,
puis se lit d'un coup.

Mesuré le 9 septembre 2026 sur le fichier des législatives 2024 :

    début du département 38 : octet 30 538 102
    fin   du département 38 : octet 31 774 481
    taille du bloc          : 1,2 Mo — soit 1,6 % du fichier
    coût de la recherche    : 17 requêtes de 4 Ko

**Ce procédé repose sur une hypothèse**, et une hypothèse se vérifie :
après lecture, toutes les lignes retenues doivent porter le département
attendu. Si ce n'était pas le cas — fichier trié autrement, un jour — le
scrutin est refusé avec son motif plutôt que publié de travers.

DEUX NIVEAUX DE LECTURE, ET POURQUOI
-------------------------------------
Les fichiers ne se ressemblent pas d'un scrutin à l'autre : les
municipales parlent de « Nuance liste », les législatives de « Nuance
candidat », le nombre de colonnes varie de 187 à plus de 300, et le
guillemetage change — les municipales encadrent chaque champ, les
législatives non.

Mais **quatre colonnes sont identiques partout** : « Code commune »,
« Inscrits », « Votants », « Exprimés ». D'où la règle :

  · la PARTICIPATION est lue sur tous les scrutins, parce qu'elle ne
    repose que sur ces quatre colonnes ;
  · le DÉTAIL DES LISTES n'est lu que sur les municipales, dont la
    forme est connue et vérifiée.

C'est moins ambitieux qu'une lecture universelle, et beaucoup plus sûr.

TROIS PRÉCAUTIONS
------------------
  · **Le module csv de la bibliothèque standard fait le travail.** Un
    découpage naïf sur le point-virgule lirait `"38"` au lieu de `38`
    sur la moitié des scrutins. Je m'y suis laissé prendre au premier
    essai ;
  · **une liste unique n'est pas un plébiscite.** À Rencurel, la seule
    liste en présence a obtenu 100 % des suffrages exprimés. L'écrire
    sans dire qu'il n'y avait qu'une liste serait exact et trompeur. Le
    collecteur compte les listes et écrit la réserve ;
  · **les nuances sont des étiquettes préfectorales**, parfois
    contestées par les intéressés. Elles sont publiées en citant leur
    origine, et rien n'en est déduit.

Produit :
    data/mesures-elections.json   repris par 03_agregation.py

Utilisation :
    python 21_elections.py
    python 21_elections.py --scrutins        liste les scrutins et sort
    python 21_elections.py --fichier F --scrutin ID
                                             lit un CSV déjà téléchargé
"""

import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

VERSION_SCRIPT = 1

DONNEES = Path("data")
REFERENTIEL = DONNEES / "referentiel-communes.json"
SORTIE = DONNEES / "mesures-elections.json"

API_DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"

SOURCE = ("Ministère de l'Intérieur — résultats électoraux par commune "
          "(data.gouv.fr)")
LICENCE = "Licence Ouverte 2.0"

VERSION = 1
RUBRIQUE = "elections"
SOUS_RUBRIQUE = "resultats"
ANCRE = "resultats-electoraux"

DELAI = 60
TENTATIVES = 3

# ── Les scrutins publiés ─────────────────────────────────────────────
# Ordre chronologique. « listes » n'est vrai que pour les scrutins dont
# la forme du fichier a été vérifiée colonne par colonne : ailleurs on
# ne lit que la participation.
#
# Les adresses ne sont JAMAIS écrites en dur : elles portent un
# horodatage et changent à chaque réédition. On passe par l'API de
# data.gouv.fr, qui donne l'adresse courante de la ressource.
SCRUTINS = [
    {"id": "presidentielle-2022-t1",
     "nom": "Présidentielle 2022, 1er tour", "etiquette": "Prés. 2022",
     "jeu": "election-presidentielle-des-10-et-24-avril-2022-"
            "resultats-definitifs-du-1er-tour",
     "motif": r"commune", "listes": False},
    {"id": "europeennes-2024",
     "nom": "Européennes 2024", "etiquette": "Eur. 2024",
     "jeu": "resultats-des-elections-europeennes-du-9-juin-2024",
     "motif": r"commune", "listes": False},
    {"id": "legislatives-2024-t1",
     "nom": "Législatives 2024, 1er tour", "etiquette": "Lég. 2024",
     "jeu": "elections-legislatives-des-30-juin-et-7-juillet-2024-"
            "resultats-definitifs-du-1er-tour",
     "motif": r"commune", "listes": False},
    {"id": "municipales-2026-t1",
     "nom": "Municipales 2026, 1er tour", "etiquette": "Mun. 2026",
     "jeu": "elections-municipales-2026-resultats-du-premier-tour",
     "motif": r"R[ée]sultats\s*-\s*Communes", "listes": True},
    {"id": "municipales-2026-t2",
     "nom": "Municipales 2026, 2nd tour", "etiquette": "Mun. 2026 T2",
     "jeu": "elections-municipales-2026-resultats-du-second-tour",
     "motif": r"R[ée]sultats\s*-\s*Communes", "listes": True},
]

# Le scrutin dont on publie le détail des listes : le plus récent parmi
# ceux dont la forme est vérifiée.
DETAIL = "municipales-2026-t1"

# En dessous, aucune chronique de participation : deux ou trois points
# ne dessinent pas une évolution.
SCRUTINS_MINIMUM = 4

# Taille des sondes de la dichotomie, et taille maximale d'un bloc
# départemental. Le bloc de l'Isère mesure 1,2 Mo dans le plus gros
# fichier ; dix mégaoctets laissent une marge confortable sans risquer
# de rapatrier le fichier entier par accident.
SONDE = 4096
BLOC_MAXIMUM = 10 * 1024 * 1024


# ══════════════════════════════════════════════════════════════════
# ACCÈS AUX FICHIERS
# ══════════════════════════════════════════════════════════════════

def lire_url(url, entetes=None):
    """Contenu brut d'une adresse, ou None. Sans reprise silencieuse."""
    attente = 3
    for tentative in range(1, TENTATIVES + 1):
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "portail-territorial/1.0",
                              **(entetes or {})})
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                return reponse.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentative < TENTATIVES:
                time.sleep(attente)
                attente *= 2
                continue
            print(f"    [HTTP {e.code}] {url[:80]}")
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if tentative < TENTATIVES:
                time.sleep(attente)
                attente *= 2
                continue
            print(f"    [{type(e).__name__}] {e}")
            return None
    return None


def ressource_du_scrutin(scrutin):
    """(adresse, titre, taille) du fichier communal d'un scrutin.

    Choisit, parmi les ressources CSV du jeu, celle dont le titre parle
    de communes — et la plus volumineuse en cas d'égalité, parce qu'un
    fichier communal pèse toujours plus qu'un fichier départemental.
    Le titre retenu est imprimé : c'est le seul moyen de voir qu'on a
    pris le bon.
    """
    brut = lire_url(API_DATAGOUV + scrutin["jeu"] + "/")
    if not brut:
        return None, None, 0
    try:
        jeu = json.loads(brut.decode("utf-8"))
    except json.JSONDecodeError:
        return None, None, 0

    motif = re.compile(scrutin["motif"], re.I)
    candidates = []
    for r in jeu.get("resources") or []:
        titre = str(r.get("title") or "")
        if str(r.get("format") or "").lower() != "csv" or not motif.search(titre):
            continue
        if re.search(r"bv|bureau|arrondissement|polyn[ée]sie", titre, re.I):
            continue
        extras = r.get("extras") or {}
        taille = int(extras.get("analysis:content-length")
                     or r.get("filesize") or 0)
        candidates.append((taille, titre, r.get("url")))
    if not candidates:
        return None, None, 0
    taille, titre, url = max(candidates)
    return url, titre, taille


def entete_de(url):
    """Première ligne du fichier, lue en une requête partielle."""
    brut = lire_url(url, {"Range": "bytes=0-8191"})
    if not brut:
        return None
    texte = brut.decode("utf-8-sig", errors="replace")
    return texte.split("\n", 1)[0].rstrip("\r")


def departement_a(url, position, taille):
    """Code de département lu juste après une position donnée.

    La première ligne d'une tranche est presque toujours coupée : on la
    jette et on lit la suivante. Si aucune ligne exploitable n'apparaît,
    on avance — c'est le cas près de la fin du fichier.
    """
    for _ in range(6):
        if position >= taille:
            return None
        fin = min(taille - 1, position + SONDE)
        brut = lire_url(url, {"Range": f"bytes={position}-{fin}"})
        if brut is None:
            return None
        texte = brut.decode("utf-8", errors="replace")
        for ligne in texte.split("\n")[1:]:
            champs = [c.strip().strip('"') for c in ligne.split(";")]
            if len(champs) > 4 and re.fullmatch(r"\d{2,3}|2[AB]", champs[0]):
                return champs[0]
        position += SONDE
    return None


def bloc_du_departement(url, taille, code):
    """Octets du fichier couvrant un département, par dichotomie.

    Renvoie (octets, nombre de sondes) ou (None, nombre de sondes).
    """
    sondes = 0

    def rang(valeur):
        # Les codes sont comparés comme des chaînes, car c'est ainsi
        # qu'ils sont triés dans le fichier : « 09 » avant « 10 ».
        return valeur

    bas, haut = 0, taille
    while haut - bas > 200000:
        milieu = (bas + haut) // 2
        d = departement_a(url, milieu, taille)
        sondes += 1
        if d is None:
            bas = milieu
            continue
        if rang(d) < rang(code):
            bas = milieu
        else:
            haut = milieu
    debut = bas

    bas2, haut2 = haut, taille
    while haut2 - bas2 > 200000:
        milieu = (bas2 + haut2) // 2
        d = departement_a(url, milieu, taille)
        sondes += 1
        if d is None:
            bas2 = milieu
            continue
        if rang(d) <= rang(code):
            bas2 = milieu
        else:
            haut2 = milieu
    fin = min(taille - 1, haut2)

    if fin - debut > BLOC_MAXIMUM:
        print(f"    [refusé] le bloc du département {code} ferait "
              f"{(fin - debut) / 1048576:.0f} Mo — le fichier n'est "
              f"probablement pas trié par département.")
        return None, sondes

    octets = lire_url(url, {"Range": f"bytes={debut}-{fin}"})
    return octets, sondes


# ══════════════════════════════════════════════════════════════════
# LECTURE DES LIGNES
# ══════════════════════════════════════════════════════════════════

def entier(valeur):
    try:
        return int(str(valeur).strip().replace(" ", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def pourcentage(valeur):
    """« 58,57% » → 58.57. None si illisible."""
    texte = str(valeur or "").strip().replace("%", "").replace(",", ".")
    try:
        return float(texte)
    except ValueError:
        return None


def lignes_du_bloc(octets, entete, codes_voulus):
    """Lignes du bloc concernant nos communes, en dictionnaires.

    L'en-tête vient du début du fichier, jamais du bloc : celui-ci
    commence au milieu des données. La première ligne du bloc est
    coupée et se jette.
    """
    texte = octets.decode("utf-8", errors="replace")
    corps = texte.split("\n", 1)[1] if "\n" in texte else ""
    colonnes = next(csv.reader(io.StringIO(entete), delimiter=";"))
    lecteur = csv.DictReader(io.StringIO(corps), fieldnames=colonnes,
                             delimiter=";")
    retenues, departements = {}, set()
    for ligne in lecteur:
        code = str(ligne.get("Code commune") or "").strip()
        departements.add(str(ligne.get("Code département") or "").strip())
        if code in codes_voulus:
            retenues[code] = ligne
    return retenues, departements


def participation_de(ligne):
    """Inscrits, votants, exprimés et taux, ou None si incohérent."""
    inscrits = entier(ligne.get("Inscrits"))
    votants = entier(ligne.get("Votants"))
    exprimes = entier(ligne.get("Exprimés"))
    if not inscrits or votants is None:
        return None
    # Un contrôle qui ne coûte rien et attrape une colonne décalée :
    # on ne peut pas voter plus de fois qu'il n'y a d'inscrits.
    if votants > inscrits:
        return None
    taux = pourcentage(ligne.get("% Votants"))
    if taux is None or not (0 <= taux <= 100):
        taux = round(100 * votants / inscrits, 2)
    return {"inscrits": inscrits, "votants": votants,
            "exprimes": exprimes, "taux": taux}


def listes_de(ligne):
    """Listes en présence, dans l'ordre des panneaux.

    Les colonnes sont repérées par leur suffixe numérique, jamais par
    leur position : le nombre de listes varie d'une commune à l'autre,
    et le fichier réserve autant de blocs que la commune la mieux
    pourvue en compte.
    """
    trouvees = []
    for rang in range(1, 60):
        libelle = (ligne.get(f"Libellé de liste {rang}")
                   or ligne.get(f"Libellé abrégé de liste {rang}")
                   or "").strip()
        voix = entier(ligne.get(f"Voix {rang}"))
        if not libelle and voix is None:
            continue
        if voix is None:
            continue
        trouvees.append({
            "libelle": libelle or f"Liste {rang}",
            "nuance": (ligne.get(f"Nuance liste {rang}") or "").strip(),
            "voix": voix,
            "part": pourcentage(ligne.get(f"% Voix/exprimés {rang}")),
            "sieges": entier(ligne.get(f"Sièges au CM {rang}")),
            "tete": " ".join(x for x in (
                (ligne.get(f"Prénom candidat {rang}") or "").strip(),
                (ligne.get(f"Nom candidat {rang}") or "").strip()) if x),
        })
    trouvees.sort(key=lambda l: -l["voix"])
    return trouvees


# ══════════════════════════════════════════════════════════════════
# MISE EN FORME
# ══════════════════════════════════════════════════════════════════

def nombre(valeur):
    try:
        return f"{int(valeur):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(valeur)


def taux_fr(valeur):
    return f"{valeur:.2f}".replace(".", ",") if valeur is not None else "—"


def mesure(valeur, unite, nom, **habillage):
    base = {"valeur": valeur, "unite": unite, "nom": nom,
            "obtention": "natif", "source": SOURCE, "licence": LICENCE,
            "format": "texte", "rubrique": RUBRIQUE,
            "sous_rubrique": SOUS_RUBRIQUE}
    base.update(habillage)
    return base


NOTE_NUANCES = (
    "Les nuances politiques sont attribuées par les services de l'État "
    "lors du dépôt des candidatures. Elles sont reprises telles quelles, "
    "sans interprétation.")


def bloc_scrutin(scrutin, part, listes):
    """Le détail d'un scrutin sur une commune."""
    details = {
        "Inscrits": nombre(part["inscrits"]),
        "Votants": f"{nombre(part['votants'])} — {taux_fr(part['taux'])} %",
    }
    if part.get("exprimes"):
        details["Suffrages exprimés"] = nombre(part["exprimes"])

    items = [{"titre": "Participation", "details": details,
              "etat": [scrutin["nom"], "neutre"], "texte": ""}]

    for l in listes:
        d = {"Voix": f"{nombre(l['voix'])}"
                     + (f" — {taux_fr(l['part'])} %" if l["part"] is not None
                        else "")}
        if l["nuance"]:
            d["Nuance"] = l["nuance"]
        if l["tete"]:
            d["Tête de liste"] = l["tete"]
        if l["sieges"]:
            d["Sièges au conseil municipal"] = str(l["sieges"])
        items.append({"titre": l["libelle"], "details": d,
                      "etat": (["Élue au 1er tour", "neutre"] if l["sieges"]
                               else ["", "neutre"]),
                      "texte": ""})

    note = f"Résultats définitifs — {scrutin['nom']}."
    if listes:
        note += " " + NOTE_NUANCES
    if len(listes) == 1:
        # Le piège de Rencurel : une liste unique obtient 100 % des
        # suffrages exprimés, ce qui est exact et ne veut rien dire
        # d'autre que « il n'y avait qu'une liste ».
        note += (" Une seule liste était en présence : son pourcentage "
                 "traduit l'absence de concurrence, non un plébiscite.")
    return {"rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
            "id": ANCRE, "titre": f"Résultats — {scrutin['nom']}",
            "items": items,
            "lien": {"url": f"https://www.data.gouv.fr/fr/datasets/"
                            f"{scrutin['jeu']}/",
                     "libelle": "Consulter la source"},
            "note": note}


def ecrire_vide(motif):
    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION, "source": SOURCE, "licence": LICENCE,
        "frequence": "annuelle", "motif_absence": motif,
        "communes": {}, "territoires": {},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Rien publié — {motif}")
    print(f"  Fichier écrit vide : {SORTIE}\n")


# ══════════════════════════════════════════════════════════════════

def collecter(scrutin, codes, departements_voulus, fichier_local=None):
    """Lignes d'un scrutin pour nos communes. None si le scrutin échoue."""
    print(f"\n  {scrutin['nom']}")

    if fichier_local:
        brut = Path(fichier_local).read_bytes()
        texte = brut.decode("utf-8-sig", errors="replace")
        entete = texte.split("\n", 1)[0].rstrip("\r")
        lignes, vus = lignes_du_bloc(b"\n" + brut, entete, codes)
        print(f"    fichier local, {len(lignes)} commune(s) retrouvée(s)")
        return lignes

    url, titre, taille = ressource_du_scrutin(scrutin)
    if not url:
        print("    [écarté] aucune ressource communale trouvée dans le jeu")
        return None
    print(f"    ressource : {titre}  ({taille / 1048576:.0f} Mo)")

    entete = entete_de(url)
    if not entete or "Code commune" not in entete:
        print("    [écarté] l'en-tête ne porte pas « Code commune » — "
              "la forme du fichier a changé")
        return None

    retenues, sondes_totales = {}, 0
    for departement in sorted(departements_voulus):
        octets, sondes = bloc_du_departement(url, taille, departement)
        sondes_totales += sondes
        if not octets:
            continue
        lignes, vus = lignes_du_bloc(octets, entete, codes)
        # Le contrôle de l'hypothèse : le bloc ne doit contenir que le
        # département cherché, à la ligne coupée près.
        etrangers = {d for d in vus if d and d != departement}
        if etrangers and len(etrangers) > 1:
            print(f"    [écarté] le bloc du {departement} contient aussi "
                  f"{', '.join(sorted(etrangers)[:4])} — le fichier n'est "
                  f"pas trié comme attendu")
            return None
        retenues.update(lignes)

    lu = sum(1 for _ in retenues)
    print(f"    {sondes_totales} sonde(s), {lu} commune(s) retrouvée(s) "
          f"sur {len(codes)}")
    return retenues


def main():
    print("\nRésultats électoraux par commune")
    print("─" * 60)
    print(f"  version {VERSION_SCRIPT} du script")

    if "--scrutins" in sys.argv:
        print(f"\n  {len(SCRUTINS)} scrutin(s) déclaré(s) :\n")
        for s in SCRUTINS:
            marque = "  [listes]" if s["listes"] else ""
            print(f"    {s['id']:26} {s['nom']}{marque}")
        print()
        return

    if not REFERENTIEL.exists():
        print(f"\n[ERREUR] {REFERENTIEL} introuvable.\n")
        sys.exit(1)

    reference = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    communes = reference["communes"]
    par_code = {c["code"]: c for c in communes}
    codes = set(par_code)
    departements = {c.get("code_departement") for c in communes
                    if c.get("code_departement")}
    cantons = {c.get("code_canton") for c in communes if c.get("code_canton")}
    codes_epci = {c.get("code_epci") for c in communes if c.get("code_epci")}

    fichier_local, un_seul = None, None
    if "--fichier" in sys.argv:
        i = sys.argv.index("--fichier")
        fichier_local = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    if "--scrutin" in sys.argv:
        i = sys.argv.index("--scrutin")
        un_seul = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

    resultats, retenus = {}, []
    for scrutin in SCRUTINS:
        if un_seul and scrutin["id"] != un_seul:
            continue
        lignes = collecter(scrutin, codes, departements, fichier_local)
        if not lignes:
            continue
        resultats[scrutin["id"]] = lignes
        retenus.append(scrutin)

    if not retenus:
        ecrire_vide("aucun scrutin n'a pu être lu")
        return

    # ── communes ─────────────────────────────────────────────────────
    sortie, sans_donnee = {}, []
    for code, commune in par_code.items():
        participations, mesures, blocs = {}, {}, []
        for scrutin in retenus:
            ligne = resultats[scrutin["id"]].get(code)
            if not ligne:
                continue
            part = participation_de(ligne)
            if not part:
                continue
            participations[scrutin["id"]] = part

            if scrutin["id"] == DETAIL:
                listes = listes_de(ligne) if scrutin["listes"] else []
                mesures["POL-10"] = mesure(
                    taux_fr(part["taux"]), "%",
                    "Participation", rang=10, ancre=ANCRE,
                    repere=f"{scrutin['nom']} · "
                           f"{nombre(part['votants'])} votants sur "
                           f"{nombre(part['inscrits'])} inscrits",
                    explication=("Part des inscrits qui se sont déplacés, "
                                 "au dernier scrutin municipal."))
                if listes:
                    premiere = listes[0]
                    mesures["POL-11"] = mesure(
                        premiere["libelle"], "", "Liste arrivée en tête",
                        rang=20, ancre=ANCRE,
                        repere=(f"{nombre(premiere['voix'])} voix"
                                + (f" — {taux_fr(premiere['part'])} %"
                                   if premiere["part"] is not None else "")
                                + (" · liste unique" if len(listes) == 1
                                   else f" · {len(listes)} listes en lice")),
                        explication=("Liste ayant obtenu le plus de "
                                     "suffrages exprimés." +
                                     (" Une seule liste était en présence."
                                      if len(listes) == 1 else "")))
                blocs.append(bloc_scrutin(scrutin, part, listes))

        if not participations:
            sans_donnee.append(commune["nom"])
            continue

        entree = {"mesures": mesures, "blocs": blocs}

        # ── chronique de participation ───────────────────────────────
        # Les étiquettes sont fournies : les scrutins ne tombent pas à
        # intervalle régulier, et aucune forme raisonnant sur un pas de
        # temps ne conviendrait. Mécanisme livré en version 33.
        ordonnes = [s for s in retenus if s["id"] in participations]
        if len(ordonnes) >= SCRUTINS_MINIMUM:
            entree["chroniques"] = [{
                "id": "participation",
                "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                "forme": "barres",
                "titre": "Participation aux derniers scrutins",
                "source": SOURCE, "licence": LICENCE,
                "unite": "%", "decimales": 1, "rang": 20,
                "note": ("Part des inscrits ayant voté. Les scrutins ne "
                         "sont pas comparables entre eux : une "
                         "municipale et une européenne ne mobilisent "
                         "pas le même électorat."),
                "etiquettes": [s["etiquette"] for s in ordonnes],
                "pas": "libre",
                "valeurs": [participations[s["id"]]["taux"]
                            for s in ordonnes],
                "agregation": "aucune",
            }]

        if mesures or blocs:
            sortie[code] = entree

    # ── canton et intercommunalité ───────────────────────────────────
    # La participation d'un territoire n'est pas la moyenne de celles de
    # ses communes : elle se recalcule sur les totaux, sans quoi un
    # village de trois cents habitants pèserait autant que
    # Saint-Marcellin.
    territoires = {}
    for niveau, identifiants in (("canton", cantons), ("epci", codes_epci)):
        for identifiant in identifiants:
            if niveau == "canton":
                membres = [c["code"] for c in communes
                           if c.get("code_canton") == identifiant]
            else:
                membres = [c["code"] for c in communes
                           if c.get("code_epci") == identifiant]
            # Un taux par scrutin, recalculé sur les totaux du
            # territoire. La chronique du canton ne peut donc pas venir
            # d'une somme des séries communales — un taux ne s'additionne
            # pas — et se construit ici, à partir des effectifs.
            taux_par_scrutin, couverture = {}, {}
            for s_ in retenus:
                ins = vot = 0
                n = 0
                for code in membres:
                    ligne = resultats[s_["id"]].get(code)
                    part = participation_de(ligne) if ligne else None
                    if not part:
                        continue
                    ins += part["inscrits"]
                    vot += part["votants"]
                    n += 1
                if ins:
                    taux_par_scrutin[s_["id"]] = round(100 * vot / ins, 2)
                    couverture[s_["id"]] = (n, vot, ins)

            scrutin = next((s for s in retenus if s["id"] == DETAIL), None)
            if not scrutin or scrutin["id"] not in taux_par_scrutin:
                continue
            couvertes, votants, inscrits = couverture[scrutin["id"]]
            taux = taux_par_scrutin[scrutin["id"]]
            territoires[f"{niveau}:{identifiant}"] = {
                "mesures": {
                    "POL-10": mesure(
                        taux_fr(taux), "%", "Participation", rang=10,
                        ancre=ANCRE,
                        repere=(f"{scrutin['nom']} · {nombre(votants)} "
                                f"votants sur {nombre(inscrits)} inscrits"),
                        explication=("Recalculée sur les totaux du "
                                     "territoire, et non moyennée entre "
                                     "communes : chaque électeur y pèse "
                                     "autant.")),
                },
                "blocs": [],
            }
            ordonnes = [s_ for s_ in retenus if s_["id"] in taux_par_scrutin]
            if len(ordonnes) >= SCRUTINS_MINIMUM:
                territoires[f"{niveau}:{identifiant}"]["chroniques"] = [{
                    "id": "participation",
                    "rubrique": RUBRIQUE, "sous_rubrique": SOUS_RUBRIQUE,
                    "forme": "barres",
                    "titre": "Participation aux derniers scrutins",
                    "source": SOURCE, "licence": LICENCE,
                    "unite": "%", "decimales": 1, "rang": 20,
                    "note": ("Part des inscrits ayant voté, recalculée sur "
                             "les totaux du territoire. Les scrutins ne "
                             "sont pas comparables entre eux : une "
                             "municipale et une européenne ne mobilisent "
                             "pas le même électorat."),
                    "etiquettes": [s_["etiquette"] for s_ in ordonnes],
                    "pas": "libre",
                    "valeurs": [taux_par_scrutin[s_["id"]] for s_ in ordonnes],
                    "agregation": "aucune",
                }]
            print(f"\n  {niveau} {identifiant} : participation {taux_fr(taux)} % "
                  f"({couvertes}/{len(membres)} communes)")

    DONNEES.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({
        "genere_le": date.today().isoformat(),
        "version": VERSION,
        "source": SOURCE, "licence": LICENCE, "frequence": "annuelle",
        "scrutins": [s["id"] for s in retenus],
        "scrutin_detaille": DETAIL,
        "communes": sortie,
        "territoires": territoires,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    avec_chronique = sum(1 for v in sortie.values() if v.get("chroniques"))
    print(f"\n  Scrutins retenus   : {len(retenus)} "
          f"({', '.join(s['id'] for s in retenus)})")
    print(f"  Communes servies   : {len(sortie)} sur {len(par_code)}")
    print(f"  Chroniques         : {avec_chronique}"
          + ("" if avec_chronique
             else f"  (il en faut {SCRUTINS_MINIMUM} pour en tracer une)"))
    if sans_donnee:
        print(f"  Sans résultat ({len(sans_donnee)}) : "
              f"{', '.join(sans_donnee[:6])}"
              + ("…" if len(sans_donnee) > 6 else ""))
    print(f"\n  Fichier : {SORTIE}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu.\n")
        sys.exit(130)
