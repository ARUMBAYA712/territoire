# État du projet — reprise

Document de passation. À lire en premier pour reprendre le travail sans
rien redécouvrir.

**Mis à jour le 9 septembre 2026.** La version précédente datait du 8 au
matin et était devenue fausse sur une dizaine de points — versions des
scripts, nombre de pages, tâches déjà faites. Un document de reprise qui
se trompe coûte plus cher que pas de document du tout.

---

## 1. Ce qu'est le projet

**Sud Grésiv'** — portail de données publiques territoriales, en ligne sur
`territoire.sudgresiv.com`. Il couvre les 44 communes du canton du Sud
Grésivaudan et les 47 de l'intercommunalité, à trois échelles : commune,
canton, intercommunalité.

Ce portail est **une partie du site sudgresiv.com**, à regrouper avec le
reste plus tard. Rien ne doit supposer qu'il occupe seul le domaine.

**775 pages produites**, dont 726 au plan du site — les 49 qui manquent
sont les pages « Résultats électoraux », encore en annonce. Dix rubriques,
dont deux à sous-rubriques.

---

## 2. Documents à lire, dans cet ordre

| Document | Contenu |
|---|---|
| `CAHIER-DES-CHARGES.md` | **Le plus important.** Exigences numérotées, et la section des arbitrages rendus avec leur motif. Ne pas les rouvrir sans élément nouveau. |
| `EXECUTION.md` | Ordre de lancement, durées mesurées, rythmes |
| `FEUILLE-DE-ROUTE.md` | Ce qui vient ensuite, par difficulté |
| `LIVRAISON-TRANSPORTS.md` | La dernière livraison : train, autocar, licences |
| `LIVRAISON-CARBURANTS.md` | La rubrique Carburants et la version 35 |
| `ELECTIONS-FAISABILITE.md` | Source instruite, technique de lecture partielle mesurée |
| `TRANSPORTS-FAISABILITE.md` | Sources transport, et le point de licence |
| `HISTORIQUES-FAISABILITE.md` | Les chroniques : formes, seuils, sources |
| `AUDIT.md`, `TESTS.md` | Audit de septembre, fiche de contrôle |

---

## 3. Architecture en cinq phrases

Des collecteurs Python produisent des fichiers `data/mesures-*.json`.
`03_agregation.py` les fusionne et publie `data/publie/v1/**`, contrat
stable destiné aussi à des sites tiers. `05_cartes.py` produit les SVG.
`04_generation.py` écrit les pages HTML statiques. Aucun serveur applicatif,
aucune bibliothèque tierce, aucune chaîne de construction.

Le déploiement se fait par webhook GitHub vers un hébergement OVH mutualisé,
où **PHP est disponible mais pas Python** — d'où le choix de GitHub Actions
pour l'automatisation.

---

## 4. Les scripts et leurs versions

Chaque script porte un `VERSION_SCRIPT` affiché à l'exécution. `lancer.py`
compare avec ses `VERSIONS_ATTENDUES` et refuse de partir si un fichier n'a
pas été remplacé. **Ce mécanisme existe parce que trois allers-retours ont
été perdus sur des fichiers oubliés.**

| Script | Version | Rôle |
|---|---|---|
| `01_referentiel.py` | 1 | Communes, depuis geo.api.gouv.fr |
| `02_canton.py` | 2 | Rattachement cantonal, décret n° 2014-180 |
| `03_agregation.py` | **5** | Agrégation, publication, sommes de chroniques |
| `04_generation.py` | **37** | Pages, thème, cartes, graphiques, licences |
| `05_cartes.py` | 3 | SVG en projection Web Mercator |
| `06_eau.py` | 4 | Eau potable, Hub'Eau |
| `07_vigieau.py` | 4 | Restrictions sécheresse |
| `08_georisques.py` | **11** | Risques, catastrophes naturelles, décennies |
| `09_nappes.py` | **3** | Nappes, chronique mensuelle |
| `10_ecoles.py` | 5 | Établissements scolaires |
| `11_population.py` | 5 | Population, logement, équipements |
| `12_rivieres.py` | **6** | Débits, chronique mensuelle, par station |
| `13_hivernal.py` | 2 | Équipements hivernaux — **saisi à la main** |
| `14_vigilance.py` | 2 | Vigilance météo — **clé requise, inerte** |
| `15_elus.py` | 2 | Élus locaux |
| `16_bio.py` | **4** | Agriculture biologique, 18 millésimes |
| `17_climat.py` | **1** | Climat mensuel Météo-France |
| `18_carburants.py` | **4** | Prix des carburants et enseignes |
| `19_gares.py` | **1** | Gares et fréquentation ferroviaire |
| `20_cars.py` | **1** | Desserte en autocar, GTFS |

Ordre d'exécution : collecteurs `06` à `20`, puis `03`, puis `05`, puis `04`.
La numérotation n'est pas l'ordre. `lancer.py` s'en charge.

**Durée d'une séquence complète : de 7 à 16 minutes**, selon l'humeur de
Hub'Eau, qui répond en 503 par vagues. `06_eau.py` a été mesuré à
1 min 34 s un jour et 10 min 36 s le lendemain, sans rien changer chez
nous.

---

## 5. Les principes qui ont structuré tout le reste

**Ne jamais confondre absence de donnée et échec technique.** Une réponse
vide d'API vaut « pas de donnée » ; une erreur vaut « non obtenue ».

**Une donnée sans repère ne vaut rien.** Chacune porte une échelle de
lecture ou une comparaison. C'est ce travail, plus que la collecte, qui
prend du temps.

**Bloquer plutôt que publier faux.** Un contrôle en défaut arrête le
traitement sans rien écrire. Mais une configuration simplement absente
n'est pas une défaillance : le collecteur le signale et rend la main.

**Retirer plutôt que laisser vieillir.** Un référentiel expiré, un prix de
plus de huit jours : le collecteur publie un fichier vide plutôt que de
laisser en place la collecte précédente.

**Ce qui n'est pas affiché n'est pas vérifié.** Plusieurs défauts graves
sont restés invisibles faute d'être montrés à l'exécution. D'où les
récapitulatifs de fin de script, et la règle : la sortie du script **est**
la surface de contrôle. Un récapitulatif qui noie cinq lignes utiles sous
quatre-vingt-huit inutiles ne remplit pas ce rôle.

**Chaque collecteur déclare où sa donnée s'affiche** — `rubrique`,
`sous_rubrique`, `rang`, et depuis septembre `licence`. Le générateur ne
devine rien.

**Ne pas inventer un critère qu'on n'a pas vérifié.** Quand la donnée
manque pour trancher, le script inventorie et le dit, plutôt que de
supposer. C'est le mode `--inventaire` de `20_cars.py` et le
`--modele-enseignes` de `18_carburants.py`.

---

## 6. Erreurs déjà commises — ne pas les refaire

| Erreur | Leçon |
|---|---|
| `Redirect` Apache au lieu de `RedirectMatch` | Opère par préfixe ; toutes les fiches étaient cassées en production |
| Noms de champs d'API devinés | Toujours prévoir un mode d'inspection et demander la sortie réelle |
| Millésimes INSEE mélangés | Un fichier peut porter plusieurs années côte à côte |
| Dates Géorisques en `JJ/MM/AAAA` lues comme de l'ISO | **Silencieux depuis le début** : bandeau « catastrophe reconnue » mort, tri faux. Toujours accepter les deux écritures |
| Valeurs anciennes dix fois trop faibles (la Bourne) | Des données vraies peuvent raconter une histoire fausse : borner le plausible, et **dire** ce qu'on écarte |
| `in_bbox` avec la longitude d'abord | L'API répond `200` et zéro ligne. Une requête qui réussit n'est pas une requête juste |
| Banc d'essai rejouant une collecte enregistrée | Il ne teste pas la collecte elle-même. Les filtres étaient éprouvés, la requête ne l'avait jamais été |
| Rayon unique autour d'un territoire en bande | Le rectangle attrape deux agglomérations voisines. Décider **page par page**, pas par un rayon global |
| Titre de chronique nommant un objet unique | Il devient faux à l'agrégation. D'où `titre_agrege` |
| Nœud voisin pris pour la bonne station | Sans seuil de distance, une enseigne à 700 m se serait affichée sur une autre station. **Mieux vaut rien qu'un faux** |
| Repère d'une commune repris à l'agrégation | Un repère décrit son territoire |
| SVG sans attributs de dimension | S'affiche en 300 × 150 |
| Chemin d'administration dans `robots.txt` | Ce fichier est public |
| Codes INSEE inventés dans un modèle | Désigner les communes par leur nom |
| `.gitignore` nommant les caches un par un | L'arrivée de `17_climat.py` a créé 27 Mo qu'aucune règle ne couvrait. Écrire `data/cache-*` |

**Une leçon revient trois fois** : le défaut était une **sélection**
incomplète — quel fichier, quelle station, quel poste — jamais le calcul.

---

## 7. Méthode de travail établie

L'utilisateur exécute les scripts sur sa machine et renvoie la sortie
réelle. Les corrections se font sur cette base, jamais sur supposition.

Chaque livraison comprend : les fichiers modifiés, le plan mis à jour dans
`lancer.py`, et une note de livraison récapitulant ce qu'il faut installer
et vérifier. **Tout document produit est aussi déposé dans
`Terri_Admin/Documents/`.**

Rédaction en français, code et commentaires compris. Ton direct, sans
emphase. Les réserves et les limites sont dites, pas tues.

---

## 8. État des sources

**En place et vérifiées sur données réelles** : référentiel, canton, eau
potable, sécheresse, risques, nappes, rivières, écoles, population,
logement, équipements, élus, agriculture biologique, climat, carburants,
gares.

Quelques chiffres de référence, relevés les 8 et 9 septembre 2026 :

| | |
|---|---|
| Bio du canton | 390 ha en 2008 → **2 769 ha** en 2025 ; 27 → 151 exploitations |
| Climat, poste de Chatte | normale 1991-2020 **12,0 °C**, 2025 **13,5 °C**, 48 jours à 30 °C |
| Nappe retenue | Fontchaude `07953X0104/P`, 2007-2026 |
| Débit retenu | La Vernaisson `W333521201`, **727 mois** 1965-2026 |
| Carburants | 5 stations sur le territoire, gazole le moins cher 2,256 €/L |
| Gares | 4 gares, **684 019 → 960 098 voyageurs** de 2015 à 2024 |

**Le collecteur autocars est le moins éprouvé du lot.** Il a été validé sur
une archive GTFS fabriquée pour l'essai — géométrie, calendrier,
exceptions, comptages — mais jamais sur l'archive réelle de 30 Mo.
Attendre un ou deux ajustements à la première collecte.

**Livrées, en attente d'une configuration**

| Source | Ce qui manque |
|---|---|
| Vigilance météo | La clé Météo-France. Le collecteur s'arrête proprement sans elle. |
| Autocars | La sortie de `python 20_cars.py --inventaire`, pour distinguer le scolaire du régulier. Sans elle, la desserte publiée est la desserte totale, et la note de la page le dit. |
| Enseignes des stations | Deux stations qu'OpenStreetMap ne sait pas nommer : `38160007` Saint-Marcellin et `38160003` Saint-Sauveur. `python 18_carburants.py --modele-enseignes` crée le fichier. |

**L'arrêté « loi Montagne » est saisi et complet** depuis le 8 septembre :
9 communes, dont 3 partiellement. **Il court jusqu'au 31 octobre 2027** —
l'arrêté du 12 janvier 2026 abroge celui de 2023 et ne porte pas de date
de fin.

**En attente d'une source**

| Sujet | Obstacle |
|---|---|
| Espaces et espèces protégés | Serveurs du Muséum hors service après une attaque |
| Prix de l'eau, assainissement | API Hub'Eau arrêtée ; passer par les fichiers SISPEA |
| Cultures et élevage | Agreste, secret statistique fréquent |
| Fioul domestique par revendeur | **N'existe pas** : l'arrêté de 2006 ne couvre que les carburants routiers ≥ 500 m³. Seule une série nationale hebdomadaire depuis 1985 existe. Écarté le 8 septembre. |
| Chasse, cueillette | Arrêtés préfectoraux, saisie manuelle, forte responsabilité |

---

## 9. Ce qu'il reste à faire, par priorité

**Bloquant avant communication publique**

1. ~~Renseigner `MENTIONS`~~ — fait.
2. ~~Protéger `/Terri_Admin/`~~ — fait.
3. ~~Retirer `administration/index.html` du dépôt~~ — **sans objet** :
   ce fichier n'existe pas. Le fichier réel est `administration/index.php`,
   et il doit rester. Vérifié dans l'index Git le 9 septembre : ni cache,
   ni clé, ni archive n'y figurent.
4. **Pousser sur GitHub**, laisser le webhook déployer.
5. **Déclarer `sitemap.xml` en Search Console et Bing.** Rien ne
   s'indexe avant ce geste, et les 726 adresses portent maintenant toutes
   du contenu réel.

**Mise en route**

6. `python 20_cars.py --inventaire`, puis régler `MOTIFS_SCOLAIRES`
7. `python 18_carburants.py --modele-enseignes`, compléter les deux
   stations
8. Clé sur `portail-api.meteofrance.fr`, puis `14_vigilance.py --modele`
9. **Automatisation par GitHub Actions.** À traiter maintenant : les prix
   des carburants se périment en huit jours, et la rubrique se vide
   d'elle-même si la collecte cesse. Python n'étant pas disponible sur
   l'hébergement mutualisé, le CRON OVH est exclu.

**Ensuite**

10. **Élections** — municipales 2026 d'abord, puis remonter à 2017.
    Source instruite, technique de lecture partielle mesurée :
    1,2 Mo au lieu de 75. Voir `ELECTIONS-FAISABILITE.md`.
11. Image de partage 1200 × 630, à faire à la main
12. Textes explicatifs générés à partir des valeurs réelles ; polices
    servies depuis le site plutôt que par Google Fonts
13. Cinq noms de communes encore non placés sur la carte du canton
14. Regroupement avec sudgresiv.com

---

## 10. Points de vigilance permanents

**Les licences ne sont plus uniformes.** Depuis le 9 septembre, le site
mêle Licence Ouverte 2.0 et ODbL — cette dernière pour les données de
transport et les enseignes issues d'OpenStreetMap. L'ODbL impose le
**partage à l'identique** des bases dérivées, et le site publie ses fiches
en téléchargement. Le générateur affiche donc les licences source par
source, à partir de ce que les collecteurs déclarent. **Ne jamais
réintroduire une licence écrite en dur dans une page.**

**Le `.gitignore`** couvre désormais `data/cache-*` de façon générique,
plus l'archive INSEE de 198 Mo et la clé Météo-France. Le `.htpasswd` doit
au contraire **rester** dans le dépôt, qui doit donc rester privé.
`data/contours.json` y figure comme ignoré mais reste suivi depuis un
commit antérieur : à trancher.

**GitHub désactive les tâches planifiées** après soixante jours sans
activité humaine sur le dépôt, sans le signaler.

**Le `.htaccess` de la racine est régénéré** à chaque exécution : toute
règle ajoutée à la main serait écrasée.

**Les données personnelles** : le répertoire des élus contient dates de
naissance et professions, délibérément non republiées.

**La rubrique Élections demandera une vigilance de ton.** Les nuances
politiques sont des étiquettes préfectorales, parfois contestées par les
intéressés. Les publier en citant leur origine reste dans le rôle d'un
portail de données ; en tirer une lecture en sortirait. C'est la seule
rubrique dont les textes générés méritent une relecture avant mise en
ligne.

**Le dossier `Terri_Admin/Documents/`** est protégé par mot de passe mais
servi par le web : aucun secret ne doit y être déposé.
