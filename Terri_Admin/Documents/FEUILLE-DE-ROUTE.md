# Feuille de route — données à ajouter

Classement par difficulté croissante. La difficulté tient à trois choses :
la qualité de la source, la maille disponible, et le travail d'interprétation
nécessaire pour que la donnée veuille dire quelque chose.

---

## Palier 1 — sources nationales, maille communale, API simple

Chacune se traite en un collecteur sur le modèle de ceux déjà en place.

| # | Donnée | Source | Rubrique | Difficulté |
|---|---|---|---|---|
| 1 | **Population détaillée** (âge, sexe, ménages, familles) | INSEE, recensement | Population | Facile |
| 2 | **Parc de logements** (vacance, résidences secondaires) | INSEE, recensement | Urbanisme | Facile |
| 3 | **Permis de construire** | Sitadel | Urbanisme | Facile |
| 4 | **Équipements publics** (commerces, santé, sport, école) | INSEE, base permanente | Plusieurs | Facile |
| 5 | **Mutations immobilières** (prix médian, volumes) | DGFiP, DVF | Urbanisme | Moyenne |
| 6 | **Diagnostics de performance énergétique** | ADEME | Urbanisme | Moyenne |
| 7 | **Espaces naturels protégés** (Natura 2000, ZNIEFF, PNR) | INPN | Environnement | Moyenne |
| 7b | **Espèces protégées présentes sur le territoire** | INPN, occurrences par commune | Environnement | Moyenne à difficile |
| 8 | **Établissements scolaires** | Annuaire de l'éducation | Éducation | Facile |
| 9 | **Obligation d'équipements hivernaux** | Arrêté préfectoral, à vérifier sur data.gouv.fr | Transports et fiche commune | Facile |

Les quatre premières partagent une caractéristique précieuse : un seul fichier
national, aucune limite de débit, aucune reprise à gérer. Ce sont les moins
risquées et celles qui remplissent le plus vite les rubriques encore vides.

---

## Palier 2 — maille station, à ramener à une vision large

Même schéma que les nappes : rattachement au canton, station de référence
nommée, distance affichée.

| # | Donnée | Source | Rubrique |
|---|---|---|---|
| 9 | **Débit des rivières** (Isère, Bourne, Vernaison) | Hub'Eau hydrométrie | Environnement / Rivières |
| 10 | **Qualité des cours d'eau** | Hub'Eau qualité rivières | Environnement / Rivières |
| 11 | **Prélèvements en eau** | BNPE | Environnement / Eau |
| 12 | **Normales et projections climatiques** | Météo-France | Météo & climat |

Le débit d'étiage estival est, avec la sécheresse, l'indicateur le plus parlant
de cette famille sur votre territoire.

---

## Palier 3 — sources exigeant un traitement particulier

### 12b. Espèces protégées — un sujet à fort attrait, une source fragile

L'INPN publie les occurrences d'espèces observées commune par commune, avec
leur statut de protection. C'est la seule source nationale sérieuse, et elle
permettrait d'afficher la faune et la flore remarquables du territoire —
un angle qu'aucun portail de données local ne propose.

Trois difficultés à connaître avant de s'y engager.

**La source est actuellement hors service.** Les serveurs du Muséum national
d'histoire naturelle ont subi une attaque informatique, pour une durée
indéterminée. Rien ne peut être construit tant qu'ils ne sont pas rétablis.

**La donnée d'observation n'est pas une donnée de présence.** Une commune sans
observation n'est pas une commune sans espèces : elle peut simplement n'avoir
jamais été prospectée. Afficher « 3 espèces protégées » à côté de « 47 » dans
la commune voisine induirait en erreur. Il faudra présenter cela comme un
inventaire d'observations, jamais comme un recensement.

**Certaines localisations sont volontairement floutées.** Les stations
d'espèces sensibles — orchidées rares, rapaces nicheurs — sont diffusées à
une maille dégradée précisément pour éviter le pillage. Il ne faudra ni
chercher à les préciser, ni les cartographier finement.

Sous ces réserves, le sujet a un vrai potentiel : c'est le genre de contenu
qu'on consulte par curiosité et qu'on partage.

### 13. Prix de l'eau et performance du service — **à ne pas construire sur Hub'Eau**

Point critique découvert en préparant votre demande : **l'API Hub'Eau
« Indicateurs des services » est en cours de décommissionnement, avec un arrêt
annoncé au 10 septembre 2026.** Les producteurs invitent à récupérer les données
directement sur le site SISPEA.

Conséquence : la voie normale passe désormais par le **téléchargement des jeux
de données SISPEA**, qui publient la composition communale des services année
par année, ainsi que les indicateurs de prix et de performance. C'est un
traitement par fichiers, pas par API : téléchargement périodique, jointure
commune → service → indicateurs.

Ce que l'on pourra afficher : prix du mètre cube toutes taxes, rendement du
réseau, nombre d'habitants desservis, nom du service et de son opérateur.

Difficulté réelle : la maille est le **service**, pas la commune. Plusieurs
communes partagent un service, et une commune peut relever de deux services
selon la compétence — eau potable d'un côté, assainissement de l'autre. Le
schéma des réseaux d'eau potable, déjà en place, servira de modèle.

À noter aussi : seuls les services de plus de 3 500 habitants ont l'obligation
de publier. Sur un territoire de petites communes, la couverture sera partielle.

### 14. Assainissement et stations d'épuration

Même source et même difficulté de maille. À traiter avec le prix de l'eau.

### 15. Élections

Le chantier le plus lourd, et le plus différenciant. Modèle de données distinct,
maille bureau de vote, un connecteur par scrutin. Analysé en détail dans
l'onglet « Résultats électoraux » du catalogue.

Calendrier favorable : présidentielle en avril 2027, départementales en mars
2028. En commençant par la présidentielle 2022, format récent et propre, la
chaîne sera rodée bien avant.

---

## Palier 3 bis — le territoire rural

Quatre sujets propres à un territoire rural, classés du plus simple au plus
exigeant. Trois d'entre eux reposent sur des arrêtés préfectoraux, ce qui
introduit une catégorie nouvelle : voir la section « Référentiels saisis à la
main » plus bas.

### A. Obligation d'équipements hivernaux — le meilleur rapport effort/valeur

Depuis la loi Montagne, certaines communes imposent pneus hiver ou chaînes du
1er novembre au 31 mars. La liste est fixée par arrêté préfectoral et publiée ;
plusieurs communes du Vercors sont concernées.

C'est un simple oui/non par commune, avec une période d'application. Il tient
en une tuile sur la fiche communale, et se répète dans la future rubrique
Transports. Utile, sans ambiguïté, et à faible risque d'erreur.

**Difficulté : faible.** À vérifier : existence d'un jeu national sur
data.gouv.fr, sinon saisie depuis l'arrêté départemental.

### B. Cultures, sylviculture et élevage

Deux sources possibles, très différentes.

Le **recensement agricole** d'Agreste publie par commune le nombre
d'exploitations, la surface agricole utilisée, l'orientation dominante et le
cheptel. Données riches, mais le secret statistique masque beaucoup de petites
communes — sur un territoire comme le vôtre, ce sera fréquent.

Le **registre parcellaire graphique** recense les parcelles déclarées par les
agriculteurs, avec leur culture, chaque année. Il permettrait d'afficher les
surfaces par type de culture, voire une carte. Mais ce sont des fichiers
géographiques lourds à traiter, par région.

**Difficulté : moyenne pour Agreste, élevée pour le parcellaire.**
Je commencerais par Agreste, en assumant les communes masquées.

### C. Dates de chasse

Fixées chaque année par arrêté préfectoral, avec des dates différentes selon
l'espèce et parfois selon la zone. Aucune source lisible par une machine :
c'est un document, pas un jeu de données.

**Difficulté : faible techniquement, mais engageante.** Une date erronée peut
conduire quelqu'un à commettre une infraction. Si ce sujet est retenu, la
fiche devra citer l'arrêté, sa date, un lien vers le document, et préciser
qu'il fait seul foi.

### D. Cueillette — champignons et plantes

Le sujet le plus délicat des quatre, et le plus recherché.

Trois réglementations se superposent : les arrêtés préfectoraux qui limitent
les quantités, le code forestier qui subordonne la cueillette à l'accord du
propriétaire, et les listes d'espèces protégées dont le ramassage est interdit.
S'y ajoutent, chez vous, les règles propres au parc naturel régional du Vercors.

**Difficulté : moyenne techniquement, élevée en responsabilité.** Indiquer
qu'une cueillette est permise alors qu'elle ne l'est pas expose le lecteur.
Je ne traiterais ce sujet qu'en citant chaque règle avec sa source, et sans
jamais formuler d'autorisation — seulement rappeler ce que dit le texte.

À noter : ce sujet ne dit rien de la comestibilité. Il ne faudra en aucun cas
laisser croire qu'il aide à identifier un champignon.

---

## Référentiels saisis à la main

Ces quatre sujets, sauf le parcellaire, introduisent une catégorie que le
projet n'a pas encore : des données **transcrites depuis un document officiel**
plutôt que collectées par un programme.

Elles imposent des règles propres, à poser avant le premier de ces sujets :

- **Citer le texte source** — nature, date, autorité — sur la fiche même.
- **Publier un lien vers le document**, qui fait seul référence.
- **Dater la saisie** et afficher cette date au visiteur.
- **Prévoir une péremption** : un arrêté annuel doit être signalé comme
  périmé passé sa date de validité, plutôt que d'être affiché indéfiniment.
- **Faire figurer ces référentiels dans la section d'administration**, avec
  leur échéance, au même titre que les collectes automatiques.

Sans ces règles, ces données vieilliraient en silence — exactement le risque
contre lequel tout le reste du projet a été construit.

## Palier 4 — carburants

Traité à part : c'est le seul sujet où vous disposez déjà d'un travail abouti.

Voir le document dédié.

---

## Ordre recommandé

1. **Population détaillée** — remplit une rubrique déjà ouverte, source connue
2. **Carburants** — voir document dédié, forte valeur d'usage
3. **Parc de logements et permis de construire** — ouvre la rubrique Urbanisme
4. **Équipements publics** — alimente Santé, Éducation, Culture d'un coup
4 bis. **Équipements hivernaux obligatoires** — une tuile, forte valeur d'usage
5. **Débits de rivière** — complète Environnement, schéma déjà éprouvé
6. **Mutations immobilières** — très consultée, un peu plus technique
7. **Prix de l'eau** — après clarification de la voie SISPEA
8. **Élections** — chantier long, à démarrer une fois le reste stabilisé

---

## Deux règles qui se dégagent de ce qui a été fait

**Une donnée sans repère ne vaut rien.** Une profondeur de nappe, une dureté de
l'eau, un taux de conformité : chacun a demandé une échelle de lecture ou une
comparaison. C'est ce travail-là, plus que la collecte, qui prend du temps —
et c'est lui qui distingue votre portail d'un affichage brut.

**Chaque source apporte son piège de maille.** Réseaux d'eau, stations
piézométriques, services SISPEA, bureaux de vote : aucun ne suit les limites
administratives. Le mécanisme de rattachement par territoire, mis en place pour
les nappes, resservira à chaque fois.
