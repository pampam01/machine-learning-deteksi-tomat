import cv2
import numpy as np
import sys

def hitung_persentase_warna(gambar_path):
    # Baca gambar
    img = cv2.imread(gambar_path)
    if img is None:
        print(f"Gambar tidak ditemukan di: {gambar_path}")
        return

    # Ubah ke HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total_piksel = hsv.shape[0] * hsv.shape[1]

    # Definisikan rentang warna dalam HSV
    # Merah (dua rentang karena melingkar)
    merah_bawah1 = np.array([0, 50, 50])
    merah_atas1 = np.array([10, 255, 255])
    merah_bawah2 = np.array([170, 50, 50])
    merah_atas2 = np.array([180, 255, 255])

    # Kuning
    kuning_bawah = np.array([20, 50, 50])
    kuning_atas = np.array([30, 255, 255])

    # Hijau
    hijau_bawah = np.array([40, 50, 50])
    hijau_atas = np.array([70, 255, 255])

    # Putih (nilai S rendah, V tinggi)
    putih_bawah = np.array([0, 0, 200])
    putih_atas = np.array([180, 30, 255])

    # Hitam (nilai V rendah)
    hitam_bawah = np.array([0, 0, 0])
    hitam_atas = np.array([180, 255, 30])

    # Buat mask untuk setiap warna
    mask_merah1 = cv2.inRange(hsv, merah_bawah1, merah_atas1)
    mask_merah2 = cv2.inRange(hsv, merah_bawah2, merah_atas2)
    mask_merah = cv2.bitwise_or(mask_merah1, mask_merah2)

    mask_kuning = cv2.inRange(hsv, kuning_bawah, kuning_atas)
    mask_hijau = cv2.inRange(hsv, hijau_bawah, hijau_atas)
    mask_putih = cv2.inRange(hsv, putih_bawah, putih_atas)
    mask_hitam = cv2.inRange(hsv, hitam_bawah, hitam_atas)

    # Hitung jumlah piksel setiap warna
    jml_merah = cv2.countNonZero(mask_merah)
    jml_kuning = cv2.countNonZero(mask_kuning)
    jml_hijau = cv2.countNonZero(mask_hijau)
    jml_putih = cv2.countNonZero(mask_putih)
    jml_hitam = cv2.countNonZero(mask_hitam)

    # Hitung persentase
    persen_merah = (jml_merah / total_piksel) * 100
    persen_kuning = (jml_kuning / total_piksel) * 100
    persen_hijau = (jml_hijau / total_piksel) * 100
    persen_putih = (jml_putih / total_piksel) * 100
    persen_hitam = (jml_hitam / total_piksel) * 100

    # Tampilkan hasil
    print(f"Total piksel: {total_piksel}")
    print(f"Merah  : {persen_merah:.2f}%  ({jml_merah} piksel)")
    print(f"Kuning : {persen_kuning:.2f}%  ({jml_kuning} piksel)")
    print(f"Hijau  : {persen_hijau:.2f}%  ({jml_hijau} piksel)")
    print(f"Putih  : {persen_putih:.2f}%  ({jml_putih} piksel)")
    print(f"Hitam  : {persen_hitam:.2f}%  ({jml_hitam} piksel)")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        jalur_gambar = sys.argv[1]
    else:
        jalur_gambar = input("Masukkan jalur file gambar: ").strip()
    hitung_persentase_warna(jalur_gambar)