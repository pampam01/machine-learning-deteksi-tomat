#!/bin/bash
# ============================================================
# SCRIPT UNTUK MENGHAPUS / MEMATIKAN AUTOSTART BACKGROUND SERVICE
# Gunakan script ini jika ingin kembali menjalankan sistem secara
# manual dengan tampilan layar monitor / HDMI.
# ============================================================

echo "============================================================"
echo "  MEMATIKAN AUTOSTART BACKGROUND SERVICE"
echo "============================================================"

# Pastikan dijalankan dengan sudo
if [ "$EUID" -ne 0 ]; then
  echo "[PERINGATAN] Silakan jalankan script ini dengan sudo:"
  echo "sudo bash copot_autostart.sh"
  exit 1
fi

echo "[INFO] Menghentikan service pemilah-tomat..."
systemctl stop pemilah-tomat 2>/dev/null || true

echo "[INFO] Menonaktifkan autostart saat boot..."
systemctl disable pemilah-tomat 2>/dev/null || true

echo "[INFO] Menghapus file service..."
rm -f /etc/systemd/system/pemilah-tomat.service

echo "[INFO] Reload daemon systemd..."
systemctl daemon-reload

echo ""
echo "============================================================"
echo "  SUKSES! AUTOSTART SERVICE TELAH DICOPOT"
echo "============================================================"
echo "Sekarang Anda bisa kembali menjalankan program secara manual"
echo "di layar monitor HDMI dengan perintah biasa:"
echo "  ./jalankan.sh"
echo "Jendela kamera dan UI prediksi akan langsung muncul di monitor!"
echo "============================================================"
