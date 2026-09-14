<?php
// Konfigurasi Database
define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_NAME', 'db_tomat');

// Koneksi Database
$conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);

// Cek koneksi
if ($conn->connect_error) {
    die("Koneksi database gagal: " . $conn->connect_error);
}

// Set charset
$conn->set_charset("utf8mb4");

// Set timezone & region (UTC +7 / Asia/Jakarta, Indonesia)
date_default_timezone_set('Asia/Jakarta');
ini_set('date.timezone', 'Asia/Jakarta');
setlocale(LC_ALL, 'id_ID.utf8', 'id_ID', 'ind', 'Indonesian');

// Sinkronisasi timezone MySQL ke UTC +07:00 (WIB)
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
