<?php
// The database of the game server, shared by api.php and check.php.
// Written for PHP 7.4 and newer, like api.php.

const SQLITE_FILE = __DIR__ . '/data/games.sqlite';

function database(): PDO
{
    // config.php (never in git) sets $dsn, $user and $password for MariaDB on the host.
    // Without it, an SQLite file in data/, a folder that data/.htaccess hides from browsers.
    $dsn = null;
    $user = null;
    $password = null;
    if (file_exists(__DIR__ . '/config.php')) {
        require __DIR__ . '/config.php';
    }
    if ($dsn === null) {
        $file = getenv('SCHLURP_SQLITE') ?: SQLITE_FILE;
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
