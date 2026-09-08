<?php
// Documents de travail — consultation, lecture seule.
//
// Liste le sous-dossier Documents et sert son contenu, pour pouvoir
// relire la documentation du projet depuis un téléphone.
//
// Trois précautions, dans l'esprit du reste du site :
//
//   · cette page hérite de la protection par mot de passe du dossier
//     parent, elle n'en ajoute aucune ;
//   · seules les extensions déclarées ci-dessous sont listées et
//     servies — une clé ou un fichier de configuration déposés là par
//     mégarde resteraient invisibles ;
//   · rien n'est écrit ni supprimé : le dépôt reste la seule voie
//     d'ajout d'un document.

header('X-Robots-Tag: noindex, nofollow');

$base = __DIR__ . '/Documents';
$racine = realpath($base);

// Extensions servies, avec leur libellé, leur type et leur mode
// d'affichage. N'y ajoutez jamais php, htaccess, json ni key.
$TYPES = [
    'md'   => ['Document', 'text/plain; charset=utf-8', 'markdown'],
    'txt'  => ['Texte', 'text/plain; charset=utf-8', 'brut'],
    'csv'  => ['Tableau', 'text/plain; charset=utf-8', 'brut'],
    'pdf'  => ['PDF', 'application/pdf', 'incorpore'],
    'png'  => ['Image', 'image/png', 'incorpore'],
    'jpg'  => ['Image', 'image/jpeg', 'incorpore'],
    'jpeg' => ['Image', 'image/jpeg', 'incorpore'],
    'webp' => ['Image', 'image/webp', 'incorpore'],
    'svg'  => ['Image', 'image/svg+xml', 'telecharge'],
    'xlsx' => ['Classeur', 'application/octet-stream', 'telecharge'],
    'docx' => ['Document Word', 'application/octet-stream', 'telecharge'],
    'zip'  => ['Archive', 'application/zip', 'telecharge'],
];

function extension($nom)
{
    return strtolower(pathinfo($nom, PATHINFO_EXTENSION));
}

function poids($octets)
{
    if ($octets < 1024) {
        return $octets . ' o';
    }
    if ($octets < 1048576) {
        return round($octets / 1024) . ' Ko';
    }
    return round($octets / 1048576, 1) . ' Mo';
}

// Fichiers présents, triés par nom. Les sous-dossiers ne sont pas
// parcourus : un seul niveau, cela suffit et rien ne peut déborder.
function inventaire($base, $TYPES)
{
    $liste = [];
    if (!is_dir($base)) {
        return $liste;
    }
    foreach (scandir($base) as $nom) {
        if ($nom === '.' || $nom === '..' || $nom[0] === '.') {
            continue;
        }
        $chemin = $base . '/' . $nom;
        if (!is_file($chemin) || !isset($TYPES[extension($nom)])) {
            continue;
        }
        $liste[] = [
            'nom' => $nom,
            'taille' => filesize($chemin),
            'date' => filemtime($chemin),
            'type' => $TYPES[extension($nom)][0],
        ];
    }
    usort($liste, function ($a, $b) {
        return strcasecmp($a['nom'], $b['nom']);
    });
    return $liste;
}

// ── rendu du markdown ─────────────────────────────────────────────
// Assez pour relire la documentation du projet : titres, tableaux,
// listes, code, citations. Le texte est échappé AVANT toute mise en
// forme, et un lien dont le schéma n'est pas explicitement autorisé
// n'est pas rendu cliquable — « javascript: » n'a rien à faire ici.

function md_ligne($texte, $TYPES)
{
    $t = htmlspecialchars($texte, ENT_QUOTES, 'UTF-8');
    $t = preg_replace('/`([^`]+)`/u', '<code>$1</code>', $t);
    $t = preg_replace('/\*\*([^*]+)\*\*/u', '<strong>$1</strong>', $t);
    $t = preg_replace('/(?<![*\w])\*([^*\n]+)\*(?!\*)/u', '<em>$1</em>', $t);
    $t = preg_replace_callback(
        '/\[([^\]]*)\]\(([^)\s]+)\)/u',
        function ($m) use ($TYPES) {
            $libelle = $m[1];
            $url = html_entity_decode($m[2], ENT_QUOTES, 'UTF-8');
            // Renvoi vers un autre document du dossier : on repasse par
            // cette page plutôt que de servir le fichier en direct.
            if (!preg_match('#^[a-z][a-z0-9+.-]*:#i', $url)
                && isset($TYPES[extension($url)])) {
                $cible = '?f=' . rawurlencode(basename($url));
                return '<a href="' . htmlspecialchars($cible, ENT_QUOTES, 'UTF-8')
                    . '">' . $libelle . '</a>';
            }
            if (!preg_match('#^(https?://|mailto:)#i', $url)) {
                return $libelle;
            }
            return '<a href="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8')
                . '" rel="noopener noreferrer" target="_blank">' . $libelle . '</a>';
        },
        $t
    );
    return $t;
}

function md_tableau($lignes, $TYPES)
{
    $html = '<div class="deborde"><table>';
    $entete = true;
    foreach ($lignes as $ligne) {
        $cellules = array_map('trim', explode('|', trim($ligne, " \t|")));
        // La ligne de séparation ne porte que tirets et deux-points.
        if (preg_match('/^[\s|:-]+$/', $ligne)) {
            $entete = false;
            continue;
        }
        $html .= '<tr>';
        foreach ($cellules as $cellule) {
            $balise = $entete ? 'th' : 'td';
            $html .= "<$balise>" . md_ligne($cellule, $TYPES) . "</$balise>";
        }
        $html .= '</tr>';
        $entete = false;
    }
    return $html . '</table></div>';
}

function markdown($texte, $TYPES)
{
    $lignes = preg_split('/\r\n|\r|\n/', $texte);
    $html = '';
    $liste = null;      // 'ul' ou 'ol' en cours
    $item = null;       // texte de l'élément de liste en cours
    $code = false;
    $paragraphe = [];
    $tableau = [];

    $vider_paragraphe = function () use (&$paragraphe, &$html, $TYPES) {
        if ($paragraphe) {
            $html .= '<p>' . md_ligne(implode(' ', $paragraphe), $TYPES) . '</p>';
            $paragraphe = [];
        }
    };
    // Un élément de liste est mis en attente plutôt qu'écrit aussitôt :
    // une phrase repliée sur la ligne suivante appartient à l'élément
    // en cours, et non à un paragraphe nouveau.
    $vider_item = function () use (&$item, &$html, $TYPES) {
        if ($item !== null) {
            $html .= '<li>' . md_ligne($item, $TYPES) . '</li>';
            $item = null;
        }
    };
    $fermer_liste = function () use (&$liste, &$html, &$vider_item) {
        $vider_item();
        if ($liste) {
            $html .= "</$liste>";
            $liste = null;
        }
    };
    $vider_tableau = function () use (&$tableau, &$html, $TYPES) {
        if ($tableau) {
            $html .= md_tableau($tableau, $TYPES);
            $tableau = [];
        }
    };

    foreach ($lignes as $ligne) {
        if (preg_match('/^\s*```/', $ligne)) {
            $vider_paragraphe();
            $fermer_liste();
            $vider_tableau();
            $html .= $code ? '</code></pre>' : '<pre><code>';
            $code = !$code;
            continue;
        }
        if ($code) {
            $html .= htmlspecialchars($ligne, ENT_QUOTES, 'UTF-8') . "\n";
            continue;
        }

        if (strpos(ltrim($ligne), '|') === 0) {
            $vider_paragraphe();
            $fermer_liste();
            $tableau[] = $ligne;
            continue;
        }
        $vider_tableau();

        if (trim($ligne) === '') {
            $vider_paragraphe();
            $fermer_liste();
            continue;
        }
        if (preg_match('/^\s*(-{3,}|\*{3,}|_{3,})\s*$/', $ligne)) {
            $vider_paragraphe();
            $fermer_liste();
            $html .= '<hr>';
            continue;
        }
        if (preg_match('/^(#{1,6})\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            $fermer_liste();
            $niveau = min(6, strlen($m[1]) + 1);
            $html .= "<h$niveau>" . md_ligne(trim($m[2]), $TYPES) . "</h$niveau>";
            continue;
        }
        if (preg_match('/^\s*>\s?(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            $fermer_liste();
            $html .= '<blockquote>' . md_ligne($m[1], $TYPES) . '</blockquote>';
            continue;
        }
        if (preg_match('/^\s*[-*+]\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            if ($liste !== 'ul') {
                $fermer_liste();
                $html .= '<ul>';
                $liste = 'ul';
            }
            $vider_item();
            $item = $m[1];
            continue;
        }
        if (preg_match('/^\s*\d+[.)]\s+(.*)$/', $ligne, $m)) {
            $vider_paragraphe();
            if ($liste !== 'ol') {
                $fermer_liste();
                $html .= '<ol>';
                $liste = 'ol';
            }
            $vider_item();
            $item = $m[1];
            continue;
        }
        // Suite d'un élément de liste replié sur plusieurs lignes.
        if ($item !== null) {
            $item .= ' ' . trim($ligne);
            continue;
        }
        $paragraphe[] = trim($ligne);
    }

    $vider_paragraphe();
    $fermer_liste();
    $vider_tableau();
    if ($code) {
        $html .= '</code></pre>';
    }
    return $html;
}

// ── fichier demandé ───────────────────────────────────────────────
// basename écarte tout chemin, et realpath vérifie que le fichier
// servi est bien dans le dossier des documents : deux verrous plutôt
// qu'un, la traversée de répertoire étant la faute classique ici.

$demande = isset($_GET['f']) ? basename((string) $_GET['f']) : '';
$fichier = null;
$mode = '';
if ($demande !== '' && isset($TYPES[extension($demande)]) && $racine) {
    $chemin = realpath($racine . '/' . $demande);
    if ($chemin && is_file($chemin) && strpos($chemin, $racine . '/') === 0) {
        $fichier = $chemin;
        $mode = $TYPES[extension($demande)][2];
    }
}

// Service direct : image, PDF, classeur, ou source brute d'un texte.
if ($fichier && ($mode === 'incorpore' || $mode === 'telecharge'
                 || isset($_GET['brut']))) {
    $type = $TYPES[extension($demande)][1];
    if (isset($_GET['brut'])) {
        $type = 'text/plain; charset=utf-8';
    }
    header('Content-Type: ' . $type);
    header('Content-Length: ' . filesize($fichier));
    header('X-Content-Type-Options: nosniff');
    if ($mode === 'telecharge' && !isset($_GET['brut'])) {
        header('Content-Disposition: attachment; filename="'
               . str_replace('"', '', $demande) . '"');
    }
    readfile($fichier);
    exit;
}

$documents = inventaire($base, $TYPES);
$titre = $fichier ? $demande : 'Documents de travail';
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title><?= htmlspecialchars($titre, ENT_QUOTES, 'UTF-8') ?></title>
<style>
:root{--paper:#EDF0EA;--surface:#FFF;--ink:#16211C;--soft:#5D6E64;
  --line:#D5DCD3;--accent:#2C6B4C;--sunken:#F5F7F3}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:20px 16px 60px;
  background:var(--paper);color:var(--ink);line-height:1.6}
main{max-width:860px;margin:0 auto}
a{color:var(--accent)}
h1{font-size:21px;margin:0 0 4px}
.chapeau{font-size:13px;color:var(--soft);margin:0 0 20px}
.retour{display:inline-block;font-size:13px;margin-bottom:14px;
  text-decoration:none}
.retour:hover{text-decoration:underline}
ul.docs{list-style:none;margin:0;padding:0}
ul.docs li{background:var(--surface);border:1px solid var(--line);
  border-radius:4px;margin-bottom:8px}
ul.docs a{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;
  padding:13px 14px;text-decoration:none;color:var(--ink)}
ul.docs a:hover{background:var(--sunken)}
.nom{font-weight:600;flex:1 1 auto;word-break:break-word}
.meta{font-size:12px;color:var(--soft);white-space:nowrap}
.vide{background:var(--surface);border:1px dashed var(--line);border-radius:4px;
  padding:18px;font-size:14px;color:var(--soft)}
article{background:var(--surface);border:1px solid var(--line);border-radius:4px;
  padding:18px 20px}
article h2{font-size:19px;margin:26px 0 8px;padding-bottom:5px;
  border-bottom:1px solid var(--line)}
article h3{font-size:16px;margin:22px 0 6px}
article h4,article h5,article h6{font-size:14px;margin:18px 0 4px}
article p,article li{font-size:15px}
article code{font-family:ui-monospace,monospace;font-size:13px;
  background:var(--sunken);padding:1px 4px;border-radius:3px}
article pre{background:var(--sunken);border:1px solid var(--line);
  border-radius:3px;padding:12px;overflow-x:auto}
article pre code{background:none;padding:0}
article blockquote{margin:10px 0;padding-left:12px;
  border-left:3px solid var(--line);color:var(--soft)}
article hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.deborde{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;font-size:14px;min-width:100%}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);
  vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--soft);white-space:nowrap}
.pied{margin-top:20px;font-size:12px;color:var(--soft)}
.pied a{margin-right:14px}
@media(max-width:520px){body{padding:14px 10px 50px}article{padding:14px}}
</style>
</head>
<body><main>
<?php if ($fichier) { ?>
<a class="retour" href="?">&larr; Tous les documents</a>
<h1><?= htmlspecialchars($demande, ENT_QUOTES, 'UTF-8') ?></h1>
<p class="chapeau">Modifié le
<?= date('d/m/Y à H\hi', filemtime($fichier)) ?> ·
<?= poids(filesize($fichier)) ?></p>
<article>
<?php
if ($mode === 'markdown') {
    echo markdown(file_get_contents($fichier), $TYPES);
} else {
    echo '<pre><code>'
        . htmlspecialchars(file_get_contents($fichier), ENT_QUOTES, 'UTF-8')
        . '</code></pre>';
}
?>
</article>
<p class="pied">
<a href="?f=<?= rawurlencode($demande) ?>&amp;brut=1">Voir la source</a>
<a href="?">Retour à la liste</a></p>
<?php } else { ?>
<a class="retour" href="index.html">&larr; Administration</a>
<h1>Documents de travail</h1>
<p class="chapeau"><?= count($documents) ?> document(s) dans le dossier
<code>Documents</code>. Lecture seule : l'ajout et la mise à jour
passent par le dépôt.</p>
<?php if (!$documents) { ?>
<p class="vide">Aucun document lisible dans ce dossier. Seules les
extensions déclarées dans cette page y sont listées — un fichier d'un
autre type n'apparaîtra pas, même présent.</p>
<?php } else { ?>
<ul class="docs">
<?php foreach ($documents as $d) { ?>
  <li><a href="?f=<?= rawurlencode($d['nom']) ?>">
    <span class="nom"><?= htmlspecialchars($d['nom'], ENT_QUOTES, 'UTF-8') ?></span>
    <span class="meta"><?= htmlspecialchars($d['type'], ENT_QUOTES, 'UTF-8') ?>
      · <?= poids($d['taille']) ?>
      · <?= date('d/m/Y', $d['date']) ?></span>
  </a></li>
<?php } ?>
</ul>
<?php } ?>
<p class="pied">Ces documents sont internes. Ils ne contiennent ni mot de
passe ni clé : ceux-ci n'ont leur place ni ici, ni dans le dépôt.</p>
<?php } ?>
</main></body>
</html>
