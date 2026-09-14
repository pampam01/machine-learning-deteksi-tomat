import cv2
import numpy as np
import pickle
import time

# ============================================================
# KONFIGURASI
# ============================================================
MODEL_PATH = "model_c45.pkl"
INDEX_KAMERA = 1  # 1 = Kamera Eksternal (USB Webcam), 0 = Kamera Internal Laptop
NAMA_FITUR = ["MERAH", "KUNING", "HIJAU", "PUTIH", "HITAM"]
WARNA_FITUR_BGR = [
    (0, 0, 255),       # merah
    (0, 255, 255),     # kuning
    (0, 255, 0),       # hijau
    (255, 255, 255),   # putih
    (60, 60, 60)       # hitam
]
MAX_LANGKAH_TAMPIL = 7   # batasi langkah decision tree yang ditampilkan

# ============================================================
# EKSTRAKSI FITUR WARNA
# ============================================================
def ekstrak_fitur_frame(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total_pixel = hsv.shape[0] * hsv.shape[1]

    # Mask untuk masing-masing warna
    merah1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
    merah2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
    mask_merah = cv2.bitwise_or(merah1, merah2)

    mask_kuning = cv2.inRange(hsv, np.array([20, 50, 50]), np.array([30, 255, 255]))
    mask_hijau  = cv2.inRange(hsv, np.array([40, 50, 50]), np.array([70, 255, 255]))
    mask_putih  = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 30, 255]))
    mask_hitam  = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 30]))

    # Hitung persentase
    merah  = cv2.countNonZero(mask_merah)  / total_pixel * 100
    kuning = cv2.countNonZero(mask_kuning) / total_pixel * 100
    hijau  = cv2.countNonZero(mask_hijau)  / total_pixel * 100
    putih  = cv2.countNonZero(mask_putih)  / total_pixel * 100
    hitam  = cv2.countNonZero(mask_hitam)  / total_pixel * 100

    return [merah, kuning, hijau, putih, hitam]

# ============================================================
# TELUSURI DECISION TREE
# ============================================================
def telusuri_tree(model, fitur):
    tree = model.tree_
    node = 0
    langkah = []
    nomor = 1

    while tree.children_left[node] != tree.children_right[node]:
        index_fitur = tree.feature[node]
        threshold = tree.threshold[node]
        nama = NAMA_FITUR[index_fitur]
        nilai = fitur[index_fitur]

        if nilai <= threshold:
            kondisi = f"{nama} <= {threshold:.2f}%"
            perbandingan = f"{nilai:.2f}% <= {threshold:.2f}%"
            node = tree.children_left[node]
        else:
            kondisi = f"{nama} > {threshold:.2f}%"
            perbandingan = f"{nilai:.2f}% > {threshold:.2f}%"
            node = tree.children_right[node]

        langkah.append({
            "nomor": nomor,
            "kondisi": kondisi,
            "perbandingan": perbandingan,
            "keputusan": "YA"
        })
        nomor += 1

    kelas_index = np.argmax(tree.value[node][0])
    hasil = model.classes_[kelas_index]
    return langkah, hasil

# ============================================================
# GAMBAR PIE CHART DENGAN LABEL
# ============================================================
def gambar_pie_chart(panel, fitur, pusat, radius):
    total = sum(fitur)
    if total <= 0:
        return

    sudut = 0
    for i, (nilai, warna) in enumerate(zip(fitur, WARNA_FITUR_BGR)):
        besar_sudut = nilai / total * 360
        # Gambar potongan pie
        cv2.ellipse(panel, pusat, (radius, radius), 0, sudut,
                    sudut + besar_sudut, warna, -1)
        # Gambar label persentase di tengah potongan jika cukup besar
        if besar_sudut > 15:  # hanya tampilkan jika cukup lebar
            sudut_tengah = np.deg2rad(sudut + besar_sudut / 2)
            x_label = int(pusat[0] + (radius * 0.65) * np.cos(sudut_tengah))
            y_label = int(pusat[1] + (radius * 0.65) * np.sin(sudut_tengah))
            teks = f"{nilai:.1f}%"
            # Pilih warna teks kontras terhadap potongan
            if i == 4:  # hitam -> teks putih
                warna_teks = (255, 255, 255)
            else:
                warna_teks = (0, 0, 0)
            cv2.putText(panel, teks, (x_label - 15, y_label + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, warna_teks, 1, cv2.LINE_AA)
        sudut += besar_sudut

    # Garis luar pie
    cv2.circle(panel, pusat, radius, (255, 255, 255), 2)

# ============================================================
# TAMPILKAN INFORMASI (DIPERBAIKI)
# ============================================================
def tampilkan(frame, fitur, langkah, hasil):
    tinggi, lebar = frame.shape[:2]

    # ============ PANEL KANAN ============
    panel_lebar = 600
    panel = np.zeros((tinggi, panel_lebar, 3), dtype=np.uint8)
    panel[:] = (30, 30, 30)  # latar belakang abu-abu gelap

    # ============ JUDUL ============
    cv2.putText(panel, "C4.5 REALTIME", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(panel, "KOMPOSISI WARNA", (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    # ============ AREA PIE CHART DAN LEGENDA ============
    # Pie chart di kiri, legenda di kanan
    pusat_pie = (140, 180)
    radius_pie = 90
    gambar_pie_chart(panel, fitur, pusat_pie, radius_pie)

    # Legenda / data warna di kanan pie
    x_legenda = 280
    y_legenda = 110
    for i, (nama, nilai, warna) in enumerate(zip(NAMA_FITUR, fitur, WARNA_FITUR_BGR)):
        # Bullet warna
        cv2.rectangle(panel, (x_legenda, y_legenda - 10),
                      (x_legenda + 15, y_legenda + 5), warna, -1)
        cv2.rectangle(panel, (x_legenda, y_legenda - 10),
                      (x_legenda + 15, y_legenda + 5), (200, 200, 200), 1)
        # Nama dan persentase
        cv2.putText(panel, f"{nama:<8} : {nilai:6.2f}%",
                    (x_legenda + 25, y_legenda),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_legenda += 30

    # ============ GARIS PEMISAH ============
    y_garis = 300
    cv2.line(panel, (20, y_garis), (580, y_garis), (100, 100, 100), 1)

    # ============ ALUR DECISION TREE ============
    y = y_garis + 20
    cv2.putText(panel, "ALUR DECISION TREE", (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    y += 30

    # Batasi jumlah langkah yang ditampilkan
    langkah_tampil = langkah[:MAX_LANGKAH_TAMPIL]
    for langkah_data in langkah_tampil:
        nomor = langkah_data["nomor"]
        kondisi = langkah_data["kondisi"]
        perbandingan = langkah_data["perbandingan"]
        keputusan = langkah_data["keputusan"]

        cv2.putText(panel, f"[{nomor}] {kondisi} ?",
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
        y += 20

        cv2.putText(panel, perbandingan,
                    (35, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y += 20

        cv2.putText(panel, f"-> {keputusan}",
                    (35, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 2)
        y += 25

        cv2.putText(panel, "|", (45, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += 18

        # Berhenti jika mendekati area hasil
        if y > tinggi - 120:
            break

    # Jika masih ada langkah yang tidak ditampilkan
    if len(langkah) > len(langkah_tampil):
        cv2.putText(panel, f"... ({len(langkah) - len(langkah_tampil)} langkah lagi)",
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        y += 20

    # ============ HASIL KESIMPULAN ============
    kotak_hasil_y1 = tinggi - 80
    kotak_hasil_y2 = tinggi - 20
    cv2.rectangle(panel, (15, kotak_hasil_y1), (585, kotak_hasil_y2),
                  (60, 60, 60), -1)
    cv2.rectangle(panel, (15, kotak_hasil_y1), (585, kotak_hasil_y2),
                  (0, 255, 0), 2)

    cv2.putText(panel, "KESIMPULAN:", (30, kotak_hasil_y1 + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(panel, str(hasil), (180, kotak_hasil_y1 + 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)

    # ============ GABUNG CAMERA + PANEL ============
    output = np.hstack((frame, panel))
    return output

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Load model
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
    except Exception as e:
        print("Gagal membuka model:", e)
        exit()

    print("=" * 60)
    print("MODEL C4.5 BERHASIL DIMUAT")
    print("Kelas:")
    for kelas in model.classes_:
        print(" -", kelas)
    print("\nTekan Q untuk keluar")
    print("=" * 60)

    # Buka kamera
    print(f"[INFO] Membuka kamera eksternal (index {INDEX_KAMERA})...")
    kamera = cv2.VideoCapture(INDEX_KAMERA, cv2.CAP_DSHOW)
    if not kamera.isOpened() and INDEX_KAMERA != 0:
        print(f"[WARN] Kamera index {INDEX_KAMERA} gagal dibuka, mencoba kamera internal (index 0)...")
        kamera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not kamera.isOpened():
        print("Kamera tidak dapat dibuka. Pastikan kamera terhubung dan tidak dipakai aplikasi lain.")
        exit()

    kamera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    kamera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("[INFO] Menginisialisasi sensor kamera...")
    for _ in range(10):
        kamera.read()
        time.sleep(0.02)

    while True:
        ret, frame = kamera.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        frame = cv2.flip(frame, 1)  # mirror

        fitur = ekstrak_fitur_frame(frame)
        langkah, hasil = telusuri_tree(model, fitur)
        output = tampilkan(frame, fitur, langkah, hasil)

        cv2.imshow("C4.5 - Deteksi Realtime", output)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    kamera.release()
    cv2.destroyAllWindows()