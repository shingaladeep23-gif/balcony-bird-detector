/**
 * AeroSentinel - Active Pan-Targeting Balcony Bird Deterrent Firmware
 * 
 * Hardware Setup:
 * - Arduino Uno connected via USB to the Host PC.
 * - Servo Signal (Orange/Yellow) connected to Digital Pin 9.
 * - Servo VCC and GND connected to an external 5V-6V power source (min 2A).
 * - Digital Pin 4 connected to the Signal (IN) of a 5V Relay module.
 * - Relay COM and NO (Normally Open) switch the 12V water pump.
 * - Common grounds: Arduino GND connected to External Power supply GND.
 * 
 * Protocol:
 * - Listens on serial port at 9600 baud for: "S[angle]\n" (e.g., "S105\n").
 * - Sweeps the servo to [angle] (45 to 135 deg range).
 * - Waits 400ms for physical servo rotation to complete.
 * - Fires water spray for 1.5 seconds to deter the bird.
 * - Returns to center (90 deg) and locks out further triggers for 10 seconds.
 */

#include <Servo.h>

// Hardware Pins
const int SERVO_PIN = 9;         // Servo control PWM pin
const int RELAY_PIN = 4;         // Water pump relay control pin
const int LED_PIN = 13;          // Onboard status feedback LED
const bool RELAY_ACTIVE = HIGH;   // Active-high relay signal (HIGH turns water on)

// Panning configuration
Servo panServo;
const int IDLE_ANGLE = 90;        // Facing straight ahead (default)
const int MIN_SAFE_ANGLE = 45;    // Safe horizontal limit (left)
const int MAX_SAFE_ANGLE = 135;   // Safe horizontal limit (right)

// Timing configurations
const unsigned long SPRAY_DURATION_MS = 1500;    // Duration of spray burst (1.5 seconds)
const unsigned long HARDWARE_COOLDOWN_MS = 10000; // Flood protection lockout delay (10 seconds)

// State variables
unsigned long lastSprayTime = 0;
bool isSpraying = false;

void setup() {
  // Setup control pins
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  // Set default idle state (water off)
  digitalWrite(RELAY_PIN, !RELAY_ACTIVE);
  digitalWrite(LED_PIN, LOW);
  
  // Initialize Servo and position it to center
  panServo.attach(SERVO_PIN);
  panServo.write(IDLE_ANGLE);
  
  // Start Serial communications at 9600 baud
  Serial.begin(9600);
  
  // Flash status LED twice to confirm setup complete
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
}

void loop() {
  unsigned long currentTime = millis();
  
  // 1. Handle Active Spraying timing
  if (isSpraying && (currentTime - lastSprayTime >= SPRAY_DURATION_MS)) {
    // Turn off water spray
    digitalWrite(RELAY_PIN, !RELAY_ACTIVE);
    digitalWrite(LED_PIN, LOW);
    
    // Allow water pressure to settle, then return servo to center
    delay(500);
    panServo.write(IDLE_ANGLE);
    isSpraying = false;
  }
  
  // 2. Read incoming serial commands
  if (Serial.available() > 0) {
    char firstChar = Serial.read();
    
    // Check for target trigger packet starter
    if (firstChar == 'S') {
      // Parse horizontal pan angle from serial string
      int parsedAngle = Serial.parseInt();
      
      // Enforce physical and safety bounds
      parsedAngle = constrain(parsedAngle, MIN_SAFE_ANGLE, MAX_SAFE_ANGLE);
      
      // 3. Enforce Safety Cooldown Lockout
      if (!isSpraying && (currentTime - lastSprayTime >= HARDWARE_COOLDOWN_MS || lastSprayTime == 0)) {
        // Point servo directly at the bird's horizontal angle
        panServo.write(parsedAngle);
        
        // Wait 400ms for physical motor sweep to complete
        delay(400);
        
        // Trigger water spray relay
        digitalWrite(RELAY_PIN, RELAY_ACTIVE);
        digitalWrite(LED_PIN, HIGH);
        
        // Reset timing reference to current time
        lastSprayTime = millis();
        isSpraying = true;
      }
    }
  }
}
