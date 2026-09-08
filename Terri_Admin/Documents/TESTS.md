# Fiche de contrôle après installation

À dérouler après chaque livraison. Les contrôles A se lisent au terminal,
les autres à l'écran.

Séquence : `python lancer.py`. Le lanceur refuse de partir si un script n'a
pas été remplacé.

---

## A — Au terminal

| # | Attendu |
|---|---|
| A1 | Aucun message « fichiers non remplacés » au démarrage |
| A2 | Chaque script annonce sa version sous son titre |
| A3 | `01_referentiel.py` : 47 communes, population 45 296 |
| A4 | `02_canton.py` : 44 / 44 communes retrouvées, source du décret affichée |
| A5 | `06_eau.py` : 47/47 communes renseignées |
| A6 | `08_georisques.py` : récapitulatif des risques reconnus — des libellés lisibles, pas des listes d'objets |
| A7 | `10_ecoles.py` : 47/47, et « les effectifs ne sont pas publiés par cette source » |
| A8 | `11_population.py` : millésime 2022, 47/47, dictionnaire des variables chargé |
| A9 | `12_rivieres.py` : au moins trois sites exploitables |
| A10 | `13_hivernal.py` : aucune commune « hors du périmètre » |
| A11 | `15_elus.py` : maires retrouvés, communes renseignées, effectif cohérent |
| A12 | `16_bio.py` : millésime affiché, surfaces cumulées plausibles |
| A13 | `03_agregation.py` : un « Complément repris » par collecteur ayant produit |
| A14 | `05_cartes.py` : noms placés sur le canton, poids moyen sous 30 Ko |
| A15 | `04_generation.py` : 47/47 communes joignables, cartes 49/49 avec noms |
| A16 | Aucun script ne s'arrête sur `[BLOCAGE]` |
| A17 | Un collecteur non configuré rend la main sans interrompre la chaîne |

---

## B — Contenu des fiches

| # | Page | Attendu |
|---|---|---|
| B1 | Commune, Aperçu | Six tuiles, dont le maire, avec renvoi vers les élus |
| B2 | Commune, Aperçu | Bandeau sécheresse en tête, pleine largeur, coloré selon la gravité |
| B3 | Canton, Aperçu | Quatre tuiles ; les conseillers départementaux remplacent le maire |
| B4 | Toute page | « Rattachements » sous les bandeaux, avant les tuiles |
| B5 | Toute page | Aucun renvoi « Voir le détail » ne mène dans le vide |
| B6 | Environnement | Sous-rubriques : Eau potable, Sécheresse, Nappes, Rivières, Vigilance, Agriculture, Risques |
| B7 | Canton, Environnement | Nappes et Rivières présentes ; Eau potable absente |
| B8 | Population | Somme des parts des sept tranches d'âge égale à 100 % |
| B9 | Urbanisme | Chiffres du logement issus du recensement 2022, non de 2006 |
| B10 | Équipements | Détail par type avec libellés lisibles, non des codes |
| B11 | Élections / Élus | Conseil municipal dans l'ordre protocolaire |
| B12 | Élections / Élus | Aucune date de naissance, aucune profession |
| B13 | Environnement / Agriculture | Réserve sur le siège d'exploitation présente |
| B14 | Environnement / Risques | Libellés de risques lisibles, déclinaisons présentées à part |

---

## C — Agrégation

| # | Attendu |
|---|---|
| C1 | Aucune tuile agrégée ne porte de repère d'une commune |
| C2 | Les unités agrégées sont au pluriel |
| C3 | Aucune tuile agrégée ne propose « Voir le détail » |
| C4 | Densité du canton recalculée sur les totaux, non moyennée |

---

## D — Cartes

| # | Attendu |
|---|---|
| D1 | Les noms de communes s'affichent, sans chevauchement |
| D2 | Le nom de la commune courante est en couleur d'accent |
| D3 | Bascule Plan IGN : les limites communales restent nettement visibles |
| D4 | Les contours coïncident avec les routes du fond de plan |
| D5 | Aucune tuile chargée tant que « Schéma » est actif |
| D6 | Éducation : les établissements apparaissent en points, avec nom et type au survol |
| D7 | Case « Noms des communes » : les noms disparaissent, la carte reste cliquable |

---

## E — Icônes et mise en page

| # | Attendu |
|---|---|
| E1 | Les icônes font environ un quart de plus que le texte, jamais davantage |
| E2 | Chaque entrée de menu, tuile et bandeau de section porte un pictogramme |
| E3 | Sur un bandeau d'alerte, l'icône prend la couleur de l'état |
| E4 | Accueil : mêmes bandeaux que les fiches, chiffres clés en trois cellules |
| E5 | Écrans étroits — canton et intercommunalité passent sous le titre |
| E6 | Écrans étroits — les deux barres de navigation défilent sans casser |

---

## F — Administration et sécurité

| # | Attendu |
|---|---|
| F1 | `/Terri_Admin/` demande un mot de passe |
| F2 | `chiffrer.php` a disparu une fois la protection en place |
| F3 | `/administration/` présente la fausse page de connexion, avec attente |
| F4 | `/Terri_Admin/journal.php` liste les tentatives, adresses tronquées |
| F5 | `robots.txt` ne mentionne aucun de ces deux chemins |
| F6 | `sitemap.xml` ne contient ni l'un ni l'autre |
| F7 | La page d'administration signale les référentiels saisis et leur échéance |
| F8 | Les mentions légales existent et identifient l'éditeur |

---

## G — Dépôt

| # | Attendu |
|---|---|
| G1 | `git status` ne propose pas `data/dossier-complet.zip` |
| G2 | `data/mesures-*.json` et `data/publie/` sont bien suivis |
| G3 | `Terri_Admin/.htpasswd` est présent — sans lui, pas de protection |
| G4 | `Terri_Admin/chiffrer.php` est absent |
| G5 | `administration/index.html` a été supprimé du dépôt |
| G6 | `data/cle-meteofrance.json` n'est pas suivi |

---

## H — À rapporter en cas d'écart

Pour chaque anomalie, la **sortie du terminal** vaut mieux qu'une
description : c'est elle qui a permis de trouver la quasi-totalité des
défauts corrigés jusqu'ici.

Pour un défaut d'affichage, une capture d'écran et l'adresse de la page.
