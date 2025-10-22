#include <Adafruit_NeoPixel.h>

#define LED_PIN     6       // Data pin for WS2812
#define LED_COUNT   16      // Number of LEDs
#define BUTTON_PIN  2       // Button input pin

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// Button state tracking
bool lastButtonState = HIGH;       // Previous stable button state
bool lastReading = HIGH;           // Last raw reading
unsigned long lastDebounceTime = 0; // Last time button state changed
unsigned long buttonPressTime = 0;
bool isHolding = false;
bool holdSent = false;

// Click detection state
enum ClickState {
  IDLE,
  FIRST_CLICK,
  WAITING_FOR_SECOND
};
ClickState clickState = IDLE;
unsigned long firstClickTime = 0;

// Thresholds (in milliseconds)
const unsigned long DEBOUNCE_DELAY = 50;
const unsigned long HOLD_THRESHOLD = 500;
const unsigned long DOUBLE_CLICK_THRESHOLD = 300; // Increased for easier detection

// LED state
uint8_t currentR = 0, currentG = 0, currentB = 0;
uint8_t currentBrightness = 30;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP); // button to GND, so LOW = pressed
  Serial.begin(115200);
  strip.begin();
  strip.setBrightness(currentBrightness);
  strip.show(); // Initialize all pixels to 'off'
}

void loop() {
  handleButton();
  handleSerial();
}

void handleButton() {
  // Read the raw button state
  bool reading = digitalRead(BUTTON_PIN);

  // If the reading changed (due to noise or actual press), reset debounce timer
  if (reading != lastReading) {
    lastDebounceTime = millis();
  }

  // Only process if the reading has been stable for the debounce period
  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
    // We have a stable reading - check if it's different from our last stable state
    bool buttonState = reading;

    // Button is pressed (transition HIGH -> LOW)
    if (buttonState == LOW && lastButtonState == HIGH) {
      buttonPressTime = millis();
      isHolding = false;
      holdSent = false;

      // Check if this is a second click
      if (clickState == WAITING_FOR_SECOND) {
        unsigned long timeSinceFirst = millis() - firstClickTime;
        if (timeSinceFirst < DOUBLE_CLICK_THRESHOLD) {
          // Double click detected!
          Serial.println("button_double_click");
          clickState = IDLE;
          firstClickTime = 0;
        } else {
          // Too slow, treat as new first click
          clickState = FIRST_CLICK;
          firstClickTime = millis();
        }
      } else {
        // This is a first click
        clickState = FIRST_CLICK;
        firstClickTime = millis();
      }
    }

    // Check if button is being held (using stable state)
    if (buttonState == LOW && !holdSent) {
      unsigned long pressDuration = millis() - buttonPressTime;
      if (pressDuration >= HOLD_THRESHOLD) {
        Serial.println("button_hold");
        isHolding = true;
        holdSent = true;
        // Cancel any click detection
        clickState = IDLE;
      }
    }

    // Button is released (transition LOW -> HIGH)
    if (buttonState == HIGH && lastButtonState == LOW) {
      // If this was a hold, emit release
      if (isHolding) {
        Serial.println("button_release");
        isHolding = false;
        clickState = IDLE;
      } else if (clickState == FIRST_CLICK) {
        // Released after first click - now waiting for potential second click
        clickState = WAITING_FOR_SECOND;
      }
    }

    // Update last stable state
    lastButtonState = buttonState;
  }

  // Check if we're waiting for a second click and timeout expired
  if (clickState == WAITING_FOR_SECOND) {
    unsigned long timeSinceFirst = millis() - firstClickTime;
    if (timeSinceFirst >= DOUBLE_CLICK_THRESHOLD) {
      // Timeout - it's just a single click
      Serial.println("button_click");
      clickState = IDLE;
      firstClickTime = 0;
    }
  }

  // Update last reading
  lastReading = reading;
}

void handleSerial() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("COLOR:")) {
      // Parse COLOR:r,g,b or COLOR:r,g,b,brightness
      String params = command.substring(6);
      int firstComma = params.indexOf(',');
      int secondComma = params.indexOf(',', firstComma + 1);
      int thirdComma = params.indexOf(',', secondComma + 1);

      if (firstComma > 0 && secondComma > 0) {
        currentR = params.substring(0, firstComma).toInt();
        currentG = params.substring(firstComma + 1, secondComma).toInt();
        currentB = params.substring(secondComma + 1, thirdComma > 0 ? thirdComma : params.length()).toInt();

        if (thirdComma > 0) {
          currentBrightness = params.substring(thirdComma + 1).toInt();
          strip.setBrightness(currentBrightness);
        }

        setAllPixels(currentR, currentG, currentB);
      }
    } else if (command.startsWith("BRIGHTNESS:")) {
      // Parse BRIGHTNESS:value
      currentBrightness = command.substring(11).toInt();
      strip.setBrightness(currentBrightness);
      strip.show();
    }
  }
}

void setAllPixels(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < LED_COUNT; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
}
