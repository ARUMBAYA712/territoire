# Séries historiques et graphiques — rapport de faisabilité

8 septembre 2026, fin de journée.

**Ce rapport remplace la partie 6 de `DEMANDES-2026-09-08.md`.** Celle-ci
était de l'analyse sur documents : je n'avais alors aucun accès réseau
vers les sources. Cette fois j'ai pu les interroger réellement, station
par station, sur l'emprise du Sud Grésivaudan.

Ce qui suit distingue systématiquement **ce que j'ai vérifié** — chaque
chiffre vient d'une requête dont l'adresse est donnée — de **ce que
j'estime**, qui reste une estimation.

---

## En un paragraphe

C'est faisable, et nettement mieux que je ne le pensais ce matin. Trois
raisons : les débits mensuels sont **déjà calculés par l'API** et
remontent à **1969** ; les températures mensuelles sont **déjà calculées
par Météo-France** et remontent à **1988** pour un poste situé à
**Chatte**, dans la vallée ; et le poids d'un graphique est **cinq fois
inférieur** à celui d'une de nos cartes. Le vrai sujet n'est ni la
donnée ni la technique : c'est de ne pas faire dire à une courbe plus
qu'elle ne dit.

---

## 1. Ce que portent réellement les stations du territoire

Toutes les stations ci-dessous sont sur des communes du canton — j'ai
croisé les codes INSEE retournés par les API avec `COMMUNES_CANTON` de
`02_canton.py`. Ce n'est pas un hasard : la vallée de l'Isère est
instrumentée depuis longtemps.

### Débit des rivières — vérifié

Hub'Eau, API hydrométrie v2, référentiel des stations sur l'emprise
`bbox=5.05,44.95,5.60,45.30` : **22 stations**, dont sept sur des
communes du canton.

| Station | Commune | Ouverte depuis | Ce qu'elle vaut |
|---|---|---|---|
| L'Isère à Saint-Gervais [Le Port] — EDF | Saint-Gervais | **1969** | La grande rivière du territoire |
| La Bourne à Saint-Just-de-Claix — EDF | Saint-Just-de-Claix | **1967** | Affluent majeur, régime karstique |
| La Vernaisson à Pont-en-Royans — EDF | Pont-en-Royans | **1965** | Petit bassin, très réactif |
| L'Isère à Saint-Gervais — DREAL | Saint-Gervais | 2009 | Doublon récent du même site |
| Le Vézy à Têche | Têche | déc. 2025 | Trop récente pour un historique |

**Le fait décisif** : l'API sert directement le **débit moyen mensuel**
(`grandeur_hydro_elab=QmM`), déjà calculé et qualifié. Pour l'Isère à
Saint-Gervais, elle renvoie **687 valeurs mensuelles, la première datée
de janvier 1969** — soit cinquante-sept ans. Chaque valeur porte son
statut (« Donnée validée »), sa méthode (« Expertisée ») et sa
qualification (« Bonne ») : de quoi afficher les lacunes honnêtement
plutôt que de les deviner.

> `hubeau.eaufrance.fr/api/v2/hydrometrie/obs_elab?code_entite=W320001001&grandeur_hydro_elab=QmM&sort=asc`
> → `"count": 687`, première ligne `"date_obs_elab":"1969-01-01"`

**Une réserve de fond, et elle est sérieuse.** L'Isère est une rivière
très aménagée. Son débit mesuré à Saint-Gervais traduit autant la
gestion des ouvrages EDF que la pluie et la fonte des neiges. Une courbe
de l'Isère ne raconte donc pas le climat — elle raconte l'Isère
aménagée. L'API publie aussi un **débit naturel reconstitué**
(`W320001201`, « QNR Le Port ») : c'est celui-là qu'il faudra utiliser
pour parler d'évolution, et le dire. La Bourne et la Vernaisson, elles,
sont beaucoup plus proches d'un régime naturel.

### Niveau des nappes — vérifié

Onze piézomètres sur l'emprise, dont **trois en Isère**, et deux
exploitables :

| Piézomètre | Commune | Période | Mesures |
|---|---|---|---|
| Puits de Fontchaude | **Saint-Bonnet-de-Chavagne** | 2005-09 → aujourd'hui | **6 839** |
| Forage Croix du Plâtre | **Vatilieu** | 2011-07 → aujourd'hui | 5 490 |
| (un troisième, commune 38453) | — | — | **0 mesure** |

Les huit autres sont dans la Drôme. Chaque mesure porte une
`qualification` (« Correcte », « Incertaine ») — même bénéfice que
pour les débits.

**Différence importante avec les débits** : Hub'Eau ne publie **pas** de
moyenne mensuelle pour les nappes. Il faudra agréger nous-mêmes les
6 839 mesures journalières en 252 valeurs mensuelles. Ce n'est pas
difficile, mais c'est du calcul à écrire, et donc à contrôler.

### Températures et précipitations — vérifié, et c'est la bonne surprise

Météo-France publie sur data.gouv.fr les **« Données climatologiques de
base — mensuelles »**, en Licence Ouverte, **sans clé d'API** (la clé
n'est nécessaire que pour la vigilance et le temps réel). Un fichier par
département, mis à jour quotidiennement pour les deux dernières années.

Pour l'Isère : `MENSQ_38_previous-1950-2024.csv.gz`, **2,8 Mo
compressés**, **64 789 lignes** — une ligne par poste et par mois.

**Trois postes sur des communes du canton** :

| Poste | Commune | Altitude |
|---|---|---|
| CHATTE_SAPC | **Chatte** | 272 m — dans la vallée |
| SERRE-NERPOL_SAPC | **Serre-Nerpol** | 632 m |
| RENCUREL | **Rencurel** | 885 m |

Trois altitudes, trois climats : la vallée, le piémont, le Vercors. Pour
un territoire qui va de 200 à 1 500 mètres, c'est exactement ce qu'il
faut.

**Profondeur au poste de Chatte** : 448 mois de relevés depuis mai 1987,
dont **438 mois de température complète depuis janvier 1988** — trente-
sept ans. Les premiers mois ne portent que la pluie : le poste a été
équipé en température plus tard. **C'est le genre de chose qu'il faudra
montrer, pas lisser.**

Et le fichier ne contient pas que des moyennes. Chaque ligne porte
notamment :

| Champ | Ce que c'est |
|---|---|
| `TM`, `TX`, `TN` | Températures moyenne, maximale, minimale du mois |
| `RR` | Cumul de pluie |
| `NBJGELEE` | **Nombre de jours de gel** |
| `NBJTX30`, `NBJTX35` | **Nombre de jours à 30 °C, à 35 °C** |
| `NBJRR10`, `NBJRR30` | Jours de pluie forte, de pluie très forte |
| `NEIGETOTM` | Enneigement |
| `NBTM` | Nombre de jours réellement mesurés dans le mois |

Ce dernier champ vaut de l'or : il dit si le mois est complet. Un mois
calculé sur cinq jours ne devra pas être tracé comme un mois calculé sur
trente et un.

### Population depuis 1876 — existe, non inspecté

L'INSEE publie l'« Historique des populations communales » depuis 1876.
Je n'ai pas ouvert le fichier : c'est la seule source de ce rapport que
je n'ai pas vérifiée dans le détail. Format et millésimes restent à
confirmer.

### Ce que nous avons déjà, sans rien télécharger

Deux séries dorment dans nos propres fichiers :

| Donnée | Profondeur | Maille | Coût de collecte |
|---|---|---|---|
| Agriculture biologique | 2008 → 2025, 18 millésimes | **Commune** | **Nul** — le fichier est en cache, nous n'en lisons que la dernière ligne |
| Catastrophes naturelles | Depuis 1982, 215 arrêtés | **Commune** | **Nul** — déjà collecté, seules les dates sont à regrouper |

---

## 2. La question de la maille, qui décide de tout

**Nappes, débits et climat se mesurent en stations.** Il n'y aura pas de
courbe de température « à Saint-Antoine-l'Abbaye » : il y aura la courbe
du poste de Chatte, nommé, avec son altitude et sa distance. Promettre
une finesse communale sur ces trois-là serait faux, et le site s'est
interdit ce genre de promesse partout ailleurs.

C'est d'ailleurs déjà l'arbitrage rendu : `09_nappes.py` et
`12_rivieres.py` publient au **canton** et à l'**intercommunalité**, avec
la station nommée. Les séries historiques suivront la même règle — et
cela règle du même coup la question du poids.

**Deux séries font exception et sont bien communales** : le bio et les
catastrophes naturelles. Ce sont aussi les moins chères. C'est par elles
qu'il faut commencer.

---

## 3. Finesse recommandée

| Donnée | Finesse | Pourquoi |
|---|---|---|
| Débits | **Mensuelle** | C'est la maille qui montre la saison et l'étiage |
| Nappes | **Mensuelle** | Idem ; le cycle annuel est l'information première |
| Températures, pluie | **Mensuelle** pour le détail, **annuelle** pour la tendance | Deux lectures différentes, deux graphiques |
| Jours de gel, jours ≥ 30 °C | **Annuelle** | Un comptage mensuel serait du bruit |
| Population, bio, CatNat | **Annuelle** | La donnée n'existe pas plus fin |

**Le trimestre n'apporte rien ici** : trop grossier pour montrer une
saison, trop fin pour montrer une tendance. Je ne le recommande pour
aucune des séries.

**Deux précautions statistiques**, qui changent ce que la courbe raconte :

- **Médiane, et non moyenne, pour les débits.** Une crue de trois jours
  double la moyenne mensuelle et fait croire à une année humide.
- **Moyenne pour la température**, c'est la convention climatologique,
  et la comparaison se fait à la **normale 1991-2020**. C'est l'écart à
  la normale qui donne le sens, pas la valeur brute.

---

## 4. La forme

### Le graphique lui-même : SVG écrit dans la page

Aucune bibliothèque, comme pour les cartes. Le graphique est dans le
HTML : lisible sans JavaScript, imprimable, indexable, et il ne dépend
d'aucun service tiers.

**Interactif, oui, mais en second.** Le survol affiche la valeur exacte,
comme il le fait déjà sur les cartes ; un sélecteur permet de passer de
« 10 ans » à « tout l'historique ». Ce sont des conforts. Rien de ce que
le graphique raconte ne doit dépendre d'eux — c'est l'exigence ENF-05.

**Sous chaque graphique, le tableau des valeurs, replié**, avec le
mécanisme `details` introduit aujourd'hui pour les communes. C'est ce
qui rend la série accessible à un lecteur d'écran, et copiable par un
journaliste.

### Trois formes, pas une seule

Votre objectif — « mieux se rendre compte que les évolutions sont
marquées » — n'est pas servi de la même façon selon la donnée.

**La courbe mensuelle sur fond de saison.** En arrière-plan, la plage
des valeurs observées pour ce mois sur toute la chronique ; devant, les
douze derniers mois. On voit immédiatement si l'année est dans la norme
ou en dehors. C'est la forme qui convient aux débits et aux nappes.

**Les barres annuelles.** Pour tout ce qui se compte : jours ≥ 30 °C,
jours de gel, arrêtés de catastrophe naturelle, hectares en bio. C'est
la forme la plus honnête pour un comptage, et la plus lisible.

**Les bandes de réchauffement.** Une bande de couleur par année, du bleu
au rouge selon l'écart à la normale. Aucune échelle, aucun chiffre : une
seule image qui se comprend en une seconde et se partage. Trente-sept
bandes pour Chatte. **C'est, pour votre objectif précis, la forme la
plus efficace de toutes** — à condition de la poser à côté du graphique
chiffré, jamais à sa place.

---

## 5. Le poids — mesuré, pas estimé

J'ai écrit un prototype de générateur SVG et mesuré ce qu'il produit,
sur des séries de la cardinalité réelle :

| Graphique | Points | SVG | Une fois compressé |
|---|---|---|---|
| Débit mensuel, Isère, 1969-2026 | 687 | 8,6 Ko | **3,5 Ko** |
| Température mensuelle, Chatte, 1988-2026 | 452 | 5,9 Ko | 2,5 Ko |
| Nappe, moyenne mensuelle, 2005-2026 | 252 | 3,5 Ko | 1,5 Ko |
| Jours ≥ 30 °C par an, 1988-2026 | 38 | 1,1 Ko | 0,5 Ko |

**Pour comparaison, une carte du site pesait 45 Ko avant simplification.**
Le graphique le plus lourd fait un cinquième de cela. La crainte que
j'exprimais ce matin sur le poids n'était pas fondée — parce que les
séries de station ne vivent que sur deux fiches, le canton et
l'intercommunalité, et non sur les 47 communes.

Côté données publiées, une chronique mensuelle de 57 ans écrite en JSON
compact pèse **4,2 Ko**, moins de 2 Ko compressée. Quatre chroniques sur
la fiche du canton : **17 Ko**. Les 18 millésimes bio sur les 47
communes : **5 Ko au total**.

**Le poids n'est pas un sujet.** C'est le premier point sur lequel je me
suis trompé ce matin, et il valait la peine d'être mesuré.

---

## 6. Les règles à poser avant d'écrire la première ligne

C'est ici que se joue la qualité, pas dans la technique.

Une station déplacée, un capteur remplacé, une lacune de deux ans :
chacun produit une rupture qui **ressemble** à une tendance. Sur une
courbe, l'œil voit une évolution là où il n'y a qu'un changement de
méthode. Le poste de Chatte en est l'exemple parfait : la pluie y est
mesurée depuis 1987, la température depuis 1988 seulement. Qui trace les
deux sur la même échelle de temps sans le dire produit une fausse
impression avec des données vraies.

Quatre règles, non négociables :

1. **Afficher les lacunes, ne jamais les interpoler.** Un trou dans la
   courbe est une information. Le prototype le fait déjà : le tracé
   s'interrompt et reprend.
2. **Ne pas tracer de droite de tendance** sans test statistique. Une
   pente calculée sur une série courte ou lacuneuse n'a aucune valeur,
   et elle sera reprise telle quelle par un lecteur.
3. **Nommer la station, son altitude et la période couverte** sur le
   graphique lui-même, pas dans une note de bas de page.
4. **Écarter les mois incomplets**, ou les marquer. Le champ `NBTM` dit
   combien de jours ont servi au calcul ; un mois à cinq jours n'est pas
   un mois.

Sans ces règles, cette rubrique produirait exactement ce que tout le
reste du site s'interdit : une impression fausse, appuyée sur des
données vraies.

---

## 7. Autres données que je propose

Par ordre de rapport intérêt / coût.

**Jours de gel et jours à plus de 30 °C, par an, depuis 1988.** Ma
première recommandation. Ce sont des comptages, pas des moyennes : ils
ne demandent aucune précaution statistique, ils sont dans le fichier que
nous téléchargerons de toute façon, et ils rendent l'évolution
infiniment plus visible qu'une moyenne annuelle qui bouge d'un dixième
de degré. C'est la donnée qui répond le mieux à ce que vous cherchez.

**Débit d'étiage plutôt que débit moyen.** Le minimum sur trois jours
consécutifs (VCN3) traduit la sécheresse ; son évolution est bien plus
parlante qu'une moyenne annuelle. À vérifier : Hub'Eau publie plusieurs
grandeurs élaborées, je n'ai confirmé que `QmM`.

**Arrêtés de catastrophe naturelle par décennie et par type.** Données
déjà en main, maille communale, aucun risque. La sécheresse-argile y est
en forte progression partout, et c'est un fait local et vérifiable.

**Enneigement à Rencurel.** Le champ `NEIGETOTM` existe. Sur un poste à
885 mètres, une série de trente ans dirait quelque chose de concret à
tout le monde ici. À vérifier : la profondeur réelle de la série à ce
poste.

**Parc de logements et résidences secondaires.** Séries INSEE, même
fichier que la population.

---

## 8. Ordre proposé et charge

Six lots. La charge est donnée en séances de travail, à la demi-journée
près ; l'écart vient surtout du temps passé à contrôler, pas à écrire.

| # | Lot | Ce qu'il contient | Charge |
|---|---|---|---|
| 0 | **La mécanique de graphique** | Générateur SVG, tableau replié, styles, survol. Le prototype existe déjà | 1 à 1,5 séance |
| 1 | **Bio 2008-2025 et CatNat par décennie** | Données en main, maille communale, aucun risque réseau. Éprouve la mécanique | 1 séance |
| 2 | **Débits mensuels** | Extension de `12_rivieres.py` : ajouter la grandeur `QmM` à un appel qui existe déjà | 1 séance |
| 3 | **Nappes mensuelles** | Extension de `09_nappes.py`, plus l'agrégation mensuelle à écrire et à contrôler | 1 à 1,5 séance |
| 4 | **Climat — `17_climat.py`** | Source nouvelle, fichier de 2,8 Mo à télécharger, décompresser et filtrer. Le collecteur le plus gros du lot | 2 séances |
| 5 | **Population depuis 1876** | Source à instruire d'abord | 1 séance, après inspection |

**Le lot 0 est le seul qui soit un investissement** : une fois écrit, les
cinq autres ne font qu'appeler la même mécanique. Et le lot 1 ne dépend
d'aucun réseau : c'est le bon endroit pour découvrir les problèmes de
rendu avant d'y ajouter des problèmes de source.

Une remarque sur l'ordre : le lot 2 est **plus simple que le lot 1**
techniquement, mais il demande le réseau et il produit un graphique de
station, moins parlant qu'un graphique de commune. Je maintiens le bio
en premier.

---

## 9. Ce que je n'ai pas vérifié

Par souci d'être clair sur les limites de ce rapport :

- **La profondeur des séries à Serre-Nerpol et à Rencurel.** Vérifiée à
  Chatte seulement.
- **L'existence du fichier climatologique de l'année courante.** La
  fiche du jeu de données annonce une mise à jour quotidienne pour les
  deux dernières années ; je n'ai pas ouvert ce fichier-là.
- **Les grandeurs élaborées de Hub'Eau autres que `QmM`.** Le débit
  d'étiage reste à confirmer.
- **Le fichier INSEE des populations historiques.**
- **Les colonnes exactes du fichier climatologique au-delà de celles
  citées** — j'ai lu une ligne complète, pas la documentation.

Aucune de ces cinq inconnues ne remet en cause le verdict : les trois
séries principales sont là, elles sont longues, elles sont sur nos
communes, et elles sont légères.
