#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Ticker.h>
#include <LiquidCrystal_I2C.h>

// Pin Definitions
#define SCAN_RX 16
#define SCAN_TX 17
HardwareSerial SerialScan(2);

#define SDA_PIN 21
#define SCL_PIN 22
LiquidCrystal_I2C lcd(0x27, 16, 2);

#define TRIG_PIN 23
#define ECHO_PIN 18
#define BUTTON_PIN 26
#define BUZZER_PIN 27
#define SERVO_DOOR_PIN 13
#define SERVO_M1_PIN 25
#define SERVO_M2_PIN 12

// MQTT Configuration
const char* MQTT_SERVER = "YOUR_MQTT_SERVER_IP";
const int MQTT_PORT = 1883;
const char* MQTT_USERNAME = "YOUR_MQTT_USERNAME";
const char* MQTT_PASSWORD = "YOUR_MQTT_PASSWORD";

// Device Information
const char* DEVICE_ID = "JMAILBOX-001";
const char* FIRMWARE_VERSION = "5.0.0-VPS";

// WiFi Configuration 
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// MQTT Topics
#define TOPIC_SENSOR_IN "alat/sensor"
#define TOPIC_COMMAND_OUT "alat/perintah"
#define TOPIC_STATUS_OUT "alat/status"
#define TOPIC_AI_RESULT "alat/ai_result"

// Constants
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;
const unsigned long DOOR_TIMEOUT = 15000; // 15 seconds
const unsigned long COMMAND_TIMEOUT = 30000; // 30 seconds
const int PACKAGE_DISTANCE_THRESHOLD = 15; // cm
const unsigned long PULSEIN_TIMEOUT = 10000; // microseconds
const unsigned long SENSOR_UPDATE_INTERVAL = 2000; // ms
const unsigned long STATUS_UPDATE_INTERVAL = 30000; // ms

// System State Machine
enum SystemState {
    STATE_INITIALIZING,
    STATE_IDLE,
    STATE_SCANNING,
    STATE_SENDING_SCAN_TO_VPS,
    STATE_WAITING_VPS_RESPONSE,
    STATE_MONITORING,
    STATE_WAITING_MQTT_COMMAND,
    STATE_DOOR_OPENING,
    STATE_WAITING_PACKAGE,
    STATE_DOOR_CLOSING,
    STATE_PAYMENT_DISPENSING,
    STATE_COMPLETING,
    STATE_ERROR,
    STATE_WAITING_MANUAL_INPUT
};

// Global Objects
WiFiClient espClient;
PubSubClient mqttClient(espClient);
Preferences preferences;
Ticker sensorTicker;
Ticker lcdTicker;
Servo doorServo;
Servo moneyServo1;
Servo moneyServo2;

// Package Structure
struct Package {
    String resi;
    String customer;
    String courier;
    bool isCOD;
    bool validated;
    int moneySlot;
    float amount;
    unsigned long timestamp;
    
    Package() { reset(); }
    
    void reset() {
        resi = "";
        customer = "";
        courier = "";
        isCOD = false;
        validated = false;
        moneySlot = 0;
        amount = 0.0;
        timestamp = 0;
    }
    
    bool isValid() {
        return resi.length() >= 5 && resi.length() <= 20;
    }
};

// Global Variables
SystemState currentState = STATE_INITIALIZING;
Package currentPackage;
String scannedResi = "";
String sessionId = "";
String instructionMsg = "";
String lastError = "";
bool doorOpen = false;
bool packageDetected = false;
bool mqttConnected = false;
int distance = 999;
unsigned long doorOpenTime = 0;
unsigned long stateStartTime = 0;
unsigned long lastActivityTime = 0;
unsigned long lastLoopTime = 0;
unsigned long lastMqttReconnectAttempt = 0;
unsigned long lastStatusSend = 0;
unsigned long lastSensorSend = 0;

// Buzzer Control
bool buzzerActive = false;
unsigned long buzzerStartTime = 0;
int buzzerPattern = 0;

// LCD Control
String lcdLine1 = "";
String lcdLine2 = "";
bool lcdNeedsUpdate = false;

// Command Handling
String pendingCommand = "";
String pendingResi = "";
String pendingMessageId = "";
unsigned long lastCommandTime = 0;

// Function Prototypes
void setup();
void loop();
void changeState(SystemState newState);
void handleStateMachine(unsigned long currentTime);
void handleStateTimeouts(unsigned long currentTime);
void handleDoorOpening();
void handleWaitingPackage(unsigned long currentTime);
void handleDoorClosing();
void handlePaymentDispensing();
void handleCompleting();
void beepPattern(int pattern);
void handleBuzzer();
void readUltrasonic();
void updateLCD(String line1, String line2, bool force = false);
void updateLCDPeriodic();
void updateInstruction(String message);
void checkButton();
void scanBarcode();
bool validateResiFormat(String resi);
void setupWiFi();
void setupMQTT();
void handleNetwork();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void handleVPSCommand(JsonDocument& doc);
void sendScanToVPS();
void sendSensorData();
void sendSystemStatus();
void sendStatusUpdate(String event, String details);
void sendDeliveryComplete();
void resetSystem();
void relaxServos();
void delayNonBlocking(unsigned long ms);
void executeMQTTCommand(String command, String resi, String reason);
void sendCommandResponse(String command, String status, String message = "");
void openMoneySlot(int slot = 0);
void closeMoneySlot(int slot = 0);
void openDoor();
void closeDoor();
void activateBuzzer();
void deactivateBuzzer();

void setup() {
    Serial.begin(115200);
    SerialScan.begin(9600, SERIAL_8N1, SCAN_RX, SCAN_TX);
    
    Serial.println("\n========================================");
    Serial.println("J-MAILBOX VPS INTEGRATION");
    Serial.println("Version: " + String(FIRMWARE_VERSION));
    Serial.println("Device ID: " + String(DEVICE_ID));
    Serial.println("========================================\n");
    
    // Initialize GPIO pins
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(TRIG_PIN, LOW);
    
    // Initialize I2C and LCD
    Wire.begin(SDA_PIN, SCL_PIN);
    lcd.init();
    lcd.backlight();
    lcd.clear();
    
    // Initialize Servos
    ESP32PWM::allocateTimer(0);
    doorServo.setPeriodHertz(50);
    moneyServo1.setPeriodHertz(50);
    moneyServo2.setPeriodHertz(50);
    
    // Generate session ID
    sessionId = String(millis()) + "-" + String(random(1000, 9999));
    
    // Initialize subsystems
    setupWiFi();
    setupMQTT();
    
    // Setup periodic tasks
    sensorTicker.attach_ms(300, readUltrasonic);
    lcdTicker.attach_ms(200, updateLCDPeriodic);
    
    // Initial state
    changeState(STATE_IDLE);
    updateInstruction("System Ready - VPS Mode");
    beepPattern(1);
    
    // Initialize timers
    lastActivityTime = millis();
    lastLoopTime = millis();
    
    Serial.println("[SYSTEM] Setup complete");
}

void loop() {
    unsigned long currentTime = millis();
    
    // Handle subsystems
    handleBuzzer();
    handleNetwork();
    checkButton();
    
    // State-specific handling
    switch (currentState) {
        case STATE_SCANNING:
            scanBarcode();
            break;
            
        case STATE_MONITORING:
            if (currentTime - lastSensorSend > SENSOR_UPDATE_INTERVAL) {
                sendSensorData();
                lastSensorSend = currentTime;
            }
            break;
    }
    
    // Handle state machine
    handleStateTimeouts(currentTime);
    handleStateMachine(currentTime);
    
    // Send periodic status updates
    if (currentTime - lastStatusSend > STATUS_UPDATE_INTERVAL) {
        sendSystemStatus();
        lastStatusSend = currentTime;
    }
    
    // Maintain loop timing
    unsigned long loopDuration = millis() - currentTime;
    if (loopDuration < 10) {
        delay(10 - loopDuration);
    }
    
    lastLoopTime = millis();
}

void changeState(SystemState newState) {
    SystemState oldState = currentState;
    currentState = newState;
    stateStartTime = millis();
    
    Serial.println("[STATE] " + String(oldState) + " -> " + String(newState));
    
    // State-specific initialization
    switch (newState) {
        case STATE_IDLE:
            lcdLine1 = "J-MAILBOX VPS";
            lcdLine2 = "Press button";
            lcdNeedsUpdate = true;
            relaxServos();
            updateInstruction("Ready - VPS Mode");
            break;
            
        case STATE_SCANNING:
            lcdLine1 = "SCAN RESI";
            lcdLine2 = "Waiting barcode...";
            lcdNeedsUpdate = true;
            updateInstruction("Ready to scan");
            beepPattern(1);
            break;
            
        case STATE_SENDING_SCAN_TO_VPS:
            lcdLine1 = "SENDING TO VPS";
            lcdLine2 = scannedResi.substring(0, 16);
            lcdNeedsUpdate = true;
            updateInstruction("Sending to VPS...");
            break;
            
        case STATE_WAITING_VPS_RESPONSE:
            lcdLine1 = "WAITING VPS";
            lcdLine2 = "Response...";
            lcdNeedsUpdate = true;
            updateInstruction("Waiting VPS response");
            break;
            
        case STATE_MONITORING:
            lcdLine1 = "MONITORING";
            lcdLine2 = currentPackage.resi.substring(0, 16);
            lcdNeedsUpdate = true;
            updateInstruction("Monitoring package");
            break;
            
        case STATE_WAITING_MQTT_COMMAND:
            lcdLine1 = "WAITING COMMAND";
            lcdLine2 = "From VPS...";
            lcdNeedsUpdate = true;
            updateInstruction("Waiting MQTT command");
            break;
            
        case STATE_DOOR_OPENING:
            lcdLine1 = "OPENING DOOR";
            lcdLine2 = "";
            lcdNeedsUpdate = true;
            updateInstruction("Opening door...");
            break;
            
        case STATE_WAITING_PACKAGE:
            lcdLine1 = "PLACE PACKAGE";
            lcdLine2 = "Insert now...";
            lcdNeedsUpdate = true;
            updateInstruction("Place package inside");
            break;
            
        case STATE_DOOR_CLOSING:
            lcdLine1 = "CLOSING DOOR";
            lcdLine2 = "";
            lcdNeedsUpdate = true;
            updateInstruction("Closing door...");
            break;
            
        case STATE_PAYMENT_DISPENSING:
            lcdLine1 = "TAKE MONEY";
            lcdLine2 = "Payment ready";
            lcdNeedsUpdate = true;
            updateInstruction("Dispensing money...");
            break;
            
        case STATE_COMPLETING:
            lcdLine1 = "COMPLETED";
            lcdLine2 = "Success!";
            lcdNeedsUpdate = true;
            updateInstruction("Delivery complete!");
            break;
            
        case STATE_ERROR:
            lcdLine1 = "ERROR";
            lcdLine2 = lastError.substring(0, 16);
            lcdNeedsUpdate = true;
            beepPattern(3);
            break;
            
        case STATE_WAITING_MANUAL_INPUT:
            lcdLine1 = "MANUAL INPUT";
            lcdLine2 = "From Dashboard";
            lcdNeedsUpdate = true;
            updateInstruction("Waiting manual input");
            beepPattern(2);
            break;
    }
}

void handleStateMachine(unsigned long currentTime) {
    static unsigned long lastStateAction = 0;
    
    if (currentTime - lastStateAction < 100) return;
    lastStateAction = currentTime;
    
    switch (currentState) {
        case STATE_SENDING_SCAN_TO_VPS:
            sendScanToVPS();
            break;
            
        case STATE_DOOR_OPENING:
            handleDoorOpening();
            break;
            
        case STATE_WAITING_PACKAGE:
            handleWaitingPackage(currentTime);
            break;
            
        case STATE_DOOR_CLOSING:
            handleDoorClosing();
            break;
            
        case STATE_PAYMENT_DISPENSING:
            handlePaymentDispensing();
            break;
            
        case STATE_COMPLETING:
            handleCompleting();
            break;
    }
}

void handleStateTimeouts(unsigned long currentTime) {
    switch (currentState) {
        case STATE_WAITING_VPS_RESPONSE:
            if (currentTime - stateStartTime > 30000) {
                updateInstruction("VPS timeout (30s)");
                beepPattern(2);
                changeState(STATE_WAITING_MANUAL_INPUT);
            }
            break;
            
        case STATE_WAITING_MQTT_COMMAND:
            if (currentTime - stateStartTime > 60000) {
                updateInstruction("Command timeout (60s)");
                beepPattern(3);
                changeState(STATE_IDLE);
            }
            break;
            
        case STATE_WAITING_MANUAL_INPUT:
            if (currentTime - stateStartTime > 120000) {
                updateInstruction("Manual input timeout (120s)");
                beepPattern(3);
                changeState(STATE_IDLE);
            }
            break;
    }
}

void handleDoorOpening() {
    static bool doorOpened = false;
    
    if (!doorOpened) {
        updateInstruction("Opening door...");
        beepPattern(1);
        
        // Attach and open door
        doorServo.attach(SERVO_DOOR_PIN);
        doorServo.write(90); // Open position
        delayNonBlocking(800);
        
        // Slightly close for stability
        doorServo.write(85);
        delayNonBlocking(200);
        doorServo.detach();
        
        // Update state
        doorOpen = true;
        doorOpenTime = millis();
        doorOpened = true;
        
        updateInstruction("Door open - place package");
        beepPattern(1);
        sendStatusUpdate("door_opened", "ready_for_package");
        
        changeState(STATE_WAITING_PACKAGE);
    }
}

void handleWaitingPackage(unsigned long currentTime) {
    // Calculate remaining time
    unsigned long elapsed = currentTime - doorOpenTime;
    unsigned long remaining = DOOR_TIMEOUT - elapsed;
    
    if (remaining > DOOR_TIMEOUT) return; // Handle overflow
    
    // Update LCD with countdown
    if (remaining > 0) {
        String line2 = "Time: " + String(remaining / 1000) + "s";
        if (lcdLine2 != line2) {
            lcdLine2 = line2;
            lcdNeedsUpdate = true;
        }
    }
    
    // Check for package
    if (distance < PACKAGE_DISTANCE_THRESHOLD && distance > 0) {
        if (!packageDetected) {
            packageDetected = true;
            updateInstruction("Package detected!");
            beepPattern(4);
            delayNonBlocking(1000);
            changeState(STATE_DOOR_CLOSING);
        }
    } else {
        packageDetected = false;
    }
    
    // Check timeout
    if (elapsed > DOOR_TIMEOUT) {
        updateInstruction("Door timeout - no package");
        beepPattern(2);
        changeState(STATE_DOOR_CLOSING);
    }
}

void handleDoorClosing() {
    static bool doorClosed = false;
    
    if (!doorClosed) {
        updateInstruction("Closing door...");
        beepPattern(1);
        
        // Attach and close door
        doorServo.attach(SERVO_DOOR_PIN);
        doorServo.write(0); // Closed position
        delayNonBlocking(800);
        
        // Slightly open for stability
        doorServo.write(5);
        delayNonBlocking(200);
        doorServo.detach();
        
        // Update state
        doorOpen = false;
        doorClosed = true;
        
        updateInstruction("Door closed");
        beepPattern(1);
        
        // Send status
        String details = packageDetected ? "package_detected" : "no_package";
        sendStatusUpdate("door_closed", details);
        
        // Determine next state
        if (packageDetected) {
            if (currentPackage.isCOD && currentPackage.amount > 0) {
                updateInstruction("Waiting COD payment...");
                delayNonBlocking(1000);
                changeState(STATE_WAITING_MQTT_COMMAND);
            } else {
                changeState(STATE_COMPLETING);
            }
        } else {
            updateInstruction("No package inserted");
            delayNonBlocking(2000);
            changeState(STATE_IDLE);
        }
    }
}

void handlePaymentDispensing() {
    static bool paymentDone = false;
    
    if (!paymentDone) {
        updateInstruction("Dispensing money...");
        beepPattern(1);
        
        // Determine which slot to use
        if (currentPackage.moneySlot == 1) {
            moneyServo1.attach(SERVO_M1_PIN);
            moneyServo1.write(0);
            delayNonBlocking(800);
            moneyServo1.write(90);
            delayNonBlocking(500);
            moneyServo1.detach();
        } else if (currentPackage.moneySlot == 2) {
            moneyServo2.attach(SERVO_M2_PIN);
            moneyServo2.write(180);
            delayNonBlocking(800);
            moneyServo2.write(90);
            delayNonBlocking(500);
            moneyServo2.detach();
        }
        
        updateInstruction("Please take money");
        beepPattern(4);
        paymentDone = true;
        
        // Send status
        sendStatusUpdate("money_dispensed", "slot_" + String(currentPackage.moneySlot));
        
        // Wait a moment then complete
        if (millis() - stateStartTime > 3000) {
            changeState(STATE_COMPLETING);
        }
    }
}

void handleCompleting() {
    static bool completed = false;
    
    if (!completed) {
        // Send delivery complete notification
        sendDeliveryComplete();
        updateInstruction("Delivery complete!");
        beepPattern(4);
        completed = true;
        
        // Send status update
        sendStatusUpdate("delivery_complete", "resi:" + currentPackage.resi);
        
        // Wait then reset
        if (millis() - stateStartTime > 2000) {
            resetSystem();
            changeState(STATE_IDLE);
        }
    }
}

void beepPattern(int pattern) {
    buzzerPattern = pattern;
    buzzerStartTime = millis();
    buzzerActive = true;
}

void handleBuzzer() {
    if (!buzzerActive) return;
    
    unsigned long elapsed = millis() - buzzerStartTime;
    
    switch (buzzerPattern) {
        case 1: // Short beep
            if (elapsed < 200) {
                tone(BUZZER_PIN, 1000);
            } else {
                buzzerActive = false;
                noTone(BUZZER_PIN);
            }
            break;
            
        case 2: // Double beep
            if (elapsed < 200) {
                tone(BUZZER_PIN, 800);
            } else if (elapsed < 400) {
                noTone(BUZZER_PIN);
            } else if (elapsed < 600) {
                tone(BUZZER_PIN, 800);
            } else {
                buzzerActive = false;
                noTone(BUZZER_PIN);
            }
            break;
            
        case 3: // Triple beep (error)
            for (int i = 0; i < 3; i++) {
                if (elapsed < (i * 200 + 150)) {
                    tone(BUZZER_PIN, 600);
                } else if (elapsed < (i * 200 + 300)) {
                    noTone(BUZZER_PIN);
                }
            }
            if (elapsed > 900) {
                buzzerActive = false;
                noTone(BUZZER_PIN);
            }
            break;
            
        case 4: // Success pattern
            if (elapsed < 200) {
                tone(BUZZER_PIN, 1000);
            } else if (elapsed < 400) {
                noTone(BUZZER_PIN);
            } else if (elapsed < 600) {
                tone(BUZZER_PIN, 1200);
            } else if (elapsed < 800) {
                noTone(BUZZER_PIN);
            } else if (elapsed < 1000) {
                tone(BUZZER_PIN, 1400);
            } else {
                buzzerActive = false;
                noTone(BUZZER_PIN);
            }
            break;
    }
}

void readUltrasonic() {
    // Send trigger pulse
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    
    // Measure echo
    long duration = pulseIn(ECHO_PIN, HIGH, PULSEIN_TIMEOUT);
    
    if (duration == 0) {
        distance = 999; // No echo received
    } else {
        distance = duration * 0.034 / 2; // Convert to cm
        if (distance > 300) distance = 999; // Cap at 300cm
    }
}

void updateLCD(String line1, String line2, bool force) {
    if (force || line1 != lcdLine1 || line2 != lcdLine2) {
        lcdLine1 = line1;
        lcdLine2 = line2;
        lcdNeedsUpdate = true;
    }
}

void updateLCDPeriodic() {
    if (lcdNeedsUpdate) {
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print(lcdLine1.substring(0, 16));
        lcd.setCursor(0, 1);
        lcd.print(lcdLine2.substring(0, 16));
        lcdNeedsUpdate = false;
    }
}

void updateInstruction(String message) {
    instructionMsg = message;
    Serial.println("[INSTR] " + message);
    lastActivityTime = millis();
}

void checkButton() {
    static unsigned long lastPress = 0;
    static bool buttonPressed = false;
    
    if (digitalRead(BUTTON_PIN) == LOW) {
        if (!buttonPressed && millis() - lastPress > 1000) {
            buttonPressed = true;
            lastPress = millis();
            lastActivityTime = millis();
            
            Serial.println("[BUTTON] Pressed");
            
            switch (currentState) {
                case STATE_IDLE:
                    updateInstruction("Starting delivery process");
                    beepPattern(1);
                    changeState(STATE_SCANNING);
                    break;
                    
                case STATE_ERROR:
                    updateInstruction("Resetting system...");
                    resetSystem();
                    changeState(STATE_IDLE);
                    break;
                    
                case STATE_WAITING_MANUAL_INPUT:
                    updateInstruction("Cancelling manual input");
                    changeState(STATE_IDLE);
                    break;
                    
                default:
                    Serial.println("[BUTTON] Ignored in current state");
                    break;
            }
        }
    } else {
        buttonPressed = false;
    }
}

void scanBarcode() {
    if (SerialScan.available()) {
        String barcode = SerialScan.readStringUntil('\n');
        barcode.trim();
        
        if (barcode.length() > 5) {
            scannedResi = barcode;
            lastActivityTime = millis();
            
            Serial.println("[SCANNER] Scanned: " + scannedResi);
            updateInstruction("Scanned: " + scannedResi);
            beepPattern(1);
            
            // Validate resi format
            if (!validateResiFormat(scannedResi)) {
                updateInstruction("Invalid resi format");
                beepPattern(3);
                changeState(STATE_IDLE);
                return;
            }
            
            // Store in current package
            currentPackage.resi = scannedResi;
            currentPackage.timestamp = millis();
            
            changeState(STATE_SENDING_SCAN_TO_VPS);
        }
    }
}

bool validateResiFormat(String resi) {
    if (resi.length() < 5 || resi.length() > 20) {
        return false;
    }
    
    for (unsigned int i = 0; i < resi.length(); i++) {
        char c = resi.charAt(i);
        if (!isalnum(c) && c != '-' && c != '.' && c != '/' && c != '_') {
            return false;
        }
    }
    
    return true;
}

void setupWiFi() {
    updateInstruction("Connecting to WiFi...");
    Serial.print("Connecting to ");
    Serial.println(WIFI_SSID);
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
        delay(500);
        Serial.print(".");
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        updateInstruction("WiFi: " + WiFi.localIP().toString());
        Serial.println("\nWiFi connected!");
        Serial.println("IP address: " + WiFi.localIP().toString());
    } else {
        updateInstruction("WiFi connection failed");
        Serial.println("\nWiFi connection failed!");
    }
}

void setupMQTT() {
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setKeepAlive(60);
    mqttClient.setBufferSize(2048);
}

void handleNetwork() {
    // Check WiFi
    if (WiFi.status() != WL_CONNECTED) {
        static unsigned long lastWiFiCheck = 0;
        if (millis() - lastWiFiCheck > 10000) {
            lastWiFiCheck = millis();
            updateInstruction("WiFi disconnected");
            Serial.println("[WIFI] Reconnecting...");
            setupWiFi();
        }
        return;
    }
    
    // Handle MQTT
    if (!mqttClient.connected()) {
        unsigned long currentTime = millis();
        if (currentTime - lastMqttReconnectAttempt > MQTT_RECONNECT_INTERVAL) {
            lastMqttReconnectAttempt = currentTime;
            reconnectMQTT();
        }
    } else {
        mqttClient.loop();
    }
}

void reconnectMQTT() {
    String clientId = "JMailbox-" + String(DEVICE_ID) + "-" + String(millis());
    
    Serial.println("[MQTT] Attempting connection...");
    
    if (mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
        mqttConnected = true;
        
        // Subscribe to command topic
        mqttClient.subscribe(TOPIC_COMMAND_OUT);
        
        updateInstruction("MQTT connected");
        beepPattern(1);
        
        Serial.println("[MQTT] Connected and subscribed");
        
        // Send initial status
        sendSystemStatus();
        
    } else {
        mqttConnected = false;
        updateInstruction("MQTT failed: " + String(mqttClient.state()));
        Serial.println("[MQTT] Connection failed, state: " + String(mqttClient.state()));
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    String message;
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    
    String topicStr = String(topic);
    Serial.println("[MQTT] Received: " + topicStr + " -> " + message);
    
    // Parse JSON
    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        Serial.println("JSON parse error: " + String(error.c_str()));
        return;
    }
    
    lastActivityTime = millis();
    
    // Handle based on topic
    if (topicStr == TOPIC_COMMAND_OUT) {
        handleVPSCommand(doc);
    }
}

void handleVPSCommand(JsonDocument& doc) {
    String resi = doc["resi"] | "";
    String command = doc["command"] | "";
    String reason = doc["reason"] | "";
    String msgId = doc["message_id"] | doc["mqtt_message_id"] | "";
    
    Serial.println("[VPS] Command: " + command + " for resi: " + resi);
    
    // Check if command is for current package
    if (resi == currentPackage.resi || resi == scannedResi || resi == "") {
        pendingCommand = command;
        pendingResi = resi;
        pendingMessageId = msgId;
        lastCommandTime = millis();
        
        updateInstruction("VPS: " + command);
        
        // Execute command
        executeMQTTCommand(command, resi, reason);
        
    } else {
        Serial.println("[VPS] Command for different resi: " + resi);
    }
}

void executeMQTTCommand(String command, String resi, String reason) {
    if (command == "buka_slot_uang") {
        updateInstruction("Opening money slot...");
        beepPattern(1);
        openMoneySlot();
        sendCommandResponse(command, "executed", "Money slot opened");
        
    } else if (command == "tutup_slot_uang") {
        updateInstruction("Closing money slot...");
        beepPattern(1);
        closeMoneySlot();
        sendCommandResponse(command, "executed", "Money slot closed");
        
    } else if (command == "buka_pintu") {
        changeState(STATE_DOOR_OPENING);
        sendCommandResponse(command, "executed", "Door opening started");
        
    } else if (command == "tutup_pintu") {
        if (currentState == STATE_WAITING_PACKAGE) {
            changeState(STATE_DOOR_CLOSING);
            sendCommandResponse(command, "executed", "Door closing started");
        } else {
            sendCommandResponse(command, "rejected", "Not in waiting state");
        }
        
    } else if (command == "buzzer_on") {
        activateBuzzer();
        sendCommandResponse(command, "executed", "Buzzer activated");
        
    } else if (command == "buzzer_off") {
        deactivateBuzzer();
        sendCommandResponse(command, "executed", "Buzzer deactivated");
        
    } else if (command == "verify_cod_slot") {
        updateInstruction("Verifying COD slot...");
        sendSensorData();
        sendCommandResponse(command, "executed", "Sensor data sent");
        
    } else if (command == "reset_system") {
        updateInstruction("Resetting by VPS command...");
        resetSystem();
        changeState(STATE_IDLE);
        sendCommandResponse(command, "executed", "System reset");
        
    } else if (command == "nyalakan_led") {
        updateInstruction("LED on");
        // Add LED control here if available
        sendCommandResponse(command, "executed", "LED activated");
        
    } else if (command == "matikan_led") {
        updateInstruction("LED off");
        // Add LED control here if available
        sendCommandResponse(command, "executed", "LED deactivated");
        
    } else {
        updateInstruction("Unknown command: " + command);
        sendCommandResponse(command, "rejected", "Unknown command");
    }
}

void sendCommandResponse(String command, String status, String message) {
    if (!mqttConnected) return;
    
    DynamicJsonDocument doc(256);
    doc["resi"] = (currentPackage.resi.length() > 0) ? currentPackage.resi : pendingResi;
    doc["command"] = command;
    doc["status"] = status;
    doc["message"] = message;
    doc["device_id"] = DEVICE_ID;
    if (pendingMessageId.length() > 0) doc["message_id"] = pendingMessageId;
    doc["timestamp"] = millis();
    
    String json;
    serializeJson(doc, json);
    
    String responseTopic = TOPIC_COMMAND_OUT + String("/response");
    if (mqttClient.publish(responseTopic.c_str(), json.c_str())) {
        Serial.println("[VPS] Command response sent: " + status);
    }
}

void openMoneySlot(int slot) {
    // Default to slot 1 if not specified
    if (slot == 0) slot = 1;
    
    if (slot == 1) {
        moneyServo1.attach(SERVO_M1_PIN);
        moneyServo1.write(0); // Open position
        delayNonBlocking(800);
        moneyServo1.detach();
    } else if (slot == 2) {
        moneyServo2.attach(SERVO_M2_PIN);
        moneyServo2.write(180); // Open position
        delayNonBlocking(800);
        moneyServo2.detach();
    }
    
    updateInstruction("Money slot " + String(slot) + " open");
}

void closeMoneySlot(int slot) {
    // Default to slot 1 if not specified
    if (slot == 0) slot = 1;
    
    if (slot == 1) {
        moneyServo1.attach(SERVO_M1_PIN);
        moneyServo1.write(90); // Closed position
        delayNonBlocking(800);
        moneyServo1.detach();
    } else if (slot == 2) {
        moneyServo2.attach(SERVO_M2_PIN);
        moneyServo2.write(90); // Closed position
        delayNonBlocking(800);
        moneyServo2.detach();
    }
    
    updateInstruction("Money slot " + String(slot) + " closed");
}

void openDoor() {
    doorServo.attach(SERVO_DOOR_PIN);
    doorServo.write(90); // Open position
    delayNonBlocking(800);
    doorServo.detach();
    doorOpen = true;
}

void closeDoor() {
    doorServo.attach(SERVO_DOOR_PIN);
    doorServo.write(0); // Closed position
    delayNonBlocking(800);
    doorServo.detach();
    doorOpen = false;
}

void activateBuzzer() {
    beepPattern(3);
}

void deactivateBuzzer() {
    buzzerActive = false;
    noTone(BUZZER_PIN);
}

void sendScanToVPS() {
    if (!mqttConnected) {
        updateInstruction("MQTT offline - use manual");
        beepPattern(2);
        changeState(STATE_WAITING_MANUAL_INPUT);
        return;
    }
    
    DynamicJsonDocument doc(256);
    doc["type"] = "resi_scanned";
    doc["resi"] = scannedResi;
    doc["device_id"] = DEVICE_ID;
    if (pendingMessageId.length() > 0) doc["message_id"] = pendingMessageId;
    doc["timestamp"] = millis();
    doc["status"] = "waiting_validation";
    
    String json;
    serializeJson(doc, json);
    
    if (mqttClient.publish(TOPIC_STATUS_OUT, json.c_str())) {
        Serial.println("[VPS] Scan sent: " + scannedResi);
        updateInstruction("Scan sent to VPS");
        
        changeState(STATE_WAITING_VPS_RESPONSE);
        
    } else {
        updateInstruction("Failed to send scan");
        beepPattern(3);
        changeState(STATE_WAITING_MANUAL_INPUT);
    }
}

void sendSensorData() {
    if (!mqttConnected) return;
    
    // Read button state
    int buttonState = digitalRead(BUTTON_PIN) == LOW ? 1 : 0;
    
    // Prepare sensor data
    DynamicJsonDocument doc(256);
    doc["resi"] = (currentPackage.resi.length() > 0) ? currentPackage.resi : pendingResi;
    doc["jarak"] = distance;
    doc["durasi"] = 0.0; // Not measured in this version
    doc["slot"] = 0; // Money slot status
    doc["tombol"] = buttonState;
    doc["device_id"] = DEVICE_ID;
    if (pendingMessageId.length() > 0) doc["message_id"] = pendingMessageId;
    doc["timestamp"] = millis();
    doc["door_open"] = doorOpen;
    doc["package_detected"] = packageDetected;
    
    String json;
    serializeJson(doc, json);
    
    if (mqttClient.publish(TOPIC_SENSOR_IN, json.c_str())) {
        Serial.println("[SENSOR] Data sent: " + String(distance) + "cm, button=" + buttonState);
    } else {
        Serial.println("[SENSOR] Failed to send data");
    }
}

void sendSystemStatus() {
    if (!mqttConnected) return;
    
    DynamicJsonDocument doc(256);
    doc["device_id"] = DEVICE_ID;
    doc["state"] = currentState;
    doc["state_name"] = String(currentState); // For debugging
    doc["wifi"] = WiFi.status() == WL_CONNECTED;
    doc["mqtt"] = mqttConnected;
    doc["door"] = doorOpen;
    doc["package"] = packageDetected;
    doc["distance"] = distance;
    doc["resi"] = (currentPackage.resi.length() > 0) ? currentPackage.resi : pendingResi;
    doc["scanned_resi"] = scannedResi;
    doc["timestamp"] = millis();
    doc["firmware"] = FIRMWARE_VERSION;
    doc["uptime"] = millis() / 1000; // Seconds
    
    String json;
    serializeJson(doc, json);
    
    if (mqttClient.publish(TOPIC_STATUS_OUT, json.c_str())) {
        Serial.println("[STATUS] System status sent");
    }
}

void sendStatusUpdate(String event, String details) {
    if (!mqttConnected) return;
    
    DynamicJsonDocument doc(256);
    doc["event"] = event;
    doc["device_id"] = DEVICE_ID;
    doc["resi"] = (currentPackage.resi.length() > 0) ? currentPackage.resi : pendingResi;
    doc["details"] = details;
    doc["timestamp"] = millis();
    
    String json;
    serializeJson(doc, json);
    
    if (mqttClient.publish(TOPIC_STATUS_OUT, json.c_str())) {
        Serial.println("[STATUS] Event: " + event + " - " + details);
    }
}

void sendDeliveryComplete() {
    if (!mqttConnected) return;
    
    DynamicJsonDocument doc(256);
    doc["event"] = "delivery_complete";
    doc["device_id"] = DEVICE_ID;
    doc["resi"] = (currentPackage.resi.length() > 0) ? currentPackage.resi : pendingResi;
    doc["customer"] = currentPackage.customer;
    doc["amount"] = currentPackage.amount;
    doc["is_cod"] = currentPackage.isCOD;
    doc["timestamp"] = millis();
    
    String json;
    serializeJson(doc, json);
    
    if (mqttClient.publish(TOPIC_STATUS_OUT, json.c_str())) {
        Serial.println("[DELIVERY] Complete notification sent");
    }
}

void resetSystem() {
    currentPackage.reset();
    scannedResi = "";
    packageDetected = false;
    pendingCommand = "";
    pendingResi = "";
    doorOpen = false;
    
    // Detach all servos
    relaxServos();
    
    updateInstruction("System reset to idle");
    Serial.println("[SYSTEM] Reset complete");
}

void relaxServos() {
    if (doorServo.attached()) doorServo.detach();
    if (moneyServo1.attached()) moneyServo1.detach();
    if (moneyServo2.attached()) moneyServo2.detach();
}

void delayNonBlocking(unsigned long ms) {
    unsigned long start = millis();
    while (millis() - start < ms) {
        handleNetwork();
        handleBuzzer();
        delay(1);
    }
}