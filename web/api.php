<?php
// The game server: stores the moves of online games and passes them from one browser to the other.
// It does not know the rules: each browser checks every move with our engine (see docs/adr/0005).
// Written for PHP 7.4 and newer, because we do not know yet which PHP the host runs.
//
// Requests, all answered in JSON:
//   POST api.php?action=create  {"first": "blue"}
//        A new game. Answers {"game": id, "first": "blue", "secrets": {"blue": ..., "green": ...}}.
//        Each secret goes into one player's game link; only its holder can move for that player.
//   POST api.php?action=move    {"game": id, "secret": ..., "number": 0, "move": "a1c3"}
//        Move number `number` (the first move is 0) by the player the secret belongs to.
//        Taken only if the game has exactly `number` moves so far, so a move is never stored twice.
//        Answers {"moves": total}.
//   GET  api.php?action=game&game=id&after=0[&secret=...]
//        The game's first player and its moves from number `after` on, each with the player who sent it,
//        and, with a secret, which player it belongs to. Browsers ask this about once a second.
// An error answers {"error": message} with an HTTP status: 400 bad request, 403 wrong secret,
// 404 no such game, 405 wrong method, 409 the move number is taken or skipped, 500 server problem.

const PLAYERS = ['blue', 'green'];
// Far more moves than any game has: clones fill the board and the fifty-move rule stops endless jumps.
const MOVES_PER_GAME = 5000;
// Games nobody moved in for this long are deleted when a new game is made.
const KEEP_GAMES_FOR_SECONDS = 30 * 24 * 3600;

class Problem extends Exception
{
}

function answer(int $status, array $body): void
{
    http_response_code($status);
    header('Content-Type: application/json');
    header('Cache-Control: no-store');
    echo json_encode($body);
}

function database(): PDO
{
    // config.php (never in git) sets $dsn, $user and $password for MariaDB on the host.
    // Without it, an SQLite file: on Taras's laptop and in the tests.
    $dsn = null;
    $user = null;
    $password = null;
    if (file_exists(__DIR__ . '/config.php')) {
        require __DIR__ . '/config.php';
    }
    if ($dsn === null) {
        $file = getenv('SCHLURP_SQLITE') ?: __DIR__ . '/../records/web-games.sqlite';
        if (!is_dir(dirname($file))) {
            mkdir(dirname($file), 0777, true);
        }
        $dsn = 'sqlite:' . $file;
    }
    $db = new PDO($dsn, $user, $password, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    // Plain SQL that both MariaDB and SQLite accept.
    $db->exec('CREATE TABLE IF NOT EXISTS games (
        id VARCHAR(16) PRIMARY KEY,
        first_player VARCHAR(5) NOT NULL,  -- not `first`, a keyword in MariaDB
        blue_secret VARCHAR(32) NOT NULL,
        green_secret VARCHAR(32) NOT NULL,
        updated BIGINT NOT NULL
    )');
    // The primary key stops two moves with the same number, even when two requests come at once.
    $db->exec('CREATE TABLE IF NOT EXISTS moves (
        game VARCHAR(16) NOT NULL,
        number INTEGER NOT NULL,
        player VARCHAR(5) NOT NULL,
        move VARCHAR(4) NOT NULL,
        PRIMARY KEY (game, number)
    )');
    return $db;
}

function body(): array
{
    $body = json_decode(file_get_contents('php://input'), true);
    if (!is_array($body)) {
        throw new Problem('The request body must be a JSON object', 400);
    }
    return $body;
}

function find_game(PDO $db, $id): array
{
    $query = $db->prepare('SELECT * FROM games WHERE id = ?');
    $query->execute([(string) $id]);
    $game = $query->fetch(PDO::FETCH_ASSOC);
    if (!$game) {
        throw new Problem('There is no such game', 404);
    }
    return $game;
}

// The player a secret belongs to, or null. hash_equals takes the same time for any wrong secret.
function player_of(array $game, $secret): ?string
{
    foreach (PLAYERS as $player) {
        if (is_string($secret) && hash_equals($game[$player . '_secret'], $secret)) {
            return $player;
        }
    }
    return null;
}

function count_moves(PDO $db, string $game): int
{
    $query = $db->prepare('SELECT COUNT(*) FROM moves WHERE game = ?');
    $query->execute([$game]);
    return (int) $query->fetchColumn();
}

function create(PDO $db): array
{
    $first = body()['first'] ?? 'blue';
    if (!in_array($first, PLAYERS, true)) {
        throw new Problem('Who moves first must be blue or green', 400);
    }
    $old = $db->prepare('SELECT id FROM games WHERE updated < ?');
    $old->execute([time() - KEEP_GAMES_FOR_SECONDS]);
    foreach ($old->fetchAll(PDO::FETCH_COLUMN) as $id) {
        $db->prepare('DELETE FROM moves WHERE game = ?')->execute([$id]);
        $db->prepare('DELETE FROM games WHERE id = ?')->execute([$id]);
    }
    $id = bin2hex(random_bytes(8));
    $secrets = ['blue' => bin2hex(random_bytes(16)), 'green' => bin2hex(random_bytes(16))];
    $db->prepare('INSERT INTO games (id, first_player, blue_secret, green_secret, updated) VALUES (?, ?, ?, ?, ?)')
        ->execute([$id, $first, $secrets['blue'], $secrets['green'], time()]);
    return ['game' => $id, 'first' => $first, 'secrets' => $secrets];
}

function move(PDO $db): array
{
    $body = body();
    $game = find_game($db, $body['game'] ?? '');
    $player = player_of($game, $body['secret'] ?? null);
    if ($player === null) {
        throw new Problem('This secret does not belong to a player of this game', 403);
    }
    $move = $body['move'] ?? null;
    $number = $body['number'] ?? null;
    if (!is_string($move) || !preg_match('/^[a-g][1-7]([a-g][1-7])?$/', $move)) {
        throw new Problem("A move is written like 'c3' or 'a1c3'", 400);
    }
    if (!is_int($number) || $number < 0 || $number >= MOVES_PER_GAME) {
        throw new Problem('The move number must be a whole number from 0', 400);
    }
    $total = count_moves($db, $game['id']);
    if ($number !== $total) {
        throw new Problem("The game has $total moves, so the next one is number $total", 409);
    }
    try {
        $db->prepare('INSERT INTO moves (game, number, player, move) VALUES (?, ?, ?, ?)')
            ->execute([$game['id'], $number, $player, $move]);
    } catch (PDOException $taken) {
        throw new Problem("Move number $number was just taken", 409);
    }
    $db->prepare('UPDATE games SET updated = ? WHERE id = ?')->execute([time(), $game['id']]);
    return ['moves' => $total + 1];
}

function game(PDO $db): array
{
    $game = find_game($db, $_GET['game'] ?? '');
    $after = filter_var($_GET['after'] ?? 0, FILTER_VALIDATE_INT, ['options' => ['min_range' => 0]]);
    if ($after === false) {
        throw new Problem('after must be a whole number from 0', 400);
    }
    $query = $db->prepare('SELECT number, player, move FROM moves WHERE game = ? AND number >= ? ORDER BY number');
    $query->execute([$game['id'], $after]);
    $moves = [];
    foreach ($query->fetchAll(PDO::FETCH_ASSOC) as $row) {
        $moves[] = ['number' => (int) $row['number'], 'player' => $row['player'], 'move' => $row['move']];
    }
    $state = ['game' => $game['id'], 'first' => $game['first_player'], 'moves' => $moves];
    if (isset($_GET['secret'])) {
        $state['you'] = player_of($game, $_GET['secret']);
    }
    return $state;
}

$actions = ['create' => 'POST', 'move' => 'POST', 'game' => 'GET'];
try {
    $action = $_GET['action'] ?? '';
    if (!isset($actions[$action])) {
        throw new Problem('Unknown action: use create, move or game', 400);
    }
    if ($_SERVER['REQUEST_METHOD'] !== $actions[$action]) {
        throw new Problem("$action needs a {$actions[$action]} request", 405);
    }
    answer(200, $action(database()));
} catch (Problem $problem) {
    answer($problem->getCode(), ['error' => $problem->getMessage()]);
} catch (Throwable $crash) {
    error_log((string) $crash);  // the details go to the server's log, never to the browser
    answer(500, ['error' => 'The server had a problem']);
}
