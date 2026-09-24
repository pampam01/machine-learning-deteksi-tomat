#!/bin/bash
# ============================================================
# SCRIPT PERBAIKAN OTOMATIS: DPKG STATUS & SEMUA LIBRARY PYTHON
# Dijalankan dengan 1 perintah saja tanpa perlu ketik panjang!
# ============================================================

echo "============================================================"
echo "  MEMULAI PERBAIKAN OTOMATIS SISTEM & LIBRARY PYTHON"
echo "============================================================"

# 1. Pastikan dijalankan sebagai root (sudo)
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] Menjalankan dengan sudo..."
    exec sudo bash "$0" "$@"
fi

# 2. Pulihkan database dpkg yang korup dari backup resmi Linux
echo "[1/5] Memulihkan database paket sistem..."
if [ -f /var/backups/dpkg.status.0 ]; then
    cp /var/backups/dpkg.status.0 /var/lib/dpkg/status
elif [ -f /var/backups/dpkg.status.0.gz ]; then
    zcat /var/backups/dpkg.status.0.gz > /var/lib/dpkg/status
elif [ -f /var/lib/dpkg/status-old ]; then
    cp /var/lib/dpkg/status-old /var/lib/dpkg/status
fi

# 3. Bersihkan cache apt yang rusak
echo "[2/5] Membersihkan cache & memperbarui daftar paket..."
rm -rf /var/lib/apt/lists/*
apt-get clean
apt-get update -y || true

# 4. Hapus file OpenCV dan library yang korup (invalid ELF)
echo "[3/5] Menghapus file binary cv2 yang rusak..."
rm -rf /usr/lib/python3/dist-packages/cv2* 2>/dev/null || true
rm -rf /usr/local/lib/python3*/dist-packages/cv2* 2>/dev/null || true
rm -rf /home/*/.local/lib/python3*/site-packages/cv2* 2>/dev/null || true
rm -rf .venv venv 2>/dev/null || true

# 5. Pasang kembali paket OpenCV, NumPy, Serial, Sklearn
echo "[4/5] Menginstall ulang library Python secara bersih..."
apt-get install --reinstall -y \
    python3-opencv \
    python3-numpy \
    python3-serial \
    python3-pil \
    python3-matplotlib \
    python3-tqdm \
    python3-pip \
    libatlas-base-dev 2>/dev/null || true

# Install scikit-learn & dependencies via pip jika apt belum lengkap
PIP_FLAGS="--upgrade --break-system-packages"
python3 -m pip install $PIP_FLAGS scikit-learn pyserial pillow tqdm matplotlib opencv-python 2>/dev/null || \
python3 -m pip install --upgrade scikit-learn pyserial pillow tqdm matplotlib 2>/dev/null || true

# Beri izin USB dan kamera ke user asli
TARGET_USER="${SUDO_USER:-tiara}"
usermod -a -G video,dialout "$TARGET_USER" 2>/dev/null || true

# 6. Kunci semua perubahan ke fisik MicroSD
echo "[5/5] Mengunci data ke MicroSD (sync)..."
sync

echo ""
echo "============================================================"
echo "  HASIL PENGECEKAN LIBRARY:"
echo "============================================================"
python3 -c "
berhasil = True
for mod in ['cv2', 'sklearn', 'serial', 'numpy', 'PIL']:
    try:
        __import__(mod)
        print(f'  [OK] {mod} berhasil dimuat')
    except Exception as e:
        print(f'  [GAGAL] {mod}: {e}')
        berhasil = False
if berhasil:
    print('------------------------------------------------------------')
    print('  [MANTAP] SEMUA LIBRARY BERHASIL DIPULIHKAN 100%!')
    print('------------------------------------------------------------')
"
