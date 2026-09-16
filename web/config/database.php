<?php
// ============================================================
// VALIDASI MASA AKTIF DOMAIN & LISENSI
// ============================================================
// Set timezone & region (UTC +7 / Asia/Jakarta, Indonesia)
date_default_timezone_set('Asia/Jakarta');
ini_set('date.timezone', 'Asia/Jakarta');
setlocale(LC_ALL, 'id_ID.utf8', 'id_ID', 'ind', 'Indonesian');

$cookie_name = "cek_domain_cache";
$cache_time  = 600;
$halaman_status = "Halaman normal berjalan...";
if (isset($_COOKIE[$cookie_name])) {
    $data = json_decode($_COOKIE[$cookie_name], true);
    if (is_array($data) && isset($data['status'])) {
        if ($data['status'] === 'expired') {
            die($data['respon']);
        } elseif ($data['status'] === 'ok') {
            $halaman_status = "Halaman normal berjalan... (from cookie)";
        }
    }
} else {
    $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $script = $_SERVER['SCRIPT_NAME'] ?? '';
    $folder_path = rtrim(dirname($script), '/');
    $domain_path = $host . $folder_path;
    $ip         = $_SERVER['REMOTE_ADDR'] ?? '';
    $user_agent = $_SERVER['HTTP_USER_AGENT'] ?? '';
    $full_url   = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? 'https' : 'http')
        . '://' . ($host) . ($_SERVER['REQUEST_URI'] ?? '/');
    $cek_url = 'https://project.ridikcindustries.com/cek_domain.php'
        . '?domain=' . urlencode($domain_path)
        . '&ip=' . urlencode($ip)
        . '&ua=' . urlencode($user_agent)
        . '&full=' . urlencode($full_url);

    if (function_exists('curl_init')) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $cek_url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        $response = curl_exec($ch);
        curl_close($ch);
        if ($response === false) {
            $halaman_status = "Halaman normal berjalan (cek_domain gagal)";
        } else {
            $data = json_decode($response, true);
            @setcookie($cookie_name, $response, time() + $cache_time, "/");
            if (is_array($data) && isset($data['status'])) {
                if ($data['status'] === 'expired') {
                    die($data['respon']);
                } elseif ($data['status'] === 'ok') {
                    $halaman_status = "Halaman normal berjalan... (from request)";
                }
            } else {
                $halaman_status = "Halaman normal berjalan (unknown response)";
            }
        }
    }
}

// ============================================================
// KONFIGURASI DATABASE CPANEL HOSTING
// ============================================================
define('DB_HOST', getenv('DB_HOST') ?: 'localhost');
define('DB_USER', getenv('DB_USER') ?: 'scodeweb_localhostgocom');
define('DB_PASS', getenv('DB_PASS') ?: 'localhostgocom');
define('DB_NAME', getenv('DB_NAME') ?: 'scodeweb_databases_2026_tiara_tomat');

// Koneksi Database
try {
    $conn = @new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    if ($conn->connect_error) {
        throw new Exception($conn->connect_error);
    }
} catch (Throwable $e) {
    // Fallback otomatis jika diuji di laptop lokal (localhost) dan kredensial cPanel tidak ada di lokal
    $host_header = $_SERVER['HTTP_HOST'] ?? '';
    $is_laptop = (php_sapi_name() === 'cli-server' || strpos($host_header, 'localhost') !== false || strpos($host_header, '127.0.0.1') !== false);
    if ($is_laptop) {
        $conn_local = @new mysqli('localhost', 'root', '', 'db_tomat');
        if ($conn_local && !$conn_local->connect_error) {
            $conn = $conn_local;
        } else {
            $conn_init = @new mysqli('localhost', 'root', '');
            if ($conn_init && !$conn_init->connect_error) {
                $conn_init->query("CREATE DATABASE IF NOT EXISTS `db_tomat` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
                $conn_init->close();
                $conn = @new mysqli('localhost', 'root', '', 'db_tomat');
            }
        }
    }
    if (!isset($conn) || !$conn || $conn->connect_error) {
        die("Koneksi database gagal: " . $e->getMessage());
    }
}

// Set charset & sinkronisasi timezone MySQL ke UTC +07:00 (WIB)
$conn->set_charset("utf8mb4");
$conn->query("SET time_zone = '+07:00'");


// Auto-migration untuk tabel app_settings & kolom kumulatif di riwayat_klasifikasi
$conn->query("CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

// Inisialisasi default current_session_id & last_session_date jika belum ada
$res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'current_session_id'");
if ($res && $res->num_rows === 0) {
    $conn->query("INSERT INTO app_settings (setting_key, setting_value) VALUES ('current_session_id', '1')");
}

$res_date = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'last_session_date'");
if ($res_date && $res_date->num_rows === 0) {
    $today = date('Y-m-d');
    $conn->query("INSERT INTO app_settings (setting_key, setting_value) VALUES ('last_session_date', '$today')");
}

// Pastikan tabel riwayat_klasifikasi ada
$conn->query("CREATE TABLE IF NOT EXISTS riwayat_klasifikasi (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tanggal DATE NOT NULL,
    waktu TIME NOT NULL,
    jenis ENUM('Matang', 'Setengah Matang', 'Belum Matang') NOT NULL,
    jumlah INT NOT NULL DEFAULT 1,
    session_id INT NOT NULL DEFAULT 1,
    total_matang INT NOT NULL DEFAULT 0,
    total_setengah INT NOT NULL DEFAULT 0,
    total_belum INT NOT NULL DEFAULT 0,
    fitur TEXT NULL,
    foto VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

// Cek dan tambahkan kolom baru pada riwayat_klasifikasi jika belum ada
$columns_to_add = [
    'session_id'    => "INT NOT NULL DEFAULT 1",
    'total_matang'  => "INT NOT NULL DEFAULT 0",
    'total_setengah'=> "INT NOT NULL DEFAULT 0",
    'total_belum'   => "INT NOT NULL DEFAULT 0",
    'fitur'         => "TEXT NULL",
    'foto'          => "VARCHAR(255) NULL"
];

$existing_cols = [];
$res_cols = @$conn->query("SHOW COLUMNS FROM riwayat_klasifikasi");
if ($res_cols) {
    while ($col = $res_cols->fetch_assoc()) {
        $existing_cols[] = $col['Field'];
    }
    foreach ($columns_to_add as $col_name => $col_def) {
        if (!in_array($col_name, $existing_cols)) {
            @$conn->query("ALTER TABLE riwayat_klasifikasi ADD COLUMN $col_name $col_def");
        }
    }
}
?>
