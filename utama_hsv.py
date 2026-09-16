import cv2
import numpy as np
import pickle
import time
import os
import sys
import threading
import queue
import urllib.request
import uuid
from collections import deque, Counter

python = sys.executable

import serial
import serial.tools.list_ports

print("path PYTHON === >", python)  # ini venv yang aktif di VSCode)


# ============================================================
# KONFIGURASI PATH & SISTEM
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model_c45_hist.pkl")

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
# KONFIGURASI WEB API / CPANEL & SENSOR IR
# ============================================================
# Endpoint Web API cPanel aktif untuk pengiriman data klasifikasi realtime
WEB_API_URL = "https://localhost.scode.web.id/2026-tiara-tomat/api/klasifikasi.php"
WEB_API_ENABLED = True
KIRIM_FOTO_TOMAT = True
# Throttle jeda antar pengiriman ke web agar aman dari rate limiting / ModSecurity cPanel (10s window)
WEB_API_THROTTLE_DETIK = 2.0


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
        self.ir_triggered = False
        self.ir_count = 0
        self.running = True
        self.lock = threading.Lock()

    def _drain_incoming_lines(self):
        """Membaca dan memproses semua baris serial yang ada di buffer tanpa membuang event IR."""
        while self.ser and self.ser.is_open and self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if "event_ir_trigger" in line.lower():
                    with self.lock:
                        self.ir_triggered = True
                        self.ir_count += 1
                    print(f"[SENSOR IR] Tomat terdeteksi melewati sensor IR (GPIO 32)! Total hitung: {self.ir_count}")
                elif "ack" in line.lower() or "ok" in line.lower():
                    with self.lock:
                        self.last_ack = line
                elif line in ("0", "1"):
                    with self.lock:
                        self.sensor_value = line
            except Exception:
                break

    def run(self):
        last_poll = 0.0
        while self.running and self.ser and self.ser.is_open:
            now = time.time()

            # 0. Dapatkan semua pesan tak terjadwal dari ESP32 (misal EVENT_IR_TRIGGER)
            self._drain_incoming_lines()

            # 1. Kirim command jika ada di antrean
            try:
                cmd = self.queue_cmd.get_nowait()
                self._drain_incoming_lines()  # Jangan buang data serial sebelum kirim!
                self.ser.write((cmd.strip() + "\n").encode())
                time.sleep(0.005)
                # Tunggu respon ACK singkat tanpa blocking lama
                t_wait = time.time()
                while time.time() - t_wait < 0.05:
                    if self.ser.in_waiting:
                        ack = self.ser.readline().decode(errors="ignore").strip()
                        if ack:
                            if "event_ir_trigger" in ack.lower():
                                with self.lock:
                                    self.ir_triggered = True
                                    self.ir_count += 1
                                print(f"[SENSOR IR] Tomat terdeteksi (GPIO 32)! Total hitung: {self.ir_count}")
                            else:
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
                    self._drain_incoming_lines()
                    self.ser.write(b"se\n")
                    time.sleep(0.005)
                    t_wait = time.time()
                    while time.time() - t_wait < 0.05:
                        if self.ser.in_waiting:
                            val = self.ser.readline().decode(errors="ignore").strip()
                            if val:
                                if "event_ir_trigger" in val.lower():
                                    with self.lock:
                                        self.ir_triggered = True
                                        self.ir_count += 1
                                else:
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

    def pop_ir_trigger(self):
        with self.lock:
            val = self.ir_triggered
            self.ir_triggered = False
            return val

    def get_ir_count(self):
        with self.lock:
            return self.ir_count

    def is_connected(self):
        return self.ser and self.ser.is_open

    def stop(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(b"mati\n")
                    time.sleep(0.05)
                except Exception:
                    pass
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
            temp_ser = serial.Serial(port.device, BAUD_RATE_ESP32, timeout=0.25)
            # ESP32 auto-reset saat serial dibuka (DTR/RTS).
            # Lakukan handshake aktif berulang selama s/d 4.5 detik
            t_mulai = time.time()
            terhubung = False
            while time.time() - t_mulai < 4.5:
                temp_ser.write(b"go\n")
                time.sleep(0.2)
                while temp_ser.in_waiting:
                    baris = temp_ser.readline().decode(errors="ignore").strip().lower()
                    if "ok" in baris or "esp32_ready" in baris:
                        terhubung = True
                        break
                if terhubung:
                    break
                time.sleep(0.15)

            if terhubung:
                print(f"[SERIAL] Berhasil terhubung ke {port.device} ({port.description})")
                worker = ESP32Worker(temp_ser, port.device)
                worker.start()
                return worker
            else:
                temp_ser.close()
        except Exception as e:
            print(f"[SERIAL] Gagal membuka {port.device}: {e}")
            continue

    print("[SERIAL] Tidak ada ESP32 yang terhubung. Mode kamera mandiri aktif.")
    return None


serial_worker = init_serial()


# ============================================================
# WORKER PENGIRIMAN WEB API / CPANEL (NON-BLOCKING & ANTI-RATE LIMIT)
# ============================================================
class WebAPIWorker(threading.Thread):
    """
    Background worker mandiri untuk mengirim data hasil pemilahan dan foto tomat
    ke API web (cPanel / Apache / PHP) secara non-blocking (kamera tetap 30 FPS halus).
    Memiliki fitur perlindungan:
    - Rate-limiting throttle (jeda aman >= 2 detik antar request agar tidak diblokir ModSecurity cPanel)
    - Browser standard User-Agent header (mencegah WAF blocking)
    - Connection: close header (mencegah deadlock socket keep-alive)
    - Kompresi JPEG otomatis sebelum upload
    - Auto-retry hingga 3 kali jika ada gangguan koneksi sementara
    - Offline fallback journal (riwayat_offline.jsonl) agar tidak ada data yang hilang
    """
    def __init__(self, url, enabled=True, throttle_detik=2.0):
        super().__init__(daemon=True)
        self.url = url
        self.enabled = enabled
        self.throttle_detik = throttle_detik
        self.queue = queue.Queue(maxsize=100)
        self.running = True
        self.total_terkirim = 0
        self.total_gagal = 0
        self.status_terakhir = "STANDBY"
        self.waktu_kirim_terakhir = 0.0
        self.lock = threading.Lock()
        self.offline_file = os.path.join(BASE_DIR, "riwayat_offline.jsonl")

    def send(self, label, confidence=0.96, metode="realtime_hsv", fitur="", crop_bgr=None):
        if not self.enabled:
            return
        payload = {
            "label": label,
            "confidence": float(confidence),
            "metode": metode,
            "fitur": fitur,
            "crop_bgr": crop_bgr.copy() if crop_bgr is not None else None,
        }
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            print("[WEB API WARN] Antrean upload penuh, membuang data lama.")

    def run(self):
        while self.running:
            try:
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # Jaga jeda antar request agar aman dari WAF / ModSecurity 10 detik cPanel
            selisih = time.time() - self.waktu_kirim_terakhir
            if selisih < self.throttle_detik:
                time.sleep(self.throttle_detik - selisih)

            sukses = self._post_data_with_retry(item)
            self.waktu_kirim_terakhir = time.time()
            with self.lock:
                if sukses:
                    self.total_terkirim += 1
                    self.status_terakhir = f"SUKSES ({self.total_terkirim})"
                else:
                    self.total_gagal += 1
                    self.status_terakhir = f"OFFLINE ({self.total_gagal})"

    def _post_data_with_retry(self, item):
        boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
        body_parts = []

        fields = {
            "label": item.get("label", "matang"),
            "confidence": str(item.get("confidence", 0.96)),
            "metode": item.get("metode", "realtime_hsv"),
            "fitur": item.get("fitur", ""),
        }

        for k, v in fields.items():
            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
            body_parts.append(f"{v}\r\n".encode("utf-8"))

        crop_bgr = item.get("crop_bgr")
        if crop_bgr is not None and crop_bgr.size > 0:
            sukses_encode, jpg_buffer = cv2.imencode(".jpg", crop_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if sukses_encode:
                nama_file = f"tomat_{int(time.time())}.jpg"
                body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
                body_parts.append(f'Content-Disposition: form-data; name="foto"; filename="{nama_file}"\r\n'.encode("utf-8"))
                body_parts.append(b"Content-Type: image/jpeg\r\n\r\n")
                body_parts.append(jpg_buffer.tobytes())
                body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        payload_bytes = b"".join(body_parts)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(payload_bytes)),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "close",
        }

        # Percobaan pengiriman dengan auto-retry (maksimal 3 kali)
        for attempt in range(1, 4):
            req = urllib.request.Request(self.url, data=payload_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    status_code = resp.status
                    if status_code in (200, 201):
                        print(f"[WEB API] Upload data berhasil ({status_code}) pada percobaan ke-{attempt}: {item.get('label')}")
                        return True
            except urllib.error.HTTPError as http_err:
                # Otomatis beralih jika server PHP lokal dijalankan di root (/web/api/klasifikasi.php) vs di folder web (/api/klasifikasi.php)
                if http_err.code == 404 and ("127.0.0.1" in self.url or "localhost:8000" in self.url or "localhost/" in self.url):
                    if "/web/api/" in self.url:
                        alt_url = self.url.replace("/web/api/", "/api/")
                    else:
                        alt_url = self.url.replace("/api/", "/web/api/")
                    print(f"[WEB API INFO] Endpoint 404 terdeteksi, otomatis beralih ke: {alt_url}")
                    self.url = alt_url
                    continue
                if attempt < 3:
                    print(f"[WEB API WARN] Percobaan {attempt} gagal ({http_err}), mencoba ulang dalam 1.0 detik...")
                    time.sleep(1.0)
                else:
                    print(f"[WEB API ERROR] Gagal mengirim data ke server web setelah 3 percobaan: {http_err}")
            except Exception as e:
                if attempt < 3:
                    print(f"[WEB API WARN] Percobaan {attempt} gagal ({e}), mencoba ulang dalam 1.0 detik...")
                    time.sleep(1.0)
                else:
                    print(f"[WEB API ERROR] Gagal mengirim data ke server web setelah 3 percobaan: {e}")

        # Fallback offline journaling: Catat ke file lokal agar tidak ada data yang hilang saat server offline
        try:
            cadangan = {
                "waktu": time.strftime("%Y-%m-%d %H:%M:%S"),
                "label": item.get("label"),
                "confidence": item.get("confidence"),
                "metode": item.get("metode"),
                "fitur": item.get("fitur"),
            }
            with open(self.offline_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(cadangan) + "\n")
            print(f"[WEB API OFFLINE] Data klasifikasi tersimpan aman di file cadangan lokal: {self.offline_file}")
        except Exception as file_err:
            print(f"[WEB API ERROR] Gagal menulis cadangan offline: {file_err}")

        return False

    def get_status(self):
        with self.lock:
            return self.status_terakhir, self.total_terkirim

    def stop(self):
        self.running = False


web_worker = None
if WEB_API_ENABLED:
    web_worker = WebAPIWorker(url=WEB_API_URL, enabled=True, throttle_detik=WEB_API_THROTTLE_DETIK)
    web_worker.start()
    print(f"[WEB API] Background worker aktif -> Target URL: {WEB_API_URL}")


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
def tampilkan(frame, langkah, hasil, port_info="TIDAK TERHUBUNG", status_sensor="-", fps=0.0, bbox=None, in_zone=False, ir_count=0, web_status="STANDBY"):

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
    is_connected = port_info and ("COM" in str(port_info).upper() or "TTY" in str(port_info).upper())
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

    sensor_teks = f"IR Count: {ir_count} | Sensor: {status_sensor}"
    cv2.putText(
        panel,
        sensor_teks,
        (230, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        (220, 220, 220),
        1,
    )

    # Indikator status Web API / cPanel
    web_teks = f"Web API: {web_status}"
    web_warna = (0, 255, 0) if ("SUKSES" in str(web_status) or "STANDBY" in str(web_status)) else (0, 165, 255)
    cv2.putText(
        panel,
        web_teks,
        (20, 108),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        web_warna,
        1,
    )

    # ========================================================
    # INFORMASI PROSES DECISION TREE
    # ========================================================

    y = 136

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

        # Ambil nilai sensor proximity dan status trigger IR secara instan (0 ms)
        respon_sensor = serial_worker.get_sensor() if serial_worker else "-"
        ir_terpicu = serial_worker.pop_ir_trigger() if serial_worker else False
        if ir_terpicu:
            print("[SENSOR IR] Buah tomat fisik terkonfirmasi melewati sensor proximity!")

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

            # 4. Syarat konfirmasi: Cukup 2 frame jika sensor IR mendeteksi objek fisik,
            # atau 4 frame jika murni mengandalkan deteksi visual kamera
            syarat_frame = 2 if ir_terpicu else 4

            # Kirim ke ESP32 tepat SATU KALI per objek tomat ketika sudah stabil & cooldown selesai
            if (not sudah_dieksekusi_untuk_objek_ini) and (count >= syarat_frame) and (waktu_sekarang - waktu_kirim_terakhir >= COOLDOWN_SERVO):
                print(f"[INFO] Prediksi Terkonfirmasi: {hasil} ({info_kelas['label_ui']}) -> Mengirim: '{info_kelas['command']}'")

                if serial_worker and serial_worker.is_connected():
                    serial_worker.send(info_kelas["command"])
                else:
                    print(f"[SERIAL] ESP32 tidak terhubung, perintah '{info_kelas['command']}' dilewati.")

                # Ekstraksi spektrum HSV & RGB fisik nyata dari tomat untuk dikirim ke web dashboard
                try:
                    hsv_crop = cv2.cvtColor(crop_tomat, cv2.COLOR_BGR2HSV)
                    mean_h = float(np.mean(hsv_crop[:, :, 0]))
                    mean_s = float(np.mean(hsv_crop[:, :, 1]))
                    mean_v = float(np.mean(hsv_crop[:, :, 2]))

                    mean_b = float(np.mean(crop_tomat[:, :, 0]))
                    mean_g = float(np.mean(crop_tomat[:, :, 1]))
                    mean_r = float(np.mean(crop_tomat[:, :, 2]))

                    ringkasan_fitur = f"HSV:({mean_h:.0f},{mean_s:.0f},{mean_v:.0f}) | RGB:({mean_r:.0f},{mean_g:.0f},{mean_b:.0f})"
                except Exception:
                    ringkasan_fitur = f"Kelas {hasil} ({info_kelas['label_ui']})"

                # Kirim data klasifikasi real & foto tomat ke Web API / cPanel secara non-blocking
                if web_worker:
                    web_worker.send(
                        label=info_kelas["command"],
                        confidence=0.96,
                        metode="realtime_hsv",
                        fitur=ringkasan_fitur,
                        crop_bgr=crop_tomat if KIRIM_FOTO_TOMAT else None,
                    )

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
        total_ir = serial_worker.get_ir_count() if serial_worker else 0
        status_web = web_worker.get_status()[0] if web_worker else "OFF"

        output = tampilkan(
            frame,
            langkah,
            hasil,
            port_info=status_port,
            status_sensor=respon_sensor,
            fps=fps_hitung,
            bbox=bbox,
            in_zone=in_zone,
            ir_count=total_ir,
            web_status=status_web,
        )

        cv2.imshow(window_name, output)

        # ====================================================
        # KEYBOARD
        # ====================================================

        tombol = cv2.waitKey(1) & 0xFF

        if tombol == ord("q"):
            break
        elif tombol == ord("r"):
            if serial_worker and serial_worker.is_connected():
                serial_worker.send("reset_tomat")
                print("[SERIAL] Reset counter tomat dikirim ke ESP32 LCD.")

    # ========================================================
    # CLEANUP
    # ========================================================

    if web_worker:
        web_worker.stop()
        print("[WEB API] Worker web dimatikan.")

    if serial_worker:
        serial_worker.stop()
        print("[SERIAL] Koneksi serial ditutup.")

    kamera.release()
    cv2.destroyAllWindows()
