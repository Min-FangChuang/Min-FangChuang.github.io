#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

#include <IRremoteESP8266.h>
#include <IRsend.h>
#include <ir_Daikin.h>

WebServer server(80);
Servo myServo;

// ===== 腳位 =====
const int servoPin = 13;
const int irPin = 4;

// ===== 冷氣 =====
IRDaikin152 ac(irPin);

// ===== 定時設定 =====
String onTime = "";
String offTime = "";
String acOnTime = "";
String acOffTime = "";
String lastCompared = "";

int startHour = 0;
int startMinute = 0;
unsigned long startMillis = 0;
bool timeSynced = false;

unsigned long lastCheck = 0;
const unsigned long interval = 30000;

// ===== 燈光動作 =====
void lightOn() {
  myServo.write(30);
  delay(800);
  myServo.write(90);
}

void lightOff() {
  myServo.write(150);
  delay(800);
  myServo.write(90);
}

// ===== 冷氣動作 =====
void acOn25() {
  ac.on();
  ac.setMode(kDaikinCool);
  ac.setTemp(25);
  ac.setFan(kDaikinFanAuto);
  ac.setQuiet(true);
  ac.setComfort(true);
  ac.send();

  Serial.println("❄️ 冷氣開啟 25°C");
}

void acOff() {
  ac.off();
  ac.send();

  Serial.println("🛑 冷氣關閉");
}

// ===== HTML =====
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ESP 燈光與冷氣控制</title>
<style>
body {
  font-family: Arial;
  padding: 20px;
}
button {
  font-size: 20px;
  padding: 12px;
  margin: 6px;
}
input {
  font-size: 18px;
}
.box {
  background: #eeeeee;
  padding: 12px;
  margin: 12px 0;
}
</style>
</head>
<body>

<h2>ESP 燈光與冷氣控制</h2>

<div class="box">
<form action="/sync" method="POST">
  目前時間（HH:MM）：
  <input name="nowtime" type="time" required>
  <input type="submit" value="同步現在時間">
</form>
</div>

<div class="box">
<form action="/set" method="POST">

  <h3>燈光定時</h3>
  開燈時間：
  <input name="ontime" type="time"><br><br>

  關燈時間：
  <input name="offtime" type="time"><br><br>

  <h3>冷氣定時</h3>
  冷氣開啟時間：
  <input name="acontime" type="time"><br><br>

  冷氣關閉時間：
  <input name="acofftime" type="time"><br><br>

  <input type="submit" value="設定定時">
</form>
</div>

<h3>燈光控制</h3>
<a href="/on"><button>💡 手動開燈</button></a>
<a href="/off"><button>🌙 手動關燈</button></a>

<h3>冷氣控制</h3>
<a href="/ac_on"><button>❄️ 冷氣 25°C</button></a>
<a href="/ac_off"><button>🛑 關閉冷氣</button></a>

<div class="box">
<p>
目前時間：%NOW%<br><br>

開燈時間：%ONTIME%<br>
關燈時間：%OFFTIME%<br><br>

冷氣開啟時間：%ACONTIME%<br>
冷氣關閉時間：%ACOFFTIME%
</p>
</div>

</body>
</html>
)rawliteral";

// ===== 推算現在時間 =====
String getCurrentTime() {
  if (!timeSynced) return "未對時";

  unsigned long elapsed = millis() - startMillis;
  int totalMinutes = startHour * 60 + startMinute + (elapsed / 60000);

  int hour = (totalMinutes / 60) % 24;
  int minute = totalMinutes % 60;

  char buf[6];
  snprintf(buf, sizeof(buf), "%02d:%02d", hour, minute);

  return String(buf);
}

// ===== 定時控制 =====
void checkSchedule() {
  if (!timeSynced) return;

  String now = getCurrentTime();

  if (now == lastCompared) return;
  lastCompared = now;

  if (onTime != "" && now == onTime) {
    Serial.println("⏰ 定時開燈：" + now);
    lightOn();
  }

  if (offTime != "" && now == offTime) {
    Serial.println("⏰ 定時關燈：" + now);
    lightOff();
  }

  if (acOnTime != "" && now == acOnTime) {
    Serial.println("❄️ 定時開冷氣：" + now);
    acOn25();
  }

  if (acOffTime != "" && now == acOffTime) {
    Serial.println("🛑 定時關冷氣：" + now);
    acOff();
  }
}

void setup() {
  Serial.begin(115200);

  myServo.attach(servoPin);
  myServo.write(90);

  ac.begin();

  WiFi.softAP("ESP_Light_AC", "12345678");

  Serial.println("AP模式開啟");
  Serial.println("SSID: ESP_Light_AC");
  Serial.println("Password: 12345678");
  Serial.print("IP: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", []() {
    String html = index_html;

    html.replace("%NOW%", getCurrentTime());
    html.replace("%ONTIME%", onTime == "" ? "未設定" : onTime);
    html.replace("%OFFTIME%", offTime == "" ? "未設定" : offTime);
    html.replace("%ACONTIME%", acOnTime == "" ? "未設定" : acOnTime);
    html.replace("%ACOFFTIME%", acOffTime == "" ? "未設定" : acOffTime);

    server.send(200, "text/html; charset=utf-8", html);
  });

  server.on("/on", []() {
    lightOn();
    Serial.println("💡 手動開燈");

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.on("/off", []() {
    lightOff();
    Serial.println("🌙 手動關燈");

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.on("/ac_on", []() {
    acOn25();

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.on("/ac_off", []() {
    acOff();

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.on("/set", HTTP_POST, []() {
    if (!timeSynced) {
      server.send(400, "text/plain; charset=utf-8", "請先同步現在時間");
      return;
    }

    onTime = server.arg("ontime");
    offTime = server.arg("offtime");
    acOnTime = server.arg("acontime");
    acOffTime = server.arg("acofftime");

    Serial.println("設定燈光：開 " + onTime + "，關 " + offTime);
    Serial.println("設定冷氣：開 " + acOnTime + "，關 " + acOffTime);

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.on("/sync", HTTP_POST, []() {
    String now = server.arg("nowtime");

    int split = now.indexOf(':');

    if (split == -1 || now.length() != 5) {
      server.send(400, "text/plain; charset=utf-8", "時間格式錯誤，請使用 HH:MM 格式");
      return;
    }

    startHour = now.substring(0, split).toInt();
    startMinute = now.substring(split + 1).toInt();

    startMillis = millis() - (millis() % 60000);
    timeSynced = true;
    lastCompared = "";

    Serial.println("✅ 手動對時成功：" + now);

    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.begin();
}

void loop() {
  server.handleClient();

  if (millis() - lastCheck >= interval) {
    lastCheck = millis();
    checkSchedule();
  }
}