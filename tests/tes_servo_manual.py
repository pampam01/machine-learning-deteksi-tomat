import serial
import serial.tools.list_ports
import time
import sys

def main():
    print("=" * 60)
    print("ALAT UJI MANUAL SERVO ESP32 (COM4 / AUTO)")
    print("=" * 60)

    port_name = "COM4"
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if port_name not in ports and len(ports) > 0:
        port_name = ports[0]

    print(f"Membuka port serial {port_name} (115200)...")
    try:
        ser = serial.Serial(port_name, 115200, timeout=1)
        time.sleep(1.8)
        ser.reset_input_buffer()
        ser.write(b"go\n")
        time.sleep(0.2)
        resp = ser.readline().decode(errors="ignore").strip()
        print(f"Respon ESP32: {resp}")
    except Exception as e:
        print(f"Gagal membuka {port_name}: {e}")
        print("Pastikan tidak ada program lain (seperti utama_hsv atau Serial Monitor) yang membuka COM4.")
        return

    def send_cmd(cmd):
        ser.reset_input_buffer()
        ser.write((cmd.strip() + "\n").encode())
        time.sleep(0.1)
        while ser.in_waiting:
            print("ESP32:", ser.readline().decode(errors="ignore").strip())

    print("\nPILIHAN UJI CEPAT S-CURVE & LCD I2C:")
    print(" [1] Gerak S-Curve Servo 1 ke 10 derajat (Matang / Buang Kiri)")
    print(" [2] Gerak S-Curve Servo 1 ke 80 derajat (Standby / Dinding Kiri)")
    print(" [3] Gerak S-Curve Servo 2 ke 155 derajat (Kuning / Buka Buang Kanan)")
    print(" [4] Gerak S-Curve Servo 2 ke 90 derajat  (Standby / Dinding Kanan)")
    print(" [m] Siklus Matang: Buka S-Curve Cepat -> Tahan 8.4s -> Tutup Halus (Servo 1)")
    print(" [k] Siklus Kuning: Buka S-Curve Cepat -> Tahan 9.0s -> Tutup Halus (Servo 2)")
    print(" [t] Uji Cepat Berurutan Kedua Servo (Quick Test Sequence)")
    print(" [h] LCD: Ubah Status Sistem ke HIDUP")
    print(" [x] LCD: Ubah Status Sistem ke MATI")
    print(" [r] LCD: Reset Jumlah Tomat ke 0")
    print(" [s] LCD: Cek Status & Jumlah Tomat Saat Ini")
    print(" [q] Keluar")
    print("-" * 60)

    try:
        while True:
            pilih = input("\nMasukkan pilihan [1/2/3/4/m/k/t/h/x/r/s/q]: ").strip().lower()
            if pilih == "1":
                print("Mengirim: s1 10 (S-Curve Buang Kiri)")
                send_cmd("s1 10")
            elif pilih == "2":
                print("Mengirim: s1 80 (S-Curve Standby Kiri)")
                send_cmd("s1 80")
            elif pilih == "3":
                print("Mengirim: s2 155 (S-Curve Buka Buang Kanan)")
                send_cmd("s2 155")
            elif pilih == "4":
                print("Mengirim: s2 90 (S-Curve Standby Kanan)")
                send_cmd("s2 90")
            elif pilih == "m":
                print("Mengirim: matang (Buka Cepat -> Tahan 8.4 detik -> Tutup Halus)")
                send_cmd("matang")
                print("Servo 1 membuka dan menahan 8.4 detik...")
            elif pilih == "k":
                print("Mengirim: kuning (Buka Cepat -> Tahan 9.0 detik -> Tutup Halus)")
                send_cmd("kuning")
                print("Servo 2 membuka dan menahan 9.0 detik...")
            elif pilih == "t":
                print("Mengirim: test (S-Curve Sequence)")
                send_cmd("test")
                time.sleep(3.5)
                while ser.in_waiting:
                    print("ESP32:", ser.readline().decode(errors="ignore").strip())
            elif pilih == "h":
                print("Mengirim: hidup (LCD Status HIDUP)")
                send_cmd("hidup")
            elif pilih == "x":
                print("Mengirim: mati (LCD Status MATI)")
                send_cmd("mati")
            elif pilih == "r":
                print("Mengirim: reset_tomat (Reset Counter Tomat)")
                send_cmd("reset_tomat")
            elif pilih == "s":
                print("Mengirim: status")
                send_cmd("status")
            elif pilih == "q":
                break
            else:
                print("Pilihan tidak valid.")
    finally:
        ser.close()
        print("Koneksi ditutup.")

if __name__ == "__main__":
    main()
