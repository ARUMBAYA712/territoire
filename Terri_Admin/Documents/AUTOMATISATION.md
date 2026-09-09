# Automatisation des collectes — GitHub Actions

9 septembre 2026. **Quatre fichiers à poser dans `.github/workflows/`.**
Ils n'existaient pas : le dossier `.github` est absent du dépôt.

---

## Pourquoi maintenant

Trois rubriques se périment désormais toutes seules, et c'est voulu :

| Rubrique | Ce qui se passe si personne ne lance rien |
|---|---|
| **Carburants** | Un prix de plus de huit jours n'est pas publié. Au bout d'une semaine sans collecte, la page redevient une annonce vide et **sort du plan du site**. |
| Sécheresse | Les arrêtés changent en cours d'été sans prévenir |
| Vigilance météo | Plusieurs fois par jour, quand la clé sera là |

Le mécanisme qui retire une donnée périmée est une bonne chose — il vaut
mieux une page vide qu'un prix faux. Mais il transforme l'automatisation
d'un confort en une nécessité : **sans elle, la rubrique Carburants
disparaît du site huit jours après votre dernière exécution manuelle.**

---

## Les quatre plans

L'ordre des scripts n'est écrit nulle part dans ces fichiers : il vit
dans `lancer.py`, et chaque tâche se contente de l'appeler avec une
option. Un fichier de tâche planifiée qui énumérerait lui-même les
collecteurs finirait par diverger du lanceur sans que personne ne le
voie.

| Fichier | Quand | Ce qu'il collecte |
|---|---|---|
| `collecte-quotidienne.yml` | **deux fois par jour**, 5 h 15 et 15 h 15 UTC | sécheresse, vigilance, carburants |
| `collecte-hebdomadaire.yml` | **lundi** 4 h 30 UTC | nappes, débits |
| `collecte-mensuelle.yml` | **le 2 du mois**, 3 h UTC | eau potable, risques, écoles, arrêté hivernal, climat, autocars |
| `collecte-trimestrielle.yml` | **le 3 janvier, avril, juillet, octobre** | référentiel, population, élus, bio, gares, élections |

**Deux passages par jour pour les carburants**, pas davantage. Le flux se
rafraîchit toutes les dix minutes, mais régénérer sept cent soixante-quinze
pages aussi souvent n'aurait aucun sens : c'est l'horodatage affiché qui
fait la sincérité, pas la fréquence.

**Le 2 du mois et non le 1er** : les producteurs n'ont pas toujours fini
de publier le premier jour.

**Les heures sont en UTC**, comme l'exige GitHub. 5 h 15 UTC font 7 h 15
en heure d'été française, 6 h 15 en hiver. Les collectes tombent donc
avant que quiconque consulte le site.

---

## Ce que chaque tâche fait, et ne fait pas

**Elle ne valide rien quand rien n'a changé.** Une source qui n'a pas
bougé ne doit pas produire de commit ; l'historique du dépôt resterait
lisible.

**Elle se replace derrière vous.** Si vous avez poussé entre-temps, la
tâche se rebase plutôt que de refuser ou d'écraser.

**Elle ne se marche pas sur les pieds.** Les quatre plans partagent un
verrou : deux exécutions qui se chevaucheraient produiraient un conflit
de poussée. Le 2 janvier au matin, trois plans pourraient tomber à
quelques heures d'intervalle — ils s'attendront.

**Elle n'installe rien.** Les collecteurs n'emploient que la
bibliothèque standard de Python. C'est une contrainte que vous vous
êtes donnée au départ, et elle se paie ici : la tâche tient en quatre
étapes.

**Elle s'arrête si le lanceur bloque.** Un contrôle de version en défaut,
un collecteur qui refuse de publier : rien n'est validé, et vous recevez
un courriel d'échec.

---

## Trois choses à faire avant que cela tourne

### 1. Poser les fichiers et pousser

```
.github/workflows/collecte-quotidienne.yml
.github/workflows/collecte-hebdomadaire.yml
.github/workflows/collecte-mensuelle.yml
.github/workflows/collecte-trimestrielle.yml
```

Les tâches planifiées ne démarrent **que sur la branche par défaut**, et
seulement une fois le fichier poussé.

### 2. Autoriser les tâches à écrire dans le dépôt

Dans **Settings → Actions → General → Workflow permissions**, choisir
**Read and write permissions**. Sans cela, la collecte s'exécutera mais
la poussée sera refusée — et l'échec ne sera pas évident à lire.

### 3. Essayer à la main avant de faire confiance au calendrier

Onglet **Actions**, choisir « Collecte — sources quotidiennes », puis
**Run workflow**. C'est le seul moyen de voir la chaîne s'exécuter
ailleurs que chez vous, et le premier passage est celui qui révèle les
surprises.

---

## Le piège des soixante jours

**GitHub désactive les tâches planifiées d'un dépôt resté soixante jours
sans activité humaine — et il ne le signale pas.**

Les commits produits par la tâche elle-même **ne comptent pas** comme
activité : c'est précisément le cas d'un dépôt qui ne fait que collecter.
Le site cesserait donc de se mettre à jour au bout de deux mois, en
silence, et la rubrique Carburants se viderait huit jours plus tard.

Trois parades, de la plus simple à la plus lourde :

| Parade | Coût |
|---|---|
| Lancer une tâche à la main depuis l'onglet Actions, une fois tous les deux mois | Deux clics, mais il faut y penser |
| Pousser n'importe quel commit — une virgule dans un document suffit | Idem |
| Employer un jeton personnel au lieu du jeton intégré, pour que les commits comptent | Un secret à créer et à renouveler |

**Ma recommandation : la première**, avec un rappel dans votre agenda le
1er de chaque mois pair. C'est la seule qui n'introduit pas de secret à
gérer, et l'occasion de jeter un œil à la page « Fraîcheur des données »,
qui dirait de toute façon qu'une source a cessé d'être mise à jour.

C'est d'ailleurs le rôle de cette page : **elle est le témoin qui
survivrait à la panne.** Si les collectes s'arrêtent, elle le montre.

---

## La clé Météo-France

Le fichier `data/cle-meteofrance.json` est exclu du dépôt, à juste titre.
Les tâches savent le reconstituer à partir d'un secret :

**Settings → Secrets and variables → Actions → New repository secret**,
nommé `CLE_METEOFRANCE`, contenant le fichier JSON entier.

Tant que ce secret n'existe pas, l'étape est sautée et `14_vigilance.py`
s'arrête proprement en le disant. Rien ne casse.

---

## Ce que ces tâches ne feront jamais

**Elles ne déploient pas.** C'est le webhook OVH déjà en place qui
déploie, sur poussée. La chaîne est donc : GitHub Actions collecte et
valide → le webhook déploie. Rien à ajouter.

**Elles ne collectent pas le soir des élections.** Le jour venu, on
lancera à la main : un scrutin ne se traite pas au calendrier, et
l'embargo légal jusqu'à vingt heures interdit toute publication
automatique.

**Elles ne mettent pas en cache les gros fichiers.** L'archive INSEE de
198 Mo sera retéléchargée quatre fois par an, le GTFS de 30 Mo une fois
par mois. Un cache serait possible, mais il ajouterait de la mécanique
là où quelques minutes suffisent. À revoir seulement si les durées
deviennent gênantes.

---

## Durées attendues

Mesurées chez vous, augmentées d'une marge pour un runner partagé :

| Plan | Durée observée | Limite fixée |
|---|---|---|
| Quotidien | moins d'une minute | 20 min |
| Hebdomadaire | 3 minutes | 30 min |
| Mensuel | 10 à 20 minutes | 90 min |
| Trimestriel | 15 à 25 minutes | 180 min |

La variabilité vient presque entièrement de Hub'Eau, qui répond en 503
par vagues : `06_eau.py` a été mesuré à 1 min 34 s un jour et 10 min 36 s
le lendemain, sans rien changer de notre côté. Les limites sont larges
pour cette raison.
