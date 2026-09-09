# Livraison — la rubrique Élections

9 septembre 2026, huitième livraison. **Les fichiers sont posés dans
votre dépôt.**

| Fichier | Version | Ce qui change |
|---|---|---|
| `21_elections.py` | **nouveau, v1** | Participation et résultats par commune |
| `lancer.py` | — | Le collecteur entre au plan trimestriel |
| `ETAT-DU-PROJET.md` | — | **Remis à jour**, il était faux sur dix points |
| `CAHIER-DES-CHARGES.md` | — | Quatre exigences et cinq arbitrages versés |

Rien d'autre n'a bougé. Le générateur reste en 37.

---

## 1. Ce que la rubrique montrera

Quarante-neuf pages `Résultats` qui sortent enfin de l'annonce. Sur les
municipales de mars 2026, valeurs réelles relevées dans le fichier du
ministère :

| Commune | Inscrits | Participation |
|---|---|---|
| Saint-Marcellin | 5 390 | **58,57 %** |
| Rencurel | 285 | **57,54 %** |
| Vinay | 3 295 | **57,18 %** |

Trois communes que tout oppose par la taille, et trois chiffres à trois
points d'écart. C'est exactement le genre de fait qu'un habitant cherche
et que personne ne publie à cette échelle.

Sur chaque commune : la participation en tête, la liste arrivée en tête,
puis le détail — voix, pourcentage, nuance, tête de liste, sièges
obtenus. Au canton et à l'intercommunalité, **la participation est
recalculée sur les totaux**, jamais moyennée entre communes : sans quoi
un village de trois cents habitants pèserait autant que Saint-Marcellin.

---

## 2. Le problème de volume, et sa solution

Les fichiers communaux du ministère pèsent **124 Mo** pour les
européennes, 75 pour les législatives, 14 pour les municipales. Cinq
scrutins auraient représenté plus de deux cent cinquante mégaoctets à
chaque collecte, pour quarante-sept communes.

Ils sont triés par département, et data.gouv.fr accepte les requêtes
partielles. Le collecteur cherche donc les bornes du bloc de l'Isère
**par dichotomie**, en une quinzaine de sondes de quatre kilooctets, puis
lit le bloc d'un coup :

```
    début du département 38 : octet 30 538 102
    fin   du département 38 : octet 31 774 481
    taille du bloc          : 1,2 Mo — soit 1,6 % du fichier
```

**Ce procédé repose sur une hypothèse, et une hypothèse se vérifie.**
Après lecture, toutes les lignes du bloc doivent porter le département
attendu. Si un fichier était trié autrement un jour, le scrutin serait
**refusé avec son motif** plutôt que publié de travers. Un garde-fou
supplémentaire refuse un bloc de plus de dix mégaoctets : c'est le signe
que la dichotomie a échoué.

Ce qui **ne marche pas**, et qu'il ne faut pas essayer : l'API tabulaire
de data.gouv.fr. Interrogée sur le fichier des municipales, elle répond
que la ressource « a été définitivement supprimée par son producteur » —
alors qu'elle se télécharge. Ces fichiers, dont le nombre de colonnes
varie d'une ligne à l'autre, ne sont pas indexables par cet outil.

---

## 3. Deux niveaux de lecture, et pourquoi

Les fichiers ne se ressemblent pas d'un scrutin à l'autre : les
municipales parlent de « Nuance liste », les législatives de « Nuance
candidat », le nombre de colonnes va de 187 à plus de 300, et **le
guillemetage change** — les municipales encadrent chaque champ, les
législatives non. Un découpage naïf sur le point-virgule lirait `"38"` au
lieu de `38` sur la moitié des scrutins. Je m'y suis laissé prendre au
premier essai ; le module `csv` de la bibliothèque standard règle cela
sans un caractère de plus.

Mais **quatre colonnes sont identiques partout** : « Code commune »,
« Inscrits », « Votants », « Exprimés ». D'où la règle :

| | |
|---|---|
| **Participation** | lue sur **tous** les scrutins déclarés |
| **Détail des listes** | lu **seulement** sur les municipales, dont la forme est vérifiée colonne par colonne |

C'est moins ambitieux qu'une lecture universelle, et beaucoup plus sûr.
Cinq scrutins sont déclarés — présidentielle 2022, européennes 2024,
législatives 2024, municipales 2026 aux deux tours — et il en faut
quatre pour qu'une chronique de participation soit tracée. Les
**étiquettes libres** livrées en version 33 servent enfin : « Prés.
2022 », « Eur. 2024 », « Lég. 2024 », « Mun. 2026 » ne tombent pas à
intervalle régulier.

La chronique porte sa propre réserve : *« Les scrutins ne sont pas
comparables entre eux : une municipale et une européenne ne mobilisent
pas le même électorat. »*

---

## 4. Le piège de Rencurel

À Rencurel, la seule liste en présence a obtenu **100 % des suffrages
exprimés**. C'est exact, et publié tel quel ce serait trompeur — le genre
de chiffre juste qui raconte une histoire fausse, comme la tempête de
1982 sur les catastrophes naturelles.

Le collecteur compte les listes et écrit la réserve, deux fois : dans le
repère de la tuile — « 154 voix — 100,00 % · **liste unique** » — et dans
la note du bloc :

> Une seule liste était en présence : son pourcentage traduit l'absence
> de concurrence, non un plébiscite.

**Et une précaution qui n'est pas technique.** Les nuances politiques —
LDVC, LDVG, LDVD — sont des étiquettes attribuées par les services de
l'État au dépôt des candidatures, parfois contestées par les intéressés.
Elles sont publiées **en citant leur origine**, et rien n'en est déduit.
La note le dit sur chaque bloc.

C'est la seule rubrique du site dont je vous recommande de relire
vous-même les textes générés avant la mise en ligne.

---

## 5. Éprouvé sur quoi, et ce qui reste incertain

Le collecteur a été rejoué sur un fichier reconstruit à l'identique du
format réel — en-tête des municipales 2026 relevé colonne par colonne,
guillemetage compris, avec les **valeurs réelles** de Saint-Marcellin,
Vinay et Rencurel, et une commune de la Drôme glissée dedans pour
vérifier le filtre. Résultat : 47 communes sur 47, Romans écartée,
participation cantonale recalculée à 58,16 %, chronique rendue avec ses
étiquettes libres, graphique dessiné.

**Ce qui n'a pas pu l'être** : la dichotomie sur le vrai fichier. Mon
environnement n'atteint pas data.gouv.fr — les mesures de la section 2
ont été faites à travers votre navigateur, pas par le script. C'est la
même limite que pour les autocars, et elle se lèvera de la même façon :
en regardant la sortie de la première collecte réelle.

**Ce qu'il faut regarder à ce moment-là**, dans l'ordre :

```
    ressource : Municipales 2026 - Résultats - Communes_…csv  (14 Mo)
    17 sonde(s), 47 commune(s) retrouvée(s) sur 47
```

Si le nombre de sondes dépasse la trentaine, ou si le nombre de communes
retrouvées est bas, la dichotomie a mal tourné et il ne faut rien
publier. Si un scrutin s'écarte avec un motif, c'est le filet qui joue
son rôle — envoyez-moi la ligne.

---

## 6. Les deux documents remis à jour

**`ETAT-DU-PROJET.md` était devenu faux**, et c'est le document qu'on lit
en premier pour reprendre le travail. Il annonçait le générateur en
version 24 quand il est en 37, ignorait cinq collecteurs, parlait de
480 pages quand il y en a 775, demandait de supprimer un fichier qui
n'existe pas, et donnait l'arrêté hivernal comme expirant en 2026 alors
qu'il court jusqu'en 2027. Il est réécrit, avec les chiffres de
référence des 8 et 9 septembre et les leçons accumulées.

**`CAHIER-DES-CHARGES.md`** reçoit quatre exigences — EF-44 à EF-47 — et
cinq arbitrages. Les plus structurants :

| Exigence | |
|---|---|
| **EF-44** | Afficher les licences réellement présentes dans la collecte. Aucune licence écrite en dur dans une page. |
| **EF-46** | Ne publier un nom ou un rattachement issu d'un rapprochement géométrique que sous un seuil de distance vérifié. |
| **EF-47** | Quand une donnée manque pour trancher, inventorier et le dire, plutôt que supposer. |

Ces trois-là ne sont pas des règles de style : chacune est née d'une
erreur commise cette semaine.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | `21_elections.py` annonce la **version 1** ; `lancer.py` attend 21 scripts |
| 2 | `python 21_elections.py --scrutins` liste cinq scrutins |
| 3 | Chaque scrutin imprime le **titre de la ressource retenue** — vérifiez qu'il parle bien de communes |
| 4 | « 47 commune(s) retrouvée(s) sur 47 » sur les municipales ; moins sur les scrutins anciens est normal si une commune a fusionné |
| 5 | Participation du canton autour de **58 %** aux municipales 2026 |
| 6 | Sur `/commune/38333-rencurel/elections/resultats/`, la mention **« liste unique »** apparaît deux fois |
| 7 | Une chronique de participation apparaît dès **quatre scrutins** lus |
| 8 | Le plan du site gagne 49 adresses : plus aucune page « en attente » |
