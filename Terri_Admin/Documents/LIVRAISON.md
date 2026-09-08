# Livraison du 8 septembre 2026

Mentions légales, consultation de la documentation, agriculture
biologique débloquée, pages d'annonce pour l'indexation.

---

## Fichiers à installer — quatre

| Fichier | Version | Nature |
|---|---|---|
| `04_generation.py` | 23 → **29** | Mentions, documents, pages d'annonce, administration allégée, page de fraîcheur, rattachements repliables |
| `16_bio.py` | 1 → **3** | Choix du fichier source, puis lecture du code commune |
| `lancer.py` | mis à jour | Versions attendues et plan de livraison |
| `.gitignore` | mis à jour | Caches volumineux exclus du dépôt |

`15_elus.py` version 2 est déjà chez vous : c'est vous qui me l'avez
envoyé. Le contrôle de versions passe désormais au vert sur les seize
scripts.

---

## Ce qui change

### Mentions légales

`MENTIONS` est renseigné : éditeur, statut, adresse, contact, directeur
de la publication, hébergeur. La page `/mentions-legales/` est donc
produite, et le rappel à l'exécution disparaît. **Le premier des trois
bloquants avant communication publique est levé.**

Le SIRET est laissé vide plutôt qu'à `-` : la ligne n'est alors pas
produite du tout, ce qui vaut mieux qu'un tiret dont le lecteur ne sait
que faire. Renseignez-le si vous vous immatriculez un jour.

### Agriculture biologique — le bon fichier

`16_bio.py` s'arrêtait sur « Colonne de code commune introuvable ». Le
diagnostic était trompeur : le fichier lu était celui des **cheptels**,
non celui des surfaces.

Le jeu de données de l'Agence Bio publie cinq fichiers communaux, tous
intitulés « de 2008 à 2024 ». La règle « retenir le titre au millésime le
plus élevé » les départageait au hasard de leur ordre, et les cheptels
l'emportaient — 47 Mo téléchargés pour rien, puis un blocage.

Le choix est désormais explicite : le titre doit contenir « surface », et
les mentions « cheptel », « opérateur » et « production » l'écartent. La
dernière exclusion vise le fichier « surfaces de production », 465 Mo,
qui porte un autre niveau de détail. Éprouvé sur les cinq titres réels :
c'est bien le fichier des surfaces, 41 Mo, qui est retenu.

Trois conséquences pratiques :

- **Le cache porte l'empreinte du fichier retenu.** Un cache unique
  aurait fait relire les cheptels sans nouveau téléchargement. Supprimez
  `data/cache-bio.csv`, hérité de la version précédente : il n'est plus
  lu.
- **`--fichier <fragment>`** force un autre fichier du jeu, le jour où
  l'Agence Bio renommera ses publications.
- **Le titre retenu s'affiche en entier**, avec son format et son poids.
  C'est en le voyant tronqué à 52 caractères qu'un fichier de cheptels a
  pu passer pour un fichier de surfaces.

En cas d'échec, le script liste maintenant les colonnes du fichier plutôt
que de renvoyer vers `--colonnes` : une exécution suffit à comprendre.

**Et c'est ce diagnostic qui a livré le second défaut.** Le bon fichier
étant enfin retenu, le blocage a persisté — mais en affichant cette fois
les dix-sept colonnes réelles. Le code de commune s'y écrit
`codeinseecommune`, en un seul mot ; le motif de reconnaissance exigeait
un séparateur — `code_insee` ou `code insee` — et ne trouvait donc rien.
Corrigé en version 3, avec une précaution : `codepostalcommune` figure
juste à côté dans le fichier, et le confondre avec le code INSEE ferait
échouer tout le rapprochement sans le moindre message. Le motif l'écarte
explicitement, et un contrôle le vérifie.

Lecture éprouvée sur l'en-tête réel : millésime, surfaces certifiées,
surfaces en conversion et nombre d'exploitations sont tous reconnus.

**Une réserve à connaître.** Ce fichier ne contient aucune répartition
par groupe de cultures : ni fourrage, ni grandes cultures, ni viticulture.
La rubrique affichera donc les surfaces engagées, la part en conversion et
le nombre d'exploitations — pas le détail par culture. Ce détail existe
dans le fichier « surfaces de production », 465 Mo, qu'il faudrait traiter
à part. À décider plus tard : ce que nous publions déjà a du sens seul.

### Caches exclus du dépôt

Le `.gitignore` laissait passer `data/cache-elus/` — 78 Mo de fichiers du
répertoire des élus, dont un de 63 Mo — et le cache de l'Agence Bio.
GitHub refuse un fichier de plus de 100 Mo et signale ceux de plus de
50 Mo. Ces deux lignes manquaient ; elles sont ajoutées.

Si ces fichiers ont déjà été validés, retirez-les de l'index :

```
git rm -r --cached data/cache-elus
git rm --cached data/cache-bio.csv
```

### Pages d'annonce — Carburants et Élections

Deux rubriques décidées mais pas encore alimentées reçoivent une page
d'annonce, aux trois échelles :

- `/…/carburants/` — nouvel onglet en bout de barre, comme arbitré ;
- `/…/elections/resultats/` — nouvelle sous-rubrique, à côté d'Élus.

Cela fait **98 adresses nouvelles** — 49 territoires fois deux pages —
toutes inscrites au plan du site, qui passe de 628 à 726 adresses. C'est ce
qui lance l'exploration puis l'indexation, qui prennent des semaines.

**La réserve, et elle est sérieuse.** Quarante-sept pages au texte
identique sont exactement le schéma que les moteurs déclassent. Chaque
annonce porte donc des faits propres au territoire : nom, code INSEE ou
SIREN, codes postaux, canton et intercommunalité de rattachement, et pour
les élections les élus déjà collectés — le maire et l'effectif du conseil
municipal, le binôme départemental, la présidence de l'intercommunalité.
Les formules de lieu sont accordées : « à Saint-Marcellin », mais « dans
le canton du Sud Grésivaudan ».

**Aucune date n'est annoncée.** Une promesse tenue en retard vaut moins
que pas de promesse du tout.

**L'annonce s'efface d'elle-même** : elle n'est rendue que si la rubrique
n'a aucune mesure à montrer. Le jour où le collecteur carburants publiera,
la page d'annonce disparaîtra sans intervention — même principe que le
référentiel saisi à la main qui se retire à sa péremption.

Le contenu annoncé reprend les arbitrages du cahier des charges de Carbu :
six carburants, prix par station-service, source `data.economie.gouv.fr`.
Pour les élections : résultats par bureau de vote, embargo à 20 heures
posé dans le traitement et pas seulement à l'affichage, résultats partiels
annoncés comme tels.

Ceci consomme l'exigence **EF-17**, ajoutée au cahier des charges, qui
tempère EF-16 — « n'écrire une page que si elle a du contenu ».

### Mesure d'audience — Google Analytics, après consentement

Identifiant `G-ER3H1G7XSP`, configuré dans `ANALYTICS` en tête de
`04_generation.py`. **Vide, rien n'est ajouté au site** : ni script, ni
bandeau, et le fichier `assets/mesure.js` est même supprimé. C'est le
seul interrupteur.

Le script que Google fournit se colle tel quel dans chaque page et se
charge immédiatement. **Je ne l'ai pas posé ainsi**, pour trois raisons
qui tiennent au projet lui-même :

- vos mentions légales affirment que « ce site ne dépose aucun
  traceur » — la phrase serait devenue fausse sur une page qui vous
  identifie comme éditeur ;
- ENF-01 interdit tout traceur en consultation ordinaire, ENF-06 toute
  requête au chargement hors polices ;
- GA4 dépose des traceurs qui ne sont pas nécessaires au service : sans
  recueil du consentement, c'est un manquement à l'article 82 de la loi
  Informatique et Libertés.

**Ce qui est en place.** Un bandeau discret en bas de page, deux
boutons, « Refuser » à gauche de « Accepter » — pas de bouton unique ni
d'acceptation par défaut. Rien de Google n'est chargé tant que le
visiteur n'a pas répondu, et un refus ne charge rien du tout. Le choix
est conservé dans le navigateur pour ne pas être redemandé, et se révoque
depuis les mentions légales, qui décrivent désormais la mesure et
comportent un bouton « Revenir sur mon choix ».

Sans JavaScript : ni bandeau, ni mesure. Le défaut est le silence.

Les signaux publicitaires de Google sont désactivés à la configuration
(`allow_google_signals` et `allow_ad_personalization_signals` à faux) :
la mesure se limite à l'audience, sans ciblage ni recoupement entre
sites. L'espace d'administration n'est pas mesuré.

**Parcours éprouvé sur un serveur local**, appels réseau observés :
arrivée — bandeau affiché, zéro appel à Google ; refus — zéro appel, et
toujours zéro après rechargement ; acceptation — un appel, au bon
identifiant ; réinitialisation depuis les mentions légales — le bandeau
revient.

Le cahier des charges passe en version 2.0 : ENF-01 est reformulée,
ENF-01 b ajoutée, ENF-06 amendée, et l'arbitrage inscrit en section 7
avec les options écartées.

### Référencement — trois correctifs

Détaillés dans `SEO-2026-09-08.md`, qui répond aussi à la question de
l'indexation et de la liste des 404.

- **Le `h1` distingue enfin les pages.** Les quinze pages d'une commune
  portaient toutes « Saint-Marcellin » : pour un moteur, le signal le
  plus fort de la page ne distinguait rien. Elles portent désormais
  « Saint-Marcellin — Population ». Le premier jet plaçait le tiret dans
  la feuille de style, et le moteur lisait « Saint-MarcellinPopulation » :
  corrigé, le séparateur est dans le texte.
- **Une vraie page 404**, `404.html`, servie par `ErrorDocument`, en
  `noindex`, avec la recherche et les renvois utiles. Elle répond bien
  404 — une redirection vers l'accueil serait une « soft 404 », que
  Google compte comme une erreur.
- **Des redirections pour l'ancien site.** Une recherche a montré que
  l'index de Google porte encore des adresses en PHP sous `/rubriques/`.
  Une règle par commune les renvoie vers la fiche correspondante, avec
  les variantes `saint_`/`st_` et les articles initiaux ; le reste de
  cette ancienne arborescence est renvoyé vers l'accueil. Les motifs sont
  déduits de deux adresses observées et éprouvés sur des chemins réels :
  ils ne capturent aucune page vivante du portail.

### Liste des communes repliée

Sur le canton et l'intercommunalité, les 44 ou 47 communes rattachées
occupaient la moitié de l'écran avant la première tuile. Elles sont
désormais derrière « Voir les 44 communes », dépliables d'un clic.

- **Balise `details` native**, sans JavaScript : le repli fonctionne sans
  script, au clavier, et est annoncé par un lecteur d'écran. C'est ENF-05
  appliqué à une commande d'interface.
- **Les liens restent écrits dans la page** : un repli qui les chargerait
  à la demande les retirerait du maillage interne et de l'exploration par
  les moteurs.
- **Seuil à six communes** : en dessous, la liste tient sur une ligne et
  le repli coûterait un clic pour rien. Les fiches communales sont
  inchangées.

### Page publique de fraîcheur des données

Nouvelle page `/fraicheur/`, liée depuis le pied de page de tout le site.
Elle donne, source par source, la date de la dernière collecte, son
ancienneté, le rythme de publication du producteur et son nom, avec un
état : à jour, à rafraîchir, pas encore collectée, ou indisponible.

Elle était inscrite en priorité « élevée » au cahier des charges comme
argument de crédibilité. Elle devient surtout le **garde-fou de
l'automatisation** : une chaîne planifiée qui tombe en panne ne prévient
personne, et un site statique affiche sans broncher des chiffres de la
semaine dernière. Ici, cela se voit.

Trois principes appliqués :

- **Rien du fonctionnement interne.** Ni nom de script, ni commande, ni
  chemin. C'est ce qui la distingue de la page d'administration, qui
  affiche les mêmes états avec les moyens d'agir.
- **Du plus grave au moins grave** : collecte inexploitable, puis donnée
  absente, puis retard, puis à jour ; à état égal, la plus ancienne
  d'abord. C'est la règle du site pour tout état en cours.
- **La réserve est dite** : les dates sont celles de la collecte par le
  portail, non de la publication par le producteur. Une donnée collectée
  hier peut porter sur une année antérieure — son millésime est alors
  affiché à côté.

La page explique aussi, en clair, qu'un site statique n'interroge aucune
source au moment de la consultation. Mieux vaut le dire que laisser
croire à une actualisation permanente.

### Page d'administration allégée

Trois changements, à votre demande et pour la même raison — gagner de la
place et rendre l'accès évident :

- **La barre de recherche disparaît du bandeau.** Elle sert au visiteur à
  trouver un territoire ; sur une page d'administration elle n'avait aucun
  usage. Le script de recherche n'est plus chargé non plus. Elle reste
  bien entendu sur l'accueil, les fiches et les mentions légales.
- **Le texte sous le titre disparaît.** Il annonçait « discrétion
  seulement, protégez ce dossier par mot de passe » — ce qui est devenu
  faux depuis que la protection est en place.
- **Deux raccourcis le remplacent** : *Documents de travail* et *Journal
  du leurre*, directement sous le titre.

Le lien vers les documents existait déjà, mais dans une section placée en
avant-dernière position, tout en bas d'une page longue : il fallait le
chercher. Il est désormais en tête. La section « Documentation » reste
plus bas, avec le compte de documents lisibles et les réserves d'usage.

Une règle a été ajoutée au thème pour que ces raccourcis se distinguent du
texte : sur ce site, `a` hérite de la couleur courante partout, et un lien
posé dans cet en-tête serait resté invisible.

### Consultation des documents de travail

Nouvelle page `Terri_Admin/documents.php`. Elle liste le sous-dossier
`Documents/` et affiche son contenu, pour relire la documentation depuis
un téléphone. Le markdown est mis en forme — titres, tableaux, listes,
code — plutôt que servi brut : les tableaux du cahier des charges sont
illisibles autrement sur un petit écran.

Un lien depuis le tableau de bord, section « Documentation », qui indique
aussi le nombre de documents lisibles.

Trois précautions, dans l'esprit du reste du site :

- **Rien n'est écrit ni supprimé.** La page ne fait que lire ; l'ajout
  d'un document passe par le dépôt.
- **Seules les extensions déclarées sont listées et servies** — md, txt,
  csv, pdf, images, xlsx, docx, zip. Un fichier de configuration ou une
  clé déposés là par mégarde n'apparaîtraient pas, et ne seraient pas
  servis même en tapant leur nom dans l'adresse.
- **Deux verrous contre la traversée de répertoire** : `basename()` sur
  le nom demandé, puis vérification que le fichier résolu est bien sous
  `Documents/`. Éprouvé sur `../.htpasswd`, `../../04_generation.py`,
  `Documents/../../.htpasswd` et leurs formes encodées : aucune ne sort
  du dossier.

Un lien externe présent dans un document n'est rendu cliquable que si son
schéma est `http`, `https` ou `mailto` — c'est le défaut A-03 de l'audit,
fermé ici aussi. Un lien vers un autre document du dossier est réécrit
pour repasser par la page.

Le dossier `Documents/` est créé s'il manque, et reçoit un `.htaccess`
qui interdit le listage automatique par le serveur. Son contenu n'est
jamais touché.

---

## Mise en route

Installez les quatre fichiers, puis :

```
python 16_bio.py
python lancer.py --site
```

Le fichier de l'Agence Bio est déjà dans votre cache et son adresse n'a
pas changé : rien à retélécharger. `--colonnes` n'est plus nécessaire,
la lecture ayant été éprouvée sur l'en-tête réel de votre exécution.

`--site` ne sollicite aucun serveur public : il agrège, redessine les
cartes et régénère les pages.

---

## À vérifier après installation

| # | Attendu |
|---|---|
| 1 | Le lanceur ne signale aucun fichier en retard de version |
| 2 | Plus de rappel « Mentions légales non produites » à l'exécution |
| 3 | `/mentions-legales/` existe et identifie l'éditeur |
| 4 | Le pied de page renvoie vers les mentions légales |
| 5 | `/Terri_Admin/` affiche une section « Documentation » avec le compte |
| 6 | `/Terri_Admin/documents.php` liste les documents déposés |
| 7 | Un document s'ouvre, ses tableaux sont lisibles sur téléphone |
| 8 | `documents.php?f=../.htpasswd` renvoie la liste, et rien d'autre |
| 9 | La ligne « Documents : … document(s) lisible(s) » s'affiche à l'exécution |
| 10 | `16_bio.py` annonce « Données communales certifiées des surfaces », 41 Mo |
| 11 | `16_bio.py` annonce un millésime récent et des surfaces cumulées plausibles |
| 11 bis | La fiche d'une commune agricole affiche surface bio, part en conversion et exploitations |
| 12 | `git status` ne propose ni `data/cache-elus/` ni `data/cache-bio*.csv` |
| 13 | L'onglet Carburants apparaît en bout de barre, non grisé, aux trois échelles |
| 14 | Élections affiche deux sous-rubriques : Élus et Résultats |
| 15 | Une page d'annonce communale nomme la commune, son code INSEE, son canton et son maire |
| 16 | La page du canton écrit « dans le canton du Sud Grésivaudan », jamais « à Le Sud Grésivaudan » |
| 17 | `sitemap.xml` compte 96 adresses de plus qu'avant |

---

## Ce qui reste des bloquants

| Sujet | État |
|---|---|
| Mentions légales | **Fait** |
| Protection de `/Terri_Admin/` | **Fait** — pensez à vérifier que `chiffrer.php` a bien disparu du dépôt et du serveur |
| Ancien dossier `administration` | **À faire** : `git rm --cached administration/index.html`. Le générateur supprime le fichier localement, mais tant qu'il est suivi par Git il revient au déploiement suivant |

---

## Règle nouvelle — ce qui a sa place dans `Documents/`

Ce dossier est protégé par mot de passe, mais il est servi par le web :
la protection peut sauter d'un déploiement malheureux, et une capture
d'écran se partage. La règle est donc la même que pour le dépôt.

**Y ont leur place** : les documents de travail du projet — cahier des
charges, état du projet, feuille de route, exécution, tests, audit,
livraisons.

**N'y ont pas leur place** : `.htpasswd`, la clé Météo-France, tout
identifiant ou mot de passe, tout fichier de configuration portant un
secret. Ces fichiers ne sont d'ailleurs pas servis par la page, mais
mieux vaut ne pas les y déposer du tout.

**À décider au cas par cas** : un document décrivant précisément un
mécanisme de sécurité. `AUDIT.md` est dans ce cas — il nomme le chemin
d'administration et détaille le leurre. Il reste utile là, derrière le
mot de passe, mais c'est un document à ne pas sortir de ce cadre.
