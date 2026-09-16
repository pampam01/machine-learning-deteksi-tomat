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
const int pinServo1    = 18;  // GPIO Servo 1 (Pemilah Matang - Buang Kiri)
const int pinServo2    = 19;  // GPIO Servo 2 (Pemilah Setengah Matang - Buang Kanan)
const int pinProximity = 32;  // GPIO Sensor Proximity Konveyor (Pin 32)
const int pinRelay     = 14;  // GPIO Relay (opsional: kontrol motor konveyor)

// Konfigurasi Pin I2C untuk LCD (Pin 21 SDA, Pin 22 SCL)
const int pinSDA       = 21;  // GPIO 21 = SDA
const int pinSCL       = 22;  // GPIO 22 = SCL

// Alamat I2C LCD 16x2 (Default 0x27, beberapa tipe modul PCF8574A menggunakan 0x3F)
#ifndef LCD_I2C_ADDR
#define LCD_I2C_ADDR 0x27
#endif

LiquidCrystal_I2C lcd(LCD_I2C_ADDR, 16, 2);

// Status & Counter untuk Tampilan LCD
bool statusSistemHidup = true;  // true = HIDUP, false = MATI
int totalTomat         = 0;
int totalMatang        = 0;
int totalSetengah      = 0;
int totalMentah        = 0;

// Flag keberadaan LCD & buffer timer (anti-flicker & anti-freeze)
bool lcdTerdeteksi     = false;
bool perluUpdateLcd    = true;
String pesanKhususLcd  = "";
unsigned long waktuPesanKhusus = 0;
unsigned long waktuLcdTerakhir = 0;

// Baud rate komunikasi serial (disamakan dengan Python: 115200)
const long BAUD_RATE = 115200;

// ============================================================
// KONFIGURASI SUDUT SERVO (0 - 180 Derajat)
// ============================================================
// Posisi Standby / Terbuka lurus (kedua lengan sejajar dinding konveyor menghadap ke depan)
// Catatan: Gunakan 10 derajat (bukan 0 mentok) agar servo 2 tidak menabrak batas mekanik (penyebab macet/brownout reset)
const int SERVO1_STANDBY = 90;  // Servo 1 merapat ke dinding kiri (lurus ke depan)
const int SERVO2_STANDBY = 10;  // Servo 2 merapat ke dinding kanan (lurus ke depan, aman tanpa stall)

// Posisi Buang (menutup jalur tengah untuk membelokkan tomat ke wadah)
const int SERVO1_BUKA    = 10;  // Servo 1 buang kiri (bergerak ke tengah)
const int SERVO2_BUKA    = 90;  // Servo 2 buang kanan (bergerak ke tengah)

// ============================================================
// KONFIGURASI PROFIL GERAKAN S-CURVE (TORSI PROFESIONAL)
// ============================================================
// Durasi ayunan servo dari satu posisi ke posisi lain (ms):
// Profil S-Curve: Awal lambat (torsi halus) -> Tengah kencang -> Akhir lambat (deselerasi lembut)
const unsigned long SWEEP_DURATION_MS = 400; // 0.40 detik (gerakan anggun, cepat, & tanpa getaran)

// Waktu servo menahan posisi buang sebelum menutup otomatis (Auto-Close)
const unsigned long WAKTU_TAHAN_MS    = 800; // 0.8 detik

// Interval update sinyal servo (ms) - Sinkron dengan frekuensi PWM 50Hz tanpa getaran
const unsigned long UPDATE_TICK_MS    = 10;

// Fungsi Easing S-Curve (Quintic Smootherstep: 6p^5 - 15p^4 + 10p^3)
// - Kecepatan awal = 0, akselerasi awal = 0 (torsi awal dibangun bertahap tanpa hentakan roda gigi)
// - Kecepatan puncak di tengah (p = 0.5)
// - Kecepatan akhir = 0, akselerasi akhir = 0 (mendarat lembut tanpa bouncing / getaran gedek-gedek)
float hitungSCurve(float p) {
  if (p <= 0.0f) return 0.0f;
  if (p >= 1.0f) return 1.0f;
  return p * p * p * (p * (p * 6.0f - 15.0f) + 10.0f);
}

// ============================================================
// STATE MACHINE PENGONTROL GERAKAN
// ============================================================
enum SorterState {
  STATE_IDLE,
  STATE_SERVO1_OPENING,
  STATE_SERVO1_HOLDING,
  STATE_SERVO1_CLOSING,
  STATE_SERVO2_OPENING,
  STATE_SERVO2_HOLDING,
  STATE_SERVO2_CLOSING
};

SorterState stateSorter = STATE_IDLE;
unsigned long waktuMulaiAksi      = 0;
unsigned long waktuMulaiGerak     = 0;
unsigned long waktuMulaiTahan     = 0;
unsigned long waktuUpdateTerakhir = 0;

int startAngle1   = SERVO1_STANDBY;
int startAngle2   = SERVO2_STANDBY;
int currentAngle1 = SERVO1_STANDBY;
int currentAngle2 = SERVO2_STANDBY;
int targetAngle1  = SERVO1_STANDBY;
int targetAngle2  = SERVO2_STANDBY;

// Status & Debounce Sensor Proximity IR (Pin 32)
int statusProximity     = 1;
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
// FUNGSI GERAK S-CURVE MANUAL / TEST (BLOCKING AMAN UNTUK TEST)
// ============================================================
void gerakSCurveSatuServo(Servo &s, int &currentAngleVar, int fromAng, int toAng, unsigned long durasiMs) {
  unsigned long t0 = millis();
  while (true) {
    unsigned long elapsed = millis() - t0;
    if (elapsed >= durasiMs) {
      currentAngleVar = toAng;
      s.write(currentAngleVar);
      break;
    }
    float p = (float)elapsed / (float)durasiMs;
    float factor = hitungSCurve(p);
    int ang = (int)round(fromAng + (toAng - fromAng) * factor);
    if (ang != currentAngleVar) {
      currentAngleVar = ang;
      s.write(currentAngleVar);
    }
    delay(UPDATE_TICK_MS);
  }
}

// ============================================================
// FUNGSI INTERPOLASI GERAKAN S-CURVE & SIKLUS AUTO-CLOSE (NON-BLOCKING)
// ============================================================
void updateSmoothServo() {
  unsigned long sekarang = millis();

  // Watchdog Pengaman: Jika gerakan memilah berjalan lebih dari 2.5 detik,
  // paksa reset ke STATE_IDLE agar servo tidak pernah macet
  if (stateSorter != STATE_IDLE && (sekarang - waktuMulaiAksi >= 2500)) {
    targetAngle1  = SERVO1_STANDBY;
    targetAngle2  = SERVO2_STANDBY;
    currentAngle1 = SERVO1_STANDBY;
    currentAngle2 = SERVO2_STANDBY;
    servo1.write(SERVO1_STANDBY);
    servo2.write(SERVO2_STANDBY);
    stateSorter   = STATE_IDLE;
    Serial.println("WARN_WATCHDOG_RESET_IDLE");
    return;
  }

  // Kontrol interval pembaruan posisi servo
  if (sekarang - waktuUpdateTerakhir < UPDATE_TICK_MS) {
    return;
  }
  waktuUpdateTerakhir = sekarang;

  switch (stateSorter) {
    case STATE_IDLE:
      break;

    // --- SIKLUS SERVO 1 (MATANG - BUANG KIRI) ---
    case STATE_SERVO1_OPENING: {
      unsigned long elapsed = sekarang - waktuMulaiGerak;
      if (elapsed >= SWEEP_DURATION_MS) {
        currentAngle1 = targetAngle1;
        servo1.write(currentAngle1);
        waktuMulaiTahan = sekarang;
        stateSorter = STATE_SERVO1_HOLDING;
        Serial.println("ACK_SERVO1_OPENED");
      } else {
        float p = (float)elapsed / (float)SWEEP_DURATION_MS;
        float factor = hitungSCurve(p);
        int nextAngle = (int)round(startAngle1 + (targetAngle1 - startAngle1) * factor);
        if (nextAngle != currentAngle1) {
          currentAngle1 = nextAngle;
          servo1.write(currentAngle1);
        }
      }
      break;
    }

    case STATE_SERVO1_HOLDING:
      if (sekarang - waktuMulaiTahan >= WAKTU_TAHAN_MS) {
        startAngle1     = currentAngle1;
        targetAngle1    = SERVO1_STANDBY;
        waktuMulaiGerak = sekarang;
        stateSorter     = STATE_SERVO1_CLOSING;
      }
      break;

    case STATE_SERVO1_CLOSING: {
      unsigned long elapsed = sekarang - waktuMulaiGerak;
      if (elapsed >= SWEEP_DURATION_MS) {
        currentAngle1 = targetAngle1;
        servo1.write(currentAngle1);
        stateSorter   = STATE_IDLE;
        Serial.println("ACK_SERVO1_CLOSED");
      } else {
        float p = (float)elapsed / (float)SWEEP_DURATION_MS;
        float factor = hitungSCurve(p);
        int nextAngle = (int)round(startAngle1 + (targetAngle1 - startAngle1) * factor);
        if (nextAngle != currentAngle1) {
          currentAngle1 = nextAngle;
          servo1.write(currentAngle1);
        }
      }
      break;
    }

    // --- SIKLUS SERVO 2 (SETENGAH MATANG - BUANG KANAN) ---
    case STATE_SERVO2_OPENING: {
      unsigned long elapsed = sekarang - waktuMulaiGerak;
      if (elapsed >= SWEEP_DURATION_MS) {
        currentAngle2 = targetAngle2;
        servo2.write(currentAngle2);
        waktuMulaiTahan = sekarang;
        stateSorter = STATE_SERVO2_HOLDING;
        Serial.println("ACK_SERVO2_OPENED");
      } else {
        float p = (float)elapsed / (float)SWEEP_DURATION_MS;
        float factor = hitungSCurve(p);
        int nextAngle = (int)round(startAngle2 + (targetAngle2 - startAngle2) * factor);
        if (nextAngle != currentAngle2) {
          currentAngle2 = nextAngle;
          servo2.write(currentAngle2);
        }
      }
      break;
    }

    case STATE_SERVO2_HOLDING:
      if (sekarang - waktuMulaiTahan >= WAKTU_TAHAN_MS) {
        startAngle2     = currentAngle2;
        targetAngle2    = SERVO2_STANDBY;
        waktuMulaiGerak = sekarang;
        stateSorter     = STATE_SERVO2_CLOSING;
      }
      break;

    case STATE_SERVO2_CLOSING: {
      unsigned long elapsed = sekarang - waktuMulaiGerak;
      if (elapsed >= SWEEP_DURATION_MS) {
        currentAngle2 = targetAngle2;
        servo2.write(currentAngle2);
        stateSorter   = STATE_IDLE;
        Serial.println("ACK_SERVO2_CLOSED");
      } else {
        float p = (float)elapsed / (float)SWEEP_DURATION_MS;
        float factor = hitungSCurve(p);
        int nextAngle = (int)round(startAngle2 + (targetAngle2 - startAngle2) * factor);
        if (nextAngle != currentAngle2) {
          currentAngle2 = nextAngle;
          servo2.write(currentAngle2);
        }
      }
      break;
    }
  }
}

// ============================================================
// FUNGSI UPDATE DISPLAY LCD 16X2 (ANTI-FLICKER / NON-BLOCKING)
// ============================================================
void updateTampilanLcd() {
  if (!lcdTerdeteksi) return; // Lindungi jika LCD belum terpasang agar tidak menghambat pergerakan servo

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
// EKSEKUSI PERINTAH KLASIFIKASI DENGAN PROTEKSI ANTI-TABRAKAN
// ============================================================
void eksekusiAksi(String cmd) {
  // 1. MATANG (Kelas '0') -> Buka Servo 1 (Buang Kiri) dengan Profil S-Curve
  if (cmd == "matang" || cmd == "0") {
    totalTomat++;
    totalMatang++;
    pesanKhususLcd = "SORTIR: MATANG";
    waktuPesanKhusus = millis();
    perluUpdateLcd = true;

    if (stateSorter == STATE_IDLE) {
      waktuMulaiAksi   = millis();
      waktuMulaiGerak  = waktuMulaiAksi;
      startAngle1      = currentAngle1;
      targetAngle1     = SERVO1_BUKA;
      startAngle2      = SERVO2_STANDBY;
      targetAngle2     = SERVO2_STANDBY;
      stateSorter      = STATE_SERVO1_OPENING;
      Serial.println("ACK_MATANG_OPENING");
    } else {
      Serial.println("STATUS_BUSY");
    }
  }
  // 2. SETENGAH MATANG (Kelas '2') -> Buka Servo 2 (Buang Kanan) dengan Profil S-Curve
  else if (cmd == "setengah_matang" || cmd == "2") {
    totalTomat++;
    totalSetengah++;
    pesanKhususLcd = "SORTIR: SETENGAH";
    waktuPesanKhusus = millis();
    perluUpdateLcd = true;

    if (stateSorter == STATE_IDLE) {
      waktuMulaiAksi   = millis();
      waktuMulaiGerak  = waktuMulaiAksi;
      startAngle2      = currentAngle2;
      targetAngle2     = SERVO2_BUKA;
      startAngle1      = SERVO1_STANDBY;
      targetAngle1     = SERVO1_STANDBY;
      stateSorter      = STATE_SERVO2_OPENING;
      Serial.println("ACK_SETENGAH_OPENING");
    } else {
      Serial.println("STATUS_BUSY");
    }
  }
  // 3. MENTAH (Kelas '1') -> Kedua Servo Tetap Standby (Lolos Lurus)
  else if (cmd == "mentah" || cmd == "1") {
    totalTomat++;
    totalMentah++;
    pesanKhususLcd = "SORTIR: MENTAH";
    waktuPesanKhusus = millis();
    perluUpdateLcd = true;

    if (stateSorter == STATE_IDLE) {
      targetAngle1  = SERVO1_STANDBY;
      targetAngle2  = SERVO2_STANDBY;
      currentAngle1 = SERVO1_STANDBY;
      currentAngle2 = SERVO2_STANDBY;
      servo1.write(SERVO1_STANDBY);
      servo2.write(SERVO2_STANDBY);
    }
    Serial.println("ACK_MENTAH_PASSTHROUGH");
  }
  // 4. RESET / STANDBY MANUAL
  else if (cmd == "standby" || cmd == "reset" || cmd == "3") {
    targetAngle1  = SERVO1_STANDBY;
    targetAngle2  = SERVO2_STANDBY;
    currentAngle1 = SERVO1_STANDBY;
    currentAngle2 = SERVO2_STANDBY;
    servo1.write(SERVO1_STANDBY);
    servo2.write(SERVO2_STANDBY);
    stateSorter   = STATE_IDLE;
    pesanKhususLcd = "SERVO: STANDBY";
    waktuPesanKhusus = millis();
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
    totalTomat    = 0;
    totalMatang   = 0;
    totalSetengah = 0;
    totalMentah   = 0;
    pesanKhususLcd = "RESET COUNTER OK";
    waktuPesanKhusus = millis();
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

        // 1. Handshake saat Python mendeteksi port
        if (data == "go") {
          statusSistemHidup = true;
          digitalWrite(pinRelay, HIGH);
          perluUpdateLcd = true;
          Serial.println("ok");
        }
        // 2. Pembacaan sensor proximity konveyor
        else if (data == "se") {
          statusProximity = digitalRead(pinProximity);
          Serial.println(statusProximity);
        }
        // 3. Perintah pemilah tomat & kontrol status
        else if (data == "matang" || data == "0" ||
                 data == "setengah_matang" || data == "2" ||
                 data == "mentah" || data == "1" ||
                 data == "standby" || data == "reset" || data == "3" ||
                 data == "hidup" || data == "mati" ||
                 data == "on" || data == "off" ||
                 data == "start" || data == "stop" ||
                 data == "reset_tomat" || data == "reset_count" || data == "clear") {
          eksekusiAksi(data);
        }
        // 4. Set jumlah tomat manual / sinkronisasi dari serial
        else if (data.startsWith("set_tomat ") || data.startsWith("count:")) {
          int idx = data.indexOf(' ');
          if (idx < 0) idx = data.indexOf(':');
          if (idx >= 0) {
            totalTomat = data.substring(idx + 1).toInt();
            perluUpdateLcd = true;
            Serial.print("ACK_SET_TOMAT: "); Serial.println(totalTomat);
          }
        }
        // 5. Query status sistem & counter
        else if (data == "status") {
          Serial.print("STATUS:");
          Serial.print(statusSistemHidup ? "HIDUP" : "MATI");
          Serial.print(",TOMAT:");
          Serial.println(totalTomat);
        }
        // 6. Perintah manual uji sudut dengan profil S-Curve halus
        else if (data.startsWith("s1 ")) {
          int ang = data.substring(3).toInt();
          gerakSCurveSatuServo(servo1, currentAngle1, currentAngle1, ang, SWEEP_DURATION_MS);
          targetAngle1 = currentAngle1;
          startAngle1  = currentAngle1;
          stateSorter  = STATE_IDLE;
          Serial.print("ACK_SET_SERVO1: "); Serial.println(currentAngle1);
        }
        else if (data.startsWith("s2 ")) {
          int ang = data.substring(3).toInt();
          gerakSCurveSatuServo(servo2, currentAngle2, currentAngle2, ang, SWEEP_DURATION_MS);
          targetAngle2 = currentAngle2;
          startAngle2  = currentAngle2;
          stateSorter  = STATE_IDLE;
          Serial.print("ACK_SET_SERVO2: "); Serial.println(currentAngle2);
        }
        // 7. Tes gerakan berurutan kedua servo dengan profil S-Curve
        else if (data == "test") {
          Serial.println("ACK_TEST_START");
          gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_STANDBY, SERVO1_BUKA, SWEEP_DURATION_MS);
          delay(WAKTU_TAHAN_MS);
          gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_BUKA, SERVO1_STANDBY, SWEEP_DURATION_MS);
          delay(300);

          gerakSCurveSatuServo(servo2, currentAngle2, SERVO2_STANDBY, SERVO2_BUKA, SWEEP_DURATION_MS);
          delay(WAKTU_TAHAN_MS);
          gerakSCurveSatuServo(servo2, currentAngle2, SERVO2_BUKA, SERVO2_STANDBY, SWEEP_DURATION_MS);

          currentAngle1 = SERVO1_STANDBY; targetAngle1 = SERVO1_STANDBY; startAngle1 = SERVO1_STANDBY;
          currentAngle2 = SERVO2_STANDBY; targetAngle2 = SERVO2_STANDBY; startAngle2 = SERVO2_STANDBY;
          stateSorter = STATE_IDLE;
          Serial.println("ACK_TEST_DONE");
        }
        else {
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

  servo1.setPeriodHertz(50); // Frekuensi standar servo 50Hz
  servo2.setPeriodHertz(50);

  // Inisialisasi pin servo dengan rentang pulsa standar Arduino (544 - 2400us)
  servo1.attach(pinServo1, 544, 2400);
  servo2.attach(pinServo2, 544, 2400);

  // Set posisi awal standby
  currentAngle1 = SERVO1_STANDBY;
  currentAngle2 = SERVO2_STANDBY;
  targetAngle1  = SERVO1_STANDBY;
  targetAngle2  = SERVO2_STANDBY;
  startAngle1   = SERVO1_STANDBY;
  startAngle2   = SERVO2_STANDBY;
  servo1.write(currentAngle1);
  servo2.write(currentAngle2);

  // Inisialisasi I2C LCD dengan Fast Mode 400kHz & Timeout aman
  Wire.begin(pinSDA, pinSCL);
  Wire.setClock(400000); // 400kHz Fast I2C (mencegah delay pada pergerakan servo)
  Wire.setTimeOut(30);   // Timeout 30ms

  // Cek apakah modul LCD terpasang fisik di bus I2C (coba 0x27, lalu 0x3F)
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
    lcd.print("SISTEM PEMILAH  ");
    lcd.setCursor(0, 1);
    lcd.print("TOMAT C4.5 READY");
    delay(200);
    updateTampilanLcd();
  }

  // Uji gerak halus singkat saat boot
  delay(100);
  gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_STANDBY, 75, 100);
  gerakSCurveSatuServo(servo1, currentAngle1, 75, SERVO1_STANDBY, 100);
  gerakSCurveSatuServo(servo2, currentAngle2, SERVO2_STANDBY, 25, 100);
  gerakSCurveSatuServo(servo2, currentAngle2, 25, SERVO2_STANDBY, 100);

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

  // 4. Perbarui LCD HANYA saat servo TIDAK sedang bergerak aktif
  //    agar ayunan servo 100% mulus tanpa terinterupsi transaksi I2C
  bool servoSedangBergerak = (stateSorter == STATE_SERVO1_OPENING || 
                              stateSorter == STATE_SERVO1_CLOSING || 
                              stateSorter == STATE_SERVO2_OPENING || 
                              stateSorter == STATE_SERVO2_CLOSING);

  if (!servoSedangBergerak) {
    if (perluUpdateLcd || (pesanKhususLcd.length() > 0 && millis() - waktuPesanKhusus >= 1500)) {
      updateTampilanLcd();
      perluUpdateLcd = false;
    }
  }

  // Beri kesempatan FreeRTOS scheduler agar watchdog tidak terpicu
  yield();
}