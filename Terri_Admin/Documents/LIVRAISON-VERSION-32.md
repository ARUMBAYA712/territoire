# Livraison — `04_generation.py` version 32

8 septembre 2026, troisième livraison. **Lot 0 du rapport de
faisabilité : la mécanique de graphique.**

C'est l'investissement du chantier « historiques ». Une fois posé, les
cinq lots suivants ne font qu'appeler cette mécanique — ils n'écrivent
plus une ligne de dessin.

**Un seul fichier change** : `04_generation.py`. Plus la ligne de version
dans `lancer.py`.

```
python lancer.py --site
```

**Rien ne bouge tant qu'aucun collecteur ne déclare de chronique.** C'est
vérifié : sur des données sans chronique, les 727 pages sortent
identiques **au caractère près** à celles de la version 31, et le plan du
site compte le même nombre d'adresses.

---

## 1. Ce qu'un collecteur écrit

Une chronique est une suite de valeurs régulièrement espacées, attachée
à une rubrique comme le sont les mesures et les blocs. Elle se déclare
dans la fiche, sous la clé `chroniques` :

```python
{"id": "debit-mensuel",
 "rubrique": "environnement", "sous_rubrique": "rivieres",
 "forme": "saison",                    # saison | courbe | barres | bandes
 "titre": "Débit mensuel de l'Isère à Saint-Gervais [Le Port]",
 "source": "Hub'Eau · débit naturel reconstitué · 1969-2026",
 "unite": "m³/s", "decimales": 1, "rang": 10,
 "note": "L'Isère est très aménagée : la valeur affichée est le "
         "débit naturel reconstitué.",
 "debut": "1969-01", "pas": "mois",    # ou "pas": "an" et "debut": "1988"
 "valeurs": [82.7, 71.4, None, 96.2, ...]}
```

**Le format est délibérément compact** : une date de départ, un pas, et
un tableau de nombres. Écrire un objet par point — avec sa date, son
libellé, son unité répétés — triplerait le poids du fichier publié sans
rien apprendre à personne. Une chronique mensuelle de 57 ans pèse ainsi
4,2 Ko.

`None` marque une lacune. C'est la seule chose à savoir pour en
produire une.

---

## 2. Les quatre formes

| `forme` | Ce qu'elle fait | Pour quoi |
|---|---|---|
| `saison` | Douze mois en abscisse ; la bande montre tout ce qui a été observé, la ligne sombre la médiane, la ligne verte l'année en cours | Débits, nappes — situer l'année en cours |
| `courbe` | La chronique entière, lacunes comprises | Montrer l'évolution longue |
| `barres` | Un comptage par période | Jours de gel, jours chauds, arrêtés CatNat |
| `bandes` | Une bande de couleur par année, du bleu au rouge | L'écart au repère, compris en une seconde |

Une forme qui ne peut pas être produite honnêtement **ne produit rien**
plutôt qu'un graphique faux : `saison` exige douze mois d'historique
complet, `courbe` au moins trois valeurs. Un collecteur peut donc
déclarer une chronique avant que la donnée soit suffisante — elle
apparaîtra le jour où elle le sera. Le même filet attrape une forme
inconnue ou une donnée malformée.

---

## 3. Les quatre règles, tenues par le code

Ce sont les règles du rapport de faisabilité. Elles ne dépendent pas de
la vigilance de qui écrira le prochain collecteur : elles sont dans le
générateur.

**Les lacunes s'affichent, jamais ne s'interpolent.** Un `None`
interrompt le tracé et grise la période. Sans cela, l'œil relie les deux
bords et invente une continuité qui n'existe pas.

**Aucune droite de tendance.** Une pente calculée sur une série courte ou
lacuneuse n'a pas de valeur, et elle serait reprise telle quelle par un
lecteur. Le générateur n'en trace pas, et **il n'y a pas d'option pour en
demander une**.

**La période couverte est écrite sur le graphique**, dans sa source, pas
dans une note de bas de page.

**Toute valeur est lisible sans le graphique.** Sous chacun, le tableau
replié : une matrice années × mois pour les séries mensuelles, deux
colonnes pour les séries annuelles, les lacunes marquées d'un tiret.
C'est ce qui rend la donnée accessible à un lecteur d'écran, et copiable
par un journaliste.

---

## 4. Le survol, et ce qu'il n'est pas

Le graphique est écrit dans la page : il se lit sans JavaScript,
s'imprime, et s'explore par un moteur. Le script `assets/graphiques.js`
ajoute un viseur et une infobulle — **1,6 Ko**, et **il n'est chargé que
sur les pages qui portent un graphique**. Une page de population ne
télécharge rien.

Vérifié, JavaScript désactivé : les tracés et les 22 lignes du tableau
sont toujours là.

La zone sensible d'un point vaut la moitié de l'écart à ses voisins —
jamais un pixel à viser.

---

## 5. Deux choix de couleur, et leur raison

**La palette des bandes est divergente au sens strict** : deux teintes
opposées — le bleu du site, son rouge d'alerte — et un milieu qui doit
se lire comme « rien ». Un dégradé arc-en-ciel, ou une teinte au milieu,
ferait croire à une progression là où il y a un signe.

**Le vert d'accent et le bleu du site ne peuvent pas servir de deux
séries dans un même graphique.** Passés au validateur, leur écart
perceptuel est de **11,8** là où **15** est nécessaire pour être
distingués en vision normale : deux courbes ainsi colorées se
confondraient. Le bleu et le rouge sont à **24,8**, et tiennent aussi en
vision des couleurs déficiente. C'est une contrainte à retenir pour la
suite du chantier.

---

## 6. Le reste du générateur

- Une chronique **rend sa rubrique et sa sous-rubrique actives**, comme
  le fait une mesure ou un bloc. C'est ce qui fait apparaître la
  sous-rubrique dans la navigation et son adresse au plan du site.
- Les graphiques se placent **après les tuiles et avant les blocs
  détaillés**, dans une section « Évolution » avec son pictogramme.
- L'empreinte des ressources tient compte du nouveau script : pas de
  cache périmé après mise à jour.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | Le run annonce la **version 32** |
| 2 | **727 pages et 727 adresses au sitemap** — inchangé. Aucun collecteur ne déclare encore de chronique |
| 3 | Une page de rubrique est identique à ce qu'elle était en version 31 |
| 4 | `assets/graphiques.js` existe et n'est appelé par aucune page pour l'instant |

Le point 4 est normal : le script est écrit, il attend ses données.

---

## Ce qui vient ensuite

D'après l'ordre du rapport de faisabilité, et rien n'a changé :

1. **Bio 2008-2025 et catastrophes naturelles par décennie** — données
   déjà en cache chez vous, maille communale, aucun risque réseau. C'est
   le lot qui éprouve la mécanique avant d'y ajouter des problèmes de
   source. Il demande d'étendre `16_bio.py` et `08_georisques.py` pour
   qu'ils publient leurs millésimes au lieu de n'en garder qu'un.
2. Débits mensuels — extension de `12_rivieres.py`, un paramètre à
   ajouter à un appel qui existe déjà.
3. Nappes mensuelles — extension de `09_nappes.py`, plus l'agrégation
   mensuelle à écrire.
4. Climat — `17_climat.py`, source nouvelle.
5. Population depuis 1876 — après inspection de la source.

Le lot 1 se prépare ici, il ne se termine pas : il lui faut vos fichiers
de cache, qui sont sur votre poste.
