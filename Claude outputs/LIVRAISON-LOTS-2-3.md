# Livraison — lots 2 et 3 : débits et nappes mensuels

8 septembre 2026, cinquième livraison. **Les fichiers sont posés dans
votre dépôt.**

| Fichier | Version | Ce qui change |
|---|---|---|
| `12_rivieres.py` | 5 → **6** | Débits moyens mensuels, deux filets de contrôle, et l'interrogation **par station** |
| `09_nappes.py` | 2 → **3** | Chronique complète du piézomètre, agrégée au mois |
| `08_georisques.py` | 11 → **11** *(retouche)* | Une note quand une décennie est dominée par un événement unique |
| `lancer.py` | — | Versions attendues |

Aucune modification du générateur : ces collecteurs se contentent
d'écrire des chroniques au format livré en version 32.

```
python lancer.py --tout
```

---

## 1. Ce que j'ai trouvé en vérifiant, et qui change tout

Le rapport de faisabilité recommandait de publier la série la plus
longue. **C'était un mauvais critère, et j'ai dû le corriger deux fois
dans la même journée.**

La station EDF de la Bourne à Saint-Just-de-Claix annonce 708 valeurs
mensuelles depuis janvier 1967. Vérification faite, valeur par valeur :

| Mois | Valeur servie | Qualification |
|---|---|---|
| janvier 1967 | 947 L/s — 0,9 m³/s | **Non qualifiée** |
| janvier 1990 | 1 542 L/s | Bonne |
| janvier 2020 | 8 536 L/s | Bonne |

Les valeurs anciennes sont **dix fois trop faibles**, régulièrement.
Ce n'est pas de l'hydrologie : c'est une rupture d'échelle dans
l'archive. Tracées telles quelles, elles auraient dessiné une hausse
spectaculaire du débit de la Bourne depuis cinquante ans — une
impression fausse appuyée sur des données vraies, et cette fois dans un
graphique produit par nous.

**Un troisième piège au passage** : le même site porte deux stations
simultanées, EDF et DREAL. En janvier 2003, l'une annonce 0,9 m³/s et
l'autre **20,5 m³/s** pour la même rivière au même endroit. Le
collecteur interrogeait les observations **par site**, ce qui les
mélangeait. **Vous avez tranché pour la station, et c'est fait** — voir
la section 5.

---

## 2. Les deux filets, dans `12_rivieres.py`

**Le premier vient de la source.** Chaque valeur porte une
qualification. Les mois « Non qualifiée » sont écartés : le producteur
n'a pas expertisé la valeur, ce n'est pas à nous de le faire à sa place.

**Le second ne vient de personne.** La médiane des cinq premières
années est comparée à celle des cinq dernières. Au-delà d'un rapport de
trois, la série entière est refusée, et le motif est écrit dans la
sortie du script :

```
    [écartée] W334000101 — médiane 1.22 m³/s au début contre 13.58 à la
              fin, soit un rapport de 11 — rupture d'échelle, pas une
              tendance
```

Le second existe parce que le premier repose sur un champ que le
producteur remplit — et qu'un champ peut être rempli à tort.

**Éprouvé sur cinq cas** : série à rupture d'échelle (refusée), même
série amputée de sa partie non qualifiée (acceptée), série trop courte
(refusée), série lacuneuse (trous conservés, non interpolés), et
arbitrage entre deux stations (la saine l'emporte).

Une seule station porte les graphiques — la plus longue des séries
saines. En publier plusieurs multiplierait les courbes sans ajouter de
sens : le visiteur n'a pas à arbitrer entre deux stations dont il
ignore tout.

**Si la station retenue est sur une rivière aménagée** — l'Isère, la
Romanche, le Drac — la réserve est écrite sur le graphique : le débit
mesuré traduit autant la gestion des ouvrages que la pluie et la fonte
des neiges. La courbe décrit la rivière telle qu'elle coule, non le
climat du bassin.

---

## 3. Trois décisions dans `09_nappes.py`

Hub'Eau ne calcule pas de moyenne mensuelle pour les nappes, à la
différence des débits : c'est à nous de regrouper. Trois choix, et
chacun change ce que la courbe raconte.

**On trace le niveau, pas la profondeur.** Le piézomètre publie les
deux. La tuile de la fiche affiche la profondeur, qui parle à tout le
monde — « l'eau est à 41 mètres ». Mais sur une courbe elle s'inverse :
elle monte quand la nappe baisse. Un lecteur qui voit un trait monter
comprend « plus d'eau ». On trace donc l'altitude, où monter veut dire
monter. Si la station ne publie que la profondeur, on la trace, et la
note dit dans quel sens la lire.

**La médiane, pas la moyenne.** Un relevé aberrant — purge, pompage
d'essai — déplace la moyenne d'un mois entier. La médiane l'ignore.

**Le seuil de représentativité s'adapte à la station.** Un mois n'est
retenu que s'il porte assez de relevés — mais « assez » ne peut pas
être un nombre fixe : une sonde mesure tous les jours, un piézomètre
ancien est relevé à la main une fois par mois. Exiger trois relevés
partout jetterait toutes les chroniques anciennes. Le seuil vaut donc
un quart de la cadence habituelle de la station, plafonné à trois.

Éprouvé sur quatre cadences — quotidienne, mensuelle, irrégulière, et
quotidienne avec quelques mois presque vides : dans les trois premiers
cas les 250 mois sont conservés et seule la panne de capteur de
quatorze mois fait un trou ; dans le dernier, les mois à un seul relevé
deviennent des trous, ce qui est le comportement voulu.

**La station de la chronique n'est pas forcément celle des
indicateurs.** Un indicateur se lit sur la station la plus **proche** et
la plus fraîche : c'est ce qui compte pour dire où en est la nappe
aujourd'hui. Une chronique se lit sur la plus **ancienne** : c'est ce
qui compte pour montrer une évolution. À profondeur comparable — dix
pour cent près — la plus proche l'emporte. Le graphique nomme sa
station.

---

## 4. Ce que la sortie du script vous dira

Les deux collecteurs écrivent ce qu'ils ont retenu et ce qu'ils ont
écarté. C'est le seul moyen de savoir ce qui sera publié :

```
  Chroniques mensuelles :
    W320001001    684 mois qualifiés 1969-2026
    W334000101    440 mois qualifiés 1990-2026  (268 écarté(s), non qualifiés)
    [écartée] …
    → série retenue : Hub'Eau — hydrométrie … · station W320001001 · 1969-2026
```

Les chiffres ci-dessus sont une illustration, pas une prévision : le
décompte réel ne se connaîtra qu'à la première collecte.

---

## 5. Le passage à la station, et ce qu'il entraîne

Les débits journaliers sont désormais demandés **par station**, comme
les chroniques. Deux conséquences, à connaître avant de regarder le
site :

**La valeur affichée peut changer.** L'indicateur « Débit : proche des
valeurs habituelles » se calculait sur un mélange de deux stations
lorsqu'un site en portait deux. Il se calcule maintenant sur une seule,
nommée. Si le chiffre bouge, ce n'est pas une régression.

**Le dédoublonnage a dû changer de règle.** Tant que l'on interrogeait
le site, ne garder qu'une station par site allait de soi : elles
renvoyaient la même chronique, et la plus proche faisait l'affaire.
Ce n'est plus vrai. Deux stations au même endroit ont la même distance :
« la plus proche » les départageait au hasard. Le script en conserve
donc **deux par site**, les interroge, et retient celle qui est la
mieux fournie — la densité réelle des mesures est le seul signal
disponible pour distinguer la station de référence du dispositif d'un
exploitant.

---

## 6. Une retouche à `08_georisques.py`

Vos données publiées ont révélé un piège de lecture. Sur le canton, les
arrêtés par décennie donnent :

```
    1980s  98   ·   1990s  34   ·   2000s  27   ·   2010s  12   ·   2020-26  15
```

Lu tel quel, cela raconte une forte baisse des catastrophes naturelles
depuis quarante ans. C'est faux : la tempête de novembre 1982 a été
reconnue le même jour pour presque toutes les communes de France, et le
dispositif venait d'être créé. Une décennie entière est portée par un
épisode unique.

Le collecteur le détecte désormais tout seul : quand **une seule date
fait plus du tiers** des arrêtés d'une période, elle est nommée sous le
graphique. Aucune valeur n'est retirée — c'est la lecture qui est
cadrée, pas la donnée qui est corrigée.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | `12_rivieres.py` annonce la **version 6**, `09_nappes.py` la **version 3** |
| 2 | Chaque collecteur imprime un bloc « Chroniques mensuelles » avec, station par station, le nombre de mois retenus et écartés |
| 3 | Au moins une station est **écartée** avec son motif — c'est le signe que les filets fonctionnent, pas qu'il y a un problème |
| 4 | Sur `/canton/…/environnement/rivieres/`, deux graphiques : l'année en cours sur fond d'historique, puis la chronique entière |
| 5 | Sur `/canton/…/environnement/nappes/`, les deux mêmes formes, en m NGF |
| 6 | Si la station retenue est sur l'Isère, la réserve « rivière fortement aménagée » est écrite sous le graphique |
| 7 | Les collectes sont plus longues : une requête de plus par station, soit une douzaine au total |
| 8 | Sur le canton, la note du graphique des arrêtés nomme l'événement de novembre 1982 |
| 9 | L'indicateur « Débit » peut afficher une autre valeur qu'avant : c'est attendu |

---
