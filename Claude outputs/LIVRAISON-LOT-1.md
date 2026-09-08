# Livraison — lot 1 : les premières séries historiques

8 septembre 2026, quatrième livraison.

**Les fichiers sont déjà posés dans votre dépôt** — je les ai écrits
directement dans `00- DEV\territoire\`. Rien à copier.

| Fichier | Version | Ce qui change |
|---|---|---|
| `16_bio.py` | 3 → **4** | Publie les dix-huit millésimes, plus le dernier |
| `08_georisques.py` | 10 → **11** | Arrêtés par décennie, **et une correction de fond** |
| `03_agregation.py` | 3 → **4** | Reprend et agrège les chroniques |
| `04_generation.py` | 32 → **33** | Étiquettes libres, deux correctifs d'axe |
| `lancer.py` | — | Versions attendues |
| `data/reference-equipements-hivernaux.json` | — | **La liste de l'arrêté, complète** |

```
python lancer.py --tout
```

Une recollecte entière est nécessaire : les deux collecteurs modifiés
doivent réinterroger leurs sources.

---

## 1. Ce que le site va montrer

Éprouvé sur **vos données**, pas sur des valeurs d'essai : j'ai repris
depuis votre poste le cache de l'Agence Bio, le référentiel et les
mesures de Géorisques, et rejoué toute la chaîne.

### Agriculture biologique, 2008-2025

Deux graphiques par commune, et leur somme au canton et à
l'intercommunalité :

| | 2008 | 2025 |
|---|---|---|
| Surface bio du canton | **390 ha** | **2 707 ha** |
| Exploitations engagées | **27** | **144** |

Multiplié par sept en dix-huit ans. C'est la série la plus parlante du
site, et elle ne coûtait rien : le fichier était déjà téléchargé, nous
n'en lisions que la dernière ligne.

**Une décision de fond, à connaître.** Le fichier de l'Agence Bio ne
cite une commune une année donnée que si elle compte au moins un
opérateur certifié. Une commune absente en 2008 n'a donc pas « pas de
donnée » : elle a **zéro hectare**. C'est une valeur, et elle est
tracée comme telle. C'est exactement l'inverse de la règle des nappes,
où un trou signale un capteur en panne — et c'est pourquoi la règle est
écrite dans le collecteur, à côté de la donnée qu'elle concerne.

Les communes qui n'ont jamais rien déclaré n'ont pas de graphique du
tout : dix-huit barres à zéro n'apprennent rien.

### Catastrophes naturelles par décennie

Les 215 arrêtés du territoire, regroupés par décennie. La dernière
période ne compte que sept années : c'est écrit sous le graphique, sans
quoi la comparaison avec les décennies pleines ferait croire à une
baisse.

En dessous de trois arrêtés, aucune répartition n'est produite : à ce
compte-là, une barre de plus ou de moins ne dit rien.

---

## 2. Une correction de fond dans `08_georisques.py`

C'est le point important de cette livraison, et il ne concerne pas les
graphiques.

**Géorisques sert ses dates en `14/05/1988`. Le script ne savait lire
que l'ISO.** Toute date postérieure à 1987 était donc perdue —
silencieusement. Seuls les arrêtés d'avant 1987, dont la date se déduit
du substitut de numéro NOR, restaient exploitables.

Trois conséquences, visibles sur le site en ligne aujourd'hui :

- **« date non précisée »** sur la grande majorité des arrêtés. Sur
  Saint-Marcellin, quatre des sept arrêtés n'affichent aucune date ;
- la liste, annoncée « du plus récent au plus ancien », **ne l'était
  pas** : les deux arrêtés de 1982 arrivaient en tête, les récents
  derrière, tous à égalité sur une date nulle ;
- le bandeau **« Catastrophe naturelle reconnue »**, prévu pour signaler
  une reconnaissance de moins de six mois, **ne pouvait jamais
  s'afficher** — la date comparée était toujours nulle.

Ce dernier point est le plus coûteux : c'est une fonction écrite,
testée en apparence, et morte depuis le début.

Les deux écritures sont désormais acceptées, l'ISO d'abord. Vérifié sur
les sept enregistrements réels de Saint-Marcellin, tirés de l'API :
toutes les dates sont lues, le tri est correct, et l'arrêté d'inondation
de juin 2023 est reconnu comme le plus récent.

**Ce que vous verrez après la recollecte** : des dates d'événement sur
tous les arrêtés, une liste vraiment chronologique, et — sur les
communes concernées — le bandeau de reconnaissance récente.

---

## 3. L'arrêté « loi Montagne » — la saisie est complète

Relevé sur le document numérisé que vous m'avez transmis. **Neuf
communes du territoire figurent dans l'arrêté du 12 janvier 2026**, et
la saisie précédente en donnait une image fausse.

| Commune | Portée | Ce que disait le fichier avant |
|---|---|---|
| Châtelus | Toute la commune | *absente* |
| Choranche | Toute la commune | *absente* |
| Malleval-en-Vercors | Toute la commune | *absente* |
| Montaud | Toute la commune | *absente* |
| Presles | Toute la commune | *absente* |
| Rencurel | Toute la commune | *absente* |
| Cognin-les-Gorges | **RD22**, PR 13+380, carrefour du chemin des Garrigues | « toute la commune » |
| Rovon | **RD35**, PR 8+720, portail aval des Écouges | « toute la commune » |
| Saint-Gervais | **RD35**, PR 8+720, portail aval des Écouges | « toute la commune » |

Autrement dit : le site annonçait à trois communes une obligation sur
tout leur territoire alors qu'elle ne porte que sur une route, et
n'annonçait rien aux six qui sont entièrement concernées. C'est corrigé.

Aucune autre commune du périmètre n'apparaît dans l'arrêté — j'ai
comparé les 150 communes citées avec votre référentiel, sans exception.
La saisie est donc déclarée **complète**, et le blocage disparaît.

**L'échéance passe au 31 octobre 2027.** L'arrêté abroge celui de 2023
et ne porte pas de date de fin : il vaut chaque saison jusqu'à son
remplacement. La faire tomber le 31 octobre 2026 aurait coupé
l'information la veille du jour où l'obligation commence. La
vérification est donc à refaire en octobre 2027 — ou plus tôt si la
préfecture publie un nouvel arrêté.

**Deux réserves.** Le numéro de l'arrêté n'est pas lisible sur la
numérisation (l'OCR rend `38- J,oJ.6- CYi- /1.t - OOOOS`) : le fichier
cite le texte par sa date, pas par son numéro. Et la date du 12 janvier
2026 vient de votre saisie précédente et de la date de création du PDF,
la signature étant elle aussi illisible. Si vous avez le numéro exact
sous les yeux, il a sa place dans le fichier.

---

## 4. Ce qui change dans le générateur

**Étiquettes libres.** Une chronique peut désormais fournir ses propres
libellés de période, sous la clé `etiquettes`, au lieu de les déduire
d'une date de départ et d'un pas. C'est ce qui permet les décennies —
et ce qui permettra les **années d'élection**, qui ne tombent pas à
intervalle régulier. Les formes qui raisonnent sur des dates, saison et
courbe, refusent ces séries plutôt que d'inventer un calendrier.

**Deux correctifs vus au rendu :**

- Sur une commune plafonnant à deux exploitations, l'axe affichait
  « 0 0 1 2 2 » : le pas valait 0,5 et l'arrondi écrasait les
  graduations. Un comptage se gradue désormais en entiers.
- La première barre d'une série n'est plus étiquetée quand elle vaut
  zéro : cela attirait l'œil sur le seul point qui ne dit rien.
- Une unité longue — « exploitations » — débordait à gauche du cadre.
  Elle passe à l'intérieur au-delà de six caractères.

---

## À vérifier après la recollecte

| # | Attendu |
|---|---|
| 1 | `lancer.py --tout` passe sans blocage ; les versions annoncées sont 4, 11, 4 et 33 |
| 2 | `13_hivernal.py` n'affiche plus « saisie déclarée incomplète » et annonce **9 communes, dont 3 partiellement** |
| 3 | Sur `/canton/…/environnement/agriculture/`, deux graphiques : 390 → 2 707 ha, et 27 → 144 exploitations |
| 4 | Sur une commune, le bloc « Catastrophes naturelles » affiche de **vraies dates**, la plus récente en tête |
| 5 | Sur `/commune/38333-rencurel/transports/`, l'obligation porte sur **toute la commune** |
| 6 | Sur `/commune/38390-saint-gervais/transports/`, elle porte sur la **RD35** seulement |
| 7 | Le nombre de pages augmente : les rubriques Transports et Environnement s'ouvrent sur des communes qui n'en avaient pas |

Le point 7 mérite une explication : sur mon banc d'essai, partiel, le
site passait de 442 à 489 pages du seul fait de l'arrêté hivernal. Chez
vous, avec toutes les sources, l'augmentation sera du même ordre — ce
sont de vraies pages, avec du contenu propre à chaque commune.

---

## Ce qui vient ensuite

Selon votre calendrier :

**Cette semaine** — lots 2 à 4 des séries historiques : débits mensuels
(en tête, La Bourne à Saint-Just-de-Claix et ses 708 valeurs depuis
1967), nappes mensuelles, puis le climat de Chatte. Ce sont des
extensions de collecteurs existants, sauf le climat qui demande un
`17_climat.py`.

**Dans une semaine** — les carburants. Le mécanisme « une donnée dans
deux rubriques », livré en version 31, les attend.

**Début octobre** — les élections. Point d'attention dès maintenant :
les étiquettes libres, livrées ici, sont ce qui permettra d'aligner des
scrutins qui ne tombent pas tous les cinq ans. La source reste à
instruire, et c'est le chantier le plus lourd des trois.
