/*
 * ESP32 Light Control for NAO Robot
 * 
 * This code runs on ESP32 to control an LED connected to GPIO 4.
 * It connects to WiFi and runs a simple web server that responds to
 * /on and /off endpoints to control the LED.
 * 
 * WiFi: ll_cst_labs
 * Password: C$tlaBS+10-2023
 * Fixed IP: 172.18.16.50
 * LED Pin: GPIO 4
 */

#include <WiFi.h>
#include <WebServer.h>

// WiFi credentials
const char* ssid = "ll_cst_labs";
const char* password = "C$tlaBS+10-2023";

// Fixed IP configuration
IPAddress local_IP(172, 18, 16, 50);
IPAddress gateway(172, 18, 16, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

// LED Pin
const int LED_PIN = 4;

// Web server on port 80
WebServer server(80);

// LED state
bool ledState = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println();
  Serial.println("================================");
  Serial.println("ESP32 Light Control for NAO Robot");
  Serial.println("================================");
  
  // Configure LED pin as output
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.println("LED pin configured: GPIO 4");
  
  // Configure static IP
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS)) {
    Serial.println("Failed to configure static IP");
  }
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi connection failed!");
    Serial.println("Restarting...");
    delay(3000);
    ESP.restart();
  }
  
  // Setup web server routes
  server.on("/", handleRoot);
  server.on("/on", handleLightOn);
  server.on("/off", handleLightOff);
  server.on("/status", handleStatus);
  server.on("/toggle", handleToggle);
  server.onNotFound(handleNotFound);
  
  // Start server
  server.begin();
  Serial.println("HTTP server started on port 80");
  Serial.println();
  Serial.println("Available endpoints:");
  Serial.println("  /       - Status page");
  Serial.println("  /on     - Turn LED ON");
  Serial.println("  /off    - Turn LED OFF");
  Serial.println("  /toggle - Toggle LED");
  Serial.println("  /status - Get JSON status");
  Serial.println();
  Serial.println("Ready for NAO robot commands!");
  Serial.println("================================");
}

void loop() {
  server.handleClient();
  
  // Reconnect WiFi if disconnected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    WiFi.begin(ssid, password);
    delay(5000);
  }
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head>";
  html += "<title>ESP32 Light Control</title>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
  html += "<style>";
  html += "body { font-family: Arial; text-align: center; background: #1a1a2e; color: white; padding: 20px; }";
  html += ".btn { padding: 20px 40px; font-size: 20px; margin: 10px; border: none; border-radius: 10px; cursor: pointer; }";
  html += ".on { background: #ffc107; color: black; }";
  html += ".off { background: #444; color: white; }";
  html += ".status { font-size: 48px; margin: 30px; }";
  html += "</style></head><body>";
  html += "<h1>ESP32 Light Control</h1>";
  html += "<h2>NAO Robot Integration</h2>";
  html += "<div class='status'>";
  html += ledState ? "💡 LIGHT ON" : "🌙 LIGHT OFF";
  html += "</div>";
  html += "<div>";
  html += "<a href='/on'><button class='btn on'>Turn ON</button></a>";
  html += "<a href='/off'><button class='btn off'>Turn OFF</button></a>";
  html += "</div>";
  html += "<p>IP: " + WiFi.localIP().toString() + "</p>";
  html += "<p>LED Pin: GPIO 4</p>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
}

void handleLightOn() {
  digitalWrite(LED_PIN, HIGH);
  ledState = true;
  Serial.println("LED turned ON");
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "Light ON");
}

void handleLightOff() {
  digitalWrite(LED_PIN, LOW);
  ledState = false;
  Serial.println("LED turned OFF");
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "Light OFF");
}

void handleToggle() {
  ledState = !ledState;
  digitalWrite(LED_PIN, ledState ? HIGH : LOW);
  Serial.println(ledState ? "LED toggled ON" : "LED toggled OFF");
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", ledState ? "Light ON" : "Light OFF");
}

void handleStatus() {
  String json = "{";
  json += "\"light_on\":" + String(ledState ? "true" : "false") + ",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"pin\":4,";
  json += "\"rssi\":" + String(WiFi.RSSI());
  json += "}";
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(404, "text/plain", "Not Found");
}
