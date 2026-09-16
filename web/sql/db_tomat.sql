-- =============================================
-- Database Setup - Sistem Klasifikasi Tomat C4.5
-- Kompatibel untuk Hosting cPanel & Localhost
-- =============================================

-- Catatan untuk cPanel:
-- Di cPanel phpMyAdmin, buka database Anda (misal: scodeweb_databases_2026_tiara_tomat),
-- lalu langsung klik tab "Import" dan pilih file ini.
-- (Jangan aktifkan CREATE DATABASE karena cPanel melarang nama database tanpa prefix).

-- Jika ingin import di Localhost (XAMPP/Laragon), aktifkan 2 baris di bawah ini:
-- CREATE DATABASE IF NOT EXISTS db_tomat;
-- USE db_tomat;

-- 1. Tabel Admin
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    nama VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Tabel Riwayat Klasifikasi (Lengkap dengan kolom fitur & foto)
CREATE TABLE IF NOT EXISTS riwayat_klasifikasi (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Tabel Pengaturan Sistem / Counter Session
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Inisialisasi Counter Session
INSERT IGNORE INTO app_settings (setting_key, setting_value) VALUES ('current_session_id', '1');

-- 5. Index untuk performa query rekap harian & dashboard
CREATE INDEX idx_tanggal ON riwayat_klasifikasi(tanggal);
CREATE INDEX idx_jenis ON riwayat_klasifikasi(jenis);
CREATE INDEX idx_session ON riwayat_klasifikasi(session_id);

-- 6. Insert Akun Admin Default (Username: admin | Password: password)
INSERT IGNORE INTO admin (username, password, nama) VALUES 
('admin', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'Administrator');
