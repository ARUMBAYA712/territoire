# Élections — instruction de la source

8 septembre 2026. **Rapport de faisabilité. Aucun code écrit, rien
d'installé dans votre dépôt.**

Vous placez les élections début octobre, avec l'idée qu'un historique
des votes par commune et au canton préparerait le référencement des
prochains scrutins. J'ai instruit la source pendant votre absence.
Tout ce qui suit est **vérifié requête par requête**, sur les fichiers
réels.

**Conclusion en une phrase** : c'est faisable, la source est bonne, et
le seul obstacle sérieux — le poids des fichiers — est levé par une
mesure qui ramène **75 mégaoctets à 1,2**.

---

## 1. La source, et son état

Le ministère de l'Intérieur publie sur data.gouv.fr **un jeu de données
par scrutin et par tour**, sous **Licence Ouverte 2.0**. Chaque jeu
contient les mêmes résultats à sept échelles : France entière, régions,
départements, circonscriptions, **cantons**, **communes**, bureaux de
vote.

Deux échelles nous concernent, et elles sont exactement les vôtres :
**la commune** et **le canton**. Le canton au sens électoral est le
canton départemental — pour vous, le 3823, celui-là même que le site
publie déjà.

Scrutins disponibles avec un fichier communal, du plus récent au plus
ancien :

| Scrutin | Tours | Publié |
|---|---|---|
| **Municipales 2026** | 1 et 2 | mars 2026 |
| Législatives 2024 | 1 et 2 | juillet 2024 |
| Européennes 2024 | tour unique | juin 2024 |
| Législatives 2022 | 1 et 2 | juin 2022 |
| Présidentielle 2022 | 1 et 2 | avril 2022 |
| Régionales 2021 | 1 et 2 | juin 2021 |
| Départementales 2021 | 1 et 2 | juin 2021 |
| Municipales 2020 | 1 et 2 | mars-juin 2020 |
| Européennes 2019 | tour unique | mai 2019 |
| Présidentielle 2017, législatives 2017 | 1 et 2 | 2017 |

Au-delà de 2017, les jeux existent encore — européennes 2014,
municipales 2014, municipales 2008 — mais la structure des fichiers
change et la comparabilité s'effrite. **Une profondeur de 2017 à 2026,
soit huit ou neuf scrutins, est ce que je recommanderais** : c'est
suffisant pour montrer une évolution, et tous les fichiers y ont la
même forme.

Un point à signaler tout de suite : **les municipales de mars 2026 sont
déjà publiées.** C'est le scrutin le plus local qui existe, il a six
mois, et aucun site du territoire n'en présente les résultats commune
par commune.

---

## 2. Le vrai obstacle, et sa solution

Les fichiers communaux sont **énormes** :

| Fichier | Poids |
|---|---|
| Européennes 2024 — par commune | **124 Mo** |
| Législatives 2024 — par commune | **75 Mo** |
| Municipales 2026 — par commune | 14 Mo |

Huit scrutins représenteraient **plusieurs centaines de mégaoctets à
chaque collecte**, pour quarante-sept communes. Ce serait le fichier
le plus lourd du projet, devant l'INSEE.

**Ils sont triés par code de département.** Toutes les communes de
l'Isère sont donc contiguës dans le fichier, et le serveur de
data.gouv.fr **accepte les requêtes partielles** — vérifié, il répond
bien `206 Partial Content`.

J'ai mesuré ce que cela donne sur le fichier des législatives 2024, en
cherchant les bornes du bloc « 38 » par dichotomie :

```
  début du département 38 : octet 30 538 102
  fin   du département 38 : octet 31 774 481
  taille du bloc          : 1,2 Mo — soit 1,6 % du fichier
  coût de la recherche    : 17 requêtes de 4 Ko
```

**1,2 mégaoctet au lieu de 75.** Huit scrutins tiendraient dans une
dizaine de mégaoctets, moins que le cache climat que nous venons
d'exclure du dépôt. La collecte devient une affaire de secondes, et
aucun fichier volumineux n'a besoin d'être conservé.

C'est la même idée que le seuil adaptatif des nappes ou le filet
journalier des rivières : **la mesure qui rend la chose possible est
une mesure de lecture, pas de calcul.**

Deux réserves honnêtes sur ce procédé :

- il suppose que le tri par département ne change pas. Si un fichier
  futur était trié autrement, la dichotomie renverrait n'importe quoi.
  **Le collecteur devra donc vérifier**, après lecture, que toutes les
  lignes retenues portent bien le département attendu, et retomber sur
  une lecture complète en flux si ce n'est pas le cas ;
- une lecture partielle tombe au milieu d'une ligne. La première ligne
  de chaque tranche est donc à jeter, ce qui est sans conséquence dès
  lors qu'on se recale sur le retour à la ligne suivant.

**Ce qui ne marche pas, et qu'il ne faut pas essayer** : l'API
tabulaire de data.gouv.fr, qui permettrait normalement d'interroger un
CSV ligne à ligne. Interrogée sur le fichier des municipales 2026, elle
répond que la ressource *« a été définitivement supprimée par son
producteur »* — alors que le fichier est bien là et se télécharge. Ces
fichiers, dont le nombre de colonnes varie d'une ligne à l'autre, ne
sont pas indexables par cet outil. Il ne faut pas compter dessus.

---

## 3. La forme des fichiers, et le piège qu'elle cache

Le format est **large** : les colonnes d'identité, puis un bloc de
colonnes répété pour chaque candidat ou chaque liste.

```
Code département;Libellé département;Code commune;Libellé commune;
Inscrits;Votants;% Votants;Abstentions;% Abstentions;Exprimés;…;
Numéro de panneau 1;Nuance candidat 1;Nom candidat 1;Prénom candidat 1;
Sexe candidat 1;Voix 1;% Voix/inscrits 1;% Voix/exprimés 1;Elu 1;
Numéro de panneau 2;…
```

Trois observations, chacune vérifiée :

**« Code commune » porte le code INSEE complet, sur cinq chiffres** —
`49311`, `38416`. Ce n'est pas le code sur trois chiffres qu'on
rencontre dans d'autres fichiers du ministère. Le rapprochement avec
votre référentiel est donc direct.

**Le nombre de colonnes varie d'un scrutin à l'autre** : 187 pour les
municipales 2026, davantage pour les européennes qui comptaient
trente-huit listes. Le collecteur ne peut pas travailler sur des
positions fixes : il devra lire l'en-tête et repérer les blocs par leur
suffixe numérique.

**Et surtout : le guillemetage change d'un fichier à l'autre.** Les
municipales 2026 encadrent chaque champ de guillemets, les législatives
2024 ne le font pas. Un collecteur qui découperait sur le point-virgule
sans passer par un vrai lecteur CSV lirait `"38"` au lieu de `38` sur
la moitié des scrutins — je m'y suis laissé prendre à la première
tentative. Le module `csv` de la bibliothèque standard règle cela sans
un caractère de plus.

---

## 4. Ce que cela donne sur vos communes

Municipales 2026, premier tour, extrait du fichier réel :

| Commune | Inscrits | Participation | Première liste | Voix |
|---|---|---|---|---|
| Saint-Marcellin | 5 390 | **58,57 %** | Saint-Marcellin Demain (LDVC) | 580 — 18,81 % |
| Vinay | 3 295 | **57,18 %** | Alternatives citoyennes et solidaires (LDVG) | 251 — 13,69 % |
| Rencurel | 285 | **57,54 %** | Ensemble Rencurel | 154 — **100 %**, 11 sièges |

Le cas de Rencurel est instructif : **liste unique, élue au premier
tour avec la totalité des suffrages exprimés.** Une page qui
afficherait « 100 % des voix » sans dire qu'il n'y avait qu'une liste
serait exacte et trompeuse — c'est très exactement le genre de piège
que nous avons déjà rencontré avec la tempête de 1982. Le fichier
donne le nombre de listes ; le collecteur doit s'en servir pour écrire
la réserve.

Le département de l'Isère compte **510 communes** dans ce fichier, et
la lecture des quarante-sept qui vous concernent tient dans le bloc de
900 Ko que j'ai extrait pour l'essai.

---

## 5. Ce que la rubrique pourrait publier

**Une chronique de participation par commune**, 2017-2026, huit ou neuf
points. C'est ici que les **étiquettes libres livrées en version 33**
trouvent leur emploi : les scrutins ne tombent pas à intervalle
régulier, et aucune forme raisonnant sur un pas de temps ne conviendrait.
La forme `barres` avec des étiquettes explicites — « Prés. 2017 »,
« Mun. 2020 », « Lég. 2024 », « Mun. 2026 » — est celle qui convient.

C'est probablement la série la plus parlante de tout le site après le
bio : la participation aux municipales dans un village se lit, se
compare aux voisines, et personne ne la publie à cette échelle.

**Les résultats du dernier scrutin, par commune**, sous forme de bloc :
inscrits, votants, exprimés, puis les listes ou candidats avec leurs
voix et leur pourcentage.

**Le même au canton**, en reprenant le fichier « par cantons » du
ministère plutôt qu'en additionnant les communes — 585 Ko seulement, et
c'est le producteur qui fait la somme, pas nous.

---

## 6. Trois précautions, dont une qui n'est pas technique

**Les fusions de communes.** Entre 2017 et 2026, des communes ont
fusionné ou changé de code. Une chronique de participation qui
comparerait deux périmètres différents serait fausse. Votre référentiel
porte déjà un champ `commune_scindee` : il faudra le confronter aux
codes de chaque millésime, et **renoncer à la chronique** sur une
commune dont le périmètre a bougé, plutôt que de tracer une rupture
qu'on prendrait pour une évolution.

**Les municipales des petites communes.** En dessous de mille
habitants, le scrutin est plurinominal : on vote pour des personnes,
pas pour des listes. Le fichier de 2026 range malgré tout les résultats
en « listes », souvent sans nuance politique — c'est le cas de Rencurel.
La page doit dire ce qu'elle montre, sans plaquer le vocabulaire des
grandes communes sur les petites.

**Et la précaution qui n'est pas technique : les nuances politiques.**
Le fichier attribue à chaque liste une nuance — LDVC, LDVG, LR, RN…
Ce sont des étiquettes administratives, attribuées par la préfecture,
parfois contestées par les intéressés eux-mêmes. Les publier telles
quelles, en citant leur origine, reste dans le rôle d'un portail de
données publiques. **En tirer une lecture — « le territoire penche à
droite », « la participation s'effondre » — en sortirait.** Sur un
site qui porte le nom d'un territoire et que ses élus liront, c'est la
seule rubrique où la neutralité de ton devra être tenue ligne à ligne,
et je vous recommande de relire vous-même les textes générés de cette
rubrique avant leur mise en ligne. C'est aussi, pour le référencement
que vous visez, la meilleure garantie : une page qu'on ne peut pas
accuser de prendre parti est une page qu'on cite.

---

## 7. Estimation

| Étape | Charge |
|---|---|
| Collecteur `19_elections.py` — lecture partielle, en-tête variable, contrôles | l'essentiel du travail |
| Chronique de participation, étiquettes libres | rien à ajouter au générateur : la version 33 suffit |
| Bloc de résultats par commune et au canton | classique, comme les arrêtés Géorisques |
| Contrôle des fusions de communes | à écrire, et c'est le point le plus délicat |

Le générateur n'a **rien à apprendre** : la rubrique Élections existe
déjà, sa sous-rubrique Résultats aussi, et les étiquettes libres ont
été livrées pour cela. Tout le travail est dans le collecteur.

Votre échéance de début octobre me paraît tenable, et je dirais même
confortable — à condition de commencer par **un seul scrutin, les
municipales 2026**, et de remonter le temps ensuite. Une rubrique qui
publie correctement un scrutin vaut mieux qu'une rubrique qui en publie
neuf approximativement, et la chronique de participation peut s'ajouter
après coup sans rien casser.

---

## Ce que je n'ai pas vérifié

- La **stabilité des adresses** des fichiers statiques dans le temps.
  Elles portent un horodatage (`20240711-075056`) : il faudra passer
  par l'API de data.gouv.fr pour retrouver l'adresse courante d'une
  ressource, jamais l'écrire en dur.
- Le format exact des scrutins **antérieurs à 2017**.
- Le fichier **par cantons** des municipales — il pourrait ne pas
  exister, ce scrutin n'ayant pas de sens cantonal.
