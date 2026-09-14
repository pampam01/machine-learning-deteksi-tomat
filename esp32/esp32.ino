#include <ESP32Servo.h>

Servo servo;
Servo servo2;

int servoPin = 5;
int servoPin2 = 18;

int relayPin = 14;

int posisi_sekarang = 90;   // simpan posisi terakhir servo
int posisi_sekarang2 = 90;  // simpan posisi terakhir servo

int pin_proximity = 4;
int proximity = 0;

// =============================
// Function: gerak servo pelan/cepat
// =============================
void gerakServo(int target, int kecepatan_delay) {
  if (posisi_sekarang < target) {
    // gerak naik
    for (int pos = posisi_sekarang; pos <= target; pos++) {
      servo.write(pos);
      delay(kecepatan_delay);
    }
  } else {
    // gerak turun
    for (int pos = posisi_sekarang; pos >= target; pos--) {
      servo.write(pos);
      delay(kecepatan_delay);
    }
  }

  posisi_sekarang = target;  // update posisi terakhir
}


void gerakServo2(int target, int kecepatan_delay) {
  if (posisi_sekarang2 < target) {
    // gerak naik
    for (int pos = posisi_sekarang2; pos <= target; pos++) {
      servo2.write(pos);
      delay(kecepatan_delay);
    }
  } else {
    // gerak turun
    for (int pos = posisi_sekarang2; pos >= target; pos--) {
      servo2.write(pos);
      delay(kecepatan_delay);
    }
  }

  posisi_sekarang2 = target;  // update posisi terakhir
}


void check_port() {

  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();
    if (data == "go") {
      Serial.println("ok");
      delay(100);
      Serial.println("ok");
      delay(100);
      Serial.println("ok");
    }

    else if (data == "se") {
      Serial.println(proximity);
    }

    else if (data == "1") {
      gerakServo(0, 1);  //buka
      delay(5000);
      gerakServo(90, 1);
      delay(1000);
    }

    else if (data == "2") {

      gerakServo2(0, 3);  //tutup
      delay(5000);

      gerakServo2(90, 3);  //turun
      delay(1000);
    }

    else if (data == "3") {
    }
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(relayPin, OUTPUT);
  pinMode(pin_proximity,INPUT);
  servo.setPeriodHertz(50);
  servo.attach(servoPin, 500, 2400);
  servo2.setPeriodHertz(50);
  servo2.attach(servoPin2, 500, 2400);
  digitalWrite(relayPin, LOW);

}

void loop() {
  proximity = digitalRead(pin_proximity);
 // Serial.println(proximity);
  check_port();
  
}
