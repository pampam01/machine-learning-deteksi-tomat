#include <ESP32Servo.h>

Servo servo1;
Servo servo2;

// ============================================================
// KONFIGURASI PIN & HARDWARE
// ============================================================
const int pinServo1    = 18;  // GPIO Servo 1 (Pemilah Matang - Buang Kiri)
const int pinServo2    = 19;  // GPIO Servo 2 (Pemilah Setengah Matang - Buang Kanan)
const int pinProximity = 4;   // GPIO Sensor Proximity Konveyor
const int pinRelay     = 14;  // GPIO Relay (opsional: kontrol motor konveyor)

// Baud rate komunikasi serial (disamakan dengan Python: 115200)
const long BAUD_RATE = 115200;

// ============================================================
// KONFIGURASI SUDUT SERVO (0 - 180 Derajat)
// ============================================================
// Posisi Standby / Terbuka lurus (kedua lengan sejajar dinding konveyor menghadap ke depan)
const int SERVO1_STANDBY = 90;  // Servo 1 merapat ke dinding kiri (lurus ke depan)
const int SERVO2_STANDBY = 0;   // Servo 2 merapat ke dinding kanan (lurus ke depan)

// Posisi Buang (menutup jalur tengah untuk membelokkan tomat ke wadah)
const int SERVO1_BUKA    = 0;   // Servo 1 buang kiri (bergerak ke tengah)
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

int statusProximity = 0;

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
// EKSEKUSI PERINTAH KLASIFIKASI DENGAN PROTEKSI ANTI-TABRAKAN
// ============================================================
void eksekusiAksi(String cmd) {
  // 1. MATANG (Kelas '0') -> Buka Servo 1 (Buang Kiri) dengan Profil S-Curve
  if (cmd == "matang" || cmd == "0") {
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
    Serial.println("ACK_STANDBY");
  }
}

// ============================================================
// HANDLER KOMUNIKASI SERIAL
// ============================================================
void prosesSerial() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() == 0) return;

    // 1. Handshake saat Python mendeteksi port
    if (data == "go") {
      Serial.println("ok");
    }
    // 2. Pembacaan sensor proximity konveyor
    else if (data == "se") {
      statusProximity = digitalRead(pinProximity);
      Serial.println(statusProximity);
    }
    // 3. Perintah pemilah tomat
    else if (data == "matang" || data == "0" ||
             data == "setengah_matang" || data == "2" ||
             data == "mentah" || data == "1" ||
             data == "standby" || data == "reset" || data == "3") {
      eksekusiAksi(data);
    }
    // 4. Perintah manual uji sudut dengan profil S-Curve halus
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
    // 5. Tes gerakan berurutan kedua servo dengan profil S-Curve
    else if (data == "test") {
      Serial.println("ACK_TEST_START");
      // Servo 1 Matang (Buang Kiri)
      gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_STANDBY, SERVO1_BUKA, SWEEP_DURATION_MS);
      delay(WAKTU_TAHAN_MS);
      gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_BUKA, SERVO1_STANDBY, SWEEP_DURATION_MS);
      delay(300);

      // Servo 2 Setengah Matang (Buang Kanan)
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
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(pinProximity, INPUT);
  pinMode(pinRelay, OUTPUT);
  digitalWrite(pinRelay, LOW);

  pinMode(pinServo1, OUTPUT);
  pinMode(pinServo2, OUTPUT);

  servo1.setPeriodHertz(50); // Frekuensi standar servo 50Hz
  servo2.setPeriodHertz(50);

  // Inisialisasi pin servo
  servo1.attach(pinServo1, 500, 2400);
  servo2.attach(pinServo2, 500, 2400);

  // Set posisi awal standby
  currentAngle1 = SERVO1_STANDBY;
  currentAngle2 = SERVO2_STANDBY;
  targetAngle1  = SERVO1_STANDBY;
  targetAngle2  = SERVO2_STANDBY;
  startAngle1   = SERVO1_STANDBY;
  startAngle2   = SERVO2_STANDBY;
  servo1.write(currentAngle1);
  servo2.write(currentAngle2);

  // Uji gerak halus singkat saat boot (tanpa getaran gedek-gedek)
  delay(200);
  gerakSCurveSatuServo(servo1, currentAngle1, SERVO1_STANDBY, 75, 150);
  gerakSCurveSatuServo(servo1, currentAngle1, 75, SERVO1_STANDBY, 150);
  gerakSCurveSatuServo(servo2, currentAngle2, SERVO2_STANDBY, 15, 150);
  gerakSCurveSatuServo(servo2, currentAngle2, 15, SERVO2_STANDBY, 150);
}

// ============================================================
// LOOP UTAMA
// ============================================================
void loop() {
  // 1. Perbarui gerakan servo & timer auto-close
  updateSmoothServo();

  // 2. Baca perintah serial secara non-blocking
  prosesSerial();
}