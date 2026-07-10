import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

MQTT_BROKER = os.environ.get("MQTT_BROKER_IP", "YOUR_MQTT_SERVER_IP")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USERNAME = os.environ.get("MQTT_USER", "username")
MQTT_PASSWORD = os.environ.get("MQTT_PASS", "password")
