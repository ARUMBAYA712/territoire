# Transports en commun — instruction de la source

9 septembre 2026. **Rapport de faisabilité. Aucun code écrit, rien
d'installé dans votre dépôt.**

Réponse courte : **oui, et c'est probablement la donnée la mieux
documentée qui manque encore au site.** Deux sources, toutes deux
vérifiées ce soir requête par requête. Mais il y a **un point de
licence à trancher avant d'écrire une ligne**, et il ne se rattrape pas
après coup.

---

## 1. Le train — quatre gares, et dix ans de fréquentation

La ligne Valence–Grenoble traverse le territoire. Relevé dans la
*Liste des gares* de SNCF Réseau, quarante-cinq gares voyageurs en
Isère, dont **quatre chez vous** :

| Gare | Commune |
|---|---|
| Saint-Marcellin | Saint-Marcellin |
| Vinay | Vinay |
| Saint-Hilaire – Saint-Nazaire | Saint-Hilaire-du-Rosier |
| Poliénas | Poliénas |

Les gares voisines immédiates sont Tullins-Fures, Moirans et Voreppe.

**Et il existe une série de fréquentation annuelle, 2015-2024, gare par
gare.** C'est elle qui fait l'intérêt de la rubrique :

| Gare | 2015 | 2024 | Évolution |
|---|---|---|---|
| Saint-Marcellin | 479 187 | **601 317** | +25 % |
| Vinay | 123 108 | **206 591** | **+68 %** |
| Saint-Hilaire – Saint-Nazaire | 57 959 | **110 057** | **+90 %** |

Le creux de 2020 est net et parlant — 346 192 à Saint-Marcellin — et
le retour au-dessus du niveau de 2019 se lit en deux ans. **La
fréquentation des deux haltes a presque doublé en dix ans.** Ce fait
n'est publié nulle part à l'échelle du territoire, et il se range
directement dans le mécanisme de chroniques livré en version 32 :
forme `barres`, pas annuel, dix valeurs.

**Poliénas n'apparaît pas dans le fichier de fréquentation.** La gare
figure comme « voyageurs » au référentiel mais n'a aucun compte. À
vérifier avant de l'afficher : une gare listée sans desserte réelle
serait une information fausse pour la commune.

---

## 2. Le car — Cars Région Isère, en GTFS

Publié sur transport.data.gouv.fr, format GTFS, mis à jour le
9 septembre 2026 :

| | |
|---|---|
| Réseau | REGION — cars Région Isère |
| Lignes | **495** |
| Arrêts | **9 392** |
| Courses | **3 643** |
| Validité du service | 20 août 2026 → **31 août 2027** |
| Poids | **30 Mo** compressés |

Trois voisins utiles au besoin : **cars Région Drôme** (18 Mo, pour le
Royans), **Transports du Pays Voironnais**, et les **navettes
saisonnières Transaltitude** qui desservent les stations du Vercors —
donc potentiellement Rencurel, Presles et Villard-de-Lans.

Le GTFS donne tout ce qu'il faut : les arrêts avec leurs coordonnées,
les lignes qui les desservent, et **le nombre de passages par jour**,
calculable en croisant les horaires et le calendrier de service. Sur un
territoire rural, « combien de cars par jour » est une information que
personne ne publie commune par commune et que tout le monde cherche.

Trente mégaoctets par collecte, c'est l'ordre de grandeur du fichier de
l'Agence Bio. Le fichier n'accepte **pas** les requêtes partielles — il
faut le télécharger entier — mais la nouvelle règle du `.gitignore`
couvre déjà `data/cache-*`, et une collecte mensuelle suffirait : le
service est fixé jusqu'en août 2027.

---

## 3. Le point à trancher : la licence n'est pas la vôtre

**C'est le point important de ce rapport.**

Toutes les sources de transport — Cars Région Isère, SNCF, Voironnais,
Drôme — sont publiées sous **ODbL**, et non sous Licence Ouverte 2.0
comme les onze sources actuelles du site.

Ce n'est pas une nuance de forme. L'ODbL est une licence *de base de
données* qui, en substance, impose deux choses là où la Licence Ouverte
n'en impose qu'une :

- **l'attribution**, comme la Licence Ouverte ;
- et le **partage à l'identique** : une base dérivée que l'on publie
  doit l'être sous ODbL.

Or votre site publie ses données brutes en téléchargement, et son
pied de page annonce « Licence Ouverte 2.0 » sur toutes les pages. Un
fichier `data/publie/v1/commune/38416.json` qui contiendrait des
horaires de cars serait une base dérivée d'une base ODbL, annoncée sous
une licence qui n'est pas la sienne.

Trois façons d'en sortir, par ordre de préférence :

**a) Publier les données de transport sous ODbL, et le dire.** Le
contrat de données porte déjà une licence *par mesure* — le champ
`licence` existe dans chaque mesure produite par les collecteurs. Il
suffit qu'il vaille « ODbL 1.0 » pour ces mesures-là, et que la page de
téléchargement et les mentions légales distinguent les deux régimes.
C'est honnête, c'est exact, et cela ne coûte que du texte.

**b) N'afficher que des faits, sans republier la base.** « Quatre cars
par jour à Chantesse » est un résultat, pas une base de données.
La frontière existe mais elle est floue, et je ne suis pas en mesure de
vous dire où elle passe exactement.

**c) Ne pas prendre les cars, et ne garder que le train.** Les données
SNCF sont elles aussi en ODbL — cela ne règle donc rien.

**Je recommande (a), et je vous recommande de le faire confirmer.** Je
ne suis pas juriste, et ce paragraphe décrit ce que les licences
disent, non ce qu'un conseil vous dirait. Mais le sujet mérite dix
minutes avant d'écrire le collecteur, pas après : changer la licence
affichée d'un site déjà indexé est plus coûteux que la choisir au
départ.

---

## 4. Ce que la rubrique montrerait

**Sur une commune desservie :**

- les arrêts de car, et les lignes qui y passent ;
- **le nombre de passages un jour de semaine** — le chiffre qui
  résume tout ;
- la gare, s'il y en a une, avec sa fréquentation annuelle ;
- sinon la gare la plus proche et sa distance, exactement comme la
  rubrique Carburants nomme la station la plus proche.

**Sur une commune non desservie** — et il y en aura : dire qu'aucune
ligne régulière ne dessert la commune est une information, et c'est la
même règle que pour les carburants. Le site est peut-être le seul
endroit où elle serait écrite.

**Au canton et à l'intercommunalité :** le nombre de communes
desservies, le nombre de lignes, et **la chronique de fréquentation des
gares** — la série la plus parlante du lot.

---

## 5. Cinq pièges repérés

**Le transport scolaire.** Une partie des 495 lignes sont des services
scolaires. Les compter comme des cars « ouverts à tous » gonflerait la
desserte d'un facteur deux ou trois sur les petites communes. Le GTFS
ne les distingue pas toujours explicitement — c'est le premier point à
instruire dans le collecteur, et c'est là que se joue la sincérité de
la rubrique.

**Le calendrier de service.** Un GTFS décrit des périodes. Compter
« les passages » sans choisir un jour de référence — un mardi de
période scolaire, par exemple — donnerait un chiffre qui ne veut rien
dire. Le jour retenu devra être écrit sur la page.

**Le rattachement d'un arrêt à une commune.** Le GTFS donne des
coordonnées, pas de code INSEE. C'est exactement le problème des
stations-service, mais cette fois sans jeu de secours pour nous donner
la réponse : il faudra du point-dans-polygone, avec `contours.json`.

**Un nom de champ qui casse le motif.** Dans le fichier de
fréquentation SNCF, toutes les colonnes s'appellent
`total_voyageurs_2015`, `total_voyageurs_2016`… sauf une :
`totalvoyageurs2017`, sans les tirets bas. Un collecteur qui
construirait les noms de colonnes par formule perdrait 2017 en
silence — un trou au milieu de la chronique.

**Voyageurs et non-voyageurs.** Le fichier donne deux totaux :
les voyageurs, et les voyageurs *plus* les accompagnants estimés. Pour
Saint-Marcellin, 601 317 contre 751 646. Il faut choisir le premier et
le dire, sans quoi le chiffre publié sera 25 % au-dessus de la réalité.

---

## 6. Estimation

| Étape | Charge |
|---|---|
| Gares et fréquentation SNCF | **légère** — deux requêtes API, données minuscules, chronique immédiate |
| Lecture du GTFS et desserte par commune | l'essentiel du travail |
| Rattachement des arrêts aux communes | moyen, le mécanisme existe pour les cartes |
| Distinction scolaire / régulier | le point délicat, et il est éditorial autant que technique |

**Ma recommandation : couper en deux.** Le train seul est un collecteur
d'une demi-journée qui apporte tout de suite quatre gares et une
chronique de dix ans sur trois d'entre elles. Le car est un chantier
comparable au collecteur carburants, et il vient après.

Cela vous donnerait une rubrique Transports qui a du contenu dès la
semaine prochaine, sans retarder les carburants ni les élections.

---

## Ce que je n'ai pas vérifié

- **Le contenu réel du GTFS** : mon environnement n'a pas accès à
  data.gouv.fr, et je n'ai pu lire que les métadonnées publiées par
  transport.data.gouv.fr. Le nombre de lignes desservant réellement vos
  communes reste donc inconnu.
- **Si la halte de Poliénas est desservie** aujourd'hui.
- **La part exacte du scolaire** dans les 495 lignes.
- **Le poids du GTFS national SNCF**, que je n'ai pas pu interroger.
