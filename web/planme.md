Buat website untuk sistem IoT klasifikasi kematangan buah tomat menggunakan Machine Learning metode Decision Tree C4.5.

PENTING:
- Ikuti struktur dan kebutuhan di bawah ini secara ketat.
- Jangan menambahkan menu, fitur, halaman, atau modul lain yang tidak disebutkan.
- Fokus pada website monitoring dan pencatatan hasil klasifikasi tomat dari alat/conveyor.
- Website harus sederhana, rapi, responsif, dan mudah digunakan.
- Jangan membuat fitur statistik, grafik, dataset management, perhitungan entropy, gain ratio, konfigurasi model, atau fitur lain di luar kebutuhan berikut.

==================================================
STRUKTUR WEBSITE
==================================================

1. DATA ADMIN
   - Digunakan untuk data/login administrator.
   - Sediakan sistem login admin.
   - Data admin dapat digunakan untuk autentikasi akses website.

2. RIWAYAT
   Fungsi:
   - Menyimpan detail setiap transaksi tomat yang melewati conveyor.
   - Setiap tomat yang terdeteksi dan diklasifikasikan oleh Decision Tree C4.5 dicatat ke dalam riwayat.

   Data riwayat minimal:
   - Waktu/tanggal transaksi
   - Jenis/hasil klasifikasi tomat
   - Jumlah

   Kategori hasil klasifikasi:
   - Matang
   - Setengah Matang
   - Belum Matang

   Riwayat harus dapat menampilkan data secara terstruktur dalam tabel.

3. REKAP HARIAN
   Fungsi:
   - Menampilkan rekap hasil klasifikasi tomat berdasarkan tanggal/hari.
   - Rekap berasal dari data pada menu Riwayat.
   - Data harus otomatis terakumulasi sesuai transaksi yang masuk.

   Pada halaman Rekap Harian, tampilkan dashboard dengan data:

   - Tanggal
   - Total Matang
   - Total Setengah Matang
   - Total Belum Matang
   - Total Semua

   Contoh tampilan:

   Tanggal              : 29/08/2026
   Total Matang         : 25
   Total Setengah Matang: 18
   Total Belum Matang   : 12
   Total Semua          : 55

==================================================
ALUR DATA
==================================================

Alur sistem:

Tomat
↓
Conveyor
↓
Sensor / sistem klasifikasi
↓
Decision Tree C4.5
↓
Hasil klasifikasi:
- Matang
- Setengah Matang
- Belum Matang
↓
Data disimpan ke database
↓
Masuk ke Riwayat
↓
Diakumulasikan ke Rekap Harian
↓
Ditampilkan pada Dashboard

==================================================
MENU WEBSITE
==================================================

Menu utama hanya:

- Data Admin
- Riwayat
- Rekap Harian
- Dashboard

Logout juga harus tersedia untuk admin yang sedang login.

==================================================
DASHBOARD
==================================================

Dashboard merupakan tampilan utama dari Rekap Harian.

Tampilkan:
- Tanggal
- Total Matang
- Total Setengah Matang
- Total Belum Matang
- Total Semua

Dashboard harus mengambil data secara otomatis dari database, bukan menggunakan angka dummy.

==================================================
RIWAYAT TRANSAKSI
==================================================

Setiap kali tomat melewati conveyor dan selesai diklasifikasikan oleh Decision Tree C4.5, sistem membuat satu catatan transaksi.

Contoh:

Tanggal/Waktu       Jenis              Jumlah
29/08/2026 08:45    Matang             1
29/08/2026 08:46    Belum Matang       1
29/08/2026 08:47    Setengah Matang    1

Data tersebut kemudian digunakan untuk membuat rekap harian.

==================================================
DATABASE
==================================================

Siapkan database yang sederhana dan terstruktur untuk:

1. Data admin
2. Riwayat transaksi klasifikasi tomat
3. Rekap harian jika diperlukan

Pastikan data riwayat dapat digunakan untuk menghitung:

- total matang per hari
- total setengah matang per hari
- total belum matang per hari
- total seluruh tomat per hari

==================================================
DESAIN
==================================================

Gunakan desain website modern, bersih, dan profesional.

Prioritas:
- Mudah dibaca
- Responsive desktop dan mobile
- Navigasi sederhana
- Dashboard mudah dipahami
- Tabel riwayat jelas
- Jangan terlalu banyak elemen dekoratif
- Jangan membuat halaman yang tidak diperlukan

==================================================
HASIL YANG DIHARAPKAN
==================================================

Buat website yang benar-benar siap dikembangkan untuk terhubung dengan alat IoT.

Struktur akhirnya:

WEB TOMAT
│
├── Data Admin
│   └── Login / akun admin
│
├── Riwayat
│   └── Detail setiap transaksi tomat
│
├── Rekap Harian
│   └── Dashboard
│       ├── Tanggal
│       ├── Total Matang
│       ├── Total Setengah Matang
│       ├── Total Belum Matang
│       └── Total Semua
│
└── Logout

Jangan menambahkan fitur di luar struktur tersebut.

==================================================
PANDUAN POSTMAN: MENGIRIM DATA KLASIFIKASI (IOT)
==================================================
Berikut adalah langkah-langkah lengkap untuk mengirim data ke file `api/klasifikasi.php` menggunakan aplikasi Postman.

### 1. Buat Request Baru
1. Buka aplikasi Postman.
2. Klik tombol **"+"** atau **"New" -> "HTTP Request"**.

### 2. Atur Method dan URL
- Ubah method dari `GET` menjadi **`POST`**.
- Masukkan URL endpoint API lokal Anda, contohnya:
  `http://localhost/tiara-tomata/api/klasifikasi.php`
  *(Sesuaikan jika Anda menggunakan port atau nama folder yang berbeda).*

### 3. Kirim Data (JSON Format - Disarankan)
Karena API Anda menggunakan `json_decode(file_get_contents('php://input'), true)`, cara terbaik mengirim data adalah melalui JSON.
1. Di bawah baris URL, klik tab **Body**.
2. Pilih opsi **raw**.
3. Di sebelah kanannya, ubah pilihan `Text` menjadi **`JSON`**.
4. Masukkan struktur JSON berikut ke dalam kotak teks:
   ```json
   {
       "jenis": "Matang",
       "jumlah": 1
   }
   ```
   *Catatan:*
   - `"jenis"` harus bernilai pasti salah satu dari: `"Matang"`, `"Setengah Matang"`, atau `"Belum Matang"`.
   - `"jumlah"` adalah opsional (default 1 jika dikosongi).

### 4. Opsi Alternatif (Form-Data)
API Anda juga mendukung `$_POST` biasa. Jika Anda lebih suka form-data:
1. Di tab **Body**, pilih **x-www-form-urlencoded** atau **form-data**.
2. Pada tabel yang muncul, isi baris pertama:
   - Key: `jenis`
   - Value: `Setengah Matang`
3. Isi baris kedua:
   - Key: `jumlah`
   - Value: `1`

### 5. Jalankan Request
- Klik tombol biru **Send** di pojok kanan atas.

### 6. Cek Hasilnya
- Scroll ke bawah ke bagian **Response**.
- Anda akan melihat status HTTP `201 Created` jika sukses.
- Response bodynya akan terlihat seperti ini:
  ```json
  {
      "status": "success",
      "message": "Data klasifikasi berhasil disimpan.",
      "data": {
          "id": 12,
          "tanggal": "2026-08-31",
          "waktu": "11:25:00",
          "jenis": "Matang",
          "jumlah": 1
      }
  }
  ```
- Jika ada kesalahan (misal salah tulis "jenis"), Anda akan mendapat balasan error `400 Bad Request` dari API.