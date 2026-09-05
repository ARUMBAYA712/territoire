<?php
// Page-appât. Elle ne donne accès à rien : sa seule fonction est
// d'occuper une tentative d'intrusion et d'en conserver la trace.
//
// L'adresse du visiteur est tronquée avant écriture. Aucun identifiant
// ni mot de passe saisi n'est enregistré.

$journal = __DIR__ . '/journal-acces.log';
$retention = 90;
$attente = 3;

function adresse_tronquee() {
    $brut = $_SERVER['REMOTE_ADDR'] ?? '';
    if (strpos($brut, ':') !== false) {
        $blocs = explode(':', $brut);
        return implode(':', array_slice($blocs, 0, 3)) . ':...';
    }
    $blocs = explode('.', $brut);
    if (count($blocs) === 4) {
        $blocs[3] = 'x';
        return implode('.', $blocs);
    }
    return 'inconnue';
}

function propre($texte, $taille = 180) {
    $texte = preg_replace('/[\r\n\t;]+/', ' ', (string) $texte);
    return substr(trim($texte), 0, $taille);
}

// ── purge des entrées trop anciennes ──
if (is_file($journal) && filesize($journal) > 0) {
    $limite = time() - $retention * 86400;
    $gardees = [];
    foreach (file($journal, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $ligne) {
        $date = strtotime(substr($ligne, 0, 19));
        if ($date && $date >= $limite) { $gardees[] = $ligne; }
    }
    if (count($gardees) > 5000) { $gardees = array_slice($gardees, -5000); }
    file_put_contents($journal, implode("\n", $gardees) . "\n", LOCK_EX);
}

$entree = implode(';', [
    date('Y-m-d H:i:s'),
    adresse_tronquee(),
    propre($_SERVER['REQUEST_METHOD'] ?? '', 8),
    propre($_SERVER['REQUEST_URI'] ?? '', 120),
    propre($_SERVER['HTTP_REFERER'] ?? '-', 120),
    propre($_SERVER['HTTP_USER_AGENT'] ?? '-', 180),
]);
@file_put_contents($journal, $entree . "\n", FILE_APPEND | LOCK_EX);

// Attente délibérée : elle ralentit les outils de balayage, qui
// enchaînent des milliers d'adresses, sans gêner un visiteur égaré.
sleep($attente);

$echec = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
header('X-Robots-Tag: noindex, nofollow');
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Administration</title>
<style>
body{background:#12161a;color:#c9d3da;font-family:system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;
  margin:0;padding:24px}
main{background:#1a2026;border:1px solid #2c353d;border-radius:6px;
  padding:28px;max-width:360px;width:100%}
h1{font-size:17px;margin:0 0 4px}
p{font-size:13px;color:#8b98a3;line-height:1.5}
label{display:block;font-size:12px;margin:14px 0 4px;color:#8b98a3}
input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:4px;
  border:1px solid #2c353d;background:#12161a;color:#c9d3da;font:inherit}
button{margin-top:18px;width:100%;padding:10px;border:0;border-radius:4px;
  background:#2f6b4f;color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{margin-top:14px;padding:9px 11px;border-radius:4px;
  background:#3a1f1c;border:1px solid #6b2f26;color:#e2b4ad;font-size:13px}
</style>
</head>
<body>
<main>
  <h1>Espace d'administration</h1>
  <p>Accès réservé. Toute tentative de connexion est enregistrée.</p>
  <?php if ($echec) { ?>
  <div class="err">Identifiants incorrects. Nouvel essai possible dans quelques instants.</div>
  <?php } ?>
  <form method="post" autocomplete="off">
    <label for="u">Identifiant</label>
    <input id="u" name="u" type="text">
    <label for="p">Mot de passe</label>
    <input id="p" name="p" type="password">
    <button type="submit">Se connecter</button>
  </form>
</main>
</body>
</html>
