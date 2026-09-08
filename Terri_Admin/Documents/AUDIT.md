# Rapport d'audit — portail territorial

Deux campagnes. La première, en septembre, portait sur le code alors publié.
La seconde recense les défauts découverts ensuite, à l'usage — presque tous
révélés par une sortie d'exécution plutôt que par une relecture.

---

## Première campagne — audit du code

Portée : neuf scripts, environ 4 800 lignes. Analyse statique, relecture
ciblée, rejeu des pages produites dans un navigateur simulé.

### A-01 · Les redirections cassaient toutes les fiches — critique

`04_generation.py` produisait un `.htaccess` contenant :

```
Redirect 301 /commune/38416 /commune/38416-saint-marcellin/
```

La directive `Redirect` d'Apache opère par **préfixe d'URL**. La règle
capturait donc aussi `/commune/38416-saint-marcellin/`, réécrite en
`/commune/38416-saint-marcellin/-saint-marcellin/`. Toutes les fiches
étaient inutilisables en production.

Corrigé par `RedirectMatch` avec expression ancrée.

### A-02 à A-05 · Sécurité

Valeurs textuelles insérées sans échappement ; aucun contrôle du schéma des
liens externes, où un `javascript:` serait passé ; JSON embarqué pouvant
clore la balise `script` ; codes de territoire employés comme chemins de
fichiers sans contrôle.

Portée réelle faible — sources publiques d'administrations, aucune donnée
personnelle — mais autant fermer ces portes avant que la liste des sources
ne s'allonge.

### A-06 · Dépassement de pile sur les contours découpés

La simplification des tracés était récursive. Sur un contour de plusieurs
milliers de points, fréquent en montagne, la profondeur d'appels pouvait
interrompre le script. Version itérative, vérifiée sur 12 000 points.

### A-07 · Le classement des nappes dépendait de l'API

Toute la lecture suppose la mesure la plus récente en tête. Le tri était
demandé à Hub'Eau, jamais vérifié localement. Tri local systématique.

### A-08 · Une collecte partielle passait pour complète

Dans Géorisques, l'échec d'un point d'entrée se traduisait par une absence
silencieuse, indiscernable d'une vraie absence de donnée. Les points en
échec sont désormais listés à l'exécution.

### A-09 · Contenu dupliqué entre l'accueil et le canton

Deux adresses servaient le même contenu, toutes deux déclarées canoniques.
L'accueil a depuis reçu un contenu propre.

---

## Seconde campagne — défauts découverts à l'usage

Tous sauf un ont été révélés par une **sortie d'exécution**, non par une
relecture. C'est l'enseignement principal de cette campagne.

| # | Défaut | Ce qu'il produisait | Révélé par |
|---|---|---|---|
| B-01 | Millésimes INSEE mélangés | Les chiffres de logement publiés étaient ceux de 2006 | `--colonnes` |
| B-02 | Tranches d'âge imbriquées additionnées | Une même personne comptée plusieurs fois | `--colonnes` |
| B-03 | Risques imbriqués lus à plat | Une liste d'objets affichée telle quelle, ou le nom de la commune | Récapitulatif de fin de script |
| B-04 | Déclinaisons comptées comme des risques | Jusqu'à 14 risques là où il y en a 4 | Récapitulatif |
| B-05 | Repère d'une commune repris à l'agrégation | « 54 établissements, sur 1 établissement » | Signalé par l'utilisateur |
| B-06 | Forme singulière héritée à l'agrégation | « 54 établissement » | Même signalement |
| B-07 | SVG sans attributs de dimension | Icônes affichées en 300 × 150 pixels | Capture d'écran |
| B-08 | Liste Python insérée sans assemblage | Crochets et guillemets affichés sur l'accueil | Signalé, puis page récupérée |
| B-09 | Effectifs d'élèves absents de la source | Zéro partout, sans explication | `--inspecter` |
| B-10 | Colonne de date prise pour un libellé de fonction | Fonction des maires illisible | `--colonnes` |
| B-11 | Codes INSEE inventés dans un modèle | Trois communes hors périmètre, aucune retenue | Exécution |
| B-12 | Configuration absente traitée comme une panne | La chaîne s'arrêtait à l'étape 2 | Exécution |
| B-13 | Chemin d'administration inscrit au `robots.txt` | L'adresse à garder discrète était publiée | Relecture |
| B-14 | Fichier écrasé par une version antérieure | Deux modifications perdues | Contrôle de version |

### Ce que ces défauts ont en commun

**Aucun ne produisait d'erreur.** Les scripts se terminaient normalement,
les pages se généraient, et l'information affichée était fausse ou absente.

Trois mécanismes ont été introduits en réponse, et ils ont chacun révélé au
moins un défaut par la suite :

- **les récapitulatifs de fin de script** — libellés reconnus, communes
  renseignées, colonnes trouvées ;
- **les modes `--inspecter` et `--colonnes`**, à lancer avant toute collecte
  sur une source nouvelle ;
- **le numéro de version affiché par chaque script**, comparé par le
  lanceur, qui refuse de partir si un fichier n'a pas été remplacé.

### La règle qui s'en dégage

**Ce qui n'est pas affiché n'est pas vérifié.** Un traitement silencieux qui
réussit n'apporte aucune garantie. Chaque script doit montrer ce qu'il a
compris de ses données, pas seulement ce qu'il a écrit.

---

## Points examinés et jugés sains

| Sujet | Constat |
|---|---|
| Données personnelles | Aucune en consultation ordinaire. Élus : nom, fonction et date de mandat seulement |
| Dépendances externes | Aucune bibliothèque tierce ; polices Google et tuiles IGN, signalées aux mentions légales |
| Contrôles bloquants | Efficaces à chaque étape ; aucun script ne publie de données incohérentes |
| Reprise après incident | Sauvegarde au fil de l'eau, reprise par élément, versionnement des collectes |
| Attribution des sources | Licence et producteur portés par chaque mesure et affichés |
| Liens internes | Aucun lien mort ; les renvois sont validés contre les blocs réellement présents |
| Dégradation sans JavaScript | Contenu, chiffres et liens restent accessibles |

---

## Améliorations proposées, non traitées

| # | Sujet | Intérêt |
|---|---|---|
| C-01 | Page publique de fraîcheur des données | Fort — argument de crédibilité |
| C-02 | Héberger les polices plutôt que les appeler chez Google | Moyen — un appel externe par page |
| C-03 | Données structurées pour les moteurs de recherche | Moyen |
| C-04 | Fichier de configuration commun aux scripts | Moyen — le domaine et le périmètre sont répétés |
| C-05 | Tests automatiques sur les fonctions de calcul | Moyen — quantiles, agrégations, appréciations saisonnières |
| C-06 | Vérifier le rendu sans `:has()` sur navigateurs anciens | Faible |
