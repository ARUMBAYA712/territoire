# Rubrique Prix des carburants, et automatisation des mises à jour

---

## 1. Ce que le travail sur Carbu apporte au portail

Votre cahier des charges contient l'essentiel du travail difficile, déjà tranché.
Trois acquis se transposent directement.

**La source et ses limites.** Le flux instantané de data.economie.gouv.fr, six
carburants publiés, un plafond de 100 résultats par requête, un rafraîchissement
toutes les dix minutes. Le schéma amont a connu au moins cinq évolutions de
format : le traitement doit rester tolérant et ne jamais échouer globalement sur
un enregistrement malformé. Cette règle vaut telle quelle côté portail.

**Les arbitrages déjà rendus.** Enseignes non normalisées, donc une catégorie
« sans enseigne » qui affiche son effectif plutôt qu'un rattachement erroné.
Date de publication toujours visible, signalement au-delà de trois jours. Ni GNR
ni fioul, faute de source par point de vente. Ces décisions n'ont pas à être
reprises.

**Le fond de carte.** Vous avez migré d'OpenStreetMap vers la Géoplateforme IGN
pour Carbu, exactement pour le motif qui m'a conduit au même choix hier soir.
Les deux produits partageront donc le même fond.

**Ce qui ne se transpose pas.** L'application interroge le flux en direct à
chaque ouverture. Le portail est un site statique : les prix seront ceux de la
dernière génération, avec leur horodatage affiché. Cette différence de nature
doit être dite au visiteur, pas masquée.

---

## 2. La rubrique proposée

**Placement.** Un onglet **Carburants** en bout de barre, à droite, comme vous
le souhaitez. Il aura sa propre adresse — `/commune/38416-saint-marcellin/carburants/` —
donc son titre, sa description et son entrée dans le plan du site. C'est ce qui
répond à votre objectif de référencement.

**Double rattachement.** La même donnée apparaîtra en résumé dans Transports,
avec un renvoi vers la page complète. Le mécanisme existe déjà : une mesure
déclare sa rubrique et sa sous-rubrique, rien n'empêche d'en publier une version
courte ailleurs.

### Contenu d'une page communale

| Élément | Détail |
|---|---|
| Tuiles | Prix du gazole et du sans-plomb 95 E10 les moins chers du secteur, nombre de stations, date du relevé |
| Carte | Stations en marqueurs, prix porté directement sur le marqueur |
| Tableau | Stations classées par prix, avec adresse, distance au centre du bourg et fraîcheur du relevé |
| Renvoi | Lien vers prix-carburants.gouv.fr pour signaler une erreur |

### Affichage du prix sur la carte : ma recommandation

Vous demandez comment afficher les prix — directement, au survol, ou au clic.

**Directement sur le marqueur**, comme dans Carbu. C'est votre meilleure trouvaille
de ce projet : le prix visible sans ouvrir de fiche, avec un code couleur par
tiers calculé sur les stations réellement chargées. Sur un territoire rural où
l'on compte une quinzaine de stations, aucun risque d'encombrement — le
regroupement en bulles que vous avez dû développer pour la ville sera inutile ici.

Le survol ajoutera le nom de la station et la date du relevé, comme il le fait
déjà pour les communes. Le clic ouvrira la fiche complète dans le tableau situé
sous la carte, en faisant défiler jusqu'à la ligne concernée — le mécanisme
d'ancrage est déjà en place.

**Le guidage relève du téléphone, pas du site.** Vous avez raison. Un bouton
« Y aller » ouvrant l'application de navigation installée n'a de sens que sur
mobile ; sur ordinateur, il n'apportera rien. Je propose un lien de coordonnées
qui fonctionne sur les deux, sans prétendre remplacer un GPS.

### Peut-on renvoyer vers l'application ?

Oui, et c'est même une bonne articulation : le portail traite un territoire et
ses données publiques, l'application traite la mobilité partout en France. Un
encart discret sur la page Carburants, une fois l'application publiée, servira
les deux. À condition de ne pas transformer le portail en support publicitaire :
un renvoi factuel, pas une bannière.

### Difficulté réelle

Moyenne. Le flux est simple, sans clé d'API. Le travail porte sur trois points :
la tolérance du traitement aux changements de format, le rattachement des
stations aux communes — elles sont géolocalisées, donc par point dans polygone,
mécanisme déjà écrit pour les cartes — et l'affichage des marqueurs, nouveau
mais proche de ce qui existe.

Comptez un collecteur et une évolution du générateur, soit l'équivalent du
travail sur Géorisques.

---

## 3. L'automatisation : CRON chez OVH

Votre question est la bonne, et la réponse comporte une réserve importante.

### La réserve

L'hébergement mutualisé OVH propose bien des tâches planifiées. Mais elles
exécutent des scripts **PHP**, et l'interpréteur **Python n'est pas disponible**
sur cet hébergement. Vos six collecteurs sont en Python.

Trois voies possibles, dans l'ordre où je les recommande.

### Voie 1 — GitHub Actions (recommandée)

Le traitement s'exécute chez GitHub selon un calendrier, produit les fichiers,
les enregistre dans le dépôt, et le déploiement vers OVH se déclenche par le
webhook déjà en place.

Avantages : votre Python fonctionne tel quel, aucune administration, un courriel
en cas d'échec, et l'exécution est tracée. Le quota gratuit d'un dépôt privé est
très largement suffisant pour quelques traitements par semaine.

C'est la voie que je maintiens.

### Voie 2 — CRON OVH avec réécriture en PHP

Techniquement possible, mais il faudrait réécrire les collecteurs. Vous perdriez
tout le travail fait, et vous auriez deux langages à maintenir. À écarter.

### Voie 3 — exécution manuelle, comme aujourd'hui

Reste viable plus longtemps qu'on ne le croit. Vos rythmes réels :

| Source | Fréquence | Automatisation utile ? |
|---|---|---|
| Référentiel des communes | Annuelle | Non |
| Population, logements, permis | Annuelle | Non |
| Risques et catastrophes | Trimestrielle | Marginale |
| Qualité de l'eau | Mensuelle | Marginale |
| Nappes | Hebdomadaire | Oui |
| Restrictions sécheresse | Quotidienne | Oui |
| **Prix des carburants** | **Toutes les 10 minutes à la source** | **Indispensable** |

Les carburants changent la donne. Une page affichant un prix vieux de trois jours
perd tout intérêt, et personne ne lancera un script tous les matins pendant deux
ans. C'est précisément ce sujet qui rendra l'automatisation nécessaire.

### Ma recommandation

Traiter l'automatisation **avant** les carburants, pas après. Concrètement :
mettre en place GitHub Actions sur les collecteurs existants — sécheresse tous
les jours, nappes chaque semaine, le reste chaque mois — puis ajouter les
carburants dans une chaîne qui tourne déjà.

Une cadence réaliste pour les carburants sur un site statique : deux à quatre
fois par jour. Le flux se rafraîchit toutes les dix minutes, mais régénérer le
site aussi souvent n'aurait aucun sens. L'important est d'afficher l'horodatage,
comme votre application le fait déjà.

---

## 4. Ordre proposé

1. **Vérifier l'hypothèse Python sur l'hébergement OVH** — un point à confirmer dans votre espace client, il conditionne le reste
2. **Mettre en place GitHub Actions** sur les collecteurs existants
3. **Développer le collecteur carburants** et la rubrique dédiée
4. **Ajouter le renvoi vers l'application** une fois celle-ci publiée

L'étape 1 se règle en dix minutes et évite de partir dans la mauvaise direction.
