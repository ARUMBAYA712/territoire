# Livraison — la rubrique Carburants, et le générateur en version 35

8 septembre 2026, sixième livraison — révisée le 9 après trois collectes réelles. **Les fichiers sont posés dans
votre dépôt.**

| Fichier | Version | Ce qui change |
|---|---|---|
| `18_carburants.py` | **nouveau, v3** | Prix des carburants, commune par commune |
| `04_generation.py` | 33 → **35** | Les pages « en préparation » sortent du plan du site |
| `lancer.py` | — | Le collecteur entre au plan quotidien |

```
python lancer.py --tout
```

---

## 1. La version 34 : ce que vous aviez arbitré

Quatre-vingt-dix-huit adresses vides — carburants et résultats
électoraux sur quarante-neuf territoires — représentaient un huitième
du plan du site. Elles restent **en ligne et atteignables depuis la
navigation** : un lecteur qui suit le menu lit l'annonce, apprend ce
qui vient et pourquoi ce n'est pas encore là. Mais elles ne sont plus
proposées aux moteurs : hors du `sitemap.xml`, et porteuses d'une
balise `noindex, follow`.

**`follow` et non `nofollow`** : la page reste un chemin vers les
autres. C'est son contenu qui n'est pas prêt, pas ses liens.

Le mécanisme est le miroir exact de celui qui décide déjà qu'une
rubrique existe : **une page revient au plan du site dès qu'elle porte
un indicateur chiffré, un bloc ou une chronique.** Il n'y a rien à
décommenter le jour venu, et donc rien à oublier. La sortie du script
le dit à chaque exécution :

```
  Plan du site    : sitemap.xml (73 adresses)
  En attente      : 10 page(s) hors plan du site et en noindex, faute de donnée —
                    carburants (5)
                    elections/resultats (5)
                    Elles y reviendront seules à la première mesure publiée.
```

**Éprouvé par comparaison octet à octet** entre une génération en
version 33 et la même en version 34, sur vos fiches publiées : sur les
soixante-dix-huit pages produites, **seules les dix pages d'annonce
diffèrent**, et d'une seule ligne — la balise `robots`. Aucune autre
page n'a bougé.

Et la démonstration s'est faite toute seule dans la foulée : une fois
les mesures carburants injectées, **les cinq pages carburants sont
rentrées d'elles-mêmes** dans le plan du site, qui est passé de 73 à
78 adresses. Il ne restait plus en attente que `elections/resultats`.

---

## 2. Le collecteur carburants — la question décisive est tranchée

Je vous avais annoncé que le point dur ne serait pas l'affichage des
prix mais **le rattachement d'une station à une commune**. Il est
réglé, et pas par un calcul de notre part.

Le flux instantané, qui porte les prix les plus frais, **n'a pas de
code INSEE**. Le jeu quotidien en a un — `com_arm_code` — mais il est
en retard d'un jour et porte des lignes en double. Ma recommandation
d'hier était de calculer nous-mêmes le rattachement par point dans
polygone.

**C'était la mauvaise réponse.** Une clause `group_by` sur
l'identifiant de station efface les doublons **dans la requête
elle-même**, et le jeu quotidien rend alors, en un seul appel, la
table exacte des treize stations avec leur code INSEE :

```
  26190001 → 26311 Saint-Laurent-en-Royans
  38160002 → 38095 Chatte
  38470003 → 38559 Vinay
  …
```

Le producteur dit lui-même où sont ses stations. Nous n'avons pas à le
faire à sa place, et un calcul géométrique de plus aurait été une
occasion d'erreur de plus. **Deux requêtes suffisent** : le
rattachement d'un côté, les prix de l'autre.

Le calcul géométrique n'a pas disparu pour autant — il a changé de
rôle. Il ne produit plus rien : **il contrôle**. Si une station est
déclarée dans une commune mais située très loin de son centre, les
deux sources se contredisent, et la station est écartée avec son
motif. Le seuil n'est pas un nombre choisi au hasard : il vaut trois
fois le rayon du disque de même surface que la commune, avec un
plancher de six kilomètres. Sur Rencurel, la plus étendue après
Saint-Antoine, cela fait dix kilomètres.

---

## 3. Ce que la rubrique montrera, sur vos données du 8 septembre

Collecte réelle, relevée à travers votre navigateur, rejouée
intégralement dans la chaîne :

| | |
|---|---|
| Stations dans l'emprise de collecte | 97 |
| **Sur le territoire** | **5**, sur 5 communes |
| Retenues aux alentours | 88, dont **10 villes réellement citées** |
| Écartées | 4 — aucun relevé de moins de huit jours |
| **Communes servies** | **47 sur 47** |

La seconde station de Vinay — 2,219 €/L, la moins chère du territoire —
est écartée depuis le 9 septembre : le distributeur n'a rien redéclaré
depuis le 31 août. C'est le seuil de huit jours qui joue son rôle.

Ce dernier chiffre est le plus important, et il n'allait pas de soi.
Cinq communes ont une station ; les quarante-deux autres reçoivent
**la station la plus proche, nommée, avec sa distance et son prix** :

```
  L'Albenc     → Vinay, à 4 km — gazole 2,259 €/L, relevé il y a 4 jours
  Rencurel     → Saint-Martin-en-Vercors, à 11 km — 2,267 €/L
```

Savoir où est la pompe la plus proche est exactement ce qu'un habitant
d'un village cherche, et c'est la seule page du site où **l'absence de
la chose vaut d'être écrite**. La rubrique n'a donc pas cinq pages
utiles sur quarante-neuf : elle en a quarante-neuf.

En tête du canton :

| Indicateur | Valeur |
|---|---|
| Gazole le moins cher | **2,256 €/L** — Chatte, relevé aujourd'hui |
| Écart entre stations du territoire | **0,063 €/L** — de Chatte à Saint-Marcellin, 3 € sur un plein de 50 litres |
| Stations sur le territoire | 5 |

**Le chiffre mis en avant est celui du territoire, jamais celui d'une
voisine.** Une page du Sud Grésivaudan qui annoncerait en tête le prix
d'une station de la Drôme ne parlerait plus de son territoire. Les
voisines figurent dans le tableau, sous la mention « hors territoire »,
et une seule mesure leur est consacrée — quand l'une d'elles est
nettement moins chère, ce qui est précisément l'information qu'aucune
page nationale ne donne, faute de raisonner par territoire.

**Le mécanisme d'écho a servi pour la première fois.** Sur
`/commune/38416-saint-marcellin/transports/`, la tuile apparaît en fin
de page avec son renvoi « Voir dans Carburants ». Livré en version 31,
il n'avait encore rien à porter.

---

## 4. Quatre filets, et ce qu'ils ont attrapé à l'essai

Chacun a été éprouvé sur une collecte réelle volontairement abîmée.

**Un prix hors des bornes du plausible est écarté**, et surtout : il
est **dit**. En divisant tous les gazoles par dix — la panne exacte de
la Bourne — le script publie quand même les autres carburants, mais
écrit :

```
  [ATTENTION] 13 prix hors des bornes du plausible, écarté(s) :
    Vinay — Gazole : 0.2219 hors des bornes 0.3–5.0 €/L
    …
    Si la liste est longue, la source a probablement changé
    d'unité : vérifiez avant de publier.
```

Un relevé trop vieux, lui, est une situation ordinaire et ne déclenche
aucune alarme. Un prix hors bornes ne l'est jamais.

**Un relevé de plus de huit jours n'est pas publié.** Entre trois et
huit jours, il l'est, mais sa date est écrite en toutes lettres à côté
du prix. C'est votre règle du cahier des charges Carbu, et elle sert
dès la première collecte : la station la moins chère de Vinay affiche
un gazole du 31 août, qui n'est donc pas publié — alors que son GPLc
du 1er septembre l'est.

**Une contradiction entre les deux sources écarte la station.** En
déclarant la station de Chatte à Rencurel :

```
  [écartée] Chatte — rattachée à Rencurel mais située à 14 km de son
            centre, pour un seuil de 10 km — les deux sources se
            contredisent
```

**S'il ne reste rien, le fichier est écrit vide.** Ne rien écrire
laisserait en place la collecte précédente, et le site continuerait
d'afficher les prix de la semaine dernière sans le dire. C'est le même
choix que pour l'arrêté hivernal périmé.

---

## 5. Trois décisions que j'ai prises, et que vous pouvez défaire

Elles sont groupées en tête du fichier, sous « Réglages arbitrables ».

**Les aires d'autoroute ne comptent pas dans la comparaison.** Les deux
aires de l'A49 relevées le 8 septembre affichaient jusqu'à dix-sept
centimes de plus que la station la moins chère du territoire. Les
inclure ferait dire à la page « le plein le moins cher est ici » sur
une comparaison faussée. Elles restent listées, en fin de tableau, avec
leur situation écrite. Elles sont également exclues du calcul de la
station la plus proche : à vol d'oiseau elle peut être toute proche, et
inaccessible sans dix kilomètres jusqu'à l'échangeur.

**Ce qui s'affiche est décidé page par page, et non par un rayon
unique.** C'est le point sur lequel je me suis trompé d'abord, et la
première collecte réelle l'a montré sans appel : une marge de dix
kilomètres autour du territoire ramenait quarante-neuf stations, dont
quarante-trois extérieures — Voiron, Moirans, Échirolles,
Romans-sur-Isère. La raison est géométrique : **votre territoire est
une bande étroite**, et un rectangle autour de lui attrape deux
agglomérations qui ne sont proches d'aucune de ses communes. La page du
canton se serait mise à parler de Grenoble.

| Page | Ce qu'elle montre |
|---|---|
| **Canton, intercommunalité** | **uniquement les stations du territoire** — la comparaison entre elles *est* le sujet |
| **Commune** | les siennes, puis les **trois plus proches à moins de 15 km**, avec leur distance |

Chaque page répond ainsi à sa propre question : « qu'est-ce que le
carburant coûte ici » pour le canton, « où vais-je faire le plein »
depuis un village. Sur la collecte du 9 septembre, les voisines citées
sont toutes des voisines réelles — distances de 1 à 12 km, médiane 7 —
et aucune station de Grenoble, de Voiron ni de Romans n'apparaît nulle
part.

**Tullins figure sur vingt-huit des quarante-sept pages.** Ce n'est pas
un défaut de réglage, c'est un fait sur le territoire : la moitié nord
— Vatilieu, Quincieu, Cras, Chantesse, Morette, Têche — n'a aucune
station, et c'est vers Tullins qu'elle se tourne. La rubrique le dit
sans le commenter.

**Le collecteur entre au plan quotidien.** Les prix se périment en
jours ; si ce plan cesse de tourner, la rubrique **se vide d'elle-même**
plutôt que d'afficher des prix faux. C'est ce qui rend la rubrique
publiable avant même que GitHub Actions ne soit en place : au pire, elle
retourne à sa page d'annonce, et sort du plan du site toute seule.

---

## 6. Ce qui reste ouvert

**L'historique des prix.** Aucun des deux jeux ne publie de série. Le
seul moyen d'en avoir une est de constituer la nôtre, en conservant à
chaque collecte la valeur du jour. C'est peu de chose techniquement —
quelques kilooctets par mois, et le mécanisme de graphique livré en
version 32 l'accueillerait sans une ligne de plus. Mais c'est une
décision, pas un réglage : nous deviendrions **producteur** d'une
donnée, avec ce que cela suppose de continuité. Une série interrompue
six mois est pire que pas de série.

Votre remarque tenait : sur cinq stations, l'intérêt d'un historique
est mince. Il grandit si l'on y ajoute les voisines les plus citées.

**Deux points de la fiche du jeu de données restent à lire** : la
licence exacte, et la stabilité des identifiants de station dans le
temps — cette dernière conditionne tout historique que nous
constituerions.

---

## 7. L'erreur qui vaut d'être écrite

La première collecte réelle a publié « aucune station dans l'emprise »
sur un territoire qui en compte cinq. La cause : **l'API Explore attend
`in_bbox(champ, lat_min, lon_min, lat_max, lon_max)` — la latitude
d'abord.** Je l'avais écrite longitude d'abord. Le filtre reste
syntaxiquement valable, la requête répond `200`, et elle renvoie zéro
ligne.

Deux enseignements, et le second est le plus utile :

- **une requête qui réussit n'est pas une requête juste.** Le
  collecteur traitait déjà « zéro station » différemment de « la source
  n'a pas répondu », et c'est ce qui a rendu la panne lisible en une
  ligne au lieu de passer pour une absence de stations ;
- **un banc d'essai qui rejoue une collecte enregistrée ne teste pas la
  collecte.** Les quatre filets avaient été éprouvés sur des données
  réelles, mais la requête qui va les chercher ne l'avait jamais été.
  C'est la limite de la méthode, et elle vaut pour tous les collecteurs
  à venir.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | `04_generation.py` annonce la **version 35**, `18_carburants.py` la **version 3** |
| 2 | Le collecteur imprime les stations retenues **et** les écartées avec leur motif |
| 3 | « Communes servies : 47 sur 47 » — si le chiffre est plus bas, une commune n'a pas trouvé de station proche |
| 3 bis | « Stations du territoire » n'est **pas zéro** — sinon la collecte a échoué et il ne faut rien publier |
| 4 | Le plan du site compte **726 adresses** : les 49 pages carburants y sont, pleines |
| 5 | Il reste 49 pages en attente : `elections/resultats`, jusqu'en octobre |
| 6 | Sur `/canton/…/carburants/`, **seules** les stations du territoire figurent |
| 7 | Sur `/commune/38416-saint-marcellin/transports/`, une tuile « Gazole » renvoie « Voir dans Carburants » |
| 8 | Sur une commune sans station — L'Albenc, Rencurel — la tuile nomme la station la plus proche et sa distance |
| 9 | Aucun `[ATTENTION] … hors des bornes` : s'il y en a, la source a changé quelque chose |
