# Séquence d'exécution — portail territorial

## Ordre

```
python 01_referentiel.py     # liste des communes (API Découpage administratif)
python 02_canton.py          # rattachement cantonal + réconciliation des périmètres
python 06_eau.py             # qualité de l'eau potable (Hub'Eau)
python 03_agregation.py      # agrégation + fichiers publiés en v1
python 05_cartes.py          # cartes SVG (contours mis en cache)
python 04_generation.py      # pages HTML, thème, plan du site
```

Les collecteurs spécialisés (`06`, et les suivants) passent **avant** `03`,
qui reprend tout fichier `data/mesures-*.json` qu'il trouve.

`04` doit toujours passer **après** `05`, pour intégrer les cartes aux pages.

## Ce que chaque script attend et produit

| Script | Attend | Produit |
|---|---|---|
| `01_referentiel.py` | rien | `data/referentiel-communes.json` et `.csv` |
| `02_canton.py` | le référentiel | référentiel enrichi du canton |
| `06_eau.py` | le référentiel | `data/mesures-eau.json` |
| `03_agregation.py` | référentiel + `mesures-*.json` | `data/publie/v1/**` |
| `05_cartes.py` | le référentiel | `data/contours.json`, `assets/cartes/**` |
| `04_generation.py` | `data/publie/v1/**` + cartes | pages HTML, `assets/`, `sitemap.xml`, `.htaccess` |

## Relances partielles

- Contours déjà téléchargés : `05` repart du cache. Pour forcer, supprimer `data/contours.json`.
- Communes en erreur dans `06` : relancer le script, seules les manquantes seront reprises.
- Après toute modification du thème ou du script, `04` recalcule l'empreinte des
  ressources ; les navigateurs rechargent d'eux-mêmes.

## Fichiers versionnés dans Git

À publier : `index.html`, `commune/`, `canton/`, `epci/`, `assets/`,
`data/publie/`, `sitemap.xml`, `robots.txt`, `.htaccess`, et les scripts.

Discutable : `data/contours.json` (volumineux) et `data/referentiel-communes.json`.
Ils se régénèrent, mais les conserver rend les exécutions reproductibles.

## Contrôles bloquants

Un script qui détecte une anomalie s'arrête **sans rien écrire** : le site
reste sur ses données précédentes plutôt que d'en publier de fausses.

- `01` : population, coordonnées, codes INSEE, noms en double
- `02` : cardinalité du canton, collisions de noms normalisés
- `03` : composition du canton, communes hors intercommunalité
- `04` : exhaustivité de la recherche, unicité des adresses
