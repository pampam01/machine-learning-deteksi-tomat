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

# Cek apakah ada virtual environment (venv / .venv / env)
if [ -f "$DIR/.venv/bin/activate" ]; then
    echo "[INFO] Mengaktifkan virtual environment (.venv)..."
    source "$DIR/.venv/bin/activate"
elif [ -f "$DIR/venv/bin/activate" ]; then
    echo "[INFO] Mengaktifkan virtual environment (venv)..."
    source "$DIR/venv/bin/activate"
elif [ -f "$DIR/env/bin/activate" ]; then
    echo "[INFO] Mengaktifkan virtual environment (env)..."
    source "$DIR/env/bin/activate"
else
    echo "[INFO] Menggunakan Python sistem..."
fi

echo "[INFO] Menjalankan sistem pemilah tomat C4.5..."
python3 utama_hsv.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "[PERINGATAN] Program berhenti dengan kode status: $EXIT_CODE"
    echo "============================================================"
    read -p "Tekan [ENTER] untuk menutup jendela ini..."
fi
