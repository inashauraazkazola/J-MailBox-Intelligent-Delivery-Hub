from flask import Flask, request, jsonify, send_file, g
import os
import sqlite3
from datetime import datetime, timedelta
import re
from werkzeug.utils import secure_filename
import uuid
import logging
import json
import joblib
import numpy as np
import paho.mqtt.client as mqtt
import threading
import time
import hashlib
from collections import deque
from threading import Condition
from typing import Dict, Any, Optional, List
from functools import wraps
import secrets
import socket
import psutil

# --- SETUP LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 🔒 SECURITY CONFIGURATION
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE'] = 'database_pengiriman.db'
app.config['SESSION_TIMEOUT'] = 1800  # 30 menit
app.config['RATE_LIMIT'] = 100  # requests per minute

# 🔧 Konfigurasi
# Catatan:
# - Semua path dibuat ABSOLUT berbasis working directory proses (PM2 / systemd), agar tidak tergantung lokasi eksekusi.
# - Kamu bisa override dengan env var: RECEIVER_WORKDIR=/root/dashboard (atau folder lain).
BASE_DIR = os.path.abspath(os.environ.get("RECEIVER_WORKDIR", os.getcwd()))
APP_DIR = os.path.abspath(os.path.dirname(__file__))

BASE_FOLDER = os.path.join(BASE_DIR, 'pengiriman')
DB_NAME = os.path.join(BASE_DIR, 'database_pengiriman.db')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 🔬 KONFIGURASI AI
# Model AI biasanya disimpan sebagai file joblib/pickle.
# Agar tidak gagal karena "cwd" berbeda, kita cari model dari beberapa lokasi kandidat.
AI_MODEL_ENV = os.environ.get("AI_MODEL_PATH")  # opsional override
MODEL_CANDIDATES = [
    AI_MODEL_ENV,
    os.path.join(BASE_DIR, "ultrasonic_model.pkl"),
    os.path.join(APP_DIR, "ultrasonic_model.pkl"),
    "/root/ultrasonic_model.pkl",
    "/root/dashboard/ultrasonic_model.pkl",
]

def _pick_model_path() -> str:
    for p in MODEL_CANDIDATES:
        if not p:
            continue
        try:
            if os.path.exists(p):
                return p
        except Exception:
            continue
    return ""

MODEL_PATH = _pick_model_path()

best_model = None
scaler = None

if not MODEL_PATH:
    logger.warning("⚠️ AI model tidak ditemukan. Cek file ultrasonic_model.pkl atau set AI_MODEL_PATH.")
else:
    try:
        model_data = joblib.load(MODEL_PATH)
        # format yang diharapkan: {"best_model": ..., "scaler": ...}
        best_model = model_data.get("best_model") if isinstance(model_data, dict) else None
        scaler = model_data.get("scaler") if isinstance(model_data, dict) else None

        if best_model is None or scaler is None:
            logger.error(
                f"❌ Model AI terbaca dari {MODEL_PATH} tapi formatnya tidak sesuai (butuh keys: best_model, scaler)."
            )
            best_model = None
            scaler = None
        else:
            logger.info(f"✅ Model AI berhasil dimuat dari: {MODEL_PATH}")
    except Exception as e:
        logger.error(f"❌ Gagal memuat model AI dari {MODEL_PATH}: {e}", exc_info=True)
        best_model = None
        scaler = None

# ✅ KONFIGURASI MQTT

MQTT_BROKER = os.environ.get("MQTT_BROKER_IP", "YOUR_MQTT_SERVER_IP")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USERNAME = os.environ.get("MQTT_USER", "YOUR_MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASS", "YOUR_MQTT_PASSWORD")
MQTT_KEEPALIVE = 60
MQTT_QOS = 1  
MQTT_RETAIN = True

# ✅ TOPIC MQTT
TOPIC_SENSOR_IN = "alat/sensor"
TOPIC_COMMAND_OUT = "alat/perintah"
TOPIC_STATUS_OUT = "alat/status"
TOPIC_AI_RESULT = "alat/ai_result"
TOPIC_HEARTBEAT = "alat/heartbeat"

# ✅ MQTT CLIENT GLOBAL dengan thread safety
mqtt_client = None
mqtt_connected = False
mqtt_lock = threading.RLock()

# --- DASHBOARD EVENT BUFFER (SSE/POLLING) ---
_event_buf = deque(maxlen=300)  # simpan event terakhir
_event_lock = threading.Lock()
_event_cond = Condition(_event_lock)

mqtt_reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 10


# Konstanta status
STATUS_PENDING = 'pending'
STATUS_SCANNED = 'scanned'
STATUS_MONITORING = 'monitoring'
STATUS_COMPLETED = 'completed'
STATUS_DELIVERED = 'delivered'
STATUS_FAILED = 'failed'
STATUS_BAHAYA = 'bahaya'
STATUS_PERINGATAN = 'peringatan'

# ✅ KONSTANTA TIPE PEMBAYARAN
PAYMENT_COD = 'COD'
PAYMENT_NON_COD = 'NON_COD'
PAYMENT_TRANSFER = 'TRANSFER'
PAYMENT_LUNAS = 'LUNAS'

# ✅ KONSTANTA PERINTAH
COMMAND_OPEN_SLOT = 'buka_slot_uang'
COMMAND_CLOSE_SLOT = 'tutup_slot_uang'
COMMAND_OPEN_DOOR = 'buka_pintu'
COMMAND_CLOSE_DOOR = 'tutup_pintu'
COMMAND_BUZZER_ON = 'buzzer_on'
COMMAND_BUZZER_OFF = 'buzzer_off'
COMMAND_LED_ON = 'nyalakan_led'
COMMAND_LED_OFF = 'matikan_led'
COMMAND_VERIFY_COD = 'verify_cod_slot'
COMMAND_RESET = 'reset_system'

# Rate limiting storage
request_log = {}
rate_limit_lock = threading.Lock()  # global lock for rate limiting

# --- INISIALISASI ---
def setup_folders():
    """Setup folder yang diperlukan dengan permissions yang aman"""
    folders = [
        BASE_FOLDER,
        os.path.join(BASE_FOLDER, 'backup'),
        os.path.join(BASE_FOLDER, 'logs'),
        os.path.join(BASE_FOLDER, 'temp'),
        os.path.join(BASE_FOLDER, 'ai_logs'),
        os.path.join(BASE_FOLDER, 'mqtt_logs'),
        os.path.join(BASE_FOLDER, 'uploads'),
        os.path.join(BASE_FOLDER, 'trash')
    ]
    
    for folder in folders:
        try:
            os.makedirs(folder, mode=0o755, exist_ok=True)
            logger.info(f"✅ Folder created: {folder}")
        except OSError as e:
            logger.error(f"❌ Failed to create folder {folder}: {e}")
            raise

# --- SECURITY UTILITIES ---
def validate_resi(resi: str) -> bool:
    """Validasi format nomor resi"""
    pattern = r'^[A-Za-z0-9\-]{5,20}$'
    return bool(re.match(pattern, resi))

def sanitize_filename(filename: str) -> str:
    """Sanitize filename untuk mencegah path traversal"""
    # Remove directory components
    filename = os.path.basename(filename)
    # Remove dangerous characters
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    return filename

def validate_file_extension(filename: str) -> bool:
    """Validasi ekstensi file"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def hash_password(password: str) -> str:
    """Hash password dengan salt"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + key.hex()

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verifikasi password"""
    salt = bytes.fromhex(stored_password[:64])
    stored_key = stored_password[64:]
    provided_key = hashlib.pbkdf2_hmac(
        'sha256',
        provided_password.encode(),
        salt,
        100000
    ).hex()
    return stored_key == provided_key

def rate_limit(max_requests=100, window=60):
    """Decorator untuk rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()
            
            with rate_limit_lock:
                if client_ip not in request_log:
                    request_log[client_ip] = []
                
                # Remove old requests
                request_log[client_ip] = [
                    t for t in request_log[client_ip] 
                    if current_time - t < window
                ]
                
                # Check if limit exceeded
                if len(request_log[client_ip]) >= max_requests:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": window
                    }), 429
                
                # Add current request
                request_log[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- DATABASE UTILITIES ---

def get_db_connection():
    """Database connection helper.

    Catatan penting:
    - Callback MQTT berjalan di background thread (di luar Flask request context), jadi TIDAK aman memakai `g`.
    - Untuk menyederhanakan dan mencegah error "Working outside of application context", koneksi dibuat per pemakaian.

    Pastikan caller melakukan conn.close() setelah selesai.
    """
    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False,
        timeout=10
    )
    conn.row_factory = sqlite3.Row
    # Enable WAL mode untuk concurrency yang lebih baik
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


from contextlib import contextmanager

@contextmanager
def db_conn():
    """Context manager for DB connections (always closes)."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

def init_db() -> None:
    """Inisialisasi database dengan semua tabel dan index"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # ✅ TABEL USER untuk autentikasi
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                api_key TEXT UNIQUE,
                last_login TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ✅ TABEL UTAMA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pengiriman (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nomor_resi TEXT UNIQUE NOT NULL,
                tipe_pembayaran TEXT DEFAULT 'COD',
                waktu_scan TEXT NOT NULL,
                waktu_upload TEXT,
                waktu_monitoring TEXT,
                waktu_selesai TEXT,
                nama_foto TEXT,
                path_foto TEXT,
                status TEXT DEFAULT 'pending',
                jarak_paket REAL DEFAULT 0,
                durasi_objek REAL DEFAULT 0,
                slot_uang INTEGER DEFAULT 0,
                tombol_ditekan INTEGER DEFAULT 0,
                prediksi_ai TEXT,
                confidence_ai REAL DEFAULT 0,
                alasan_selesai TEXT,
                uang_diterima BOOLEAN DEFAULT FALSE,
                mqtt_commands_sent INTEGER DEFAULT 0,
                mqtt_last_update TEXT,
                created_by INTEGER,
                updated_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (updated_by) REFERENCES users(id)
            )
        ''')
        
        # ✅ TABEL MONITORING LOG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resi TEXT NOT NULL,
                waktu_log TEXT NOT NULL,
                jarak_paket REAL,
                durasi_objek REAL,
                slot_uang INTEGER,
                tombol_ditekan INTEGER DEFAULT 0,
                prediksi_ai TEXT,
                confidence_ai REAL DEFAULT 0,
                source TEXT DEFAULT 'http',
                client_ip TEXT,
                user_agent TEXT,
                FOREIGN KEY (resi) REFERENCES pengiriman(nomor_resi) ON DELETE CASCADE
            )
        ''')
        
        # ✅ TABEL AI LOGS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resi TEXT NOT NULL,
                waktu_log TEXT NOT NULL,
                jarak REAL,
                durasi REAL,
                prediksi TEXT,
                confidence REAL,
                features_scaled TEXT,
                model_version TEXT DEFAULT '1.0',
                processing_time_ms INTEGER,
                FOREIGN KEY (resi) REFERENCES pengiriman(nomor_resi) ON DELETE CASCADE
            )
        ''')
        
        # ✅ TABEL MQTT LOGS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mqtt_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu_log TEXT NOT NULL,
                topic TEXT NOT NULL,
                direction TEXT NOT NULL,
                payload TEXT,
                resi TEXT,
                message_id INTEGER,
                qos INTEGER DEFAULT 0,
                retained BOOLEAN DEFAULT FALSE,
                processed BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                FOREIGN KEY (resi) REFERENCES pengiriman(nomor_resi) ON DELETE SET NULL
            )
        ''')
        
        # ✅ TABEL PERINTAH
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perintah (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resi TEXT NOT NULL,
                perintah TEXT NOT NULL,
                tipe_aksi TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                waktu_perintah TEXT NOT NULL,
                waktu_eksekusi TEXT,
                message TEXT,
                triggered_by_ai BOOLEAN DEFAULT FALSE,
                sent_via_mqtt BOOLEAN DEFAULT FALSE,
                mqtt_message_id TEXT,
                response_received BOOLEAN DEFAULT FALSE,
                response_payload TEXT,
                executed_by INTEGER,
                FOREIGN KEY (resi) REFERENCES pengiriman(nomor_resi) ON DELETE CASCADE,
                FOREIGN KEY (executed_by) REFERENCES users(id)
            )
        ''')
        
        # ✅ TABEL AUDIT LOG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu_log TEXT NOT NULL,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                client_ip TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # ✅ TABEL SYSTEM HEALTH
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu_check TEXT NOT NULL,
                service_name TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time_ms INTEGER,
                error_message TEXT,
                details TEXT
            )
        ''')
        
        # Index untuk performa
        indexes = [
            ('idx_resi_status', 'pengiriman(nomor_resi, status)'),
            ('idx_payment_status', 'pengiriman(tipe_pembayaran, status)'),
            ('idx_created_at', 'pengiriman(created_at)'),
            ('idx_mqtt_update', 'pengiriman(mqtt_last_update)'),
            ('idx_monitoring_resi_time', 'monitoring_log(resi, waktu_log)'),
            ('idx_perintah_status_time', 'perintah(status, waktu_perintah)'),
            ('idx_audit_time', 'audit_log(waktu_log)'),
            ('idx_system_health_time', 'system_health(waktu_check)')
        ]
        
        for idx_name, idx_column in indexes:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_column}')
        
        # Buat user default jika belum ada
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        if count == 0:

            default_password = hash_password('admin123')
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, api_key)
                VALUES (?, ?, ?, ?)
            ''', ('admin', default_password, 'admin', secrets.token_hex(32)))
            logger.info("✅ Default admin user created")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Database {DB_NAME} initialized successfully")
        
    except sqlite3.Error as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise

# --- MQTT FUNCTIONS ---
def on_mqtt_connect(client, userdata, flags, rc):
    """Callback ketika terhubung ke MQTT broker.

    ⚠️ Penting: callback ini berjalan di network-thread Paho.
    Jangan memegang mqtt_lock lalu memanggil fungsi lain yang juga memakai mqtt_lock
    (mis. publish_mqtt_message), karena bisa deadlock dan membuat on_message tidak pernah jalan.
    """
    global mqtt_connected, mqtt_reconnect_attempts

    if rc == 0:
        # Update state di dalam lock (ringan)
        with mqtt_lock:
            mqtt_connected = True
            mqtt_reconnect_attempts = 0

        # Subscribe topic (tidak perlu lock)
        try:
            client.subscribe(TOPIC_SENSOR_IN, qos=MQTT_QOS)
            client.subscribe(f"{TOPIC_COMMAND_OUT}/response", qos=MQTT_QOS)
            client.subscribe(TOPIC_STATUS_OUT, qos=MQTT_QOS)
        except Exception as e:
            logger.error(f"❌ MQTT subscribe error: {e}", exc_info=True)

        logger.info(f"✅ MQTT Connected to {MQTT_BROKER}:{MQTT_PORT}")
        logger.info(f"✅ Subscribed to: {TOPIC_SENSOR_IN}")
        logger.info(f"✅ Subscribed to: {TOPIC_STATUS_OUT}")
        logger.info(f"✅ Subscribed to: {TOPIC_COMMAND_OUT}/response")

        # Publish status online (hindari deadlock: publish_mqtt_message pakai mqtt_lock juga)
        try:
            publish_mqtt_message(
                TOPIC_STATUS_OUT,
                {
                    "status": "online",
                    "service": "receiver_api",
                    "version": "6.0",
                    "timestamp": datetime.now().isoformat(),
                },
                retain=True,
            )
        except Exception as e:
            logger.error(f"❌ MQTT publish online status error: {e}", exc_info=True)

        # Log event
        try:
            log_mqtt_event("connect", "Connected to MQTT broker")
        except Exception:
            pass

    else:
        # Connection failed
        with mqtt_lock:
            mqtt_connected = False

        error_messages = {
            1: "Protocol version error",
            2: "Client identifier error",
            3: "Server unavailable",
            4: "Bad username/password",
            5: "Not authorized",
        }
        error_msg = error_messages.get(rc, f"Code: {rc}")
        logger.error(f"❌ MQTT Connection failed: {error_msg}")

        # Auto reconnect backoff
        try:
            if mqtt_reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                delay = min(2 ** mqtt_reconnect_attempts, 30)
                time.sleep(delay)
                mqtt_reconnect_attempts += 1
                client.reconnect()
        except Exception as e:
            logger.error(f"❌ MQTT reconnect attempt error: {e}", exc_info=True)


def on_mqtt_disconnect(client, userdata, rc):
    """Callback ketika terputus dari MQTT broker"""
    global mqtt_connected
    
    with mqtt_lock:
        mqtt_connected = False
        logger.warning(f"⚠️ MQTT Disconnected. Code: {rc}")
        
        # Log ke database
        log_mqtt_event("disconnect", f"Disconnected from MQTT broker (rc={rc})")
        
        if rc != 0:
            # Unexpected disconnect, try to reconnect
            time.sleep(5)
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"❌ MQTT Reconnect failed: {e}")



def on_mqtt_subscribe(client, userdata, mid, granted_qos, properties=None):
    """Callback ketika broker meng-ACK subscribe.

    granted_qos berisi list qos yang diberikan broker per topic.
    Jika nilai 128 -> subscribe ditolak (ACL / auth).
    """
    try:
        logger.info(f"✅ MQTT SUBACK mid={mid} granted_qos={list(granted_qos)}")
    except Exception:
        logger.info(f"✅ MQTT SUBACK mid={mid} granted_qos={granted_qos}")

def on_mqtt_log(client, userdata, level, buf):
    """Log internal Paho MQTT untuk debugging masalah subscribe/ACL/disconnect."""
    # level lebih kecil = lebih penting (ERROR/WARNING)
    try:
        if level <= mqtt.MQTT_LOG_WARNING:
            logger.warning(f"MQTT LOG: {buf}")
        elif level <= mqtt.MQTT_LOG_INFO:
            logger.info(f"MQTT LOG: {buf}")
    except Exception:
        pass



def on_mqtt_message(client, userdata, msg):
    """Callback ketika menerima message dari MQTT"""
    try:
        logger.info(f"📥 MQTT Message received on {msg.topic}")
        
        # Decode payload
        payload = msg.payload.decode('utf-8', errors='ignore')
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON from MQTT: {payload[:100]}...")
            return
        
        # Log ke database
        log_mqtt_incoming(msg.topic, payload, data.get('resi', 'unknown'))

        # push event untuk dashboard
        try:
            evt = {
                'topic': msg.topic,
                'payload': data,
                'received_at': datetime.now().isoformat()
            }
            with _event_cond:
                _event_buf.append(evt)
                _event_cond.notify_all()
        except Exception:
            pass
        
        # Handle berdasarkan topic
        if msg.topic == TOPIC_SENSOR_IN:
            handle_sensor_data(data)
        elif msg.topic == f"{TOPIC_COMMAND_OUT}/response":
            handle_command_response(data)
        elif msg.topic == TOPIC_STATUS_OUT:
            handle_status_event(data)
            
    except Exception as e:
        logger.error(f"❌ Error processing MQTT message: {e}", exc_info=True)


def handle_sensor_data(data: Dict):
    """Handle sensor data dari ESP32"""
    try:
        resi = data.get('resi', '').strip()
        jarak = float(data.get('jarak', 0))
        durasi = float(data.get('durasi', 0))
        slot = int(data.get('slot', 0))
        tombol = int(data.get('tombol', 0))

        logger.info(f"📡 Sensor data from {resi}: jarak={jarak}cm, durasi={durasi}s")

        waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Simpan ke database monitoring (pastikan conn selalu ditutup)
        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO monitoring_log
                (resi, waktu_log, jarak_paket, durasi_objek, slot_uang, tombol_ditekan, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (resi, waktu_log, jarak, durasi, slot, tombol, 'mqtt'))
            conn.commit()

        # Kirim ke HTTP endpoint untuk processing (opsional, tapi tetap dipertahankan)
        import requests
        try:
            response = requests.post(
                "http://localhost:5000/update_status",
                json={
                    "resi": resi,
                    "jarak": jarak,
                    "durasi": durasi,
                    "slot": slot,
                    "tombol": tombol,
                    "source": "mqtt"
                },
                timeout=3
            )

            if response.status_code == 200:
                logger.info(f"✅ Sensor data processed for {resi}")
            else:
                logger.error(f"❌ Failed to process sensor data: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP request failed: {e}")

    except Exception as e:
        logger.error(f"❌ Error handling sensor data: {e}", exc_info=True)



def handle_command_response(data: Dict):
    """Handle response dari ESP32 untuk perintah yang dikirim"""
    try:
        resi = data.get('resi', '')
        command = data.get('command', '')
        status = data.get('status', '')
        message = data.get('message', '')

        # ✅ ambil message_id dari device (harus sama dengan yang dikirim)
        msg_id = data.get('message_id') or data.get('mqtt_message_id')

        logger.info(f"📩 Command response for {resi}: {command} -> {status} | {message}")

        waktu_eksekusi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_conn() as conn:
            cursor = conn.cursor()

            if msg_id:
                cursor.execute('''
                    UPDATE perintah
                    SET status = ?, waktu_eksekusi = ?, response_received = TRUE, response_payload = ?
                    WHERE resi = ? AND perintah = ? AND status = 'pending' AND mqtt_message_id = ?
                ''', (status, waktu_eksekusi, json.dumps(data), resi, command, msg_id))
            else:
                # fallback kalau firmware belum kirim message_id balik (kurang aman)
                cursor.execute('''
                    UPDATE perintah
                    SET status = ?, waktu_eksekusi = ?, response_received = TRUE, response_payload = ?
                    WHERE resi = ? AND perintah = ? AND status = 'pending'
                ''', (status, waktu_eksekusi, json.dumps(data), resi, command))

            conn.commit()

    except Exception as e:
        logger.error(f"❌ Error handling command response: {e}", exc_info=True)

def handle_status_event(data: Dict):
    """Handle event status dari ESP32 (mis. hasil scan barcode GM65).

    Expect payload:
      {"type":"resi_scanned","resi":"...","tipe_pembayaran":"COD"|...,"timestamp":"..."}
    """
    try:
        event_type = data.get("type") or data.get("event")
        if event_type != "resi_scanned":
            return

        resi = str(data.get("resi", "")).strip()
        if not validate_resi(resi):
            logger.warning(f"Invalid resi from MQTT status: {resi}")
            return

        safe_resi = secure_filename(resi)
        waktu_scan = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        payment_type = str(data.get("tipe_pembayaran") or data.get("payment_type") or PAYMENT_COD).upper()

        # folder resi
        os.makedirs(os.path.join(BASE_FOLDER, safe_resi), mode=0o755, exist_ok=True)

        # payment type (default COD)
        payment_type = str(data.get("tipe_pembayaran") or data.get("payment_type") or PAYMENT_COD).upper()
        if payment_type not in [PAYMENT_COD, PAYMENT_NON_COD, PAYMENT_TRANSFER, PAYMENT_LUNAS]:
            payment_type = PAYMENT_COD

        # simpan ke DB (insert / update)
        with db_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO pengiriman (nomor_resi, tipe_pembayaran, waktu_scan, status)
                    VALUES (?, ?, ?, ?)
                ''', (safe_resi, payment_type, waktu_scan, STATUS_SCANNED))
            except sqlite3.IntegrityError:
                cursor.execute('''
                    UPDATE pengiriman
                    SET tipe_pembayaran = COALESCE(NULLIF(?, ''), tipe_pembayaran),
                        waktu_scan = ?, status = ?, updated_at = ?
                    WHERE nomor_resi = ?
                ''', (payment_type, waktu_scan, STATUS_SCANNED, waktu_scan, safe_resi))
            conn.commit()

        logger.info(f"✅ Resi from MQTT saved: {safe_resi}")

        # broadcast event ke dashboard (biar UI auto update walau tanpa polling mqtt_logs)
        try:
            evt = {
                'topic': TOPIC_STATUS_OUT,
                'payload': data,
                'received_at': datetime.now().isoformat()
            }
            with _event_cond:
                _event_buf.append(evt)
                _event_cond.notify_all()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"❌ handle_status_event error: {e}", exc_info=True)
def publish_mqtt_message(topic: str, payload: Dict, retain=False, qos=1):
    """Thread-safe MQTT publishing"""
    global mqtt_client, mqtt_connected
    
    with mqtt_lock:
        if mqtt_client and mqtt_connected:
            try:
                message = json.dumps(payload, default=str)
                msg_info = mqtt_client.publish(topic, message, qos=qos, retain=retain)
                
                if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"📤 MQTT Published to {topic} (QoS={qos})")
                    
                    # Log outgoing message
                    log_mqtt_outgoing(topic, message, payload.get('resi', 'unknown'))
                    
                    return True
                else:
                    logger.error(f"❌ MQTT Publish failed: {mqtt.error_string(msg_info.rc)}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Failed to publish MQTT message: {e}")
                return False
        else:
            logger.warning(f"⚠️ MQTT not connected, cannot publish to {topic}")
            return False

def send_mqtt_command(resi: str, command: str, reason: str = "", timeout=30):
    """Kirim perintah ke ESP32 dengan timeout"""
    payload = {
        "resi": resi,
        "command": command,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
        "message_id": secrets.token_hex(8)
    }
    
    # Kirim perintah
    if publish_mqtt_message(TOPIC_COMMAND_OUT, payload, qos=1):
        # Simpan ke database
        save_command_to_db(resi, command, reason, payload['message_id'])
        
        # Wait for response dengan timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Cek apakah response sudah diterima
            with db_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT status, response_payload 
                    FROM perintah 
                    WHERE resi = ? AND perintah = ? AND mqtt_message_id = ?
                ''', (resi, command, payload['message_id']))
                result = cursor.fetchone()
            
            if result and result['status'] != 'pending':
                return {
                    "success": True,
                    "status": result['status'],
                    "response": json.loads(result['response_payload']) if result['response_payload'] else None
                }
            
            time.sleep(0.5)
        
        # Timeout
        return {
            "success": False,
            "status": "timeout",
            "message": "No response received within timeout period"
        }
    else:
        return {
            "success": False,
            "status": "failed",
            "message": "Failed to publish MQTT message"
        }


def save_command_to_db(resi: str, command: str, reason: str = "", message_id: str = None):
    """Simpan perintah ke database"""
    try:
        waktu_perintah = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Tentukan tipe aksi
        tipe_aksi = 'normal'
        if 'slot' in command:
            tipe_aksi = 'slot_control'
        elif 'pintu' in command or 'door' in command:
            tipe_aksi = 'door_control'
        elif 'buzzer' in command:
            tipe_aksi = 'alert_system'
        elif 'led' in command:
            tipe_aksi = 'indicator'

        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO perintah
                (resi, perintah, tipe_aksi, status, waktu_perintah, message, mqtt_message_id, sent_via_mqtt)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, TRUE)
            ''', (resi, command, tipe_aksi, waktu_perintah, reason, message_id))
            conn.commit()

        logger.info(f"💾 Command saved to DB: {command} for {resi}")

    except Exception as e:
        logger.error(f"❌ Failed to save command to DB: {e}", exc_info=True)




def _resi_exists_in_pengiriman(conn, resi: str) -> bool:
    """Return True if resi exists in pengiriman. Used to avoid FK failures in mqtt_logs."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pengiriman WHERE nomor_resi=? LIMIT 1", (resi,))
        return cur.fetchone() is not None
    except Exception:
        return False




def log_mqtt_incoming(topic: str, payload: str, resi: str = None):
    """Log incoming MQTT message ke database.

    ⚠️ mqtt_logs.resi punya FOREIGN KEY ke pengiriman(nomor_resi).
    Jadi kalau resi belum ada di pengiriman, kita simpan NULL agar tidak FK error.
    """
    try:
        waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        resi_db = None
        if resi:
            resi_s = str(resi).strip()
            if resi_s and resi_s.lower() != "unknown":
                with db_conn() as conn:
                    if _resi_exists_in_pengiriman(conn, resi_s):
                        resi_db = resi_s
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO mqtt_logs
                        (waktu_log, topic, direction, payload, resi)
                        VALUES (?, ?, 'incoming', ?, ?)
                    ''', (waktu_log, topic, payload, resi_db))
                    conn.commit()
                    return

        # fallback: simpan resi NULL
        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO mqtt_logs
                (waktu_log, topic, direction, payload, resi)
                VALUES (?, ?, 'incoming', ?, ?)
            ''', (waktu_log, topic, payload, None))
            conn.commit()

    except Exception as e:
        logger.error(f"❌ Failed to log MQTT incoming: {e}", exc_info=True)



def log_mqtt_outgoing(topic: str, payload: str, resi: str = None):
    """Log outgoing MQTT message ke database.

    Sama seperti incoming: resi disimpan hanya jika sudah ada di pengiriman agar tidak FK error.
    """
    try:
        waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        resi_db = None
        if resi:
            resi_s = str(resi).strip()
            if resi_s and resi_s.lower() != "unknown":
                with db_conn() as conn:
                    if _resi_exists_in_pengiriman(conn, resi_s):
                        resi_db = resi_s
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO mqtt_logs
                        (waktu_log, topic, direction, payload, resi)
                        VALUES (?, ?, 'outgoing', ?, ?)
                    ''', (waktu_log, topic, payload, resi_db))
                    conn.commit()
                    return

        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO mqtt_logs
                (waktu_log, topic, direction, payload, resi)
                VALUES (?, ?, 'outgoing', ?, ?)
            ''', (waktu_log, topic, payload, None))
            conn.commit()

    except Exception as e:
        logger.error(f"❌ Failed to log MQTT outgoing: {e}", exc_info=True)


def log_mqtt_event(event_type: str, message: str):
    """Log MQTT event ke database"""
    try:
        waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_health
                (waktu_check, service_name, status, details)
                VALUES (?, 'mqtt', ?, ?)
            ''', (waktu_log, event_type, message))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to log MQTT event: {e}", exc_info=True)


def init_mqtt_client():
    """Initialize MQTT client dengan reconnection logic"""
    global mqtt_client, mqtt_connected
    
    try:
        mqtt_connected = False
        # Create client dengan unique ID
        client_id = os.getenv("MQTT_CLIENT_ID") or f"receiver-api-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        mqtt_client = mqtt.Client(
            client_id=client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )
        
        # Set username/password
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        # Set TLS jika diperlukan (uncomment jika menggunakan TLS)
        # mqtt_client.tls_set(ca_certs="ca.crt")
        
        # Set callback functions
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.on_message = on_mqtt_message
        mqtt_client.on_subscribe = on_mqtt_subscribe
        mqtt_client.on_log = on_mqtt_log
        try:
            mqtt_client.enable_logger(logger)
        except Exception:
            pass
        logger.info(f"🆔 MQTT client_id={client_id}")
        
        # Set Last Will and Testament
        mqtt_client.will_set(
            TOPIC_STATUS_OUT,
            json.dumps({
                "status": "offline",
                "service": "receiver_api",
                "timestamp": datetime.now().isoformat()
            }),
            qos=1,
            retain=True
        )
        
        # Set reconnect delay
        mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
        
        # Connect to broker
        logger.info(f"🔗 Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        
        # Start loop in background thread
        mqtt_client.loop_start()
        logger.info("✅ MQTT loop_start() started")
        
        # Wait for connection
        for i in range(15):
            if mqtt_connected:
                break
            time.sleep(0.5)
        
        if mqtt_connected:
            logger.info("✅ MQTT client initialized successfully")
            return True
        else:
            logger.error("❌ MQTT client failed to connect")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize MQTT client: {e}")
        return False

def mqtt_health_check():
    """Periodic MQTT health check dan maintenance"""
    while True:
        try:
            time.sleep(30)  # Check every 30 seconds
            
            if mqtt_connected:
                # Publish heartbeat
                publish_mqtt_message(TOPIC_HEARTBEAT, {
                    "service": "receiver_api",
                    "status": "alive",
                    "timestamp": datetime.now().isoformat(),
                    "uptime": time.time() - start_time,
                    "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024  # MB
                }, qos=0)
                
                # Clean old MQTT logs (older than 7 days)
                with db_conn() as conn:
                    cursor = conn.cursor()
                    cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

                    cursor.execute('''
                        DELETE FROM mqtt_logs
                        WHERE waktu_log < ?
                    ''', (cutoff_date,))

                    deleted_count = cursor.rowcount
                    if deleted_count > 0:
                        logger.info(f"🧹 Cleaned {deleted_count} old MQTT logs")
                    conn.commit()

            else:
                logger.warning("⚠️ MQTT not connected, attempting to reconnect...")
                
        except Exception as e:
            logger.error(f"❌ MQTT health check error: {e}")

# --- AI FUNCTIONS ---
def predict_ai_status(jarak: float, durasi: float) -> Dict[str, Any]:
    """Prediksi status berdasarkan data ultrasonik dengan error handling"""
    if best_model is None or scaler is None:
        return {
            "prediction": "unknown",
            "confidence": 0.0,
            "features_scaled": [],
            "model_available": False,
            "error": "Model tidak tersedia"
        }
    
    try:
        start_time = time.time()
        
        features = np.array([[jarak, durasi]])
        features_scaled = scaler.transform(features)
        
        # Prediksi
        prediction_raw = best_model.predict(features_scaled)[0]
        prediction = int(prediction_raw)
        
        # Confidence
        if hasattr(best_model, 'predict_proba'):
            probabilities = best_model.predict_proba(features_scaled)[0]
            confidence = float(max(probabilities))
        else:
            confidence = 1.0
        
        # Mapping label
        prediction_labels = {
            0: "aman",
            1: "peringatan", 
            2: "bahaya"
        }
        prediction_label = prediction_labels.get(prediction, "unknown")
        
        processing_time = int((time.time() - start_time) * 1000)  # ms
        
        # Log ke database
        try:
            with db_conn() as conn:
                cursor = conn.cursor()
                waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute('''
                INSERT INTO ai_logs 
                (resi, waktu_log, jarak, durasi, prediksi, confidence, 
                 features_scaled, model_version, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('system', waktu_log, jarak, durasi, prediction_label, 
                  confidence, json.dumps(features_scaled[0].tolist()), 
                  '1.0', processing_time))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Failed to log AI prediction: {e}")
        
        logger.info(f"🤖 AI Prediction: {prediction_label} (confidence={confidence:.2f}, time={processing_time}ms)")
        
        return {
            "prediction": prediction_label,
            "confidence": confidence,
            "features_scaled": features_scaled[0].tolist(),
            "model_available": True,
            "processing_time_ms": processing_time,
            "raw_prediction": prediction
        }
        
    except Exception as e:
        logger.error(f"❌ AI Prediction error: {e}")
        return {
            "prediction": "error",
            "confidence": 0.0,
            "features_scaled": [],
            "model_available": False,
            "error": str(e)
        }


def get_payment_type(resi: str) -> str:
    """Ambil tipe pembayaran untuk resi tertentu"""
    try:
        with db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tipe_pembayaran FROM pengiriman WHERE nomor_resi = ?
            ''', (resi,))
            result = cursor.fetchone()

        if result:
            return result['tipe_pembayaran']
        return PAYMENT_COD

    except Exception as e:
        logger.error(f"❌ Error getting payment type: {e}", exc_info=True)
        return PAYMENT_COD


# --- ROUTES ---
@app.route('/')
@rate_limit(max_requests=60, window=60)
def home():
    """Health check endpoint dengan status lengkap"""
    conn = None
    try:
        import platform

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as count FROM pengiriman')
        total_resi = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM mqtt_logs WHERE direction = ?', ('incoming',))
        mqtt_incoming = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM mqtt_logs WHERE direction = ?', ('outgoing',))
        mqtt_outgoing = cursor.fetchone()['count']

        system_info = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }

        return jsonify({
            "status": "online",
            "service": "Receiver API dengan MQTT",
            "version": "6.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": system_info,
            "database": {
                "total_resi": total_resi,
                "mqtt_messages": {
                    "incoming": mqtt_incoming,
                    "outgoing": mqtt_outgoing
                }
            },
            "mqtt": {
                "connected": mqtt_connected,
                "broker": f"{MQTT_BROKER}:{MQTT_PORT}",
                "topics": {
                    "sensor_in": TOPIC_SENSOR_IN,
                    "command_out": TOPIC_COMMAND_OUT,
                    "status_out": TOPIC_STATUS_OUT,
                    "ai_result": TOPIC_AI_RESULT,
                    "heartbeat": TOPIC_HEARTBEAT
                }
            },
            "ai_system": best_model is not None
        }), 200

    except Exception as e:
        logger.error(f"❌ Home endpoint error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

@app.route('/scan_resi', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def scan_resi():
    """Scan resi dengan validasi lengkap"""
    logger.info(f"Scan resi request from {request.remote_addr}")
    
    if not request.is_json:
        return jsonify({"error": "Content-Type harus application/json"}), 400
    
    data = request.get_json()
    if not data or 'resi' not in data:
        return jsonify({"error": "Field 'resi' diperlukan"}), 400
    
    resi = data['resi'].strip()
    
    # Validasi resi
    if not resi:
        return jsonify({"error": "Nomor resi tidak boleh kosong"}), 400
    
    if not validate_resi(resi):
        return jsonify({
            "error": "Format resi tidak valid",
            "note": "Hanya boleh mengandung huruf, angka, dan dash (5-20 karakter)"
        }), 400
    
    # Sanitize resi
    safe_resi = secure_filename(resi)
    if safe_resi != resi:
        logger.warning(f"Resi sanitized: {resi} -> {safe_resi}")
    
    path_resi = os.path.join(BASE_FOLDER, safe_resi)
    
    try:
        # Buat folder untuk resi
        os.makedirs(path_resi, mode=0o755, exist_ok=True)
        logger.info(f"📁 Folder created for resi: {safe_resi}")
        
        # Tentukan tipe pembayaran
        payment_type = data.get('tipe_pembayaran', PAYMENT_COD).upper()
        valid_types = [PAYMENT_COD, PAYMENT_NON_COD, PAYMENT_TRANSFER, PAYMENT_LUNAS]
        if payment_type not in valid_types:
            payment_type = PAYMENT_COD
        
        # Simpan ke database
        waktu_scan = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO pengiriman 
                    (nomor_resi, tipe_pembayaran, waktu_scan, status) 
                    VALUES (?, ?, ?, ?)
                ''', (safe_resi, payment_type, waktu_scan, STATUS_SCANNED))
                logger.info(f"✅ Resi {safe_resi} berhasil discan (Tipe: {payment_type})")
            except sqlite3.IntegrityError:
                # Resi sudah ada, update
                cursor.execute('''
                    UPDATE pengiriman 
                    SET waktu_scan = ?, status = ?, updated_at = ?
                    WHERE nomor_resi = ?
                ''', (waktu_scan, STATUS_SCANNED, waktu_scan, safe_resi))
                logger.info(f"🔁 Resi {safe_resi} diupdate (Tipe: {payment_type})")

            conn.commit()

        # Publish ke MQTT
        if mqtt_connected:
            publish_mqtt_message(TOPIC_STATUS_OUT, {
                "event": "resi_scanned",
                "resi": safe_resi,
                "payment_type": payment_type,
                "status": STATUS_SCANNED,
                "timestamp": waktu_scan,
                "message": f"Resi {safe_resi} berhasil discan"
            })
        
        return jsonify({
            "success": True,
            "message": f"Resi {safe_resi} berhasil diproses",
            "data": {
                "resi": safe_resi,
                "tipe_pembayaran": payment_type,
                "waktu_scan": waktu_scan,
                "status": STATUS_SCANNED,
                "is_cod": payment_type == PAYMENT_COD,
                "mqtt_published": mqtt_connected,
                "next_action": "upload_foto"
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Scan resi error: {e}")
        return jsonify({
            "error": "Gagal memproses resi",
            "details": str(e)
        }), 500

@app.route('/upload_wajah/<resi>', methods=['POST'])
@rate_limit(max_requests=20, window=60)
def upload_wajah(resi):
    """Upload foto dengan security dan validation lengkap"""
    logger.info(f"Upload foto request for resi: {resi}")
    
    # Cek apakah request memiliki file
    if 'file' not in request.files and 'image' not in request.files:
        return jsonify({
            "error": "Tidak ada file yang diupload",
            "available_fields": list(request.files.keys()),
            "note": "Gunakan field 'file' atau 'image'"
        }), 400
    
    # Cari file di field yang tersedia
    file = None
    field_name = None
    
    for field in ['image', 'file']:
        if field in request.files:
            file = request.files[field]
            field_name = field
            break
    
    if not file or file.filename == '':
        return jsonify({"error": "File tidak ditemukan atau kosong"}), 400
    
    # Validasi nama file
    original_filename = file.filename
    sanitized_filename = sanitize_filename(original_filename)
    
    if sanitized_filename != original_filename:
        logger.warning(f"Filename sanitized: {original_filename} -> {sanitized_filename}")
    
    # Validasi ekstensi
    if not validate_file_extension(sanitized_filename):
        return jsonify({
            "error": "Format file tidak didukung",
            "allowed_extensions": list(ALLOWED_EXTENSIONS),
            "received_file": sanitized_filename
        }), 400
    
    # Validasi ukuran file
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            "error": f"File terlalu besar. Maksimal {MAX_FILE_SIZE/(1024*1024):.1f}MB",
            "file_size": file_size,
            "max_size": MAX_FILE_SIZE
        }), 400
    
    if file_size == 0:
        return jsonify({"error": "File kosong (0 bytes)"}), 400
    
    # Validasi resi
    if not validate_resi(resi):
        return jsonify({"error": "Nomor resi tidak valid"}), 400
    
    safe_resi = secure_filename(resi)
    
    try:
        # Buat folder resi jika belum ada
        resi_folder = os.path.join(BASE_FOLDER, safe_resi)
        os.makedirs(resi_folder, mode=0o755, exist_ok=True)
        
        # Generate nama file unik
        waktu_obj = datetime.now()
        waktu_str = waktu_obj.strftime("%Y-%m-%d %H:%M:%S")
        date_str = waktu_obj.strftime('%Y%m%d')
        time_str = waktu_obj.strftime('%H%M%S')
        unique_id = secrets.token_hex(8)
        
        # Ambil ekstensi yang aman
        file_ext = sanitized_filename.rsplit('.', 1)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            file_ext = 'jpg'  # Default jika ekstensi tidak valid
        
        nama_file = f"wajah_{safe_resi}_{date_str}_{time_str}_{unique_id}.{file_ext}"
        save_path = os.path.join(resi_folder, nama_file)
        
        # Simpan file dengan chunk untuk menghindari memory overload
        try:
            with open(save_path, 'wb') as f:
                chunk_size = 8192
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
        except IOError as e:
            logger.error(f"❌ Failed to save file: {e}")
            return jsonify({"error": "Gagal menyimpan file"}), 500
        
        # Verifikasi file tersimpan
        if not os.path.exists(save_path) or os.path.getsize(save_path) != file_size:
            logger.error(f"❌ File save verification failed: {save_path}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return jsonify({"error": "File gagal disimpan"}), 500
        
        logger.info(f"✅ File saved: {save_path} ({file_size} bytes)")
        
        # Update database
        with db_conn() as conn:
            cursor = conn.cursor()
            # Cek apakah resi sudah ada
            cursor.execute('SELECT id FROM pengiriman WHERE nomor_resi = ?', (safe_resi,))
            existing = cursor.fetchone()
        
            if existing:
                # Update existing
                cursor.execute('''
                    UPDATE pengiriman 
                    SET waktu_upload = ?, nama_foto = ?, path_foto = ?, status = ?, updated_at = ?
                    WHERE nomor_resi = ?
                ''', (waktu_str, nama_file, save_path, STATUS_MONITORING, waktu_str, safe_resi))
            else:
                # Insert new
                payment_type = get_payment_type(safe_resi)
                cursor.execute('''
                    INSERT INTO pengiriman 
                    (nomor_resi, tipe_pembayaran, waktu_scan, waktu_upload, nama_foto, path_foto, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (safe_resi, payment_type, waktu_str, waktu_str, nama_file, save_path, STATUS_MONITORING))
        
            conn.commit()
        
        # Publish ke MQTT
        if mqtt_connected:
            publish_mqtt_message(TOPIC_STATUS_OUT, {
                "event": "foto_uploaded",
                "resi": safe_resi,
                "filename": nama_file,
                "file_size": file_size,
                "timestamp": waktu_str,
                "message": f"Foto untuk {safe_resi} berhasil diupload"
            })
        
        return jsonify({
            "success": True,
            "message": "Foto berhasil diupload",
            "data": {
                "resi": safe_resi,
                "nama_file": nama_file,
                "original_filename": original_filename,
                "waktu_upload": waktu_str,
                "file_size": file_size,
                "file_path": save_path,
                "status": STATUS_MONITORING,
                "mqtt_published": mqtt_connected,
                "security_checks": {
                    "filename_sanitized": sanitized_filename != original_filename,
                    "extension_validated": file_ext in ALLOWED_EXTENSIONS,
                    "size_validated": file_size <= MAX_FILE_SIZE
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Upload error: {e}", exc_info=True)
        # Bersihkan file jika gagal
        if 'save_path' in locals() and os.path.exists(save_path):
            try:
                os.remove(save_path)
            except:
                pass
        return jsonify({
            "error": "Gagal mengupload file",
            "details": str(e)
        }), 500

@app.route('/update_status', methods=['POST'])
@rate_limit(max_requests=60, window=60)
def update_status():
    """Main logic untuk processing sensor data"""
    logger.info(f"Monitoring update from {request.remote_addr}")
    
    if not request.is_json:
        return jsonify({"error": "Content-Type harus application/json"}), 400
    
    data = request.get_json()
    
    # Validasi field wajib
    required_fields = ['resi', 'jarak', 'slot', 'durasi']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": f"Field berikut diperlukan: {', '.join(missing_fields)}"
        }), 400
    
    # Validasi dan parse data
    try:
        resi = str(data['resi']).strip()
        jarak = float(data['jarak'])
        slot = int(data['slot'])
        durasi = float(data['durasi'])
        tombol = int(data.get('tombol', 0))
        source = data.get('source', 'http')
    except (ValueError, TypeError) as e:
        return jsonify({
            "error": "Format data tidak valid",
            "details": str(e)
        }), 400
    
    # Validasi nilai
    if not validate_resi(resi):
        return jsonify({"error": "Nomor resi tidak valid"}), 400
    
    if not (0 <= jarak <= 500):
        return jsonify({"error": "Jarak harus antara 0-500 cm"}), 400
    
    if durasi < 0:
        return jsonify({"error": "Durasi tidak boleh negatif"}), 400
    
    if slot not in [0, 1]:
        return jsonify({"error": "Slot harus 0 (tertutup) atau 1 (terbuka)"}), 400
    
    if tombol not in [0, 1]:
        return jsonify({"error": "Tombol harus 0 (lepas) atau 1 (ditekan)"}), 400
    
    safe_resi = secure_filename(resi)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        waktu_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Ambil tipe pembayaran
        payment_type = get_payment_type(safe_resi)
        is_cod = payment_type == PAYMENT_COD
        
        # 2. Prediksi AI
        ai_result = predict_ai_status(jarak, durasi)
        prediksi_label = ai_result['prediction']
        confidence = ai_result['confidence']
        
        # 3. Logika berdasarkan payment type
        is_completed = False
        is_danger = False
        is_warning = False
        completed_reason = ""
        completed_by = ""
        mqtt_commands = []
        
        # SCENARIO A: COD
        if is_cod:
            if prediksi_label == 'aman':
                if slot == 0:
                    # Buka slot uang
                    result = send_mqtt_command(safe_resi, COMMAND_OPEN_SLOT, "AI aman: Buka slot uang")
                    if result['success']:
                        mqtt_commands.append(COMMAND_OPEN_SLOT)
                        completed_reason = "AI verifikasi aman, slot uang dibuka"
                else:
                    # Slot sudah terbuka, tutup dan buka pintu
                    send_mqtt_command(safe_resi, COMMAND_CLOSE_SLOT, "Slot terbuka: Tutup slot")
                    send_mqtt_command(safe_resi, COMMAND_OPEN_DOOR, "COD paid: Buka pintu")
                    mqtt_commands.extend([COMMAND_CLOSE_SLOT, COMMAND_OPEN_DOOR])
                    is_completed = True
                    completed_reason = "Pembayaran COD diterima"
                    completed_by = "cod_paid"
            
            elif prediksi_label == 'bahaya':
                is_danger = True
                send_mqtt_command(safe_resi, COMMAND_BUZZER_ON, "AI bahaya: Alarm")
                mqtt_commands.append(COMMAND_BUZZER_ON)
                completed_reason = "AI mendeteksi bahaya"
            
            elif prediksi_label == 'peringatan':
                is_warning = True
                completed_reason = "AI memberikan peringatan"
        
        # SCENARIO B: NON-COD
        else:
            if prediksi_label == 'aman':
                send_mqtt_command(safe_resi, COMMAND_OPEN_DOOR, f"{payment_type}: Buka pintu")
                mqtt_commands.append(COMMAND_OPEN_DOOR)
                is_completed = True
                completed_reason = f"Paket {payment_type}, pintu dibuka"
                completed_by = "non_cod_auto"
            
            elif prediksi_label == 'bahaya':
                is_danger = True
                completed_reason = f"AI mendeteksi bahaya untuk {payment_type}"
            
            elif prediksi_label == 'peringatan':
                is_warning = True
                completed_reason = f"AI memberikan peringatan untuk {payment_type}"
        
        # 4. Tombol override
        if tombol == 1:
            send_mqtt_command(safe_resi, COMMAND_OPEN_DOOR, "Tombol ditekan: Buka pintu")
            mqtt_commands.append(COMMAND_OPEN_DOOR)
            is_completed = True
            completed_reason = "Tombol konfirmasi ditekan"
            completed_by = "tombol_override"
        
        # 5. Tidak ada objek terdeteksi
        if jarak > 100 and not (is_completed or is_danger or is_warning):
            completed_reason = "Paket tidak terdeteksi"
            completed_by = "no_object"
        
        # 6. Tentukan status final
        status_final = STATUS_MONITORING
        if is_completed:
            status_final = STATUS_COMPLETED
        elif is_danger:
            status_final = STATUS_BAHAYA
        elif is_warning:
            status_final = STATUS_PERINGATAN
        
        # 7. Update database
        cursor.execute('''
            UPDATE pengiriman 
            SET jarak_paket = ?, durasi_objek = ?, slot_uang = ?, tombol_ditekan = ?,
                prediksi_ai = ?, confidence_ai = ?, status = ?, waktu_monitoring = ?,
                mqtt_last_update = ?, updated_at = ?, uang_diterima = ?,
                mqtt_commands_sent = mqtt_commands_sent + ?
            WHERE nomor_resi = ?
        ''', (jarak, durasi, slot, tombol, prediksi_label, confidence,
              status_final, waktu_log, waktu_log, waktu_log, slot == 1,
              len(mqtt_commands), safe_resi))
        
        if is_completed:
            cursor.execute('''
                UPDATE pengiriman 
                SET waktu_selesai = ?, alasan_selesai = ?, updated_at = ?
                WHERE nomor_resi = ?
            ''', (waktu_log, completed_reason, waktu_log, safe_resi))
        
        # 8. Log monitoring
        cursor.execute('''
            INSERT INTO monitoring_log 
            (resi, waktu_log, jarak_paket, durasi_objek, slot_uang, tombol_ditekan, 
             prediksi_ai, confidence_ai, source, client_ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (safe_resi, waktu_log, jarak, durasi, slot, tombol,
              prediksi_label, confidence, source, request.remote_addr,
              request.user_agent.string[:200]))
        
        conn.commit()
        
        # 9. Publish AI result ke MQTT
        if mqtt_connected:
            publish_mqtt_message(TOPIC_AI_RESULT, {
                "resi": safe_resi,
                "ai_prediction": prediksi_label,
                "confidence": confidence,
                "status": status_final,
                "payment_type": payment_type,
                "timestamp": waktu_log,
                "commands_sent": mqtt_commands
            })
        
        # 10. Response
        response_data = {
            "resi": safe_resi,
            "payment_info": {
                "type": payment_type,
                "is_cod": is_cod
            },
            "sensor_data": {
                "jarak": jarak,
                "durasi": durasi,
                "slot": slot,
                "tombol": tombol
            },
            "ai_result": {
                "prediction": prediksi_label,
                "confidence": confidence,
                "model_available": ai_result['model_available']
            },
            "status": status_final,
            "actions_taken": mqtt_commands,
            "timestamp": waktu_log
        }
        
        if is_danger:
            response_message = f"🚨 BAHAYA terdeteksi untuk {payment_type}"
        elif is_completed:
            response_message = f"✅ Transaksi {payment_type} selesai"
        else:
            response_message = f"⏳ Monitoring {payment_type} berjalan"
        
        return jsonify({
            "success": True,
            "message": response_message,
            "data": response_data
        }), 200
    except Exception as e:
        logger.error(f"❌ Update status error: {e}", exc_info=True)
        return jsonify({
            "error": "Gagal memproses data sensor",
            "details": str(e)
        }), 500

        
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

# --- MQTT CONTROL ROUTES ---
@app.route('/mqtt/send_command', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def mqtt_send_command():
    """Kirim perintah langsung via MQTT"""
    if not request.is_json:
        return jsonify({"error": "Content-Type harus application/json"}), 400
    
    data = request.get_json()
    resi = data.get('resi', '').strip()
    command = data.get('command', '').strip()
    reason = data.get('reason', 'Manual command')
    
    if not resi or not command:
        return jsonify({"error": "resi dan command diperlukan"}), 400
    
    # Validasi command
    valid_commands = [
        COMMAND_OPEN_SLOT, COMMAND_CLOSE_SLOT,
        COMMAND_OPEN_DOOR, COMMAND_CLOSE_DOOR,
        COMMAND_BUZZER_ON, COMMAND_BUZZER_OFF,
        COMMAND_LED_ON, COMMAND_LED_OFF,
        COMMAND_VERIFY_COD, COMMAND_RESET
    ]
    
    if command not in valid_commands:
        return jsonify({
            "error": "Command tidak valid",
            "valid_commands": valid_commands
        }), 400
    
    try:
        # Kirim command dengan timeout
        result = send_mqtt_command(resi, command, reason, timeout=10)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": f"Perintah {command} berhasil dikirim",
                "data": result
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": f"Gagal mengirim perintah {command}",
                "data": result
            }), 500
            
    except Exception as e:
        logger.error(f"❌ MQTT send command error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/mqtt/status', methods=['GET'])
def mqtt_status():
    """Get status MQTT connection"""
    mqtt_stats = {
        "connected": mqtt_connected,
        "broker": f"{MQTT_BROKER}:{MQTT_PORT}",
        "client_id": mqtt_client._client_id.decode() if mqtt_client and hasattr(mqtt_client, '_client_id') else "unknown",
        "topics": {
            "subscribed": [TOPIC_SENSOR_IN, TOPIC_STATUS_OUT, f"{TOPIC_COMMAND_OUT}/response"],
            "published": [TOPIC_COMMAND_OUT, TOPIC_STATUS_OUT, TOPIC_AI_RESULT, TOPIC_HEARTBEAT]
        },
        "qos": MQTT_QOS,
        "retain": MQTT_RETAIN
    }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Message statistics
        cursor.execute('''
            SELECT direction, COUNT(*) as count,
                   MIN(waktu_log) as first_message,
                   MAX(waktu_log) as last_message
            FROM mqtt_logs
            GROUP BY direction
        ''')

        messages = {}
        for row in cursor.fetchall():
            messages[row['direction']] = {
                "count": row['count'],
                "first_message": row['first_message'],
                "last_message": row['last_message']
            }

        # Recent errors
        cursor.execute('''
            SELECT waktu_log, topic, error_message
            FROM mqtt_logs
            WHERE error_message IS NOT NULL
            ORDER BY waktu_log DESC
            LIMIT 10
        ''')
        recent_errors = [dict(row) for row in cursor.fetchall()]

        mqtt_stats.update({
            "message_statistics": messages,
            "recent_errors": recent_errors,
            "database_stats": {
                "total_logs": sum(msg['count'] for msg in messages.values()),
                "last_check": datetime.now().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"❌ Error getting MQTT stats: {e}", exc_info=True)

    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    return jsonify({
        "success": True,
        "mqtt": mqtt_stats
    }), 200

# --- PAYMENT ROUTES ---
@app.route('/set_payment/<resi>', methods=['POST'])
@rate_limit(max_requests=20, window=60)
def set_payment_type(resi):
    """Set tipe pembayaran"""
    if not request.is_json:
        return jsonify({"error": "Content-Type harus application/json"}), 400
    
    data = request.get_json()
    payment_type = data.get('tipe_pembayaran', '').upper()
    
    valid_types = [PAYMENT_COD, PAYMENT_NON_COD, PAYMENT_TRANSFER, PAYMENT_LUNAS]
    if payment_type not in valid_types:
        return jsonify({
            "error": "Tipe pembayaran tidak valid",
            "valid_types": valid_types
        }), 400
    
    safe_resi = secure_filename(resi)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        waktu_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            UPDATE pengiriman 
            SET tipe_pembayaran = ?, updated_at = ?
            WHERE nomor_resi = ?
        ''', (payment_type, waktu_update, safe_resi))
        
        if cursor.rowcount == 0:
            # Resi belum ada, buat baru
            cursor.execute('''
                INSERT INTO pengiriman 
                (nomor_resi, tipe_pembayaran, waktu_scan, status)
                VALUES (?, ?, ?, ?)
            ''', (safe_resi, payment_type, waktu_update, STATUS_PENDING))
        
        conn.commit()
        
        # Publish ke MQTT
        if mqtt_connected:
            publish_mqtt_message(TOPIC_STATUS_OUT, {
                "event": "payment_type_changed",
                "resi": safe_resi,
                "payment_type": payment_type,
                "timestamp": waktu_update
            })
        
        return jsonify({
            "success": True,
            "message": f"Tipe pembayaran diubah menjadi {payment_type}",
            "data": {
                "resi": safe_resi,
                "tipe_pembayaran": payment_type,
                "is_cod": payment_type == PAYMENT_COD,
                "waktu_update": waktu_update
            }
        }), 200
    except Exception as e:
        logger.error(f"❌ Set payment error: {e}")
        return jsonify({"error": str(e)}), 500

        
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

@app.route('/get_payment/<resi>', methods=['GET'])
def get_payment_info(resi):
    """Get informasi pembayaran"""
    safe_resi = secure_filename(resi)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT nomor_resi, tipe_pembayaran, status, waktu_scan, 
                   waktu_upload, waktu_monitoring, waktu_selesai,
                   jarak_paket, durasi_objek, slot_uang, tombol_ditekan,
                   prediksi_ai, confidence_ai, uang_diterima,
                   mqtt_commands_sent, mqtt_last_update,
                   alasan_selesai
            FROM pengiriman 
            WHERE nomor_resi = ?
        ''', (safe_resi,))
        
        result = cursor.fetchone()
        
        if not result:
            return jsonify({"error": "Resi tidak ditemukan"}), 404
        
        data = dict(result)
        
        return jsonify({
            "success": True,
            "data": {
                "payment_info": {
                    "resi": data['nomor_resi'],
                    "type": data['tipe_pembayaran'],
                    "status": data['status'],
                    "is_cod": data['tipe_pembayaran'] == PAYMENT_COD,
                    "cash_received": bool(data['uang_diterima']),
                    "completion_reason": data['alasan_selesai']
                },
                "timestamps": {
                    "scan": data['waktu_scan'],
                    "upload": data['waktu_upload'],
                    "monitoring": data['waktu_monitoring'],
                    "completed": data['waktu_selesai']
                },
                "sensor_data": {
                    "last_distance": data['jarak_paket'],
                    "last_duration": data['durasi_objek'],
                    "last_slot_status": data['slot_uang'],
                    "last_button_status": data['tombol_ditekan']
                },
                "ai_data": {
                    "last_prediction": data['prediksi_ai'],
                    "last_confidence": data['confidence_ai']
                },
                "mqtt_info": {
                    "connected": mqtt_connected,
                    "commands_sent": data['mqtt_commands_sent'],
                    "last_update": data['mqtt_last_update']
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"❌ Get payment info error: {e}")
        return jsonify({"error": str(e)}), 500

        
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

# --- DATA RETRIEVAL ROUTES ---
@app.route('/list_resi', methods=['GET'])
def list_resi():
    """Dapatkan semua data pengiriman"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get query parameters
        status_filter = request.args.get('status')
        payment_filter = request.args.get('payment_type')
        limit = min(int(request.args.get('limit', 100)), 500)  # Max 500
        offset = int(request.args.get('offset', 0))
        
        query = '''
            SELECT nomor_resi, tipe_pembayaran, status, waktu_scan, waktu_upload,
                   waktu_monitoring, waktu_selesai, jarak_paket, durasi_objek,
                   slot_uang, tombol_ditekan, prediksi_ai, confidence_ai,
                   uang_diterima, mqtt_commands_sent, mqtt_last_update
            FROM pengiriman 
            WHERE 1=1
        '''
        params = []
        
        if status_filter:
            query += ' AND status = ?'
            params.append(status_filter)
        
        if payment_filter:
            query += ' AND tipe_pembayaran = ?'
            params.append(payment_filter)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        
        # Get total count
        count_query = 'SELECT COUNT(*) as total FROM pengiriman WHERE 1=1'
        count_params = []
        
        if status_filter:
            count_query += ' AND status = ?'
            count_params.append(status_filter)
        
        if payment_filter:
            count_query += ' AND tipe_pembayaran = ?'
            count_params.append(payment_filter)
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']
        
        
        return jsonify({
            "success": True,
            "data": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": total > (offset + limit),
                "results": results
            }
        }), 200
    except Exception as e:
        logger.error(f"❌ List resi error: {e}")
        return jsonify({"error": str(e)}), 500

        
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

@app.route('/stats', methods=['GET'])
def get_stats():
    """Statistik sistem lengkap"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Overall statistics
        cursor.execute('SELECT COUNT(*) as total FROM pengiriman')
        total_resi = cursor.fetchone()['total']
        
        cursor.execute(f'SELECT COUNT(*) as completed FROM pengiriman WHERE status = ?', (STATUS_COMPLETED,))
        completed = cursor.fetchone()['completed']
        
        # Payment statistics
        cursor.execute('''
            SELECT tipe_pembayaran, COUNT(*) as count,
                   SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN uang_diterima = 1 THEN 1 ELSE 0 END) as cash_received
            FROM pengiriman 
            GROUP BY tipe_pembayaran
        ''', (STATUS_COMPLETED,))
        
        payment_stats = {}
        for row in cursor.fetchall():
            payment_stats[row['tipe_pembayaran']] = dict(row)
        
        # AI statistics
        cursor.execute('''
            SELECT prediksi_ai, COUNT(*) as count, AVG(confidence_ai) as avg_confidence
            FROM pengiriman 
            WHERE prediksi_ai IS NOT NULL
            GROUP BY prediksi_ai
        ''')
        
        ai_stats = {}
        for row in cursor.fetchall():
            ai_stats[row['prediksi_ai']] = dict(row)
        
        # MQTT statistics
        cursor.execute('SELECT COUNT(*) as total FROM mqtt_logs')
        mqtt_total = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as today FROM mqtt_logs WHERE DATE(waktu_log) = DATE("now")')
        mqtt_today = cursor.fetchone()['today']
        
        # System health
        cursor.execute('''
            SELECT service_name, status, MAX(waktu_check) as last_check
            FROM system_health 
            GROUP BY service_name
        ''')
        
        system_health = {}
        for row in cursor.fetchall():
            system_health[row['service_name']] = dict(row)
        
        
        return jsonify({
            "success": True,
            "data": {
                "overall": {
                    "total_resi": total_resi,
                    "completed": completed,
                    "completion_rate": completed / total_resi if total_resi > 0 else 0
                },
                "payment_statistics": payment_stats,
                "ai_statistics": ai_stats,
                "mqtt_statistics": {
                    "total_messages": mqtt_total,
                    "today_messages": mqtt_today,
                    "current_connection": mqtt_connected
                },
                "system_health": system_health,
                "timestamp": datetime.now().isoformat()
            }
        }), 200
    except Exception as e:
        logger.error(f"❌ Get stats error: {e}")
        return jsonify({"error": str(e)}), 500

        
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

# --- UTILITY ROUTES ---
@app.route('/system/health', methods=['GET'])
def system_health():
    """Health check endpoint untuk monitoring"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # Database check
    conn = None
    try:
        start_t = time.time()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_time = (time.time() - start_t) * 1000

        health_status["checks"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time, 2)
        }

    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    # MQTT check
    health_status["checks"]["mqtt"] = {
        "status": "healthy" if mqtt_connected else "unhealthy",
        "connected": mqtt_connected,
        "broker": f"{MQTT_BROKER}:{MQTT_PORT}"
    }
    if not mqtt_connected:
        health_status["status"] = "degraded"

    # AI model check
    health_status["checks"]["ai_model"] = {
        "status": "healthy" if best_model is not None else "unhealthy",
        "loaded": best_model is not None,
        "scaler_loaded": scaler is not None
    }
    if best_model is None:
        health_status["status"] = "degraded"

    # Disk space check
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        health_status["checks"]["disk"] = {
            "status": "healthy" if (free / total) > 0.1 else "warning",
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "free_percent": round((free / total) * 100, 2)
        }
        if (free / total) < 0.1:
            health_status["status"] = "warning"
    except Exception as e:
        health_status["checks"]["disk"] = {"status": "unknown", "error": str(e)}

    return jsonify(health_status), 200

@app.route('/debug/upload_fields', methods=['POST'])
def debug_upload_fields():
    """Debug endpoint untuk melihat field upload"""
    result = {
        "method": request.method,
        "content_type": request.content_type,
        "content_length": request.content_length,
        "form_fields": list(request.form.keys()),
        "files_fields": list(request.files.keys())
    }
    
    files_info = []
    for field_name, file in request.files.items():
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        files_info.append({
            "field_name": field_name,
            "filename": file.filename,
            "content_type": file.content_type,
            "content_length": file_size
        })
    
    result["files_info"] = files_info
    
    return jsonify(result), 200


# --- DASHBOARD ROUTES (Polling + SSE) ---
@app.route('/dashboard/latest', methods=['GET'])
@rate_limit(max_requests=120, window=60)
def dashboard_latest():
    """Ambil event MQTT terakhir untuk dashboard (polling)."""
    with _event_cond:
        latest = list(_event_buf)[-50:]
    return jsonify({
        'success': True,
        'count': len(latest),
        'events': latest
    }), 200


@app.route('/dashboard/stream', methods=['GET'])
@rate_limit(max_requests=120, window=60)
def dashboard_stream():
    """Realtime stream via Server-Sent Events (tanpa websocket)."""
    from flask import Response

    def gen():
        # snapshot awal
        with _event_cond:
            snap = list(_event_buf)[-10:]
            last_len = len(_event_buf)
        for evt in snap:
            yield f"data: {json.dumps(evt, default=str)}\n\n"

        while True:
            with _event_cond:
                _event_cond.wait(timeout=25)
                buf = list(_event_buf)
            if len(buf) > last_len:
                for evt in buf[last_len:]:
                    yield f"data: {json.dumps(evt, default=str)}\n\n"
                last_len = len(buf)
            else:
                yield ": ping\n\n"

    return Response(gen(), mimetype='text/event-stream')

# --- ERROR HANDLERS ---
@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        "error": "Bad Request",
        "message": "Permintaan tidak valid"
    }), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not Found",
        "message": "Endpoint tidak ditemukan"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method Not Allowed",
        "message": "Method tidak diizinkan untuk endpoint ini"
    }), 405

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "error": "Request Too Large",
        "message": f"File terlalu besar. Maksimal {MAX_FILE_SIZE/(1024*1024):.1f}MB"
    }), 413

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        "error": "Too Many Requests",
        "message": "Rate limit exceeded",
        "retry_after": 60
    }), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Server error: {error}")
    return jsonify({
        "error": "Internal Server Error",
        "message": "Terjadi kesalahan pada server"
    }), 500

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    try:
        # Import tambahan untuk system monitoring
        import socket
        import psutil
        
        # Setup
        setup_folders()
        init_db()
        
        # Catat waktu start
        start_time = time.time()
        
        # Initialize MQTT
        logger.info("🚀 Starting Receiver API v6.0...")
        mqtt_success = init_mqtt_client()
        
        # Start health check thread
        if mqtt_success:
            health_thread = threading.Thread(target=mqtt_health_check, daemon=True)
            health_thread.start()
            logger.info("✅ MQTT health check thread started")
        
        # Startup banner
        logger.info("=" * 70)
        logger.info("🚀 RECEIVER API - Sistem Pengiriman dengan MQTT v6.0")
        logger.info("📁 Base Folder: %s", os.path.abspath(BASE_FOLDER))
        logger.info("🗄️ Database: %s", os.path.abspath(DB_NAME))
        logger.info("📡 MQTT Broker: %s:%s", MQTT_BROKER, MQTT_PORT)
        logger.info("🔐 Security Features: Rate limiting, Input validation, File sanitization")
        logger.info("🤖 AI Model: %s", "LOADED" if best_model else "NOT LOADED")
        logger.info("💰 Payment System: COD & Non-COD dengan logika otomatis")
        logger.info("🌐 Host: 0.0.0.0:5000")
        logger.info("📊 Endpoints:")
        logger.info("   • GET  /                 - System status")
        logger.info("   • POST /scan_resi        - Scan resi")
        logger.info("   • POST /upload_wajah/<resi> - Upload foto")
        logger.info("   • POST /update_status    - Main logic processing")
        logger.info("   • POST /mqtt/send_command - Send MQTT command")
        logger.info("   • GET  /system/health    - Health check")
        logger.info("=" * 70)
        
        # Start Flask dengan production settings
        app.run(
            host='0.0.0.0',
            port=5000, 
            debug=False,
            threaded=True,
            use_reloader=False
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        if mqtt_client:
            # Publish offline status
            publish_mqtt_message(TOPIC_STATUS_OUT, {
                "status": "offline",
                "service": "receiver_api",
                "timestamp": datetime.now().isoformat(),
                "uptime": time.time() - start_time
            }, retain=True)
            
            # Stop MQTT
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        
        logger.info("✅ Server stopped gracefully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}", exc_info=True)
        raise
