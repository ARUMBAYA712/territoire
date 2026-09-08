# Carburants — inspection du flux, enfin faite

8 septembre 2026.

Cette inspection était en suspens depuis le premier jour : le conteneur
qui exécute mes traitements n'a jamais eu d'accès sortant vers
`data.economie.gouv.fr`. Elle a pu être menée ce soir à travers votre
navigateur. **Tout ce qui suit est vérifié, requête par requête.**

---

## 1. Deux jeux de données, et non un seul

Le portail n'en publie que deux sur le sujet, et ils ne servent pas à
la même chose.

| | `prix-des-carburants-en-france-flux-instantane-v2` | `prix-carburants-quotidien` |
|---|---|---|
| Stations | **9 805** en France | 76 489 lignes |
| Forme | une ligne par station, un champ par carburant | une ligne par station **et par carburant** |
| Code commune | **absent** | **`com_arm_code`**, code INSEE |
| Intercommunalité | absente | `epci_name` |
| Géométrie | `geom` en longitude/latitude propres | présente aussi |
| Fraîcheur | la plus récente | **environ un jour de retard** |

Le retard du second est mesuré, pas supposé : à Chatte, le gazole y
vaut 2,267 € relevé le 7 septembre à 9 h 31, quand le flux instantané
donne 2,256 € relevé le 8 à 9 h 40.

**Et il porte des doublons.** À Saint-Marcellin, la ligne « Gazole »
apparaît trois fois, à l'identique. Un collecteur qui compterait les
lignes annoncerait trois stations là où il n'y en a qu'une.

---

## 2. Ce qu'il y a réellement sur le territoire

Requête sur le flux instantané, dans un rayon de 18 km autour de
Saint-Marcellin : **13 stations**, dont **six sur des communes du
canton**.

| Commune | Gazole | E10 | Dernier relevé |
|---|---|---|---|
| Vinay | 2,219 € | 1,990 € | 31 août |
| Chatte | 2,256 € | 2,080 € | 8 septembre |
| Saint-Sauveur | 2,256 € | 2,080 € | 8 septembre |
| Vinay | 2,259 € | 2,079 € | 4 septembre |
| Saint-Just-de-Claix | 2,267 € | 2,129 € | 7 septembre |
| Saint-Marcellin | 2,319 € | 2,139 € | 7 septembre |

Les sept autres sont dans la Drôme ou sur le plateau du Vercors —
Saint-Jean-en-Royans, Eymeux, La Baume-d'Hostun, Autrans-Méaudre,
Saint-Martin-en-Vercors.

**Trois faits qui font le contenu de la rubrique** :

**L'écart local atteint dix centimes** entre Vinay et Saint-Marcellin,
et dix-sept si l'on inclut La Baume-d'Hostun à 2,394 €. Sur un plein de
cinquante litres, cela fait cinq euros. C'est exactement le genre de
fait qu'aucun média local ne publie et qu'un habitant cherche.

**La fraîcheur est très inégale** : de quelques heures à huit jours
selon la station. La règle de votre cahier des charges Carbu —
signaler au-delà de trois jours — n'est pas une précaution théorique,
elle se déclenchera dès la première collecte.

**Le plafond de cent résultats par requête ne nous concerne pas.** Il
gênait l'application, qui balaie la France ; ici, un filtre de distance
ramène treize lignes en une seule requête. Cette réserve du cahier des
charges Carbu peut être rayée pour le portail.

---

## 3. Rattacher une station à une commune : ma recommandation

Le flux instantané n'a pas de code INSEE ; le jeu quotidien en a un.
Ce n'est pas une raison suffisante pour préférer le second.

**Je recommande le flux instantané, avec un rattachement par point dans
polygone.** Trois raisons :

- **la fraîcheur est tout le sujet.** Publier des prix vieux d'un jour
  de plus, sur un site déjà statique, ajoute un retard à un retard ;
- le mécanisme de point dans polygone **existe déjà** dans le projet,
  écrit pour les stations hydrométriques et les contours communaux ;
- le jeu quotidien porte des doublons visibles, et rien ne dit qu'ils
  soient les seuls.

**Mais le jeu quotidien a un usage, et il est précieux** : servir de
contrôle. À la première collecte, comparer le rattachement calculé par
géométrie au `com_arm_code` publié. S'ils divergent sur une station, il
faut regarder pourquoi avant de publier. C'est gratuit, et cela ferme
la seule vraie inconnue de ce collecteur.

---

## 4. Ce que le flux donne, et qui n'était pas prévu

Le flux instantané porte plus que des prix :

- `carburants_indisponibles` et `carburants_rupture_definitive` — une
  station qui ne vend plus de SP95 depuis 2022 le dit, avec la date.
  Afficher « pas de gazole ici » vaut parfois autant qu'un prix ;
- `horaires`, et `horaires_automate_24_24` — la station est-elle
  accessible la nuit ;
- `services` — toilettes, gonflage, DAB, station de lavage ;
- `pop` — « R » pour route, « A » pour autoroute.

Ces champs coûtent zéro requête de plus. Sur un territoire rural,
« ouvert 24 h/24 » et « ne vend plus de GPL » sont des informations
utiles, et aucune application de prix ne les met en avant.

---

## 5. Ce qui reste à trancher avant d'écrire le collecteur

**Un historique des prix est-il possible ?** Aucun des deux jeux ne
publie de série. Le seul moyen d'en avoir un est de **constituer le
nôtre**, en conservant à chaque collecte la valeur du jour. C'est
faisable — un fichier par mois, quelques kilooctets — mais c'est une
décision : cela crée une donnée dont nous devenons producteur, avec ce
que cela suppose de continuité. Le mécanisme de graphique livré
aujourd'hui l'accueillerait sans une ligne de plus.

**Quelle cadence ?** Le flux se rafraîchit toutes les dix minutes. Sur
un site statique, deux à quatre publications par jour suffisent, et
c'est l'horodatage affiché qui fait la sincérité, pas la fréquence.

**Quel rayon ?** Dix-huit kilomètres ramènent treize stations, dont
sept hors territoire. Trop peu de stations sur le seul canton — six —
pour que la page soit utile sans les voisines ; trop de voisines et la
page ne parle plus du territoire. À mon avis : toutes les stations des
communes du territoire, plus les extérieures à moins de dix kilomètres
d'une commune, clairement distinguées.

---

## Ce que je n'ai pas vérifié

- La **licence exacte** du jeu et les conditions de réutilisation.
- Le comportement du flux **en cas de station nouvelle ou fermée** :
  le champ `fermeture` existe, je ne l'ai vu rempli que sur un
  enregistrement de 2009.
- La **stabilité des identifiants** de station dans le temps, qui
  conditionne tout historique que nous constituerions nous-mêmes.

Ces trois points se règlent en une collecte réelle et une lecture de la
fiche du jeu de données.
