#include <Wire.h>
#include "MAX30100_PulseOximeter.h"

#define ECG_PIN A0
#define ECG_SAMPLING_INTERVAL_MS 20   // 50 Hz
#define REPORTING_PERIOD_MS      1000 // HR/SpO2 refresh window

PulseOximeter pox;
uint32_t lastEcgMs = 0;
uint32_t lastHrUpdateMs = 0;

volatile float hr = 0.0f;
volatile float spo2 = 0.0f;

// Optional beat callback (disabled printing to keep CSV clean)
void onBeatDetected() {
  // Avoid Serial prints here (will corrupt CSV)
}

void setup() {
  Serial.begin(115200);
  // Small delay to let serial settle
  delay(1500);

  // I2C init
  Wire.begin();

  // MAX30100 init
  if (!pox.begin()) {
    // If you need to debug, use LED or uncomment temporarily.
    Serial.println("ERR: MAX30100 init failed");
    while (1);
  }
  // Tune LED current if needed (common values: 7.6mA, 11mA, 24mA, 50mA)
  pox.setIRLedCurrent(MAX30100_LED_CURR_50MA);
  pox.setOnBeatDetectedCallback(onBeatDetected);

  // Stabilize sensor
  delay(1000);
}

void loop() {
  // Update MAX30100 internal state frequently
  pox.update();

  uint32_t now = millis();

  // Refresh HR/SpO₂ approximately once per second from sensor
  if (now - lastHrUpdateMs >= REPORTING_PERIOD_MS) {
    hr = pox.getHeartRate();   // 0 if not ready yet
    spo2 = pox.getSpO2();      // 0 if not ready yet
    lastHrUpdateMs = now;
  }

  // ECG sample @ 50 Hz
  if (now - lastEcgMs >= ECG_SAMPLING_INTERVAL_MS) {
    lastEcgMs = now;

    // Raw ECG (10-bit ADC 0..1023). Center near 512. You can high-pass in ML or in Pi code.
    int ecgRaw = analogRead(ECG_PIN);
    // Normalize to volts-ish if you like (optional); we’ll send raw ADC for now:
    float ecg = (float)ecgRaw;

    // CSV: hr,spo2,ecg  (no spaces, no extra prints)
    // Replicate most recent hr/spo2 so all three signals are 50 Hz
    Serial.print(hr, 2); Serial.print(",");
    Serial.print(spo2, 2); Serial.print(",");
    Serial.println(ecg, 2);
  }
}
