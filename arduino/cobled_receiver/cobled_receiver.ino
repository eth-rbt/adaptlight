/*
 * COB LED Serial Receiver for Pro Micro (ATmega32U4)
 *
 * Receives RGB values over Serial1 from Raspberry Pi
 * and outputs PWM signals to drive RGB MOSFETs.
 *
 * Protocol: [0xFF, R, G, B]  (4 bytes per update)
 *  - 0xFF is a sync marker
 *  - R/G/B are 0-255 (you said 0-254; 255 is fine too)
 *
 * Wiring:
 *   Pi GPIO14 (TX) -> Pro Micro RX (pin 1)  (with your series resistor)
 *   Pi GND -> Pro Micro GND
 *   Pro Micro pin 9 -> Red MOSFET gate (PWM)
 *   Pro Micro pin 5 -> Green MOSFET gate (PWM)
 *   Pro Micro pin 6 -> Blue MOSFET gate (PWM)
 */

#include <Arduino.h>

// ===================== User Config =====================

// PWM pins for RGB (Pro Micro PWM-capable pins)
static const uint8_t RED_PIN   = 9;  // Timer1
static const uint8_t GREEN_PIN = 5;  // Timer3
static const uint8_t BLUE_PIN  = 6;  // Timer4

// UART baud rate (must match Pi)
static const uint32_t PI_BAUD = 115200;

// Enable/disable USB debug printing
static const bool USB_DEBUG = true;

// How long to wait for USB Serial to enumerate (ms)
// Keep short so external VCC boot never blocks.
static const uint16_t USB_WAIT_MS = 250;

// Protocol constants
static const uint8_t SYNC_BYTE = 0xFF;

// ===================== Internal State =====================

enum ParseState : uint8_t {
  WAIT_SYNC = 0,
  READ_R,
  READ_G,
  READ_B
};

static ParseState state = WAIT_SYNC;

static uint8_t currentR = 0;
static uint8_t currentG = 0;
static uint8_t currentB = 0;

// Throttle debug prints (optional)
static uint32_t lastPrintMs = 0;
static const uint16_t PRINT_PERIOD_MS = 50; // limit to 20 Hz

// ===================== Helpers =====================

static inline void applyPWM(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(RED_PIN, r);
  analogWrite(GREEN_PIN, g);
  analogWrite(BLUE_PIN, b);
}

static inline bool usbReady() {
#if defined(__AVR_ATmega32U4__)
  return (bool)Serial;  // true if enumerated/open
#else
  return true;
#endif
}

static void usbPrintln(const __FlashStringHelper* msg) {
  if (USB_DEBUG && usbReady()) Serial.println(msg);
}

static void usbPrintRGB(uint8_t r, uint8_t g, uint8_t b) {
  if (!USB_DEBUG || !usbReady()) return;
  uint32_t now = millis();
  if (now - lastPrintMs < PRINT_PERIOD_MS) return;
  lastPrintMs = now;

  Serial.print(F("RGB: "));
  Serial.print(r);
  Serial.print(F(", "));
  Serial.print(g);
  Serial.print(F(", "));
  Serial.println(b);
}

// Robust packet parser: looks for 0xFF then reads 3 bytes.
// If 0xFF appears mid-packet, treat it as a resync.
static void processByte(uint8_t x) {
  if (x == SYNC_BYTE) {
    state = READ_R;
    return;
  }

  switch (state) {
    case WAIT_SYNC:
      // ignore until SYNC
      break;

    case READ_R:
      currentR = x;
      state = READ_G;
      break;

    case READ_G:
      currentG = x;
      state = READ_B;
      break;

    case READ_B:
      currentB = x;
      state = WAIT_SYNC;
      applyPWM(currentR, currentG, currentB);
      usbPrintRGB(currentR, currentG, currentB);
      break;
  }
}

// ===================== Arduino Hooks =====================

void setup() {
  // PWM outputs
  pinMode(RED_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(BLUE_PIN, OUTPUT);

  // Start with LEDs off
  applyPWM(0, 0, 0);

#if defined(__AVR_ATmega32U4__)
  // Hardware UART from Pi
  Serial1.begin(PI_BAUD);

  // USB debug (non-blocking)
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0 < USB_WAIT_MS)) {
    // wait a short time only; do NOT block forever
  }

  if (USB_DEBUG && usbReady()) {
    Serial.println(F("COB LED Receiver - Pro Micro (ATmega32U4)"));
    Serial.println(F("Listening on Serial1 @ 115200 (RX pin 1)"));
    Serial.println(F("Protocol: [0xFF, R, G, B]"));
  }
#else
  // Non-32U4 boards (not your case, but harmless)
  Serial.begin(PI_BAUD);
#endif
}

void loop() {
#if defined(__AVR_ATmega32U4__)
  while (Serial1.available() > 0) {
    processByte((uint8_t)Serial1.read());
  }
#else
  while (Serial.available() > 0) {
    processByte((uint8_t)Serial.read());
  }
#endif
}
