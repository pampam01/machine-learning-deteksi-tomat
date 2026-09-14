<?php
ob_start(); // Buffer output agar PHP warning tidak merusak HTML
$base_path = dirname(__DIR__);
$current_page = basename($_SERVER['PHP_SELF'], '.php');

// Fallback jika BASE_URL belum didefinisikan (Case-insensitive support for Windows XAMPP)
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
$css_path = $base_path . '/assets/css/style.css';
$css_ver = file_exists($css_path) ? filemtime($css_path) : time();
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Sistem IoT Klasifikasi Kematangan Tomat - Decision Tree C4.5">
    <title>Tomata IoT - Klasifikasi Tomat</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css?v=<?= $css_ver ?>">
</head>
<body>
    <!-- Sidebar -->
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <div class="sidebar-logo">
                <span class="logo-icon">🍅</span>
                <h1>Tomata IoT</h1>
            </div>
            <button class="sidebar-toggle" id="sidebarToggle" aria-label="Toggle Sidebar">
                <span></span>
                <span></span>
                <span></span>
            </button>
        </div>

        <ul class="sidebar-menu">
            <li class="<?= $current_page === 'dashboard' ? 'active' : '' ?>">
                <a href="<?= BASE_URL ?>/pages/dashboard.php">
                    <span class="menu-icon">📊</span>
                    <span class="menu-text">Dashboard</span>
                </a>
            </li>
            <li class="<?= $current_page === 'riwayat' ? 'active' : '' ?>">
                <a href="<?= BASE_URL ?>/pages/riwayat.php">
                    <span class="menu-icon">📋</span>
                    <span class="menu-text">Riwayat</span>
                </a>
            </li>
            <li class="<?= $current_page === 'rekap-harian' ? 'active' : '' ?>">
                <a href="<?= BASE_URL ?>/pages/rekap-harian.php">
                    <span class="menu-icon">📅</span>
                    <span class="menu-text">Rekap Harian</span>
                </a>
            </li>
            <li class="<?= $current_page === 'data-admin' ? 'active' : '' ?>">
                <a href="<?= BASE_URL ?>/pages/data-admin.php">
                    <span class="menu-icon">👤</span>
                    <span class="menu-text">Data Admin</span>
                </a>
            </li>
        </ul>

        <div class="sidebar-footer">
            <div class="admin-info">
                <span class="admin-icon">👤</span>
                <span class="admin-name"><?= htmlspecialchars($_SESSION['admin_nama'] ?? 'Admin') ?></span>
            </div>
            <a href="<?= BASE_URL ?>/logout.php" class="btn-logout">
                <span class="logout-icon">🚪</span>
                <span class="menu-text">Logout</span>
            </a>
        </div>
    </nav>

    <!-- Overlay untuk mobile -->
    <div class="sidebar-overlay" id="sidebarOverlay"></div>

    <!-- Konten Utama -->
    <main class="main-content" id="mainContent">
        <div class="content-wrapper">
