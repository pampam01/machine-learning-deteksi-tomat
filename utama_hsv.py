import cv2
import numpy as np
import pickle
import time
import os
import sys
import threading
import queue
from collections import deque, Counter

python = sys.executable

import serial
import serial.tools.list_ports

print("path PYTHON === >", python)  # ini venv yang aktif di VSCode)


# ============================================================
# KONFIGURASI
# ============================================================
MODEL_PATH = "model_c45_hist.pkl"

# Deteksi sistem operasi (Windows vs Linux / Raspberry Pi)
IS_LINUX = sys.platform.startswith("linux")
# Pada Raspberry Pi / Linux, webcam USB tunggal biasanya berada di index 0.
# Pada Windows laptop, index 0 adalah webcam bawaan laptop dan index 1 adalah webcam USB.
INDEX_KAMERA = 0 if IS_LINUX else 1
BACKEND_KAMERA = cv2.CAP_V4L2 if IS_LINUX else (cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY)

BINS_HSV = (8, 8, 4)
JUMLAH_FITUR = BINS_HSV[0] * BINS_HSV[1] * BINS_HSV[2]
NAMA_FITUR = [f"fitur_{i}" for i in range(JUMLAH_FITUR)]

# Resolusi standar 640x480 agar ringan di CPU/RAM dan berjalan halus di 30 FPS
UKURAN_FRAME = (640, 480)

# ============================================================
# PEMETAAN KELAS HASIL MODEL C4.5
# ============================================================
# Sesuai data.yaml dan dataset training YOLO / C4.5:
# - Kelas '0' = matang (Merah) -> kirim perintah 'matang'
# - Kelas '1' = mentah (Hijau) -> kirim perintah 'mentah'
# - Kelas '2' = setengah_matang (Kuning) -> kirim perintah 'setengah_matang'
KELAS_MAP = {
    "0": {
        "command": "matang",
        "label_ui": "MATANG (MERAH)",
        "warna_bgr": (0, 0, 255),       # Merah (BGR)
    },
    "1": {
        "command": "mentah",
        "label_ui": "MENTAH (HIJAU)",
        "warna_bgr": (0, 255, 0),       # Hijau (BGR)
    },
    "2": {
        "command": "setengah_matang",
        "label_ui": "SETENGAH MATANG (KUNING)",
        "warna_bgr": (0, 255, 255),     # Kuning (BGR)
    },
    # Fallback string langsung
    "matang": {
        "command": "matang",
        "label_ui": "MATANG (MERAH)",
        "warna_bgr": (0, 0, 255),
    },
    "mentah": {
        "command": "mentah",
        "label_ui": "MENTAH (HIJAU)",
        "warna_bgr": (0, 255, 0),
    },
    "setengah_matang": {
        "command": "setengah_matang",
        "label_ui": "SETENGAH MATANG (KUNING)",
        "warna_bgr": (0, 255, 255),
    },
}

# ============================================================
# KOMUNIKASI SERIAL ESP32 (THREADED / NON-BLOCKING)
# ============================================================
# Menggunakan background worker thread agar operasi serial (I/O)
# tidak pernah memblokir loop video kamera (menjaga FPS tetap 30 FPS).
BAUD_RATE_ESP32 = 115200


class ESP32Worker(threading.Thread):
    def __init__(self, ser_instance, port_name):
        super().__init__(daemon=True)
        self.ser = ser_instance
        self.port_name = port_name
        self.queue_cmd = queue.Queue()
        self.sensor_value = "-"
        self.last_ack = "-"
        self.running = True
        self.lock = threading.Lock()

    def run(self):
        last_poll = 0.0
        while self.running and self.ser and self.ser.is_open:
            now = time.time()

            # 1. Kirim command jika ada di antrean
            try:
                cmd = self.queue_cmd.get_nowait()
                self.ser.reset_input_buffer()
                self.ser.write((cmd.strip() + "\n").encode())
                time.sleep(0.005)
                # Tunggu respon ACK singkat tanpa blocking lama
                t_wait = time.time()
                while time.time() - t_wait < 0.05:
                    if self.ser.in_waiting:
                        ack = self.ser.readline().decode(errors="ignore").strip()
                        if ack:
                            with self.lock:
                                self.last_ack = ack
                            print(f"[SERIAL] Respon ESP32: {ack}")
                            break
                    time.sleep(0.003)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[SERIAL ERROR] Kirim command: {e}")

            # 2. Polling sensor proximity konveyor setiap 300 ms jika antrean kosong
            if now - last_poll >= 0.3 and self.queue_cmd.empty():
                try:
                    self.ser.reset_input_buffer()
                    self.ser.write(b"se\n")
                    time.sleep(0.005)
                    t_wait = time.time()
                    while time.time() - t_wait < 0.05:
                        if self.ser.in_waiting:
                            val = self.ser.readline().decode(errors="ignore").strip()
                            if val:
                                with self.lock:
                                    self.sensor_value = val
                                break
                        time.sleep(0.003)
                    last_poll = now
                except Exception:
                    pass

            time.sleep(0.01)  # Jeda 10ms hemat CPU

    def send(self, cmd):
        self.queue_cmd.put(cmd)

    def get_sensor(self):
        with self.lock:
            return self.sensor_value

    def is_connected(self):
        return self.ser and self.ser.is_open

    def stop(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass


serial_worker = None


def init_serial():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Lewati virtual port Bluetooth agar tidak hang
        if "bluetooth" in port.description.lower():
            continue
        try:
            print(f"[SERIAL] Mengecek port {port.device}: {port.description} (Baud: {BAUD_RATE_ESP32})")
            temp_ser = serial.Serial(port.device, BAUD_RATE_ESP32, timeout=0.4)
            time.sleep(1.8)  # Tunggu inisialisasi boot hardware ESP32
            temp_ser.reset_input_buffer()
            temp_ser.write(b"go\n")
            time.sleep(0.2)
            for _ in range(3):
                resp = temp_ser.readline().decode(errors="ignore").strip()
                if "ok" in resp.lower():
                    print(f"[SERIAL] Berhasil terhubung ke {port.device} ({port.description})")
                    worker = ESP32Worker(temp_ser, port.device)
                    worker.start()
                    return worker
            temp_ser.close()
        except Exception:
            continue

    print("[SERIAL] Tidak ada ESP32 yang terhubung. Mode kamera mandiri aktif.")
    return None


serial_worker = init_serial()


# ============================================================
# ZONA INSPEKSI AKTIF KONVEYOR & VALIDASI WARNA FISIK
# ============================================================
# Tomat hanya diproses saat berada mantap di dalam zona tengah konveyor,
# agar tidak salah baca akibat potongan objek terpotong di tepi kamera.
ZONA_INSPEKSI = {
    "x_min": 0.12,  # 12% dari lebar kiri frame
    "x_max": 0.88,  # 88% dari lebar kiri frame
    "y_min": 0.08,  # 8% dari tinggi atas frame
    "y_max": 0.92,  # 92% dari tinggi atas frame
}


def validasi_hue_warna(crop_bgr, raw_hasil):
    """
    Guard rail spektrum warna fisik objektif.
    Mengeliminasi keraguan atau salah cabang pohon C4.5 jika spektrum warna fisik sangat jelas:
    1. Objek dominan merah jelas (merah > 55% & 2x kuning, atau merah > 60% & kuning < 25%) -> '0' (Matang / Merah)
    2. Objek dominan kuning murni (kuning > 55% & 1.5x merah, seperti motor TT kuning) -> '2' (Setengah Matang / Kuning)
    3. Objek dominan hijau murni (hijau > 60% & merah < 15%) -> '1' (Mentah / Hijau)
    """
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    mask = (hsv[:, :, 1] > 40) & (hsv[:, :, 2] > 40)
    if np.count_nonzero(mask) < 50:
        return raw_hasil

    hues = hsv[:, :, 0][mask]
    total = len(hues)
    merah_ratio = np.count_nonzero((hues < 14) | (hues >= 165)) / total
    kuning_ratio = np.count_nonzero((hues >= 14) & (hues < 34)) / total
    hijau_ratio = np.count_nonzero((hues >= 34) & (hues <= 85)) / total

    # 1. OBJEK DOMINAN MERAH JELAS (MATANG / '0')
    # Hilangkan keraguan jika C4.5 salah menebak mentah ('1') atau setengah matang ('2')
    if (merah_ratio > 0.55 and merah_ratio > (kuning_ratio * 2.0) and hijau_ratio < 0.15) or \
       (merah_ratio > 0.60 and kuning_ratio < 0.25 and hijau_ratio < 0.15):
        if str(raw_hasil) in ["1", "2"]:
            return "0"

    # 2. OBJEK DOMINAN KUNING MURNI (SETENGAH MATANG / '2')
    # Benda sangat kuning murni (seperti motor TT kuning atau tomat kuning)
    if kuning_ratio > 0.55 and kuning_ratio > (merah_ratio * 1.5) and hijau_ratio < 0.20:
        return "2"
    # C4.5 menebak mentah (hijau) tapi fisik dominan kuning
    if kuning_ratio > 0.45 and hijau_ratio < 0.20 and str(raw_hasil) == "1":
        return "2"
    # C4.5 menebak matang (merah) tapi fisik dominan kuning
    if kuning_ratio > 0.50 and kuning_ratio > (merah_ratio * 2.0) and str(raw_hasil) == "0":
        return "2"

    # 3. OBJEK DOMINAN HIJAU JELAS (MENTAH / '1')
    if hijau_ratio > 0.60 and merah_ratio < 0.15 and str(raw_hasil) in ["0", "2"]:
        return "1"

    return raw_hasil


# ============================================================
# DETEKSI OBJEK TOMAT & REGION OF INTEREST (ROI)
# ============================================================
def deteksi_objek_tomat(frame, min_area=2000):
    """
    Mendeteksi posisi objek tomat (merah/kuning/hijau) di frame kamera.
    Mengembalikan (crop_tomat, bbox, in_zone) jika ditemukan, atau (None, None, False) jika meja kosong.
    Model C4.5 dilatih pada potongan (crop) tomat murni (folder crops/),
    sehingga background meja hitam/kabel/konveyor harus dipisahkan agar prediksi 100% akurat.
    """
    h_frame, w_frame = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Mask warna objek tomat:
    # 1. Spektrum Merah bawah, Oranye, Kuning, dan Hijau: Hue 0 s/d 88
    # 2. Spektrum Merah atas (wrap-around HSV): Hue 160 s/d 180
    # Memfilter background konveyor abu-abu/hitam/biru/ungu
    mask1 = cv2.inRange(hsv, (0, 40, 40), (88, 255, 255))
    mask2 = cv2.inRange(hsv, (160, 40, 40), (180, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)

    # Bersihkan noise kamera dengan filter morfologi
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None, False

    # Ambil kontur terbesar (objek tomat)
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)

    # Hanya proses jika luas objek mencukupi (bukan bayangan / kabel kecil)
    if area < min_area:
        return None, None, False

    x, y, w, h = cv2.boundingRect(c)

    # Cek apakah titik tengah objek berada di dalam Zona Inspeksi Konveyor
    cx = x + w // 2
    cy = y + h // 2
    in_zone = (
        int(w_frame * ZONA_INSPEKSI["x_min"]) <= cx <= int(w_frame * ZONA_INSPEKSI["x_max"])
        and int(h_frame * ZONA_INSPEKSI["y_min"]) <= cy <= int(h_frame * ZONA_INSPEKSI["y_max"])
    )

    # Berikan sedikit margin (padding) agar bentuk utuh tomat masuk
    pad = 8
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w_frame, x + w + pad)
    y2 = min(h_frame, y + h + pad)

    crop = frame[y1:y2, x1:x2]
    return crop, (x, y, w, h), in_zone


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
def tampilkan(frame, langkah, hasil, port_info="TIDAK TERHUBUNG", status_sensor="-", fps=0.0, bbox=None, in_zone=False):

    tinggi, lebar = frame.shape[:2]

    # ========================================================
    # GAMBAR ZONA INSPEKSI KONVEYOR & BOUNDING BOX
    # ========================================================
    zx1 = int(lebar * ZONA_INSPEKSI["x_min"])
    zx2 = int(lebar * ZONA_INSPEKSI["x_max"])
    zy1 = int(tinggi * ZONA_INSPEKSI["y_min"])
    zy2 = int(tinggi * ZONA_INSPEKSI["y_max"])
    warna_zona = (0, 200, 0) if in_zone else (75, 75, 75)
    cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), warna_zona, 1, cv2.LINE_AA)
    cv2.putText(
        frame,
        "ZONA INSPEKSI",
        (zx1 + 6, zy1 + 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        warna_zona,
        1,
        cv2.LINE_AA,
    )

    if bbox is not None:
        bx, by, bw, bh = bbox
        if not in_zone:
            warna_box = (150, 150, 150)
            label_box = "MENUNGGU MASUK ZONA"
        elif hasil is not None:
            info_k = KELAS_MAP.get(str(hasil), {
                "command": str(hasil),
                "label_ui": str(hasil),
                "warna_bgr": (0, 255, 0),
            })
            warna_box = info_k["warna_bgr"]
            label_box = f"{info_k['label_ui']} ({hasil})"
        else:
            warna_box = (0, 255, 255)
            label_box = "MENGANALISIS..."

        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), warna_box, 2)
        cv2.putText(
            frame,
            label_box,
            (bx, max(22, by - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            warna_box,
            2,
        )

    # Panel kanan
    panel_lebar = 480

    panel = np.zeros((tinggi, panel_lebar, 3), dtype=np.uint8)

    panel[:] = (30, 30, 30)

    # ========================================================
    # JUDUL & STATUS KONEKSI
    # ========================================================

    cv2.putText(
        panel,
        "C4.5 REALTIME",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
    )

    # Tampilkan FPS realtime
    fps_teks = f"FPS: {fps:.1f}"
    cv2.putText(
        panel,
        fps_teks,
        (370, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        1,
    )

    cv2.putText(
        panel,
        "PREDIKSI HISTOGRAM HSV",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (200, 200, 200),
        1,
    )

    # Indikator status koneksi ESP32 & sensor konveyor
    is_connected = port_info and "COM" in str(port_info).upper()
    status_warna = (0, 255, 0) if is_connected else (100, 100, 255)
    status_teks = f"ESP32: {port_info}"
    cv2.putText(
        panel,
        status_teks,
        (20, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        status_warna,
        1,
    )

    sensor_teks = f"Sensor: {status_sensor}"
    cv2.putText(
        panel,
        sensor_teks,
        (280, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 220),
        1,
    )

    # ========================================================
    # INFORMASI PROSES DECISION TREE
    # ========================================================

    y = 115

    cv2.putText(
        panel,
        "PROSES DECISION TREE:",
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (0, 255, 255),
        1,
    )

    y += 26

    if hasil is None or not langkah:
        cv2.putText(
            panel,
            "Menunggu objek tomat di depan kamera...",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (140, 140, 140),
            1,
        )
    else:
        # Tampilkan beberapa langkah tree
        for langkah_tree in langkah:

            text = f"{langkah_tree['nomor']}. " f"{langkah_tree['perbandingan']}"

            # Jika terlalu panjang, potong
            if len(text) > 46:
                text = text[:46] + "..."

            cv2.putText(
                panel, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1
            )

            y += 22

            if y > tinggi - 110:
                cv2.putText(
                    panel, "...", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1
                )
                break

    # ========================================================
    # HASIL PREDIKSI
    # ========================================================

    kotak_y1 = tinggi - 90
    kotak_y2 = tinggi - 15

    if hasil is None:
        cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), (45, 45, 45), -1)
        cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), (100, 100, 100), 2)
        cv2.putText(
            panel,
            "STATUS SISTEM:",
            (25, kotak_y1 + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (180, 180, 180),
            1,
        )
        cv2.putText(
            panel,
            "SIAGA / STANDBY",
            (25, kotak_y1 + 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (150, 150, 150),
            2,
        )
    else:
        info_kelas = KELAS_MAP.get(str(hasil), {
            "command": str(hasil),
            "label_ui": str(hasil),
            "warna_bgr": (0, 255, 0),
        })
        warna_aksen = info_kelas["warna_bgr"]

        cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), (45, 45, 45), -1)
        cv2.rectangle(panel, (15, kotak_y1), (panel_lebar - 15, kotak_y2), warna_aksen, 2)

        cv2.putText(
            panel,
            f"PREDIKSI (KODE {hasil}):",
            (25, kotak_y1 + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (200, 200, 200),
            1,
        )

        cv2.putText(
            panel,
            info_kelas["label_ui"],
            (25, kotak_y1 + 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            warna_aksen,
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
    # KAMERA (OPTIMASI LOGITECH C270 HD WEBCAM)
    # ========================================================

    print(f"[INFO] Membuka kamera Logitech (index {INDEX_KAMERA}, backend: {'V4L2 (Linux)' if IS_LINUX else 'DSHOW (Windows)'})...")
    kamera = cv2.VideoCapture(INDEX_KAMERA, BACKEND_KAMERA)

    if not kamera.isOpened():
        fallback_idx = 0 if INDEX_KAMERA == 1 else 1
        print(f"[WARN] Kamera index {INDEX_KAMERA} gagal dibuka, mencoba index {fallback_idx}...")
        kamera = cv2.VideoCapture(fallback_idx, BACKEND_KAMERA)

    if not kamera.isOpened():
        print("[ERROR] Kamera tidak dapat dibuka. Pastikan webcam terhubung dan tidak sedang digunakan aplikasi lain.")
        exit()

    # Tiga kunci agar Logitech C270 berjalan halus di 30 FPS tanpa patah-patah:
    # 1. Codec MJPG: Mengaktifkan kompresi hardware bawaan kamera C270 (sangat ringan di USB 2.0)
    # 2. Resolusi standar 640x480: Menjamin 30 FPS stabil dan CPU tetap dingin
    # 3. Buffer Size 1: Mencegah delay/lag antrean frame, tampilan selalu realtime
    kamera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    kamera.set(cv2.CAP_PROP_FRAME_WIDTH, UKURAN_FRAME[0])
    kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, UKURAN_FRAME[1])
    kamera.set(cv2.CAP_PROP_FPS, 30)
    kamera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("[INFO] Menstabilkan sensor auto-exposure kamera...")
    # Warmup beberapa frame awal agar sensor auto-exposure (RightLight) Logitech stabil
    for _ in range(10):
        kamera.read()
        time.sleep(0.01)

    lebar_aktif = int(kamera.get(cv2.CAP_PROP_FRAME_WIDTH))
    tinggi_aktif = int(kamera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Kamera aktif (Backend: {kamera.getBackendName()}, Resolusi: {lebar_aktif}x{tinggi_aktif})")

    # ========================================================
    # WINDOW
    # ========================================================

    window_name = "C4.5 - Prediksi Realtime"

    cv2.namedWindow(window_name)

    # ========================================================
    # LOOP VIDEO
    # ========================================================

    hasil = None
    langkah = []
    last_hasil = None
    last_command_sent = None
    waktu_kirim_terakhir = 0.0
    COOLDOWN_SERVO = 1.8  # Jeda aman (detik) sesuai siklus S-Curve: buka (0.4s) + tahan (0.8s) + tutup (0.4s) = 1.6s
    buffer_prediksi = deque(maxlen=7)  # Buffer 7 frame (~0.23s pada 30 FPS) untuk konsensus cepat & stabil
    sudah_dieksekusi_untuk_objek_ini = False
    frames_kosong = 5  # Mulai dalam kondisi standby awal

    t_awal = time.time()
    frame_count = 0
    fps_hitung = 0.0

    print("[INFO] Memulai loop video... Tekan 'Q' untuk keluar.")

    while True:
        waktu_sekarang = time.time()

        # Hitung FPS secara berkala
        frame_count += 1
        if waktu_sekarang - t_awal >= 1.0:
            fps_hitung = frame_count / (waktu_sekarang - t_awal)
            frame_count = 0
            t_awal = waktu_sekarang

        # Ambil nilai sensor proximity dari background thread secara instan (0 ms)
        respon_sensor = serial_worker.get_sensor() if serial_worker else "-"

        ret, frame = kamera.read()

        if not ret or frame is None:
            time.sleep(0.005)
            continue

        # Mirror kamera
        frame = cv2.flip(frame, 1)

        # Resize jika ukuran frame berbeda dengan UKURAN_FRAME
        if frame.shape[1] != UKURAN_FRAME[0] or frame.shape[0] != UKURAN_FRAME[1]:
            frame = cv2.resize(frame, UKURAN_FRAME)

        # ====================================================
        # DETEKSI OBJEK TOMAT (ROI CROPPING & ZONA INSPEKSI)
        # ====================================================
        crop_tomat, bbox, in_zone = deteksi_objek_tomat(frame)

        if crop_tomat is not None and in_zone:
            frames_kosong = 0

            # 1. Ekstraksi fitur HSV HANYA dari area tomat murni
            fitur = ekstrak_fitur_frame(crop_tomat)
            langkah, raw_hasil = telusuri_tree(model, fitur)

            # 2. Validasi spektrum warna fisik (Hue Guard Rail)
            final_raw = validasi_hue_warna(crop_tomat, raw_hasil)

            # 3. Filter Stabilisasi: Masukkan ke buffer suara terbanyak (Majority Voting)
            buffer_prediksi.append(str(final_raw))
            counter = Counter(buffer_prediksi)
            stable_hasil, count = counter.most_common(1)[0]
            hasil = stable_hasil

            info_kelas = KELAS_MAP.get(str(hasil), {
                "command": str(hasil),
                "label_ui": str(hasil),
                "warna_bgr": (0, 255, 0),
            })

            # 4. Kirim ke ESP32 tepat SATU KALI per objek tomat ketika sudah stabil & cooldown selesai
            if (not sudah_dieksekusi_untuk_objek_ini) and (count >= 4) and (waktu_sekarang - waktu_kirim_terakhir >= COOLDOWN_SERVO):
                print(f"[INFO] Prediksi Terkonfirmasi: {hasil} ({info_kelas['label_ui']}) -> Mengirim: '{info_kelas['command']}'")

                if serial_worker and serial_worker.is_connected():
                    serial_worker.send(info_kelas["command"])
                else:
                    print(f"[SERIAL] ESP32 tidak terhubung, perintah '{info_kelas['command']}' dilewati.")

                sudah_dieksekusi_untuk_objek_ini = True
                last_hasil = hasil
                last_command_sent = info_kelas["command"]
                waktu_kirim_terakhir = waktu_sekarang

        else:
            # Objek di luar zona inspeksi atau meja / konveyor kosong
            frames_kosong += 1
            if frames_kosong >= 5:  # Debounce ~150ms agar objek benar-benar terkonfirmasi lewat
                buffer_prediksi.clear()
                hasil = None
                langkah = []
                sudah_dieksekusi_untuk_objek_ini = False
                if waktu_sekarang - waktu_kirim_terakhir >= COOLDOWN_SERVO:
                    last_hasil = None
                    last_command_sent = None

        # ====================================================
        # TAMPILKAN
        # ====================================================

        status_port = serial_worker.port_name if (serial_worker and serial_worker.is_connected()) else "TIDAK TERHUBUNG"
        output = tampilkan(frame, langkah, hasil, port_info=status_port, status_sensor=respon_sensor, fps=fps_hitung, bbox=bbox, in_zone=in_zone)

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

    if serial_worker:
        serial_worker.stop()
        print("[SERIAL] Koneksi serial ditutup.")

    kamera.release()
    cv2.destroyAllWindows()
