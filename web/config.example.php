<?php
// Copy this file to config.php on the server and fill it in. config.php is never in git: it holds a password.
// Without config.php the game server uses an SQLite file in data/, which is enough for a small site.
$dsn = 'mysql:host=localhost;dbname=schlurp;charset=utf8mb4';
$user = 'schlurp';
$password = 'the password of the database user';
