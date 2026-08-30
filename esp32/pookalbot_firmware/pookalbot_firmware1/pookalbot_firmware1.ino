#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

void setup() {
  tft.init();
  tft.setRotation(1);

  tft.fillScreen(TFT_BLACK);

  tft.setTextColor(TFT_RED, TFT_BLACK);
  tft.setTextSize(3);
  tft.setCursor(20, 20);
  tft.println("HELLO!");

  delay(1000);

  tft.fillScreen(TFT_BLUE);
  delay(1000);

  tft.fillScreen(TFT_GREEN);
  delay(1000);

  tft.fillScreen(TFT_RED);
}

void loop() {
}