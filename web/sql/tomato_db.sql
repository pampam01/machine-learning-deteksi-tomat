-- =============================================
-- Database Setup - Sistem Klasifikasi Tomat
-- =============================================

CREATE DATABASE IF NOT EXISTS db_tomat;
USE db_tomat;

-- Tabel Admin
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    nama VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabel Riwayat Klasifikasi
CREATE TABLE IF NOT EXISTS riwayat_klasifikasi (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tanggal DATE NOT NULL,
    waktu TIME NOT NULL,
    jenis ENUM('Matang', 'Setengah Matang', 'Belum Matang') NOT NULL,
    jumlah INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Index untuk performa query rekap harian
CREATE INDEX idx_tanggal ON riwayat_klasifikasi(tanggal);
CREATE INDEX idx_jenis ON riwayat_klasifikasi(jenis);

-- Insert admin default (password: admin123)
INSERT INTO admin (username, password, nama) VALUES 
('admin', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'Administrator');
