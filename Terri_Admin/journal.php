<?php
// Lecture du journal du leurre. Même réserve que pour le reste de cette
// section : discrétion, pas protection. Protégez le dossier par mot de
// passe depuis l'espace client OVH si vous souhaitez le fermer.
header('X-Robots-Tag: noindex, nofollow');
$journal = __DIR__ . '/../administration/journal-acces.log';
$lignes = is_file($journal)
    ? array_reverse(file($journal, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES))
    : [];
$total = count($lignes);
$lignes = array_slice($lignes, 0, 200);
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Journal du leurre</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#EDF0EA;
  color:#16211C}
h1{font-family:sans-serif;font-size:20px}
p{font-size:13px;color:#5D6E64}
table{width:100%;border-collapse:collapse;font-size:12px;background:#fff;
  margin-top:16px}
th{text-align:left;padding:6px 8px;font-size:10px;text-transform:uppercase;
  letter-spacing:.06em;color:#5D6E64;border-bottom:1px solid #D5DCD3}
td{padding:5px 8px;border-top:1px solid #EDF0EA;font-family:monospace;
  word-break:break-all}
</style>
</head>
<body>
<h1>Journal du leurre</h1>
<p><?= $total ?> tentative(s) conservée(s), 200 dernières affichées.
Les adresses sont tronquées de leur dernier segment. Conservation :
90 jours.</p>
<table>
<tr><th>Date</th><th>Adresse</th><th>Méthode</th><th>Chemin</th>
<th>Provenance</th><th>Agent</th></tr>
<?php foreach ($lignes as $ligne) {
    $c = array_pad(explode(';', $ligne), 6, '');
    echo '<tr>';
    foreach ($c as $valeur) {
        echo '<td>' . htmlspecialchars($valeur, ENT_QUOTES, 'UTF-8') . '</td>';
    }
    echo '</tr>';
} ?>
</table>
</body>
</html>
