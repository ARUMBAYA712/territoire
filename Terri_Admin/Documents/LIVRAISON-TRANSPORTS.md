# Livraison — Train, Autocar, et l'affichage des licences

9 septembre 2026, septième livraison. **Les fichiers sont posés dans
votre dépôt.**

| Fichier | Version | Ce qui change |
|---|---|---|
| `19_gares.py` | **nouveau, v1** | Gares, fréquentation 2015-2024, gare la plus proche |
| `20_cars.py` | **nouveau, v1** | Desserte en autocar depuis le GTFS |
| `04_generation.py` | 35 → **36** | Licences affichées source par source ; sous-rubriques Train et Autocar |
| `03_agregation.py` | 4 → **5** | Un titre de chronique peut changer à l'échelle agrégée |
| `lancer.py` | — | Les deux collecteurs entrent dans la séquence |

```
python lancer.py --tout
```

Une séquence complète est nécessaire : `20_cars.py` a besoin de
`contours.json`, que `05_cartes.py` produit **après** les collecteurs.
Au premier passage sur une machine neuve, il le dit et écrit un fichier
vide plutôt que d'arrêter la chaîne ; au second, il travaille. Chez
vous le fichier est déjà là.

---

## 1. Les licences — ce que vous avez arbitré, et comment c'est fait

Le site annonçait « Licence Ouverte 2.0 » en pied de chaque page. C'était
exact tant que toutes ses sources l'étaient. Les données de transport
sont sous **ODbL**, qui ajoute à l'attribution une obligation de
**partage à l'identique** : une base dérivée republiée doit l'être sous
la même licence. Le site publie ses fiches en téléchargement — il est
donc concerné.

**Rien n'est écrit en dur.** Chaque mesure porte déjà sa licence dans le
contrat de données ; le générateur la lit et l'affiche telle quelle, à
quatre endroits :

| Où | Ce qui s'affiche |
|---|---|
| Pied de page, toutes les pages | « Licence Ouverte 2.0 et ODbL 1.0 » |
| Mentions légales | un tableau **construit sur la collecte** : quelle licence, pour quelles rubriques, avec la réserve de partage à l'identique là où elle s'applique |
| Page « Fraîcheur des données » | une ligne « Licence » sous chaque source, à côté de son producteur |
| JSON-LD de chaque page | `license` pointe vers les mentions légales quand les licences diffèrent, vers Etalab quand il n'y en a qu'une |

**Éprouvé dans les deux sens.** Avec une seule licence collectée, le
pied de page affiche exactement « Licence Ouverte 2.0 » comme avant, et
le JSON-LD pointe de nouveau vers Etalab. Le jour où une source change
de licence, c'est son collecteur qui le dit et le site suit — personne
n'a de liste à tenir à la main.

La sortie du script le récapitule à chaque exécution :

```
  Licences        : Licence Ouverte 2.0 et ODbL 1.0 — 14 source(s) déclarée(s)
                    Licence Ouverte 2.0 : 12 source(s)
                    ODbL 1.0 : 2 source(s)
```

**Au passage, quatre sources manquaient à la page de fraîcheur** :
climat, carburants, et maintenant gares et cars. Elles y sont.

---

## 2. Le train — quatre gares, et la réserve d'hier est levée

Je vous avais écrit que Poliénas figurait au référentiel des gares sans
apparaître dans le fichier de fréquentation, et qu'il faudrait vérifier
avant de l'afficher. **Vérifié : la halte est bien comptée.** Ma requête
d'hier butait sur l'accent du nom.

Les quatre gares, sur la collecte réelle du 9 septembre :

| Gare | 2015 | 2024 | |
|---|---|---|---|
| Saint-Marcellin | 479 187 | **601 317** | +25 % |
| Vinay | 123 108 | **206 591** | +68 % |
| Saint-Hilaire – Saint-Nazaire | 57 959 | **110 057** | +90 % |
| **Poliénas** | 23 765 | **42 133** | **+77 %** |

Sommées, les quatre passent de **684 019 à 960 098 voyageurs** — et le
creux de 2020 à 521 280 rend la série lisible d'un coup d'œil.

**Les 43 communes sans gare reçoivent la plus proche**, nommée, avec sa
distance à vol d'oiseau et sa fréquentation. Même règle que pour les
carburants : l'absence de la chose vaut d'être écrite. **47 communes sur
47 ont donc du contenu.**

### Trois pièges, et ce qui les attrape

**Le référentiel des gares porte des doublons.** Moirans, Valence-TGV et
Gières y figurent deux fois, même code UIC, coordonnées distantes de
quelques dizaines de mètres. Compter les lignes donnerait un nombre de
gares faux. Le dédoublonnage se fait sur le code UIC, et le nombre de
doublons écartés est écrit dans la sortie.

**Une colonne casse le motif.** Toutes s'appellent
`total_voyageurs_2015`, `_2016`, `_2018`… sauf une : `totalvoyageurs2017`,
sans les tirets bas. Les noms de colonnes sont donc écrits un par un
plutôt que construits par formule, **et un contrôle vérifie que 2017 a
bien été lu** : si la SNCF régularisait ce nom, la chronique perdrait
son année centrale en silence. Le script le dirait.

**Deux totaux cohabitent.** Le fichier donne les voyageurs, et les
voyageurs *plus* les accompagnants estimés — 601 317 contre 751 646 pour
Saint-Marcellin, 25 % d'écart. On publie le premier, et la note le dit.

**Et un contrôle de position**, comme pour les stations-service : une
gare rattachée par son nom à une commune du territoire mais située très
loin de son centre est écartée. Il existe plusieurs Saint-Hilaire et
plusieurs Saint-Sauveur en France.

---

## 3. Un correctif de fond dans `03_agregation.py`

Il est né du train, mais il ne le concerne pas seul.

La chronique de Poliénas s'intitule « Voyageurs à la gare de Poliénas ».
Sommée au canton, elle gardait ce titre — un graphique qui additionne
quatre gares, annoncé comme celui d'une seule. Exact dans ses chiffres,
faux dans ce qu'il dit.

Une chronique peut désormais déclarer `titre_agrege` et `note_agregee` :
le titre et la note qu'elle prend **une fois sommée**. Sans eux, le titre
est conservé tel quel — c'est le cas des surfaces bio, dont le libellé
est déjà générique, et leur sortie ne bouge pas d'un octet.

Le canton affiche donc « Voyageurs dans les gares du territoire », avec
une note qui précise que la série additionne toutes les gares.

---

## 4. L'autocar — et la question que je n'ai pas tranchée

Le GTFS de cars Région Isère : 495 lignes, 9 392 arrêts, 3 643 courses,
30 Mo, offre fixée jusqu'au 31 août 2027.

Le collecteur rattache les arrêts aux communes **par point dans
polygone**, avec vos contours — deux filtres successifs, le rectangle
englobant du territoire puis le contour exact, ce qui écarte en une
comparaison les milliers d'arrêts du reste du département. Les
« stations » du GTFS, qui regroupent plusieurs quais, ne sont pas
comptées : ce serait compter deux fois le même lieu.

### Le jour de référence

Un GTFS ne décrit pas « la desserte », il décrit un calendrier. Compter
les passages sans dire de quel jour on parle produirait un chiffre qui
ne veut rien dire. **Deux jours sont donc comptés et publiés
séparément** : un mardi, et un samedi. Les deux dates sont écrites sur
la page.

Le calendrier des exceptions est lu, pas seulement la règle
hebdomadaire — sans quoi des cars circuleraient le 25 décembre. À
l'essai, une exception retirant un service le mardi de référence est
bien prise en compte.

### Ce que je n'ai pas tranché, et pourquoi

Une partie des 495 lignes sont des services scolaires. Les compter comme
des cars ouverts à tous gonflerait la desserte des petites communes.
**Le GTFS ne porte aucun champ normalisé qui les distingue.**

Plutôt que d'inventer un critère que je n'ai pas vérifié — mon
environnement n'a pas accès à data.gouv.fr, je n'ai jamais eu cette
archive sous les yeux — le script **inventorie les lignes et vous les
montre** :

```
python 20_cars.py --inventaire
```

Il n'écrit rien et liste les vingt lignes les plus fournies avec leur
nombre de courses. C'est à la lecture de cette liste que se règle
`MOTIFS_SCOLAIRES`, en tête du fichier. **Envoyez-moi cette sortie et je
le renseigne.**

Tant que la liste est vide, la desserte publiée est la desserte
**totale**, et la note de la page le dit franchement : « Les services
scolaires ne sont pas distingués des lignes ouvertes à tous : le chiffre
du mardi les comprend. » C'est moins bien que la vérité fine, mais ce
n'est pas trompeur.

### Une distinction de vocabulaire qui compte

« Pourvue d'un arrêt » et « desservie » ne sont pas la même chose : une
commune peut compter un poteau où aucun car ne s'arrête le jour de
référence. Les deux chiffres sont donnés, et nommés pour ce qu'ils sont.

---

## 5. Ce que le site gagne

La rubrique Transports ne portait qu'une obligation réglementaire
hivernale et un écho des carburants. Elle a maintenant **deux
sous-rubriques avec leur propre adresse** :

```
  /commune/38416-saint-marcellin/transports/train/
  /commune/38416-saint-marcellin/transports/autocar/
```

Une adresse par mode vaut mieux qu'une page unique où « gare » et
« arrêt de car » se disputeraient le même titre — c'est la même logique
que les sous-rubriques de l'Environnement.

**Éprouvé de bout en bout** : les collecteurs rejoués sur données
réelles, injectés dans les fiches, générés en pages. Le graphique de
fréquentation s'affiche, les tuiles portent leur licence ODbL, les
arrêts sont classés du mieux desservi au moins desservi.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | Les versions annoncées sont **5**, **36**, **1** et **1** |
| 2 | `19_gares.py` annonce **4 gares du territoire** et **47 communes servies sur 47** |
| 3 | Aucun `[ATTENTION] Aucune valeur lue pour 2017` — sinon la source a changé un nom de colonne |
| 4 | `20_cars.py` annonce un nombre d'arrêts non nul, et **avertit que MOTIFS_SCOLAIRES est vide** — c'est attendu |
| 5 | `04_generation.py` affiche « Licences : Licence Ouverte 2.0 et ODbL 1.0 » avec le détail par licence |
| 6 | Le pied de page des fiches porte les deux licences |
| 7 | Sur `/mentions-legales/`, un tableau donne la licence de chaque famille de sources, avec la réserve de partage à l'identique sur l'ODbL |
| 8 | Sur `/fraicheur/`, chaque source porte une ligne « Licence » |
| 9 | Sur `/canton/…/transports/train/`, le graphique s'intitule « Voyageurs dans les gares du territoire » — **pas** « à la gare de Poliénas » |
| 10 | Le nombre de pages augmente d'environ cent : deux sous-rubriques sur quarante-neuf territoires |

---

## Ce qu'il me faut de vous

**La sortie de `python 20_cars.py --inventaire`.** C'est la seule chose
qui manque pour distinguer le scolaire du régulier, et elle ne peut
venir que d'une machine qui a l'archive. Trois minutes de votre part,
et la rubrique passe de « honnête mais grossière » à juste.
