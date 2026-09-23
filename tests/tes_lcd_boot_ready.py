import serial
import serial.tools.list_ports
import time
import sys

# ============================================================
# SCRIPT UJI COBA STATUS LCD BOOTING & READY ESP32
# ============================================================
BAUD = 115200

def cari_port_esp32():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "bluetooth" in p.description.lower():
            continue
        print(f"[PORT] Ditemukan: {p.device} - {p.description}")
        return p.device
    return None

def main():
    print("=" * 60)
    print("   UJI COBA TAMPILAN LCD: BOOTING -> READY -> NORMAL")
    print("============================================================")
    
    port = cari_port_esp32()
    if not port:
        print("[ERROR] Port serial ESP32 tidak terdeteksi. Colokkan kabel USB ESP32.")
        return

    print(f"[INFO] Membuka port {port} pada {BAUD} baud...")
    ser = serial.Serial(port, BAUD, timeout=0.5)
    time.sleep(2.0)  # Tunggu auto-reset ESP32

    # Baca pesan boot awal ESP32
    while ser.in_waiting:
        print("ESP32:", ser.readline().decode(errors="ignore").strip())

    print("\n1. Mengirim perintah: 'booting'...")
    ser.write(b"booting\n")
    time.sleep(1.0)
    print("   -> Periksa LCD: Seharusnya menampilkan:")
    print("      Baris 1: SISTEM BOOTING.. (animasi titik)")
    print("      Baris 2: MOHON TUNGGU...")

    print("\n   Menunggu 4 detik seolah-olah Raspberry Pi sedang loading Linux...")
    for i in range(4, 0, -1):
        print(f"   [Booting...] {i} detik tersisa...")
        time.sleep(1.0)

    print("\n2. Mengirim perintah: 'ready' (Raspberry Pi Selesai Booting)...")
    ser.write(b"ready\n")
    time.sleep(0.5)
    while ser.in_waiting:
        print("ESP32 ACK:", ser.readline().decode(errors="ignore").strip())

    print("   -> Periksa LCD: Seharusnya menampilkan:")
    print("      Baris 1:  SISTEM: READY! ")
    print("      Baris 2:  SIAP MEMILAH :)")

    print("\n   Menunggu 2.5 detik durasi banner...")
    time.sleep(2.8)

    print("   -> Periksa LCD: Layar sekarang otomatis di-CLEAR dan masuk ke:")
    print("      Baris 1: STATUS: HIDUP   ")
    print("      Baris 2: JML TOMAT: 0    ")

    print("\n============================================================")
    print("UJI COBA SELESAI DENGAN SUKSES!")
    print("============================================================")
    ser.close()

if __name__ == "__main__":
    main()
