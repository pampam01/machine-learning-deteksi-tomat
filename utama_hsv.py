import cv2
import numpy as np
import pickle
import time
import os
import sys


python = sys.executable

import serial
import serial.tools.list_ports

print("path PYTHON === >", python)  # ini venv yang aktif di VSCode)


# ============================================================
# KONFIGURASI
# ============================================================
MODEL_PATH = "model_c45_hist.pkl"
INDEX_KAMERA = 1  # 1 = Kamera Eksternal (USB Webcam), 0 = Kamera Internal Laptop

BINS_HSV = (8, 8, 4)
JUMLAH_FITUR = BINS_HSV[0] * BINS_HSV[1] * BINS_HSV[2]
NAMA_FITUR = [f"fitur_{i}" for i in range(JUMLAH_FITUR)]

UKURAN_FRAME = (800, 600)


ser = None

def find_active_port():
    global ser
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Lewati virtual port Bluetooth agar tidak hang/freeze lama
        if "bluetooth" in port.description.lower():
            continue
        try:
            print(f"[SERIAL] Mengecek port {port.device}: {port.description}")
            temp_ser = serial.Serial(port.device, 9600, timeout=1)
            time.sleep(1.5)  # Tunggu inisialisasi boot hardware
            temp_ser.reset_input_buffer()
            temp_ser.write(b"go\n")
            time.sleep(0.3)
            for _ in range(3):
                resp = temp_ser.readline().decode(errors="ignore").strip()
                if "ok" in resp.lower():
                    print(f"[SERIAL] Berhasil terhubung ke {port.device}")
                    ser = temp_ser
                    return True
            temp_ser.close()
        except Exception as e:
            continue

    print("[SERIAL] Tidak ada port serial yang merespon.")
    ser = None
    return False


def send_serial_command(command):
    global ser
    if ser and ser.is_open:
        try:
            ser.write(command.encode() + b"\n")
            response = ser.readline().decode(errors="ignore").strip()
            return response
        except Exception:
            return None
    return None


if find_active_port():
    print("[OK] Serial siap")
else:
    print("[WARN] Serial tidak terhubung. Mode kamera mandiri aktif (sensor/aktuator dilewati).")


# ============================================================
# EKSTRAKSI FITUR HISTOGRAM HSV
# ============================================================
def ekstrak_fitur_frame(img):

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    hist = cv2.calcHist([hsv], [0, 1, 2], None, BINS_HSV, [0, 180, 0, 256, 0, 256])

    hist = cv2.normalize(hist, hist).flatten()

    return hist.tolist()


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

            kondisi = f"{nama} <= {threshold:.4f}"
            perbandingan = f"{nilai:.4f} <= {threshold:.4f}"

            node = tree.children_left[node]

        else:

            kondisi = f"{nama} > {threshold:.4f}"
            perbandingan = f"{nilai:.4f} > {threshold:.4f}"

            node = tree.children_right[node]

        langkah.append(
            {
                "nomor": nomor,
                "kondisi": kondisi,
                "perbandingan": perbandingan,
                "keputusan": "YA",
            }
        )

        nomor += 1

    kelas_index = np.argmax(tree.value[node][0])

    hasil = model.classes_[kelas_index]

    return langkah, hasil


# ============================================================
# TAMPILKAN HASIL
# ============================================================
def tampilkan(frame, langkah, hasil):

    tinggi, lebar = frame.shape[:2]

    # Panel kanan
    panel_lebar = 500

    panel = np.zeros((tinggi, panel_lebar, 3), dtype=np.uint8)

    panel[:] = (30, 30, 30)

    # ========================================================
    # JUDUL
    # ========================================================

    cv2.putText(
        panel,
        "C4.5 REALTIME",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        panel,
        "PREDIKSI HISTOGRAM HSV",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1,
    )

    # ========================================================
    # INFORMASI PROSES DECISION TREE
    # ========================================================

    y = 105

    cv2.putText(
        panel,
        "PROSES DECISION TREE:",
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        1,
    )

    y += 30

    # Tampilkan beberapa langkah tree
    for langkah_tree in langkah:

        text = f"{langkah_tree['nomor']}. " f"{langkah_tree['perbandingan']}"

        # Jika terlalu panjang, potong
        if len(text) > 48:
            text = text[:48] + "..."

        cv2.putText(
            panel, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1
        )

        y += 23

        if y > tinggi - 130:
            cv2.putText(
                panel, "...", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1
            )
            break

    # ========================================================
    # HASIL PREDIKSI
    # ========================================================

    kotak_y1 = tinggi - 100
    kotak_y2 = tinggi - 20

    cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), (50, 50, 50), -1)

    cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), (0, 255, 0), 2)

    cv2.putText(
        panel,
        "PREDIKSI:",
        (30, kotak_y1 + 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        panel,
        str(hasil),
        (180, kotak_y1 + 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 0),
        2,
    )

    # ========================================================
    # GABUNG VIDEO + PANEL
    # ========================================================

    output = np.hstack((frame, panel))

    return output


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":


    # ========================================================
    # LOAD MODEL
    # ========================================================

    try:

        with open(MODEL_PATH, "rb") as f:

            model = pickle.load(f)

    except Exception as e:

        print("Gagal membuka model:", e)
        print("Pastikan model sudah dilatih " "dengan fitur histogram HSV.")

        exit()

    # ========================================================
    # INFORMASI MODEL
    # ========================================================

    print("=" * 60)
    print("MODEL C4.5 HISTOGRAM HSV BERHASIL DIMUAT")
    print("=" * 60)

    print("Kelas:")

    for kelas in model.classes_:
        print(" -", kelas)

    print()
    print("Tekan Q untuk keluar.")
    print("=" * 60)

    # ========================================================
    # KAMERA
    # ========================================================

    print(f"[INFO] Membuka kamera eksternal (index {INDEX_KAMERA})...")
    kamera = cv2.VideoCapture(INDEX_KAMERA, cv2.CAP_DSHOW)

    if not kamera.isOpened() and INDEX_KAMERA != 0:
        print(f"[WARN] Kamera index {INDEX_KAMERA} gagal dibuka, mencoba kamera bawaan (index 0)...")
        kamera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not kamera.isOpened():
        print("Kamera tidak dapat dibuka. Pastikan kamera terhubung dan tidak dipakai aplikasi lain.")
        exit()

    # Konfigurasi codec MJPG & resolusi agar kompatibel dengan webcam Logitech C270 pada Windows
    kamera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    kamera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Warmup kamera (sensor Logitech memerlukan beberapa frame awal untuk inisialisasi auto-exposure)
    print("[INFO] Menginisialisasi sensor kamera...")
    for _ in range(10):
        kamera.read()
        time.sleep(0.02)

    # ========================================================
    # WINDOW
    # ========================================================

    window_name = "C4.5 - Prediksi Realtime"

    cv2.namedWindow(window_name)

    # ========================================================
    # LOOP VIDEO
    # ========================================================

    last_hasil = None

    while True:
        if ser and ser.is_open:
            respon = send_serial_command("se")
            print("[SERIAL] Respon sensor:", respon) # sensor konveyor

        ret, frame = kamera.read()

        if not ret or frame is None:
            time.sleep(0.01)
            continue

        # Mirror kamera
        frame = cv2.flip(frame, 1)

        # Resize
        frame = cv2.resize(frame, UKURAN_FRAME)

        # ====================================================
        # EKSTRAKSI FITUR HSV
        # ====================================================

        fitur = ekstrak_fitur_frame(frame)

        # ====================================================
        # PREDIKSI C4.5
        # ====================================================

        langkah, hasil = telusuri_tree(model, fitur)


        if(hasil != last_hasil):
            print("[INFO] Hasil prediksi berubah:", hasil)

            send_serial_command(str(hasil))


            last_hasil = hasil

        # ====================================================
        # TAMPILKAN
        # ====================================================

        output = tampilkan(frame, langkah, hasil)

        cv2.imshow(window_name, output)

        # ====================================================
        # KEYBOARD
        # ====================================================

        tombol = cv2.waitKey(1) & 0xFF

        if tombol == ord("q"):
            break

    # ========================================================
    # CLEANUP
    # ========================================================

    kamera.release()
    cv2.destroyAllWindows()
