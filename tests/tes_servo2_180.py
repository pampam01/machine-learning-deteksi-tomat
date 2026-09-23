import serial
import serial.tools.list_ports
import time
import sys

def cari_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ch340" in desc or "cp210" in desc or "uart" in desc or "usb" in desc:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return "COM4"

def kirim(ser, cmd, delay_detik=0.08):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode())
    time.sleep(delay_detik)
    respon = []
    while ser.in_waiting:
        baris = ser.readline().decode(errors="ignore").strip()
        if baris:
            respon.append(baris)
    return respon

def main():
    print("=" * 68)
    print("   ALAT UJI & PENYETEL ARAH SERVO 2 (KUNING / 180 DERAJAT)")
    print("=" * 68)

    port_pilihan = cari_port()
    print(f"[INFO] Mendeteksi port serial: {port_pilihan}")
    
    try:
        ser = serial.Serial(port_pilihan, 115200, timeout=0.5)
        time.sleep(1.8)
        ser.reset_input_buffer()
        resp = kirim(ser, "go", 0.2)
        print(f"[STATUS] Terhubung ke ESP32 di {port_pilihan} | Respon: {resp}")
    except Exception as e:
        print("\n" + "!" * 68)
        print(f"[ERROR] Gagal membuka port {port_pilihan}: {e}")
        print("!" * 68)
        print("KEMUNGKINAN PENYEBAB:")
        print("1. Port sedang digunakan oleh 'jalankan.bat' / 'utama_hsv.py'.")
        print("   -> Tutup jendela kamera (klik jendela lalu tekan tombol 'Q').")
        print("2. Serial Monitor Arduino IDE sedang terbuka.")
        print("   -> Tutup Serial Monitor di Arduino IDE.")
        print("!" * 68)
        input("\nTekan Enter untuk keluar...")
        return

    sudut_aktif = 90

    try:
        while True:
            print("\n" + "=" * 68)
            print("MENU PENGUJIAN & PENENTUAN ARAH SERVO 2:")
            print("=" * 68)
            print(f" [1] Uji Preset Utama (Standby 90° -> Buka 155° Ayun Halus Mikrodetik)")
            print(f" [2] Uji Variasi 160° (Standby 90° -> Buka 160°)")
            print(f" [3] Uji Variasi 145° (Standby 90° -> Buka 145°)")
            print(f" [4] PENYETEL LANGSUNG / ANGLE TUNER (Geser sudut per 5° atau 1° secara live)")
            print(f" [5] Uji Sudut Mentah Bertahap: 0°, 45°, 70°, 90°, 120°, 140°, 155°, 160°")
            print(f" [6] Uji Siklus Lengkap S-Curve (Buka Cepat -> Tahan 9.0s -> Tutup Halus)")
            print(f" [7] Atur Custom: Simpan Standby & Buka ke ESP32 saat ini")
            print(f" [8] Input Sudut Bebas (0 - 180 derajat)")
            print(f" [q] Keluar")
            print("-" * 68)
            
            pilih = input("Pilih menu [1/2/3/4/5/6/7/8/q]: ").strip().lower()
            
            if pilih == "1":
                print("\n-> MENGUJI PRESET UTAMA: Standby 90° (Dinding) -> Buka 155° (BUANG KANAN)")
                print("1. Gerak ke Standby (90°)...")
                kirim(ser, "raw2 90", 0.6)
                time.sleep(0.5)
                print("2. Ayun S-Curve HALUS MIKRODETIK (ke 155°)...")
                kirim(ser, "s2 155", 1.2)
                time.sleep(1.0)
                print("3. Kembali ke Standby HALUS (ke 90°)...")
                kirim(ser, "s2 90", 1.2)
                print("[OK] Apakah pergerakan 90° -> 155° halus tanpa hentakan/gedek-gedek?")
                
            elif pilih == "2":
                print("\n-> MENGUJI VARIASI 160: Standby 90° (Dinding) -> Buka 160°")
                print("1. Gerak ke Standby (90°)...")
                kirim(ser, "raw2 90", 0.6)
                time.sleep(0.5)
                print("2. Ayun S-Curve MASUK (ke 160°)...")
                kirim(ser, "s2 160", 1.2)
                time.sleep(1.0)
                print("3. Kembali ke Standby (ke 90°)...")
                kirim(ser, "s2 90", 1.2)
                print("[OK] Periksa sudut 160 derajat.")
                
            elif pilih == "3":
                print("\n-> MENGUJI VARIASI 145: Standby 90° -> Buka 145°")
                print("1. Gerak ke Standby (90°)...")
                kirim(ser, "raw2 90", 0.6)
                time.sleep(0.5)
                print("2. Ayun S-Curve (ke 145°)...")
                kirim(ser, "s2 145", 1.2)
                time.sleep(1.0)
                print("3. Kembali ke Standby (ke 90°)...")
                kirim(ser, "s2 90", 1.2)
                
            elif pilih == "4":
                print("\n" + "=" * 60)
                print("MODE PENYETEL LANGSUNG (LIVE ANGLE TUNER):")
                print("Perhatikan fisik lengan servo di konveyor sambil menekan tombol:")
                print("  [w] : Tambah sudut +5 derajat")
                print("  [s] : Kurang sudut -5 derajat")
                print("  [e] : Tambah sudut +1 derajat (halus)")
                print("  [d] : Kurang sudut -1 derajat (halus)")
                print("  [1] : Jadikan sudut saat ini sebagai STANDBY (Dinding)")
                print("  [2] : Jadikan sudut saat ini sebagai BUKA (Nyerong buang)")
                print("  [t] : Tes ayun antara Standby & Buka yang baru dipilih")
                print("  [x] : Selesai dan kembali ke menu utama")
                print("=" * 60)
                
                sudut_tuner = 90
                kirim(ser, f"raw2 {sudut_tuner}", 0.3)
                print(f"Posisi awal Servo 2: {sudut_tuner}°")
                
                cur_sb = 90
                cur_bk = 155
                
                while True:
                    cmd_t = input(f"\r[Posisi: {sudut_tuner:3d}° | SB={cur_sb}° BK={cur_bk}°] Tekan [w/s/e/d/1/2/t/x]: ").strip().lower()
                    if cmd_t == "w":
                        sudut_tuner = min(180, sudut_tuner + 5)
                        kirim(ser, f"raw2 {sudut_tuner}", 0.05)
                    elif cmd_t == "s":
                        sudut_tuner = max(0, sudut_tuner - 5)
                        kirim(ser, f"raw2 {sudut_tuner}", 0.05)
                    elif cmd_t == "e":
                        sudut_tuner = min(180, sudut_tuner + 1)
                        kirim(ser, f"raw2 {sudut_tuner}", 0.05)
                    elif cmd_t == "d":
                        sudut_tuner = max(0, sudut_tuner - 1)
                        kirim(ser, f"raw2 {sudut_tuner}", 0.05)
                    elif cmd_t == "1":
                        cur_sb = sudut_tuner
                        kirim(ser, f"s2_standby {cur_sb}", 0.1)
                        print(f"\n[DISIMPAN] Standby Servo 2 disetel ke: {cur_sb}°")
                    elif cmd_t == "2":
                        cur_bk = sudut_tuner
                        kirim(ser, f"s2_buka {cur_bk}", 0.1)
                        print(f"\n[DISIMPAN] Buka Servo 2 disetel ke: {cur_bk}°")
                    elif cmd_t == "t":
                        print(f"\n[UJI AYUN] Standby({cur_sb}°) -> Buka({cur_bk}°) -> Standby({cur_sb}°)...")
                        kirim(ser, f"raw2 {cur_sb}", 0.4)
                        time.sleep(0.3)
                        kirim(ser, f"s2 {cur_bk}", 1.0)
                        time.sleep(1.0)
                        kirim(ser, f"s2 {cur_sb}", 1.0)
                        time.sleep(0.5)
                    elif cmd_t == "x":
                        kirim(ser, f"sudut_kuning {cur_sb} {cur_bk}", 0.2)
                        print(f"\n[SELESAI] Konfigurasi aktif di ESP32: Standby={cur_sb}°, Buka={cur_bk}°\n")
                        break
                        
            elif pilih == "5":
                print("\n--- UJI SUDUT MENTAH BERTAHAP (RAW 0 - 180 DERAJAT) ---")
                for ang in [0, 20, 45, 60, 70, 85, 90, 120, 150, 175, 180]:
                    print(f" -> Servo 2 ke {ang}°...")
                    kirim(ser, f"raw2 {ang}", 0.5)
                    time.sleep(0.4)
                print(" -> Kembali ke 85° (Standby)...")
                kirim(ser, "raw2 85", 0.4)
                
            elif pilih == "6":
                print("\n--- UJI SIKLUS REALTIME TOMAT KUNING ---")
                print("Mengirim perintah: 'kuning'")
                res = kirim(ser, "kuning", 0.2)
                for r in res:
                    print(f"ESP32: {r}")
                print("Servo 2 membuka ke dalam dan MENAHAN 9.0 detik...")
                for s in range(9, 0, -1):
                    print(f"\rMenahan... sisa {s:2d} detik ", end="", flush=True)
                    time.sleep(1.0)
                print("\nServo 2 menutup kembali secara halus ke dinding standby!")
                time.sleep(1.0)
                while ser.in_waiting:
                    print("ESP32:", ser.readline().decode(errors="ignore").strip())
                    
            elif pilih == "7":
                sb = input("Masukkan sudut STANDBY baru (misal 90): ").strip()
                bk = input("Masukkan sudut BUKA baru (misal 155): ").strip()
                if sb.isdigit() and bk.isdigit():
                    kirim(ser, f"sudut_kuning {sb} {bk}", 0.2)
                    kirim(ser, f"raw2 {sb}", 0.3)
                    print(f"[BERHASIL] Sudut aktif di ESP32 diubah ke Standby={sb}°, Buka={bk}°")
                else:
                    print("[BATAL] Input harus berupa angka.")
                    
            elif pilih == "8":
                val = input("Masukkan sudut bebas (0 - 180): ").strip()
                if val.isdigit():
                    ang = int(val)
                    if 0 <= ang <= 180:
                        res = kirim(ser, f"raw2 {ang}", 0.3)
                        for r in res:
                            print(f"ESP32: {r}")
                    else:
                        print("[ERROR] Sudut harus 0 - 180.")
                        
            elif pilih == "q":
                break
                
    finally:
        ser.close()
        print("Port serial telah ditutup.")

if __name__ == "__main__":
    main()
