#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

Servo servo1;
Servo servo2;

// ============================================================
// KONFIGURASI PIN & HARDWARE
// ============================================================
const int pinServo1 = 18;     // GPIO Servo 1 (Pemilah Matang - Buang Kiri)
const int pinServo2 = 19;     // GPIO Servo 2 (Pemilah Setengah Matang - Buang Kanan)
const int pinProximity = 32;  // GPIO Sensor Proximity Konveyor (Pin 32)
const int pinRelay = 14;      // GPIO Relay (opsional: kontrol motor konveyor)

// Konfigurasi Pin I2C untuk LCD (Pin 21 SDA, Pin 22 SCL)
const int pinSDA = 21;  // GPIO 21 = SDA
const int pinSCL = 22;  // GPIO 22 = SCL

// Alamat I2C LCD 16x2 (Default 0x27, beberapa tipe modul PCF8574A menggunakan 0x3F)
#ifndef LCD_I2C_ADDR
#define LCD_I2C_ADDR 0x27
#endif

LiquidCrystal_I2C lcd(LCD_I2C_ADDR, 16, 2);

// Status & Counter untuk Tampilan LCD
bool statusSistemHidup = true;  // true = HIDUP, false = MATI
int totalTomat = 0;
int totalMatang = 0;
int totalSetengah = 0;
int totalMentah = 0;

// Siklus Status Tampilan LCD (BOOTING -> READY -> NORMAL)
enum SystemLcdState {
  LCD_BOOTING,      // Sedang booting (menunggu Raspberry Pi / Python)
  LCD_SHOW_READY,   // Menampilkan banner "SISTEM: READY!"
  LCD_NORMAL        // Tampilan operasional normal (STATUS & JML TOMAT)
};

SystemLcdState stateLcd = LCD_BOOTING;
unsigned long waktuMulaiReady = 0;
const unsigned long DURASI_BANNER_READY_MS = 2500;  // 2.5 detik tampil banner sebelum clear ke normal

// Flag keberadaan LCD & buffer timer (anti-flicker & anti-freeze)
bool lcdTerdeteksi = false;
bool perluUpdateLcd = true;
String pesanKhususLcd = "";
unsigned long waktuPesanKhusus = 0;
unsigned long waktuLcdTerakhir = 0;

// Baud rate komunikasi serial (disamakan dengan Python: 115200)
const long BAUD_RATE = 115200;


// ============================================================
// KONFIGURASI SUDUT SERVO (0 - 180 Derajat)
// ============================================================
// Servo 1 (Matang - Buang Kiri):
int SERVO1_STANDBY = 80;  // Servo 1 merapat ke dinding kiri konveyor (lurus ke depan)
int SERVO1_BUKA = 10;     // Servo 1 buang kiri (menutup jalur untuk membelokkan tomat matang)

// Servo 2 (Setengah Matang / Kuning - Buang Kanan):
// Standby lurus merapat ke dinding kanan = 90 derajat
// Buka buang kanan (ayun masuk KE DALAM jalur konveyor) = 155 derajat
int SERVO2_STANDBY = 90;   // Standby merapat ke dinding kanan konveyor (90 derajat)
int SERVO2_BUKA    = 155;  // Buka ayun MASUK KE DALAM jalur konveyor (155 derajat, buang kanan)

// ============================================================
// KONVERSI SUDUT KE PULSA MIKRODETIK (MICROSECONDS RESOLUTION)
// Resolusi tinggi: Menghilangkan loncatan integer derajat yang membuat servo analog tersendat
// ============================================================
const float SERVO_MIN_US = 544.0f;
const float SERVO_MAX_US = 2400.0f;

inline float derajatKeUs(float deg) {
  return SERVO_MIN_US + (constrain(deg, 0.0f, 180.0f) / 180.0f) * (SERVO_MAX_US - SERVO_MIN_US);
}

inline float usKeDerajat(float us) {
  return (constrain(us, SERVO_MIN_US, SERVO_MAX_US) - SERVO_MIN_US) * 180.0f / (SERVO_MAX_US - SERVO_MIN_US);
}

// ============================================================
// KONFIGURASI PROFIL GERAKAN S-CURVE & WAKTU TAHAN (HOLD TIME)
// ============================================================
// 1. Ayunan halus menggunakan rumus S-Curve (Sinusoidal Smooth Easing)
//    - Servo 1 (Matang - buang kiri 70 deg): 400ms (cepat & mulus)
//    - Servo 2 (Kuning - buang kanan 65 deg): 800ms (ayun halus kontinyu dengan mikrodetik)
unsigned long SWEEP_S1_DURATION_MS = 400;  // 0.40 detik untuk Servo 1
unsigned long SWEEP_S2_DURATION_MS = 800;  // 0.80 detik untuk Servo 2
unsigned long SWEEP_DURATION_MS    = 450;  // Fallback default

// 2. Waktu servo MENAHAN posisi buang sesuai detik yang ditentukan user:
//    - Servo Matang (Servo 1): Tahan 8.4 detik
//    - Servo Kuning (Servo 2): Tahan 9.0 detik (sampai tomat kuning tiba di penampungan)
unsigned long waktuTahanMatangMs = 8400;  // 8.4 detik (menahan posisi buang tomat matang)
unsigned long waktuTahanKuningMs = 9000;  // 9.0 detik (menahan posisi buang tomat kuning)

// Interval update sinyal servo (ms) - Sinkron persis dengan frekuensi PWM 50Hz (20ms) tanpa distorsi pulsa
const unsigned long UPDATE_TICK_MS = 20;

// Fungsi Easing S-Curve (Sinusoidal Smooth Easing: 0.5 * (1 - cos(pi * p)))
// - Memiliki akselerasi awal bertahap tanpa 'dead-zone' datar (mencegah stiction / motor tersangkut saat mulai buka)
// - Kecepatan puncak di tengah (p = 0.5) terkendali dan stabil sehingga roda gigi motor servo tidak slip / kewalahan
// - Mendarat lembut di target akhir tanpa bouncing / getaran gedek-gedek
float hitungSCurve(float p) {
  if (p <= 0.0f) return 0.0f;
  if (p >= 1.0f) return 1.0f;
  return (1.0f - cos(p * 3.14159265f)) * 0.5f;
}

// ============================================================
// STATE MACHINE PENGONTROL INDEPENDEN SETIAP SERVO
// ============================================================
enum ServoState {
  SERVO_IDLE,
  SERVO_OPENING,
  SERVO_HOLDING,
  SERVO_CLOSING
};

ServoState stateServo1 = SERVO_IDLE;
ServoState stateServo2 = SERVO_IDLE;

unsigned long s1WaktuMulaiGerak = 0;
unsigned long s1WaktuMulaiTahan = 0;
unsigned long s2WaktuMulaiGerak = 0;
unsigned long s2WaktuMulaiTahan = 0;

// Debounce timer agar perintah ganda / refleksi kamera tidak memicu ulang gerakan mid-stroke
unsigned long lastHitMatangMs = 0;
unsigned long lastHitKuningMs = 0;

unsigned long waktuUpdateTerakhir = 0;

int startAngle1 = SERVO1_STANDBY;
int startAngle2 = SERVO2_STANDBY;
int currentAngle1 = SERVO1_STANDBY;
int currentAngle2 = SERVO2_STANDBY;
int targetAngle1 = SERVO1_STANDBY;
int targetAngle2 = SERVO2_STANDBY;

float startUs1 = derajatKeUs(SERVO1_STANDBY);
float startUs2 = derajatKeUs(SERVO2_STANDBY);
float currentUs1 = derajatKeUs(SERVO1_STANDBY);
float currentUs2 = derajatKeUs(SERVO2_STANDBY);
float targetUs1 = derajatKeUs(SERVO1_STANDBY);
float targetUs2 = derajatKeUs(SERVO2_STANDBY);

// Status & Debounce Sensor Proximity IR (Pin 32)
int statusProximity = 1;
int lastStatusProximity = 1;
unsigned long lastProxDebounce = 0;

void updateProximitySensor() {
  int reading = digitalRead(pinProximity);
  if (reading != lastStatusProximity) {
    lastProxDebounce = millis();
  }
  if ((millis() - lastProxDebounce) > 25) {
    if (reading != statusProximity) {
      statusProximity = reading;
      // Sensor IR: Transisi ke LOW saat buah tomat memotong sinar IR
      if (statusProximity == LOW) {
        Serial.println("EVENT_IR_TRIGGER");
      }
    }
  }
  lastStatusProximity = reading;
}

// ============================================================
// FUNGSI GERAK S-CURVE MANUAL / TEST (MICROSECOND RESOLUTION)
// ============================================================
void gerakSCurveSatuServo(Servo &s, int &currentAngleVar, float &currentUsVar, int fromAng, int toAng, unsigned long durasiMs) {
  float fromUs = derajatKeUs(fromAng);
  float toUs = derajatKeUs(toAng);
  unsigned long t0 = millis();
  while (true) {
    unsigned long elapsed = millis() - t0;
    if (elapsed >= durasiMs) {
      currentUsVar = toUs;
      currentAngleVar = toAng;
      s.writeMicroseconds((int)round(currentUsVar));
      break;
    }
    float p = (float)elapsed / (float)durasiMs;
    float factor = hitungSCurve(p);
    currentUsVar = fromUs + (toUs - fromUs) * factor;
    currentAngleVar = (int)round(usKeDerajat(currentUsVar));
    s.writeMicroseconds((int)round(currentUsVar));
    delay(UPDATE_TICK_MS);
  }
}

// ============================================================
// FUNGSI INTERPOLASI GERAKAN S-CURVE & SIKLUS AUTO-CLOSE (NON-BLOCKING)
// ============================================================
void updateSmoothServo() {
  unsigned long sekarang = millis();

  // Kontrol interval pembaruan posisi servo (10ms)
  if (sekarang - waktuUpdateTerakhir < UPDATE_TICK_MS) {
    return;
  }
  waktuUpdateTerakhir = sekarang;

  // ------------------------------------------------------------
  // 1. STATE MACHINE SERVO 1 (PEMILAH MATANG - BUANG KIRI)
  // ------------------------------------------------------------
  switch (stateServo1) {
    case SERVO_IDLE:
      break;

    case SERVO_OPENING:
      {
        unsigned long elapsed = sekarang - s1WaktuMulaiGerak;
        if (elapsed >= SWEEP_S1_DURATION_MS) {
          currentUs1 = targetUs1;
          currentAngle1 = targetAngle1;
          servo1.writeMicroseconds((int)round(currentUs1));
          s1WaktuMulaiTahan = sekarang;
          stateServo1 = SERVO_HOLDING;
          Serial.println("ACK_SERVO1_OPENED");
        } else {
          float p = (float)elapsed / (float)SWEEP_S1_DURATION_MS;
          float factor = hitungSCurve(p);
          currentUs1 = startUs1 + (targetUs1 - startUs1) * factor;
          currentAngle1 = (int)round(usKeDerajat(currentUs1));
          servo1.writeMicroseconds((int)round(currentUs1));
        }
        break;
      }

    case SERVO_HOLDING:
      // Tahan sesuai durasi yang ditentukan (default 8.4 detik untuk matang)
      if (sekarang - s1WaktuMulaiTahan >= waktuTahanMatangMs) {
        startUs1 = currentUs1;
        startAngle1 = currentAngle1;
        targetAngle1 = SERVO1_STANDBY;  // 80 derajat
        targetUs1 = derajatKeUs(targetAngle1);
        s1WaktuMulaiGerak = sekarang;
        stateServo1 = SERVO_CLOSING;
        Serial.println("ACK_SERVO1_CLOSING");
      }
      break;

    case SERVO_CLOSING:
      {
        unsigned long elapsed = sekarang - s1WaktuMulaiGerak;
        if (elapsed >= SWEEP_S1_DURATION_MS) {
          currentUs1 = targetUs1;
          currentAngle1 = targetAngle1;
          servo1.writeMicroseconds((int)round(currentUs1));
          stateServo1 = SERVO_IDLE;
          Serial.println("ACK_SERVO1_CLOSED");
        } else {
          float p = (float)elapsed / (float)SWEEP_S1_DURATION_MS;
          float factor = hitungSCurve(p);
          currentUs1 = startUs1 + (targetUs1 - startUs1) * factor;
          currentAngle1 = (int)round(usKeDerajat(currentUs1));
          servo1.writeMicroseconds((int)round(currentUs1));
        }
        break;
      }
  }

  // ------------------------------------------------------------
  // 2. STATE MACHINE SERVO 2 (PEMILAH KUNING - BUANG KANAN)
  //    Ayunan mikrodetik kontinyu (Microsecond Resolution S-Curve)
  //    Menghilangkan getaran patah-patah pada servo analog Futaba S3003
  // ------------------------------------------------------------
  switch (stateServo2) {
    case SERVO_IDLE:
      break;

    case SERVO_OPENING:
      {
        unsigned long elapsed = sekarang - s2WaktuMulaiGerak;
        if (elapsed >= SWEEP_S2_DURATION_MS) {
          currentUs2 = targetUs2;
          currentAngle2 = targetAngle2;
          servo2.writeMicroseconds((int)round(currentUs2));
          s2WaktuMulaiTahan = sekarang;
          stateServo2 = SERVO_HOLDING;
          Serial.println("ACK_SERVO2_OPENED");
        } else {
          float p = (float)elapsed / (float)SWEEP_S2_DURATION_MS;
          float factor = hitungSCurve(p);
          currentUs2 = startUs2 + (targetUs2 - startUs2) * factor;
          currentAngle2 = (int)round(usKeDerajat(currentUs2));
          servo2.writeMicroseconds((int)round(currentUs2));
        }
        break;
      }

    case SERVO_HOLDING:
      // Tahan sesuai durasi yang ditentukan (default 9.0 detik untuk kuning)
      if (sekarang - s2WaktuMulaiTahan >= waktuTahanKuningMs) {
        startUs2 = currentUs2;
        startAngle2 = currentAngle2;
        targetAngle2 = SERVO2_STANDBY;  // Standby lurus di dinding (90 derajat)
        targetUs2 = derajatKeUs(targetAngle2);
        s2WaktuMulaiGerak = sekarang;
        stateServo2 = SERVO_CLOSING;
        Serial.println("ACK_SERVO2_CLOSING");
      }
      break;

    case SERVO_CLOSING:
      {
        unsigned long elapsed = sekarang - s2WaktuMulaiGerak;
        if (elapsed >= SWEEP_S2_DURATION_MS) {
          currentUs2 = targetUs2;
          currentAngle2 = targetAngle2;
          servo2.writeMicroseconds((int)round(currentUs2));
          stateServo2 = SERVO_IDLE;
          Serial.println("ACK_SERVO2_CLOSED");
        } else {
          float p = (float)elapsed / (float)SWEEP_S2_DURATION_MS;
          float factor = hitungSCurve(p);
          currentUs2 = startUs2 + (targetUs2 - startUs2) * factor;
          currentAngle2 = (int)round(usKeDerajat(currentUs2));
          servo2.writeMicroseconds((int)round(currentUs2));
        }
        break;
      }
  }
}

// ============================================================
// FUNGSI UPDATE DISPLAY LCD 16X2 (ANTI-FLICKER / NON-BLOCKING)
// ============================================================
void updateTampilanLcd() {
  if (!lcdTerdeteksi) return;  // Lindungi jika LCD belum terpasang agar tidak menghambat pergerakan servo

  // 1. TAHAP BOOTING: Animasi titik berjalan sampai Raspberry Pi siap terhubung
  if (stateLcd == LCD_BOOTING) {
    static unsigned long lastAnimBoot = 0;
    static int dotIndex = 0;
    if (millis() - lastAnimBoot >= 450) {
      lastAnimBoot = millis();
      dotIndex = (dotIndex + 1) % 4;  // 0, 1, 2, 3
      char baris1[17];
      if (dotIndex == 0) snprintf(baris1, sizeof(baris1), "SISTEM BOOTING  ");
      else if (dotIndex == 1) snprintf(baris1, sizeof(baris1), "SISTEM BOOTING. ");
      else if (dotIndex == 2) snprintf(baris1, sizeof(baris1), "SISTEM BOOTING..");
      else snprintf(baris1, sizeof(baris1), "SISTEM BOOTING...");

      lcd.setCursor(0, 0);
      lcd.print(baris1);
      lcd.setCursor(0, 1);
      lcd.print("MOHON TUNGGU... ");
    }
    return;
  }

  // 2. TAHAP BANNER READY: Tampilkan pesan "SISTEM: READY!" selama 2.5 detik
  if (stateLcd == LCD_SHOW_READY) {
    if (millis() - waktuMulaiReady >= DURASI_BANNER_READY_MS) {
      // Waktu 2.5 detik selesai -> Bersihkan layar (clear) dan beralih ke mode operasional biasa!
      stateLcd = LCD_NORMAL;
      lcd.clear();
      perluUpdateLcd = true;
    } else {
      return;  // Pertahankan tulisan READY di layar sampai durasi selesai
    }
  }

  // 3. TAHAP OPERASIONAL NORMAL
  // Throttle pembaruan LCD: maksimal sekali tiap 250ms agar bus I2C tidak membebani servo
  if (millis() - waktuLcdTerakhir < 250) return;
  waktuLcdTerakhir = millis();

  char baris1[17];
  char baris2[17];

  // Baris 1: Status Sistem (HIDUP / MATI atau Notifikasi Sortir Sementara)
  if (pesanKhususLcd.length() > 0 && (millis() - waktuPesanKhusus < 1500)) {
    snprintf(baris1, sizeof(baris1), "%-16s", pesanKhususLcd.c_str());
  } else {
    pesanKhususLcd = "";
    if (statusSistemHidup) {
      snprintf(baris1, sizeof(baris1), "STATUS: HIDUP   ");
    } else {
      snprintf(baris1, sizeof(baris1), "STATUS: MATI    ");
    }
  }

  // Baris 2: Jumlah Tomat
  snprintf(baris2, sizeof(baris2), "JML TOMAT: %-5d", totalTomat);

  lcd.setCursor(0, 0);
  lcd.print(baris1);
  lcd.setCursor(0, 1);
  lcd.print(baris2);
}


// ============================================================
// EKSEKUSI PERINTAH KLASIFIKASI DENGAN DELAY TRANSIT KONVEYOR
// ============================================================
void eksekusiAksi(String cmd) {
  cmd.toLowerCase();
  unsigned long sekarang = millis();

  // 1. MATANG (Kelas '0') -> Buka cepat S-Curve (10 deg) -> Tahan 8.4s -> Tutup halus S-Curve (80 deg)
  if (cmd == "matang" || cmd == "0" || cmd == "merah") {
    pesanKhususLcd = "SORTIR: MATANG";
    waktuPesanKhusus = sekarang;

    // Debounce counter: Hanya hitung 1x per tomat (abaikan spam paket dalam 3 detik)
    if (sekarang - lastHitMatangMs > 3000) {
      totalTomat++;
      totalMatang++;
      lastHitMatangMs = sekarang;
      perluUpdateLcd = true;
    }

    // GUARD PERGERAKAN: Cegah gerakan patah-patah jika ada perintah berulang
    if (stateServo1 == SERVO_OPENING) {
      // Jika sudah sedang berayun membuka, JANGAN reset s1WaktuMulaiGerak (agar kecepatan tidak drop ke 0)!
      // Cukup perbarui timer tahan agar servo tetap menahan 8.4 detik setelah sampai
      s1WaktuMulaiTahan = sekarang;
      Serial.println("ACK_MATANG_EXTEND_HOLD");
    } else if (stateServo1 == SERVO_HOLDING) {
      // Jika sudah membuka penuh dan sedang menahan, cukup perpanjang waktu tahan
      s1WaktuMulaiTahan = sekarang;
      Serial.println("ACK_MATANG_EXTEND_HOLD");
    } else {
      // Sedang IDLE atau sedang CLOSING -> mulai buka secara halus dari sudut saat ini
      startUs1 = currentUs1;
      startAngle1 = currentAngle1;
      targetAngle1 = SERVO1_BUKA;  // 10 derajat
      targetUs1 = derajatKeUs(targetAngle1);
      s1WaktuMulaiGerak = sekarang;
      s1WaktuMulaiTahan = sekarang;
      stateServo1 = SERVO_OPENING;

      Serial.print("ACK_MATANG_OPENING_HOLD_");
      Serial.print(waktuTahanMatangMs);
      Serial.println("MS");
    }
  }
  // 2. SETENGAH MATANG / KUNING (Kelas '2') -> Buka cepat S-Curve (155 deg) -> Tahan 9.0s -> Tutup halus S-Curve (90 deg)
  else if (cmd == "kuning" || cmd == "setengah" || cmd == "setengah_matang" || cmd == "2") {
    pesanKhususLcd = "SORTIR: KUNING";
    waktuPesanKhusus = sekarang;

    // Debounce counter: Hanya hitung 1x per tomat (abaikan spam paket dalam 3 detik)
    if (sekarang - lastHitKuningMs > 3000) {
      totalTomat++;
      totalSetengah++;
      lastHitKuningMs = sekarang;
      perluUpdateLcd = true;
    }

    // GUARD PERGERAKAN: Cegah gerakan patah-patah/tersendat jika ada perintah berulang
    if (stateServo2 == SERVO_OPENING) {
      // Jika sudah sedang berayun membuka, JANGAN reset s2WaktuMulaiGerak (agar kecepatan tidak drop ke 0)!
      // Cukup perbarui timer tahan agar servo tetap menahan 9.0 detik setelah sampai
      s2WaktuMulaiTahan = sekarang;
      Serial.println("ACK_KUNING_EXTEND_HOLD");
    } else if (stateServo2 == SERVO_HOLDING) {
      // Jika sudah membuka penuh dan sedang menahan, cukup perpanjang waktu tahan
      s2WaktuMulaiTahan = sekarang;
      Serial.println("ACK_KUNING_EXTEND_HOLD");
    } else {
      // Sedang IDLE atau sedang CLOSING -> mulai buka secara halus dari sudut saat ini
      startUs2 = currentUs2;
      startAngle2 = currentAngle2;
      targetAngle2 = SERVO2_BUKA;  // 155 derajat
      targetUs2 = derajatKeUs(targetAngle2);
      s2WaktuMulaiGerak = sekarang;
      s2WaktuMulaiTahan = sekarang;
      stateServo2 = SERVO_OPENING;

      Serial.print("ACK_KUNING_OPENING_HOLD_");
      Serial.print(waktuTahanKuningMs);
      Serial.println("MS");
    }
  }
  // 3. MENTAH (Kelas '1') -> Kedua Servo Tetap Standby (Lolos Lurus)
  else if (cmd == "mentah" || cmd == "1" || cmd == "hijau") {
    if (sekarang - lastHitMatangMs > 2000 && sekarang - lastHitKuningMs > 2000) {
      totalTomat++;
      totalMentah++;
      perluUpdateLcd = true;
    }
    pesanKhususLcd = "SORTIR: MENTAH";
    waktuPesanKhusus = sekarang;

    Serial.println("ACK_MENTAH_PASSTHROUGH");
  }
  // 4. RESET / STANDBY MANUAL
  else if (cmd == "standby" || cmd == "reset" || cmd == "3") {
    stateServo1 = SERVO_IDLE;
    stateServo2 = SERVO_IDLE;
    targetAngle1 = SERVO1_STANDBY;
    targetAngle2 = SERVO2_STANDBY;
    currentAngle1 = SERVO1_STANDBY;
    currentAngle2 = SERVO2_STANDBY;
    startAngle1 = SERVO1_STANDBY;
    startAngle2 = SERVO2_STANDBY;
    currentUs1 = derajatKeUs(SERVO1_STANDBY);
    currentUs2 = derajatKeUs(SERVO2_STANDBY);
    targetUs1 = currentUs1;
    targetUs2 = currentUs2;
    startUs1 = currentUs1;
    startUs2 = currentUs2;
    servo1.writeMicroseconds((int)round(currentUs1));
    servo2.writeMicroseconds((int)round(currentUs2));
    pesanKhususLcd = "SERVO: STANDBY";
    waktuPesanKhusus = sekarang;
    perluUpdateLcd = true;
    Serial.println("ACK_STANDBY");
  }
  // 5. STATUS SISTEM: HIDUP
  else if (cmd == "hidup" || cmd == "on" || cmd == "start") {
    statusSistemHidup = true;
    digitalWrite(pinRelay, HIGH);
    perluUpdateLcd = true;
    Serial.println("ACK_STATUS_HIDUP");
  }
  // 6. STATUS SISTEM: MATI
  else if (cmd == "mati" || cmd == "off" || cmd == "stop") {
    statusSistemHidup = false;
    digitalWrite(pinRelay, LOW);
    perluUpdateLcd = true;
    Serial.println("ACK_STATUS_MATI");
  }
  // 7. RESET JUMLAH TOMAT
  else if (cmd == "reset_tomat" || cmd == "reset_count" || cmd == "clear") {
    totalTomat = 0;
    totalMatang = 0;
    totalSetengah = 0;
    totalMentah = 0;
    pesanKhususLcd = "RESET COUNTER OK";
    waktuPesanKhusus = sekarang;
    perluUpdateLcd = true;
    Serial.println("ACK_RESET_TOMAT_OK");
  }
}

// ============================================================
// HANDLER KOMUNIKASI SERIAL (100% NON-BLOCKING TANPA DELAY)
// ============================================================
String serialBuffer = "";

void prosesSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        String data = serialBuffer;
        serialBuffer = "";

        // 1. Handshake & Sinyal Status Ready / Booting dari Raspberry Pi
        if (data == "ready" || data == "system_ready") {
          statusSistemHidup = true;
          digitalWrite(pinRelay, HIGH);
          stateLcd = LCD_SHOW_READY;
          waktuMulaiReady = millis();
          if (lcdTerdeteksi) {
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print(" SISTEM: READY! ");
            lcd.setCursor(0, 1);
            lcd.print(" SIAP MEMILAH :)");
          }
          Serial.println("ACK_READY_OK");
        }
        else if (data == "go") {
          statusSistemHidup = true;
          digitalWrite(pinRelay, HIGH);
          // Jika masih dalam tahap booting dan menerima handshake 'go', aktifkan banner ready
          if (stateLcd == LCD_BOOTING) {
            stateLcd = LCD_SHOW_READY;
            waktuMulaiReady = millis();
            if (lcdTerdeteksi) {
              lcd.clear();
              lcd.setCursor(0, 0);
              lcd.print(" SISTEM: READY! ");
              lcd.setCursor(0, 1);
              lcd.print(" SIAP MEMILAH :)");
            }
          }
          perluUpdateLcd = true;
          Serial.println("ok");
        }
        else if (data == "booting") {
          stateLcd = LCD_BOOTING;
          if (lcdTerdeteksi) {
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("SISTEM: BOOTING ");
            lcd.setCursor(0, 1);
            lcd.print("MOHON TUNGGU... ");
          }
          Serial.println("ACK_BOOTING");
        }
        // 2. Pembacaan sensor proximity konveyor
        else if (data == "se") {

          statusProximity = digitalRead(pinProximity);
          Serial.println(statusProximity);
        }
        // 3. Perintah pemilah tomat & kontrol status
        else if (data == "matang" || data == "0" || data == "merah" || data == "kuning" || data == "setengah" || data == "setengah_matang" || data == "2" || data == "mentah" || data == "1" || data == "hijau" || data == "standby" || data == "reset" || data == "3" || data == "hidup" || data == "mati" || data == "on" || data == "off" || data == "start" || data == "stop" || data == "reset_tomat" || data == "reset_count" || data == "clear") {
          eksekusiAksi(data);
        }
        // 4. Set jumlah tomat manual / sinkronisasi dari serial (bisa: "set_tomat 25" atau "set_tomat 25 10 8 7")
        else if (data.startsWith("set_tomat ") || data.startsWith("count:") || data.startsWith("sync_tomat ")) {
          int idx = data.indexOf(' ');
          if (idx < 0) idx = data.indexOf(':');
          if (idx >= 0) {
            String sisa = data.substring(idx + 1);
            sisa.trim();
            int sp1 = sisa.indexOf(' ');
            if (sp1 > 0) {
              totalTomat = sisa.substring(0, sp1).toInt();
              String s2 = sisa.substring(sp1 + 1);
              s2.trim();
              int sp2 = s2.indexOf(' ');
              if (sp2 > 0) {
                totalMatang = s2.substring(0, sp2).toInt();
                String s3 = s2.substring(sp2 + 1);
                s3.trim();
                int sp3 = s3.indexOf(' ');
                if (sp3 > 0) {
                  totalSetengah = s3.substring(0, sp3).toInt();
                  totalMentah = s3.substring(sp3 + 1).toInt();
                } else {
                  totalSetengah = s3.toInt();
                }
              } else {
                totalMatang = s2.toInt();
              }
            } else {
              totalTomat = sisa.toInt();
            }
            perluUpdateLcd = true;
            Serial.print("ACK_SET_TOMAT: ");
            Serial.println(totalTomat);
          }
        }
        // 5. Query status sistem & counter
        else if (data == "status") {
          Serial.print("STATUS:");
          Serial.print(statusSistemHidup ? "HIDUP" : "MATI");
          Serial.print(",TOMAT:");
          Serial.println(totalTomat);
        }
        // 6. Perintah manual uji sudut dengan profil S-Curve halus (Microseconds Resolution)
        else if (data.startsWith("s1 ")) {
          int ang = constrain(data.substring(3).toInt(), 0, 180);
          gerakSCurveSatuServo(servo1, currentAngle1, currentUs1, currentAngle1, ang, SWEEP_S1_DURATION_MS);
          targetAngle1 = currentAngle1;
          startAngle1 = currentAngle1;
          targetUs1 = currentUs1;
          startUs1 = currentUs1;
          stateServo1 = SERVO_IDLE;
          Serial.print("ACK_SET_SERVO1: ");
          Serial.println(currentAngle1);
        } else if (data.startsWith("s2 ")) {
          int ang = constrain(data.substring(3).toInt(), 0, 180);
          gerakSCurveSatuServo(servo2, currentAngle2, currentUs2, currentAngle2, ang, SWEEP_S2_DURATION_MS);
          targetAngle2 = currentAngle2;
          startAngle2 = currentAngle2;
          targetUs2 = currentUs2;
          startUs2 = currentUs2;
          stateServo2 = SERVO_IDLE;
          Serial.print("ACK_SET_SERVO2: ");
          Serial.println(currentAngle2);
        }
        // Perintah Direct Write (Raw tanpa S-Curve)
        else if (data.startsWith("raw1 ")) {
          int ang = constrain(data.substring(5).toInt(), 0, 180);
          currentAngle1 = ang;
          targetAngle1 = ang;
          startAngle1 = ang;
          currentUs1 = derajatKeUs(ang);
          targetUs1 = currentUs1;
          startUs1 = currentUs1;
          servo1.writeMicroseconds((int)round(currentUs1));
          stateServo1 = SERVO_IDLE;
          Serial.print("ACK_RAW_SERVO1: ");
          Serial.println(currentAngle1);
        } else if (data.startsWith("raw2 ")) {
          int ang = constrain(data.substring(5).toInt(), 0, 180);
          currentAngle2 = ang;
          targetAngle2 = ang;
          startAngle2 = ang;
          currentUs2 = derajatKeUs(ang);
          targetUs2 = currentUs2;
          startUs2 = currentUs2;
          servo2.writeMicroseconds((int)round(currentUs2));
          stateServo2 = SERVO_IDLE;
          Serial.print("ACK_RAW_SERVO2: ");
          Serial.println(currentAngle2);
        }
        // Pengaturan Durasi Ayunan S-Curve Dinamis
        else if (data.startsWith("durasi2 ") || data.startsWith("speed2 ")) {
          int idx = data.indexOf(' ');
          int d = data.substring(idx + 1).toInt();
          if (d >= 200 && d <= 4000) {
            SWEEP_S2_DURATION_MS = d;
            Serial.print("ACK_SET_DURASI2: ");
            Serial.println(SWEEP_S2_DURATION_MS);
          }
        } else if (data.startsWith("durasi1 ") || data.startsWith("speed1 ")) {
          int idx = data.indexOf(' ');
          int d = data.substring(idx + 1).toInt();
          if (d >= 100 && d <= 3000) {
            SWEEP_S1_DURATION_MS = d;
            Serial.print("ACK_SET_DURASI1: ");
            Serial.println(SWEEP_S1_DURATION_MS);
          }
        } else if (data.startsWith("durasi ") || data.startsWith("speed ")) {
          int idx = data.indexOf(' ');
          int d = data.substring(idx + 1).toInt();
          if (d >= 100 && d <= 3000) {
            SWEEP_S1_DURATION_MS = d;
            SWEEP_S2_DURATION_MS = (unsigned long)(d * 1.6f);
            SWEEP_DURATION_MS = d;
            Serial.print("ACK_SET_DURASI: S1=");
            Serial.print(SWEEP_S1_DURATION_MS);
            Serial.print("MS, S2=");
            Serial.print(SWEEP_S2_DURATION_MS);
            Serial.println("MS");
          }
        }
        // 7. Pengaturan Sudut Servo 2 Kuning secara Dinamis (bisa disetel langsung dari Serial)
        //    Format: "sudut_kuning <standby> <buka>" atau "s2_buka <sudut>" atau "s2_standby <sudut>"
        else if (data.startsWith("sudut_kuning ") || data.startsWith("sudut_s2 ")) {
          int idx = data.indexOf(' ');
          String s = data.substring(idx + 1);
          s.trim();
          int sp = s.indexOf(' ');
          if (sp > 0) {
            SERVO2_STANDBY = s.substring(0, sp).toInt();
            SERVO2_BUKA = s.substring(sp + 1).toInt();
          } else {
            SERVO2_BUKA = s.toInt();
          }
          Serial.print("ACK_SET_SUDUT_KUNING: STANDBY=");
          Serial.print(SERVO2_STANDBY);
          Serial.print(", BUKA=");
          Serial.println(SERVO2_BUKA);
        } else if (data.startsWith("s2_buka ")) {
          SERVO2_BUKA = data.substring(8).toInt();
          Serial.print("ACK_SET_S2_BUKA: ");
          Serial.println(SERVO2_BUKA);
        } else if (data.startsWith("s2_standby ")) {
          SERVO2_STANDBY = data.substring(11).toInt();
          Serial.print("ACK_SET_S2_STANDBY: ");
          Serial.println(SERVO2_STANDBY);
        }
        // 8. Konfigurasi Waktu Tahan Servo Dinamis (opsional via serial)
        //    Format: "tahan 8400 10200" atau "delay 8400 10200"
        else if (data.startsWith("tahan ") || data.startsWith("delay ")) {
          int idx = data.indexOf(' ');
          String s = data.substring(idx + 1);
          s.trim();
          int sp = s.indexOf(' ');
          if (sp > 0) {
            waktuTahanMatangMs = s.substring(0, sp).toInt();
            waktuTahanKuningMs = s.substring(sp + 1).toInt();
          } else {
            waktuTahanMatangMs = s.toInt();
          }
          Serial.print("ACK_SET_TAHAN: MATANG=");
          Serial.print(waktuTahanMatangMs);
          Serial.print("MS, KUNING=");
          Serial.print(waktuTahanKuningMs);
          Serial.println("MS");
        } else if (data.startsWith("tahan_matang ") || data.startsWith("delay_matang ")) {
          int idx = data.indexOf(' ');
          waktuTahanMatangMs = data.substring(idx + 1).toInt();
          Serial.print("ACK_SET_TAHAN_MATANG: ");
          Serial.println(waktuTahanMatangMs);
        } else if (data.startsWith("tahan_kuning ") || data.startsWith("delay_kuning ")) {
          int idx = data.indexOf(' ');
          waktuTahanKuningMs = data.substring(idx + 1).toInt();
          Serial.print("ACK_SET_TAHAN_KUNING: ");
          Serial.println(waktuTahanKuningMs);
        }
        // 8. Tes gerakan berurutan kedua servo dengan profil S-Curve (buka cepat -> tahan 0.8s -> tutup halus)
        else if (data == "test") {
          Serial.println("ACK_TEST_START");
          gerakSCurveSatuServo(servo1, currentAngle1, currentUs1, SERVO1_STANDBY, SERVO1_BUKA, SWEEP_S1_DURATION_MS);
          delay(800);
          gerakSCurveSatuServo(servo1, currentAngle1, currentUs1, SERVO1_BUKA, SERVO1_STANDBY, SWEEP_S1_DURATION_MS);
          delay(300);

          gerakSCurveSatuServo(servo2, currentAngle2, currentUs2, SERVO2_STANDBY, SERVO2_BUKA, SWEEP_S2_DURATION_MS);
          delay(800);
          gerakSCurveSatuServo(servo2, currentAngle2, currentUs2, SERVO2_BUKA, SERVO2_STANDBY, SWEEP_S2_DURATION_MS);

          currentAngle1 = SERVO1_STANDBY;
          targetAngle1 = SERVO1_STANDBY;
          startAngle1 = SERVO1_STANDBY;
          currentAngle2 = SERVO2_STANDBY;
          targetAngle2 = SERVO2_STANDBY;
          startAngle2 = SERVO2_STANDBY;
          currentUs1 = derajatKeUs(SERVO1_STANDBY);
          targetUs1 = currentUs1;
          startUs1 = currentUs1;
          currentUs2 = derajatKeUs(SERVO2_STANDBY);
          targetUs2 = currentUs2;
          startUs2 = currentUs2;
          stateServo1 = SERVO_IDLE;
          stateServo2 = SERVO_IDLE;
          Serial.println("ACK_TEST_DONE");
        } else {
          Serial.print("ERR_UNKNOWN_CMD: ");
          Serial.println(data);
        }
      }
    } else {
      if (serialBuffer.length() < 64) {
        serialBuffer += c;
      }
    }
  }
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  // Nonaktifkan brownout detector agar ESP32 tidak restart saat beban arus puncak servo/LCD
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(BAUD_RATE);

  pinMode(pinProximity, INPUT_PULLUP);
  pinMode(pinRelay, OUTPUT);
  digitalWrite(pinRelay, LOW);

  pinMode(pinServo1, OUTPUT);
  pinMode(pinServo2, OUTPUT);

  // Alokasikan semua timer PWM hardware ESP32 (0-3)
  // Ini SANGAT KRUSIAL di ESP32Servo agar Servo 1 dan Servo 2 masing-masing
  // mendapatkan hardware timer independen dan tidak berebut clock / phase jitter
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  servo1.setPeriodHertz(50);  // Frekuensi standar servo 50Hz
  servo2.setPeriodHertz(50);

  // Inisialisasi pin servo dengan rentang pulsa standar Arduino (544 - 2400us)
  servo1.attach(pinServo1, 544, 2400);
  servo2.attach(pinServo2, 544, 2400);

  // Set posisi awal standby (Servo 1 = 80 deg, Servo 2 = 90 deg)
  currentAngle1 = SERVO1_STANDBY;
  currentAngle2 = SERVO2_STANDBY;
  targetAngle1 = SERVO1_STANDBY;
  targetAngle2 = SERVO2_STANDBY;
  startAngle1 = SERVO1_STANDBY;
  startAngle2 = SERVO2_STANDBY;
  currentUs1 = derajatKeUs(SERVO1_STANDBY);
  currentUs2 = derajatKeUs(SERVO2_STANDBY);
  targetUs1 = currentUs1;
  targetUs2 = currentUs2;
  startUs1 = currentUs1;
  startUs2 = currentUs2;
  servo1.writeMicroseconds((int)round(currentUs1));
  servo2.writeMicroseconds((int)round(currentUs2));

  // Inisialisasi I2C LCD dengan Fast Mode 400kHz & Timeout aman
  Wire.begin(pinSDA, pinSCL);
  Wire.setClock(400000);
  Wire.setTimeOut(30);

  // Deteksi kehadiran modul I2C LCD (coba 0x27, lalu fallback 0x3F)
  byte alamatLcd = LCD_I2C_ADDR;
  Wire.beginTransmission(alamatLcd);
  if (Wire.endTransmission() == 0) {
    lcdTerdeteksi = true;
  } else {
    Wire.beginTransmission(0x3F);
    if (Wire.endTransmission() == 0) {
      alamatLcd = 0x3F;
      lcd = LiquidCrystal_I2C(alamatLcd, 16, 2);
      lcdTerdeteksi = true;
    }
  }

  if (lcdTerdeteksi) {
    lcd.init();
    lcd.backlight();
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("SISTEM BOOTING..");
    lcd.setCursor(0, 1);
    lcd.print("MOHON TUNGGU... ");
    stateLcd = LCD_BOOTING;
  }

  // Uji gerak halus singkat saat boot (sangat halus dengan resolusi microsecond)
  delay(100);
  gerakSCurveSatuServo(servo1, currentAngle1, currentUs1, SERVO1_STANDBY, 70, 200);
  gerakSCurveSatuServo(servo1, currentAngle1, currentUs1, 70, SERVO1_STANDBY, 200);
  gerakSCurveSatuServo(servo2, currentAngle2, currentUs2, SERVO2_STANDBY, 105, 300);
  gerakSCurveSatuServo(servo2, currentAngle2, currentUs2, 105, SERVO2_STANDBY, 300);

  Serial.println("ESP32_READY");
}

// ============================================================
// LOOP UTAMA
// ============================================================
void loop() {
  // 1. Perbarui gerakan servo & timer auto-close (prioritas utama)
  updateSmoothServo();

  // 2. Pantau transisi sensor infrared proximity (Pin 32)
  updateProximitySensor();

  // 3. Baca perintah serial secara 100% non-blocking (instan tanpa timeout delay)
  prosesSerial();

  // 4. Perbarui LCD HANYA saat servo TIDAK sedang berayun fisik aktif
  //    agar ayunan servo 100% mulus tanpa terinterupsi transaksi I2C
  bool servoSedangBergerak = (stateServo1 == SERVO_OPENING || stateServo1 == SERVO_CLOSING || stateServo2 == SERVO_OPENING || stateServo2 == SERVO_CLOSING);

  if (!servoSedangBergerak) {
    if (stateLcd != LCD_NORMAL || perluUpdateLcd || (pesanKhususLcd.length() > 0 && millis() - waktuPesanKhusus >= 1500)) {
      updateTampilanLcd();
      perluUpdateLcd = false;
    }
  }


  // Beri kesempatan FreeRTOS scheduler agar watchdog tidak terpicu
  yield();
}