<?php
// For PHP's own web server only (`schlurp web` and the tests): it does not read .htaccess files,
// so this does what web/data/.htaccess does under Apache. It lives outside web/, so it is never installed.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (preg_match('#^/(data/|config\.php)#', $path)) {
    http_response_code(403);
    echo 'Forbidden';
    return true;
}
return false;  // anything else: served as usual
