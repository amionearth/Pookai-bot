/*
 * PookalBot Firmware v5.2 — High-Power L298N Drive & Universal Parser
 * ==================================================================================
 *
 * Hardware Pinout (Verified & Tested):
 * --------------------------------------------------
 * L298N Motor Driver:
 *   - Left Motor:  IN1 = GPIO 25, IN2 = GPIO 26
 *   - Right Motor: IN3 = GPIO 32, IN4 = GPIO 33
 *   - Note: ENA & ENB 5V jumpers installed on L298N board.
 *
 * SG90 Servo:
 *   - Signal (Orange/Yellow) -> GPIO 13
 *   - Power (Red)            -> 5V
 *   - Ground (Brown/Black)   -> GND
 *
 * 1.8" SPI TFT (ST7735 128x160):
 *   - CS    -> GPIO 5
 *   - RESET -> GPIO 4
 *   - A0/DC -> GPIO 2
 *   - SCK   -> GPIO 18
 *   - SDA   -> GPIO 23 (MOSI)
 *   - VCC   -> 3.3V
 *   - GND   -> GND
 *   - LED   -> 3.3V
 * ==================================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>

// ==================================================================================
//                                   CONFIGURATION
// ==================================================================================

const char* WIFI_SSID     = "Tinker Space";
const char* WIFI_PASSWORD = "123tinkerspace";

const char* PI_IP          = "192.168.11.237"; // Raspberry Pi 5 IP
const int   PI_PORT        = 9000;
const int   LOCAL_UDP_PORT = 9000;
const int   DISPLAY_PORT   = 9001;

const bool INVERT_LEFT    = false;
const bool INVERT_RIGHT   = false;
const unsigned long MOTOR_WATCHDOG_MS = 600;

// Servo Angles (Degrees)
const int PEN_UP_ANGLE   = 30;
const int PEN_DOWN_ANGLE = 95;

#define PIN_IN1 25
#define PIN_IN2 26
#define PIN_IN3 32
#define PIN_IN4 33
#define PIN_SERVO 13

#define TFT_CS    5
#define TFT_RST   4
#define TFT_DC    2
#define TFT_SCK   18
#define TFT_MOSI  23

#define SCREEN_W  160
#define SCREEN_H  128
#define FRAME_BYTES (SCREEN_W * SCREEN_H * 2)

// ==================================================================================
//                                     GLOBALS
// ==================================================================================

WiFiUDP udp;
WiFiServer displayServer(DISPLAY_PORT);
WiFiClient displayClient;

Servo penServo;
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

uint8_t frameBuffer[FRAME_BYTES];
char packetBuf[512];
char serialBuf[256];
int  serialBufIdx = 0;

unsigned long lastCommandMs    = 0;
unsigned long lastStatusSendMs = 0;

bool penIsDown    = false;
int  currentLeft  = 0;
int  currentRight = 0;

// Forward declarations
void setupMotors();
void setupServo();
void setupTFT();
void setupWiFi();
void setLeftMotor(int speed);
void setRightMotor(int speed);
void stopMotors();
void setPen(bool down);
void setServoAngle(int angle);
void processCommand(char* cmdStr);
void sendStatusToPi();
void handleDisplayStream();
void showBootScreen();

// ==================================================================================
//                                      SETUP
// ==================================================================================

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n=================================================");
  Serial.println("   PookalBot Firmware v5.2 — Direct Hardware Control ");
  Serial.println("=================================================");

  setupMotors();
  setupServo();
  setupTFT();
  setupWiFi();

  showBootScreen();
  Serial.println("[ESP32] Listening for UDP Drive/Pen (9000) & TCP Video (9001)");
}

// ==================================================================================
//                                      LOOP
// ==================================================================================

void loop() {
  unsigned long now = millis();

  // 1. Process High-Speed GIF Video Stream (TCP 9001)
  handleDisplayStream();

  // 2. Process UDP Drive & Pen Commands (UDP 9000)
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    int len = udp.read(packetBuf, sizeof(packetBuf) - 1);
    if (len > 0) {
      packetBuf[len] = '\0';
      processCommand(packetBuf);
      lastCommandMs = now;
    }
  }

  // 3. Process USB Serial Commands (fallback/debugging)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialBufIdx > 0) {
        serialBuf[serialBufIdx] = '\0';
        processCommand(serialBuf);
        serialBufIdx = 0;
        lastCommandMs = now;
      }
    } else {
      if (serialBufIdx < (int)sizeof(serialBuf) - 1) {
        serialBuf[serialBufIdx++] = c;
      }
    }
  }

  // 4. Watchdog: Auto-stop if no packet received within timeout
  if (now - lastCommandMs > MOTOR_WATCHDOG_MS) {
    if (currentLeft != 0 || currentRight != 0) {
      stopMotors();
    }
  }

  // 5. Periodic Telemetry (every 500ms)
  if (now - lastStatusSendMs > 500) {
    lastStatusSendMs = now;
    sendStatusToPi();
  }
}

// ==================================================================================
//                            HIGH-SPEED STREAM RECEIVER
// ==================================================================================

void handleDisplayStream() {
  if (!displayClient || !displayClient.connected()) {
    WiFiClient newClient = displayServer.available();
    if (newClient) {
      displayClient = newClient;
      displayClient.setNoDelay(true);
      Serial.println("[TFT] Pi 5 connected to stream display!");
    }
    return;
  }

  while (displayClient.available() >= 4) {
    uint8_t peekByte = displayClient.peek();
    if (peekByte == 0xAA || peekByte == 'G') {
      uint8_t hdr[4];
      displayClient.read(hdr, 4);
      bool isAA = (hdr[0] == 0xAA && hdr[1] == 0x55 && hdr[2] == 0xAA && hdr[3] == 0x55);
      bool isGF = (hdr[0] == 'G' && hdr[1] == 'F' && hdr[2] == '5' && hdr[3] == '6');

      if (isAA || isGF) {
        size_t bytesRead = 0;
        unsigned long tStart = millis();

        while (bytesRead < FRAME_BYTES && displayClient.connected()) {
          size_t avail = displayClient.available();
          if (avail > 0) {
            size_t toRead = min(avail, (size_t)(FRAME_BYTES - bytesRead));
            size_t n = displayClient.readBytes((char*)(frameBuffer + bytesRead), toRead);
            bytesRead += n;
          } else {
            delayMicroseconds(50);
          }
          if (millis() - tStart > 500) break;
        }

        if (bytesRead == FRAME_BYTES) {
          tft.startWrite();
          tft.setAddrWindow(0, 0, SCREEN_W, SCREEN_H);
          SPI.writeBytes(frameBuffer, FRAME_BYTES);
          tft.endWrite();
        }
        return;
      }
    } else {
      displayClient.read();
    }
  }
}

// ==================================================================================
//                         HIGH-POWER MOTOR DRIVER (L298N)
// ==================================================================================

void setupMotors() {
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  stopMotors();
}

void setLeftMotor(int speed) {
  if (INVERT_LEFT) speed = -speed;
  speed = constrain(speed, -255, 255);
  currentLeft = speed;

  if (speed > 40) {
    digitalWrite(PIN_IN1, HIGH);
    digitalWrite(PIN_IN2, LOW);
  } else if (speed < -40) {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, HIGH);
  } else {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, LOW);
  }
}

void setRightMotor(int speed) {
  if (INVERT_RIGHT) speed = -speed;
  speed = constrain(speed, -255, 255);
  currentRight = speed;

  if (speed > 40) {
    digitalWrite(PIN_IN3, HIGH);
    digitalWrite(PIN_IN4, LOW);
  } else if (speed < -40) {
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, HIGH);
  } else {
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
  }
}

void stopMotors() {
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);
  currentLeft = 0;
  currentRight = 0;
}

// ==================================================================================
//                                     SERVO CONTROL
// ==================================================================================

void setupServo() {
  penServo.setPeriodHertz(50);
  penServo.attach(PIN_SERVO, 500, 2400);
  penServo.write(PEN_UP_ANGLE);
  delay(200);
  penServo.detach();
  penIsDown = false;
}

void setServoAngle(int angle) {
  angle = constrain(angle, 0, 180);
  penServo.attach(PIN_SERVO, 500, 2400);
  penServo.write(angle);
  delay(250);
  penServo.detach();
  Serial.printf("[Servo] Angle set to: %d deg\n", angle);
}

void setPen(bool down) {
  penIsDown = down;
  setServoAngle(down ? PEN_DOWN_ANGLE : PEN_UP_ANGLE);
  Serial.printf("[Servo] Pen: %s\n", down ? "DOWN (Drawing)" : "UP (Travel)");
}

// ==================================================================================
//                      UNIVERSAL COMMAND PARSER (JSON & Text)
// ==================================================================================

void processCommand(char* str) {
  if (!str || strlen(str) == 0) return;

  // 1. "STOP" or "ESTOP"
  if (strcasecmp(str, "STOP") == 0 || strcasecmp(str, "ESTOP") == 0) {
    stopMotors();
    Serial.println("[CMD] STOP");
    return;
  }

  // 2. Directional Text
  if (strcasecmp(str, "FORWARD") == 0 || strcasecmp(str, "FWD") == 0) {
    setLeftMotor(255);
    setRightMotor(255);
    return;
  }
  if (strcasecmp(str, "BACK") == 0 || strcasecmp(str, "REV") == 0) {
    setLeftMotor(-255);
    setRightMotor(-255);
    return;
  }
  if (strcasecmp(str, "LEFT") == 0) {
    setLeftMotor(-255);
    setRightMotor(255);
    return;
  }
  if (strcasecmp(str, "RIGHT") == 0) {
    setLeftMotor(255);
    setRightMotor(-255);
    return;
  }

  // 3. "DRIVE:left,right"
  if (strncasecmp(str, "DRIVE:", 6) == 0) {
    int l = 0, r = 0;
    if (sscanf(str + 6, "%d,%d", &l, &r) >= 1) {
      if (sscanf(str + 6, "%d,%d", &l, &r) == 1) r = l;
      setLeftMotor(l);
      setRightMotor(r);
      return;
    }
  }

  // 4. "SERVO:angle"
  if (strncasecmp(str, "SERVO:", 6) == 0) {
    int ang = 90;
    if (sscanf(str + 6, "%d", &ang) == 1) {
      setServoAngle(ang);
      return;
    }
  }

  // 5. Pen commands
  if (strcasecmp(str, "PEN:DOWN") == 0 || strcasecmp(str, "PEN_DOWN") == 0) {
    setPen(true);
    return;
  }
  if (strcasecmp(str, "PEN:UP") == 0 || strcasecmp(str, "PEN_UP") == 0) {
    setPen(false);
    return;
  }
  if (strcasecmp(str, "PEN:TOGGLE") == 0) {
    setPen(!penIsDown);
    return;
  }

  // 6. JSON format
  if (str[0] == '{') {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, str);
    if (!err) {
      if (doc.containsKey("left") || doc.containsKey("right")) {
        int l = doc["left"] | 0;
        int r = doc["right"] | 0;
        setLeftMotor(l);
        setRightMotor(r);
        if (doc.containsKey("pen")) setPen((doc["pen"] | 0) != 0);
        return;
      }
      if (doc.containsKey("cmd")) {
        const char* cmd = doc["cmd"] | "";
        if (strcmp(cmd, "drive") == 0) {
          setLeftMotor(doc["left"] | 0);
          setRightMotor(doc["right"] | 0);
        } else if (strcmp(cmd, "pen") == 0) {
          const char* st = doc["state"] | "up";
          setPen(strcmp(st, "down") == 0);
        } else if (strcmp(cmd, "stop") == 0) {
          stopMotors();
        }
        return;
      }
    }
  }
}

// ==================================================================================
//                                  STATUS & TELEMETRY
// ==================================================================================

void sendStatusToPi() {
  StaticJsonDocument<192> doc;
  doc["status"]  = "ok";
  doc["ip"]      = WiFi.localIP().toString();
  doc["left"]    = currentLeft;
  doc["right"]   = currentRight;
  doc["pen"]     = penIsDown ? 1 : 0;
  doc["rssi"]    = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;

  char out[192];
  size_t len = serializeJson(doc, out);

  if (WiFi.status() == WL_CONNECTED && PI_IP[0] != '\0') {
    udp.beginPacket(PI_IP, PI_PORT);
    udp.write((const uint8_t*)out, len);
    udp.endPacket();
  }
}

// ==================================================================================
//                                  TFT DISPLAY
// ==================================================================================

void setupTFT() {
  SPI.begin(TFT_SCK, -1, TFT_MOSI, TFT_CS);
  tft.initR(INITR_BLACKTAB);
  tft.setRotation(1);
  tft.fillScreen(ST77XX_BLACK);
}

void showBootScreen() {
  tft.fillScreen(ST77XX_BLACK);
  tft.fillRect(0, 0, SCREEN_W, 24, ST77XX_BLUE);
  tft.setTextColor(ST77XX_YELLOW);
  tft.setTextSize(2);
  tft.setCursor(14, 4);
  tft.println("POOKALBOT");

  tft.setTextSize(1);
  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(10, 36);
  tft.print("WiFi: ");
  tft.println(WIFI_SSID);

  tft.setCursor(10, 52);
  tft.print("Status: ");
  if (WiFi.status() == WL_CONNECTED) {
    tft.setTextColor(ST77XX_GREEN);
    tft.println("Connected");
  } else {
    tft.setTextColor(ST77XX_RED);
    tft.println("Connecting...");
  }

  tft.drawRoundRect(8, 70, SCREEN_W - 16, 32, 4, ST77XX_CYAN);
  tft.setTextColor(ST77XX_YELLOW);
  tft.setCursor(16, 75);
  tft.println("ESP32 IP:");

  tft.setTextColor(ST77XX_GREEN);
  tft.setTextSize(1);
  tft.setCursor(16, 88);
  tft.println(WiFi.localIP().toString());

  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(10, 112);
  tft.println("UDP: 9000  TCP: 9001");
}

// ==================================================================================
//                                      WIFI SETUP
// ==================================================================================

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[WiFi] Connecting to '%s'", WIFI_SSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected! IP Address: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] Connection failed. Retrying in background.");
  }

  udp.begin(LOCAL_UDP_PORT);
  displayServer.begin();
  Serial.printf("[TCP] Display server listening on port %d\n", DISPLAY_PORT);
}
