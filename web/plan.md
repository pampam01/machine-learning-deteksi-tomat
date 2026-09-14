# Website IoT Klasifikasi Kematangan Tomat — Implementation Plan

Website monitoring dan pencatatan hasil klasifikasi kematangan buah tomat menggunakan Decision Tree C4.5, dibangun dengan **PHP + MySQL**.

## Tech Stack

- **Backend:** PHP 7.4+ (native, tanpa framework)
- **Database:** MySQL / MariaDB
- **Frontend:** HTML5, CSS3 (vanilla), JavaScript (vanilla)
- **Auth:** Session-based login
- **API:** REST endpoint sederhana untuk menerima data dari perangkat IoT (ESP32/Arduino)

---

## Struktur Folder

```
tiara-tomata/
├── config/
│   └── database.php          # Koneksi database
├── assets/
│   ├── css/
│   │   └── style.css         # Stylesheet utama
│   └── js/
│       └── main.js           # JavaScript utama
├── includes/
│   ├── header.php            # Header + navigasi
│   ├── footer.php            # Footer
│   └── auth.php              # Middleware autentikasi
├── api/
│   └── klasifikasi.php       # API endpoint untuk IoT device
├── pages/
│   ├── login.php             # Halaman login
│   ├── dashboard.php         # Dashboard rekap harian
│   ├── riwayat.php           # Riwayat transaksi
│   ├── rekap-harian.php      # Rekap harian (tabel)
│   └── data-admin.php        # Manajemen data admin
├── sql/
│   └── setup.sql             # Script setup database
├── index.php                 # Entry point (redirect ke dashboard/login)
└── logout.php                # Proses logout
```

---

## Database Schema

### Tabel `admin`
| Kolom      | Tipe            | Keterangan           |
|------------|-----------------|----------------------|
| id         | INT PRIMARY KEY | Auto increment       |
| username   | VARCHAR(50)     | Username admin       |
| password   | VARCHAR(255)    | Password (hashed)    |
| nama       | VARCHAR(100)    | Nama lengkap admin   |
| created_at | TIMESTAMP       | Waktu pembuatan      |

### Tabel `riwayat_klasifikasi`
| Kolom        | Tipe            | Keterangan                              |
|--------------|-----------------|------------------------------------------|
| id           | INT PRIMARY KEY | Auto increment                           |
| tanggal      | DATE            | Tanggal transaksi                        |
| waktu        | TIME            | Waktu transaksi                          |
| jenis        | ENUM            | 'Matang', 'Setengah Matang', 'Belum Matang' |
| jumlah       | INT             | Jumlah tomat (default 1)                 |
| created_at   | TIMESTAMP       | Waktu record dibuat                      |

> **Catatan:** Rekap harian tidak memerlukan tabel terpisah — dihitung secara otomatis dari tabel `riwayat_klasifikasi` menggunakan query `GROUP BY DATE(tanggal)`.

---

## Halaman & Fitur

### 1. Login (`pages/login.php`)
- Form login (username + password)
- Validasi dengan database, password di-hash menggunakan `password_hash()` / `password_verify()`
- Session-based auth

### 2. Dashboard (`pages/dashboard.php`)
- Tampilan utama setelah login
- Menampilkan rekap hari ini:
  - Tanggal hari ini
  - Total Matang
  - Total Setengah Matang
  - Total Belum Matang
  - Total Semua
- Data diambil real-time dari database

### 3. Riwayat (`pages/riwayat.php`)
- Tabel riwayat semua transaksi klasifikasi
- Kolom: No, Tanggal/Waktu, Jenis Klasifikasi, Jumlah
- Filter berdasarkan tanggal (opsional)
- Pagination

### 4. Rekap Harian (`pages/rekap-harian.php`)
- Tabel rekap per tanggal
- Kolom: Tanggal, Total Matang, Total Setengah Matang, Total Belum Matang, Total Semua
- Data diagregasi dari tabel riwayat

### 5. Data Admin (`pages/data-admin.php`)
- Daftar akun admin
- Tambah / edit / hapus admin

### 6. Logout (`logout.php`)
- Hapus session dan redirect ke login

### 7. API IoT (`api/klasifikasi.php`)
- **POST** endpoint untuk menerima data klasifikasi dari perangkat IoT
- Parameter: `jenis` (Matang/Setengah Matang/Belum Matang), `jumlah` (default 1)
- Response: JSON status success/error
- Tidak memerlukan login (atau API key sederhana)

---

## Desain UI

- **Warna utama:** Hijau tua (#1B5E20) + merah tomat (#E53935) + putih
- **Layout:** Sidebar navigasi + konten utama
- **Responsif:** Desktop & mobile
- **Font:** Google Fonts (Inter / Roboto)
- **Dashboard cards:** Untuk menampilkan total per kategori
- **Tabel:** Bersih, striped, responsive

---

## Langkah Implementasi

- [x] **Langkah 1:** Setup database — `sql/setup.sql` ✅
- [x] **Langkah 2:** Konfigurasi database — `config/database.php` ✅
- [x] **Langkah 3:** Sistem autentikasi — `includes/auth.php`, `pages/login.php`, `logout.php` ✅
- [x] **Langkah 4:** Layout dasar — `includes/header.php`, `includes/footer.php`, `assets/css/style.css` ✅
- [x] **Langkah 5:** Halaman Dashboard — `pages/dashboard.php` ✅
- [x] **Langkah 6:** Halaman Riwayat — `pages/riwayat.php` ✅
- [x] **Langkah 7:** Halaman Rekap Harian — `pages/rekap-harian.php` ✅
- [x] **Langkah 8:** Halaman Data Admin — `pages/data-admin.php` ✅
- [x] **Langkah 9:** API endpoint IoT — `api/klasifikasi.php` ✅
- [x] **Langkah 10:** Entry point — `index.php` ✅
- [x] **Langkah 11:** JavaScript — `assets/js/main.js` ✅
- [ ] **Langkah 12:** Testing dan verifikasi seluruh fitur

---

## Langkah Selanjutnya

### 🚀 Cara Menjalankan Website

1. **Pastikan XAMPP / Laragon sudah terinstall dan MySQL aktif**

2. **Buat database** — jalankan file `sql/setup.sql` di phpMyAdmin atau MySQL CLI:
   ```sql
   SOURCE C:/Users/Windows/OneDrive/Dokumen/Arduino/tiara-tomata/sql/setup.sql;
   ```

3. **Konfigurasi web server** — arahkan document root ke folder `tiara-tomata`, atau copy folder ini ke `htdocs` (XAMPP) / `www` (Laragon)

4. **Akses website** di browser: `http://localhost/` atau sesuai konfigurasi

5. **Login** dengan akun default:
   - Username: `admin`
   - Password: `admin123`

### 🔌 Cara Kirim Data dari IoT Device (ESP32/Arduino)

Kirim HTTP POST ke endpoint `http://[IP-SERVER]/api/klasifikasi.php`:

```
POST /api/klasifikasi.php
Content-Type: application/json

{
    "jenis": "Matang",
    "jumlah": 1
}
```

Nilai `jenis` yang valid: `Matang`, `Setengah Matang`, `Belum Matang`

### 📝 TODO Selanjutnya
- [ ] Setup database di MySQL (jalankan `setup.sql`)
- [ ] Test login/logout
- [ ] Test API endpoint dari Postman/curl
- [ ] Verifikasi tampilan dashboard, riwayat, rekap harian
- [ ] Integrasikan dengan perangkat IoT (ESP32)
- [ ] Kode Arduino/ESP32 untuk kirim data ke API

---

## Verifikasi

### Manual
- Jalankan di XAMPP / Laragon / server lokal
- Test login / logout
- Test tambah data via API menggunakan Postman atau curl
- Cek dashboard, riwayat, dan rekap harian menampilkan data yang benar
- Cek responsivitas di mobile

### Automated
- Tes API endpoint dengan curl command
