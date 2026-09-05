<?php
// Assistant de protection — À SUPPRIMER une fois la protection en place.
//
// Il chiffre un mot de passe avec les fonctions du serveur, ce qui
// garantit la compatibilité avec Apache, et compose les deux fichiers
// à créer. Le mot de passe saisi n'est ni enregistré ni transmis.

header('X-Robots-Tag: noindex, nofollow');
$dossier = __DIR__;
$identifiant = trim($_POST['u'] ?? '');
$motdepasse = $_POST['p'] ?? '';
$empreinte = '';
$erreur = '';

if ($identifiant !== '' && $motdepasse !== '') {
    if (strlen($motdepasse) < 12) {
        $erreur = 'Choisissez un mot de passe d\'au moins 12 caractères.';
    } elseif (!preg_match('/^[A-Za-z0-9_.-]+$/', $identifiant)) {
        $erreur = 'Identifiant : lettres, chiffres, point, tiret ou souligné.';
    } else {
        $empreinte = password_hash($motdepasse, PASSWORD_BCRYPT);
    }
}
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Protéger cette section</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#EDF0EA;
  color:#16211C}
main{max-width:760px;margin:0 auto}
h1{font-size:20px}
h2{font-size:15px;margin-top:26px}
p,li{font-size:14px;line-height:1.55;color:#5D6E64}
code,pre{font-family:ui-monospace,monospace;font-size:12px}
pre{background:#fff;border:1px solid #D5DCD3;border-radius:3px;padding:12px;
  overflow:auto;white-space:pre-wrap;word-break:break-all;color:#16211C}
label{display:block;font-size:13px;margin:12px 0 4px}
input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:3px;
  border:1px solid #D5DCD3;font:inherit}
button{margin-top:16px;padding:10px 20px;border:0;border-radius:3px;
  background:#2C6B4C;color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{background:#FBEAE7;border:1px solid #A32C1B;color:#A32C1B;padding:9px 11px;
  border-radius:3px;font-size:13px;margin-top:14px}
.ok{background:#EAF3EE;border:1px solid #2C6B4C;padding:12px;border-radius:3px}
</style>
</head>
<body><main>
<h1>Protéger cette section par mot de passe</h1>
<p>Le chiffrement est fait par le serveur, ce qui garantit la compatibilité
avec Apache. Le mot de passe saisi n'est ni enregistré ni transmis ailleurs.</p>

<?php if ($erreur) { ?><div class="err"><?= htmlspecialchars($erreur) ?></div><?php } ?>

<?php if ($empreinte === '') { ?>
<form method="post" autocomplete="off">
  <label for="u">Identifiant</label>
  <input id="u" name="u" type="text" value="<?= htmlspecialchars($identifiant) ?>">
  <label for="p">Mot de passe — 12 caractères au moins</label>
  <input id="p" name="p" type="password">
  <button type="submit">Chiffrer</button>
</form>
<?php } else { ?>
<div class="ok">
<h2>1. Créez le fichier <code>.htpasswd</code> dans ce dossier</h2>
<pre><?= htmlspecialchars($identifiant . ':' . $empreinte) ?></pre>

<h2>2. Créez le fichier <code>.htaccess</code> dans ce dossier</h2>
<pre>AuthType Basic
AuthName "Administration Sud Gresiv"
AuthUserFile <?= htmlspecialchars($dossier) ?>/.htpasswd
Require valid-user

&lt;FilesMatch "^\.ht"&gt;
    Require all denied
&lt;/FilesMatch&gt;</pre>

<h2>3. Envoyez les deux fichiers, puis supprimez celui-ci</h2>
<p>Ajoutez <code>.htpasswd</code> et <code>.htaccess</code> à votre dépôt,
publiez, vérifiez que l'accès demande bien un mot de passe, puis
<strong>supprimez <code>chiffrer.php</code></strong> du dépôt et du serveur.</p>
<p>Le fichier <code>.htpasswd</code> ne contient qu'une empreinte, non le
mot de passe. Il doit néanmoins rester dans un dépôt privé.</p>
</div>
<?php } ?>
</main></body>
</html>
