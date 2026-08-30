// ─── User_Setup.h — 1.8" 128x160 ST7735 (A0-labeled DC, backlight hardwired) ───
#define ST7735_DRIVER
#define ST7735_REDTAB
#define TFT_WIDTH  128
#define TFT_HEIGHT 160

// Pin map (matches your wiring table)
#define TFT_MOSI   23
#define TFT_SCLK   18
#define TFT_CS      5
#define TFT_DC      2
#define TFT_RST     4
// No TFT_BL — your backlight is hardwired straight to 3.3V, not GPIO-controlled

// Fonts
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT