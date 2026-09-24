#!/bin/bash
# ============================================================
# SCRIPT INSTALLASI DEPENDENCIES LANGSUNG DI OS (RESMI & STABIL)
# Sistem Deteksi & Pemilah Tomat C4.5 - Raspberry Pi OS (Bookworm)
# ============================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================================"
echo "  INSTALLASI RESMI LIBRARY DI OS RASPBERRY PI"
echo "  (MODE SISTEM RESMI GLOBAL - BEBAS VENV & AMAN DARI ROOT)"
echo "============================================================"

# 1. Pastikan script memiliki hak akses root (sudo)
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] Menjalankan dengan hak akses root (sudo)..."
    exec sudo bash "$0" "$@"
fi

# 2. Deteksi otomatis nama user asli (tiara / pi) meski dijalankan lewat 'sudo su'
TARGET_USER="${SUDO_USER:-$USER}"
if [ "$TARGET_USER" = "root" ] || [ -z "$TARGET_USER" ]; then
    # Deteksi user yang memiliki folder di /home
    TARGET_USER="$(ls -1 /home 2>/dev/null | head -n 1)"
    if [ -z "$TARGET_USER" ]; then
        TARGET_USER="tiara"
    fi
fi
echo "[INFO] User sistem yang digunakan: $TARGET_USER"

# 3. Pulihkan hak milik folder proyek agar tidak terkunci root (Mencegah error Git & Bad Message)
echo "[INFO] Menyelaraskan izin kepemilikan folder ke user $TARGET_USER..."
chown -R "$TARGET_USER:$TARGET_USER" "$DIR" 2>/dev/null || true
sudo -u "$TARGET_USER" git config --global --add safe.directory "$DIR" 2>/dev/null || true
git config --global --add safe.directory "$DIR" 2>/dev/null || true

echo "[1/5] Memperbarui daftar paket sistem resmi (apt update)..."
apt-get update -y

echo "[2/5] Menginstall library resmi sistem Raspberry Pi (OpenCV, NumPy, Serial, Sklearn)..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-numpy \
    python3-opencv \
    python3-serial \
    python3-pil \
    python3-matplotlib \
    python3-tqdm \
    python3-sklearn \
    libatlas-base-dev \
    v4l-utils

echo "[3/5] Memastikan Scikit-Learn 1.5.2 & PySerial terpasang sempurna..."
# Debian 12 Bookworm membutuhkan flag --break-system-packages untuk pip global
PIP_FLAGS="--upgrade --break-system-packages"
python3 -m pip install $PIP_FLAGS "scikit-learn==1.5.2" pyserial pillow tqdm matplotlib 2>/dev/null || \
python3 -m pip install --upgrade "scikit-learn==1.5.2" pyserial pillow tqdm matplotlib 2>/dev/null || true

echo "[4/5] Memberikan izin port USB ESP32 & Kamera ke user $TARGET_USER..."
usermod -a -G video,dialout "$TARGET_USER" 2>/dev/null || true

# Hapus folder .venv lama jika ada agar tidak bentrok
if [ -d "$DIR/.venv" ] || [ -d "$DIR/venv" ]; then
    echo "[INFO] Menghapus folder virtual environment lama agar sistem bersih..."
    rm -rf "$DIR/.venv" "$DIR/venv" 2>/dev/null || true
fi

# Kembalikan lagi hak milik folder proyek ke TARGET_USER setelah pip/apt
chown -R "$TARGET_USER:$TARGET_USER" "$DIR" 2>/dev/null || true

# Kunci seluruh penulisan ke kartu MicroSD secara fisik
sync

echo "[5/5] Memverifikasi instalasi Python..."
python3 -c "
import cv2
import sklearn
import serial
import numpy as np
import PIL
import tqdm
print('------------------------------------------------------------')
print('  [SUKSES] SEMUA LIBRARY RESMI BERHASIL DIINSTALL DI OS!')
print(f'  - OpenCV      : {cv2.__version__}')
print(f'  - Scikit-Learn: {sklearn.__version__}')
print(f'  - NumPy       : {np.__version__}')
print(f'  - PySerial    : {serial.__version__}')
print('------------------------------------------------------------')
"

echo ""
echo "============================================================"
echo "  SELESAI! Sistem siap digunakan langsung tanpa venv."
echo "  Izin folder sudah dinormalkan, Git tidak perlu sudo su lagi."
echo ""
echo "  Untuk menjalankan program sekarang, cukup ketik:"
echo "      python3 utama_hsv.py"
echo "  Atau pasang autostart background:"
echo "      sudo bash pasang_autostart.sh"
echo "============================================================"
