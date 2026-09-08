# Livraison — `04_generation.py` version 31

8 septembre 2026, seconde livraison de la journée. À poser **après** la
version 30, dont elle reprend tout.

Deux chantiers, faits dans cet ordre : le mécanisme qui débloque les
cours d'eau et les carburants, puis le référencement.

**Un seul fichier change** : `04_generation.py`. Plus une ligne dans
`lancer.py`, qui attend désormais la version 31.

```
python lancer.py --site
```

Aucune collecte à relancer. Trois secondes.

---

## 1. Une donnée dans deux rubriques

C'était le préalable annoncé dans `DEMANDES-2026-09-08.md` : tant qu'il
n'existait pas, les cours d'eau et les carburants attendaient derrière
lui. Il est écrit.

### La règle

Vous aviez raison sur le fond — on ne sait pas par quel chemin le
visiteur arrive. Mais dupliquer la tuile aurait créé deux vérités à
tenir à jour, et deux pages du même site se disputant le même mot-clé.

La règle retenue : **le détail vit dans une seule rubrique**, celle que
la mesure déclare. Ailleurs, elle laisse un **écho** — son nom, sa
valeur, sa source, et un lien qui nomme sa destination : « Voir dans
Rivières », pas « Voir le détail ». Le lecteur sait qu'il change de
rubrique ; un moteur apprend quelque chose du lien.

Visuellement, l'écho se distingue : fond en creux, bordure pointillée,
valeur en teinte sourde. Il se lit comme un renvoi, pas comme une
donnée de la page.

### Trois garde-fous, qui sont l'essentiel

**Un écho ne rend jamais une rubrique active.** Une rubrique qui n'aurait
que des échos n'aurait rien à elle : elle n'apparaîtrait ni dans la
navigation ni au plan du site. C'est ce qui empêche le mécanisme de
fabriquer des pages creuses — exactement le risque que nous refusons
partout ailleurs.

**Un écho n'est écrit que si la page visée existe pour ce territoire.**
Une commune sans station hydrométrique n'aura pas d'écho renvoyant vers
une page qui n'a pas été produite. Le contrôle se fait fiche par fiche,
comme celui des renvois « Voir le détail ».

**Un écho ne remonte jamais sur l'Aperçu**, ne colore jamais la carte, ne
compte pas dans la description de la page, et ne prend pas le bandeau de
tête même si la mesure est mise en avant sur sa propre page. La mise en
avant est une revendication de place, et elle ne vaut que là où la
donnée est traitée. Le ton, lui, est conservé : une eau non conforme
reste non conforme vue depuis la géographie.

### Ce que le collecteur écrit

Une ligne sur la mesure, rien d'autre :

```python
"aussi": {"rubrique": "transports"}
"aussi": {"rubrique": "environnement", "sous_rubrique": "rivieres"}
"aussi": "transports"          # forme abrégée, sans sous-rubrique
```

La rubrique de détail reste celle que la mesure déclare, ou celle que
son préfixe désigne — un collecteur n'a pas à déclarer sa rubrique juste
pour pouvoir faire un écho ailleurs.

### Éprouvé sur six cas

Un jeu d'essai a été construit pour couvrir ce qui pouvait mal tourner :

| Cas | Attendu | Résultat |
|---|---|---|
| Écho vers une rubrique | Tuile d'écho, lien nommé | ✓ |
| Écho vers une sous-rubrique précise | Lien vers la sous-rubrique, pas la rubrique | ✓ |
| Écho depuis une mesure mise en avant | Bandeau perdu, ton conservé | ✓ |
| Écho vers une rubrique inactive ici | Rien, silencieusement | ✓ |
| Écho vers sa propre rubrique | Rien — ce serait un lien sur soi-même | ✓ |
| Mesure sans valeur | Rien | ✓ |

Et le contrôle qui compte le plus : **sur des données sans aucun `aussi`
déclaré, les pages produites sont identiques au caractère près à celles
de la version 30.** Le mécanisme ne coûte rien tant que personne ne s'en
sert.

### Ce que cela débloque

- **Cours d'eau** : détail dans Géographie, écho dans Environnement.
- **Carburants** : détail dans la rubrique Carburants, écho dans
  Transports — l'arbitrage rendu dans la note Carbu.

---

## 2. Référencement

### Données structurées

Trois déclarations en JSON-LD, et pas une de plus. Chacune correspond à
quelque chose que la page montre réellement — des données structurées
qui décrivent autre chose que le contenu visible sont une faute au sens
des consignes de Google, et la sanction est le retrait des
enrichissements, sans avertissement.

| Déclaration | Où | Ce qu'elle apporte |
|---|---|---|
| `BreadcrumbList` | Toutes les pages de territoire | Le fil d'ariane remplace l'adresse sous le résultat de recherche. C'est la seule à produire un effet visible, et elle sert surtout sur les adresses profondes — les nôtres le sont |
| `City` / `AdministrativeArea` | Toutes les pages de territoire | Rattache la page à une entité connue : nom, code officiel, code postal, ce qui la contient, et pour un canton la liste de ses communes |
| `Dataset` | Page d'accueil de chaque territoire | Le fichier JSON téléchargeable, sa licence, son auteur, sa date. C'est la déclaration qui permet à un moteur de données de le référencer |
| `WebSite` + `ItemList` | Accueil du site | Le site, et les 49 territoires en une lecture |

Trois choix qui méritent d'être dits :

- **Le `Dataset` n'est porté que par la page d'accueil du territoire**,
  celle qui offre effectivement le fichier. Le déclarer sur les quinze
  pages d'une commune annoncerait quinze jeux de données là où il n'y en
  a qu'un.
- **Le code d'une intercommunalité est déclaré comme un SIREN**, pas
  comme un code INSEE. Les confondre dans une donnée destinée aux
  machines serait pire que de ne rien déclarer.
- **Pas de `SearchAction`.** La boîte de recherche du site est un filtre
  exécuté dans le navigateur, sans adresse de résultat. Déclarer un
  gabarit d'URL qui ne mène nulle part obtiendrait peut-être la boîte de
  recherche dans Google, et sûrement un lien mort le jour où quelqu'un
  s'en sert.

Les thèmes annoncés dans le `Dataset` sont ceux que le fichier contient
réellement, calculés fiche par fiche : une description de catalogue qui
promet ce qui n'y est pas est exactement ce que ce site s'interdit
ailleurs.

### Plan des titres

Un défaut de fond, corrigé.

Les titres de section — « Rattachements », « Carte », le titre de chaque
bloc détaillé — étaient écrits en `span`. Pour un moteur comme pour un
lecteur d'écran, ils n'existaient pas : le plan d'une page de commune se
réduisait à une quinzaine de titres de même niveau, les noms des tuiles,
sans rien qui les regroupe.

Désormais :

- **h1** — le titre de la page ;
- **h2** — les sections : rattachements, indicateurs, blocs, carte ;
- **h3** — les tuiles et les items de bloc.

Quatre pages n'avaient **aucun titre de premier niveau** : mentions
légales, fraîcheur, 404, administration. Leur titre était un `h2` sans
rien au-dessus. C'est réparé.

La grille de tuiles reçoit un titre écrit mais masqué à l'œil — « et
masqué à l'œil seulement » : c'est le même contenu pour tout le monde,
pas du texte réservé aux moteurs. Sans lui, un lecteur d'écran ne peut
pas sauter la grille.

**Contrôle** : chaque page produite a exactement un `h1`, aucun saut de
niveau, et toutes les balises de titre équilibrées. Vérifié
automatiquement sur les 27 pages du jeu d'essai.

### Aperçus de partage

`og:site_name`, `og:locale`, `twitter:card`, `twitter:title`,
`twitter:description` sur toutes les pages. Ces balises sont lues par
plus de monde que leur nom ne le laisse croire : Slack, Signal et
plusieurs messageries s'en servent.

Et un correctif : `og:title` annonçait « Saint-Marcellin — Sud Grésiv' »
sur les quinze pages d'une commune. Il annonce maintenant le sujet de la
page — « Saint-Marcellin — Population ».

### L'image de partage : le seul point que je ne peux pas faire

Il y a dans `04_generation.py` un réglage `IMAGE_PARTAGE`, vide. Rempli,
il produit les balises d'aperçu sur toutes les pages. Laissé vide,
aucune balise n'est écrite — mieux vaut pas d'image qu'une image
absente, qui ferait afficher un cadre gris.

**Pourquoi le fichier n'est pas produit ici.** Les cartes du site sont
des SVG, et aucun des réseaux concernés ne sait afficher un SVG en
aperçu. Il faudrait une image matricielle portant du texte, ce
qu'aucune bibliothèque standard de Python ne sait dessiner — et ajouter
un moteur de rendu contredirait la règle qui tient ce projet depuis le
début.

C'est donc un fichier à faire à la main, une fois : **1200 × 630
pixels**, PNG ou JPEG sous 1 Mo, le nom du site lisible en grand, et
rien d'important dans les 60 pixels du bord, les vignettes étant
recadrées. Posez-le dans `assets/`, écrivez son chemin dans
`IMAGE_PARTAGE`, et les 727 pages le porteront.

### Descriptions vides

Une page dont le contenu tient en blocs détaillés, sans valeur chiffrée,
produisait `« Chatte (commune) : . Données publiques INSEE et IGN. »`.
Un moteur rejette une description mal formée et en fabrique une
lui-même. Elle nomme désormais son sujet.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | Le run annonce la **version 31** |
| 2 | Le nombre de pages et d'adresses au sitemap est **inchangé** : 727 et 727. Le mécanisme d'écho ne crée aucune page |
| 3 | Sur une page de commune, le code source contient un bloc `application/ld+json` — trois objets sur la page d'accueil du territoire, deux sur une page de rubrique |
| 4 | `/mentions-legales/`, `/fraicheur/` et la page 404 ont leur titre à la même place et à la même taille qu'avant. Le seul écart visible : l'interligne du titre est resserré, ce qui remonte le contenu de six pixels — un titre n'a pas à porter l'interligne du corps de texte |
| 5 | Les tuiles ont exactement le même aspect qu'avant |
| 6 | Test de Google pour les résultats enrichis (`search.google.com/test/rich-results`) sur `/commune/38416-saint-marcellin/` : le fil d'ariane et le jeu de données sont reconnus, sans erreur |

Le point 6 est le seul qui demande le réseau, et il ne peut se faire
qu'une fois le site déployé.

---

## Ce que cette livraison ne fait pas

- **L'image de partage** : le fichier est à fournir, le code l'attend.
- **Le texte d'explication autour des données**, que vous avez noté pour
  plus tard. C'est le levier de référencement le plus fort qui reste, et
  le plus long : il demande de générer des phrases à partir des valeurs
  réelles, sans jamais écrire une phrase fausse quand la donnée manque.
- **Les cours d'eau et les carburants** eux-mêmes : le mécanisme est
  prêt, les collecteurs restent à écrire, et tous deux demandent une
  inspection de source depuis votre poste.
