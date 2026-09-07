# Livraison en attente d'installation

Établie d'après votre dernière exécution, celle qui affichait
`12_rivieres.py version 5` et `04_generation.py version 7`.

---

## Fichiers à envoyer — sept en tout

| Fichier | Version | Nature |
|---|---|---|
| `04_generation.py` | 7 → **22** | Modifié en profondeur |
| `13_hivernal.py` | **nouveau**, version 2 | Équipements hivernaux |
| `14_vigilance.py` | **nouveau**, version 2 | Vigilance météorologique |
| `15_elus.py` | **nouveau**, version 2 | Élus locaux |
| `16_bio.py` | **nouveau** | Agriculture biologique |
| `lancer.py` | mis à jour | Contrôle des versions, nouveau plan |
| `.gitignore` | mis à jour | Clé Météo-France exclue |

Les autres scripts — `01`, `02`, `03`, `05` à `12` — sont déjà à jour chez
vous. Le lanceur le vérifiera et refusera de partir si l'un manque.

**Documents** : `AUTOMATISATION.md` est nouveau. `FEUILLE-DE-ROUTE.md` et
`CAHIER-DES-CHARGES.md` ont été enrichis.

---

## Mise en route — trois commandes, une seule fois

### Équipements hivernaux

```
python 13_hivernal.py --modele
```

Crée `data/reference-equipements-hivernaux.json`. Trois communes y figurent
déjà : Cognin-les-Gorges, Saint-Gervais et Rovon, que l'arrêté nomme
explicitement. Complétez la liste depuis le PDF de la préfecture, puis
passez `saisie_complete` à `true`.

Les communes se désignent par leur **nom**, tel qu'il figure dans l'arrêté :
le script les rapproche du référentiel sans tenir compte des accents, des
tirets ni de la casse. Un code INSEE reste accepté.

**Supprimez le fichier de référence créé lors de votre premier essai** :
il contient des codes INSEE erronés.

Tant qu'elle est à `false`, les communes non listées n'affichent **rien** —
pas un « non concernée » qui pourrait être faux.

### Vigilance météorologique

```
python 14_vigilance.py --modele
```

Nécessite une clé gratuite : compte sur `portail-api.meteofrance.fr`,
souscription à l'API Bulletin Vigilance, génération d'une clé. Puis
`python 14_vigilance.py --inspecter` pour l'éprouver.

Sans clé, le collecteur s'arrête proprement sans rien écrire.

### Agriculture biologique

```
python 16_bio.py --colonnes
```

Vérifie que les colonnes du fichier de l'Agence Bio sont bien reconnues.
Trente secondes, et cela évite une collecte pour rien.

### Élus

Trois défauts de lecture ont été corrigés grâce à votre sortie `--colonnes` :
le fichier des maires ne porte pas de colonne de fonction — elle était
confondue avec « Date de début de la fonction » ; le fichier des conseillers
communautaires ne porte pas le code de l'intercommunalité, le rattachement
se fait donc par les communes membres ; et le code de canton du répertoire
est local au département — 23 et non 3823.

Relancez pour confirmer :

```
python 15_elus.py --colonnes
```

Puis la collecte. Le fichier des conseillers municipaux pèse 64 Mo : il est
mis en cache, le second passage est immédiat.

---

## Ensuite

```
python lancer.py
```

Six étapes. Les collecteurs sans configuration s'arrêtent proprement en
expliquant ce qui leur manque.

---

## Ce qui change à l'écran

**Aperçu** — une tuile supplémentaire renvoie vers les élus : le maire sur
une commune, les conseillers départementaux sur le canton, le président sur
l'intercommunalité.

**Icônes** — chaque rubrique, sous-rubrique, tuile et bandeau de section
porte un pictogramme. Taille, couleur et épaisseur de trait sont trois
variables du thème.

**Accueil** — mêmes bandeaux que les fiches, introduction en pleine largeur,
chiffres clés redessinés.

**Sous-rubriques nouvelles** : Vigilance et Agriculture sous Environnement,
Élus sous Élections.

**Administration** — `/Terri_Admin/` suit désormais les référentiels saisis
à la main, séparément des collectes automatiques.

---

## Points restés en suspens

| Sujet | Action |
|---|---|
| Mentions légales | Renseigner `MENTIONS` en tête de `04_generation.py` — obligatoire avant communication publique |
| Protection de `/Terri_Admin/` | Ouvrir `chiffrer.php`, suivre les trois étapes, supprimer l'assistant |
| Ancien dossier `administration` | Supprimer `index.html` du dépôt : il serait servi à la place du leurre |
| Liste des équipements hivernaux | Compléter depuis l'arrêté préfectoral |
| Clé Météo-France | À demander |

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | Le lanceur ne signale aucun fichier en retard de version |
| 2 | L'aperçu d'une commune affiche le nom de son maire, avec renvoi |
| 3 | Les icônes sont à la bonne taille, pas démesurées |
| 4 | La rubrique Élections apparaît, avec sa sous-rubrique Élus |
| 5 | Aucune fiche d'élu n'affiche de date de naissance ni de profession |
| 6 | La sous-rubrique Agriculture affiche surfaces et cultures |
| 7 | La réserve sur le siège d'exploitation figure sous le bloc bio |
| 8 | `/administration/` présente la fausse page de connexion |
| 9 | `/Terri_Admin/` demande un mot de passe, une fois protégé |
