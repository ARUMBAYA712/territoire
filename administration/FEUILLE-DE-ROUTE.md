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

## Palier 4 — carburants

Traité à part : c'est le seul sujet où vous disposez déjà d'un travail abouti.

Voir le document dédié.

---

## Ordre recommandé

1. **Population détaillée** — remplit une rubrique déjà ouverte, source connue
2. **Carburants** — voir document dédié, forte valeur d'usage
3. **Parc de logements et permis de construire** — ouvre la rubrique Urbanisme
4. **Équipements publics** — alimente Santé, Éducation, Culture d'un coup
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
