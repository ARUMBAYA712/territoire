# Cahier des charges
## Sud Grésiv' — portail de données territoriales

Document interne

| | |
|---|---|
| Version du document | 2.0 |
| Date | 8 septembre 2026 |
| Plateforme cible | Site web statique — ordinateur, tablette, téléphone |
| Adresse | territoire.sudgresiv.com |
| Intégration | Sous-ensemble du site sudgresiv.com, à regrouper après les carburants et les élections |
| Statut | En développement — en ligne, périmètre partiel |
| Mise à jour du document | À la demande, ou tous les trois jours |

---

## 1. Objet du document

Ce document formalise le périmètre du portail Sud Grésiv', site de données
publiques territoriales. Il reprend l'ensemble des demandes formulées au fil du
projet, les arbitrages retenus, et — point important — les options écartées avec
leur motif, afin qu'une décision déjà tranchée ne soit pas rouverte sans élément
nouveau.

### 1.1 Objectif du produit

Permettre à un habitant, un élu, un journaliste ou une association de connaître
son territoire à partir des seules données publiques françaises, présentées à
trois échelles administratives, sans compte utilisateur et sans publicité.

Le portail est également le premier consommateur d'un service de données
versionné, destiné à être appelé par d'autres sites locaux.

### 1.2 Principes directeurs

- **Ne publier que l'existant et le pertinent** — un indicateur qui n'a pas de
  sens à une échelle n'y est pas affiché. Le nombre de fiches varie donc d'un
  niveau à l'autre, et c'est assumé.
- **Ne jamais confondre absence de donnée et échec technique** — les deux cas
  sont distingués partout, dans les collectes comme à l'affichage.
- **Une donnée sans repère ne vaut rien** — chaque valeur porte son unité, sa
  source, son millésime et, quand cela s'impose, une échelle de lecture.
- **Bloquer plutôt que publier faux** — un contrôle en défaut arrête le
  traitement sans rien écrire ; le site conserve ses données précédentes.
- **Aucune dépendance payante** — aucune clé d'API, aucun quota facturable,
  aucune bibliothèque tierce côté site.
- **Le contenu ne dépend pas du JavaScript** — chiffres, textes et liens sont
  écrits dans la page ; le script n'ajoute que du confort.

---

## 2. Historique des demandes et décisions

| Demande | Décision retenue | Version |
|---|---|---|
| Portail de données publiques à trois échelles, seize catégories | Catalogue des sources établi, cinq catégories documentées sur seize | 0.1 |
| Choix de la pile technique | Site statique, HTML et JavaScript sans bibliothèque, ETL en Python | 0.1 |
| Hébergement | OVH mutualisé, déploiement automatique depuis GitHub par webhook | 0.2 |
| Périmètre du laboratoire | Les 44 communes du canton du Sud Grésivaudan ; chargement sur les 47 de l'intercommunalité, le canton en étant un sous-ensemble strict | 0.2 |
| Référentiel des territoires | Réalisé. Réconciliation automatique canton / intercommunalité, contrôles bloquants | 0.3 |
| Moteur d'agrégation | Réalisé. Trois modes : natif, somme, ratio recalculé | 0.3 |
| Pages indexables | Réalisé. Génération statique, une page par territoire et par rubrique | 0.4 |
| Adresses lisibles | Réalisé. `/commune/38416-saint-marcellin/`, code INSEE en tête pour la stabilité | 0.4 |
| Cartes | Réalisé. SVG produit à partir des contours IGN, sans bibliothèque | 0.5 |
| Fond de carte | OpenStreetMap écarté, Géoplateforme IGN retenue. Plan et vue aérienne | 0.8 |
| Noms de communes sur les cartes | Réalisé, avec placement anti-chevauchement | 0.9 |
| Qualité de l'eau potable | Réalisé à partir de Hub'Eau, avec le détail par réseau de distribution | 0.6 |
| Restrictions sécheresse | Réalisé à partir de VigiEau, avec lien vers l'arrêté préfectoral | 0.7 |
| Risques et catastrophes naturelles | Réalisé à partir de Géorisques | 0.7 |
| Niveau des nappes | Réalisé, rattaché au canton et non aux communes | 0.8 |
| Navigation par rubriques | Réalisé. Barre horizontale, sous-rubriques pour Environnement | 0.9 |
| Prix de l'eau | Reporté. L'API Hub'Eau est arrêtée le 10 septembre 2026 ; passage par les fichiers SISPEA à instruire | — |
| Audit complet | Réalisé : 1 défaut critique, 4 risques de sécurité, 2 de robustesse, 2 de référencement, tous corrigés | 1.0 |
| Rubrique Prix des carburants | Décidée, non développée. Onglet dédié en bout de barre, plus un résumé dans Transports | — |
| Automatisation des mises à jour | GitHub Actions retenu. CRON OVH écarté pour les collecteurs : Python n'est pas disponible sur l'hébergement mutualisé | — |
| Résultats en direct le soir d'élection | **Décision révisée** : retenu. Motif invoqué : crédibilité du site, non fréquentation. Architecture à concevoir, contrainte légale d'embargo à respecter | — |
| Amorcer l'indexation avant la donnée | Retenu. Pages d'annonce Carburants et Élections / Résultats, aux trois échelles, portant des faits propres à chaque territoire et s'effaçant à l'arrivée de la donnée | 1.8 |
| Mesurer l'audience du site | Retenu. Google Analytics, chargé après consentement explicite seulement | 2.0 |

---

## 3. Périmètre fonctionnel

### 3.1 Territoires et navigation

| Réf. | Exigence |
|---|---|
| EF-01 | Afficher une fiche par commune, par canton et par intercommunalité, à une adresse stable et indexable. |
| EF-02 | Placer le code INSEE en tête de l'adresse, le nom ne servant que la lisibilité, afin qu'un changement de nom ne rompe pas le lien. |
| EF-03 | Rediriger les anciennes adresses sans nom, par correspondance exacte. |
| EF-04 | Rechercher un territoire par nom, par code INSEE ou par code postal, sans tenir compte des accents. |
| EF-05 | Classer les résultats alphabétiquement, les noms commençant par la saisie venant en tête. |
| EF-06 | Afficher les rattachements en montrant que canton et intercommunalité ne regroupent pas les mêmes communes. |
| EF-07 | Rappeler dans le bandeau le canton et l'intercommunalité de la commune, l'un et l'autre cliquables. |
| EF-08 | Maintenir le bandeau du territoire affiché au défilement, en le comprimant. |

### 3.2 Rubriques

| Réf. | Exigence |
|---|---|
| EF-10 | Organiser le contenu en rubriques : Aperçu, Population, Géographie, Urbanisme, Environnement, Transports, Élections. |
| EF-11 | Donner à chaque rubrique sa propre adresse, son titre et sa description. |
| EF-12 | Afficher en grisé les rubriques encore vides, pour montrer ce qui existe et ce qui vient. |
| EF-13 | Doter les rubriques volumineuses de sous-rubriques et d'une seconde barre de navigation. |
| EF-14 | Limiter l'Aperçu à une sélection de six indicateurs choisis, et non à l'ensemble. |
| EF-15 | Faire remonter sur l'Aperçu tout indicateur en état d'alerte, même hors sélection. |
| EF-16 | N'écrire une page que si elle a du contenu, afin qu'aucun lien ne mène à une page vide. |
| EF-17 | Publier, pour une rubrique décidée mais pas encore alimentée, une page d'annonce disant ce qui sera diffusé, d'où viendra la donnée et sous quelles réserves. Elle ne s'écrit que si elle porte des faits propres au territoire, n'annonce aucune date, et s'efface d'elle-même dès qu'une mesure arrive. |
| EF-18 | Permettre à une mesure d'intéresser deux rubriques sans être dupliquée : le détail reste dans la rubrique qu'elle déclare, la seconde reçoit un écho — valeur, source et lien nommé vers la page de détail. Un écho ne rend jamais une rubrique active, ne remonte pas sur l'Aperçu et n'est écrit que si la page visée existe pour ce territoire. |
| EF-19 | Doter chaque page d'un titre de premier niveau unique et d'un plan de titres sans saut de niveau, et déclarer en JSON-LD le fil d'ariane, le territoire et — sur la page d'accueil du territoire — le jeu de données offert au téléchargement. Ne rien déclarer qui ne soit sur la page. |

### 3.3 Indicateurs

| Réf. | Exigence |
|---|---|
| EF-20 | Afficher pour chaque indicateur sa valeur, son unité, sa source et son mode d'obtention. |
| EF-21 | Adjoindre une explication et une échelle de lecture aux indicateurs qui ne parlent pas d'eux-mêmes. |
| EF-22 | Distinguer limite de qualité réglementaire, référence de qualité et absence de seuil. |
| EF-23 | Colorer un indicateur en état d'attention ou d'alerte selon des seuils déclarés. |
| EF-24 | Renvoyer d'un indicateur vers son bloc détaillé, à condition que ce bloc existe sur la page. |
| EF-25 | Publier un lien vers le document officiel chaque fois qu'il en existe un. |
| EF-26 | Classer toute liste historique du plus récent au plus ancien, et toute liste d'états en cours du plus grave au moins grave. |
| EF-27 | Publier des séries historiques sous forme de graphiques écrits dans la page, sans bibliothèque : quatre formes (saison, courbe, barres, bandes), le tableau des valeurs replié sous chacune, et le survol comme simple confort. Une forme qui ne peut être produite honnêtement ne produit rien. |
| EF-28 | Afficher les lacunes d'une série, ne jamais les interpoler ; ne tracer aucune droite de tendance ; nommer sur le graphique la source et la période couverte. Ces règles sont tenues par le générateur, non par la vigilance du collecteur. |

### 3.4 Cartes

| Réf. | Exigence |
|---|---|
| EF-30 | Situer chaque commune dans son territoire plutôt que d'afficher un contour isolé. |
| EF-31 | Afficher le nom des communes, en évitant les chevauchements et les débordements. |
| EF-32 | Rendre chaque commune cliquable vers sa fiche, et son nom lisible au survol. |
| EF-33 | Proposer un fond de plan optionnel : schéma, plan IGN, vue aérienne. |
| EF-34 | Ne télécharger les tuiles qu'au moment où le fond est demandé. |
| EF-35 | Maintenir les limites communales nettement visibles quel que soit le fond. |
| EF-36 | Colorer la carte selon l'indicateur choisi, en classes d'effectifs comparables. |
| EF-37 | Permettre de masquer les noms, notamment sur écran étroit. |

### 3.5 Résultats électoraux en direct

Applicable les soirs de scrutin uniquement. Le reste du temps, la rubrique
Élections fonctionne comme les autres.

| Réf. | Exigence |
|---|---|
| EF-50 | Ne publier aucun résultat avant la fermeture du dernier bureau de vote, soit 20 heures. Contrainte légale, non négociable. |
| EF-51 | Afficher en permanence l'heure de la dernière relève et la part de bureaux dépouillés. |
| EF-52 | Qualifier explicitement les résultats de partiels tant que le dépouillement n'est pas achevé. |
| EF-53 | Rafraîchir la page d'elle-même, sans intervention du visiteur, et signaler visuellement chaque mise à jour. |
| EF-54 | Renvoyer vers la publication officielle du ministère, qui fait seule foi. |
| EF-55 | En cas d'échec de la relève, conserver les derniers chiffres obtenus en affichant leur ancienneté, plutôt que d'afficher une page vide. |
| EF-56 | Distinguer un bureau non dépouillé d'un bureau à zéro voix. |

### 3.6 Service de données

| Réf. | Exigence |
|---|---|
| EF-40 | Publier les données sous des adresses versionnées, un fichier par territoire. |
| EF-41 | Faire porter à chaque valeur sa source, sa licence et la date de génération. |
| EF-42 | Ne publier aucune valeur mise en forme : la présentation appartient au site qui affiche. |
| EF-43 | Conserver la stabilité des identifiants d'indicateurs, qui constituent le contrat. |

---

## 4. Exigences non fonctionnelles

| Réf. | Domaine | Exigence |
|---|---|---|
| ENF-01 | Confidentialité | Aucun compte, aucun formulaire, aucune donnée personnelle lors d'une consultation ordinaire. Seules les tentatives d'accès à l'espace d'administration sont consignées, avec une adresse tronquée. |
| ENF-01 b | Mesure d'audience | La mesure de fréquentation par Google Analytics n'est activée qu'après accord explicite du visiteur. Tant qu'il n'a pas répondu, et s'il refuse, aucun script du mesureur n'est chargé et aucune donnée ne lui est transmise. Sans JavaScript, ni bandeau ni mesure : le défaut est le silence. Les signaux publicitaires sont désactivés. Le choix est réversible depuis les mentions légales. |
| ENF-02 | Publicité | Aucune publicité, aucune mise en avant rémunérée. |
| ENF-03 | Coût d'exploitation | Aucune API payante, aucune clé, aucun quota facturable. |
| ENF-04 | Référencement | Contenu écrit dans la page, une adresse par territoire et par rubrique, plan du site, adresses canoniques. |
| ENF-05 | Dégradation | Sans JavaScript, le contenu, les chiffres et les liens restent accessibles. |
| ENF-06 | Réactivité | Pages statiques, aucune requête au chargement hors polices et, après accord seulement, du mesureur d'audience ; tuiles à la demande. |
| ENF-07 | Adaptation aux écrans | Ordinateur, tablette et téléphone ; les tableaux deviennent des listes sur écran étroit. |
| ENF-08 | Accessibilité | Libellés vocaux sur les cartes et les boutons, navigation au clavier, contrastes conformes. |
| ENF-09 | Identité visuelle | Contenue dans un fichier de thème unique, remplaçable sans toucher à la structure. |
| ENF-10 | Portabilité | Aucune dépendance à l'hébergeur hors déploiement ; le site peut être servi ailleurs sans modification. |
| ENF-11 | Reprise | Toute collecte est reprenable ; une coupure ne fait perdre que l'élément en cours. |
| ENF-12 | Traçabilité | Chaque collecteur porte un numéro de version ; une collecte à un format périmé est détectée. |
| ENF-13 | Administration | Section de suivi à `/Terri_Admin/`, majuscules volontaires, appelée depuis les pages d'administration de sudgresiv.com et non depuis le portail. Ni indexée, ni liée, ni mentionnée dans le robots.txt. La documentation du projet y sera copiée dans un sous-dossier. |
| ENF-14 | Leurre | L'ancienne adresse `/administration/` présente une fausse page de connexion, impose une attente et consigne les tentatives. Adresses tronquées d'un segment, conservation limitée, aucun identifiant saisi enregistré. |

---

## 5. Sources de données

Toutes les sources sont publiques, gratuites et sans clé d'API.

| Usage | Service | Contrainte |
|---|---|---|
| Référentiel des communes | geo.api.gouv.fr — découpage administratif | Les cantons n'y sont pas exposés |
| Rattachement cantonal | Décret n° 2014-180 du 18 février 2014 | Vérifié nom par nom ; Dionay retiré après fusion de 2016 |
| Contours géographiques | geo.api.gouv.fr — Admin Express | Volumétrie importante, mise en cache |
| Fonds de carte | data.geopf.fr — Plan IGN v2 et orthophotos | France et outre-mer uniquement |
| Qualité de l'eau potable | Hub'Eau — contrôle sanitaire | Lenteurs fréquentes, champs multivalués |
| Restrictions sécheresse | api.vigieau.gouv.fr | Coordonnées exigées si plusieurs zones |
| Risques et catastrophes | georisques.gouv.fr | Réponses vides sur certains points d'entrée |
| Niveau des nappes | Hub'Eau — niveaux nappes | Stations rares et inégalement suivies |

### 5.1 Contraintes structurelles

- **Aucune source ne suit les limites administratives.** Réseaux d'eau, stations
  de mesure, services d'eau, bureaux de vote : chacun impose son propre
  rattachement. Le modèle traite le territoire comme une clé et non comme une
  hiérarchie.
- **Le canton n'est pas exposé par l'API du découpage administratif**, les
  communes de plus de 3 500 habitants pouvant être scindées. Sur le Sud
  Grésivaudan aucune ne l'est, ce qui rend les agrégations exactes — propriété
  du territoire, non règle générale.
- **Les libellés de paramètres varient selon les agences régionales.** Le
  repérage se fait par motif, jamais par correspondance exacte.
- **Les schémas amont évoluent.** Champs tantôt simples tantôt multiples,
  réponses vides valant absence de donnée : les collecteurs normalisent
  systématiquement.
- **Le secret statistique** empêche la diffusion de certains indicateurs sur les
  petites communes, majoritaires ici.

---

## 6. Architecture technique

| Élément | Choix |
|---|---|
| Traitement des données | Python, bibliothèque standard uniquement |
| Site | HTML et JavaScript sans bibliothèque, généré statiquement |
| Cartographie | SVG produit en Python, projection Web Mercator |
| Publication | Fichiers JSON versionnés, une adresse par territoire |
| Hébergement | OVH mutualisé, déploiement depuis GitHub par webhook |
| Ordonnancement | Manuel aujourd'hui ; GitHub Actions à terme |

### 6.1 Règles d'architecture

- **Le périmètre est une donnée de configuration**, jamais du code. L'élargir
  consiste à ajouter une ligne.
- **Toute donnée est stockée à la maille communale**, les rattachements vivant
  dans une table séparée. Les périmètres changent, les communes non.
- **Chaque collecteur déclare où sa donnée s'affiche** — rubrique,
  sous-rubrique, rang. Le générateur ne devine rien.
- **Une courbe ne dit jamais plus que la série.** Une station déplacée, un
  capteur remplacé, deux ans de relevés manquants : chacun produit une rupture
  qui *ressemble* à une tendance. Le générateur montre les trous et refuse de
  tracer une pente ; il n'existe pas d'option pour en demander une.
- **Une donnée ne vit qu'à un seul endroit.** Quand elle intéresse deux
  rubriques, la seconde reçoit un renvoi, jamais une copie : deux tuiles
  identiques seraient deux vérités à tenir à jour, et deux pages du site
  se disputant le même mot-clé.
- **Le moteur d'agrégation reprend tout fichier de mesures qu'il trouve.**
  Ajouter une source ne demande jamais de le modifier.
- **Un contrôle en défaut arrête le traitement sans rien écrire.**
- **Les taux et moyennes sont recalculés sur les agrégats**, jamais moyennés.
- **L'identité visuelle est isolée dans un bloc unique.**
- **Les ressources portent une empreinte de leur contenu**, ce qui évite tout
  problème de cache après modification.
- **Le portail est un sous-ensemble d'un site plus large.** Rien ne doit
  supposer qu'il occupe seul le domaine : le thème est isolé, les adresses
  sont préfixées par le niveau de territoire, et le plan du site comme les
  redirections ne portent que sur ce périmètre. Un regroupement avec le
  reste de sudgresiv.com est prévu après les carburants et les élections.
- **Ce qui compte le plus vient en premier.** Toute liste historique se lit du
  plus récent au plus ancien ; toute liste d'états en cours, du plus grave au
  moins grave. Le classement alphabétique est réservé aux listes que le visiteur
  parcourt pour y chercher un élément connu — communes, résultats de recherche.

---

## 7. Arbitrages et options écartées

| Sujet | Retenu | Écarté | Motif |
|---|---|---|---|
| Pile technique | JavaScript sans bibliothèque, génération statique | React | Chaîne de construction à maintenir, rendu non indexable sans couche supplémentaire |
| Fond de carte | Géoplateforme IGN | OpenStreetMap | La politique d'usage réserve les serveurs aux usages qui ne les mettent pas sous tension et prévient les services commerciaux d'un retrait possible |
| Base de données | Fichiers JSON publiés | Base en production | Aucun serveur à administrer ; la base reste un outil de préparation |
| Ordonnancement | GitHub Actions | CRON OVH | Python n'est pas disponible sur l'hébergement mutualisé |
| Périmètre chargé | Les 47 communes de l'intercommunalité | Les 44 du canton seules | Coût nul, et tout agrégat intercommunal serait sinon partiel |
| Qualité de l'eau au canton | Non agrégée | Taux de conformité cantonal | Les réseaux ne suivent pas les limites administratives ; un taux cantonal n'aurait aucun sens hydraulique |
| Conformité sanitaire | Limites de qualité seules | Références de qualité incluses | Une eau non conforme aux références reste potable ; les confondre alarmerait à tort |
| Champ de conformité vide | Prélèvement écarté du calcul | Compté non conforme | Annoncer à tort une eau non conforme est la faute la plus grave possible |
| Niveau des nappes | Appréciation par rapport aux valeurs de saison | Profondeur brute seule | Trois mètres ne veut rien dire sans référence |
| Station de référence | La plus proche parmi les récentes | La plus récente | La référence basculait sur une station lointaine au gré des mises à jour |
| Infobulle des cartes | JavaScript | Balise `title` native | Neutralisée par le navigateur dès que la forme est dans un lien |
| Interactivité des cartes | Zoom absent | Bibliothèque cartographique | Le territoire tient dans un écran ; une dépendance de plus pour un gain nul |
| Aperçu | Six indicateurs choisis | Tous les indicateurs | Dix-neuf tuiles n'étaient plus une fiche mais un inventaire |
| Arborescence | Deux niveaux | Trois niveaux | Une page pour quatre paramètres coûte plus qu'elle ne rapporte |
| Regroupement électoral par bloc | Table éditoriale datée et réversible | Classement figé | Le regroupement est un choix du site, pas une donnée officielle |
| Séries cantonales avant 2015 | Anciens cantons en couche datée | Rupture non traitée | Permet d'afficher l'histoire électorale sans réécrire les périmètres |
| Prix de l'eau | Reporté, voie SISPEA | API Hub'Eau | Arrêt de l'API au 10 septembre 2026 |
| Résultats en direct | Retenu, sur données publiées après 20 h | Abstention le soir du scrutin | Arbitrage rouvert : être absent le seul soir de forte affluence dessert la crédibilité recherchée |
| Diffusion du direct | Fichiers de données rafraîchis, page qui interroge la même origine | Régénération complète du site à chaque relève | 250 pages régénérées toutes les dix minutes pour quelques chiffres qui changent |
| Mesure d'audience | Google Analytics soumis au consentement | Google Analytics sans bandeau ; compteur maison sans cookie ; aucune mesure | Un traceur non nécessaire au service exige le consentement, article 82 de la loi Informatique et Libertés. Le poser sans bandeau rendait fausses les mentions légales du site. Le compteur maison évitait le bandeau mais n'aurait pas donné les analyses attendues |
| Rubrique décidée, sans donnée | Page d'annonce indexable | Aucune page jusqu'à la donnée, conformément à EF-16 | L'exploration puis l'indexation d'une adresse prennent des semaines : les engager d'avance fait gagner ce délai. Réserve assumée : quarante-sept pages au texte identique sont le schéma que les moteurs déclassent, d'où l'obligation de faits propres à chaque territoire |
| Prix des carburants sur un site statique | Prix de la dernière génération, horodatage affiché | Interrogation du flux en direct comme dans l'application Carbu | Un site statique ne peut pas interroger une source à l'ouverture ; la différence de nature est dite au visiteur plutôt que masquée |

---

## 8. Hors périmètre

| Élément | Statut |
|---|---|
| Espérance de vie, projections démographiques | Impossible — aucune maille infra-départementale |
| Déclarations de la Haute Autorité pour la transparence | Écarté — aucune maille territoriale, sujet sensible |
| Agrégation des municipales | Impossible — listes locales sans étiquette comparable |
| Contribution des visiteurs | Écarté — impliquerait comptes, serveur et modération |
| Mode sombre | Reporté — le thème le permet, la question est le fond de carte |
| Niveau départemental et régional | Phase 2 — prévu dans le modèle, non affiché |
| Application mobile | Hors sujet — un site adapté aux écrans suffit |

---

## 9. Livrables

| Livrable | Destinataire | État |
|---|---|---|
| Site public | Visiteurs | En ligne, cinq catégories sur seize |
| Service de données versionné | Sites tiers | En ligne, non documenté publiquement |
| Neuf scripts de traitement | Interne | À jour |
| Catalogue des sources | Interne | 66 données, cinq catégories |
| Note d'exécution | Interne | À jour |
| Rapport d'audit | Interne | Version 1.0 |
| Fiche de tests | Interne | À jour |
| Feuille de route | Interne | À jour |
| Cahier des charges | Interne | Ce document |

---

## 10. Reste à faire avant communication publique

| Priorité | Tâche | Nature |
|---|---|---|
| Fait | Mentions légales | Renseignées le 8 septembre 2026 ; page `/mentions-legales/` produite |
| Bloquant | Vérifier le lien vers le rapport Géorisques | Adresse supposée, jamais éprouvée |
| Élevée | Donner un contenu propre à l'accueil | Aujourd'hui identique à la fiche du canton |
| Élevée | Mettre en place GitHub Actions | Prérequis des carburants |
| Fait | Page publique de fraîcheur des données | `/fraicheur/`, liée en pied de page : date de collecte, ancienneté et rythme de chaque source, sans rien exposer du fonctionnement interne |
| Moyenne | Script unique enchaînant la séquence | La séquence n'est plus mémorisable |
| Moyenne | Héberger les polices localement | Un appel externe par page |
| Moyenne | Documenter le service de données | Condition de son usage par des tiers |
| Moyenne | Éprouver la chaîne du direct hors période électorale | Un premier essai en conditions réelles ne doit pas avoir lieu un soir de scrutin |
| Faible | Logo et identité typographique | Le nom doit rester du texte, non une image |
| À planifier | Regroupement avec sudgresiv.com | Après carburants et élections ; conditionne l'arborescence et le thème |
| Fait | Documentation consultable dans `/Terri_Admin/Documents/` | Page `documents.php` : lecture seule, extensions filtrées, hors indexation, derrière le mot de passe du dossier parent |

---

## 11. Risques identifiés

| Risque | Impact | Mesure prise |
|---|---|---|
| Publication silencieuse de données fausses | Élevé | Contrôles bloquants à chaque étape ; recoupements avec les valeurs publiées |
| Évolution des schémas amont | Élevé | Normalisation systématique ; réponse vide traitée comme absence de donnée |
| Lenteur ou coupure des API | Moyen | Nouvelles tentatives, sauvegarde au fil de l'eau, reprise par élément |
| Dépendance à une seule personne | Moyen | Code commenté en français, décisions consignées dans ce document |
| Fraîcheur des données en collecte manuelle | Moyen | Date de génération affichée sur chaque page ; automatisation prévue |
| Liste cantonale erronée | Écarté | Confrontée au décret n° 2014-180 nom par nom, et recoupée avec la population publiée |
| Retrait de l'accès à une source publique | Faible | Toutes les sources sont des services de l'État ; un point de configuration par service |
| Contestation d'une donnée sensible | Faible | Renvoi systématique vers l'autorité compétente et le document officiel |
| Résultat erroné diffusé le soir d'un scrutin | Élevé | Embargo respecté, chiffres qualifiés de partiels, heure de relève affichée, source officielle citée |
| Publication avant 20 h | Élevé | Verrou horaire dans le traitement lui-même, pas seulement à l'affichage |

---

*Fin du document. Toute évolution du périmètre doit faire l'objet d'une mise à
jour de la section 2 et, le cas échéant, de la section 7.*
