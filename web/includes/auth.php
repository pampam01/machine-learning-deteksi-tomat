<?php
session_start();

// Set timezone & region (UTC +7 / Asia/Jakarta, Indonesia)
date_default_timezone_set('Asia/Jakarta');
ini_set('date.timezone', 'Asia/Jakarta');
setlocale(LC_ALL, 'id_ID.utf8', 'id_ID', 'ind', 'Indonesian');

// Define Base URL dynamically (Case-insensitive support for Windows XAMPP)
if (!defined('BASE_URL')) {
    $raw_doc_root = $_SERVER['DOCUMENT_ROOT'] ?? '';
    $raw_proj_dir = dirname(__DIR__);
    $doc_root = rtrim(str_replace('\\', '/', realpath($raw_doc_root) ?: $raw_doc_root), '/');
    $project_dir = rtrim(str_replace('\\', '/', realpath($raw_proj_dir) ?: $raw_proj_dir), '/');
    
    if (!empty($doc_root) && stripos($project_dir, $doc_root) === 0) {
        $base_url = substr($project_dir, strlen($doc_root));
    } else {
        $script_dir = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? ''));
        $pos = strpos($script_dir, '/pages');
        if ($pos !== false) {
            $base_url = substr($script_dir, 0, $pos);
        } elseif (strpos($script_dir, '/api') !== false) {
            $base_url = substr($script_dir, 0, strpos($script_dir, '/api'));
        } else {
            $base_url = $script_dir === '/' ? '' : $script_dir;
        }
    }
    define('BASE_URL', rtrim($base_url, '/'));
}

/**
 * Cek apakah user sudah login
 */
function isLoggedIn() {
    return isset($_SESSION['admin_id']) && !empty($_SESSION['admin_id']);
}

/**
 * Redirect ke login jika belum login
 */
function requireLogin() {
    if (!isLoggedIn()) {
        header('Location: ' . BASE_URL . '/pages/login');
        exit();
    }
}

/**
 * Redirect ke dashboard jika sudah login
 */
function redirectIfLoggedIn() {
    if (isLoggedIn()) {
        header('Location: ' . BASE_URL . '/pages/dashboard');
        exit();
    }
}
?>
