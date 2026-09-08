# Livraison — lot 4 : le climat, et deux correctifs

8 septembre 2026, sixième livraison. **Cinq fichiers posés dans votre
dépôt.**

| Fichier | Version | Ce qui change |
|---|---|---|
| `17_climat.py` | **nouveau, v1** | Températures, pluie et comptages de jours, depuis l'ouverture du poste |
| `04_generation.py` | 33 | Sous-rubrique **Climat**, son pictogramme, et un correctif d'axe |
| `lancer.py` | — | `17_climat.py` inscrit au plan mensuel et à la séquence complète |
| `12_rivieres.py` | 6 | Un troisième contrôle : l'accord entre mensuel et journalier |
| `09_nappes.py` | 3 | Correction du choix de station |

```
python lancer.py --tout
```

---

## 1. Ce que votre run a montré

**Les rivières sont réparées.** Les codes font dix caractères, une
ligne par station, et les décomptes tiennent : la Vernaisson annonce
727 mois qualifiés sur les 744 que compte la période 1965-2026. Plus
aucun empilement.

**Et la Bourne démarre en 1969**, non en 1967 : les vingt et un mois non
qualifiés dont nous avons daté la rupture ont été écartés tout seuls,
sans qu'aucune règle particulière ait été écrite pour eux. C'est le
filtre de qualification qui les a pris.

Deux stations ont été écartées avec leur motif — 24 et 45 mois, moins
que les 120 requis. C'est le comportement voulu : les filets se voient.

---

## 2. Un troisième filet, sur les débits

La station retenue est la Vernaisson à Pont-en-Royans, une station EDF.
Or c'est une station EDF qui, sur la Bourne, annonçait 0,9 m³/s quand
la station DREAL en annonçait 20,5 : rien ne garantissait que celle-ci
mesure le débit de la rivière plutôt qu'un débit dérivé.

Les deux contrôles existants ne pouvaient pas le voir. La qualification
ne dit rien de ce qui est mesuré. Et l'homogénéité compare la station à
elle-même : une station qui mesure de travers depuis soixante ans le
fait de façon parfaitement homogène.

**Le nouveau contrôle ne coûte rien, parce que la réponse était déjà en
mémoire.** Le script interroge déjà, pour chaque station, un débit
moyen *journalier* sur cinq ans — c'est lui qui alimente l'indicateur
« proche des valeurs habituelles ». La chronique mensuelle vient de la
même station : les deux médianes doivent s'accorder sur la période
commune. Au-delà d'un facteur deux, la série est refusée et le motif
écrit.

C'est le contrôle le plus utile des trois, et il n'exige aucune requête
supplémentaire. J'aurais dû y penser d'emblée : la donnée qui contredit
une série est souvent déjà là, à côté.

---

## 3. Les nappes : une règle que j'avais mal réglée

Le script a retenu Vatilieu — 183 mois — alors que Fontchaude en a 232.
Les deux sont à douze kilomètres. Ma règle disait « à partir de quinze
ans, la plus proche gagne » : entre 12,4 km et 12,1 km, elle a tranché
sur trois cents mètres, et perdu quatre années d'histoire.

Du point de vue du visiteur, deux stations à un kilomètre l'une de
l'autre sont à la même distance. Dans une bande de trois kilomètres,
c'est donc la chronique la plus longue qui l'emporte. **Fontchaude, à
Saint-Bonnet-de-Chavagne, reprend sa place** — et elle a l'avantage
d'être sur une commune du territoire.

---

## 4. Le climat — `17_climat.py`

Trois fichiers mensuels de l'Isère téléchargés depuis data.gouv.fr,
**sans clé d'API**. Comme les nappes et les rivières, la publication se
fait au canton et à l'intercommunalité, avec le poste nommé, son
altitude et sa distance : annoncer une température « à Chatte » quand
le poste est à Rencurel, six cents mètres plus haut, serait faux de
plusieurs degrés.

**Quatre garde-fous, tous tirés du fichier lui-même :**

- un mois ne compte que s'il a été mesuré presque en entier — le champ
  `NBTM` donne le nombre de jours réellement relevés ;
- une année ne compte que si onze de ses mois comptent ;
- la **normale 1991-2020** n'est calculée que si vingt de ses trente
  années sont présentes. Sinon la fiche écrit « non calculable » et dit
  combien d'années manquent, plutôt que de produire un écart qui ne
  serait comparable à rien ;
- une série de comptage entièrement nulle n'est pas publiée.

**Quatre graphiques, dans un ordre qui a un sens :** les jours à 30 °C,
les jours de gel, les bandes de réchauffement, et seulement en dernier
la température moyenne annuelle. Sur la page d'essai, les trois
premiers montrent une évolution nette et le dernier ne montre presque
rien — les barres se ressemblent toutes. Les quatre disent la même
chose ; trois se lisent.

Un correctif au passage : l'axe des températures affichait
« 0,0 / 5,0 / 10,0 ». Les décimales de la donnée s'imposaient à la
graduation ; elles se déduisent maintenant du pas.

---

## À vérifier après la collecte

| # | Attendu |
|---|---|
| 1 | `17_climat.py` apparaît dans la séquence, en version 1, après le bio |
| 2 | Il annonce le nombre de postes de l'emprise et celui qu'il retient — **Chatte**, 272 m, sauf surprise |
| 3 | Il affiche la normale 1991-2020 et l'écart de la dernière année complète |
| 4 | La station de nappe retenue est **07953X0104/P — Fontchaude**, 232 mois |
| 5 | La station de débit retenue passe le nouveau contrôle, ou est écartée avec son motif |
| 6 | Une sous-rubrique **Climat** apparaît sous Environnement, sur le canton et l'intercommunalité |
| 7 | Le nombre de pages augmente de deux |

Si le point 5 écarte la Vernaisson, ce ne sera pas une régression :
ce sera le contrôle faisant son travail, et il faudra regarder quelle
station le remplace.

---

## Ce qui reste

Les quatre lots d'historiques sont posés. Restent, dans votre ordre :

- **les carburants**, la semaine prochaine — le mécanisme « une donnée
  dans deux rubriques » les attend depuis la version 31 ;
- **les élections**, début octobre — les étiquettes libres, livrées en
  version 33, sont ce qui permettra d'aligner des scrutins qui ne
  tombent pas à intervalle régulier. La source reste à instruire, et
  c'est le chantier le plus lourd des trois.
