import time
import wifi
import socketpool
import microcontroller
import adafruit_requests
import json
import ssl
import os

# 🌐 Wi-Fi Access Point Settings
SSID_AP = "PicoWeatherSetup"
PASSWORD_AP = "setup1234"
CONFIG_FILE = "wifi_config.txt"

# 🌦️ OpenWeather API
API_KEY = "70f942c991a713626618739be248dc4f"  # Replace with your API Key
CITY = "New York"
API_URL = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"

# 📡 Initialize Networking
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

def save_wifi_credentials(ssid, password):
    with open(CONFIG_FILE, "w") as f:
        f.write(json.dumps({"ssid": ssid, "password": password}))

def load_wifi_credentials():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.loads(f.read())
    except (OSError, ValueError):
        return None

def start_access_point():
    print("⚠️ No stored Wi-Fi credentials. Starting AP mode...")
    
    wifi.radio.stop_station()
    
    try:
        wifi.radio.start_ap(SSID_AP, PASSWORD_AP)
    except RuntimeError:
        print("❌ AP Mode could not start. Restarting...")
        microcontroller.reset()
    
    print("📶 AP Mode Enabled: Connect to 'PicoWeatherSetup'")
    print("🔗 Open http://192.168.4.1/setup in a browser")
    
    server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    server.bind(("0.0.0.0", 80))
    server.listen(2)
    
    while True:
        try:
            conn, addr = server.accept()
            request = conn.recv(1024).decode("utf-8")
            print(f"📥 Request: {request}")
            
            if "GET /setup" in request:
                response = """
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
    <title>Wi-Fi Setup</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h2 { color: #333; }
        form { display: inline-block; text-align: left; background: #f9f9f9; padding: 20px; border-radius: 10px; }
        input { display: block; margin-bottom: 10px; padding: 8px; width: 100%; }
        input[type="submit"] { background: #4CAF50; color: white; border: none; cursor: pointer; }
        input[type="submit"]:hover { background: #45a049; }
    </style>
</head>
<body>
    <h2>Connect to Wi-Fi</h2>
    <form action="/connect" method="post">
        <label for="ssid">SSID:</label>
        <input id="ssid" name="ssid" required>
        <label for="password">Password:</label>
        <input id="password" name="password" type="password" required>
        <input type="submit" value="Connect">
    </form>
</body>
</html>
"""
                conn.send(response.encode())
            elif "POST /connect" in request:
                body = request.split("\r\n\r\n")[-1]
                params = {kv.split("=")[0]: kv.split("=")[1] for kv in body.split("&") if "=" in kv}
                
                ssid = params.get("ssid", "")
                password = params.get("password", "")
                
                if ssid and password:
                    save_wifi_credentials(ssid, password)
                    
                    wifi.radio.stop_ap()
                    wifi.radio.connect(ssid, password)
                    
                    if wifi.radio.connected:
                        response = "HTTP/1.1 200 OK\n\n✅ Connected! Restarting..."
                        conn.send(response.encode())
                        conn.close()
                        print("✅ Wi-Fi Connected. Restarting...")
                        time.sleep(2)
                        microcontroller.reset()
                    else:
                        conn.send("HTTP/1.1 400 Bad Request\n\n❌ Failed to connect".encode())
                else:
                    conn.send("HTTP/1.1 400 Bad Request\n\n❌ Invalid Data".encode())
            
            conn.close()
        except Exception as e:
            print(f"❌ Server Error: {e}")

def get_weather():
    try:
        response = requests.get(API_URL)
        data = response.json()
        temp = data["main"]["temp"]
        weather = data["weather"][0]["description"]
        print(f"🌡️ {CITY}: {temp}°C, {weather}")
    except Exception as e:
        print(f"❌ Weather API Error: {e}")

# 🚀 Main Execution
credentials = load_wifi_credentials()
if credentials:
    try:
        wifi.radio.connect(credentials["ssid"], credentials["password"])
        print(f"✅ Connected! IP Address: {wifi.radio.ipv4_address}")
        while True:
            get_weather()
            time.sleep(600)  # Update every 10 min
    except Exception as e:
        print(f"❌ Wi-Fi Connection Failed: {e}")
        start_access_point()
else:
    start_access_point()
