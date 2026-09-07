# État du projet — reprise

Document de passation. À lire en premier pour reprendre le travail sans
rien redécouvrir.

---

## 1. Ce qu'est le projet

**Sud Grésiv'** — portail de données publiques territoriales, en ligne sur
`territoire.sudgresiv.com`. Il couvre les 44 communes du canton du Sud
Grésivaudan et les 47 de l'intercommunalité, à trois échelles : commune,
canton, intercommunalité.

Ce portail est **une partie du site sudgresiv.com**, à regrouper avec le
reste après les carburants et les élections. Rien ne doit supposer qu'il
occupe seul le domaine.

Environ 480 pages produites, sept rubriques ouvertes.

---

## 2. Documents à lire, dans cet ordre

| Document | Contenu |
|---|---|
| `CAHIER-DES-CHARGES.md` | **Le plus important.** Exigences numérotées, et surtout la section 7 : dix-huit arbitrages déjà rendus avec leur motif. Ne pas les rouvrir sans élément nouveau. |
| `LIVRAISON.md` | Ce qui reste à installer, et les points en suspens |
| `EXECUTION.md` | Ordre de lancement, durées mesurées, rythmes |
| `FEUILLE-DE-ROUTE.md` | Ce qui vient ensuite, par difficulté |
| `AUTOMATISATION.md` | Mode d'emploi GitHub Actions, prêt à appliquer |
| `AUDIT.md` | Audit de septembre, défauts corrigés |
| `TESTS.md` | Fiche de contrôle après installation |

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
| `03_agregation.py` | 3 | Agrégation et publication |
| `04_generation.py` | 22 | Pages, thème, cartes, administration |
| `05_cartes.py` | 3 | SVG en projection Web Mercator |
| `06_eau.py` | 4 | Eau potable, Hub'Eau |
| `07_vigieau.py` | 4 | Restrictions sécheresse |
| `08_georisques.py` | 10 | Risques et catastrophes naturelles |
| `09_nappes.py` | 2 | Niveau des nappes |
| `10_ecoles.py` | 5 | Établissements scolaires |
| `11_population.py` | 5 | Population, logement, équipements |
| `12_rivieres.py` | 5 | Débit des cours d'eau |
| `13_hivernal.py` | 2 | Équipements hivernaux — **saisi à la main** |
| `14_vigilance.py` | 2 | Vigilance météo — **clé requise** |
| `15_elus.py` | 2 | Élus locaux |
| `16_bio.py` | 1 | Agriculture biologique |

Ordre d'exécution : collecteurs `06` à `16`, puis `03`, puis `05`, puis `04`.
La numérotation n'est pas l'ordre. `lancer.py` s'en charge.

---

## 5. Les principes qui ont structuré tout le reste

Ils sont dans le cahier des charges, mais voici ceux qui reviennent le plus
souvent dans les décisions.

**Ne jamais confondre absence de donnée et échec technique.** Une réponse
vide d'API vaut « pas de donnée » ; une erreur vaut « non obtenue ». Les
deux s'affichent différemment.

**Une donnée sans repère ne vaut rien.** Une profondeur de nappe, un débit,
une dureté de l'eau : chacun porte une échelle de lecture ou une
comparaison saisonnière. C'est ce travail, plus que la collecte, qui prend
du temps.

**Bloquer plutôt que publier faux.** Un contrôle en défaut arrête le
traitement sans rien écrire. Mais une configuration simplement absente
n'est pas une défaillance : le collecteur le signale et rend la main, sans
interrompre les suivants.

**Retirer plutôt que laisser vieillir.** Quand un référentiel saisi à la
main expire, le collecteur publie un fichier vide : l'information disparaît
du site au lieu d'y rester périmée.

**Chaque collecteur déclare où sa donnée s'affiche** — `rubrique`,
`sous_rubrique`, `rang`. Le générateur ne devine rien, et les icônes s'en
déduisent automatiquement.

**Ce qui compte le plus vient en premier.** Historique : du plus récent au
plus ancien. État en cours : du plus grave au moins grave.

**Ce qui n'est pas affiché n'est pas vérifié.** Plusieurs défauts graves
sont restés invisibles faute d'être montrés à l'exécution : millésimes
mélangés, libellés illisibles, effectifs à zéro. D'où les récapitulatifs de
fin de script.

---

## 6. Erreurs déjà commises — ne pas les refaire

| Erreur | Leçon |
|---|---|
| `Redirect` Apache au lieu de `RedirectMatch` | La directive opère par préfixe ; toutes les fiches étaient cassées en production |
| Noms de champs d'API devinés | Toujours prévoir un mode `--inspecter` et demander la sortie réelle |
| Millésimes INSEE mélangés | Un fichier peut porter plusieurs années côte à côte : retenir la plus récente |
| Tranches d'âge imbriquées additionnées | Vérifier que la somme des parts fait 100 % |
| Repère d'une commune repris à l'agrégation | Un repère décrit son territoire, il ne s'agrège pas |
| SVG sans attributs de dimension | Un SVG sans `width` s'affiche en 300 × 150 |
| Chemin d'administration dans `robots.txt` | Ce fichier est public : y inscrire un chemin le révèle |
| Fichier écrasé par une version antérieure | Toujours vérifier la version après une copie |
| Codes INSEE inventés dans un modèle | Désigner les communes par leur nom et les rapprocher du référentiel |
| Configuration absente traitée comme une panne | Un collecteur non configuré rend la main sans interrompre la chaîne ; seule une vraie défaillance justifie un code de sortie non nul |

---

## 7. Méthode de travail établie

L'utilisateur exécute les scripts sur sa machine et renvoie la sortie
réelle. Les corrections se font sur cette base, jamais sur supposition.

Chaque livraison comprend : les fichiers modifiés, le plan mis à jour dans
`lancer.py`, et `LIVRAISON.md` récapitulant ce qu'il faut installer et
vérifier.

Avant toute collecte complète sur une source nouvelle, faire lancer un mode
`--inspecter` ou `--colonnes`. Cela a évité de nombreux allers-retours.

Rédaction en français, code et commentaires compris. Ton direct, sans
emphase. Les réserves et les limites sont dites, pas tues.

---

## 8. État des sources

**En place et vérifiées** : référentiel, canton, eau potable, sécheresse,
risques, nappes, rivières, écoles, population, logement, équipements.

**Livrées, non encore éprouvées en conditions réelles** : équipements
hivernaux, vigilance météo, élus, agriculture biologique.

**En attente d'une source** :

| Sujet | Obstacle |
|---|---|
| Espaces et espèces protégés | Serveurs du Muséum hors service après une attaque informatique |
| Prix de l'eau, assainissement | API Hub'Eau arrêtée ; passer par les fichiers SISPEA |
| Cultures et élevage | Agreste ou registre parcellaire, secret statistique fréquent |
| Chasse, cueillette | Arrêtés préfectoraux, saisie manuelle, forte responsabilité |

---

## 9. Ce qu'il reste à faire, par priorité

**Bloquant avant communication publique**

1. Renseigner `MENTIONS` en tête de `04_generation.py` — identification de
   l'éditeur, obligation légale
2. Protéger `/Terri_Admin/` par mot de passe : ouvrir `chiffrer.php`, suivre
   les trois étapes, supprimer l'assistant
3. Supprimer `administration/index.html` du dépôt, sinon l'ancienne page est
   servie à la place du leurre

**Mise en route des nouveaux collecteurs**

4. `python 13_hivernal.py --modele`, compléter depuis l'arrêté préfectoral
   du 12 janvier 2026, passer `saisie_complete` à `true`
5. Demander une clé sur `portail-api.meteofrance.fr`, puis
   `python 14_vigilance.py --modele` et `--inspecter`
6. `python 15_elus.py --colonnes` et `python 16_bio.py --colonnes` avant la
   première collecte

**Ensuite**

7. Automatisation par GitHub Actions — `AUTOMATISATION.md` est prêt
8. Carburants — cahier des charges de l'application Carbu disponible, la
   plupart des arbitrages sont déjà rendus
9. Élections — historique puis direct le soir des scrutins, avec embargo
   légal jusqu'à 20 heures
10. Regroupement avec sudgresiv.com

---

## 10. Points de vigilance permanents

**Le `.gitignore`** exclut l'archive INSEE de 198 Mo, les caches et la clé
Météo-France. Le `.htpasswd` doit au contraire **rester** dans le dépôt,
qui doit donc rester privé.

**GitHub désactive les tâches planifiées** après soixante jours sans
activité humaine sur le dépôt, sans le signaler.

**Le `.htaccess` de la racine est régénéré** à chaque exécution : toute
règle ajoutée à la main serait écrasée. Point à traiter au moment du
regroupement avec le site principal.

**Les données personnelles** : le répertoire des élus contient dates de
naissance et professions, délibérément non republiées. Deux réglages en
tête de `15_elus.py` permettent de revenir sur ce choix — le laisser tel
quel sauf motif clair.

**Le leurre** `/administration/` journalise les tentatives d'accès avec une
adresse tronquée d'un segment, conservation 90 jours. Les mentions légales
en font état.
