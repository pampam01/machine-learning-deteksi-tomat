#!/bin/bash
# ============================================================
# SCRIPT INSTALLASI DEPENDENCIES LANGSUNG DI OS (TANPA VENV)
# Sistem Deteksi & Pemilah Tomat C4.5 - Raspberry Pi
# ============================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================================"
echo "  INSTALLASI LIBRARY LANGSUNG DI OS RASPBERRY PI"
echo "  (MODE SISTEM GLOBAL - BEBAS DARI MASALAH VENV)"
echo "============================================================"

# Pastikan script dijalankan dengan sudo jika perlu izin apt
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] Menjalankan dengan hak akses root (sudo)..."
    exec sudo bash "$0" "$@"
fi

TARGET_USER="${SUDO_USER:-$USER}"
if [ "$TARGET_USER" = "root" ]; then
    TARGET_USER="pi"
fi

echo "[1/5] Memperbarui daftar paket sistem (apt update)..."
apt-get update -y

echo "[2/5] Menginstall library dasar & OpenCV resmi sistem Raspberry Pi..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-numpy \
    python3-opencv \
    python3-serial \
    python3-pil \
    python3-matplotlib \
    python3-tqdm \
    libatlas-base-dev \
    v4l-utils

echo "[3/5] Menginstall Scikit-Learn 1.5.2 langsung ke Python sistem..."
# Debian 12 Bookworm membutuhkan flag --break-system-packages untuk pip global
PIP_FLAGS="--upgrade"
if python3 -m pip install --help 2>&1 | grep -q -- "--break-system-packages"; then
    PIP_FLAGS="--upgrade --break-system-packages"
fi

# Install scikit-learn 1.5.2 dan pyserial langsung ke sistem
python3 -m pip install $PIP_FLAGS "scikit-learn==1.5.2" pyserial pillow tqdm matplotlib

echo "[4/5] Memberikan izin port USB & Kamera ke user $TARGET_USER..."
usermod -a -G video,dialout "$TARGET_USER" 2>/dev/null || true

# Hapus folder .venv lama jika ada agar tidak bentrok
if [ -d "$DIR/.venv" ] || [ -d "$DIR/venv" ]; then
    echo "[INFO] Menghapus folder virtual environment lama agar sistem bersih..."
    rm -rf "$DIR/.venv" "$DIR/venv" 2>/dev/null || true
fi

echo "[5/5] Memverifikasi instalasi Python..."
python3 -c "
import cv2
import sklearn
import serial
import numpy as np
import PIL
import tqdm
print('------------------------------------------------------------')
print('  [SUKSES] SEMUA LIBRARY BERHASIL DIINSTALL LANGSUNG DI OS!')
print(f'  - OpenCV      : {cv2.__version__}')
print(f'  - Scikit-Learn: {sklearn.__version__}')
print(f'  - NumPy       : {np.__version__}')
print('------------------------------------------------------------')
"

echo ""
echo "============================================================"
echo "  SELESAI! Sistem siap digunakan langsung tanpa venv."
echo "  Untuk menjalankan program sekarang, cukup ketik:"
echo "      python3 utama_hsv.py"
echo "  Atau jalankan launcher:"
echo "      bash jalankan.sh"
echo "============================================================"
