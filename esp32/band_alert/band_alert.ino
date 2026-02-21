/*
 * Raahi Band — ESP32 Wearable Alert System
 *
 * Receives crowd density values from the live detection server via Serial.
 * Protocol (over USB Serial at 115200 baud):
 *   "0.1" to "1.0\n"  → density value (LED color + OLED status)
 *   "2\n"              → person fall alert (buzzer + OLED warning)
 *
 * Thresholds:
 *   <= 0.3  → LOW      (green)
 *   <= 0.7  → MODERATE (yellow-orange)
 *   > 0.7   → CRITICAL (red)
 *   2       → FALL     (blue flash + buzzer SOS + OLED "Person Missing")
 *
 * Hardware:
 *   - SH1106 128x64 OLED via I2C
 *   - RGB LED (common anode) on pins 4 (R), 5 (G), 6 (B)
 *   - Buzzer on pin 7
 *   - Serial on COM3 (USB)
 */

#include <Wire.h>
#include <U8g2lib.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/U8X8_PIN_NONE);

// RGB (Common Anode)
#define RED_PIN 4
#define GREEN_PIN 5
#define BLUE_PIN 6

#define BUZZER_PIN 7

float value = 0.0;

void setup()
{

  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);

  // Attach PWM (ESP32 core 3.x)
  ledcAttach(RED_PIN, 5000, 8);
  ledcAttach(GREEN_PIN, 5000, 8);
  ledcAttach(BLUE_PIN, 5000, 8);

  u8g2.begin();
}

void loop()
{

  if (Serial.available())
  {

    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input == "2")
    {
      alertMode();
      return;
    }

    float received = input.toFloat();

    if (received >= 0.1 && received <= 1.0)
    {
      value = received;
      normalMode();
    }
  }
}

void normalMode()
{

  int redValue = map(value * 100, 10, 100, 0, 255);
  int greenValue = map(value * 100, 10, 100, 255, 0);

  redValue = 255 - redValue; // Common Anode
  greenValue = 255 - greenValue;

  ledcWrite(RED_PIN, redValue);
  ledcWrite(GREEN_PIN, greenValue);
  ledcWrite(BLUE_PIN, 255);

  u8g2.clearBuffer();

  u8g2.setFont(u8g2_font_ncenB14_tr);
  u8g2.setCursor(0, 20);
  u8g2.print(value, 1);

  u8g2.setFont(u8g2_font_6x12_tr);
  u8g2.setCursor(0, 50);

  if (value <= 0.3)
    u8g2.print("Status: LOW");
  else if (value <= 0.7)
    u8g2.print("Status: MODERATE");
  else
    u8g2.print("Status: CRITICAL");

  u8g2.sendBuffer();
}

void alertMode()
{

  ledcWrite(RED_PIN, 255);
  ledcWrite(GREEN_PIN, 255);
  ledcWrite(BLUE_PIN, 0);

  for (int i = 0; i < 5; i++)
  {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(150);
    digitalWrite(BUZZER_PIN, LOW);
    delay(150);
  }

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tr);
  u8g2.setCursor(0, 30);
  u8g2.print("Person Missing");
  u8g2.setCursor(0, 45);
  u8g2.print("In Your Zone");
  u8g2.sendBuffer();

  delay(2000);
}
