# database.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manajemen database SQLite untuk J-MailBox"""
    
    def __init__(self, db_path='jmailbox.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Membuat koneksi database dengan row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Inisialisasi semua tabel database"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                nama_lengkap TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS master_data (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                is_default BOOLEAN DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS packages (
                id TEXT PRIMARY KEY,
                resi TEXT UNIQUE NOT NULL,
                courier TEXT NOT NULL,
                nama_penerima TEXT NOT NULL,
                alamat TEXT NOT NULL,
                telepon TEXT NOT NULL,
                email TEXT,
                metode_pembayaran TEXT NOT NULL,
                status TEXT NOT NULL,
                tanggal DATE NOT NULL,
                nominal TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                master_data_id TEXT,
                created_by INTEGER,
                FOREIGN KEY (master_data_id) REFERENCES master_data(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_value REAL NOT NULL,
                status TEXT NOT NULL,
                probability REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS mqtt_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                direction TEXT NOT NULL, -- 'incoming' or 'outgoing'
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        ]
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_packages_status ON packages(status)",
            "CREATE INDEX IF NOT EXISTS idx_packages_created ON packages(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_master_data_default ON master_data(is_default)",
            "CREATE INDEX IF NOT EXISTS idx_security_timestamp ON security_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_mqtt_topic ON mqtt_messages(topic)",
            "CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_logs(timestamp)"
        ]
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create tables
            for table_sql in tables:
                cursor.execute(table_sql)
            
            # Create indexes
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            # Insert default settings
            default_settings = [
                ('theme', 'dark'),
                ('mqtt_broker', MQTT_BROKER),
                ('mqtt_port', str(MQTT_PORT)),
                ('mqtt_username', MQTT_USERNAME),
                ('mqtt_password', MQTT_PASSWORD),
                ('sensor_threshold_warning', '15'),
                ('sensor_threshold_danger', '10'),
                ('cod_slots', '3')
            ]
            
            cursor.executemany(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                default_settings
            )
            
            # Insert default admin user if not exists
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE username = 'admin'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """
                    INSERT INTO users 
                    (username, email, nama_lengkap, password_hash, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ('admin', 'admin@jmailbox.com', 'Administrator', 
                     'pbkdf2:sha256:260000$...', 'admin')
                )
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    # ===== USER MANAGEMENT =====
    def create_user(self, username: str, email: str, nama_lengkap: str, 
                   password_hash: str, role: str = 'user') -> bool:
        """Membuat user baru"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users 
                (username, email, nama_lengkap, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, nama_lengkap, password_hash, role)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Create user error: {e}")
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Mendapatkan user berdasarkan username"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            )
            user = cursor.fetchone()
            conn.close()
            return dict(user) if user else None
        except sqlite3.Error as e:
            logger.error(f"Get user error: {e}")
            return None
    
    def update_user_login(self, user_id: int):
        """Update last login timestamp"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Update login error: {e}")
    
    # ===== MASTER DATA MANAGEMENT =====
    def get_master_data(self, user_id: Optional[int] = None) -> List[Dict]:
        """Mendapatkan semua master data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute(
                    """
                    SELECT * FROM master_data 
                    WHERE created_by = ? 
                    ORDER BY created_at DESC
                    """,
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM master_data ORDER BY created_at DESC"
                )
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get master data error: {e}")
            return []
    
    def add_master_data(self, master_data: Dict) -> bool:
        """Menambahkan master data baru"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # If setting as default, unset others
            if master_data.get('is_default'):
                cursor.execute(
                    "UPDATE master_data SET is_default = 0 WHERE created_by = ?",
                    (master_data['created_by'],)
                )
            
            cursor.execute(
                """
                INSERT INTO master_data 
                (id, name, address, phone, email, is_default, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    master_data['id'],
                    master_data['name'],
                    master_data['address'],
                    master_data['phone'],
                    master_data.get('email', ''),
                    master_data.get('is_default', False),
                    master_data['created_by']
                )
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Add master data error: {e}")
            return False
    
    def update_master_data(self, master_id: str, updates: Dict) -> bool:
        """Update master data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # If setting as default, unset others for this user
            if updates.get('is_default'):
                cursor.execute(
                    """
                    UPDATE master_data SET is_default = 0 
                    WHERE created_by = (SELECT created_by FROM master_data WHERE id = ?)
                    """,
                    (master_id,)
                )
            
            set_clause = []
            params = []
            for key, value in updates.items():
                if key != 'id':
                    set_clause.append(f"{key} = ?")
                    params.append(value)
            
            params.append(master_id)
            query = f"""
                UPDATE master_data 
                SET {', '.join(set_clause)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Update master data error: {e}")
            return False
    
    def delete_master_data(self, master_id: str) -> bool:
        """Menghapus master data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM master_data WHERE id = ?",
                (master_id,)
            )
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Delete master data error: {e}")
            return False
    
    # ===== PACKAGES MANAGEMENT =====
    def get_packages(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Mendapatkan paket dengan filter"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM packages WHERE 1=1"
            params = []
            
            if filters:
                if filters.get('status') and filters['status'] != 'All':
                    query += " AND status = ?"
                    params.append(filters['status'])
                
                if filters.get('metode_pembayaran') and filters['metode_pembayaran'] != 'All':
                    query += " AND metode_pembayaran = ?"
                    params.append(filters['metode_pembayaran'])
                
                if filters.get('search'):
                    query += " AND (resi LIKE ? OR nama_penerima LIKE ?)"
                    search_term = f"%{filters['search']}%"
                    params.extend([search_term, search_term])
            
            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get packages error: {e}")
            return []
    
    def add_package(self, package: Dict) -> bool:
        """Menambahkan paket baru"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO packages 
                (id, resi, courier, nama_penerima, alamat, telepon, email,
                 metode_pembayaran, status, tanggal, nominal, master_data_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package['id'],
                    package['resi'],
                    package['courier'],
                    package['nama_penerima'],
                    package['alamat'],
                    package['telepon'],
                    package.get('email', ''),
                    package['metode_pembayaran'],
                    package['status'],
                    package['tanggal'],
                    package.get('nominal', ''),
                    package.get('master_data_id'),
                    package.get('created_by')
                )
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Add package error: {e}")
            return False
    
    def update_package_status(self, package_id: str, status: str) -> bool:
        """Update status paket"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE packages 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, package_id)
            )
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Update package status error: {e}")
            return False
    
    # ===== SECURITY MANAGEMENT =====
    def add_security_log(self, sensor_value: float, status: str, 
                        probability: float, user_id: Optional[int] = None):
        """Menambahkan log keamanan"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO security_logs 
                (sensor_value, status, probability, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (sensor_value, status, probability, user_id)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Add security log error: {e}")
    
    def get_recent_security_logs(self, limit: int = 10) -> List[Dict]:
        """Mendapatkan log keamanan terbaru"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM security_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (limit,)
            )
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get security logs error: {e}")
            return []
    
    # ===== MQTT MANAGEMENT =====
    def save_mqtt_message(self, topic: str, payload: str, direction: str):
        """Menyimpan pesan MQTT"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mqtt_messages (topic, payload, direction)
                VALUES (?, ?, ?)
                """,
                (topic, json.dumps(payload) if isinstance(payload, dict) else payload, 
                 direction)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Save MQTT message error: {e}")
    
    def get_mqtt_messages(self, topic: Optional[str] = None, 
                         limit: int = 50) -> List[Dict]:
        """Mendapatkan pesan MQTT"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if topic:
                cursor.execute(
                    """
                    SELECT * FROM mqtt_messages 
                    WHERE topic = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (topic, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM mqtt_messages 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                try:
                    row_dict['payload'] = json.loads(row_dict['payload'])
                except:
                    pass
                results.append(row_dict)
            
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get MQTT messages error: {e}")
            return []
    
    # ===== SETTINGS MANAGEMENT =====
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Mendapatkan setting"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                try:
                    return json.loads(result[0])
                except:
                    return result[0]
            return default
        except sqlite3.Error as e:
            logger.error(f"Get setting error: {e}")
            return default
    
    def update_setting(self, key: str, value: Any) -> bool:
        """Update setting"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
                """,
                (key, value_str)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Update setting error: {e}")
            return False
    
    # ===== ACTIVITY LOGS =====
    def log_activity(self, user_id: Optional[int], action: str, 
                    details: Optional[str] = None, ip_address: Optional[str] = None):
        """Mencatat aktivitas user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO activity_logs 
                (user_id, action, details, ip_address)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, action, details, ip_address)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Log activity error: {e}")
    
    def get_activity_logs(self, user_id: Optional[int] = None, 
                         limit: int = 50) -> List[Dict]:
        """Mendapatkan log aktivitas"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute(
                    """
                    SELECT al.*, u.username, u.nama_lengkap
                    FROM activity_logs al
                    LEFT JOIN users u ON al.user_id = u.id
                    WHERE al.user_id = ?
                    ORDER BY al.timestamp DESC
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT al.*, u.username, u.nama_lengkap
                    FROM activity_logs al
                    LEFT JOIN users u ON al.user_id = u.id
                    ORDER BY al.timestamp DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get activity logs error: {e}")
            return []
    
    # ===== STATISTICS =====
    def get_statistics(self, user_id: Optional[int] = None) -> Dict:
        """Mendapatkan statistik"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Package statistics
            if user_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM packages WHERE created_by = ?",
                    (user_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM packages")
            stats['total_packages'] = cursor.fetchone()[0]
            
            if user_id:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM packages 
                    WHERE created_by = ? AND status = 'Selesai'
                    """,
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM packages WHERE status = 'Selesai'"
                )
            stats['completed_packages'] = cursor.fetchone()[0]
            
            # Master data statistics
            if user_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM master_data WHERE created_by = ?",
                    (user_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM master_data")
            stats['total_master_data'] = cursor.fetchone()[0]
            
            # Recent security alerts
            cursor.execute(
                """
                SELECT COUNT(*) FROM security_logs 
                WHERE status IN ('danger', 'warning')
                AND timestamp > datetime('now', '-24 hours')
                """
            )
            stats['recent_alerts'] = cursor.fetchone()[0]
            
            # MQTT connection status
            cursor.execute(
                """
                SELECT COUNT(*) FROM mqtt_messages 
                WHERE direction = 'incoming'
                AND timestamp > datetime('now', '-5 minutes')
                """
            )
            stats['mqtt_active'] = cursor.fetchone()[0] > 0
            
            conn.close()
            return stats
        except sqlite3.Error as e:
            logger.error(f"Get statistics error: {e}")
            return {}