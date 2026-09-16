<?php
/**
 * Router untuk PHP Built-in Web Server (Development Local)
 * Meniru perilaku Apache mod_rewrite agar pretty URLs (.php hilang) berfungsi di localhost
 * Cara pakai: php -S 0.0.0.0:8000 router.php
 */

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$doc_root = __DIR__;
$file = $doc_root . $uri;

// 1. Jika request langsung ke file nyata yang ada (css, js, gambar, dsb.)
if (is_file($file)) {
    return false; // Sajikan file secara native
}

// 2. Jika request tanpa ekstensi .php tapi ada file .php nya
if (is_file($file . '.php')) {
    require $file . '.php';
    exit();
}

// 3. Jika request di dalam folder /web/
if (strpos($uri, '/web/') === 0) {
    $sub = substr($uri, 5); // buang '/web/'
    if (is_file($doc_root . '/web/' . $sub . '.php')) {
        require $doc_root . '/web/' . $sub . '.php';
        exit();
    }
}

// 4. Handle root / atau /web/
if ($uri === '/' || $uri === '/web' || $uri === '/web/') {
    require __DIR__ . '/web/index.php';
    exit();
}

// 5. Default fallback ke file
return false;
