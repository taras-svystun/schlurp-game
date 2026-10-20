<?php
// A page that checks whether this server can run the game, for whoever installs it (Pascal, in French).
// The first checks run here in PHP; the last ones run in the browser, because only a browser can tell
// whether data/ is really hidden and whether the page can reach the game server and Pyodide's CDN.
// Each check is a line with data-check and data-ok ("yes", "warn" or "no"), which the tests read.
// Written for PHP 7.4 and newer, but it must also run on an older PHP, to say that it is too old.

$checks = [];

function check($name, $ok, $label, $detail)
{
    global $checks;
    $checks[] = ['name' => $name, 'ok' => $ok, 'label' => $label, 'detail' => $detail];
}

if (version_compare(PHP_VERSION, '7.4', '>=')) {
    check('php', 'yes', 'Version de PHP', PHP_VERSION);
} elseif (version_compare(PHP_VERSION, '7.1', '>=')) {
    check('php', 'warn', 'Version de PHP', PHP_VERSION . ' : devrait marcher, mais testé seulement à partir de 7.4');
} else {
    check('php', 'no', 'Version de PHP', PHP_VERSION . ' : il faut au moins 7.1, et de préférence 7.4');
}

check('json', function_exists('json_encode') ? 'yes' : 'no', 'Extension JSON', function_exists('json_encode') ? 'présente' : 'absente');

$random = false;
try {
    $random = function_exists('random_bytes') && strlen(random_bytes(16)) === 16;
} catch (Exception $error) {
}
check('random', $random ? 'yes' : 'no', 'Nombres aléatoires sûrs (random_bytes)', $random ? 'disponibles' : 'indisponibles');

$drivers = class_exists('PDO') ? PDO::getAvailableDrivers() : [];
$uses_config = file_exists(__DIR__ . '/config.php');
$driver = $uses_config ? 'mysql' : 'sqlite';
$kind = $uses_config ? 'MariaDB (config.php)' : 'SQLite (fichier data/games.sqlite)';
check(
    'pdo',
    in_array($driver, $drivers, true) ? 'yes' : 'no',
    'PDO pour ' . $kind,
    $drivers ? 'pilotes présents : ' . implode(', ', $drivers) : 'PDO absent'
);

if (!$uses_config) {
    $writable = is_dir(__DIR__ . '/data') && is_writable(__DIR__ . '/data');
    check('writable', $writable ? 'yes' : 'no', 'Dossier data/ accessible en écriture', $writable ? 'oui' : 'non : donner le droit d\'écriture à PHP sur data/');
}

// The real test: open the database, create the tables, and write and delete one line.
$database = 'no';
$database_detail = '';
if (in_array($driver, $drivers, true)) {
    try {
        require __DIR__ . '/database.php';
        $db = database();
        $db->prepare('INSERT INTO games (id, first_player, blue_secret, green_secret, updated) VALUES (?, ?, ?, ?, ?)')
            ->execute(['check', 'blue', '', '', 0]);
        $db->prepare('DELETE FROM games WHERE id = ?')->execute(['check']);
        $database = 'yes';
        $database_detail = 'lecture et écriture réussies';
    } catch (Throwable $error) {
        $database_detail = $error->getMessage();
    }
} else {
    $database_detail = 'impossible sans le pilote PDO ci-dessus';
}
check('database', $database, 'Base de données', $database_detail);

// A file only the browser test below may find; if it can read it, so could anyone.
$probe = @file_put_contents(__DIR__ . '/data/probe.txt', 'visible') !== false;

$problems = count(array_filter($checks, function ($c) { return $c['ok'] === 'no'; }));
$colours = ['yes' => '#2f9e44', 'warn' => '#e8890c', 'no' => '#e03131'];
$marks = ['yes' => '✔', 'warn' => '!', 'no' => '✘'];
?>
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Schlurp : vérification du serveur</title>
  <link rel="icon" href="data:,">
  <style>
    body { margin: 0; padding: 16px; background: #0c0f14; color: #e2e8e4; font: 16px/1.5 system-ui, sans-serif; }
    main { max-width: 760px; margin: 0 auto; }
    li { margin: 6px 0; list-style: none; }
    .mark { display: inline-block; width: 1.4em; font-weight: 700; }
    .detail { color: #8c9c96; }
    #summary { font-weight: 600; }
  </style>
</head>
<body>
<main>
  <h1>Schlurp : vérification du serveur</h1>
<?php if (file_exists(__DIR__ . '/version.txt')): ?>
  <p class="detail">Version : <?= htmlspecialchars(trim(file_get_contents(__DIR__ . '/version.txt'))) ?></p>
<?php endif; ?>
  <p id="summary"><?= $problems ? "Il y a $problems problème(s) côté PHP, en rouge ci-dessous." : 'Côté PHP, tout est prêt.' ?></p>
  <h2>Côté serveur (PHP)</h2>
  <ul>
<?php foreach ($checks as $c): ?>
    <li data-check="<?= $c['name'] ?>" data-ok="<?= $c['ok'] ?>"><span class="mark" style="color: <?= $colours[$c['ok']] ?>"><?= $marks[$c['ok']] ?></span><?= htmlspecialchars($c['label']) ?> <span class="detail">— <?= htmlspecialchars($c['detail']) ?></span></li>
<?php endforeach; ?>
  </ul>
  <h2>Côté navigateur</h2>
  <ul id="browser">
    <li data-check="hidden" data-ok="wait"><span class="mark">…</span>Le dossier data/ est caché aux navigateurs <span class="detail"></span></li>
    <li data-check="api" data-ok="wait"><span class="mark">…</span>Le serveur de jeu (api.php) répond <span class="detail"></span></li>
    <li data-check="zip" data-ok="wait"><span class="mark">…</span>Le moteur du jeu (build/schlurp.zip) est là <span class="detail"></span></li>
    <li data-check="cdn" data-ok="wait"><span class="mark">…</span>Pyodide est joignable sur cdn.jsdelivr.net <span class="detail"></span></li>
  </ul>
  <p class="detail">Quand tout est vert, ouvre <a href="./" style="color: inherit">la page du jeu</a>. Cette page de vérification peut rester : elle ne montre rien de secret.</p>
</main>
<script>
  const colours = <?= json_encode($colours) ?>;
  const marks = <?= json_encode($marks) ?>;
  function show(name, ok, detail) {
    const line = document.querySelector(`[data-check="${name}"]`);
    line.dataset.ok = ok;
    const mark = line.querySelector(".mark");
    mark.textContent = marks[ok];
    mark.style.color = colours[ok];
    line.querySelector(".detail").textContent = `— ${detail}`;
  }
  async function status(url, options) {
    try {
      const response = await fetch(url, { cache: "no-store", ...options });
      return { code: response.status, text: await response.text() };
    } catch (error) {
      return { code: 0, text: error.message };
    }
  }
  (async () => {
    const probe = await status("data/probe.txt");
    <?php if (!$probe): ?>
    show("hidden", "warn", "pas pu être vérifié, car PHP ne peut pas écrire dans data/");
    <?php else: ?>
    if (probe.code === 200 && probe.text === "visible") {
      show("hidden", "no", "non : le fichier data/.htaccess n'est pas appliqué (AllowOverride ?). La base serait lisible par tous.");
    } else {
      show("hidden", "yes", `oui (réponse ${probe.code})`);
    }
    <?php endif; ?>
    const api = await status("api.php?action=game&game=check");
    let answer = null;
    try { answer = JSON.parse(api.text); } catch (error) {}
    show("api", api.code === 404 && answer && answer.error ? "yes" : "no", api.code === 404 && answer ? "oui" : `réponse inattendue ${api.code} : ${api.text.slice(0, 120)}`);
    const zip = await status("build/schlurp.zip", { method: "HEAD" });
    show("zip", zip.code === 200 ? "yes" : "no", zip.code === 200 ? "oui" : `non (réponse ${zip.code})`);
    const cdn = await status("https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs", { method: "HEAD" });
    show("cdn", cdn.code === 200 ? "yes" : "no", cdn.code === 200 ? "oui" : "non : le jeu a besoin d'Internet dans le navigateur");
    const all = [...document.querySelectorAll("[data-check]")].map((line) => line.dataset.ok);
    const bad = all.filter((ok) => ok === "no").length;
    document.getElementById("summary").textContent = bad
      ? `Il y a ${bad} problème(s), en rouge ci-dessous.`
      : "Tout est prêt : le jeu peut tourner sur ce serveur.";
  })();
</script>
</body>
</html>
