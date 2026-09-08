"""
04_generation.py — Génération des pages HTML statiques
=======================================================

Transforme les fichiers publiés en v1 en pages HTML complètes, avec les
chiffres écrits dans le code source. Chaque territoire obtient sa propre
adresse, indexable par les moteurs de recherche :

    /                        page d'accueil (canton)
    /commune/38416/          Saint-Marcellin
    /canton/3823/            Le Sud Grésivaudan
    /epci/200070431/         Saint-Marcellin Vercors Isère
    /sitemap.xml             plan du site
    /assets/style.css        thème, fichier unique et remplaçable

Les fichiers JSON restent publiés : ils constituent le service de données
appelable par des sites tiers. Les pages HTML en sont une lecture.

Utilisation :
    python 04_generation.py
"""

import hashlib
import json
import math
import re
import shutil
import sys
import unicodedata
from datetime import date
from html import escape
from pathlib import Path

# Numéro de version du script, affiché à l'exécution : il permet
# de vérifier d'un coup d'œil que le fichier installé est le bon.
VERSION_SCRIPT = 29

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════

SITE = "https://territoire.sudgresiv.com"

# ══════════════════════════════════════════════════════════════════
# MENTIONS LÉGALES
#
# À COMPLÉTER AVANT TOUTE COMMUNICATION PUBLIQUE.
#
# La loi impose d'identifier l'éditeur d'un site accessible au public :
# nom ou raison sociale, adresse, moyen de contact, et hébergeur avec
# son adresse. Une page est produite dès que « editeur » est renseigné ;
# tant qu'il est vide, la page n'est pas générée et un rappel s'affiche
# à l'exécution.
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# SECTION D'ADMINISTRATION
#
# Page de suivi interne. Son adresse est volontairement peu devinable et
# n'est mentionnée nulle part : ni dans le plan du site, ni dans le
# robots.txt — ce dernier étant public, y inscrire le chemin reviendrait
# à l'annoncer —, ni dans aucun lien du site.
#
# Cela reste de la discrétion, pas de la protection : un hébergement
# statique n'offre aucune authentification. Pour protéger réellement ce
# dossier, ajoutez-lui un mot de passe depuis l'espace client OVH.
#
# Le nom du dossier respecte la casse sur l'hébergement : « Terri_Admin »
# et « terri_admin » désignent deux adresses différentes.
# ══════════════════════════════════════════════════════════════════

# Les majuscules sont volontaires : l'hébergement distingue la casse,
# ce qui écarte les balayages qui n'essaient que des noms en minuscules.
# Cette adresse sera appelée depuis les pages d'administration du site
# principal sudgresiv.com, non depuis le portail lui-même.
DOSSIER_ADMIN = "Terri_Admin"

# Sous-dossier de documentation, consultable depuis un téléphone par
# documents.php. Il reçoit les documents de travail du projet ; il ne
# doit recevoir ni clé, ni mot de passe, ni fichier de configuration —
# la protection du dossier parent ne dispense pas de cette règle.
DOSSIER_DOCUMENTS = "Documents"

# ══════════════════════════════════════════════════════════════════
# LEURRE
#
# L'ancienne adresse d'administration est conservée comme appât. Elle
# présente une fausse page de connexion, ne mène nulle part, et
# consigne les tentatives d'accès.
#
# L'adresse du visiteur est tronquée avant écriture : son dernier
# segment est retiré. Cela suffit à repérer un balayage automatisé sans
# identifier une personne, et évite de contredire l'engagement de ne
# collecter aucune donnée personnelle. Aucun identifiant ni mot de passe
# saisi n'est enregistré — les recueillir serait sans intérêt et
# juridiquement hasardeux.
# ══════════════════════════════════════════════════════════════════

DOSSIER_LEURRE = "administration"
JOURNAL_LEURRE = "journal-acces.log"
RETENTION_JOURNAL = 90        # jours conservés
DELAI_LEURRE = 3              # secondes d'attente imposées

# Fichier produit → libellé, script, commande de rafraîchissement.
SOURCES_SUIVIES = [
    ("referentiel-communes.json", "Référentiel des communes",
     "01_referentiel.py", "python lancer.py --complet", "annuelle"),
    ("mesures-eau.json", "Qualité de l'eau potable",
     "06_eau.py", "python 06_eau.py", None),
    ("mesures-secheresse.json", "Restrictions sécheresse",
     "07_vigieau.py", "python 07_vigieau.py", None),
    ("mesures-risques.json", "Risques et catastrophes naturelles",
     "08_georisques.py", "python 08_georisques.py", None),
    ("mesures-nappes.json", "Niveau des nappes",
     "09_nappes.py", "python 09_nappes.py", None),
    ("mesures-rivieres.json", "Débit des cours d'eau",
     "12_rivieres.py", "python 12_rivieres.py", None),
    ("mesures-ecoles.json", "Établissements scolaires",
     "10_ecoles.py", "python 10_ecoles.py", None),
    ("mesures-population.json", "Population, logement, équipements",
     "11_population.py", "python 11_population.py", None),
    ("mesures-hivernal.json", "Équipements hivernaux (saisi à la main)",
     "13_hivernal.py", "python 13_hivernal.py", None),
    ("mesures-vigilance.json", "Vigilance météorologique",
     "14_vigilance.py", "python 14_vigilance.py", None),
    ("mesures-elus.json", "Élus locaux",
     "15_elus.py", "python 15_elus.py", None),
    ("mesures-bio.json", "Agriculture biologique",
     "16_bio.py", "python 16_bio.py", None),
]

# Référentiels transcrits depuis un document officiel. Ils ne se
# rafraîchissent pas tout seuls : leur date de validité est la seule
# garantie contre une information périmée.
REFERENTIELS_SAISIS = [
    ("reference-equipements-hivernaux.json",
     "Équipements hivernaux — arrêté préfectoral"),
]

# Ancienneté au-delà de laquelle une source est à rafraîchir, en jours.
TOLERANCE_FRAICHEUR = {
    "quotidienne": 2, "hebdomadaire": 10, "mensuelle": 45,
    "trimestrielle": 120, "annuelle": 400,
}

# Rubriques annoncées mais pas encore alimentées.
CHANTIERS = [
    ("Automatisation des collectes", "GitHub Actions",
     "Prérequis des carburants, dont la donnée se périme en heures."),
    ("Prix des carburants", "data.economie.gouv.fr",
     "Rubrique dédiée, plus un résumé dans Transports."),
    ("Résultats électoraux", "ministère de l'Intérieur",
     "Historique depuis 2000, puis direct le soir des scrutins."),
    ("Espaces naturels protégés", "INPN",
     "En attente : serveurs du Muséum hors service."),
    ("Prix de l'eau et assainissement", "SISPEA",
     "L'API Hub'Eau correspondante a été arrêtée."),
]

MENTIONS = {
    "editeur": "Fabrice Lafont",          # nom, prénom ou raison sociale
    "statut": "Particulier",              # ex. « entrepreneur individuel »
    "siret": "",                          # vide : la ligne n'est pas produite
    "adresse": "Rue Ampère, 38160 Saint-Marcellin",
    "courriel": "contact@sudgresiv.com",
    "directeur": "Fabrice Lafont",        # directeur de la publication
    "hebergeur": ("OVH SAS, 2 rue Kellermann, 59100 Roubaix, France — "
                  "ovhcloud.com"),
}
# ══════════════════════════════════════════════════════════════════
# MESURE D'AUDIENCE
#
# Identifiant Google Analytics 4. **Vide, rien n'est ajouté au site** :
# ni script, ni bandeau, et les mentions légales restent celles d'un
# site sans traceur. C'est le seul interrupteur.
#
# Quand il est renseigné, la règle appliquée est stricte : le script de
# Google n'est PAS chargé tant que le visiteur n'a pas accepté. Un refus,
# ou l'absence de réponse, ne charge rien du tout. C'est ce que demande
# l'article 82 de la loi Informatique et Libertés pour un traceur qui
# n'est pas strictement nécessaire au service.
#
# Trois conséquences, assumées :
#   · le choix du visiteur est conservé dans son navigateur — cette
#     conservation-là est dispensée de consentement, elle sert à ne pas
#     lui reposer la question ;
#   · sans JavaScript, aucun bandeau et aucune mesure : le défaut est le
#     silence, jamais le suivi ;
#   · les signaux publicitaires de Google sont désactivés à la
#     configuration, la mesure se limite à l'audience.
# ══════════════════════════════════════════════════════════════════

ANALYTICS = "G-ER3H1G7XSP"

TITRE_SITE = "Sud Grésiv'"
SOUS_TITRE = "Données publiques du territoire"

RACINE = Path(".")
PUBLIE = RACINE / "data" / "publie" / "v1"
ASSETS = RACINE / "assets"
# Territoire mis en avant sur l'accueil, pour ses chiffres clés.
ACCUEIL = ("canton", "3823")

# Empreinte du thème et du script : ajoutée aux adresses des ressources
# pour que les navigateurs rechargent d'eux-mêmes après chaque génération.
EMPREINTE = ""

LIBELLE = {"commune": "Commune", "canton": "Canton",
           "epci": "Intercommunalité", "departement": "Département"}


# ══════════════════════════════════════════════════════════════════
# THÈME — fichier unique. Le remplacer rhabille tout le site.
# ══════════════════════════════════════════════════════════════════

CSS = """
:root{
  --paper:#EDF0EA; --surface:#FFF; --sunken:#F5F7F3;
  --ink:#16211C; --soft:#5D6E64; --dim:#9AA79F; --line:#D5DCD3;
  --accent:#2C6B4C; --accent-soft:#EAF3EE; --link:#2A6F97; --mark:#9C8340;
  --attention:#B4610E; --attention-soft:#FBF0E4;
  --alerte:#A32C1B; --alerte-soft:#FBEAE7;
  --font-display:"Barlow Condensed",sans-serif;
  --font-body:"IBM Plex Sans",system-ui,sans-serif;

  /* Icônes. Taille exprimée en em : elles suivent la police du texte
     qui les accompagne. Couleur héritée par défaut ; remplacez
     currentColor par une teinte fixe pour les distinguer du libellé. */
  --ico-taille:1.25em;
  --ico-couleur:currentColor;
  --ico-trait:1.5;
  --font-data:"IBM Plex Mono",monospace;
  --radius:3px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--font-body);
  font-size:15px;line-height:1.5}
a{color:inherit;text-decoration:none}
button,input{font:inherit;color:inherit}
button{background:none;border:none;cursor:pointer}
:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
.dsp{font-family:var(--font-display);font-weight:600;text-transform:uppercase;
  letter-spacing:.09em}

.top{position:sticky;top:0;z-index:20;background:var(--surface);
  border-bottom:1px solid var(--line)}
.top .wrap{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
  gap:18px;min-height:60px;padding:8px 20px}
.logo{font-family:var(--font-display);font-weight:600;font-size:19px;
  white-space:nowrap;justify-self:start}
.find-groupe{display:flex;align-items:center;gap:10px;justify-self:center}
.find-label{font-family:var(--font-display);font-weight:600;
  text-transform:uppercase;letter-spacing:.09em;font-size:11px;
  color:var(--soft);white-space:nowrap;cursor:pointer}
.find{position:relative;width:340px;max-width:44vw}
.find input{width:100%;height:36px;padding:0 12px;background:var(--sunken);
  border:1px solid var(--line);border-radius:var(--radius);font-size:14px}
.find input::placeholder{color:var(--dim)}
.find input:focus{border-color:var(--accent);background:var(--surface);outline:none}
.hits{position:absolute;top:40px;left:0;right:0;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:0 10px 26px rgba(0,0,0,.13);max-height:300px;overflow:auto;
  display:none;z-index:30}
.hits.on{display:block}
.hits a{display:flex;gap:10px;align-items:center;padding:8px 12px;
  border-bottom:1px solid var(--line)}
.hits a:last-child{border-bottom:none}
.hits a:hover{background:var(--sunken)}
.tag{font-size:10px;padding:2px 6px;border-radius:var(--radius);
  background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.hits .nm{flex:1;font-size:14px}
.hits .cd{font-family:var(--font-data);font-size:11px;color:var(--dim)}
.vide{padding:8px 12px;font-size:13px;color:var(--dim)}

.terr{background:var(--surface);border-bottom:1px solid var(--line);
  position:sticky;top:var(--h-top,61px);z-index:19}
.terr .wrap{padding:24px 20px;transition:padding .16s ease;
  display:flex;align-items:center;justify-content:space-between;gap:24px}
.terr-identite{min-width:0}

/* Rappel des territoires de rattachement, à droite du nom.
   Taille voisine du tiers du titre, alignée à droite, centrée
   verticalement sur le bloc d'identité. */
.terr-parents{text-align:right;flex-shrink:0;display:flex;
  flex-direction:column;gap:3px;font-size:15px;line-height:1.3}
.terr-parents .p-ligne{display:block;color:var(--ink)}
.terr-parents .p-role{display:block;font-family:var(--font-display);
  font-weight:600;text-transform:uppercase;letter-spacing:.09em;
  font-size:10px;color:var(--dim);line-height:1.4}
.terr-parents a{color:inherit;border-bottom:1px solid transparent}
.terr-parents a:hover{color:var(--accent);border-bottom-color:currentColor}
.terr h1{transition:font-size .16s ease}
.terr.compact .wrap{padding-top:5px;padding-bottom:6px}
.terr.compact h1{font-size:20px}
.terr.compact .kind{font-size:10px}
.terr.compact .sub{margin-top:1px;font-size:12px}
.terr.compact .terr-parents{font-size:12px;gap:0}
.terr.compact .terr-parents .p-role{font-size:9px;line-height:1.2}
.terr .kind{font-size:11px;color:var(--soft)}
.terr h1{font-family:var(--font-display);font-size:34px;line-height:1.05;
  text-transform:none;letter-spacing:.01em;font-weight:600}
.terr .sub{font-size:13px;color:var(--soft);margin-top:4px}

.nav{background:var(--paper);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;gap:2px;padding:0 20px;overflow-x:auto;
  scrollbar-width:thin}
.ico{width:var(--ico-taille);height:var(--ico-taille);flex-shrink:0;
  color:var(--ico-couleur);stroke-width:var(--ico-trait)}
.ico.petit{width:calc(var(--ico-taille) * .85);
  height:calc(var(--ico-taille) * .85)}

.nav-item{display:inline-flex;align-items:center;gap:7px;white-space:nowrap;
  padding:10px 14px;font-size:14px;color:var(--soft);
  border-bottom:2px solid transparent;
  transition:color .12s,border-color .12s,background .12s}
.nav-item .ico{opacity:.75}
.nav-item.actif .ico,a.nav-item:hover .ico{opacity:1}
a.nav-item:hover{color:var(--accent);background:var(--accent-soft)}
.nav-item.actif{color:var(--accent);border-bottom-color:var(--accent);
  font-weight:600}
.nav-item.vide{color:var(--dim);cursor:default}

.sous-nav{background:var(--surface);border-bottom:1px solid var(--line)}
.sous-nav .wrap{display:flex;gap:4px;padding:0 20px;overflow-x:auto}
.sous-item{display:inline-flex;align-items:center;gap:6px;
  white-space:nowrap;padding:7px 12px;
  font-size:13px;color:var(--soft);border-radius:var(--radius);
  margin:6px 0;transition:background .12s,color .12s}
a.sous-item:hover{background:var(--accent-soft);color:var(--accent)}
.sous-item.actif{background:var(--accent);color:var(--surface);font-weight:600}

main .wrap{padding:26px 20px 48px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;gap:8px}
.card .id{font-family:var(--font-data);font-size:10px;color:var(--dim)}
.card h2{font-size:15px;font-weight:600;line-height:1.25}
.card .v{font-family:var(--font-data);font-size:28px;color:var(--accent);line-height:1}
.card .u{font-size:12px;color:var(--soft)}
.card footer{margin-top:auto;border-top:1px solid var(--line);padding-top:8px;
  display:flex;gap:6px;flex-wrap:wrap;font-size:10px;color:var(--soft)}
/* Bandeaux d'alerte : compacts, un ou deux par ligne selon leur nombre. */
.alertes{display:grid;grid-template-columns:1fr;gap:12px;margin-bottom:12px}
.alertes.deux-colonnes{grid-template-columns:repeat(2,1fr)}
.card.pleine{gap:6px;padding:13px 16px}
.card-tete{display:flex;align-items:center;gap:9px}
.card-tete .ico{color:var(--accent);opacity:.6}
.card-tete .id{margin-left:auto}
.card.pleine .card-tete h2{font-size:15px;flex:1}
.card.pleine .card-tete .id{margin-left:0}
.card.ton-attention .card-tete .ico{color:var(--attention);opacity:1}
.card.ton-alerte .card-tete .ico{color:var(--alerte);opacity:1}
.card.pleine .v{font-size:22px;line-height:1.15}
.card.pleine .card-expl{margin-top:2px}
.card.pleine footer{padding-top:6px}
.card.ton-attention{background:var(--attention-soft);border-color:var(--attention)}
.card.ton-attention .v{color:var(--attention)}
.card.ton-alerte{background:var(--alerte-soft);border-color:var(--alerte);
  border-width:2px}
.card.ton-alerte .v{color:var(--alerte)}
.card-repere{font-size:11px;color:var(--ink);font-family:var(--font-data);
  background:var(--sunken);border:1px solid var(--line);border-radius:var(--radius);
  padding:3px 8px;align-self:flex-start;line-height:1.4}
.card.ton-attention .card-repere{background:var(--surface);border-color:var(--attention)}
.card.ton-alerte .card-repere{background:var(--surface);border-color:var(--alerte)}
.card-expl{font-size:12px;color:var(--soft);line-height:1.45}
.card-lien{display:inline-block;font-size:12px;color:var(--link);
  border-bottom:1px solid currentColor;align-self:flex-start}
.card-lien:hover{color:var(--accent)}
.card.ton-alerte .card-lien{color:var(--alerte)}
.card.ton-attention .card-lien{color:var(--attention)}
.bloc{scroll-margin-top:calc(var(--h-top,61px) + 84px)}
.pill{border:1px solid var(--line);border-radius:var(--radius);padding:1px 6px}

.carte-bloc{margin-top:22px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px}
.carte-bloc .dsp{font-family:var(--font-body);font-size:15px;font-weight:600;
  text-transform:none;letter-spacing:0;color:var(--ink);display:block;
  margin-bottom:12px}
.carte-fonds{display:flex;gap:2px;margin-bottom:10px;flex-wrap:wrap}
.carte-fonds .opt{display:flex;align-items:center;gap:7px;padding:6px 11px;
  font-size:13px;border:1px solid var(--line);border-radius:var(--radius);
  cursor:pointer;background:var(--sunken)}
.carte-fonds .opt:hover{background:var(--surface)}
.carte-fonds .opt input{accent-color:var(--accent);margin:0}
.carte-fonds .opt:has(input:checked){background:var(--accent);
  color:var(--surface);border-color:var(--accent);font-weight:600}
.carte-fonds .bascule{margin-left:auto}
.carte-fonds .bascule:has(input:checked){background:var(--sunken);
  color:var(--ink);border-color:var(--line);font-weight:400}

.carte-cadre{position:relative;width:100%;overflow:hidden;
  border-radius:var(--radius);background:var(--sunken)}
.carte-fond{position:absolute;inset:0;display:none}
.carte-fond img{position:absolute;display:block}
.carte-cadre[data-fond="plan"] .carte-fond[data-fond="plan"],
.carte-cadre[data-fond="photo"] .carte-fond[data-fond="photo"]{display:block}

svg.carte{display:block;width:100%;height:auto;position:relative}

.carte-credits{font-size:11px;color:var(--dim);margin-top:6px;text-align:right}
.carte-credit{display:none}
.carte-credit[data-credit="schema"]{display:inline}
.carte-bloc[data-fond="plan"] .carte-credit[data-credit="plan"],
.carte-bloc[data-fond="photo"] .carte-credit[data-credit="photo"]{display:inline}
.carte-bloc[data-fond="plan"] .carte-credit[data-credit="schema"],
.carte-bloc[data-fond="photo"] .carte-credit[data-credit="schema"]{display:none}
svg.carte a{cursor:pointer}
svg.carte .c-voisine{fill:var(--sunken);stroke:var(--line);stroke-width:.8;
  transition:fill .12s,stroke .12s}
svg.carte a:hover .c-voisine,svg.carte a:focus .c-voisine{
  fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.4}
svg.carte a:focus{outline:none}
svg.carte .c-ici{fill:var(--accent);stroke:var(--accent);stroke-width:1.2;
  fill-opacity:.85}
.carte-legende{font-size:14px;color:var(--soft);margin-top:10px;line-height:1.45}
.carte-bulle{position:fixed;z-index:50;display:none;pointer-events:none;
  background:var(--ink);color:var(--surface);font-size:12px;line-height:1.3;
  padding:4px 9px;border-radius:var(--radius);white-space:nowrap;
  box-shadow:0 4px 14px rgba(0,0,0,.22)}
.carte-bulle.on{display:block}
.carte-bulle b{display:block;font-size:13px}
.carte-bulle i{font-style:normal;color:var(--accent-soft)}

.carte-grille{display:grid;grid-template-columns:172px 1fr;gap:16px;align-items:start}
.carte-menu{display:flex;flex-direction:column;gap:2px;border:1px solid var(--line);
  border-radius:var(--radius);padding:6px;background:var(--sunken)}
.carte-menu .opt{display:flex;align-items:center;gap:8px;padding:7px 9px;
  font-size:13px;border-radius:var(--radius);cursor:pointer}
.carte-menu .opt:hover{background:var(--surface)}
.carte-menu .opt input{accent-color:var(--accent);margin:0}
.carte-menu .opt:has(input:checked){background:var(--accent);color:var(--surface);
  font-weight:600}

.carte-echelle{display:flex;align-items:center;gap:3px;margin-top:10px;
  font-size:11px;color:var(--soft)}
.carte-echelle .pal{width:26px;height:11px;border:1px solid var(--line);
  background:var(--accent)}
.carte-echelle .unite{margin-left:auto;font-family:var(--font-data);
  font-size:18px;font-weight:500;color:var(--ink)}
.carte-echelle .bas{margin-right:4px}
.carte-echelle .haut{margin-left:4px}

svg.carte .n0,.carte-echelle .n0{fill-opacity:.14;opacity:.14}
svg.carte .n1,.carte-echelle .n1{fill-opacity:.32;opacity:.32}
svg.carte .n2,.carte-echelle .n2{fill-opacity:.52;opacity:.52}
svg.carte .n3,.carte-echelle .n3{fill-opacity:.74;opacity:.74}
svg.carte .n4,.carte-echelle .n4{fill-opacity:1;opacity:1}
svg.carte path.n0,svg.carte path.n1,svg.carte path.n2,
svg.carte path.n3,svg.carte path.n4{fill:var(--accent);stroke:var(--surface);
  stroke-width:.8}
svg.carte path.nd{fill:var(--sunken);stroke:var(--line)}

/* Noms de communes : cerclés d'un liseré pour rester lisibles au-dessus
   d'un fond de plan comme d'un aplat de couleur. Ils ne captent pas le
   pointeur, afin de ne pas gêner le survol ni les liens. */
/* Points d'intérêt : établissements, équipements. Cerclés de la couleur
   du fond pour rester visibles sur un aplat comme sur une photo. */
svg.carte .c-point{fill:var(--link);stroke:var(--surface);stroke-width:1.6;
  cursor:help}
svg.carte .c-point.second{fill:var(--mark)}
svg.carte .c-point:hover{stroke:var(--ink);stroke-width:2.2}
.carte-cadre[data-fond="photo"] svg.carte .c-point{stroke:#fff;stroke-width:2}

svg.carte .c-noms{pointer-events:none}
svg.carte .c-nom{fill:var(--ink);font-family:var(--font-body);font-weight:500;
  paint-order:stroke;stroke:var(--surface);stroke-width:3;
  stroke-linejoin:round}
svg.carte .c-nom.principal{font-weight:600;fill:var(--accent)}
.carte-cadre[data-fond] svg.carte .c-nom{stroke-width:3.5}
.carte-cadre[data-fond="photo"] svg.carte .c-nom{fill:#111;stroke:#fff}
.carte-cadre.sans-noms svg.carte .c-noms{display:none}

/* Avec un fond de plan, le dessin s'efface : contours seuls pour les
   voisines, remplissage translucide pour la commune mise en avant,
   afin que la carte reste lisible dessous. */
/* Sur un fond de plan, les limites communales doivent rester nettes :
   trait sombre appuyé, doublé d'un halo clair pour ressortir aussi bien
   sur une zone urbaine dense que sur une forêt. */
.carte-cadre[data-fond] svg.carte .c-formes{
  filter:drop-shadow(0 0 1.5px rgba(255,255,255,.95))}
.carte-cadre[data-fond] svg.carte .c-voisine{fill:none;stroke:var(--ink);
  stroke-width:1.7;stroke-opacity:.95;stroke-linejoin:round}
.carte-cadre[data-fond] svg.carte a:hover .c-voisine{fill:var(--accent);
  fill-opacity:.3;stroke-width:2.4}
.carte-cadre[data-fond] svg.carte .c-ici{fill:var(--accent);fill-opacity:.28;
  stroke:var(--accent);stroke-width:3.2;stroke-opacity:1}
.carte-cadre[data-fond] svg.carte path[class*="n"]{fill-opacity:.45;
  stroke:var(--ink);stroke-width:1.4;stroke-opacity:.85}
.carte-cadre[data-fond="photo"] svg.carte .c-voisine{stroke:#fff;
  stroke-opacity:1}
.carte-cadre[data-fond="photo"] svg.carte .c-formes{
  filter:drop-shadow(0 0 2px rgba(0,0,0,.85))}
svg.carte a:hover path[class*="n"],svg.carte a:focus path[class*="n"]{
  stroke:var(--ink);stroke-width:2;fill-opacity:1}

.bl-grille.pleine{grid-template-columns:1fr}
.bl-grille.pleine .bl-texte{font-size:14px;color:var(--ink);
  column-count:2;column-gap:28px}

/* Chiffres clés : une bande sobre, sans cadre, pour éviter l'effet
   de tableau brut. Le nombre porte l'accent, le pictogramme discret
   annonce le thème. */
.chiffres{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;
  margin-top:22px;background:var(--line);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden}
.chiffre{background:var(--surface);padding:22px 18px;text-align:center}
.chiffre .ico{width:calc(var(--ico-taille) * 1.9);
  height:calc(var(--ico-taille) * 1.9);color:var(--accent);opacity:.55;
  margin-bottom:8px}
.chiffre-v{font-family:var(--font-data);font-size:30px;font-weight:500;
  line-height:1;color:var(--ink);font-variant-numeric:tabular-nums}
.chiffre-k{font-family:var(--font-display);text-transform:uppercase;
  letter-spacing:.1em;font-size:11px;color:var(--soft);margin-top:7px}

.bloc{margin-top:22px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px}
.bloc > .dsp,.ratt > .dsp,.carte-bloc .dsp{font-family:var(--font-body);
  font-size:15px;font-weight:600;text-transform:none;letter-spacing:0;
  color:var(--ink);display:flex;align-items:center;gap:9px;
  margin-bottom:12px}
.bloc > .dsp .ico,.ratt > .dsp .ico,.carte-bloc .dsp .ico{
  color:var(--accent);opacity:.6}
.bl-grille{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.bl-item{border:1px solid var(--line);border-radius:var(--radius);
  padding:13px 14px;background:var(--sunken)}
.bl-item header{display:flex;align-items:flex-start;justify-content:space-between;
  gap:10px;margin-bottom:9px}
.bl-item h3{font-size:14px;font-weight:600;line-height:1.3}
.bl-etat{font-size:10px;font-weight:600;padding:3px 8px;border-radius:var(--radius);
  white-space:nowrap;text-transform:uppercase;letter-spacing:.05em}
.bl-etat.ok{background:var(--accent);color:var(--surface)}
.bl-etat.alerte{background:var(--alerte);color:var(--surface)}
.bl-etat.attention{background:var(--attention);color:var(--surface)}
.bl-etat.neutre{background:var(--line);color:var(--soft)}
.bl-ligne{display:flex;justify-content:space-between;gap:12px;font-size:13px;
  padding:3px 0;border-top:1px solid var(--line)}
.bl-ligne:first-of-type{border-top:none}
.bl-cle{color:var(--soft)}
.bl-val{font-family:var(--font-data);text-align:right}
.bl-texte{font-size:12px;color:var(--soft);margin-top:9px;line-height:1.45}
.bl-lien{display:inline-block;margin-top:9px;font-size:12px;color:var(--link);
  border-bottom:1px solid currentColor}
.bl-lien:hover{color:var(--accent)}
.bl-source{margin-top:12px}
.bl-source a{font-size:13px;color:var(--link);border-bottom:1px solid currentColor}
.bl-source a:hover{color:var(--accent)}
.bl-item .chips{margin-top:10px}
.bl-item .chip{background:var(--surface)}
.bl-note{font-size:12px;color:var(--soft);margin-top:12px;
  border-left:2px solid var(--mark);padding:6px 11px;background:var(--sunken);
  border-radius:var(--radius)}

.ratt{margin-bottom:26px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:20px}
.ratt > .dsp{font-family:var(--font-body);font-size:15px;font-weight:600;
  text-transform:none;letter-spacing:0;color:var(--ink);display:block;
  margin-bottom:14px}
.spine{position:relative;padding-left:30px}
.spine::before{content:"";position:absolute;left:9px;top:8px;bottom:8px;width:1px;
  background:repeating-linear-gradient(to bottom,var(--mark) 0 3px,transparent 3px 7px)}
.rung{position:relative;padding:10px 0;display:flex;flex-wrap:wrap;gap:10px;
  align-items:center}
.rung::before{content:"";position:absolute;left:-21px;top:50%;width:13px;height:1px;
  background:var(--mark)}
.rung::after{content:"";position:absolute;left:-24px;top:calc(50% - 3px);
  width:7px;height:7px;border-radius:50%;background:var(--surface);
  border:1px solid var(--mark)}
.rung.ici::after{background:var(--accent);border-color:var(--accent)}
.rung .lvl{font-family:var(--font-display);text-transform:uppercase;
  letter-spacing:.08em;font-size:11px;color:var(--soft);width:96px;flex-shrink:0}
.chips{display:flex;flex-wrap:wrap;gap:5px}

/* Rubrique rappelée dans le titre de premier niveau. Discrète à l'œil,
   décisive pour un moteur : c'est elle qui distingue les quinze pages
   d'un même territoire. */
.h1-rub{font-weight:400;color:var(--soft);white-space:nowrap}

/* Repli de la liste des communes. Balise details native : elle
   fonctionne sans JavaScript, se pilote au clavier et laisse les liens
   dans la page. Le marqueur par défaut du navigateur est masqué au
   profit d'un triangle qui pivote à l'ouverture. */
.repli{flex:1 1 100%}
.repli > summary{display:inline-flex;align-items:center;gap:7px;
  cursor:pointer;font-size:13px;color:var(--link);list-style:none;
  padding:3px 0}
.repli > summary::-webkit-details-marker{display:none}
.repli > summary::before{content:"";width:0;height:0;
  border-left:5px solid currentColor;border-top:4px solid transparent;
  border-bottom:4px solid transparent;transition:transform .15s}
.repli[open] > summary::before{transform:rotate(90deg)}
.repli > summary:hover{text-decoration:underline}
.repli .chips{margin-top:10px}
.repli-moins{display:none}
.repli[open] .repli-plus{display:none}
.repli[open] .repli-moins{display:inline}
.chip{border:1px solid var(--line);border-radius:var(--radius);padding:4px 10px;
  font-size:13px;display:inline-block}
a.chip{transition:background .12s,color .12s,border-color .12s}
a.chip:hover,a.chip:focus-visible{background:var(--accent);color:var(--surface);
  border-color:var(--accent);font-weight:600}
.chip.now{background:var(--accent-soft);border-color:var(--accent);
  color:var(--accent);font-weight:600}
.note{margin-top:14px;border-left:2px solid var(--mark);padding:8px 12px;
  font-size:12px;color:var(--soft);background:var(--sunken);border-radius:var(--radius)}

footer.site{border-top:1px solid var(--line);background:var(--surface);
  padding:18px 0;font-size:11px;color:var(--soft)}
footer.site a{color:var(--link)}

/* Bandeau de consentement à la mesure d'audience. Masqué tant que le
   script ne l'a pas révélé : sans JavaScript, il n'y a ni bandeau ni
   mesure — le défaut est le silence. */
.mesure{position:fixed;left:0;right:0;bottom:0;z-index:50;
  background:var(--surface);border-top:2px solid var(--accent);
  box-shadow:0 -2px 14px rgba(22,33,28,.12)}
.mesure .wrap{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
  justify-content:space-between;padding:14px 20px}
.mesure p{margin:0;font-size:13px;line-height:1.5;color:var(--soft);
  max-width:62ch}
.mesure-choix{display:flex;gap:9px;flex-shrink:0}
.mesure-btn{font:inherit;font-size:13px;font-weight:600;cursor:pointer;
  padding:8px 18px;border-radius:3px;border:1px solid var(--line);
  background:var(--sunken);color:var(--ink)}
.mesure-btn:hover{border-color:var(--soft)}
.mesure-btn.oui{background:var(--accent);border-color:var(--accent);
  color:#fff}
.mesure-btn.oui:hover{background:#245a3f}
@media(max-width:640px){
  .mesure .wrap{padding:12px 16px}
  .mesure-choix{width:100%}
  .mesure-btn{flex:1 1 0}
}

/* Raccourcis sous le titre d'une page d'administration. Les classes
   .hd et .n n'ont pas de style propre : sans cette règle, un lien y
   serait indiscernable du texte, puisque « a » hérite de la couleur
   courante partout ailleurs sur le site. */
.hd .n a{color:var(--link);border-bottom:1px solid rgba(42,111,151,.35)}
.hd .n a:hover{border-bottom-color:var(--link)}

@media(max-width:820px){
  .cards{grid-template-columns:repeat(2,1fr)}
  .alertes.deux-colonnes{grid-template-columns:1fr}
}
@media(max-width:700px){
  .carte-grille{grid-template-columns:1fr}
  .carte-menu{flex-direction:row;flex-wrap:wrap}
  .carte-menu .opt{font-size:12px;padding:6px 8px}
}
@media(max-width:640px){
  .nav .wrap{padding:0 12px}
  .nav-item{padding:10px 11px;font-size:13px}
  .sous-nav .wrap{padding:0 12px}
  .sous-item{padding:7px 10px;font-size:12px}
  .top .wrap{grid-template-columns:1fr;gap:8px;justify-items:stretch}
  .logo{justify-self:center}
  .find-groupe{justify-self:stretch}
  .find{width:auto;max-width:none;flex:1}
  .top-fin{display:none}
}
@media(max-width:700px){
  .terr .wrap{flex-direction:column;align-items:flex-start;gap:10px}
  .terr-parents{text-align:left;flex-direction:row;flex-wrap:wrap;
    gap:6px 18px;font-size:13px}
  .terr-parents .p-role{display:inline;font-size:10px;margin-right:5px}
  .terr.compact .terr-parents{font-size:12px}
}
@media(max-width:700px){
  .bl-grille.pleine .bl-texte{column-count:1}
}
@media(max-width:560px){
  .chiffres{grid-template-columns:1fr}
  .bl-grille{grid-template-columns:1fr}
  .cards{grid-template-columns:1fr}
  .terr h1{font-size:27px}
  .rung .lvl{width:100%}
}
"""

# ══════════════════════════════════════════════════════════════════
# RECHERCHE — seul JavaScript de la page. Le contenu existe sans lui.
# ══════════════════════════════════════════════════════════════════

JS = """
(function(){
  var champ = document.getElementById('q');
  var boite = document.getElementById('hits');
  if(!champ) return;
  var index = null;

  fetch(BASE + '/assets/recherche.json')
    .then(function(r){ return r.json(); })
    .then(function(d){ index = d; })
    .catch(function(){ champ.placeholder = 'Recherche indisponible'; });

  function sansAccents(t){
    return t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  // Deux groupes seulement : ce qui commence par la saisie, puis le reste.
  // À l'intérieur de chaque groupe, l'ordre alphabétique s'applique.
  function score(t, v){
    var nom = sansAccents(t.nom);
    if(nom.indexOf(v) === 0) return 0;
    if(nom.indexOf(v) !== -1) return 1;
    if(t.code.indexOf(v) === 0) return 1;
    var cp = (t.codes_postaux || []).some(function(c){ return c.indexOf(v) === 0; });
    if(cp) return 1;
    return -1;
  }

  var LIMITE = 20;

  champ.addEventListener('input', function(){
    var v = sansAccents(champ.value.trim());
    if(!v || !index){ boite.className = 'hits'; return; }

    var trouves = [];
    for(var i = 0; i < index.length; i++){
      var s = score(index[i], v);
      if(s >= 0) trouves.push({ t: index[i], s: s });
    }

    // Les noms commençant par la saisie remontent en tête ;
    // à l'intérieur de chaque groupe, ordre alphabétique.
    trouves.sort(function(a, b){
      if(a.s !== b.s) return a.s - b.s;
      return a.t.nom.localeCompare(b.t.nom, 'fr');
    });

    if(!trouves.length){
      boite.innerHTML = '<p class="vide">Aucun territoire ne correspond</p>';
      boite.className = 'hits on';
      return;
    }

    var total = trouves.length;
    var html = trouves.slice(0, LIMITE).map(function(x){
      var t = x.t;
      var repere = (t.codes_postaux || [])[0] || t.code;
      return '<a href="' + BASE + '/' + t.url + '">'
        + '<span class="tag">' + t.niveau + '</span>'
        + '<span class="nm">' + t.nom + '</span>'
        + '<span class="cd">' + repere + '</span></a>';
    }).join('');

    if(total > LIMITE){
      html += '<p class="vide">' + total + ' territoires correspondent, '
            + LIMITE + ' affichés. Précisez votre recherche.</p>';
    }
    boite.innerHTML = html;
    boite.className = 'hits on';
  });

  document.addEventListener('click', function(e){
    if(!e.target.closest('.find')) boite.className = 'hits';
  });
})();

// ── Bandeau du territoire : collant, et compressé au défilement ────
// La hauteur de la barre du haut est mesurée plutôt que devinée :
// elle varie selon la largeur d'écran et la longueur du nom du site.
(function(){
  var haut = document.querySelector('.top');
  var terr = document.querySelector('.terr');
  if(!haut || !terr) return;

  function caler(){
    document.documentElement.style.setProperty(
      '--h-top', haut.offsetHeight + 'px');
  }

  var enCours = false;
  function defiler(){
    if(enCours) return;
    enCours = true;
    window.requestAnimationFrame(function(){
      terr.classList.toggle('compact', window.scrollY > 40);
      enCours = false;
    });
  }

  caler();
  window.addEventListener('resize', caler, {passive:true});
  window.addEventListener('scroll', defiler, {passive:true});
  defiler();
})();

// ── Infobulle des cartes ────────────────────────────────────────────
// L'infobulle native du SVG n'est pas fiable quand la forme est placée
// dans un lien. On l'affiche donc nous-mêmes. Le <title> reste présent
// dans le document : il sert de secours et aux lecteurs d'écran.
(function(){
  var carte = document.querySelector('svg.carte');
  if(!carte) return;

  var bulle = document.createElement('div');
  bulle.className = 'carte-bulle';
  bulle.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bulle);

  var couches = null, active = null;
  try{
    var bloc = document.getElementById('carte-donnees');
    if(bloc){
      couches = JSON.parse(bloc.textContent);
      active = couches.defaut;
    }
  }catch(err){ couches = null; }

  function formeDe(cible){
    return cible.closest ? cible.closest('path, circle') : null;
  }

  function contenu(forme){
    var nom = forme.getAttribute('data-nom') || '';
    var info = forme.getAttribute('data-info');
    // un point d'intérêt porte son propre complément, indépendant de la
    // donnée choisie pour colorer la carte
    if(info !== null) return '<b>' + nom + '</b><i>' + info + '</i>';
    if(!couches || !active) return '<b>' + nom + '</b>';
    var code = forme.getAttribute('data-code');
    var c = couches.couches[active];
    var valeur = c.libelles[code] || 'non disponible';
    return '<b>' + nom + '</b><i>' + c.nom + ' : ' + valeur + '</i>';
  }

  // Change la donnée représentée : recolore les formes et met à jour l'unité.
  function appliquer(ident){
    if(!couches || !couches.couches[ident]) return;
    active = ident;
    var c = couches.couches[ident];
    var formes = carte.querySelectorAll('path[data-code]');
    for(var i = 0; i < formes.length; i++){
      var f = formes[i];
      var code = f.getAttribute('data-code');
      // classList fonctionne sur les éléments SVG ;
      // className y est en lecture seule, contrairement au HTML.
      f.classList.remove('n0', 'n1', 'n2', 'n3', 'n4', 'nd');
      f.classList.add(c.classes[code] || 'nd');
    }
    var u = document.getElementById('carte-unite');
    if(u) u.textContent = c.unite;
  }

  var choix = document.querySelectorAll('.carte-menu input[name="donnee"]');
  for(var k = 0; k < choix.length; k++){
    choix[k].addEventListener('change', function(){ appliquer(this.value); });
  }

  carte.addEventListener('mousemove', function(e){
    var forme = formeDe(e.target);
    if(!forme){ bulle.className = 'carte-bulle'; return; }
    bulle.innerHTML = contenu(forme);
    bulle.className = 'carte-bulle on';
    var x = e.clientX + 14, y = e.clientY + 16;
    var large = bulle.offsetWidth;
    if(x + large > window.innerWidth - 8) x = e.clientX - large - 14;
    bulle.style.left = x + 'px';
    bulle.style.top = y + 'px';
  });

  carte.addEventListener('mouseleave', function(){
    bulle.className = 'carte-bulle';
  });

  // au clavier, le nom s'affiche aussi lors du parcours par tabulation
  carte.addEventListener('focusin', function(e){
    var lien = e.target.closest('a');
    if(!lien) return;
    var forme = lien.querySelector('path');
    if(!forme) return;
    var r = lien.getBoundingClientRect();
    bulle.innerHTML = contenu(forme);
    bulle.className = 'carte-bulle on';
    bulle.style.left = (r.left + window.scrollX) + 'px';
    bulle.style.top = (r.bottom + window.scrollY + 6) + 'px';
  });
  carte.addEventListener('focusout', function(){
    bulle.className = 'carte-bulle';
  });

  // en dernier : une erreur ici ne doit plus empêcher le survol de fonctionner
  if(active) appliquer(active);
})();

// ── Fond de plan ───────────────────────────────────────────────────
// Les tuiles ne sont téléchargées qu'au moment où le fond est demandé.
// Sans JavaScript, la carte reste affichée en schéma : le contenu ne
// dépend donc jamais de ce script.
(function(){
  var cadre = document.querySelector('.carte-cadre');
  var bloc = document.querySelector('.carte-bloc');
  var choix = document.querySelectorAll('.carte-fonds input[name="fond"]');
  if(!cadre || !choix.length) return;

  function charger(couche){
    var images = couche.querySelectorAll('img[data-src]');
    for(var i = 0; i < images.length; i++){
      images[i].src = images[i].getAttribute('data-src');
      images[i].removeAttribute('data-src');
    }
  }

  function appliquer(id){
    if(id === 'schema'){
      cadre.removeAttribute('data-fond');
      if(bloc) bloc.removeAttribute('data-fond');
      return;
    }
    var couche = cadre.querySelector('.carte-fond[data-fond="' + id + '"]');
    if(couche) charger(couche);
    cadre.setAttribute('data-fond', id);
    if(bloc) bloc.setAttribute('data-fond', id);
  }

  for(var k = 0; k < choix.length; k++){
    choix[k].addEventListener('change', function(){ appliquer(this.value); });
  }

  var bascule = document.getElementById('carte-noms');
  if(bascule){
    bascule.addEventListener('change', function(){
      cadre.classList.toggle('sans-noms', !this.checked);
    });
  }
})();
"""

# ══════════════════════════════════════════════════════════════════
# GABARIT
# ══════════════════════════════════════════════════════════════════

def slug(nom):
    """Transforme un nom de commune en fragment d'adresse lisible.

    « Saint-Antoine-l'Abbaye » devient « saint-antoine-l-abbaye ».
    Le code INSEE reste en tête de l'adresse : c'est lui qui identifie
    le territoire de façon stable, le nom n'est là que pour la lisibilité.
    """
    texte = unicodedata.normalize("NFD", nom.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^a-z0-9]+", "-", texte)
    return texte.strip("-")


def nombre(v):
    """Formatage français : espace fine insécable pour les milliers,
    virgule pour les décimales."""
    if isinstance(v, str):
        # Une valeur peut provenir d'une source externe : elle est
        # échappée comme n'importe quel texte affiché.
        return escape(v)
    if not isinstance(v, (int, float)):
        return "—"
    if isinstance(v, float) and not v.is_integer():
        entier, _, decimales = f"{v:,.1f}".partition(".")
        return entier.replace(",", "\u202f") + "," + decimales
    return f"{int(v):,}".replace(",", "\u202f")


def bloc_bandeaux(bandeaux, renvois):
    """Bandeaux d'alerte, au-dessus de la grille ordinaire.

    Un seul ou deux : pleine largeur chacun. Au-delà, deux par ligne,
    sans quoi la page d'aperçu deviendrait une colonne d'alertes.
    """
    if not bandeaux:
        return ""
    classe = "alertes" + (" deux-colonnes" if len(bandeaux) > 2 else "")
    contenu = chr(10).join(carte(k, v, renvois) for k, v in bandeaux.items())
    return f'    <div class="{classe}">\n{contenu}\n    </div>'


def index_des_blocs(fiche):
    """Où se trouve chaque bloc détaillé, page par page.

    Un indicateur mis en avant sur l'aperçu renvoie souvent vers un bloc
    qui vit dans une sous-rubrique. Sans cet index, le contrôle
    anti-lien-mort supprimerait le renvoi au lieu de le rediriger.
    """
    index = {}
    for b in (fiche.get("blocs") or []):
        if b.get("id"):
            index[b["id"]] = (b.get("rubrique") or "",
                              b.get("sous_rubrique") or "")
    return index


def adresse_du_detail(ancre, index, rubrique, sous, base, chemin):
    """Adresse menant au bloc visé, sur cette page ou sur une autre."""
    if ancre not in index:
        return None
    cible_rubrique, cible_sous = index[ancre]
    ici = (rubrique["id"], sous["id"] if sous else "")
    if (cible_rubrique, cible_sous) == ici:
        return f"#{ancre}"
    morceaux = [m for m in (cible_rubrique, cible_sous) if m]
    suffixe = "".join(f"{m}/" for m in morceaux)
    return f"{base}/{chemin}{suffixe}#{ancre}"


def carte(ident, m, renvois=None):
    """Rend une carte d'indicateur.

    Trois habillages facultatifs, pilotés par la donnée elle-même :
      · mise_en_avant → la carte occupe toute la largeur, en tête de grille
      · ton           → « attention » ou « alerte » colore la carte
      · ancre         → un lien mène au bloc détaillé plus bas dans la page

    Le lien n'est posé que si le bloc visé existe réellement sur cette
    page. Un collecteur peut annoncer une ancre alors que le bloc n'a
    pas été produit — commune sans réseau connu, sans prélèvement — et
    le lien mènerait alors dans le vide.
    """
    pictogramme = icone_de(m, ident)

    classes = ["card"]
    if m.get("mise_en_avant"):
        classes.append("pleine")
    if m.get("ton") in ("attention", "alerte"):
        classes.append("ton-" + m["ton"])

    destination = (renvois or {}).get(m.get("ancre"))
    lien = (f'<a class="card-lien" href="{escape(destination)}">'
            f'Voir le détail</a>' if destination else "")
    repere = (f'<p class="card-repere">{escape(m["repere"])}</p>'
              if m.get("repere") else "")
    explication = (f'<p class="card-expl">{escape(m["explication"])}</p>'
                   if m.get("explication") else "")
    unite = (f' <span class="u">{escape(m["unite"])}</span>'
             if m.get("unite") else "")

    if m.get("mise_en_avant"):
        # Bandeau d'alerte : titre et référence sur une même ligne, pour
        # gagner en hauteur sans perdre d'information.
        entete = (f'<header class="card-tete">{pictogramme}'
                  f'<h2>{escape(m["nom"])}</h2>'
                  f'<span class="id">{escape(ident)}</span></header>')
    else:
        entete = (f'<header class="card-tete">{pictogramme}'
                  f'<span class="id">{escape(ident)}</span></header>'
                  f'<h2>{escape(m["nom"])}</h2>')

    return f"""      <article class="{' '.join(classes)}">
        {entete}
        <div><span class="v">{nombre(m['valeur'])}</span>{unite}</div>
        {repere}
        {explication}
        {lien}
        <footer><span class="pill">{escape(m['source'])}</span><span class="pill">{escape(m['obtention'])}</span></footer>
      </article>"""


def lien(r, base, adresses):
    cible = adresses.get((r["niveau"], r["code"]))
    if not cible:
        return f'<span class="chip">{escape(r["nom"])}</span>'
    return f'<a class="chip" href="{base}/{cible}">{escape(r["nom"])}</a>' 


# Au-delà de ce nombre, la liste des communes rattachées est repliée.
# En dessous, elle tient sur une ou deux lignes et le repli coûterait
# un clic pour rien.
SEUIL_REPLI = 6


def bloc_rattachements(d, base, adresses):
    t, r = d["territoire"], d["rattachements"]
    lignes = []

    dessus = [x for x in r.get("au_dessus", [])
              if x["niveau"] in ("canton", "epci", "departement")]
    connus = [x for x in dessus if x["niveau"] != "departement"]
    if connus:
        lignes.append(f"""      <div class="rung"><span class="lvl">Au-dessus</span>
        <div class="chips">{''.join(lien(x, base, adresses) for x in connus)}</div></div>""")

    lignes.append(f"""      <div class="rung ici"><span class="lvl">Ici</span>
        <div class="chips"><span class="chip now">{escape(t['nom'])}</span></div></div>""")

    # Sur un canton ou une intercommunalité, la liste des communes
    # occupait la moitié de l'écran avant la première tuile. Elle est
    # repliée par défaut, en HTML natif : les liens restent dans la page
    # — donc explorables par les moteurs et atteignables au clavier —
    # mais ne prennent plus la place du contenu.
    dessous = r.get("en_dessous", [])
    if dessous:
        chips = "".join(lien(x, base, adresses) for x in dessous)
        if len(dessous) > SEUIL_REPLI:
            lignes.append(f"""      <div class="rung"><span class="lvl">Communes</span>
        <details class="repli"><summary><span class="repli-plus">Voir les {len(dessous)} communes</span><span class="repli-moins">Masquer les {len(dessous)} communes</span></summary>
        <div class="chips">{chips}</div></details></div>""")
        else:
            lignes.append(f"""      <div class="rung"><span class="lvl">Communes</span>
        <div class="chips">{chips}</div></div>""")

    note = ""
    if t["niveau"] == "commune":
        note = ("Cette commune relève d'un canton et d'une intercommunalité qui ne "
                "regroupent pas les mêmes communes : les deux périmètres se "
                "recouvrent sans coïncider.")
    elif t["niveau"] == "canton" and t.get("communes_scindees") is False:
        note = (f"Ce canton est composé de {t.get('nombre_communes')} communes "
                "entières. Les valeurs agrégées y sont donc exactes.")

    bloc_note = f'\n      <div class="note">{note}</div>' if note else ""
    return f"""    <section class="ratt"><span class="dsp">{icone("_rattachements")}Rattachements</span>
      <div class="spine">
{chr(10).join(lignes)}
      </div>{bloc_note}
    </section>"""


def variantes_anciennes(nom):
    """Graphies possibles d'un nom de commune dans l'ancien site.

    Les adresses retrouvées dans l'index de Google — par exemple
    « commune_chevrieres.php » — suivent une convention sans accent, en
    minuscules, mots liés par un souligné. « Saint » y apparaît aussi
    abrégé en « st », d'où plusieurs variantes par commune.

    Ces motifs sont des hypothèses tirées de deux adresses observées.
    Ils ne peuvent rien casser — ils ne s'appliquent qu'à des chemins qui
    n'existent pas sur ce site — mais ils restent à confronter à la liste
    réelle des 404 relevés par la Search Console.
    """
    texte = unicodedata.normalize("NFD", nom.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "_", texte).strip("_")
    formes = {base}
    if base.startswith("saint_"):
        formes.add("st_" + base[len("saint_"):])
    if base.startswith(("l_", "la_", "le_", "les_")):
        formes.add(base.split("_", 1)[1])
    return sorted(formes)


MOTIF_FORME = re.compile(
    r'<path class="(c-voisine|c-ici)" data-code="([^"]+)" '
    r'd="([^"]*)"><title>([^<]*)</title></path>')

# Ordre de présentation des données proposées sur la carte.
# Les identifiants absents des fiches sont simplement ignorés :
# ajouter les élections plus tard ne demandera rien d'autre ici.
ORDRE_CARTE = ["POP-01", "GEO-13", "POP-10"]

# ══════════════════════════════════════════════════════════════════
# FONDS DE PLAN
#
# Les tuiles d'OpenStreetMap ne conviennent pas : leur politique
# d'usage réserve le service aux usages qui ne le mettent pas sous
# tension, et prévient que l'accès peut être retiré à tout moment aux
# services commerciaux. La Géoplateforme de l'IGN diffuse Plan IGN et
# les photographies aériennes gratuitement et sans inscription — et
# Plan IGN intègre lui-même des données OpenStreetMap.
# ══════════════════════════════════════════════════════════════════

GEOPF = ("https://data.geopf.fr/wmts?SERVICE=WMTS&amp;REQUEST=GetTile"
         "&amp;VERSION=1.0.0&amp;LAYER={couche}&amp;STYLE=normal"
         "&amp;FORMAT={format}&amp;TILEMATRIXSET=PM"
         "&amp;TILEMATRIX={z}&amp;TILEROW={y}&amp;TILECOL={x}")

FONDS = [
    {"id": "schema", "nom": "Schéma", "couche": None,
     "credit": "Contours IGN Admin Express"},
    {"id": "plan", "nom": "Plan IGN",
     "couche": "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "format": "image/png",
     "credit": "Plan IGN © IGN — Géoplateforme"},
    {"id": "photo", "nom": "Photo aérienne",
     "couche": "ORTHOIMAGERY.ORTHOPHOTOS", "format": "image/jpeg",
     "credit": "Photographies aériennes © IGN — Géoplateforme"},
]

# ══════════════════════════════════════════════════════════════════
# RUBRIQUES
#
# Chaque rubrique regroupe les indicateurs dont l'identifiant commence
# par l'un de ses préfixes. « prevue » signale une rubrique affichée
# dans la navigation même si elle est encore vide : le visiteur voit
# ce qui existe et ce qui vient, plutôt qu'un menu qui s'allonge sans
# prévenir. Ajouter une rubrique se fait ici, et nulle part ailleurs.
# ══════════════════════════════════════════════════════════════════

RUBRIQUES = [
    {"id": "", "nom": "Aperçu", "prefixes": None, "prevue": True,
     # Six tuiles au plus par territoire. Les identifiants absents à un
     # niveau sont simplement ignorés : le maire n'existe qu'à la
     # commune, les conseillers départementaux qu'au canton.
     "selection": ["POP-01", "GEO-13", "POP-10",
                   "POL-01", "POL-20", "POL-10",
                   "EAU-01", "ENV-02"]},
    # ENV-07, mis en avant par le collecteur, remonte automatiquement
    # sur l'aperçu par la règle des alertes.

    {"id": "population", "nom": "Population", "prefixes": ["POP"],
     "prevue": True},

    {"id": "geographie", "nom": "Géographie", "prefixes": ["GEO"],
     "prevue": True},

    {"id": "urbanisme", "nom": "Urbanisme", "prefixes": ["URB", "LOG"],
     "prevue": True},

    {"id": "environnement", "nom": "Environnement",
     "prefixes": ["ENV", "EAU", "MET"], "prevue": True,
     "selection": ["EAU-10", "EAU-01", "ENV-02"],
     "sous": [
         {"id": "eau-potable", "nom": "Eau potable"},
         {"id": "secheresse", "nom": "Sécheresse"},
         {"id": "nappes", "nom": "Nappes"},
         {"id": "rivieres", "nom": "Rivières"},
         {"id": "vigilance", "nom": "Vigilance"},
         {"id": "agriculture", "nom": "Agriculture"},
         {"id": "risques", "nom": "Risques"},
     ]},

    {"id": "education", "nom": "Éducation", "prefixes": ["EDU"],
     "prevue": True},

    {"id": "equipements", "nom": "Équipements", "prefixes": ["EQU"],
     "prevue": True},

    {"id": "transports", "nom": "Transports", "prefixes": ["TRA"],
     "prevue": True},

    {"id": "elections", "nom": "Élections", "prefixes": ["POL"],
     "prevue": True,
     "sous": [
         {"id": "elus", "nom": "Élus"},
         # Décidée, pas encore alimentée : la page existe pour être
         # explorée par les moteurs, et s'efface dès qu'une donnée
         # arrive. Voir la section PAGES D'ANNONCE.
         {"id": "resultats", "nom": "Résultats",
          "annonce": "elections-resultats"},
     ]},

    # En bout de barre, comme arbitré. La donnée se périme en heures :
    # elle attend l'automatisation par GitHub Actions.
    {"id": "carburants", "nom": "Carburants", "prefixes": ["CAR"],
     "prevue": True, "annonce": "carburants"},
]



# ══════════════════════════════════════════════════════════════════
# ICÔNES
#
# Dessinées dans une grammaire commune : trait seul, pas d'aplat,
# formes géométriques simples, épaisseur unique. L'inspiration vient
# des légendes de cartes topographiques plutôt que des jeux d'icônes
# d'interface — c'est ce qui donnera au site une identité propre tout
# en restant immédiatement lisible.
#
# Elles ne portent jamais le sens à elles seules : chaque icône est
# systématiquement accompagnée de son libellé.
# ══════════════════════════════════════════════════════════════════

ICONES = {
    "": '<path d="M4 6.5 12 3l8 3.5M4 6.5v11L12 21l8-3.5v-11M4 6.5 12 10l8-3.5'
        'M12 10v11"/>',
    "population": '<circle cx="9" cy="8" r="3"/><path d="M3.5 20c0-3 2.5-5.5 '
                  '5.5-5.5s5.5 2.5 5.5 5.5"/><circle cx="17" cy="9.5" r="2.2"/>'
                  '<path d="M15.5 14.7c2.6.2 5 2.5 5 5.3"/>',
    "geographie": '<path d="M3 7.5 9 4.5l6 3 6-3v12l-6 3-6-3-6 3z"/>'
                  '<path d="M9 4.5v12M15 7.5v12"/>',
    "urbanisme": '<path d="M3 21h18M5 21V9l5-3.5V21M14 21V11l5-2v12"/>'
                 '<path d="M7.5 12v.01M7.5 15.5v.01M16.5 13v.01M16.5 16.5v.01"/>',
    "environnement": '<path d="M3 17c2.5 0 2.5-1.6 5-1.6s2.5 1.6 5 1.6 '
                     '2.5-1.6 5-1.6 2.5 1.6 3 1.6"/>'
                     '<path d="M4 12.5 9 6l3.5 4.2L15.5 7l4.5 5.5"/>',
    "eau-potable": '<path d="M12 3.5c3.2 4.2 5.5 6.9 5.5 9.6a5.5 5.5 0 0 1-11 '
                   '0c0-2.7 2.3-5.4 5.5-9.6z"/><path d="M9.4 13.3a2.7 2.7 0 0 '
                   '0 2.6 3"/>',
    "secheresse": '<circle cx="12" cy="8" r="3.4"/><path d="M12 1.8v1.6M12 '
                  '12.6v1.6M5.6 8H4M20 8h-1.6M7.5 3.5l1.1 1.1M15.4 11.4l1.1 '
                  '1.1M7.5 12.5l1.1-1.1M15.4 4.6l1.1-1.1"/>'
                  '<path d="M3 18.5h4l1.5-2 2 4 2-5 2 3h6.5"/>',
    "nappes": '<path d="M3 8h18M3 8c0-2.2 4-4 9-4s9 1.8 9 4"/>'
              '<path d="M3 13c2.4 0 2.4-1.3 4.8-1.3S10.2 13 12.6 13s2.4-1.3 '
              '4.8-1.3S19.8 13 21 13"/>'
              '<path d="M3 18c2.4 0 2.4-1.3 4.8-1.3S10.2 18 12.6 18s2.4-1.3 '
              '4.8-1.3S19.8 18 21 18"/><path d="M3 8v10M21 8v10"/>',
    "rivieres": '<path d="M4 3c0 5 3.5 6.5 3.5 10.5S4 18.5 4 21"/>'
                '<path d="M20 3c0 5-3.5 6.5-3.5 10.5S20 18.5 20 21"/>'
                '<path d="M12 6.5v3M12 13v3"/>',
    "risques": '<path d="M12 4.2 21 19H3z"/><path d="M12 10v4M12 16.6v.01"/>',
    "agriculture": '<path d="M4 20c0-4.5 3-8 8-8"/>'
                   '<path d="M12 12c0-3.3 2.4-6 5.5-6.5C17.5 9 15 12 12 12z"/>'
                   '<path d="M12 12C9.4 12 7 9.8 6.5 6.6 9.7 7 12 9.2 12 12z"/>'
                   '<path d="M4 20h16"/>',
    "vigilance": '<path d="M6.5 10.5a4 4 0 0 1 7.6-1.8 3.2 3.2 0 0 1 3.9 3.1'
                 ' 2.9 2.9 0 0 1-.8 5.7H7.5a3.5 3.5 0 0 1-1-6.9z"/>'
                 '<path d="M9.5 20.5 8 22.5M13 20.5l-1.5 2M16.5 20.5 15 22.5"/>',
    "education": '<path d="M3 8.5 12 4.5l9 4-9 4z"/>'
                 '<path d="M7 11v5c0 1.6 2.2 2.8 5 2.8s5-1.2 5-2.8v-5"/>'
                 '<path d="M21 8.5v5"/>',
    "equipements": '<path d="M4 9.5 5.5 5h13L20 9.5M4 9.5h16M4 9.5V19h16V9.5"/>'
                   '<path d="M4 9.5a2.2 2.2 0 0 0 4 0 2.2 2.2 0 0 0 4 0 2.2 '
                   '2.2 0 0 0 4 0 2.2 2.2 0 0 0 4 0"/>'
                   '<path d="M10 19v-5h4v5"/>',
    "carburants": '<path d="M4 21V5.5A2.5 2.5 0 0 1 6.5 3h4A2.5 2.5 0 0 1 13 '
                  '5.5V21"/><path d="M3 21h11M6.5 8.5h4"/>'
                  '<path d="M13 10h3.5a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 0 3 '
                  '0V9.5L18.5 7"/>',
    "resultats": '<path d="M3.5 20.5h17"/><path d="M7 20.5v-5.5M12 20.5V7'
                 'M17 20.5v-9"/>',
    "transports": '<path d="M12 3v18"/><path d="M6 3v18M18 3v18"/>'
                  '<path d="M12 5.5v3M12 11v3M12 16.5v3"/>',
    "elections": '<path d="M4 10.5h16V20H4z"/><path d="M8.5 10.5V6h7v4.5"/>'
                 '<path d="M9.5 13.5h5"/>',
    "elus": '<circle cx="12" cy="6.5" r="2.6"/>'
            '<path d="M7 20v-2.2a5 5 0 0 1 10 0V20"/>'
            '<path d="M3.5 20v-1.6a3.4 3.4 0 0 1 3-3.4M20.5 20v-1.6a3.4 3.4 '
            '0 0 0-3-3.4"/>',

    # Sections transverses, présentes sur toutes les fiches.
    "_rattachements": '<circle cx="12" cy="5" r="2.2"/>'
                      '<circle cx="5.5" cy="19" r="2.2"/>'
                      '<circle cx="18.5" cy="19" r="2.2"/>'
                      '<path d="M12 7.2v4.3M5.5 16.8v-2.4h13v2.4M12 11.5v2.9"/>',
    "_carte": '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z"/>'
              '<path d="M9 4v13.5M15 6.5V20"/>'
              '<circle cx="12" cy="10.5" r="1.6"/>',
}

# Rattachement d'une famille d'indicateurs à son pictogramme, quand la
# mesure ne déclare pas elle-même sa rubrique.
ICONE_PAR_PREFIXE = {
    "POP": "population", "GEO": "geographie", "LOG": "urbanisme",
    "EQU": "equipements", "EDU": "education", "TRA": "transports",
    "POL": "elections", "ENV": "risques", "EAU": "environnement",
}


def icone_de(objet, identifiant=""):
    """Pictogramme d'une mesure ou d'un bloc.

    On s'appuie d'abord sur ce que la donnée déclare — sa sous-rubrique,
    puis sa rubrique — avant de retomber sur le préfixe de son
    identifiant. Aucune table à tenir à jour : un nouveau collecteur qui
    déclare sa rubrique hérite du pictogramme correspondant.
    """
    for cle in ("sous_rubrique", "rubrique"):
        valeur = (objet or {}).get(cle)
        if valeur and valeur in ICONES:
            return icone(valeur)
    famille = ICONE_PAR_PREFIXE.get(str(identifiant)[:3])
    return icone(famille) if famille else ""


def icone(identifiant, classe="ico"):
    """Pictogramme d'une rubrique, ou rien si elle n'en a pas."""
    trace = ICONES.get(identifiant)
    if not trace:
        return ""
    # Les attributs width et height sont inscrits dans la balise : un SVG
    # qui en est dépourvu s'affiche en 300 × 150 pixels si la feuille de
    # style n'est pas encore appliquée. La feuille les remplace ensuite
    # par la valeur du thème.
    return (f'<svg class="{classe}" width="18" height="18" '
            f'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.5" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" '
            f'focusable="false">{trace}</svg>')


def rubrique_par_id(ident):
    for r in RUBRIQUES:
        if r["id"] == ident:
            return r
    return None


def appartient(mesure, ident, prefixes, cle):
    """La mesure relève-t-elle de cette rubrique ou sous-rubrique ?

    Une mesure peut déclarer elle-même où elle s'affiche — c'est le
    collecteur qui le sait le mieux. À défaut, on retombe sur le préfixe
    de son identifiant, ce qui suffit aux familles simples.
    """
    declare = mesure.get(cle)
    if declare is not None:
        return declare == ident
    if cle == "sous_rubrique":
        return ident is None
    if prefixes is None:
        return True
    return False


def indicateurs_de(rubrique, mesures, sous=None, identifiants=None):
    """Mesures affichées sur une page donnée.

    · identifiants → sélection explicite, dans l'ordre indiqué
    · sous          → contenu d'une sous-rubrique
    · sinon         → tout le contenu de la rubrique
    """
    if identifiants is not None:
        return {i: mesures[i] for i in identifiants if i in mesures}

    prefixes = rubrique["prefixes"]
    retenues = {}
    for ident, m in mesures.items():
        if rubrique["id"] == "":
            retenues[ident] = m
            continue
        declaree = m.get("rubrique")
        if declaree is not None:
            dans_rubrique = declaree == rubrique["id"]
        else:
            dans_rubrique = bool(prefixes) and any(
                ident.startswith(p) for p in prefixes)
        if not dans_rubrique:
            continue
        if sous is not None and m.get("sous_rubrique") != sous["id"]:
            continue
        retenues[ident] = m
    return retenues


def blocs_de(fiche, rubrique, sous=None):
    cible_sous = sous["id"] if sous else None
    return [b for b in (fiche.get("blocs") or [])
            if b.get("rubrique") == rubrique["id"]
            and (b.get("sous_rubrique") or None) == cible_sous]


def alertes(mesures, deja):
    """Indicateurs à remonter sur l'aperçu, même hors sélection.

    Deux cas : un indicateur en alerte, et un indicateur que le
    collecteur a explicitement désigné comme bandeau. Le second couvre
    les situations qui méritent d'être vues sans relever de l'alerte,
    comme une reconnaissance récente de catastrophe naturelle.
    """
    return {i: m for i, m in mesures.items()
            if i not in deja and m.get("valeur") is not None
            and (m.get("ton") == "alerte" or m.get("mise_en_avant"))}


def sous_actives(rubrique, fiche):
    """Sous-rubriques disposant d'au moins une mesure ou un bloc."""
    actives = []
    for sr in rubrique.get("sous", []):
        a_mesure = any(
            m.get("valeur") is not None
            for m in indicateurs_de(rubrique, fiche["mesures"], sr).values())
        if a_mesure or blocs_de(fiche, rubrique, sr) or sr.get("annonce"):
            actives.append(sr)
    return actives


def rubriques_actives(fiche):
    """Rubriques disposant d'un contenu pour ce territoire."""
    mesures = fiche["mesures"]
    actives = set()
    for r in RUBRIQUES:
        if not r["id"]:
            continue
        contenu = indicateurs_de(r, mesures)
        if any(m.get("valeur") is not None for m in contenu.values()):
            actives.add(r["id"])
        elif any(b.get("rubrique") == r["id"] for b in (fiche.get("blocs") or [])):
            actives.add(r["id"])
        elif r.get("annonce") or any(sr.get("annonce")
                                     for sr in r.get("sous", [])):
            # Rubrique décidée mais pas encore alimentée : sa page
            # d'annonce lui tient lieu de contenu, et doit donc être
            # atteignable depuis la navigation. Une sous-rubrique
            # d'annonce suffit : sans cela, l'échec d'une collecte
            # ferait disparaître des adresses déjà indexées.
            actives.add(r["id"])
    return actives


def nav_rubriques(base, chemin, actives, courante):
    liens = []
    for r in RUBRIQUES:
        libelle = icone(r["id"]) + f'<span>{escape(r["nom"])}</span>'
        if r["id"] == courante:
            liens.append(f'<span class="nav-item actif" '
                         f'aria-current="page">{libelle}</span>')
        elif r["id"] in actives or not r["id"]:
            suffixe = f"{r['id']}/" if r["id"] else ""
            liens.append(f'<a class="nav-item" '
                         f'href="{base}/{chemin}{suffixe}">{libelle}</a>')
        elif r["prevue"]:
            liens.append(f'<span class="nav-item vide" '
                         f'title="Données à venir">{libelle}</span>')
    return ('<nav class="nav" aria-label="Rubriques"><div class="wrap">'
            + "".join(liens) + "</div></nav>")


def nav_sous(base, chemin, rubrique, sous_dispo, courante):
    if not sous_dispo:
        return ""
    liens = [f'<a class="sous-item{"" if courante else " actif"}" '
             f'href="{base}/{chemin}{rubrique["id"]}/">Vue d\'ensemble</a>'
             if courante else
             '<span class="sous-item actif">Vue d\'ensemble</span>']
    for sr in sous_dispo:
        etiquette = icone(sr["id"], "ico petit") + escape(sr["nom"])
        if courante and sr["id"] == courante["id"]:
            liens.append(f'<span class="sous-item actif" aria-current="page">'
                         f'{etiquette}</span>')
        else:
            liens.append(
                f'<a class="sous-item" '
                f'href="{base}/{chemin}{rubrique["id"]}/{sr["id"]}/">'
                f'{etiquette}</a>')
    return ('<nav class="sous-nav" aria-label="Sous-rubriques">'
            '<div class="wrap">' + "".join(liens) + "</div></nav>")


NB_CLASSES = 5


def quantiles(valeurs, nb=NB_CLASSES):
    """Découpe en classes d'effectifs comparables.

    Les distributions territoriales sont très déséquilibrées : une commune
    de 7 700 habitants voisine avec des villages de 200. Un découpage à
    intervalles réguliers produirait une carte presque uniforme, avec une
    seule commune détachée. Les quantiles répartissent les nuances.
    """
    tri = sorted(set(valeurs))
    if len(tri) < 2:
        return []
    nb = min(nb, len(tri))
    return [tri[round(i * (len(tri) - 1) / nb)] for i in range(1, nb)]


def classe(valeur, seuils):
    if valeur is None:
        return "nd"
    if not seuils:                      # valeurs toutes identiques
        return f"n{NB_CLASSES // 2}"
    for i, seuil in enumerate(seuils):
        if valeur < seuil:
            return f"n{i}"
    return f"n{len(seuils)}"


def format_valeur(v, unite):
    """Espace normale avant un mot, espace fine avant un symbole.

    « 7 700 habitants » se lit mieux avec une vraie espace ;
    « 12,4 km² » ou « 76,9 hab./km² » avec une espace fine.
    Une unité entièrement alphabétique est traitée comme un mot.
    """
    if v is None:
        return "non disponible"
    separateur = "\u00a0" if unite.isalpha() else "\u202f"
    return f"{nombre(v)}{separateur}{unite}"


def donnees_carte(membres, fiches, rubrique, sous=None):
    """Prépare les données de coloration pour les communes membres."""
    dispo = {}
    for m in membres:
        f = fiches.get(("commune", m["code"]))
        if not f:
            continue
        for ident, mesure in indicateurs_de(rubrique, f["mesures"], sous).items():
            if isinstance(mesure.get("valeur"), (int, float)):
                dispo.setdefault(ident, {"nom": mesure["nom"],
                                         "unite": mesure["unite"],
                                         "valeurs": {}})
                dispo[ident]["valeurs"][m["code"]] = mesure["valeur"]

    idents = ([i for i in ORDRE_CARTE if i in dispo]
              + sorted(i for i in dispo if i not in ORDRE_CARTE))
    if not idents:
        return None

    couches = {}
    for ident in idents:
        d = dispo[ident]
        seuils = quantiles(list(d["valeurs"].values()))
        couches[ident] = {
            "nom": d["nom"],
            "unite": d["unite"],
            "seuils": seuils,
            "classes": {code: classe(v, seuils)
                        for code, v in d["valeurs"].items()},
            "libelles": {code: format_valeur(v, d["unite"])
                         for code, v in d["valeurs"].items()},
            "bornes": [nombre(s) for s in seuils],
        }
    return {"defaut": idents[0], "ordre": idents, "couches": couches}


def menu_carte(carte):
    """Sélecteur vertical des données affichables."""
    boutons = []
    for i, ident in enumerate(carte["ordre"]):
        c = carte["couches"][ident]
        coche = " checked" if ident == carte["defaut"] else ""
        boutons.append(
            f'<label class="opt"><input type="radio" name="donnee" '
            f'value="{ident}"{coche}> <span>{escape(c["nom"])}</span></label>')
    return ('<div class="carte-menu" role="group" '
            'aria-label="Donnée représentée">'
            + "".join(boutons) + '</div>')


def legende_carte(carte):
    paliers = "".join(f'<span class="pal n{i}"></span>'
                      for i in range(NB_CLASSES))
    return (f'<div class="carte-echelle"><span class="bas">moins</span>'
            f'{paliers}<span class="haut">plus</span>'
            f'<span class="unite" id="carte-unite"></span></div>')


def _json_sur(donnees):
    """JSON destiné à une balise script : la séquence « </ » y est neutralisée.

    Sans cela, une valeur contenant « </script> » clorait la balise et
    tout ce qui suit serait interprété comme du HTML.
    """
    return json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")


def couches_tuiles(grille):
    """Fonds de plan superposables au dessin.

    Les tuiles sont positionnées en pourcentage : le fond suit donc le
    redimensionnement du cadre sans une ligne de JavaScript. L'adresse
    réelle reste dans data-src tant que le fond n'est pas demandé, pour
    ne rien télécharger inutilement.
    """
    couches = []
    for fond in FONDS:
        if not fond["couche"]:
            continue
        images = []
        for tuile in grille["tuiles"]:
            adresse = (GEOPF.replace("{couche}", fond["couche"])
                            .replace("{format}", fond["format"])
                            .replace("{z}", str(grille["zoom"]))
                            .replace("{x}", str(tuile["x"]))
                            .replace("{y}", str(tuile["y"])))
            images.append(
                f'<img data-src="{adresse}" alt="" loading="lazy" '
                f'style="left:{tuile["gauche"]}%;top:{tuile["haut"]}%;'
                f'width:{tuile["l"]}%;height:{tuile["h"]}%">')
        couches.append(f'<div class="carte-fond" data-fond="{fond["id"]}">'
                       + "".join(images) + "</div>")
    return "".join(couches)


def choix_fond(grille):
    boutons = "".join(
        f'<label class="opt"><input type="radio" name="fond" '
        f'value="{f["id"]}"{" checked" if f["id"] == "schema" else ""}> '
        f'<span>{escape(f["nom"])}</span></label>' for f in FONDS)
    credits = "".join(
        f'<span class="carte-credit" data-credit="{f["id"]}">'
        f'{escape(f["credit"])}</span>' for f in FONDS)
    noms = ('<label class="opt bascule"><input type="checkbox" id="carte-noms" '
            'checked> <span>Noms des communes</span></label>')
    return (f'<div class="carte-fonds" role="group" '
            f'aria-label="Fond de plan">{boutons}{noms}</div>', credits)


def mercator(lon, lat, zoom):
    """Coordonnées en pixels dans la projection des tuiles.

    Reprise de 05_cartes.py : le dessin et les tuiles partagent cette
    projection, donc un point placé ainsi tombe exactement au bon
    endroit, fond de plan affiché ou non.
    """
    n = 256 * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    phi = math.radians(max(-85.05, min(85.05, lat)))
    y = (1.0 - math.log(math.tan(phi) + 1.0 / math.cos(phi)) / math.pi) / 2.0 * n
    return x, y


def origine(grille):
    """Retrouve le coin haut-gauche du dessin, en pixels de projection.

    La grille ne l'enregistre pas, mais la première tuile suffit à le
    déduire : sa position en pourcentage donne l'écart avec l'origine.
    """
    tuiles = grille.get("tuiles") or []
    if not tuiles:
        return None
    premiere = tuiles[0]
    x0 = premiere["x"] * 256 - premiere["gauche"] / 100 * grille["largeur"]
    y0 = premiere["y"] * 256 - premiere["haut"] / 100 * grille["hauteur"]
    return x0, y0


def couche_points(points, grille):
    """Points d'intérêt superposés au dessin du territoire."""
    if not points or not grille:
        return ""
    repere = origine(grille)
    if not repere:
        return ""
    x0, y0 = repere
    rayon = max(3.5, grille["largeur"] / 190)

    cercles = []
    for pt in points:
        try:
            x, y = mercator(float(pt["lon"]), float(pt["lat"]), grille["zoom"])
        except (TypeError, ValueError, KeyError):
            continue
        cx, cy = x - x0, y - y0
        if not (0 <= cx <= grille["largeur"] and 0 <= cy <= grille["hauteur"]):
            continue
        classe = "c-point " + escape(str(pt.get("categorie") or "autre"))
        cercles.append(
            f'<circle class="{classe}" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'r="{rayon:.1f}" data-nom="{escape(str(pt.get("nom") or ""))}" '
            f'data-info="{escape(str(pt.get("info") or ""))}"/>')

    return f'<g class="c-points">{"".join(cercles)}</g>' if cercles else ""


def enrober_carte(svg, chemin_grille, points=None):
    """Place le dessin dans un cadre pouvant recevoir un fond de plan."""
    if not chemin_grille.exists():
        return f'<div class="carte-cadre">{svg}</div>'
    grille = json.loads(chemin_grille.read_text(encoding="utf-8"))
    marqueurs = couche_points(points, grille)
    if marqueurs:
        svg = svg.replace("</svg>", marqueurs + "</svg>")
    selecteur, credits = choix_fond(grille)
    proportion = f"{grille['largeur']} / {grille['hauteur']}"
    return (f'{selecteur}'
            f'<div class="carte-cadre" style="aspect-ratio:{proportion}">'
            f'{couches_tuiles(grille)}{svg}</div>'
            f'<p class="carte-credits">{credits}</p>')


def bloc_carte(t, base, adresses, fiches, membres, rubrique, sous=None,
               points=None):
    """Insère la carte du territoire si elle a été produite par 05_cartes.py.

    Le SVG est intégré dans la page plutôt qu'appelé en image : il hérite
    ainsi des couleurs du thème, ses formes deviennent des liens, et elles
    peuvent être colorées selon la donnée choisie.
    """
    fichier = RACINE / "assets" / "cartes" / t["niveau"] / f"{t['code']}.svg"
    if not fichier.exists():
        return ""

    carte = donnees_carte(membres, fiches, rubrique, sous) if membres else None
    defaut = carte["couches"][carte["defaut"]]["classes"] if carte else {}

    def relier(m):
        cl, code, trace, nom = m.groups()
        teinte = f" {defaut.get(code, 'nd')}" if carte else ""
        # Le nom est porté par un attribut plutôt que par une balise <title> :
        # celle-ci déclencherait l'infobulle native du navigateur, qui se
        # superposerait à la nôtre. L'accessibilité passe par aria-label.
        forme = (f'<path class="{cl}{teinte}" data-code="{code}" '
                 f'data-nom="{nom}" d="{trace}"/>')
        cible = adresses.get(("commune", code))
        if not cible or code == t["code"]:
            return f'<g role="img" aria-label="{nom}">{forme}</g>'
        return f'<a href="{base}/{cible}" aria-label="{nom}">{forme}</a>' 

    svg = MOTIF_FORME.sub(relier, fichier.read_text(encoding="utf-8"))
    svg = enrober_carte(svg, fichier.with_suffix(".json"), points)

    if not carte:
        legende = ("Situation dans le territoire — cliquez une commune "
                   "pour ouvrir sa fiche")
        return f"""    <section class="carte-bloc">
      <span class="dsp">{icone("_carte")}Carte</span>
      {svg}
      <p class="carte-legende">{legende}</p>
    </section>"""

    charge = _json_sur({
        "defaut": carte["defaut"],
        "couches": {i: {"nom": c["nom"], "unite": c["unite"],
                        "classes": c["classes"], "libelles": c["libelles"]}
                    for i, c in carte["couches"].items()},
    })

    return f"""    <section class="carte-bloc">
      <span class="dsp">Carte</span>
      <div class="carte-grille">
        {menu_carte(carte)}
        <div class="carte-zone">
          {svg}
          {legende_carte(carte)}
        </div>
      </div>
      <p class="carte-legende">Survolez une commune ou un point pour lire sa valeur,
         cliquez pour ouvrir sa fiche. Les nuances sont réparties en cinq
         groupes d'effectifs comparables.</p>
      <script type="application/json" id="carte-donnees">{charge}</script>
    </section>"""


def bloc_liste(d, rubrique, sous=None):
    """Rend les blocs détaillés attachés à une rubrique.

    Certaines données ne se réduisent pas à un chiffre : les réseaux
    d'eau qui desservent une commune forment une liste d'objets, chacun
    avec ses propres caractéristiques. Ils ont donc leur propre gabarit,
    distinct des cartes d'indicateurs.
    """
    blocs = blocs_de(d, rubrique, sous)
    if not blocs:
        return ""

    sorties = []
    for b in blocs:
        entrees = []
        for item in b["items"]:
            lignes = "".join(
                f'<div class="bl-ligne"><span class="bl-cle">{escape(k)}</span>'
                f'<span class="bl-val">{escape(str(v))}</span></div>'
                for k, v in item.get("details", {}).items())
            etat = item.get("etat")
            pastille = (f'<span class="bl-etat {escape(etat[1])}">'
                        f'{escape(etat[0])}</span>') if etat else ""
            texte = (f'<p class="bl-texte">{escape(item["texte"])}</p>'
                     if item.get("texte") else "")
            lien = item.get("lien")
            adresse = lien_sur(lien.get("url")) if lien else ""
            ancre = (f'<a class="bl-lien" href="{escape(adresse)}" '
                     f'target="_blank" rel="noopener noreferrer">'
                     f'{escape(lien["libelle"])}</a>' if adresse else "")
            entrees.append(
                f'<article class="bl-item"><header><h3>{escape(item["titre"])}</h3>'
                f'{pastille}</header>{lignes}{texte}{ancre}</article>')
        note = (f'<p class="bl-note">{escape(b["note"])}</p>'
                if b.get("note") else "")
        source = b.get("lien")
        adresse_source = lien_sur(source.get("url")) if source else ""
        renvoi = (f'<p class="bl-source"><a href="{escape(adresse_source)}" '
                  f'target="_blank" rel="noopener noreferrer">'
                  f'{escape(source["libelle"])}</a></p>'
                  if adresse_source else "")
        ancre = f' id="{escape(b["id"])}"' if b.get("id") else ""
        sorties.append(
            f'    <section class="bloc"{ancre}>'
            f'<span class="dsp">{icone_de(b)}{escape(b["titre"])}</span>'
            f'<div class="bl-grille">{"".join(entrees)}</div>'
            f'{renvoi}{note}</section>')
    return "\n".join(sorties)


def lien_sur(url):
    """N'accepte qu'une adresse web.

    Un lien fourni par une source externe pourrait porter un schéma
    « javascript: » ou « data: ». L'échappement HTML ne protège pas de
    ce cas : il faut contrôler le schéma lui-même.
    """
    texte = str(url or "").strip()
    return texte if texte.lower().startswith(("https://", "http://")) else ""


ROLES = {"canton": "Canton", "epci": "Intercommunalité",
         "departement": "Département", "region": "Région"}


def rappel_parents(d, base, adresses):
    """Rappelle les territoires auxquels la fiche se rattache.

    Affiché dans le bandeau, à droite du nom : un habitant sait
    rarement de quel canton relève sa commune, et encore moins de
    quelle intercommunalité.
    """
    lignes = []
    for r in (d["rattachements"].get("au_dessus") or []):
        role = ROLES.get(r["niveau"], r["niveau"].capitalize())
        cible = adresses.get((r["niveau"], r["code"]))
        nom = escape(r["nom"])
        contenu = (f'<a href="{base}/{cible}">{nom}</a>' if cible else nom)
        lignes.append(f'<span class="p-ligne">'
                      f'<span class="p-role">{escape(role)}</span>'
                      f'{contenu}</span>')
    if not lignes:
        return ""
    return f'<div class="terr-parents">{"".join(lignes)}</div>'



LEURRE_PHP = """<?php
// Page-appât. Elle ne donne accès à rien : sa seule fonction est
// d'occuper une tentative d'intrusion et d'en conserver la trace.
//
// L'adresse du visiteur est tronquée avant écriture. Aucun identifiant
// ni mot de passe saisi n'est enregistré.

$journal = __DIR__ . '/JOURNAL';
$retention = RETENTION;
$attente = DELAI;

function adresse_tronquee() {
    $brut = $_SERVER['REMOTE_ADDR'] ?? '';
    if (strpos($brut, ':') !== false) {
        $blocs = explode(':', $brut);
        return implode(':', array_slice($blocs, 0, 3)) . ':...';
    }
    $blocs = explode('.', $brut);
    if (count($blocs) === 4) {
        $blocs[3] = 'x';
        return implode('.', $blocs);
    }
    return 'inconnue';
}

function propre($texte, $taille = 180) {
    $texte = preg_replace('/[\\r\\n\\t;]+/', ' ', (string) $texte);
    return substr(trim($texte), 0, $taille);
}

// ── purge des entrées trop anciennes ──
if (is_file($journal) && filesize($journal) > 0) {
    $limite = time() - $retention * 86400;
    $gardees = [];
    foreach (file($journal, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $ligne) {
        $date = strtotime(substr($ligne, 0, 19));
        if ($date && $date >= $limite) { $gardees[] = $ligne; }
    }
    if (count($gardees) > 5000) { $gardees = array_slice($gardees, -5000); }
    file_put_contents($journal, implode("\\n", $gardees) . "\\n", LOCK_EX);
}

$entree = implode(';', [
    date('Y-m-d H:i:s'),
    adresse_tronquee(),
    propre($_SERVER['REQUEST_METHOD'] ?? '', 8),
    propre($_SERVER['REQUEST_URI'] ?? '', 120),
    propre($_SERVER['HTTP_REFERER'] ?? '-', 120),
    propre($_SERVER['HTTP_USER_AGENT'] ?? '-', 180),
]);
@file_put_contents($journal, $entree . "\\n", FILE_APPEND | LOCK_EX);

// Attente délibérée : elle ralentit les outils de balayage, qui
// enchaînent des milliers d'adresses, sans gêner un visiteur égaré.
sleep($attente);

$echec = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
header('X-Robots-Tag: noindex, nofollow');
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Administration</title>
<style>
body{background:#12161a;color:#c9d3da;font-family:system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;
  margin:0;padding:24px}
main{background:#1a2026;border:1px solid #2c353d;border-radius:6px;
  padding:28px;max-width:360px;width:100%}
h1{font-size:17px;margin:0 0 4px}
p{font-size:13px;color:#8b98a3;line-height:1.5}
label{display:block;font-size:12px;margin:14px 0 4px;color:#8b98a3}
input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:4px;
  border:1px solid #2c353d;background:#12161a;color:#c9d3da;font:inherit}
button{margin-top:18px;width:100%;padding:10px;border:0;border-radius:4px;
  background:#2f6b4f;color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{margin-top:14px;padding:9px 11px;border-radius:4px;
  background:#3a1f1c;border:1px solid #6b2f26;color:#e2b4ad;font-size:13px}
</style>
</head>
<body>
<main>
  <h1>Espace d'administration</h1>
  <p>Accès réservé. Toute tentative de connexion est enregistrée.</p>
  <?php if ($echec) { ?>
  <div class="err">Identifiants incorrects. Nouvel essai possible dans quelques instants.</div>
  <?php } ?>
  <form method="post" autocomplete="off">
    <label for="u">Identifiant</label>
    <input id="u" name="u" type="text">
    <label for="p">Mot de passe</label>
    <input id="p" name="p" type="password">
    <button type="submit">Se connecter</button>
  </form>
</main>
</body>
</html>
"""

LEURRE_HTACCESS = """# Le journal ne doit jamais être servi par le web.
<Files "JOURNAL">
    Require all denied
</Files>

# Rien d'autre que la page d'accueil dans ce dossier.
<FilesMatch "\\.(json|csv|zip|sql|bak|log|txt)$">
    Require all denied
</FilesMatch>
"""

DOCUMENTS_PHP = r"""<?php
// Documents de travail — consultation, lecture seule.
//
// Liste le sous-dossier DOSSIERDOCS et sert son contenu, pour pouvoir
// relire la documentation du projet depuis un téléphone.
//
// Trois précautions, dans l'esprit du reste du site :
//
//   · cette page hérite de la protection par mot de passe du dossier
//     parent, elle n'en ajoute aucune ;
//   · seules les extensions déclarées ci-dessous sont listées et
//     servies — une clé ou un fichier de configuration déposés là par
//     mégarde resteraient invisibles ;
//   · rien n'est écrit ni supprimé : le dépôt reste la seule voie
//     d'ajout d'un document.

header('X-Robots-Tag: noindex, nofollow');

$base = __DIR__ . '/DOSSIERDOCS';
$racine = realpath($base);

// Extensions servies, avec leur libellé, leur type et leur mode
// d'affichage. N'y ajoutez jamais php, htaccess, json ni key.
$TYPES = [
    'md'   => ['Document', 'text/plain; charset=utf-8', 'markdown'],
    'txt'  => ['Texte', 'text/plain; charset=utf-8', 'brut'],
    'csv'  => ['Tableau', 'text/plain; charset=utf-8', 'brut'],
    'pdf'  => ['PDF', 'application/pdf', 'incorpore'],
    'png'  => ['Image', 'image/png', 'incorpore'],
    'jpg'  => ['Image', 'image/jpeg', 'incorpore'],
    'jpeg' => ['Image', 'image/jpeg', 'incorpore'],
    'webp' => ['Image', 'image/webp', 'incorpore'],
    'svg'  => ['Image', 'image/svg+xml', 'telecharge'],
    'xlsx' => ['Classeur', 'application/octet-stream', 'telecharge'],
    'docx' => ['Document Word', 'application/octet-stream', 'telecharge'],
    'zip'  => ['Archive', 'application/zip', 'telecharge'],
];

function extension($nom)
{
    return strtolower(pathinfo($nom, PATHINFO_EXTENSION));
}

function poids($octets)
{
    if ($octets < 1024) {
        return $octets . ' o';
    }
    if ($octets < 1048576) {
        return round($octets / 1024) . ' Ko';
    }
    return round($octets / 1048576, 1) . ' Mo';
}

// Fichiers présents, triés par nom. Les sous-dossiers ne sont pas
// parcourus : un seul niveau, cela suffit et rien ne peut déborder.
function inventaire($base, $TYPES)
{
    $liste = [];
    if (!is_dir($base)) {
        return $liste;
    }
    foreach (scandir($base) as $nom) {
        if ($nom === '.' || $nom === '..' || $nom[0] === '.') {
            continue;
        }
        $chemin = $base . '/' . $nom;
        if (!is_file($chemin) || !isset($TYPES[extension($nom)])) {
            continue;
        }
        $liste[] = [
            'nom' => $nom,
            'taille' => filesize($chemin),
            'date' => filemtime($chemin),
            'type' => $TYPES[extension($nom)][0],
        ];
    }
    usort($liste, function ($a, $b) {
        return strcasecmp($a['nom'], $b['nom']);
    });
    return $liste;
}

// ── rendu du markdown ─────────────────────────────────────────────
// Assez pour relire la documentation du projet : titres, tableaux,
// listes, code, citations. Le texte est échappé AVANT toute mise en
// forme, et un lien dont le schéma n'est pas explicitement autorisé
// n'est pas rendu cliquable — « javascript: » n'a rien à faire ici.

function md_ligne($texte, $TYPES)
{
    $t = htmlspecialchars($texte, ENT_QUOTES, 'UTF-8');
    $t = preg_replace('/`([^`]+)`/u', '<code>$1</code>', $t);
    $t = preg_replace('/\*\*([^*]+)\*\*/u', '<strong>$1</strong>', $t);
    $t = preg_replace('/(?<![*\w])\*([^*\n]+)\*(?!\*)/u', '<em>$1</em>', $t);
    $t = preg_replace_callback(
        '/\[([^\]]*)\]\(([^)\s]+)\)/u',
        function ($m) use ($TYPES) {
            $libelle = $m[1];
            $url = html_entity_decode($m[2], ENT_QUOTES, 'UTF-8');
            // Renvoi vers un autre document du dossier : on repasse par
            // cette page plutôt que de servir le fichier en direct.
            if (!preg_match('#^[a-z][a-z0-9+.-]*:#i', $url)
                && isset($TYPES[extension($url)])) {
                $cible = '?f=' . rawurlencode(basename($url));
                return '<a href="' . htmlspecialchars($cible, ENT_QUOTES, 'UTF-8')
                    . '">' . $libelle . '</a>';
            }
            if (!preg_match('#^(https?://|mailto:)#i', $url)) {
                return $libelle;
            }
            return '<a href="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8')
                . '" rel="noopener noreferrer" target="_blank">' . $libelle . '</a>';
        },
        $t
    );
    return $t;
}

function md_tableau($lignes, $TYPES)
{
    $html = '<div class="deborde"><table>';
    $entete = true;
    foreach ($lignes as $ligne) {
        $cellules = array_map('trim', explode('|', trim($ligne, " \t|")));
        // La ligne de séparation ne porte que tirets et deux-points.
        if (preg_match('/^[\s|:-]+$/', $ligne)) {
            $entete = false;
            continue;
        }
        $html .= '<tr>';
        foreach ($cellules as $cellule) {
            $balise = $entete ? 'th' : 'td';
            $html .= "<$balise>" . md_ligne($cellule, $TYPES) . "</$balise>";
        }
        $html .= '</tr>';
        $entete = false;
    }
    return $html . '</table></div>';
}

function markdown($texte, $TYPES)
{
    $lignes = preg_split('/\r\n|\r|\n/', $texte);
    $html = '';
    $liste = null;      // 'ul' ou 'ol' en cours
    $item = null;       // texte de l'élément de liste en cours
    $code = false;
    $paragraphe = [];
    $tableau = [];

    $vider_paragraphe = function () use (&$paragraphe, &$html, $TYPES) {
        if ($paragraphe) {
            $html .= '<p>' . md_ligne(implode(' ', $paragraphe), $TYPES) . '</p>';
            $paragraphe = [];
        }
    };
    // Un élément de liste est mis en attente plutôt qu'écrit aussitôt :
    // une phrase repliée sur la ligne suivante appartient à l'élément
    // en cours, et non à un paragraphe nouveau.
    $vider_item = function () use (&$item, &$html, $TYPES) {
        if ($item !== null) {
            $html .= '<li>' . md_ligne($item, $TYPES) . '</li>';
            $item = null;
        }
    };
    $fermer_liste = function () use (&$liste, &$html, &$vider_item) {
        $vider_item();
        if ($liste) {
            $html .= "</$liste>";
            $liste = null;
        }
    };
    $vider_tableau = function () use (&$tableau, &$html, $TYPES) {
        if ($tableau) {
            $html .= md_tableau($tableau, $TYPES);
            $tableau = [];
        }
    };

    foreach ($lignes as $ligne) {
        if (preg_match('/^\s*```/', $ligne)) {
            $vider_paragraphe();
            $fermer_liste();
            $vider_tableau();
            $html .= $code ? '</code></pre>' : '<pre><code>';
            $code = !$code;
            continue;
        }
        if ($code) {
            $html .= htmlspecialchars($ligne, ENT_QUOTES, 'UTF-8') . "\n";
            continue;
        }

        if (strpos(ltrim($ligne), '|') === 0) {
            $vider_paragraphe();
            $fermer_liste();
            $tableau[] = $ligne;
            continue;
        }
        $vider_tableau();

        if (trim($ligne) === '') {
            $vider_paragraphe();
            $fermer_liste();
            continue;
        }
        if (preg_match('/^\s*(-{3,}|\*{3,}|_{3,})\s*$/', $ligne)) {
            $vider_paragraphe();
            $fermer_liste();
            $html .= '<hr>';
            continue;
        }
        if (preg_match('/^(#{1,6})\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            $fermer_liste();
            $niveau = min(6, strlen($m[1]) + 1);
            $html .= "<h$niveau>" . md_ligne(trim($m[2]), $TYPES) . "</h$niveau>";
            continue;
        }
        if (preg_match('/^\s*>\s?(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            $fermer_liste();
            $html .= '<blockquote>' . md_ligne($m[1], $TYPES) . '</blockquote>';
            continue;
        }
        if (preg_match('/^\s*[-*+]\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            if ($liste !== 'ul') {
                $fermer_liste();
                $html .= '<ul>';
                $liste = 'ul';
            }
            $vider_item();
            $item = $m[1];
            continue;
        }
        if (preg_match('/^\s*\d+[.)]\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            if ($liste !== 'ol') {
                $fermer_liste();
                $html .= '<ol>';
                $liste = 'ol';
            }
            $vider_item();
            $item = $m[1];
            continue;
        }
        // Suite d'un élément de liste replié sur plusieurs lignes.
        if ($item !== null) {
            $item .= ' ' . trim($ligne);
            continue;
        }
        $paragraphe[] = trim($ligne);
    }

    $vider_paragraphe();
    $fermer_liste();
    $vider_tableau();
    if ($code) {
        $html .= '</code></pre>';
    }
    return $html;
}

// ── fichier demandé ───────────────────────────────────────────────
// basename écarte tout chemin, et realpath vérifie que le fichier
// servi est bien dans le dossier des documents : deux verrous plutôt
// qu'un, la traversée de répertoire étant la faute classique ici.

$demande = isset($_GET['f']) ? basename((string) $_GET['f']) : '';
$fichier = null;
$mode = '';
if ($demande !== '' && isset($TYPES[extension($demande)]) && $racine) {
    $chemin = realpath($racine . '/' . $demande);
    if ($chemin && is_file($chemin) && strpos($chemin, $racine . '/') === 0) {
        $fichier = $chemin;
        $mode = $TYPES[extension($demande)][2];
    }
}

// Service direct : image, PDF, classeur, ou source brute d'un texte.
if ($fichier && ($mode === 'incorpore' || $mode === 'telecharge'
                 || isset($_GET['brut']))) {
    $type = $TYPES[extension($demande)][1];
    if (isset($_GET['brut'])) {
        $type = 'text/plain; charset=utf-8';
    }
    header('Content-Type: ' . $type);
    header('Content-Length: ' . filesize($fichier));
    header('X-Content-Type-Options: nosniff');
    if ($mode === 'telecharge' && !isset($_GET['brut'])) {
        header('Content-Disposition: attachment; filename="'
               . str_replace('"', '', $demande) . '"');
    }
    readfile($fichier);
    exit;
}

$documents = inventaire($base, $TYPES);
$titre = $fichier ? $demande : 'Documents de travail';
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title><?= htmlspecialchars($titre, ENT_QUOTES, 'UTF-8') ?></title>
<style>
:root{--paper:#EDF0EA;--surface:#FFF;--ink:#16211C;--soft:#5D6E64;
  --line:#D5DCD3;--accent:#2C6B4C;--sunken:#F5F7F3}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:20px 16px 60px;
  background:var(--paper);color:var(--ink);line-height:1.6}
main{max-width:860px;margin:0 auto}
a{color:var(--accent)}
h1{font-size:21px;margin:0 0 4px}
.chapeau{font-size:13px;color:var(--soft);margin:0 0 20px}
.retour{display:inline-block;font-size:13px;margin-bottom:14px;
  text-decoration:none}
.retour:hover{text-decoration:underline}
ul.docs{list-style:none;margin:0;padding:0}
ul.docs li{background:var(--surface);border:1px solid var(--line);
  border-radius:4px;margin-bottom:8px}
ul.docs a{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;
  padding:13px 14px;text-decoration:none;color:var(--ink)}
ul.docs a:hover{background:var(--sunken)}
.nom{font-weight:600;flex:1 1 auto;word-break:break-word}
.meta{font-size:12px;color:var(--soft);white-space:nowrap}
.vide{background:var(--surface);border:1px dashed var(--line);border-radius:4px;
  padding:18px;font-size:14px;color:var(--soft)}
article{background:var(--surface);border:1px solid var(--line);border-radius:4px;
  padding:18px 20px}
article h2{font-size:19px;margin:26px 0 8px;padding-bottom:5px;
  border-bottom:1px solid var(--line)}
article h3{font-size:16px;margin:22px 0 6px}
article h4,article h5,article h6{font-size:14px;margin:18px 0 4px}
article p,article li{font-size:15px}
article code{font-family:ui-monospace,monospace;font-size:13px;
  background:var(--sunken);padding:1px 4px;border-radius:3px}
article pre{background:var(--sunken);border:1px solid var(--line);
  border-radius:3px;padding:12px;overflow-x:auto}
article pre code{background:none;padding:0}
article blockquote{margin:10px 0;padding-left:12px;
  border-left:3px solid var(--line);color:var(--soft)}
article hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.deborde{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;font-size:14px;min-width:100%}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);
  vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--soft);white-space:nowrap}
.pied{margin-top:20px;font-size:12px;color:var(--soft)}
.pied a{margin-right:14px}
@media(max-width:520px){body{padding:14px 10px 50px}article{padding:14px}}
</style>
</head>
<body><main>
<?php if ($fichier) { ?>
<a class="retour" href="?">&larr; Tous les documents</a>
<h1><?= htmlspecialchars($demande, ENT_QUOTES, 'UTF-8') ?></h1>
<p class="chapeau">Modifié le
<?= date('d/m/Y à H\hi', filemtime($fichier)) ?> ·
<?= poids(filesize($fichier)) ?></p>
<article>
<?php
if ($mode === 'markdown') {
    echo markdown(file_get_contents($fichier), $TYPES);
} else {
    echo '<pre><code>'
        . htmlspecialchars(file_get_contents($fichier), ENT_QUOTES, 'UTF-8')
        . '</code></pre>';
}
?>
</article>
<p class="pied">
<a href="?f=<?= rawurlencode($demande) ?>&amp;brut=1">Voir la source</a>
<a href="?">Retour à la liste</a></p>
<?php } else { ?>
<a class="retour" href="index.html">&larr; Administration</a>
<h1>Documents de travail</h1>
<p class="chapeau"><?= count($documents) ?> document(s) dans le dossier
<code>DOSSIERDOCS</code>. Lecture seule : l'ajout et la mise à jour
passent par le dépôt.</p>
<?php if (!$documents) { ?>
<p class="vide">Aucun document lisible dans ce dossier. Seules les
extensions déclarées dans cette page y sont listées — un fichier d'un
autre type n'apparaîtra pas, même présent.</p>
<?php } else { ?>
<ul class="docs">
<?php foreach ($documents as $d) { ?>
  <li><a href="?f=<?= rawurlencode($d['nom']) ?>">
    <span class="nom"><?= htmlspecialchars($d['nom'], ENT_QUOTES, 'UTF-8') ?></span>
    <span class="meta"><?= htmlspecialchars($d['type'], ENT_QUOTES, 'UTF-8') ?>
      · <?= poids($d['taille']) ?>
      · <?= date('d/m/Y', $d['date']) ?></span>
  </a></li>
<?php } ?>
</ul>
<?php } ?>
<p class="pied">Ces documents sont internes. Ils ne contiennent ni mot de
passe ni clé : ceux-ci n'ont leur place ni ici, ni dans le dépôt.</p>
<?php } ?>
</main></body>
</html>
"""


MESURE_JS = r"""// Mesure d'audience — chargée seulement après acceptation.
//
// Rien de Google n'est demandé tant que le visiteur n'a pas répondu.
// Son choix est conservé localement pour ne pas le lui redemander ; ce
// stockage-là est dispensé de consentement puisqu'il ne sert qu'à
// respecter sa décision.
(function () {
  var CLE = "sg-mesure";
  var ID = "IDENTIFIANT";

  function memoire(action, valeur) {
    try {
      if (action === "lire") { return localStorage.getItem(CLE); }
      localStorage.setItem(CLE, valeur);
    } catch (e) { return null; }   // navigation privée, stockage refusé
  }

  function charger() {
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag("js", new Date());
    // Mesure d'audience seule : aucun signal publicitaire.
    gtag("config", ID, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  function repondre(choix) {
    memoire("ecrire", choix);
    var b = document.getElementById("mesure-bandeau");
    if (b) { b.hidden = true; }
    if (choix === "oui") { charger(); }
  }

  var choix = memoire("lire");
  if (choix === "oui") { charger(); }

  document.addEventListener("DOMContentLoaded", function () {
    var bandeau = document.getElementById("mesure-bandeau");
    if (!bandeau) { return; }
    if (!choix) { bandeau.hidden = false; }
    var oui = document.getElementById("mesure-oui");
    var non = document.getElementById("mesure-non");
    if (oui) { oui.addEventListener("click", function () { repondre("oui"); }); }
    if (non) { non.addEventListener("click", function () { repondre("non"); }); }

    // Bouton présent sur les mentions légales : permet de revenir sur
    // son choix, dans un sens comme dans l'autre.
    var revenir = document.getElementById("mesure-revenir");
    if (revenir) {
      revenir.hidden = false;
      revenir.addEventListener("click", function () {
        try { localStorage.removeItem(CLE); } catch (e) {}
        location.reload();
      });
    }
  });
})();
"""


BANDEAU_MESURE = """
<div class="mesure" id="mesure-bandeau" hidden role="region"
     aria-label="Mesure d'audience"><div class="wrap">
  <p>Ce site peut mesurer sa fréquentation avec Google Analytics, pour
  savoir quelles pages sont consultées. Rien n'est chargé tant que vous
  n'avez pas accepté, et un refus n'enlève rien au contenu.</p>
  <div class="mesure-choix">
    <button type="button" id="mesure-non" class="mesure-btn">Refuser</button>
    <button type="button" id="mesure-oui" class="mesure-btn oui">Accepter</button>
  </div>
</div></div>"""


JOURNAL_PHP = """<?php
// Lecture du journal du leurre. Même réserve que pour le reste de cette
// section : discrétion, pas protection. Protégez le dossier par mot de
// passe depuis l'espace client OVH si vous souhaitez le fermer.
header('X-Robots-Tag: noindex, nofollow');
$journal = __DIR__ . '/../LEURRE/JOURNAL';
$lignes = is_file($journal)
    ? array_reverse(file($journal, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES))
    : [];
$total = count($lignes);
$lignes = array_slice($lignes, 0, 200);
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Journal du leurre</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#EDF0EA;
  color:#16211C}
h1{font-family:sans-serif;font-size:20px}
p{font-size:13px;color:#5D6E64}
table{width:100%;border-collapse:collapse;font-size:12px;background:#fff;
  margin-top:16px}
th{text-align:left;padding:6px 8px;font-size:10px;text-transform:uppercase;
  letter-spacing:.06em;color:#5D6E64;border-bottom:1px solid #D5DCD3}
td{padding:5px 8px;border-top:1px solid #EDF0EA;font-family:monospace;
  word-break:break-all}
</style>
</head>
<body>
<h1>Journal du leurre</h1>
<p><?= $total ?> tentative(s) conservée(s), 200 dernières affichées.
Les adresses sont tronquées de leur dernier segment. Conservation :
RETENTION jours.</p>
<table>
<tr><th>Date</th><th>Adresse</th><th>Méthode</th><th>Chemin</th>
<th>Provenance</th><th>Agent</th></tr>
<?php foreach ($lignes as $ligne) {
    $c = array_pad(explode(';', $ligne), 6, '');
    echo '<tr>';
    foreach ($c as $valeur) {
        echo '<td>' . htmlspecialchars($valeur, ENT_QUOTES, 'UTF-8') . '</td>';
    }
    echo '</tr>';
} ?>
</table>
</body>
</html>
"""


CHIFFRER_PHP = r"""<?php
// Assistant de protection — À SUPPRIMER une fois la protection en place.
//
// Il chiffre un mot de passe avec les fonctions du serveur, ce qui
// garantit la compatibilité avec Apache, et compose les deux fichiers
// à créer. Le mot de passe saisi n'est ni enregistré ni transmis.

header('X-Robots-Tag: noindex, nofollow');
$dossier = __DIR__;
$identifiant = trim($_POST['u'] ?? '');
$motdepasse = $_POST['p'] ?? '';
$empreinte = '';
$erreur = '';

if ($identifiant !== '' && $motdepasse !== '') {
    if (strlen($motdepasse) < 12) {
        $erreur = 'Choisissez un mot de passe d\'au moins 12 caractères.';
    } elseif (!preg_match('/^[A-Za-z0-9_.-]+$/', $identifiant)) {
        $erreur = 'Identifiant : lettres, chiffres, point, tiret ou souligné.';
    } else {
        $empreinte = password_hash($motdepasse, PASSWORD_BCRYPT);
    }
}
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Protéger cette section</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#EDF0EA;
  color:#16211C}
main{max-width:760px;margin:0 auto}
h1{font-size:20px}
h2{font-size:15px;margin-top:26px}
p,li{font-size:14px;line-height:1.55;color:#5D6E64}
code,pre{font-family:ui-monospace,monospace;font-size:12px}
pre{background:#fff;border:1px solid #D5DCD3;border-radius:3px;padding:12px;
  overflow:auto;white-space:pre-wrap;word-break:break-all;color:#16211C}
label{display:block;font-size:13px;margin:12px 0 4px}
input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:3px;
  border:1px solid #D5DCD3;font:inherit}
button{margin-top:16px;padding:10px 20px;border:0;border-radius:3px;
  background:#2C6B4C;color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{background:#FBEAE7;border:1px solid #A32C1B;color:#A32C1B;padding:9px 11px;
  border-radius:3px;font-size:13px;margin-top:14px}
.ok{background:#EAF3EE;border:1px solid #2C6B4C;padding:12px;border-radius:3px}
</style>
</head>
<body><main>
<h1>Protéger cette section par mot de passe</h1>
<p>Le chiffrement est fait par le serveur, ce qui garantit la compatibilité
avec Apache. Le mot de passe saisi n'est ni enregistré ni transmis ailleurs.</p>

<?php if ($erreur) { ?><div class="err"><?= htmlspecialchars($erreur) ?></div><?php } ?>

<?php if ($empreinte === '') { ?>
<form method="post" autocomplete="off">
  <label for="u">Identifiant</label>
  <input id="u" name="u" type="text" value="<?= htmlspecialchars($identifiant) ?>">
  <label for="p">Mot de passe — 12 caractères au moins</label>
  <input id="p" name="p" type="password">
  <button type="submit">Chiffrer</button>
</form>
<?php } else { ?>
<div class="ok">
<h2>1. Créez le fichier <code>.htpasswd</code> dans ce dossier</h2>
<pre><?= htmlspecialchars($identifiant . ':' . $empreinte) ?></pre>

<h2>2. Créez le fichier <code>.htaccess</code> dans ce dossier</h2>
<pre>AuthType Basic
AuthName "Administration Sud Gresiv"
AuthUserFile <?= htmlspecialchars($dossier) ?>/.htpasswd
Require valid-user

&lt;FilesMatch "^\.ht"&gt;
    Require all denied
&lt;/FilesMatch&gt;</pre>

<h2>3. Envoyez les deux fichiers, puis supprimez celui-ci</h2>
<p>Ajoutez <code>.htpasswd</code> et <code>.htaccess</code> à votre dépôt,
publiez, vérifiez que l'accès demande bien un mot de passe, puis
<strong>supprimez <code>chiffrer.php</code></strong> du dépôt et du serveur.</p>
<p>Le fichier <code>.htpasswd</code> ne contient qu'une empreinte, non le
mot de passe. Il doit néanmoins rester dans un dépôt privé.</p>
</div>
<?php } ?>
</main></body>
</html>
"""

def balises_mesure(base, actif=True):
    """Bandeau de consentement et script de mesure.

    Renvoie deux chaînes vides si aucun identifiant n'est configuré, ou
    si la page ne doit pas être mesurée — l'espace d'administration, par
    exemple, qui est privé.
    """
    if not ANALYTICS or not actif:
        return "", ""
    return (BANDEAU_MESURE,
            f'<script src="{base}/assets/mesure.js?v={EMPREINTE}"></script>')


def page_simple(titre, description, corps, base, canonique,
                indexable=True, bandeau="", navigation="", recherche=True,
                mesure=True):
    """Gabarit des pages hors territoire : accueil, mentions légales.

    « recherche » retire la barre de recherche du bandeau. Elle sert au
    visiteur à trouver un territoire ; sur une page d'administration
    elle ne fait que prendre de la place.
    """
    champ_recherche = """<div class="find-groupe">
    <label class="find-label" for="q">Recherche</label>
    <div class="find">
      <input id="q" type="text" placeholder="Commune, code postal…"
             autocomplete="off">
      <div class="hits" id="hits"></div>
    </div>
  </div>""" if recherche else ""
    script_recherche = (f'<script>var BASE="{base}";</script>\n'
                        f'<script src="{base}/assets/recherche.js'
                        f'?v={EMPREINTE}"></script>') if recherche else ""
    bandeau_mesure, script_mesure = balises_mesure(base, mesure)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titre)} | {escape(TITRE_SITE)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{canonique}">
{'' if indexable else '<meta name="robots" content="noindex, nofollow">'}
<meta property="og:title" content="{escape(titre)} — {escape(TITRE_SITE)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonique}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/style.css?v={EMPREINTE}">
</head>
<body>

<div class="top"><div class="wrap">
  <a class="logo" href="{base}/">{escape(TITRE_SITE)}</a>
  {champ_recherche}
  <div class="top-fin"></div>
</div></div>
{bandeau}
{navigation}

<main><div class="wrap">
{corps}
</div></main>

<footer class="site"><div class="wrap">
  {escape(SOUS_TITRE)} — Licence Ouverte 2.0
  · <a href="{base}/fraicheur/">Fraîcheur des données</a>
  · <a href="{base}/mentions-legales/">Mentions légales</a>
</div></footer>

{bandeau_mesure}
{script_recherche}
{script_mesure}
</body>
</html>
"""


def corps_accueil(fiches, adresses, index_recherche):
    """Page d'accueil : ce que fait le site, et par où commencer.

    Elle servait jusqu'ici le contenu de la fiche du canton, ce qui
    produisait deux adresses pour un même contenu. Elle a désormais son
    propre propos.
    """
    canton = next((d for (niveau, _), d in fiches.items()
                   if niveau == "canton"), None)
    epci = next((d for (niveau, _), d in fiches.items()
                 if niveau == "epci"), None)

    chiffres = []
    if canton:
        t = canton["territoire"]
        for ident, libelle in (("POP-01", "habitants"),
                               ("GEO-13", "km²")):
            m = canton["mesures"].get(ident)
            if m and m.get("valeur") is not None:
                chiffres.append((nombre(m["valeur"]), libelle))
        if t.get("nombre_communes"):
            chiffres.insert(0, (str(t["nombre_communes"]), "communes"))

    pictogrammes = {"communes": "geographie", "habitants": "population",
                    "km²": "environnement"}
    blocs_chiffres = "".join(
        f'<div class="chiffre">{icone(pictogrammes.get(libelle, ""), "ico")}'
        f'<div class="chiffre-v">{valeur}</div>'
        f'<div class="chiffre-k">{escape(libelle)}</div></div>'
        for valeur, libelle in chiffres)

    portes = []
    for niveau, libelle in (("canton", "Le canton"),
                            ("epci", "L'intercommunalité")):
        cible = next((adresses[cle] for cle in adresses if cle[0] == niveau),
                     None)
        fiche = canton if niveau == "canton" else epci
        if not cible or not fiche:
            continue
        portes.append(
            f'<a class="chip" href="{cible}">{escape(libelle)} — '
            f'{escape(fiche["territoire"]["nom"])}</a>')
    portes = "".join(portes)

    communes = sorted(
        (t for t in index_recherche if t["niveau"] == "commune"),
        key=lambda t: -(t.get("population") or 0))[:8]
    vedettes = "".join(
        f'<a class="chip" href="{escape(t["url"])}">{escape(t["nom"])}</a>'
        for t in communes)

    rubriques_ouvertes = [r for r in RUBRIQUES if r["id"] and
                          any(r["id"] in rubriques_actives(d)
                              for d in fiches.values())]
    rubriques = "".join(f'<span class="chip">{escape(r["nom"])}</span>'
                        for r in rubriques_ouvertes)

    return f"""    <div class="hd"><h2>Les données publiques de votre commune</h2>
      <span class="n">{len(index_recherche)} territoires · {len(rubriques_ouvertes)} rubriques</span></div>

    <section class="bloc"><span class="dsp">Ce que vous trouverez ici</span>
      <div class="bl-grille pleine"><article class="bl-item">
        <p class="bl-texte">Population, logement, équipements, écoles,
        qualité de l'eau, restrictions sécheresse, risques naturels,
        niveau des nappes et débit des rivières — pour chaque commune du
        Sud Grésivaudan, ainsi que pour le canton et l'intercommunalité.</p>
        <p class="bl-texte">Toutes ces informations proviennent de
        sources publiques françaises. Chaque chiffre affiché porte le nom
        de sa source et la date de sa collecte. Quand une donnée n'existe
        pas à une échelle, elle n'est pas affichée plutôt qu'estimée.</p>
      </article></div>
    </section>

    <section class="chiffres">{blocs_chiffres}</section>

    <section class="bloc"><span class="dsp">Par où commencer</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Cherchez votre commune par son nom ou son code
        postal dans le champ ci-dessus, ou partez d'une vue d'ensemble.</p>
        <div class="chips">{portes}</div>
      </article>
      <article class="bl-item">
        <p class="bl-texte">Les communes les plus peuplées du territoire :</p>
        <div class="chips">{vedettes}</div>
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Rubriques disponibles</span>
      <div class="bl-grille"><article class="bl-item">
        <div class="chips">{rubriques}</div>
        <p class="bl-texte">D'autres rubriques s'ajouteront : transports,
        élections, prix des carburants.</p>
      </article></div>
    </section>"""


def etat_source(fichier, frequence_forcee=None):
    """Décrit l'état d'une source collectée : fraîcheur, volume, version."""
    chemin = RACINE / "data" / fichier
    if not chemin.exists():
        return {"present": False}

    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"present": True, "illisible": True}

    genere = contenu.get("genere_le")
    frequence = frequence_forcee or contenu.get("frequence") or "indéterminée"
    age = None
    if genere:
        try:
            age = (date.today() - date.fromisoformat(genere)).days
        except ValueError:
            age = None

    tolerance = TOLERANCE_FRAICHEUR.get(frequence)
    if age is None:
        etat, ton = "Date inconnue", "attention"
    elif tolerance and age > tolerance:
        etat, ton = "À rafraîchir", "attention"
    else:
        etat, ton = "À jour", "ok"

    volume = len(contenu.get("communes") or {}) or \
        len(contenu.get("territoires") or {})
    portee = "communes" if contenu.get("communes") else "territoires"

    return {"present": True, "illisible": False, "genere": genere, "age": age,
            "frequence": frequence, "etat": etat, "ton": ton,
            "volume": volume, "portee": portee,
            "version": contenu.get("version"),
            "source": contenu.get("source", ""),
            "millesime": contenu.get("millesime"),
            "poids": chemin.stat().st_size}


def corps_introuvable(adresses):
    """Page servie quand une adresse n'existe pas.

    Elle répond bien 404. Rediriger vers l'accueil ferait croire au
    moteur que la page existe — une « soft 404 », que Google traite
    comme une erreur — et ferait perdre au visiteur ce qu'il cherchait
    sans le lui dire.
    """
    entrees = []
    for niveau, libelle in (("canton", "du canton"),
                            ("epci", "de l'intercommunalité")):
        cible = next((c for (n, _), c in adresses.items() if n == niveau), None)
        if cible:
            entrees.append(f'<a class="bl-lien" href="/{cible}">'
                           f'Voir la fiche {libelle}</a>')

    return f"""    <div class="hd"><h2>Cette page n'existe pas</h2>
      <span class="n">Erreur 404</span></div>

    <section class="bloc"><span class="dsp">Où aller</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">L'adresse demandée ne correspond à aucune page
        de ce portail. Elle a peut-être changé, ou comporte une faute de
        frappe.</p>
        <p class="bl-texte">La recherche, en haut de page, trouve une
        commune par son nom, son code postal ou son code INSEE. C'est le
        plus rapide.</p>
        <a class="bl-lien" href="/">Retour à l'accueil</a>
        {" ".join(entrees)}
      </article></div>
    </section>"""


def corps_fraicheur():
    """Page publique : quand chaque donnée a été collectée pour la dernière fois.

    Un site statique affiche des chiffres figés à sa dernière génération.
    Le visiteur n'a aucun moyen de savoir si une source a cessé d'être
    mise à jour, et l'exploitant non plus tant que rien ne le montre.
    Cette page le dit.

    Elle n'expose rien du fonctionnement interne : ni nom de script, ni
    commande, ni chemin. C'est ce qui la distingue de la page
    d'administration, qui affiche les mêmes états avec les moyens d'agir.
    """
    lignes, a_jour, total = [], 0, 0

    for fichier, libelle, _script, _commande, frequence in SOURCES_SUIVIES:
        e = etat_source(fichier, frequence)
        total += 1

        if not e["present"]:
            lignes.append({"titre": libelle, "rang": 1,
                           "etat": ["Pas encore collectée", "attention"],
                           "details": {},
                           "texte": "Cette donnée n'est pas encore publiée "
                                    "sur le portail."})
            continue
        if e.get("illisible"):
            lignes.append({"titre": libelle, "rang": 0,   # le plus grave
                           "etat": ["Indisponible", "alerte"], "details": {},
                           "texte": "La dernière collecte est inexploitable ; "
                                    "les chiffres affichés sont ceux de la "
                                    "collecte précédente."})
            continue

        details = {}
        if e["genere"]:
            details["Dernière collecte"] = date.fromisoformat(
                e["genere"]).strftime("%d/%m/%Y")
        if e["age"] is not None:
            details["Ancienneté"] = ("le jour même" if e["age"] == 0
                                     else f"{e['age']} jour"
                                          f"{'s' if e['age'] > 1 else ''}")
        details["Rythme de publication"] = e["frequence"]
        if e.get("millesime"):
            details["Millésime des données"] = e["millesime"]
        if e.get("source"):
            details["Producteur"] = e["source"]
        if e["volume"]:
            details["Couverture"] = f"{e['volume']} {e['portee']}"

        if e["etat"] == "À jour":
            a_jour += 1
            texte = None
        else:
            texte = ("Cette donnée a dépassé le rythme de publication de son "
                     "producteur. Elle n'est pas fausse pour autant : elle "
                     "est simplement plus ancienne que ce qui est disponible "
                     "à la source.")

        entree = {"titre": libelle, "details": details,
                  "etat": [e["etat"], e["ton"]],
                  "rang": 2 if e["etat"] != "À jour" else 3,
                  "age": e["age"] if e["age"] is not None else 9999}
        if texte:
            entree["texte"] = texte
        lignes.append(entree)

    # Règle du site : un état en cours se lit du plus grave au moins
    # grave. Ici : collecte inexploitable, puis donnée absente, puis
    # retard, puis à jour. À état égal, la plus ancienne d'abord.
    lignes.sort(key=lambda x: (x.get("rang", 2), -x.get("age", 0), x["titre"]))

    entrees = "".join(
        f'<article class="bl-item"><header><h3>{escape(l["titre"])}</h3>'
        f'<span class="bl-etat {escape(l["etat"][1])}">'
        f'{escape(l["etat"][0])}</span></header>'
        + "".join(f'<div class="bl-ligne"><span class="bl-cle">{escape(k)}'
                  f'</span><span class="bl-val">{escape(str(v))}</span></div>'
                  for k, v in l["details"].items())
        + (f'<p class="bl-texte">{escape(l["texte"])}</p>'
           if l.get("texte") else "")
        + "</article>"
        for l in lignes)

    maj = date.today().strftime("%d/%m/%Y")
    return f"""    <div class="hd"><h2>Fraîcheur des données</h2>
      <span class="n">{a_jour} source{"s" if a_jour > 1 else ""} à jour
      sur {total} · pages produites le {maj}</span></div>

    <section class="bloc"><span class="dsp">État de chaque source</span>
      <div class="bl-grille">{entrees}</div>
      <p class="bl-note">Les dates indiquées sont celles de la collecte par
      ce portail, non celles de la publication par le producteur : une
      donnée collectée hier peut porter sur une année antérieure, et son
      millésime est alors précisé. Une source « à rafraîchir » a dépassé
      le rythme annoncé par son producteur ; ses valeurs restent celles
      qui ont été publiées, elles ne deviennent pas fausses en
      vieillissant.</p>
    </section>

    <section class="bloc"><span class="dsp">Pourquoi cette page</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Ce portail est un site statique : ses pages
        sont écrites à l'avance, elles n'interrogent aucune source au
        moment où vous les consultez. Les chiffres affichés sont donc
        ceux de la dernière collecte, et non ceux de l'instant.</p>
        <p class="bl-texte">Plutôt que de laisser croire à une
        actualisation permanente, cette page montre l'âge réel de chaque
        donnée. Si une source cesse d'être mise à jour, cela se voit
        ici — c'est la contrepartie honnête d'un site qui ne prétend pas
        être un service en temps réel.</p>
        <p class="bl-texte">Pour toute décision engageante, l'organisme
        producteur et le document officiel font seuls foi. Chaque
        indicateur du site porte le nom de sa source.</p>
      </article></div>
    </section>"""


EXTENSIONS_DOCUMENTS = (".md", ".txt", ".csv", ".pdf", ".png", ".jpg",
                        ".jpeg", ".webp", ".svg", ".xlsx", ".docx", ".zip")


def documents_lisibles():
    """Documents que la page de consultation servira réellement.

    Le compte est fait sur les mêmes extensions que documents.php : un
    fichier d'un autre type présent dans le dossier n'est ni listé ni
    compté, et ne doit donc pas apparaître ici non plus.
    """
    dossier = RACINE / DOSSIER_ADMIN / DOSSIER_DOCUMENTS
    if not dossier.is_dir():
        return 0
    return sum(1 for f in dossier.iterdir()
               if f.is_file() and not f.name.startswith(".")
               and f.suffix.lower() in EXTENSIONS_DOCUMENTS)


def corps_administration(fiches, protegee):
    """Tableau de bord interne : état des sources et actions à mener."""
    lignes, a_rafraichir = [], []

    for fichier, libelle, script, commande, frequence in SOURCES_SUIVIES:
        e = etat_source(fichier, frequence)
        if not e["present"]:
            lignes.append({
                "titre": libelle, "etat": ["Jamais collectée", "alerte"],
                "details": {"Script": script, "Commande": commande},
                "texte": "Cette source n'a pas encore été collectée."})
            a_rafraichir.append(commande)
            continue
        if e.get("illisible"):
            lignes.append({
                "titre": libelle, "etat": ["Fichier illisible", "alerte"],
                "details": {"Fichier": fichier, "Commande": commande}})
            a_rafraichir.append(commande)
            continue

        details = {
            "Collecté le": (date.fromisoformat(e["genere"]).strftime("%d/%m/%Y")
                            if e["genere"] else "inconnu"),
            "Ancienneté": (f"{e['age']} jour(s)" if e["age"] is not None
                           else "inconnue"),
            "Fréquence attendue": e["frequence"],
            "Couverture": f"{e['volume']} {e['portee']}",
            "Rafraîchir par": commande,
        }
        if e.get("millesime"):
            details["Millésime des données"] = e["millesime"]
        if e.get("poids"):
            details["Poids du fichier"] = f"{e['poids'] / 1024:.0f} Ko"

        lignes.append({"titre": libelle, "etat": [e["etat"], e["ton"]],
                       "details": details})
        if e["ton"] != "ok":
            a_rafraichir.append(commande)

    entrees = "".join(
        f'<article class="bl-item"><header><h3>{escape(l["titre"])}</h3>'
        f'<span class="bl-etat {escape(l["etat"][1])}">'
        f'{escape(l["etat"][0])}</span></header>'
        + "".join(f'<div class="bl-ligne">'
                  f'<span class="bl-cle">{escape(c)}</span>'
                  f'<span class="bl-val">{escape(str(v))}</span></div>'
                  for c, v in l["details"].items())
        + (f'<p class="bl-texte">{escape(l["texte"])}</p>'
           if l.get("texte") else "")
        + "</article>" for l in lignes)

    if a_rafraichir:
        vus, ordonnees = set(), []
        for c in a_rafraichir:
            if c not in vus:
                vus.add(c)
                ordonnees.append(c)
        actions = ("<p class=\"bl-texte\">À lancer, puis "
                   "<code>python lancer.py --site</code> :</p>"
                   + "".join(f'<div class="bl-ligne">'
                             f'<span class="bl-cle">{i}</span>'
                             f'<span class="bl-val">{escape(c)}</span></div>'
                             for i, c in enumerate(ordonnees, start=1)))
    else:
        actions = ('<p class="bl-texte">Toutes les sources sont à jour. '
                   "Aucune collecte n'est nécessaire.</p>")

    chantiers = "".join(
        f'<article class="bl-item"><header><h3>{escape(nom)}</h3>'
        f'<span class="bl-etat neutre">À venir</span></header>'
        f'<div class="bl-ligne"><span class="bl-cle">Source</span>'
        f'<span class="bl-val">{escape(source)}</span></div>'
        f'<p class="bl-texte">{escape(note)}</p></article>'
        for nom, source, note in CHANTIERS)

    controles = "".join(
        f'<div class="bl-ligne"><span class="bl-cle">{escape(quoi)}</span>'
        f'<span class="bl-val">{escape(comment)}</span></div>'
        for quoi, comment in (
            ("Communes joignables", "47/47 à la génération"),
            ("Cartes avec noms", "49/49 après 05_cartes.py"),
            ("Composition du canton", "44 communes, décret n° 2014-180"),
            ("Archive INSEE hors dépôt", "data/dossier-complet.zip ignoré"),
            ("Mentions légales", "produites si MENTIONS est renseigné"),
            ("Liens morts", "aucun renvoi vers un bloc absent"),
        ))

    saisis = []
    for fichier, libelle in REFERENTIELS_SAISIS:
        chemin = RACINE / "data" / fichier
        if not chemin.exists():
            saisis.append((libelle, "Absent", "alerte", {}))
            continue
        try:
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saisis.append((libelle, "Illisible", "alerte", {}))
            continue
        echeance = contenu.get("valable_jusqu_au")
        details = {"Texte": contenu.get("texte", "—"),
                   "Saisi le": contenu.get("saisi_le", "—"),
                   "Valable jusqu'au": echeance or "sans limite",
                   "Saisie complète": ("oui" if contenu.get("saisie_complete")
                                       else "NON — communes manquantes")}
        etat, ton = "À jour", "ok"
        if not contenu.get("saisie_complete"):
            etat, ton = "Saisie incomplète", "attention"
        if echeance:
            try:
                reste = (date.fromisoformat(echeance) - date.today()).days
                details["Échéance dans"] = f"{reste} jour(s)"
                if reste < 0:
                    etat, ton = "Périmé", "alerte"
                elif reste < 45:
                    etat, ton = "À renouveler", "attention"
            except ValueError:
                pass
        saisis.append((libelle, etat, ton, details))

    bloc_saisis = "".join(
        f'<article class="bl-item"><header><h3>{escape(libelle)}</h3>'
        f'<span class="bl-etat {ton}">{escape(etat)}</span></header>'
        + "".join(f'<div class="bl-ligne">'
                  f'<span class="bl-cle">{escape(c)}</span>'
                  f'<span class="bl-val">{escape(str(v))}</span></div>'
                  for c, v in details.items())
        + "</article>" for libelle, etat, ton, details in saisis)

    total_pages = sum(1 for _ in RACINE.rglob("index.html"))

    return f"""    <div class="hd"><h2>Administration</h2>
      <span class="n"><a href="documents.php">Documents de travail</a>
      · <a href="journal.php">Journal du leurre</a></span></div>

    <section class="bloc"><span class="dsp">État des sources</span>
      <div class="bl-grille">{entrees}</div>
      <p class="bl-note">Une source « à rafraîchir » a dépassé la
      fréquence de publication de son producteur. Cela ne rend pas les
      données fausses : elles sont simplement plus anciennes que ce que
      la source propose.</p>
    </section>

    <section class="bloc"><span class="dsp">Actions à mener</span>
      <div class="bl-grille"><article class="bl-item">{actions}</article></div>
    </section>

    <section class="bloc"><span class="dsp">Contrôles à vérifier</span>
      <div class="bl-grille"><article class="bl-item">{controles}</article></div>
      <p class="bl-note">Ces contrôles s'affichent à l'exécution des
      scripts. Un écart signale un problème silencieux.</p>
    </section>

    <section class="bloc"><span class="dsp">Référentiels saisis à la main</span>
      <div class="bl-grille">{bloc_saisis}</div>
      <p class="bl-note">Ces données sont transcrites d'un document
      officiel, non collectées. Elles ne se rafraîchissent pas seules :
      leur date de validité est la seule garantie contre une information
      périmée. Passée l'échéance, le collecteur refuse de publier.</p>
    </section>

    <section class="bloc"><span class="dsp">Automatisation</span>
      <div class="bl-grille"><article class="bl-item">
        <div class="bl-ligne"><span class="bl-cle">Mode actuel</span>
          <span class="bl-val">manuel</span></div>
        <div class="bl-ligne"><span class="bl-cle">Cible</span>
          <span class="bl-val">GitHub Actions</span></div>
        <div class="bl-ligne"><span class="bl-cle">Écarté</span>
          <span class="bl-val">CRON OVH — Python indisponible</span></div>
        <p class="bl-texte">Une fois en place : sécheresse chaque jour,
        nappes et rivières chaque semaine, le reste chaque mois. Les
        carburants imposeront plusieurs passages par jour.</p>
        <p class="bl-texte">Marche à suivre détaillée dans
        <code>AUTOMATISATION.md</code>. Point de vigilance : GitHub
        désactive les tâches planifiées après soixante jours sans
        activité humaine sur le dépôt, sans le signaler.</p>
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Chantiers ouverts</span>
      <div class="bl-grille">{chantiers}</div>
    </section>

    <section class="bloc"><span class="dsp">Sécurité</span>
      <div class="bl-grille"><article class="bl-item">
        <div class="bl-ligne"><span class="bl-cle">Accès à cette page</span>
          <span class="bl-val">{"protégé par mot de passe"
                                if protegee else "NON PROTÉGÉ"}</span></div>
        <div class="bl-ligne"><span class="bl-cle">Leurre</span>
          <span class="bl-val">/{DOSSIER_LEURRE}/</span></div>
        <div class="bl-ligne"><span class="bl-cle">Conservation</span>
          <span class="bl-val">{RETENTION_JOURNAL} jours</span></div>
        <div class="bl-ligne"><span class="bl-cle">Adresses</span>
          <span class="bl-val">tronquées d'un segment</span></div>
        <p class="bl-texte">L'ancienne adresse d'administration présente
        une fausse page de connexion qui ne mène nulle part, impose une
        attente de {DELAI_LEURRE} secondes et consigne chaque tentative.
        Aucun identifiant saisi n'est enregistré.</p>
        <a class="bl-lien" href="journal.php">Consulter le journal</a>
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Documentation</span>
      <div class="bl-grille"><article class="bl-item">
        <div class="bl-ligne"><span class="bl-cle">Dossier</span>
          <span class="bl-val">{DOSSIER_ADMIN}/{DOSSIER_DOCUMENTS}/</span></div>
        <div class="bl-ligne"><span class="bl-cle">Documents lisibles</span>
          <span class="bl-val">{documents_lisibles()}</span></div>
        <p class="bl-texte">Les documents de travail du projet, relisibles
        depuis un téléphone. La page ne sert que les extensions qu'elle
        déclare : une clé ou un fichier de configuration déposés là par
        mégarde n'y apparaîtraient pas. Elle ne permet ni dépôt ni
        suppression — l'ajout passe par le dépôt.</p>
        <a class="bl-lien" href="documents.php">Consulter les documents</a>
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Volumétrie</span>
      <div class="bl-grille"><article class="bl-item">
        <div class="bl-ligne"><span class="bl-cle">Territoires publiés</span>
          <span class="bl-val">{len(fiches)}</span></div>
        <div class="bl-ligne"><span class="bl-cle">Pages produites</span>
          <span class="bl-val">{total_pages}</span></div>
        <div class="bl-ligne"><span class="bl-cle">Générées le</span>
          <span class="bl-val">{date.today().strftime("%d/%m/%Y")}</span></div>
      </article></div>
    </section>"""


def corps_mentions():
    # La section n'existe que si la mesure est configurée : un site sans
    # traceur ne doit pas décrire un traceur qu'il n'a pas.
    bloc_mesure = """
    <section class="bloc"><span class="dsp">Mesure d'audience</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Ce site mesure sa fréquentation avec Google
        Analytics, afin de savoir quelles pages sont consultées. Cette
        mesure dépose des traceurs sur votre appareil : elle ne
        s'active donc qu'après votre accord explicite, demandé par un
        bandeau lors de votre première visite.</p>
        <p class="bl-texte">Tant que vous n'avez pas accepté, et si vous
        refusez, <strong>aucun script de Google n'est chargé</strong> et
        aucune donnée ne lui est transmise. Le refus n'enlève rien au
        contenu du site. Votre réponse est conservée dans votre
        navigateur, pour ne pas vous la redemander à chaque page.</p>
        <p class="bl-texte">Les signaux publicitaires sont désactivés :
        la mesure se limite à l'audience et ne sert ni au ciblage
        publicitaire ni au recoupement entre sites.</p>
        <button type="button" id="mesure-revenir" class="bl-lien" hidden
          style="cursor:pointer;border:0;background:none;padding:0">
          Revenir sur mon choix</button>
      </article></div>
    </section>""" if ANALYTICS else ""

    lignes = []
    for cle, libelle in (("editeur", "Éditeur"), ("statut", "Statut"),
                         ("siret", "SIRET"), ("adresse", "Adresse"),
                         ("courriel", "Contact"),
                         ("directeur", "Directeur de la publication"),
                         ("hebergeur", "Hébergeur")):
        valeur = MENTIONS.get(cle, "").strip()
        if not valeur:
            continue
        contenu = (f'<a href="mailto:{escape(valeur)}">{escape(valeur)}</a>'
                   if cle == "courriel" else escape(valeur))
        lignes.append(f'<div class="bl-ligne">'
                      f'<span class="bl-cle">{escape(libelle)}</span>'
                      f'<span class="bl-val">{contenu}</span></div>')

    return f"""    <div class="hd"><h2>Mentions légales</h2></div>
    <section class="bloc"><span class="dsp">Éditeur et hébergement</span>
      <div class="bl-grille"><article class="bl-item">
        {"".join(lignes)}
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Données publiées</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Les données présentées proviennent
        exclusivement de sources publiques françaises, diffusées sous
        Licence Ouverte 2.0 : INSEE, IGN, Hub'Eau, VigiEau, Géorisques,
        ministère de l'Éducation nationale. Chaque valeur affichée porte
        le nom de sa source et la date de sa collecte.</p>
        <p class="bl-texte">Ce site n'est ni officiel ni institutionnel.
        En cas d'écart avec la publication d'origine, cette dernière fait
        seule référence. Les données sont republiées sans modification de
        fond ; leur mise en forme et leur mise en relation relèvent de
        l'éditeur.</p>
      </article></div>
    </section>

    <section class="bloc"><span class="dsp">Vie privée</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Ce site ne demande aucune inscription et ne
        collecte aucune donnée personnelle lors d'une consultation
        ordinaire. Seules les tentatives d'accès à l'espace
        d'administration sont consignées à des fins de sécurité, avec une
        adresse tronquée de son dernier segment et une conservation
        limitée à quelques mois. Les fonds de carte sont fournis par la
        Géoplateforme de l'IGN et les polices de caractères par Google
        Fonts : la consultation d'une page comportant une carte adresse
        une requête à ces services.</p>
      </article></div>
    </section>
{bloc_mesure}

    <section class="bloc"><span class="dsp">Signaler une erreur</span>
      <div class="bl-grille"><article class="bl-item">
        <p class="bl-texte">Une donnée vous paraît inexacte ? Vérifiez
        d'abord auprès de la source citée sur la fiche : une correction
        à l'origine se répercute ici à la collecte suivante. Si l'erreur
        vient de ce site, signalez-la à l'adresse ci-dessus.</p>
      </article></div>
    </section>"""


# ══════════════════════════════════════════════════════════════════
# PAGES D'ANNONCE
#
# Une rubrique décidée mais pas encore alimentée peut porter une page
# d'annonce : elle dit ce qui sera publié, d'où viendra la donnée, et
# sous quelles réserves.
#
# Le motif : une adresse met des semaines à être explorée puis indexée
# par les moteurs. La créer avant la donnée fait gagner ce délai.
#
# La réserve, sérieuse : quarante-sept pages au texte identique sont
# exactement le schéma que les moteurs déclassent. Chaque annonce porte
# donc des faits propres au territoire — nom, code, codes postaux,
# rattachements, et pour les élections les élus déjà collectés. Une
# annonce qui n'aurait rien de propre au territoire ne vaudrait pas
# la peine d'être publiée.
#
# Elle s'efface d'elle-même : elle n'est rendue que si la rubrique n'a
# aucune mesure à montrer. Le jour où la donnée arrive, l'annonce
# disparaît sans intervention — même principe que le référentiel saisi
# à la main qui se retire à sa péremption.
#
# Ces pages n'annoncent aucune date : une promesse tenue en retard vaut
# moins que pas de promesse du tout.
# ══════════════════════════════════════════════════════════════════


def parents_de(d):
    """Canton et intercommunalité de rattachement, par niveau."""
    return {r["niveau"]: r["nom"]
            for r in ((d.get("rattachements") or {}).get("au_dessus") or [])}


def bloc_annonce(ancre, titre, details, textes, note, lien=None):
    """Gabarit commun aux pages d'annonce."""
    lignes = "".join(
        f'<div class="bl-ligne"><span class="bl-cle">{escape(cle)}</span>'
        f'<span class="bl-val">{escape(str(valeur))}</span></div>'
        for cle, valeur in details.items())
    paragraphes = "".join(f'<p class="bl-texte">{escape(x)}</p>' for x in textes)
    renvoi = (f'<a class="bl-lien" href="{escape(lien[0])}">'
              f'{escape(lien[1])}</a>' if lien else "")
    return (f'    <section class="bloc" id="{escape(ancre)}">'
            f'<span class="dsp">{icone(ancre)}{escape(titre)}</span>'
            f'<div class="bl-grille"><article class="bl-item">'
            f'{lignes}{paragraphes}{renvoi}</article></div>'
            f'<p class="bl-note">{escape(note)}</p></section>')


def article_contracte(nom):
    """« Le Sud Grésivaudan » → « du Sud Grésivaudan »."""
    bas = nom.lower()
    for debut, forme in (("le ", "du "), ("la ", "de la "),
                         ("les ", "des "), ("l'", "de l'")):
        if bas.startswith(debut):
            return forme + nom[len(debut):]
    return "de " + nom


def situe_dans(t):
    """Formule de lieu correcte selon le niveau du territoire.

    « à Saint-Marcellin », mais « dans le canton du Sud Grésivaudan » :
    écrire « à Le Sud Grésivaudan » suffirait à décrédibiliser la page.
    """
    if t["niveau"] == "commune":
        return f"à {t['nom']}"
    if t["niveau"] == "canton":
        return f"dans le canton {article_contracte(t['nom'])}"
    return f"dans l'intercommunalité {t['nom']}"


def enumerer(elements):
    """« a, b et c » — une énumération française se termine par « et »."""
    elements = [x for x in elements if x]
    if len(elements) <= 1:
        return "".join(elements)
    return ", ".join(elements[:-1]) + " et " + elements[-1]


def identite(t):
    """Code et codes postaux, pour ancrer l'annonce dans son territoire."""
    details = {}
    libelle = {"epci": "Code SIREN", "canton": "Code INSEE du canton"}
    details[libelle.get(t["niveau"], "Code INSEE")] = t["code"]
    codes = t.get("codes_postaux") or []
    if codes:
        details["Code postal" if len(codes) == 1
                else "Codes postaux"] = ", ".join(codes)
    elif t.get("nombre_communes"):
        details["Communes"] = t["nombre_communes"]
    return details


def annonce_carburants(d, base, chemin):
    t = d["territoire"]
    nom = t["nom"]
    parents = parents_de(d)
    nombre = t.get("nombre_communes")

    details = {
        "État": "en préparation",
        "Carburants suivis": "Gazole, SP95, SP95-E10, SP98, E85, GPL",
        "Source": "Base nationale des prix des carburants, "
                  "data.economie.gouv.fr",
        "Maille": "la station-service",
        "Rythme prévu": "plusieurs relevés par jour",
    }
    details.update(identite(t))

    if t["niveau"] == "commune":
        rattachement = " et ".join(
            x for x in (f"du canton {parents['canton']}" if parents.get("canton")
                        else "",
                        f"de l'intercommunalité {parents['epci']}"
                        if parents.get("epci") else "") if x)
        situe = (f"{nom} relève {rattachement}. " if rattachement else "")
        etendue = (f"Les stations-service situées à {nom} y figureront, ainsi "
                   f"que les plus proches des communes voisines : un "
                   f"automobiliste ne compare pas les prix à l'intérieur "
                   f"d'une seule commune.")
    else:
        situe = ""
        etendue = (f"Les stations-service des {nombre} communes seront "
                   f"listées, du prix le plus bas au plus élevé, avec la date "
                   f"et l'heure du dernier relevé de chacune."
                   if nombre else
                   "Les stations-service du territoire seront listées, du "
                   "prix le plus bas au plus élevé.")

    textes = [
        f"Le prix des carburants n'est pas encore publié {situe_dans(t)}. "
        f"Cette page annonce ce qui le sera : le prix du gazole, du SP95, du "
        f"SP95-E10, du SP98, du superéthanol E85 et du GPL, station-service "
        f"par station-service, avec l'heure du dernier relevé.",
        situe + etendue,
        "La donnée vient de la base nationale que les distributeurs "
        "alimentent eux-mêmes. Elle change plusieurs fois par jour : sa "
        "publication attend la mise en place de la collecte automatique, "
        "sans laquelle le portail afficherait des prix de la veille.",
    ]
    note = ("Les prix sont déclarés par les distributeurs et peuvent changer "
            "entre deux relevés : le prix affiché en station fait seul foi. "
            "Ce portail ne comporte aucune publicité ni mise en avant "
            "rémunérée, et n'en comportera pas.")

    codes = t.get("codes_postaux") or []
    reperage = f" ({codes[0]})" if codes else ""
    description = (f"Prix des carburants {situe_dans(t)}{reperage} : gazole, "
                   f"SP95-E10, SP98, E85 et GPL par station-service. Relevés "
                   f"en préparation sur le portail de données du Sud "
                   f"Grésivaudan.")

    return bloc_annonce("carburants", "Prix des carburants — en préparation",
                        details, textes, note), description


def annonce_elections(d, base, chemin):
    t = d["territoire"]
    nom = t["nom"]
    m = d["mesures"]

    def valeur(ident):
        return (m.get(ident) or {}).get("valeur")

    details = {
        "État": "en préparation",
        "Source": "Ministère de l'Intérieur — résultats officiels",
        "Maille": "le bureau de vote",
        "Scrutins prévus": "présidentielle, législatives, départementales, "
                           "municipales, européennes",
        "Le soir du scrutin": "publication après 20 heures, à la fermeture "
                              "du dernier bureau de vote",
    }
    details.update(identite(t))

    # Faits déjà collectés : ils distinguent cette page de ses voisines
    # et lui donnent une valeur propre dès aujourd'hui.
    acquis = []
    if valeur("POL-01"):
        details["Maire en fonction"] = valeur("POL-01")
        acquis.append(f"le maire {valeur('POL-01')}")
    if valeur("POL-02"):
        details["Conseil municipal"] = f"{valeur('POL-02')} élus"
        acquis.append(f"les {valeur('POL-02')} membres du conseil municipal")
    if valeur("POL-10"):
        details["Conseillers départementaux"] = f"{valeur('POL-10')} élus"
        acquis.append(f"le binôme de {valeur('POL-10')} conseillers "
                      f"départementaux")
    if valeur("POL-20"):
        details["Président"] = valeur("POL-20")
        acquis.append(f"la présidence assurée par {valeur('POL-20')}")
    if valeur("POL-21"):
        details["Conseil communautaire"] = f"{valeur('POL-21')} élus"
        acquis.append(f"les {valeur('POL-21')} conseillers communautaires")

    textes = [
        f"Les résultats des élections {situe_dans(t)} ne sont pas encore "
        f"publiés. "
        f"Cette page annonce ce qui le sera : par bureau de vote, le nombre "
        f"d'inscrits, de votants et d'abstentions, les bulletins blancs et "
        f"nuls, et les voix obtenues par chaque candidat ou chaque liste, du "
        f"scrutin le plus récent au plus ancien.",
    ]
    if acquis:
        textes.append("En attendant, les élus en fonction sont déjà "
                      "publiés : " + enumerer(acquis) + ".")
    textes.append(
        "Le soir d'un scrutin, aucun chiffre ne sera publié avant 20 heures, "
        "à la fermeture du dernier bureau de vote. C'est une obligation "
        "légale ; le verrou horaire est posé dans le traitement lui-même, et "
        "pas seulement à l'affichage. Tant que le dépouillement n'est pas "
        "achevé, les résultats seront annoncés comme partiels, avec l'heure "
        "de la dernière relève et la part de bureaux dépouillés.")

    note = ("Les résultats proclamés par le ministère de l'Intérieur et le "
            "bureau centralisateur font seuls foi. Les chiffres publiés ici "
            "seront repris de la publication officielle, jamais saisis à "
            "la main.")

    lien = ((f"{base}/{chemin}elections/elus/", "Voir les élus en fonction")
            if acquis else None)

    description = (f"Résultats des élections {situe_dans(t)} : présidentielle, "
                   f"législatives, départementales, municipales et "
                   f"européennes par bureau de vote. Publication en "
                   f"préparation sur le portail de données du Sud Grésivaudan.")

    return bloc_annonce("resultats", "Résultats électoraux — en préparation",
                        details, textes, note, lien), description


ANNONCES = {
    "carburants": annonce_carburants,
    "elections-resultats": annonce_elections,
}


def page(d, base, canonique, adresses, fiches, rubrique,
         chemin_territoire, actives, sous=None, sous_dispo=(),
         accueil=False):
    t = d["territoire"]
    niveau = LIBELLE.get(t["niveau"], t["niveau"])

    # Une page de rubrique dotée de sous-rubriques n'affiche qu'une
    # sélection : le détail vit dans les sous-rubriques. Sans sélection
    # définie, on affiche tout le contenu de la rubrique.
    selection = rubrique.get("selection") if sous is None else None

    toutes = indicateurs_de(rubrique, d["mesures"], sous, selection)
    mesures = {k: v for k, v in toutes.items() if v["valeur"] is not None}

    # Tout indicateur en alerte remonte, même hors sélection : une eau
    # non conforme ou une nappe très basse doit se voir dès l'entrée.
    # Sur une page de sélection, l'ordre voulu est celui de la liste :
    # les rangs internes aux collecteurs ne valent qu'à l'intérieur de
    # leur propre sous-rubrique.
    if selection is not None:
        ordre = {ident: i for i, ident in enumerate(selection)}
        mesures.update(alertes(indicateurs_de(rubrique, d["mesures"]), mesures))
    else:
        ordre = {}

    def rang_de(ident, m):
        if selection is not None:
            return ordre.get(ident, 900)      # alertes remontées en fin
        return m.get("rang", 500)

    mesures = dict(sorted(
        mesures.items(),
        key=lambda kv: (not kv[1].get("mise_en_avant"),
                        rang_de(kv[0], kv[1]),
                        kv[0])))

    # Destination de chaque renvoi « Voir le détail » : ancre locale si le
    # bloc est sur cette page, adresse complète sinon.
    index = index_des_blocs(d)
    renvois = {}
    for m in mesures.values():
        ancre = m.get("ancre")
        if not ancre or ancre in renvois:
            continue
        destination = adresse_du_detail(ancre, index, rubrique, sous,
                                        base, chemin_territoire)
        if destination:
            renvois[ancre] = destination

    # Points d'intérêt des blocs présents sur cette page : ils se
    # superposent à la carte du territoire.
    points = []
    for b in blocs_de(d, rubrique, sous):
        points.extend(b.get("points") or [])

    # Les indicateurs mis en avant forment un bandeau à part, au-dessus
    # de la grille ordinaire.
    bandeaux = {k: v for k, v in mesures.items() if v.get("mise_en_avant")}
    ordinaires = {k: v for k, v in mesures.items() if not v.get("mise_en_avant")}
    resume = ", ".join(f"{m['nom'].lower()} {nombre(m['valeur'])} {m['unite']}"
                       for m in list(mesures.values())[:3])
    description = (f"{t['nom']} ({niveau}) : {resume}. "
                   f"Données publiques INSEE et IGN.")

    # Le code d'un EPCI est un numéro SIREN, pas un code INSEE :
    # les nommer pareil serait une erreur de fond.
    ref = ("Code SIREN Intercommunalité" if t["niveau"] == "epci"
           else f"Code INSEE {niveau}")
    codes = t.get("codes_postaux") or []
    if codes:
        libelle_cp = "Codes postaux" if len(codes) > 1 else "Code postal"
        sous_titre = (f"<strong>{libelle_cp} {escape(', '.join(codes))}</strong>"
                      f" · {ref} {escape(t['code'])}")
    elif t.get("nombre_communes"):
        sous_titre = (f"{t['nombre_communes']} communes"
                      f" · {ref} {escape(t['code'])}")
    else:
        sous_titre = f"{ref} {escape(t['code'])}"

    if codes:
        description = (f"{t['nom']} ({codes[0]}) : {resume}. "
                       f"Données publiques INSEE et IGN.")

    # Page d'annonce : rendue seulement si la rubrique n'a rien à
    # montrer, et s'effaçant d'elle-même dès qu'une donnée arrive.
    annonce = (ANNONCES.get((sous or rubrique).get("annonce"))
               if not mesures else None)
    annonce_html = ""
    if annonce:
        annonce_html, description = annonce(d, base, chemin_territoire)

    suffixe_titre = (sous["nom"] if sous
                     else (rubrique["nom"] if rubrique["id"] else niveau))

    # Le titre de premier niveau doit dire de quoi parle LA page, pas
    # seulement de quel territoire. Sans cela, les quinze pages d'une
    # commune portent le même « Saint-Marcellin » : pour un moteur, rien
    # ne les distingue, et le signal le plus fort de la page est perdu.
    titre_rubrique = (f'<span class="h1-rub"> — {escape(suffixe_titre)}</span>'
                      if rubrique["id"] else "")

    maj = date.fromisoformat(d["genere_le"]).strftime("%d/%m/%Y")
    bandeau_mesure, script_mesure = balises_mesure(base)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t['nom'])} — {escape(suffixe_titre)} | {escape(TITRE_SITE)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{canonique}">
<meta property="og:title" content="{escape(t['nom'])} — {escape(TITRE_SITE)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonique}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/style.css?v={EMPREINTE}">
</head>
<body>

<div class="top"><div class="wrap">
  <a class="logo" href="{base}/">{escape(TITRE_SITE)}</a>
  <div class="find-groupe">
    <label class="find-label" for="q">Recherche</label>
    <div class="find">
      <input id="q" type="text" placeholder="Commune, code postal…"
             autocomplete="off">
      <div class="hits" id="hits"></div>
    </div>
  </div>
  <div class="top-fin"></div>
</div></div>

<div class="terr"><div class="wrap">
  <div class="terr-identite">
    <div class="kind dsp">{escape(niveau)}</div>
    <h1>{escape(t['nom'])}{titre_rubrique}</h1>
    <div class="sub">{sous_titre}</div>
  </div>
  {rappel_parents(d, base, adresses)}
</div></div>

{nav_rubriques(base, chemin_territoire, actives, rubrique["id"])}
{nav_sous(base, chemin_territoire, rubrique, sous_dispo, sous)}

<main><div class="wrap">
{bloc_rattachements(d, base, adresses)}
{bloc_bandeaux(bandeaux, renvois)}
{annonce_html}
    <div class="cards">
{chr(10).join(carte(k, v, renvois) for k, v in ordinaires.items())}
    </div>
{bloc_liste(d, rubrique, sous)}
{bloc_carte(t, base, adresses, fiches, d["rattachements"].get("en_dessous"), rubrique, sous, points)}
</div></main>

<footer class="site"><div class="wrap">
  {escape(SOUS_TITRE)} — Licence Ouverte 2.0 · Contrat v{d['version_contrat']}
  · Mise à jour du {maj}
  · <a href="{base}/data/publie/v1/{t['niveau']}/{t['code']}.json">données brutes</a>
  · <a href="{base}/fraicheur/">Fraîcheur des données</a>
  · <a href="{base}/mentions-legales/">Mentions légales</a>
</div></footer>

{bandeau_mesure}
<script>var BASE="{base}";</script>
<script src="{base}/assets/recherche.js?v={EMPREINTE}"></script>
{script_mesure}
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nGénération des pages statiques")
    print("─" * 46)
    print(f"  version {VERSION_SCRIPT} du script")

    if not (PUBLIE / "index.json").exists():
        print(f"\n[ERREUR] {PUBLIE / 'index.json'} introuvable.")
        print("  Lancez d'abord : python 03_agregation.py")
        sys.exit(1)

    index = json.loads((PUBLIE / "index.json").read_text(encoding="utf-8"))

    # nettoyage des dossiers générés uniquement
    # Les cartes sont produites par 05_cartes.py : on les préserve.
    cartes = ASSETS / "cartes"
    garde = None
    if cartes.exists():
        garde = RACINE / ".cartes-tmp"
        if garde.exists():
            shutil.rmtree(garde)
        shutil.move(str(cartes), str(garde))

    for sous in ("commune", "canton", "epci", "assets"):
        if (RACINE / sous).exists():
            shutil.rmtree(RACINE / sous)

    ASSETS.mkdir(parents=True, exist_ok=True)

    global EMPREINTE
    EMPREINTE = hashlib.sha1(
        (CSS + JS + MESURE_JS + ANALYTICS).encode("utf-8")).hexdigest()[:8]
    if garde:
        shutil.move(str(garde), str(cartes))
    (ASSETS / "style.css").write_text(CSS.strip(), encoding="utf-8")
    (ASSETS / "recherche.js").write_text(JS.strip(), encoding="utf-8")
    if ANALYTICS:
        (ASSETS / "mesure.js").write_text(
            MESURE_JS.replace("IDENTIFIANT", ANALYTICS).strip(),
            encoding="utf-8")
    elif (ASSETS / "mesure.js").exists():
        # L'identifiant a été retiré : le script doit disparaître du site,
        # pas seulement cesser d'être appelé.
        (ASSETS / "mesure.js").unlink()

    # ── premier passage : table des adresses ─────────────────────
    # Le nom porté par un territoire dans ses propres données fait foi.
    # Les rattachements peuvent l'abréger, d'où cette table de référence.
    fiches, adresses = {}, {}
    for t in index["territoires"]:
        fichier = PUBLIE / t["niveau"] / f"{t['code']}.json"
        if not fichier.exists():
            print(f"  [ignoré] {fichier} absent")
            continue
        d = json.loads(fichier.read_text(encoding="utf-8"))
        # Le code sert à construire un chemin de fichier : on refuse tout
        # ce qui n'est pas alphanumérique, par principe.
        if not t["code"].replace("-", "").isalnum():
            print(f"  [BLOCAGE] Code de territoire inattendu : {t['code']!r}")
            sys.exit(1)

        cle = (t["niveau"], t["code"])
        fiches[cle] = d
        adresses[cle] = f"{t['niveau']}/{t['code']}-{slug(d['territoire']['nom'])}/"

    if not fiches:
        print("\n[BLOCAGE] Aucune fiche exploitable.")
        sys.exit(1)

    # ── second passage : écriture des pages ──────────────────────
    liens_site, recherche, redirections = [], [], []

    for (niveau, code), d in fiches.items():
        t = d["territoire"]
        chemin = adresses[(niveau, code)]
        actives = rubriques_actives(d)

        def ecrire(rubrique, sous, sous_dispo):
            morceaux = [rubrique["id"], sous["id"] if sous else ""]
            suffixe = "".join(f"{m}/" for m in morceaux if m)
            dossier = RACINE / chemin / suffixe.rstrip("/") if suffixe \
                else RACINE / chemin
            dossier.mkdir(parents=True, exist_ok=True)
            url = f"{SITE}/{chemin}{suffixe}"
            profondeur = "../" * (2 + sum(1 for m in morceaux if m))
            dossier.joinpath("index.html").write_text(
                page(d, profondeur.rstrip("/"), url, adresses, fiches,
                     rubrique, chemin, actives, sous, sous_dispo),
                encoding="utf-8")
            liens_site.append(url)

        for r in RUBRIQUES:
            if r["id"] and r["id"] not in actives:
                continue
            dispo = sous_actives(r, d)
            ecrire(r, None, dispo)
            for sr in dispo:
                ecrire(r, sr, dispo)

        recherche.append({
            "nom": t["nom"],
            "niveau": niveau,
            "code": code,
            "codes_postaux": t.get("codes_postaux", []),
            "population": (d["mesures"].get("POP-01") or {}).get("valeur"),
            "url": chemin,
        })

        redirections.append((f"/{niveau}/{code}", f"/{chemin}"))


    # ── contrôle d'exhaustivité de la recherche ──────────────────
    # Toute commune du référentiel doit être atteignable depuis la barre
    # de recherche. Une commune absente serait invisible sur le site.
    referentiel = RACINE / "data" / "referentiel-communes.json"
    if referentiel.exists():
        attendues = {c["code"]: c["nom"] for c in json.loads(
            referentiel.read_text(encoding="utf-8"))["communes"]}
        presentes = {r["code"] for r in recherche if r["niveau"] == "commune"}
        manquantes = sorted(set(attendues) - presentes)
        if manquantes:
            print(f"\n[BLOCAGE] {len(manquantes)} commune(s) absente(s) "
                  f"de la recherche :")
            for code in manquantes[:20]:
                print(f"  · {code}  {attendues[code]}")
            print("\n  Ces communes seraient introuvables sur le site.")
            sys.exit(1)
        print(f"  Recherche : {len(presentes)}/{len(attendues)} communes "
              f"joignables.")

    sans_cp = [r["nom"] for r in recherche
               if r["niveau"] == "commune" and not r["codes_postaux"]]
    if sans_cp:
        print(f"  [attention] {len(sans_cp)} commune(s) sans code postal : "
              f"{', '.join(sans_cp[:5])}")

    doublons_url = [r["url"] for r in recherche]
    if len(set(doublons_url)) != len(doublons_url):
        print("\n[BLOCAGE] Deux territoires produisent la même adresse.")
        sys.exit(1)

    # ── accueil et mentions légales ──
    recherche.sort(key=lambda x: (x["niveau"] != "commune", x["nom"]))

    fiche_vedette = fiches.get(ACCUEIL)
    bandeau_accueil, nav_accueil = "", ""
    if fiche_vedette:
        t = fiche_vedette["territoire"]
        chemin_vedette = adresses[ACCUEIL]
        actives_vedette = rubriques_actives(fiche_vedette)
        communes_couvertes = sum(1 for c in adresses if c[0] == "commune")
        bandeau_accueil = f"""<div class="terr"><div class="wrap">
  <div class="terr-identite">
    <div class="kind dsp">Section Territoire</div>
    <h1>{escape(TITRE_SITE)}</h1>
    <div class="sub">{communes_couvertes} communes · trois échelles ·
      données publiques</div>
  </div>
  <div class="terr-parents">
    <span class="p-ligne"><span class="p-role">Canton</span>
      <a href="{chemin_vedette}">{escape(t["nom"])}</a></span>
    <span class="p-ligne"><span class="p-role">Département</span>Isère</span>
  </div>
</div></div>"""
        nav_accueil = nav_rubriques(".", chemin_vedette, actives_vedette, None)

    (RACINE / "index.html").write_text(
        page_simple(
            "Données publiques du Sud Grésivaudan",
            "Population, logement, équipements, eau, risques et écoles pour "
            "chaque commune du Sud Grésivaudan, à partir des sources "
            "publiques françaises.",
            corps_accueil(fiches, adresses, recherche), ".", SITE + "/",
            bandeau=bandeau_accueil, navigation=nav_accueil),
        encoding="utf-8")
    liens_site.append(SITE + "/")

    if MENTIONS.get("editeur", "").strip():
        dossier = RACINE / "mentions-legales"
        dossier.mkdir(exist_ok=True)
        dossier.joinpath("index.html").write_text(
            page_simple("Mentions légales",
                        "Éditeur, hébergement, sources des données et "
                        "protection de la vie privée.",
                        corps_mentions(), "..",
                        f"{SITE}/mentions-legales/"),
            encoding="utf-8")
        liens_site.append(f"{SITE}/mentions-legales/")
    else:
        print("  [ATTENTION] Mentions légales non produites : renseignez")
        print("              MENTIONS en tête de 04_generation.py. Elles")
        print("              sont obligatoires avant toute communication.")

    # ── page d'erreur ──
    (RACINE / "404.html").write_text(
        page_simple("Page introuvable",
                    "Cette adresse ne correspond à aucune page du portail.",
                    corps_introuvable(adresses), ".",
                    f"{SITE}/404.html", indexable=False),
        encoding="utf-8")

    # ── fraîcheur des données ──
    # Publique et indexable : c'est un argument de crédibilité, pas une
    # information interne.
    fraicheur = RACINE / "fraicheur"
    fraicheur.mkdir(exist_ok=True)
    fraicheur.joinpath("index.html").write_text(
        page_simple("Fraîcheur des données",
                    "Date de la dernière collecte de chaque source du "
                    "portail, son rythme de publication et son producteur.",
                    corps_fraicheur(), "..",
                    f"{SITE}/fraicheur/"),
        encoding="utf-8")
    liens_site.append(f"{SITE}/fraicheur/")

    # ── leurre ──
    leurre = RACINE / DOSSIER_LEURRE
    leurre.mkdir(exist_ok=True)
    leurre.joinpath("index.php").write_text(
        LEURRE_PHP.replace("JOURNAL", JOURNAL_LEURRE)
                  .replace("RETENTION", str(RETENTION_JOURNAL))
                  .replace("DELAI", str(DELAI_LEURRE)),
        encoding="utf-8")
    leurre.joinpath(".htaccess").write_text(
        LEURRE_HTACCESS.replace("JOURNAL", JOURNAL_LEURRE), encoding="utf-8")
    # L'ancienne page statique doit disparaître, sans quoi elle resterait
    # servie à la place du leurre.
    ancienne = leurre / "index.html"
    if ancienne.exists():
        ancienne.unlink()

    dossier = RACINE / DOSSIER_ADMIN
    dossier.mkdir(exist_ok=True)

    # ── protection par mot de passe ──
    # Ni .htaccess ni .htpasswd ne sont écrasés : ils sont créés une
    # fois à partir de l'assistant, et le générateur ne fait que
    # constater leur présence.
    protection = dossier / ".htaccess"
    assistant = dossier / "chiffrer.php"
    if protection.exists() and (dossier / ".htpasswd").exists():
        etat_protection = "protégée par mot de passe"
        if assistant.exists():
            assistant.unlink()
            etat_protection += " — assistant supprimé"
    else:
        assistant.write_text(CHIFFRER_PHP, encoding="utf-8")
        etat_protection = ("NON PROTÉGÉE — ouvrez "
                           f"/{DOSSIER_ADMIN}/chiffrer.php")

    dossier.joinpath("journal.php").write_text(
        JOURNAL_PHP.replace("LEURRE", DOSSIER_LEURRE)
                   .replace("JOURNAL", JOURNAL_LEURRE)
                   .replace("RETENTION", str(RETENTION_JOURNAL)),
        encoding="utf-8")

    # ── consultation des documents de travail ──
    # Le dossier est créé s'il manque, mais son contenu n'est jamais
    # touché : la page ne fait que lire.
    documents = dossier / DOSSIER_DOCUMENTS
    documents.mkdir(exist_ok=True)
    dossier.joinpath("documents.php").write_text(
        DOCUMENTS_PHP.replace("DOSSIERDOCS", DOSSIER_DOCUMENTS),
        encoding="utf-8")
    # Pas de listage automatique par le serveur : la consultation passe
    # par documents.php, qui filtre les extensions.
    documents.joinpath(".htaccess").write_text(
        "# Fichier généré par 04_generation.py.\n"
        "# La consultation passe par ../documents.php.\n"
        "Options -Indexes\n", encoding="utf-8")
    dossier.joinpath("index.html").write_text(
        page_simple("Administration",
                    "Suivi interne des sources et des mises à jour.",
                    corps_administration(
                        fiches,
                        protection.exists() and (dossier / ".htpasswd").exists()),
                    "..",
                    f"{SITE}/{DOSSIER_ADMIN}/", indexable=False,
                    recherche=False, mesure=False),
        encoding="utf-8")

    # index de recherche : propre à l'affichage, distinct du contrat v1
    recherche.sort(key=lambda x: (x["niveau"] != "commune", x["nom"]))
    (ASSETS / "recherche.json").write_text(
        json.dumps(recherche, ensure_ascii=False), encoding="utf-8")

    # redirections des anciennes adresses
    # ATTENTION : la directive Redirect d'Apache opère par PRÉFIXE d'URL.
    # « Redirect /commune/38416 » capturerait aussi
    # « /commune/38416-saint-marcellin/ » et produirait une adresse absurde.
    # RedirectMatch avec une expression ancrée est le seul moyen sûr.
    lignes = "\n".join(
        f'RedirectMatch 301 "^{a}/?$" "{b}"' for a, b in sorted(redirections))

    # ── adresses de l'ancien site ──
    # L'index de Google porte encore des adresses de la version
    # précédente, en PHP, sous /rubriques/. Elles renvoient aujourd'hui
    # une erreur. Les rediriger vers leur équivalent conserve
    # l'ancienneté acquise par ces pages ; les laisser en 404 la perd.
    #
    # L'ordre compte : Apache applique la première règle qui correspond.
    # Les communes d'abord, puis le canton, puis le reste de l'ancienne
    # arborescence vers l'accueil — un dernier recours qui vaut mieux
    # qu'une erreur, mais qui ne s'applique qu'à ce dossier.
    heritage = []
    for (niveau, code), chemin in sorted(adresses.items()):
        if niveau != "commune":
            continue
        nom = fiches[(niveau, code)]["territoire"]["nom"]
        formes = "|".join(variantes_anciennes(nom))
        heritage.append(
            f'RedirectMatch 301 "^/rubriques/.*commune[_-]({formes})\\.php$"'
            f' "/{chemin}"')

    cible_canton = next((c for (n, _), c in sorted(adresses.items())
                         if n == "canton"), None)
    if cible_canton:
        heritage.append(
            'RedirectMatch 301 "^/rubriques/.*(carte[_-]communes'
            '|canton[_-][a-z_-]+)\\.php$" ' f'"/{cible_canton}"')
    heritage.append('RedirectMatch 301 "^/rubriques/.*$" "/"')

    (RACINE / ".htaccess").write_text(
        "# Fichier généré par 04_generation.py — ne pas modifier à la main.\n"
        "# Redirige les anciennes adresses sans nom vers les nouvelles.\n"
        "# RedirectMatch et non Redirect : ce dernier opère par préfixe et\n"
        "# capturerait les adresses complètes.\n"
        f"{lignes}\n"
        "\n# Page servie quand aucune adresse ne correspond. Elle répond\n"
        "# bien 404 : une redirection vers l'accueil serait une « soft\n"
        "# 404 », que les moteurs traitent comme une erreur.\n"
        "ErrorDocument 404 /404.html\n"
        "\n# Adresses de l'ancien site, encore présentes dans l'index des\n"
        "# moteurs. À confronter à la liste réelle des 404 de la Search\n"
        "# Console : ces motifs sont déduits de deux adresses observées.\n"
        + "\n".join(heritage) + "\n", encoding="utf-8")

    # plan du site
    aujourdhui = date.today().isoformat()
    entrees = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{aujourdhui}</lastmod></url>"
        for u in sorted(set(liens_site)))
    (RACINE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entrees}\n</urlset>\n", encoding="utf-8")

    # Le dossier d'administration n'est PAS mentionné ici : robots.txt
    # est public, et une ligne « Disallow » y révélerait l'adresse que
    # l'on souhaite garder discrète. La balise noindex de la page suffit
    # à écarter les moteurs qui la trouveraient.
    (RACINE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n",
        encoding="utf-8")

    produites = len(set(liens_site))
    par_rubrique = {}
    for r in RUBRIQUES:
        n = sum(1 for d in fiches.values()
                if r["id"] in rubriques_actives(d) or not r["id"])
        if n:
            par_rubrique[r["nom"]] = n
    print(f"\n  Territoires     : {len(fiches)}")
    print(f"  Pages produites : {produites}")
    print(f"  Rubriques       : "
          + ", ".join(f"{k} ({v})" for k, v in par_rubrique.items()))
    print(f"  Accueil         : index.html, contenu propre")
    print(f"  Administration  : /{DOSSIER_ADMIN}/ — {etat_protection}")
    print(f"  Documents       : /{DOSSIER_ADMIN}/documents.php — "
          f"{documents_lisibles()} document(s) lisible(s)")
    print(f"  Leurre          : /{DOSSIER_LEURRE}/ — journal des "
          f"tentatives d'accès")
    cartes = RACINE / "assets" / "cartes"
    if cartes.exists():
        fichiers = list(cartes.rglob("*.svg"))
        avec_noms = sum(1 for f in fichiers
                        if 'class="c-nom' in f.read_text(encoding="utf-8"))
        etat = "ok" if avec_noms == len(fichiers) else "RELANCEZ 05_cartes.py"
        print(f"  Cartes          : {avec_noms}/{len(fichiers)} portent "
              f"les noms de communes — {etat}")
    else:
        print("  Cartes          : absentes — lancez 05_cartes.py")
    print(f"  Thème           : assets/style.css")
    print(f"  Redirections    : .htaccess ({len(redirections)} anciennes "
          f"adresses, {len(heritage)} règles d'héritage)")
    print(f"  Page d'erreur   : 404.html, servie par ErrorDocument")
    print(f"  Plan du site    : sitemap.xml ({len(set(liens_site))} adresses)")
    print(f"\n  Exemples d'adresses :")
    for u in list(sorted(set(liens_site)))[:3]:
        print(f"    {u}")
    print()


if __name__ == "__main__":
    main()
