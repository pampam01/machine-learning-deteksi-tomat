#!/bin/bash
# ============================================================
# EZ MODE LAUNCHER: SISTEM DETEKSI & PEMILAH TOMAT C4.5
# Otomatis mendeteksi virtual environment dan menjalankan utama_hsv.py
# ============================================================

# Pindah ke direktori tempat script ini berada
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================================"
echo "   SISTEM PEMILAH TOMAT C4.5 - RASPBERRY PI (EZ MODE)"
echo "============================================================"
echo "Direktori Kerja: $DIR"

# Langsung gunakan Python sistem Raspberry Pi (Murni Tanpa Venv)
PYTHON_BIN="/usr/bin/python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN="$(which python3)"
fi
echo "[INFO] Python yang digunakan: $PYTHON_BIN (Sistem Global - Tanpa Venv)"

# Tunggu hingga perangkat kamera dan USB terinisialisasi saat boot awal (maksimal 8 detik)
echo "[INFO] Menunggu inisialisasi hardware kamera & USB..."
for i in {1..8}; do
    if ls /dev/video* >/dev/null 2>&1; then
        echo "[INFO] Node video terdeteksi pada detik ke-$i."
        break
    fi
    sleep 1
done

# Buka izin akses video dan serial jika diperlukan (jika punya akses sudo atau dijalankan root)
if ls /dev/video* >/dev/null 2>&1; then
    chmod 666 /dev/video* 2>/dev/null || sudo chmod 666 /dev/video* 2>/dev/null || true
fi
if ls /dev/ttyUSB* /dev/ttyACM* >/dev/null 2>&1; then
    chmod 666 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || sudo chmod 666 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
fi

echo "[INFO] Menjalankan sistem pemilah tomat C4.5..."

# Cek apakah modul kamera Pi libcamera digunakan tanpa webcam USB
if command -v libcamerify >/dev/null 2>&1 && [ ! -e /dev/video0 ]; then
    echo "[INFO] Menjalankan via libcamerify untuk kamera Raspberry Pi..."
    libcamerify "$PYTHON_BIN" utama_hsv.py
else
    "$PYTHON_BIN" utama_hsv.py
fi

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "[PERINGATAN] Program berhenti dengan kode status: $EXIT_CODE"
    echo "============================================================"
    # HANYA tunggu input jika dijalankan dari terminal interaktif (bukan systemd / background)
    if [ -t 0 ]; then
        read -p "Tekan [ENTER] untuk menutup jendela ini..."
    else
        sleep 2
    fi
fi
exit $EXIT_CODE

