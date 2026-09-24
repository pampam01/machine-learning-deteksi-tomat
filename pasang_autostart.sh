#!/bin/bash
# ============================================================
# SCRIPT PEMASANG AUTOSTART RASPBERRY PI (SYSTEMD SERVICE)
# Membuat sistem berjalan otomatis saat Raspberry Pi dinyalakan
# Tanpa perlu monitor HDMI, mouse, ataupun keyboard (Appliance Mode)
# ============================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
SERVICE_NAME="pemilah-tomat"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================================"
echo "  MEMASANG AUTO-RUN SISTEM PEMILAH TOMAT C4.5"
echo "============================================================"
echo "Direktori Kerja: $DIR"

# Pastikan dijalankan dengan hak akses root (sudo)
if [ "$EUID" -ne 0 ]; then
  echo ""
  echo "[PERINGATAN] Silakan jalankan script ini dengan sudo:"
  echo "sudo bash pasang_autostart.sh"
  exit 1
fi

TARGET_USER="${SUDO_USER:-root}"

# Tambahkan user ke grup video & dialout agar bisa mengakses kamera dan USB tanpa perlu sudo
if [ "$TARGET_USER" != "root" ]; then
    echo "[INFO] Memastikan user $TARGET_USER memiliki izin port USB & kamera (grup video, dialout)..."
    usermod -a -G video,dialout "$TARGET_USER" 2>/dev/null || true
fi

echo "[INFO] Menyiapkan service systemd di $SERVICE_FILE..."

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Sistem Deteksi dan Pemilah Tomat C4.5 (Appliance Mode)
After=network.target sound.target
Wants=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$DIR
ExecStart=/bin/bash $DIR/jalankan.sh
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=5
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PYTHONUNBUFFERED=1
Environment=HEADLESS=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[INFO] Memasang izin eksekusi..."
chmod +x "$DIR/jalankan.sh"
chmod 644 "$SERVICE_FILE"

echo "[INFO] Reload daemon systemd..."
systemctl daemon-reload

echo "[INFO] Mengaktifkan service pemilah-tomat agar jalan otomatis saat boot..."
systemctl enable ${SERVICE_NAME}.service

echo "[INFO] Menjalankan service sekarang..."
systemctl restart ${SERVICE_NAME}.service

echo ""
echo "============================================================"
echo "  SUKSES! AUTO-RUN BERHASIL DIAKTIFKAN"
echo "============================================================"
echo "Sistem sekarang akan OTOMATIS BERJALAN setiap kali"
echo "Raspberry Pi dinyalakan / dicolokkan ke adaptor listrik."
echo "Klien TIDAK PERLU mencolokkan kabel HDMI lagi!"
echo ""
echo "Status dan hitungan tomat dapat langsung dilihat di LCD ESP32"
echo "serta di web dashboard cPanel."
echo ""
echo "Perintah Pemeriksaan di Terminal Raspberry Pi:"
echo " - Cek status service : sudo systemctl status pemilah-tomat"
echo " - Lihat log realtime : sudo journalctl -u pemilah-tomat -f"
echo " - Matikan sementara  : sudo systemctl stop pemilah-tomat"
echo " - Hapus autostart    : sudo systemctl disable pemilah-tomat"
echo "============================================================"
