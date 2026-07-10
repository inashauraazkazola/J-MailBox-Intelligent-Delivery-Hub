# mqtt_client_ssl.py
import paho.mqtt.client as mqtt
import ssl
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from database import DatabaseManager
from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

logger = logging.getLogger(__name__)

class MQTTClientSSL:
    """Klien MQTT dengan SSL/TLS support untuk komunikasi real-time dengan ESP32"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.client = None
        self.connected = False
        self.subscriptions = {}
        self.message_handlers = {}
        
        # Konfigurasi dari database
        self.broker = self.db_manager.get_setting('mqtt_broker', MQTT_BROKER)
        self.port = int(self.db_manager.get_setting('mqtt_port_ssl', MQTT_PORT))
        self.username = self.db_manager.get_setting('mqtt_username', MQTT_USERNAME)
        self.password = self.db_manager.get_setting('mqtt_password', MQTT_PASSWORD)
        
        # SSL Configuration
        self.use_ssl = self.db_manager.get_setting('mqtt_use_ssl', True)
        self.ca_cert = self.db_manager.get_setting('mqtt_ca_cert', 'certs/ca.crt')
        self.client_cert = self.db_manager.get_setting('mqtt_client_cert', 'certs/client.crt')
        self.client_key = self.db_manager.get_setting('mqtt_client_key', 'certs/client.key')
        
        # Topics
        self.topic_sensor_in = "alat/sensor"
        self.topic_command_out = "alat/perintah"
        self.topic_status_out = "alat/status"
        self.topic_package_update = "jmailbox/packages/update"
        self.topic_security_update = "jmailbox/security/update"
        
        self.init_client()
    
    def init_client(self):
        """Inisialisasi klien MQTT dengan SSL"""
        try:
            client_id = f"jmailbox_ssl_{int(time.time())}"
            self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            self.client.username_pw_set(self.username, self.password)
            
            # Configure SSL/TLS jika diaktifkan
            if self.use_ssl:
                self._configure_ssl()
            
            # Set callback functions
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_log = self._on_log
            
            # Set last will
            self.client.will_set(
                self.topic_status_out,
                json.dumps({
                    "status": "offline",
                    "service": "jmailbox_dashboard_ssl",
                    "timestamp": datetime.now().isoformat()
                }),
                qos=1,
                retain=True
            )
            
            # Connect to broker dengan SSL
            logger.info(f"Connecting to MQTT broker with SSL: {self.broker}:{self.port}")
            
            # Connect dengan timeout
            self.client.connect_async(self.broker, self.port, 60)
            
            # Start loop in background thread
            self.client.loop_start()
            
            # Wait for connection
            for i in range(15):
                if self.connected:
                    break
                time.sleep(0.5)
            
            if self.connected:
                logger.info("MQTT SSL client initialized successfully")
            else:
                logger.error("MQTT SSL client failed to connect")
                
        except Exception as e:
            logger.error(f"Failed to initialize MQTT SSL client: {e}")
            # Fallback to non-SSL jika SSL gagal
            self._fallback_to_non_ssl()
    
    def _configure_ssl(self):
        """Configure SSL/TLS settings"""
        try:
            # Set TLS version
            self.client.tls_set(
                ca_certs=self.ca_cert,
                certfile=self.client_cert,
                keyfile=self.client_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            
            # Disable insecure SSL options
            self.client.tls_insecure_set(False)
            logger.info("SSL/TLS configured successfully")
            
        except Exception as e:
            logger.error(f"SSL configuration failed: {e}")
            raise
    
    def _fallback_to_non_ssl(self):
        """Fallback ke koneksi non-SSL jika SSL gagal"""
        try:
            logger.warning("Falling back to non-SSL connection")
            self.use_ssl = False
            self.port = int(self.db_manager.get_setting('mqtt_port', 1883))
            
            # Reinitialize tanpa SSL
            self.client = mqtt.Client(client_id=f"jmailbox_nonssl_{int(time.time())}")
            self.client.username_pw_set(self.username, self.password)
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Non-SSL fallback also failed: {e}")
    
    def _on_log(self, client, userdata, level, buf):
        """Callback untuk logging MQTT"""
        if level == mqtt.MQTT_LOG_DEBUG:
            logger.debug(f"MQTT Debug: {buf}")
        elif level == mqtt.MQTT_LOG_INFO:
            logger.info(f"MQTT Info: {buf}")
        elif level == mqtt.MQTT_LOG_WARNING:
            logger.warning(f"MQTT Warning: {buf}")
        elif level == mqtt.MQTT_LOG_ERR:
            logger.error(f"MQTT Error: {buf}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback ketika terhubung ke broker"""
        if rc == 0:
            self.connected = True
            ssl_status = "with SSL" if self.use_ssl else "without SSL"
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port} {ssl_status}")
            
            # Subscribe to topics
            self._subscribe_all()
            
            # Publish connection status
            self.publish_status("online")
            
        else:
            self.connected = False
            error_messages = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorized"
            }
            error_msg = error_messages.get(rc, f"unknown error code: {rc}")
            logger.error(f"Connection failed: {error_msg}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
        
        # Try to reconnect after delay
        time.sleep(5)
        try:
            self.client.reconnect()
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Callback ketika menerima pesan"""
        try:
            logger.debug(f"MQTT message received on {msg.topic}")
            
            # Decode payload
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            
            # Save to database
            self.db_manager.save_mqtt_message(msg.topic, data, "incoming")
            
            # Handle by topic
            if msg.topic == self.topic_sensor_in:
                self._handle_sensor_data(data)
            elif msg.topic == self.topic_command_out:
                self._handle_command_response(data)
            
            # Call registered handlers
            if msg.topic in self.message_handlers:
                for handler in self.message_handlers[msg.topic]:
                    try:
                        handler(data)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
                        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from MQTT: {e}")
            logger.debug(f"Raw payload: {msg.payload}")
        except UnicodeDecodeError as e:
            logger.error(f"Decoding error: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _subscribe_all(self):
        """Subscribe ke semua topic yang diperlukan"""
        topics = [
            (self.topic_sensor_in, 1),
            (self.topic_command_out, 1),
            (self.topic_status_out, 1)
        ]
        
        for topic, qos in topics:
            result = self.client.subscribe(topic, qos)
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Subscribed to topic: {topic} (QoS: {qos})")
            else:
                logger.error(f"Failed to subscribe to {topic}: {result[0]}")
    
    def _handle_sensor_data(self, data: Dict):
        """Handle sensor data dari ESP32"""
        try:
            resi = data.get('resi', '').strip()
            jarak = float(data.get('jarak', 0))
            durasi = float(data.get('durasi', 0))
            slot = int(data.get('slot', 0))
            tombol = int(data.get('tombol', 0))
            
            logger.info(f"Sensor data: resi={resi}, jarak={jarak}cm, durasi={durasi}s")
            
            # Update package status based on sensor data
            self._update_package_from_sensor(resi, jarak, durasi, slot, tombol)
            
            # Broadcast security update
            self._broadcast_security_update(jarak)
            
        except Exception as e:
            logger.error(f"Error handling sensor data: {e}")
    
    def _handle_command_response(self, data: Dict):
        """Handle response dari ESP32 untuk perintah"""
        try:
            resi = data.get('resi', '')
            command = data.get('command', '')
            status = data.get('status', '')
            message = data.get('message', '')
            
            logger.info(f"Command response: {resi} - {command} - {status} - {message}")
            
            # Update package status if command affects it
            if command in ['buka_pintu', 'tutup_pintu']:
                self._update_package_status(resi, 'Dalam Proses')
            
        except Exception as e:
            logger.error(f"Error handling command response: {e}")
    
    def _update_package_from_sensor(self, resi: str, jarak: float, 
                                   durasi: float, slot: int, tombol: int):
        """Update package berdasarkan data sensor"""
        try:
            # Logic untuk update status package berdasarkan sensor data
            if jarak < 10 and durasi > 5:
                self._update_package_status(resi, 'Selesai')
                logger.info(f"Package {resi} marked as completed based on sensor data")
            elif jarak < 20 and durasi > 3:
                self._update_package_status(resi, 'Dalam Proses')
                logger.info(f"Package {resi} is in process based on sensor data")
                
        except Exception as e:
            logger.error(f"Error updating package from sensor: {e}")
    
    def _update_package_status(self, resi: str, status: str):
        """Update status package dan broadcast ke semua client"""
        try:
            # Update in database
            packages = self.db_manager.get_packages({'search': resi})
            if packages:
                package = packages[0]
                self.db_manager.update_package_status(package['id'], status)
                
                # Broadcast update
                self.publish_package_update(package['id'], status)
                logger.info(f"Package {resi} status updated to {status}")
                
        except Exception as e:
            logger.error(f"Error updating package status: {e}")
    
    def _broadcast_security_update(self, jarak: float):
        """Broadcast update keamanan"""
        try:
            # Determine security status
            status = "safe"
            if jarak < float(self.db_manager.get_setting('sensor_threshold_danger', 10)):
                status = "danger"
            elif jarak < float(self.db_manager.get_setting('sensor_threshold_warning', 15)):
                status = "warning"
            
            # Save to security logs
            probability = max(0, min(100, 100 - (jarak * 2)))
            self.db_manager.add_security_log(jarak, status, probability)
            
            # Broadcast
            self.publish_security_update(jarak, status, probability)
            
        except Exception as e:
            logger.error(f"Error broadcasting security update: {e}")
    
    def publish(self, topic: str, payload: Dict):
        """Publish pesan ke MQTT broker dengan SSL"""
        if not self.connected or not self.client:
            logger.warning(f"Cannot publish, MQTT not connected: {topic}")
            return False
        
        try:
            message = json.dumps(payload)
            result = self.client.publish(topic, message, qos=1, retain=False)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Save to database
                self.db_manager.save_mqtt_message(topic, payload, "outgoing")
                logger.info(f"Published to {topic}: {message[:100]}...")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False
    
    def publish_status(self, status: str = "online"):
        """Publish status koneksi"""
        self.publish(self.topic_status_out, {
            "status": status,
            "service": "jmailbox_dashboard_ssl",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "ssl_enabled": self.use_ssl
        })
    
    def publish_package_update(self, package_id: str, status: str):
        """Broadcast update package"""
        self.publish(self.topic_package_update, {
            "package_id": package_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "type": "status_update"
        })
    
    def publish_security_update(self, sensor_value: float, status: str, probability: float):
        """Broadcast update keamanan"""
        self.publish(self.topic_security_update, {
            "sensor_value": sensor_value,
            "status": status,
            "probability": probability,
            "timestamp": datetime.now().isoformat(),
            "type": "security_update"
        })
    
    def send_command(self, resi: str, command: str, reason: str = ""):
        """Kirim perintah ke ESP32 dengan SSL"""
        payload = {
            "resi": resi,
            "command": command,
            "reason": reason,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "server_time": datetime.now().isoformat(),
            "ssl": self.use_ssl
        }
        
        return self.publish(self.topic_command_out, payload)
    
    def register_handler(self, topic: str, handler: Callable):
        """Register handler untuk topic tertentu"""
        if topic not in self.message_handlers:
            self.message_handlers[topic] = []
        self.message_handlers[topic].append(handler)
    
    def disconnect(self):
        """Disconnect dari MQTT broker"""
        if self.client:
            self.publish_status("offline")
            time.sleep(1)
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("MQTT SSL client disconnected")
    
    def is_connected(self):
        """Cek status koneksi"""
        return self.connected

# Singleton instance
_mqtt_ssl_instance = None

def get_mqtt_ssl_client(db_manager: DatabaseManager = None):
    """Get singleton MQTT SSL client instance"""
    global _mqtt_ssl_instance
    if _mqtt_ssl_instance is None and db_manager:
        _mqtt_ssl_instance = MQTTClientSSL(db_manager)
    return _mqtt_ssl_instance