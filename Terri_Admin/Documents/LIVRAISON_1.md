# Livraison du 8 septembre 2026

Mentions légales et consultation de la documentation.

---

## Fichiers à installer — deux

| Fichier | Version | Nature |
|---|---|---|
| `04_generation.py` | 22 → **23** | Mentions renseignées, page `documents.php` |
| `lancer.py` | mis à jour | Version attendue et plan de livraison |

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

```
python lancer.py --site
```

Trois étapes, aucune sollicitation de serveur public. Inutile de
recollecter : seuls l'affichage et les pages d'administration changent.

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
