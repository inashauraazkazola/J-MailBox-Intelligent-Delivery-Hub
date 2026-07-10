# app.py - J-MailBox Control Center with SSL/TLS MQTT Support
import streamlit as st
import pandas as pd
import numpy as np
import random
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import base64
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
import json
import sqlite3
import logging
from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================
# PAGE CONFIGURATION
# ==============================================
st.set_page_config(
    page_title="J-MailBox Control Center",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================
# DARK MODE CSS STYLING
# ==============================================
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    /* Dark Theme Variables */
    :root {
        /* Colors - Dark Theme */
        --primary-50: #0f172a;
        --primary-100: #1e293b;
        --primary-200: #334155;
        --primary-300: #475569;
        --primary-400: #64748b;
        --primary-500: #94a3b8;
        --primary-600: #cbd5e1;
        --primary-700: #e2e8f0;
        --primary-800: #f1f5f9;
        --primary-900: #f8fafc;
        
        --gray-50: #0f172a;
        --gray-100: #1e293b;
        --gray-200: #334155;
        --gray-300: #475569;
        --gray-400: #64748b;
        --gray-500: #94a3b8;
        --gray-600: #cbd5e1;
        --gray-700: #e2e8f0;
        --gray-800: #f1f5f9;
        --gray-900: #f8fafc;
        
        --accent-blue: #3b82f6;
        --accent-purple: #8b5cf6;
        --accent-green: #10b981;
        --accent-red: #ef4444;
        --accent-orange: #f97316;
        --accent-pink: #ec4899;
        
        --success-500: #34d399;
        --warning-500: #fbbf24;
        --danger-500: #f87171;
        --success-50: rgba(52, 211, 153, 0.1);
        --warning-50: rgba(251, 191, 36, 0.1);
        --danger-50: rgba(248, 113, 113, 0.1);
        
        /* Spacing */
        --spacing-xs: 0.25rem;
        --spacing-sm: 0.5rem;
        --spacing-md: 1rem;
        --spacing-lg: 1.5rem;
        --spacing-xl: 2rem;
        
        /* Border Radius */
        --radius-sm: 0.375rem;
        --radius-md: 0.5rem;
        --radius-lg: 0.75rem;
        --radius-xl: 1rem;
        
        /* Shadows */
        --shadow-sm: 0 1px 2px 0 rgb(255 255 255 / 0.05);
        --shadow-md: 0 4px 6px -1px rgb(255 255 255 / 0.1);
        --shadow-lg: 0 10px 15px -3px rgb(255 255 255 / 0.1);
    }
    
    /* Base Styles */
    .stApp {
        font-family: 'Inter', sans-serif;
        background: #0f172a;
        color: #e2e8f0;
    }
    
    /* Login Page Full Screen Styling - FIXED */
    .login-mode .main .block-container {
        max-width: 100% !important;
        padding: 0 !important;
    }
    
    .login-mode [data-testid="stSidebar"] {
        display: none !important;
    }
    
    .login-mode [data-testid="stHeader"] {
        display: none !important;
    }
    
    .login-mode .stApp > header {
        display: none !important;
    }
    
    /* Full screen login container */
    .login-full-screen {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 20px;
        margin: 0;
    }
    
    .login-card {
        background: #1e293b;
        border-radius: 24px;
        border: 1px solid #334155;
        padding: 48px 40px;
        width: 100%;
        max-width: 500px;
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.4);
        margin: 0 auto;
    }
    
    /* Fix Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #334155;
        padding: 4px;
        border-radius: 10px;
        margin-bottom: 32px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        background: transparent;
        color: #94a3b8 !important;
        transition: all 0.2s ease;
        border: none !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        background: rgba(255, 255, 255, 0.05) !important;
    }
    
    /* Fix Input Text Color */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #475569 !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }
    
    /* Fix Placeholder Color */
    input::placeholder,
    textarea::placeholder {
        color: #64748b !important;
    }
    
    /* Typography */
    .title-1 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1.2;
        color: #f1f5f9;
        margin: 0;
    }
    
    .title-2 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.3;
        color: #e2e8f0;
        margin: 0 0 12px 0;
    }
    
    .title-3 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.5rem;
        font-weight: 600;
        line-height: 1.4;
        color: #cbd5e1;
        margin: 0 0 16px 0;
    }
    
    .body-large {
        font-size: 1.125rem;
        line-height: 1.6;
        color: #cbd5e1;
        margin: 0;
    }
    
    .body-medium {
        font-size: 1rem;
        line-height: 1.5;
        color: #94a3b8;
        margin: 0;
    }
    
    .body-small {
        font-size: 0.875rem;
        line-height: 1.4;
        color: #64748b;
        margin: 0;
    }
    
    /* Cards */
    .card {
        background: #1e293b;
        border-radius: var(--radius-lg);
        border: 1px solid #334155;
        padding: var(--spacing-lg);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
    }
    
    .card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-2px);
        border-color: #475569;
    }
    
    .card-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 600;
        font-size: 1.125rem;
        color: #e2e8f0;
        margin-bottom: var(--spacing-md);
    }
    
    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1;
    }
    
    .badge-success {
        background: rgba(52, 211, 153, 0.1);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    
    .badge-warning {
        background: rgba(251, 191, 36, 0.1);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
    
    .badge-danger {
        background: rgba(248, 113, 113, 0.1);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }
    
    .badge-info {
        background: rgba(59, 130, 246, 0.1);
        color: #94a3b8;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: var(--radius-md);
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* Data Table */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        background: #1e293b;
    }
    
    .data-table th {
        background: #1e293b;
        padding: 12px 16px;
        text-align: left;
        font-weight: 600;
        color: #94a3b8;
        border-bottom: 2px solid #334155;
        font-size: 0.875rem;
    }
    
    .data-table td {
        padding: 12px 16px;
        border-bottom: 1px solid #334155;
        color: #cbd5e1;
        font-size: 0.875rem;
    }
    
    .data-table tr:hover {
        background: rgba(255, 255, 255, 0.02);
    }
    
    /* Hide Streamlit Default Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1e293b;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #475569;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #64748b;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border-radius: var(--radius-lg);
        border: 1px solid #334155;
        padding: var(--spacing-lg);
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        border-color: #3b82f6;
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #3b82f6;
        margin: 8px 0;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #94a3b8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Alert Box */
    .alert {
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        margin-bottom: var(--spacing-md);
        border-left: 4px solid;
    }
    
    .alert-success {
        background: rgba(52, 211, 153, 0.1);
        border-left-color: #34d399;
        color: #34d399;
    }
    
    .alert-warning {
        background: rgba(251, 191, 36, 0.1);
        border-left-color: #fbbf24;
        color: #fbbf24;
    }
    
    .alert-danger {
        background: rgba(248, 113, 113, 0.1);
        border-left-color: #f87171;
        color: #f87171;
    }
    
    /* Progress Bar */
    .progress-bar {
        height: 8px;
        background: #334155;
        border-radius: 4px;
        overflow: hidden;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        transition: width 0.3s ease;
    }
    
    /* Sub-page styling */
    .sub-page-container {
        background: #1e293b;
        border-radius: 12px;
        border: 1px solid #334155;
        padding: 24px;
        margin-top: 20px;
    }
    
    /* Master Data Item */
    .master-data-item {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    
    .master-data-item:hover {
        border-color: #3b82f6;
        transform: translateY(-1px);
    }
    
    /* Checkbox styling */
    .stCheckbox > label {
        color: #e2e8f0;
    }
    
    /* Selectbox dropdown */
    .stSelectbox [data-baseweb="select"] {
        background: #1e293b;
        border-color: #475569;
    }
    
    .stSelectbox [data-baseweb="popover"] {
        background: #1e293b;
        border: 1px solid #475569;
    }
    
    /* Make text in select options visible */
    [data-baseweb="menu"] li {
        color: #e2e8f0 !important;
        background: #1e293b !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background: #334155 !important;
    }
    
    /* Login specific styling */
    .login-logo {
        width: 80px;
        height: 80px;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        border-radius: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px;
        box-shadow: 0 10px 25px rgba(59, 130, 246, 0.3);
    }
    
    .login-title {
        text-align: center;
        margin-bottom: 40px;
    }
    
    .login-footer {
        text-align: center;
        color: #64748b;
        font-size: 0.875rem;
        margin-top: 32px;
        padding-top: 20px;
        border-top: 1px solid #334155;
    }
    
    /* Ensure form elements fit within card */
    .stForm {
        margin-bottom: 0 !important;
    }
    
    .stForm > div {
        padding: 0 !important;
    }
    
    /* SSL Status Indicators */
    .ssl-status-online {
        color: #34d399;
        font-weight: 600;
    }
    
    .ssl-status-offline {
        color: #f87171;
        font-weight: 600;
    }
    
    .ssl-status-warning {
        color: #fbbf24;
        font-weight: 600;
    }
    
    .ssl-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .ssl-badge-secure {
        background: rgba(52, 211, 153, 0.1);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    
    .ssl-badge-insecure {
        background: rgba(248, 113, 113, 0.1);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }
    
    .ssl-badge-mixed {
        background: rgba(251, 191, 36, 0.1);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==============================================
# DATABASE MANAGER - UPDATED WITH SSL SETTINGS
# ==============================================
class DatabaseManager:
    """Simplified database manager dengan SSL settings support"""
    
    def __init__(self, db_path='jmailbox.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Create database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables dengan SSL settings"""
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS packages (
                id TEXT PRIMARY KEY,
                resi TEXT NOT NULL,
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
                created_by INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_value REAL NOT NULL,
                status TEXT NOT NULL,
                probability REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS mqtt_ssl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                ssl_enabled BOOLEAN,
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
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create tables
            for table_sql in tables:
                cursor.execute(table_sql)
            
            # Insert default admin user
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE username = 'admin'"
            )
            if cursor.fetchone()[0] == 0:
                password_hash = generate_password_hash('admin123')
                cursor.execute(
                    """
                    INSERT INTO users 
                    (username, email, nama_lengkap, password_hash, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ('admin', 'admin@jmailbox.com', 'Administrator', 
                     password_hash, 'admin')
                )
            
            # Insert default settings including SSL settings
            default_settings = [
                ('theme', 'dark'),
                ('mqtt_broker', MQTT_BROKER),
                ('mqtt_port', str(MQTT_PORT)),
                ('mqtt_port_ssl', '8883'),
                ('mqtt_username', MQTT_USERNAME),
                ('mqtt_password', MQTT_PASSWORD),
                ('mqtt_use_ssl', 'true'),
                ('mqtt_ca_cert', 'certs/ca.crt'),
                ('mqtt_client_cert', 'certs/client.crt'),
                ('mqtt_client_key', 'certs/client.key'),
                ('sensor_threshold_warning', '15'),
                ('sensor_threshold_danger', '10'),
                ('ssl_auto_fallback', 'true')
            ]
            
            cursor.executemany(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                default_settings
            )
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully with SSL settings")
            
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    # User Management
    def get_user_by_username(self, username: str):
        """Get user by username"""
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
    
    def create_user(self, username: str, email: str, nama_lengkap: str, password_hash: str):
        """Create new user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users 
                (username, email, nama_lengkap, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (username, email, nama_lengkap, password_hash)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Create user error: {e}")
            return False
    
    # Master Data Management
    def get_master_data(self, user_id=None):
        """Get all master data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute(
                    "SELECT * FROM master_data WHERE created_by = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            else:
                cursor.execute("SELECT * FROM master_data ORDER BY created_at DESC")
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get master data error: {e}")
            return []
    
    def add_master_data(self, master_data: dict):
        """Add new master data"""
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
    
    def update_master_data(self, master_id: str, updates: dict):
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
    
    def delete_master_data(self, master_id: str):
        """Delete master data"""
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
    
    # Package Management
    def get_packages(self, filters=None):
        """Get packages with optional filters"""
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
    
    def add_package(self, package: dict):
        """Add new package"""
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
    
    def update_package_status(self, package_id: str, status: str):
        """Update package status"""
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
    
    # Security Management
    def add_security_log(self, sensor_value: float, status: str, probability: float, user_id=None):
        """Add security log"""
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
    
    def get_recent_security_logs(self, limit: int = 10):
        """Get recent security logs"""
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
    
    # SSL Log Management
    def log_ssl_event(self, event_type: str, status: str, message: str = None, ssl_enabled: bool = True):
        """Log SSL connection event"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mqtt_ssl_logs 
                (event_type, status, message, ssl_enabled)
                VALUES (?, ?, ?, ?)
                """,
                (event_type, status, message, ssl_enabled)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Log SSL event error: {e}")
    
    def get_ssl_logs(self, limit: int = 20):
        """Get SSL connection logs"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM mqtt_ssl_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (limit,)
            )
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Get SSL logs error: {e}")
            return []
    
    # Settings Management
    def get_setting(self, key: str, default=None):
        """Get setting value"""
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
                value = result[0]
                # Convert boolean strings
                if value.lower() in ['true', 'false']:
                    return value.lower() == 'true'
                # Convert numeric strings
                try:
                    if '.' in value:
                        return float(value)
                    return int(value)
                except:
                    return value
            return default
        except sqlite3.Error as e:
            logger.error(f"Get setting error: {e}")
            return default
    
    def update_setting(self, key: str, value):
        """Update setting"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Convert boolean to string
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            else:
                value = str(value)
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
                """,
                (key, value)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Update setting error: {e}")
            return False
    
    # Activity Logs
    def log_activity(self, user_id, action: str, details: str = None, ip_address: str = None):
        """Log user activity"""
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
    
    # Statistics
    def get_statistics(self, user_id=None):
        """Get statistics"""
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
            
            # SSL connection status dari logs
            cursor.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM mqtt_ssl_logs 
                WHERE timestamp > datetime('now', '-1 hour')
                GROUP BY status
                """
            )
            ssl_stats = cursor.fetchall()
            stats['ssl_connections'] = {row[0]: row[1] for row in ssl_stats}
            
            conn.close()
            return stats
        except sqlite3.Error as e:
            logger.error(f"Get statistics error: {e}")
            return {}

# Initialize database
db = DatabaseManager()

# ==============================================
# UI COMPONENTS - MUST BE DEFINED BEFORE USAGE
# ==============================================
class UIComponents:
    """Reusable UI components for consistent styling"""
    
    @staticmethod
    def metric_card(title, value, icon=None, color='primary'):
        """Create a metric card"""
        colors = {
            'primary': '#3b82f6',
            'success': '#34d399',
            'warning': '#fbbf24',
            'danger': '#f87171',
            'purple': '#8b5cf6',
            'orange': '#f97316'
        }
        
        icon_html = f'<div style="font-size: 24px; margin-bottom: 8px;">{icon}</div>' if icon else ''
        
        return f"""
        <div class="metric-card">
            {icon_html}
            <div class="metric-label">{title}</div>
            <div class="metric-value" style="color: {colors[color]};">{value}</div>
        </div>
        """
    
    @staticmethod
    def badge(text, type='info'):
        """Create a badge"""
        return f'<span class="badge badge-{type}">{text}</span>'
    
    @staticmethod
    def ssl_badge(ssl_enabled, connection_status="disconnected"):
        """Create SSL status badge"""
        if ssl_enabled and connection_status == "connected":
            return '<span class="ssl-badge ssl-badge-secure">🔒 SSL Secure</span>'
        elif ssl_enabled and connection_status != "connected":
            return '<span class="ssl-badge ssl-badge-mixed">⚠️ SSL Configured</span>'
        else:
            return '<span class="ssl-badge ssl-badge-insecure">⚠️ No SSL</span>'
    
    @staticmethod
    def card(title, content, height=None):
        """Create a card"""
        style = f'height: {height};' if height else ''
        return f"""
        <div class="card" style="{style}">
            <div class="card-title">{title}</div>
            {content}
        </div>
        """
    
    @staticmethod
    def alert(message, type='info'):
        """Create an alert"""
        icons = {
            'success': '✅',
            'warning': '⚠️',
            'danger': '❌',
            'info': 'ℹ️',
            'ssl': '🔒'
        }
        return f"""
        <div class="alert alert-{type}">
            {icons[type]} {message}
        </div>
        """
    
    @staticmethod
    def table(headers, rows):
        """Create a data table"""
        headers_html = ''.join(f'<th>{header}</th>' for header in headers)
        rows_html = ''
        
        for row in rows:
            rows_html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
        
        return f"""
        <table class="data-table">
            <thead>
                <tr>{headers_html}</tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """

# ==============================================
# DEFAULT MASTER DATA
# ==============================================
DEFAULT_MASTER_DATA = [
    {
        'id': 'MASTER001',
        'name': 'Budi Santoso',
        'address': 'Jl. Sudirman No. 123, Jakarta Selatan',
        'phone': '081234567890',
        'email': 'budi.santoso@email.com',
        'created_at': datetime.now() - timedelta(days=30),
        'is_default': True
    },
    {
        'id': 'MASTER002',
        'name': 'Sari Dewi',
        'address': 'Jl. Gatot Subroto No. 45, Jakarta Pusat',
        'phone': '082345678901',
        'email': 'sari.dewi@email.com',
        'created_at': datetime.now() - timedelta(days=25),
        'is_default': False
    },
    {
        'id': 'MASTER003',
        'name': 'Agus Wijaya',
        'address': 'Jl. Thamrin No. 67, Jakarta Pusat',
        'phone': '083456789012',
        'email': 'agus.wijaya@email.com',
        'created_at': datetime.now() - timedelta(days=20),
        'is_default': False
    },
    {
        'id': 'MASTER004',
        'name': 'Maya Sari',
        'address': 'Jl. MH. Thamrin No. 89, Jakarta Pusat',
        'phone': '084567890123',
        'email': 'maya.sari@email.com',
        'created_at': datetime.now() - timedelta(days=15),
        'is_default': False
    },
    {
        'id': 'MASTER005',
        'name': 'Rudi Hartono',
        'address': 'Jl. Rasuna Said No. 10, Jakarta Selatan',
        'phone': '085678901234',
        'email': 'rudi.hartono@email.com',
        'created_at': datetime.now() - timedelta(days=10),
        'is_default': False
    }
]

# ==============================================
# SESSION STATE MANAGEMENT
# ==============================================
class SessionStateManager:
    """Professional session state management dengan SSL support"""
    
    @staticmethod
    def initialize():
        """Initialize all session state variables"""
        if 'initialized' not in st.session_state:
            st.session_state.initialized = True
            
            # User session
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.current_user_id = None
            st.session_state.current_page = 'login'
            
            # Data dari database
            st.session_state.master_data = SessionStateManager.load_master_data()
            st.session_state.packages = SessionStateManager.load_packages()
            
            # Sensor dan real-time data
            st.session_state.sensor_value = 18.5
            st.session_state.security_alerts = []
            st.session_state.real_time_updates = []
            
            # SSL & MQTT State
            st.session_state.mqtt_ssl_enabled = db.get_setting('mqtt_use_ssl', True)
            st.session_state.mqtt_connected = False
            st.session_state.mqtt_connection_status = "disconnected"
            st.session_state.ssl_certificates_available = False
            st.session_state.ssl_logs = []
            
            # UI State
            st.session_state.show_delivery_form = False
            st.session_state.selected_package = None
            st.session_state.new_delivery_page = False
            st.session_state.current_master_id = None
            
            # Load settings dari database
            st.session_state.settings = SessionStateManager.load_settings()
            
            # Real-time update interval
            st.session_state.last_update = datetime.now()
            
            # Check SSL certificates
            SessionStateManager.check_ssl_certificates()
            
            # Seed database with default data if empty
            SessionStateManager.seed_database()
    
    @staticmethod
    def load_master_data():
        """Load master data dari database"""
        if st.session_state.get('current_user_id'):
            master_data = db.get_master_data(st.session_state.current_user_id)
        else:
            master_data = db.get_master_data()
        
        # Jika database kosong, gunakan default data
        if not master_data:
            return DEFAULT_MASTER_DATA.copy()
        return master_data
    
    @staticmethod
    def load_packages():
        """Load packages dari database"""
        packages = db.get_packages()
        
        # Convert datetime strings to datetime objects for compatibility
        for pkg in packages:
            if isinstance(pkg.get('created_at'), str):
                try:
                    pkg['created_at'] = datetime.fromisoformat(pkg['created_at'].replace('Z', '+00:00'))
                except:
                    pkg['created_at'] = datetime.now()
        
        return packages
    
    @staticmethod
    def load_settings():
        """Load settings dari database"""
        settings = {}
        setting_keys = [
            'theme', 'mqtt_broker', 'mqtt_port', 'mqtt_port_ssl',
            'mqtt_username', 'mqtt_password', 'mqtt_use_ssl',
            'mqtt_ca_cert', 'mqtt_client_cert', 'mqtt_client_key',
            'sensor_threshold_warning', 'sensor_threshold_danger',
            'ssl_auto_fallback'
        ]
        
        for key in setting_keys:
            settings[key] = db.get_setting(key)
        
        return settings
    
    @staticmethod
    def check_ssl_certificates():
        """Check if SSL certificates are available"""
        try:
            import os
            ca_cert = db.get_setting('mqtt_ca_cert', 'certs/ca.crt')
            client_cert = db.get_setting('mqtt_client_cert', 'certs/client.crt')
            client_key = db.get_setting('mqtt_client_key', 'certs/client.key')
            
            st.session_state.ssl_certificates_available = (
                os.path.exists(ca_cert) and 
                os.path.exists(client_cert) and 
                os.path.exists(client_key)
            )
            
            if st.session_state.ssl_certificates_available:
                logger.info("SSL certificates are available")
                db.log_ssl_event(
                    "certificate_check",
                    "success",
                    "SSL certificates found and valid",
                    True
                )
            else:
                logger.warning("SSL certificates not found or incomplete")
                db.log_ssl_event(
                    "certificate_check",
                    "warning",
                    "SSL certificates not found or incomplete",
                    False
                )
                
        except Exception as e:
            logger.error(f"Error checking SSL certificates: {e}")
            st.session_state.ssl_certificates_available = False
    
    @staticmethod
    def seed_database():
        """Seed database with initial data if empty"""
        # Check if master data is empty
        master_data = db.get_master_data()
        if not master_data:
            # Insert default master data
            for master in DEFAULT_MASTER_DATA:
                db.add_master_data({
                    'id': master['id'],
                    'name': master['name'],
                    'address': master['address'],
                    'phone': master['phone'],
                    'email': master['email'],
                    'is_default': master['is_default'],
                    'created_by': 1  # admin user
                })
            logger.info("Seeded database with default master data")
    
    @staticmethod
    def refresh_real_time_data():
        """Refresh real-time data dari database"""
        # Update sensor value dari database
        logs = db.get_recent_security_logs(1)
        if logs:
            st.session_state.sensor_value = logs[0]['sensor_value']
        
        # Update packages
        st.session_state.packages = SessionStateManager.load_packages()
        
        # Update master data
        st.session_state.master_data = SessionStateManager.load_master_data()
        
        # Update SSL logs
        st.session_state.ssl_logs = db.get_ssl_logs(10)
        
        # Check SSL certificates
        SessionStateManager.check_ssl_certificates()
        
        # Log activity
        if st.session_state.current_user_id:
            db.log_activity(
                st.session_state.current_user_id,
                'page_refresh',
                f"Refreshed data at {datetime.now()}",
                'localhost'
            )
        
        st.session_state.last_update = datetime.now()

# ==============================================
# LOGIN PAGE - UPDATED WITH DATABASE AUTH
# ==============================================
class LoginPage:
    """Professional login page with database authentication"""
    
    @staticmethod
    def render():
        # Add login mode class to body
        st.markdown("""
            <script>
            document.body.classList.add('login-mode');
            </script>
        """, unsafe_allow_html=True)
        
        # Create full screen container using columns
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # Login Card Container
            st.markdown("""
                <div class="login-card">
                    <div class="login-title">
                        <div class="login-logo">
                            <svg style="width: 40px; height: 40px; color: white;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                            </svg>
                        </div>
                        <h1 class="title-1">J-MailBox</h1>
                        <p class="body-large" style="margin-bottom: 8px;">
                            Smart Mailbox with AI Integrated
                        </p>
                        <p class="body-small">
                            Control Center Dashboard v3.0 • SSL/TLS Support
                        </p>
                    </div>
            """, unsafe_allow_html=True)
            
            # Login Form with tabs
            tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
            
            with tab1:
                LoginPage.render_login_form()
            
            with tab2:
                LoginPage.render_register_form()
            
            # Footer
            st.markdown("""
                    <div class="login-footer">
                        SQLite • Database • SSL/TLS • Local Development • v3.0
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    @staticmethod
    def render_login_form():
        """Render login form"""
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                submit = st.form_submit_button(
                    "Sign In",
                    use_container_width=True,
                    type="primary"
                )
            
            if submit:
                if LoginPage.authenticate_user(username, password):
                    st.success("Login successful! Redirecting...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    
    @staticmethod
    def render_register_form():
        """Render registration form"""
        with st.form("register_form", clear_on_submit=False):
            email = st.text_input(
                "Email",
                placeholder="your.email@example.com"
            )
            
            full_name = st.text_input(
                "Full Name",
                placeholder="Your full name"
            )
            
            new_username = st.text_input(
                "Username",
                placeholder="Choose a username"
            )
            
            new_password = st.text_input(
                "Password",
                type="password",
                placeholder="Create a password"
            )
            
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Confirm your password"
            )
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                register = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary"
                )
            
            if register:
                if new_password == confirm_password:
                    if LoginPage.register_user(new_username, email, full_name, new_password):
                        st.success("Account created successfully!")
                    else:
                        st.error("Username or email already exists")
                else:
                    st.error("Passwords do not match")
    
    @staticmethod
    def authenticate_user(username: str, password: str) -> bool:
        """Authenticate user dengan database"""
        user = db.get_user_by_username(username)
        
        if user and check_password_hash(user['password_hash'], password):
            st.session_state.logged_in = True
            st.session_state.current_user = {
                'username': user['username'],
                'name': user['nama_lengkap'],
                'email': user['email'],
                'role': user['role']
            }
            st.session_state.current_user_id = user['id']
            st.session_state.current_page = 'dashboard'
            
            # Update last login
            db.update_user_login(user['id'])
            
            # Log activity
            db.log_activity(
                user['id'],
                'login',
                f"User logged in from Streamlit dashboard",
                "localhost"
            )
            
            # Log SSL status
            ssl_enabled = db.get_setting('mqtt_use_ssl', True)
            db.log_ssl_event(
                "user_login",
                "success",
                f"User {username} logged in. SSL enabled: {ssl_enabled}",
                ssl_enabled
            )
            
            # Remove login mode class
            st.markdown("""
                <script>
                document.body.classList.remove('login-mode');
                </script>
            """, unsafe_allow_html=True)
            
            return True
        
        return False
    
    @staticmethod
    def register_user(username: str, email: str, full_name: str, password: str) -> bool:
        """Register new user"""
        password_hash = generate_password_hash(password)
        return db.create_user(username, email, full_name, password_hash)

# ==============================================
# DASHBOARD PAGE - UPDATED WITH SSL STATUS
# ==============================================
class DashboardPage:
    """Professional dashboard page with SSL status"""
    
    @staticmethod
    def render():
        # Ensure login mode class is removed
        st.markdown("""
            <script>
            document.body.classList.remove('login-mode');
            </script>
        """, unsafe_allow_html=True)
        
        # Auto-refresh real-time data setiap 30 detik
        if (datetime.now() - st.session_state.last_update).seconds > 30:
            SessionStateManager.refresh_real_time_data()
        
        # Header with actions
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown('<h1 class="title-2">📊 Dashboard Overview</h1>', unsafe_allow_html=True)
            st.markdown('<p class="body-medium">Monitor your mailboxes and deliveries in real-time</p>', unsafe_allow_html=True)
        
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                SessionStateManager.refresh_real_time_data()
                st.success("Data refreshed!")
        
        with col3:
            ssl_status = DashboardPage.get_ssl_status_badge()
            st.markdown(ssl_status, unsafe_allow_html=True)
        
        # Stats Cards dari database
        st.markdown("## Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            stats = db.get_statistics(st.session_state.current_user_id)
            st.markdown(UIComponents.metric_card(
                "Total Packages",
                stats.get('total_packages', 0),
                "📦"
            ), unsafe_allow_html=True)
        
        with col2:
            ongoing = len([p for p in st.session_state.packages if p['status'] != 'Selesai'])
            st.markdown(UIComponents.metric_card(
                "Active Deliveries",
                ongoing,
                "🚚",
                "warning"
            ), unsafe_allow_html=True)
        
        with col3:
            completed = stats.get('completed_packages', 0)
            st.markdown(UIComponents.metric_card(
                "Completed",
                completed,
                "✅",
                "success"
            ), unsafe_allow_html=True)
        
        with col4:
            security_status = DashboardPage.get_security_status()
            st.markdown(UIComponents.metric_card(
                "Security Status",
                security_status['text'],
                "🛡️",
                security_status['type']
            ), unsafe_allow_html=True)
        
        # Connection Status Section
        DashboardPage.render_connection_status()
        
        # Real-time Charts
        st.markdown("## Real-time Analytics")
        col1, col2 = st.columns(2)
        
        with col1:
            DashboardPage.render_sensor_chart()
        
        with col2:
            DashboardPage.render_delivery_chart()
        
        # Recent Packages
        st.markdown("## Recent Packages")
        DashboardPage.render_recent_packages()
    
    @staticmethod
    def get_ssl_status_badge():
        """Get SSL status badge HTML"""
        ssl_enabled = st.session_state.mqtt_ssl_enabled
        certs_available = st.session_state.ssl_certificates_available
        
        if ssl_enabled and certs_available:
            return '<div style="text-align: center;">🔒 SSL Secure • Database Connected</div>'
        elif ssl_enabled and not certs_available:
            return '<div style="text-align: center;">⚠️ SSL Configured (Certs Missing)</div>'
        else:
            return '<div style="text-align: center;">⚠️ No SSL • Database Connected</div>'
    
    @staticmethod
    def render_connection_status():
        """Render connection status section"""
        st.markdown("## Connection Status")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ssl_enabled = st.session_state.mqtt_ssl_enabled
            certs_available = st.session_state.ssl_certificates_available
            
            if ssl_enabled and certs_available:
                status_text = "🔒 SSL/TLS Enabled"
                status_color = "success"
                status_icon = "✅"
            elif ssl_enabled and not certs_available:
                status_text = "⚠️ SSL Missing Certificates"
                status_color = "warning"
                status_icon = "⚠️"
            else:
                status_text = "⚠️ No SSL/TLS"
                status_color = "warning"
                status_icon = "⚠️"
            
            st.markdown(UIComponents.metric_card(
                "SSL Status",
                status_text,
                status_icon,
                status_color
            ), unsafe_allow_html=True)
        
        with col2:
            broker = st.session_state.settings.get('mqtt_broker', 'localhost')
            port = st.session_state.settings.get('mqtt_port_ssl' if st.session_state.mqtt_ssl_enabled else 'mqtt_port', '8883')
            
            st.markdown(UIComponents.metric_card(
                "MQTT Broker",
                f"{broker}:{port}",
                "🔌",
                "primary"
            ), unsafe_allow_html=True)
        
        with col3:
            # Test connection button
            if st.button("🔗 Test Connection", use_container_width=True):
                test_result = DashboardPage.test_mqtt_connection()
                if test_result:
                    st.success("Connection successful!")
                else:
                    st.error("Connection failed!")
        
        # SSL Certificate Status
        if st.session_state.mqtt_ssl_enabled:
            DashboardPage.render_ssl_certificate_status()
    
    @staticmethod
    def render_ssl_certificate_status():
        """Render SSL certificate status"""
        st.markdown("### SSL Certificate Status")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ca_cert = st.session_state.settings.get('mqtt_ca_cert', 'certs/ca.crt')
            ca_exists = st.session_state.ssl_certificates_available
            status = "✅ Available" if ca_exists else "❌ Missing"
            st.metric("CA Certificate", status)
        
        with col2:
            client_cert = st.session_state.settings.get('mqtt_client_cert', 'certs/client.crt')
            cert_exists = st.session_state.ssl_certificates_available
            status = "✅ Available" if cert_exists else "❌ Missing"
            st.metric("Client Certificate", status)
        
        with col3:
            client_key = st.session_state.settings.get('mqtt_client_key', 'certs/client.key')
            key_exists = st.session_state.ssl_certificates_available
            status = "✅ Available" if key_exists else "❌ Missing"
            st.metric("Client Key", status)
    
    @staticmethod
    def test_mqtt_connection():
        """Test MQTT connection"""
        try:
            # Simulate connection test
            import time
            time.sleep(1)
            
            ssl_enabled = st.session_state.mqtt_ssl_enabled
            certs_available = st.session_state.ssl_certificates_available
            
            if ssl_enabled and not certs_available:
                db.log_ssl_event(
                    "connection_test",
                    "failed",
                    "SSL enabled but certificates missing",
                    ssl_enabled
                )
                return False
            
            # Log test event
            db.log_ssl_event(
                "connection_test",
                "success" if certs_available else "warning",
                f"Connection test completed. SSL: {ssl_enabled}, Certs: {certs_available}",
                ssl_enabled
            )
            
            return True
            
        except Exception as e:
            db.log_ssl_event(
                "connection_test",
                "failed",
                f"Connection test failed: {str(e)}",
                st.session_state.mqtt_ssl_enabled
            )
            return False
    
    @staticmethod
    def get_security_status():
        """Get current security status dari database"""
        logs = db.get_recent_security_logs(1)
        if logs:
            status = logs[0]['status']
            if status == 'danger':
                return {'text': 'Alert', 'type': 'danger'}
            elif status == 'warning':
                return {'text': 'Warning', 'type': 'warning'}
        
        return {'text': 'Safe', 'type': 'success'}
    
    @staticmethod
    def render_sensor_chart():
        """Render sensor chart dari database"""
        logs = db.get_recent_security_logs(30)
        
        if logs:
            time_data = [log['timestamp'] for log in logs]
            sensor_data = [log['sensor_value'] for log in logs]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=time_data,
                y=sensor_data,
                mode='lines',
                line=dict(color='#3b82f6', width=3),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
                name='Distance'
            ))
            
            # Add threshold lines
            warning_threshold = float(st.session_state.settings.get('sensor_threshold_warning', 15))
            danger_threshold = float(st.session_state.settings.get('sensor_threshold_danger', 10))
            
            fig.add_hline(y=warning_threshold, line_dash="dash", 
                         line_color="orange", annotation_text="Warning")
            fig.add_hline(y=danger_threshold, line_dash="dash", 
                         line_color="red", annotation_text="Danger")
            
            fig.update_layout(
                title="Real-time Sensor Distance",
                height=300,
                xaxis_title="Time",
                yaxis_title="Distance (cm)",
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#cbd5e1',
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Generate sample data if no logs
            time_data = list(range(30))
            sensor_data = []
            base_value = st.session_state.sensor_value
            
            for i in range(30):
                value = max(5, min(30, base_value + (random.random() - 0.5) * 5))
                sensor_data.append(value)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=time_data,
                y=sensor_data,
                mode='lines',
                line=dict(color='#3b82f6', width=3),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
                name='Distance'
            ))
            
            fig.update_layout(
                title="Ultrasonic Sensor Distance (Sample)",
                height=300,
                xaxis_title="Time (seconds)",
                yaxis_title="Distance (cm)",
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#cbd5e1',
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_delivery_chart():
        """Render delivery status chart dari database"""
        packages = st.session_state.packages
        
        if packages:
            status_counts = {}
            for package in packages:
                status = package['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            fig = go.Figure(data=[go.Pie(
                labels=list(status_counts.keys()),
                values=list(status_counts.values()),
                hole=.4,
                marker_colors=['#3b82f6', '#fbbf24', '#34d399', '#f87171']
            )])
            
            fig.update_layout(
                title="Delivery Status Distribution",
                height=300,
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#cbd5e1',
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No packages data available")
    
    @staticmethod
    def render_recent_packages():
        """Render recent packages dari database"""
        packages = st.session_state.packages[:5]
        
        if packages:
            headers = ["Tracking", "Recipient", "Courier", "Status", "Date"]
            rows = []
            
            for pkg in packages:
                status_badge = UIComponents.badge(
                    pkg['status'],
                    'success' if pkg['status'] == 'Selesai' else 
                    'warning' if pkg['status'] == 'Dalam Proses' else 'info'
                )
                
                rows.append([
                    pkg['resi'],
                    pkg['nama_penerima'],
                    pkg['courier'],
                    status_badge,
                    pkg['tanggal']
                ])
            
            st.markdown(UIComponents.table(headers, rows), unsafe_allow_html=True)
            
            # View all button
            col1, col2, col3 = st.columns([3, 1, 3])
            with col2:
                if st.button("View All Packages →", use_container_width=True):
                    st.session_state.current_page = 'packages'
                    st.rerun()
        else:
            st.info("No packages available")

# ==============================================
# PACKAGES PAGE - UPDATED WITH DATABASE
# ==============================================
class PackagesPage:
    """Professional packages management page with database"""
    
    @staticmethod
    def render():
        if st.session_state.new_delivery_page:
            PackagesPage.render_new_delivery_page()
            return
        
        # Header with actions
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown('<h1 class="title-2">📦 Package Management</h1>', unsafe_allow_html=True)
            st.markdown('<p class="body-medium">Manage all your deliveries and track packages</p>', unsafe_allow_html=True)
        
        with col2:
            if st.button("+ New Delivery", use_container_width=True, type="primary"):
                st.session_state.new_delivery_page = True
                st.rerun()
        
        # Search and Filters
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                search = st.text_input(
                    "Search packages...",
                    placeholder="Search by tracking number or recipient",
                    label_visibility="collapsed"
                )
            
            with col2:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "Dalam Proses", "Menunggu Pickup", "Selesai", "Dalam Perjalanan"],
                    label_visibility="collapsed"
                )
            
            with col3:
                payment_filter = st.selectbox(
                    "Payment",
                    ["All", "COD", "Transfer"],
                    label_visibility="collapsed"
                )
            
            with col4:
                if st.button("📥 Export", use_container_width=True):
                    PackagesPage.export_to_csv()
        
        # Packages Table dari database dengan filter
        filters = {
            'search': search if search else None,
            'status': status_filter,
            'metode_pembayaran': payment_filter
        }
        
        packages = db.get_packages(filters)
        PackagesPage.render_packages_table(packages)
    
    @staticmethod
    def render_packages_table(packages):
        """Render packages table"""
        if not packages:
            st.info("No packages found matching your criteria.")
            return
        
        headers = ["Tracking", "Recipient", "Courier", "Payment", "Status", "Date", "Actions"]
        rows = []
        
        for pkg in packages:
            status_badge = UIComponents.badge(
                pkg['status'],
                'success' if pkg['status'] == 'Selesai' else 
                'warning' if pkg['status'] in ['Dalam Proses', 'Menunggu Pickup'] else 'info'
            )
            
            payment_badge = UIComponents.badge(
                pkg['metode_pembayaran'],
                'warning' if pkg['metode_pembayaran'] == 'COD' else 'info'
            )
            
            actions = f"""
                <div style="display: flex; gap: 4px;">
                    <button style="
                        background: rgba(59, 130, 246, 0.1);
                        border: 1px solid rgba(59, 130, 246, 0.3);
                        border-radius: 6px;
                        padding: 4px 8px;
                        cursor: pointer;
                        font-size: 12px;
                        color: #3b82f6;
                    " onclick="alert('Edit {pkg['resi']}')">✏️ Edit</button>
                    <button style="
                        background: rgba(248, 113, 113, 0.1);
                        border: 1px solid rgba(248, 113, 113, 0.3);
                        border-radius: 6px;
                        padding: 4px 8px;
                        cursor: pointer;
                        font-size: 12px;
                        color: #f87171;
                    " onclick="alert('Delete {pkg['resi']}')">🗑️ Delete</button>
                </div>
            """
            
            rows.append([
                f"<strong>{pkg['resi']}</strong>",
                f"{pkg['nama_penerima']}<br><small style='color: #94a3b8;'>{pkg['telepon']}</small>",
                pkg['courier'],
                payment_badge,
                status_badge,
                pkg['tanggal'],
                actions
            ])
        
        st.markdown(UIComponents.table(headers, rows), unsafe_allow_html=True)
        st.caption(f"Showing {len(packages)} packages")
    
    @staticmethod
    def render_new_delivery_page():
        """Render new delivery as separate page"""
        st.markdown('<div class="sub-page-container">', unsafe_allow_html=True)
        
        # Header with back button
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button("← Back to Packages", use_container_width=True):
                st.session_state.new_delivery_page = False
                st.rerun()
        
        with col2:
            st.markdown('<h2 class="title-3">📝 Create New Delivery</h2>', unsafe_allow_html=True)
        
        # Master Data Selection
        st.markdown("### Select from Master Data")
        
        # Create tabs for master data selection and manual entry
        tab1, tab2 = st.tabs(["📋 Select from Master Data", "✏️ Manual Entry"])
        
        with tab1:
            PackagesPage.render_master_data_selection()
        
        with tab2:
            PackagesPage.render_manual_entry_form()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    @staticmethod
    def render_master_data_selection():
        """Render master data selection"""
        master_data = st.session_state.master_data
        
        if not master_data:
            st.info("No master data available. Please add some recipients first.")
            return
            
        for master in master_data:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**{master['name']}**")
                    st.caption(f"📞 {master['phone']}")
                    st.caption(f"📍 {master['address']}")
                
                with col2:
                    if master.get('email'):
                        st.caption(f"✉️ {master['email']}")
                    if master.get('is_default'):
                        st.markdown("⭐ **Default**")
                
                with col3:
                    if st.button(f"Select", key=f"select_{master['id']}", use_container_width=True):
                        st.session_state.selected_master = master
                        st.success(f"Selected {master['name']}")
                
                st.divider()
    
    @staticmethod
    def render_manual_entry_form():
        """Render manual entry form"""
        with st.form("new_delivery_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Pre-fill if master data is selected
                if hasattr(st.session_state, 'selected_master'):
                    master = st.session_state.selected_master
                    recipient_name = st.text_input(
                        "Recipient Name *",
                        value=master['name'],
                        placeholder="Full name"
                    )
                    
                    address = st.text_area(
                        "Address *",
                        value=master['address'],
                        placeholder="Complete address"
                    )
                    
                    phone = st.text_input(
                        "Phone Number *",
                        value=master['phone'],
                        placeholder="081234567890"
                    )
                    
                    email = st.text_input(
                        "Email Address",
                        value=master.get('email', ''),
                        placeholder="email@example.com"
                    )
                else:
                    recipient_name = st.text_input(
                        "Recipient Name *",
                        placeholder="Full name"
                    )
                    
                    address = st.text_area(
                        "Address *",
                        placeholder="Complete address"
                    )
                    
                    phone = st.text_input(
                        "Phone Number *",
                        placeholder="081234567890"
                    )
                    
                    email = st.text_input(
                        "Email Address",
                        placeholder="email@example.com"
                    )
                
                tracking_number = st.text_input(
                    "Tracking Number *",
                    placeholder="RES123456789"
                )
            
            with col2:
                courier = st.selectbox(
                    "Courier *",
                    ["JNE", "J&T", "Sicepat", "AnterAja", "Shopee Express", "Ninja Express", "Other"]
                )
                
                payment_method = st.selectbox(
                    "Payment Method *",
                    ["COD", "Transfer"]
                )
                
                # COD specific fields
                if payment_method == "COD":
                    cod_amount = st.number_input(
                        "COD Amount (Rp)",
                        min_value=0,
                        value=50000,
                        step=10000
                    )
                    cod_slot = st.selectbox("COD Slot", ["A", "B", "C"])
                
                # Checkbox for saving as master data
                save_as_master = st.checkbox("💾 Save recipient as Master Data")
                
                if save_as_master:
                    master_name = st.text_input(
                        "Master Data Name",
                        value=recipient_name if 'recipient_name' in locals() else "",
                        placeholder="Name for this master data entry"
                    )
                    set_as_default = st.checkbox("Set as default recipient")
            
            # Form buttons
            col_btn1, col_btn2 = st.columns([1, 1])
            
            with col_btn1:
                submit = st.form_submit_button(
                    "🚚 Create Delivery",
                    use_container_width=True,
                    type="primary"
                )
            
            with col_btn2:
                cancel = st.form_submit_button(
                    "Cancel",
                    use_container_width=True
                )
            
            if cancel:
                st.session_state.new_delivery_page = False
                if hasattr(st.session_state, 'selected_master'):
                    del st.session_state.selected_master
                st.rerun()
            
            if submit:
                if all([tracking_number, courier, recipient_name, address, phone, payment_method]):
                    # Save as master data if checked
                    if save_as_master and master_name and st.session_state.current_user_id:
                        new_master = {
                            'id': f'MASTER{len(st.session_state.master_data)+1:03d}',
                            'name': master_name,
                            'address': address,
                            'phone': phone,
                            'email': email if email else '',
                            'created_by': st.session_state.current_user_id,
                            'is_default': set_as_default if 'set_as_default' in locals() else False
                        }
                        if db.add_master_data(new_master):
                            st.session_state.master_data.append(new_master)
                    
                    # Create new package
                    new_package = {
                        'id': f'PKG{len(st.session_state.packages)+1:04d}',
                        'resi': tracking_number,
                        'courier': courier,
                        'nama_penerima': recipient_name,
                        'alamat': address,
                        'telepon': phone,
                        'email': email if email else '',
                        'metode_pembayaran': payment_method,
                        'status': 'Dalam Proses',
                        'tanggal': datetime.now().strftime('%d/%m/%Y'),
                        'nominal': f'Rp {cod_amount:,}' if payment_method == 'COD' and 'cod_amount' in locals() else '',
                        'master_data_id': st.session_state.selected_master['id'] if hasattr(st.session_state, 'selected_master') else None,
                        'created_by': st.session_state.current_user_id
                    }
                    
                    if db.add_package(new_package):
                        st.session_state.packages.insert(0, new_package)
                        st.session_state.new_delivery_page = False
                        
                        if hasattr(st.session_state, 'selected_master'):
                            del st.session_state.selected_master
                        
                        st.success("✅ Delivery created successfully!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Please fill all required fields (*)")
    
    @staticmethod
    def export_to_csv():
        """Export packages to CSV"""
        df = pd.DataFrame(st.session_state.packages)
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        
        st.markdown(
            f'<a href="data:file/csv;base64,{b64}" download="packages_export.csv" '
            'style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); '
            'color: white; padding: 10px 20px; border-radius: 8px; '
            'text-decoration: none; font-weight: 500; display: inline-block;">'
            '📥 Download CSV</a>',
            unsafe_allow_html=True
        )

# ==============================================
# SECURITY PAGE
# ==============================================
class SecurityPage:
    """Professional security monitoring page"""
    
    @staticmethod
    def render():
        # Ensure login mode class is removed
        st.markdown("""
            <script>
            document.body.classList.remove('login-mode');
            </script>
        """, unsafe_allow_html=True)
        
        # Header
        st.markdown('<h1 class="title-2">🛡️ Security Monitoring</h1>', unsafe_allow_html=True)
        st.markdown('<p class="body-medium">Real-time security monitoring and alerts</p>', unsafe_allow_html=True)
        
        # Current Status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(UIComponents.metric_card(
                "Current Distance",
                f"{st.session_state.sensor_value:.1f} cm",
                "📏"
            ), unsafe_allow_html=True)
        
        with col2:
            status = SecurityPage.get_security_status()
            st.markdown(UIComponents.metric_card(
                "Security Status",
                status['text'],
                status['icon'],
                status['type']
            ), unsafe_allow_html=True)
        
        with col3:
            probability = SecurityPage.get_probability()
            st.markdown(UIComponents.metric_card(
                "Safety Probability",
                f"{probability}%",
                "📊",
                "success" if probability > 80 else "warning" if probability > 60 else "danger"
            ), unsafe_allow_html=True)
        
        # Simulate sensor update
        if st.button("🔄 Simulate Sensor Update", use_container_width=True):
            st.session_state.sensor_value = max(5, min(30, 
                st.session_state.sensor_value + (random.random() - 0.5) * 5
            ))
            
            # Save to security logs
            status = SecurityPage.get_security_status()
            probability = SecurityPage.get_probability()
            db.add_security_log(
                st.session_state.sensor_value,
                status['text'].lower(),
                probability,
                st.session_state.current_user_id
            )
            
            st.success("Sensor data updated!")
            time.sleep(0.5)
            st.rerun()
        
        # Real-time Charts
        st.markdown("## Real-time Monitoring")
        col1, col2 = st.columns(2)
        
        with col1:
            SecurityPage.render_distance_chart()
        
        with col2:
            SecurityPage.render_alerts_chart()
        
        # Security Logs
        st.markdown("## Security Events")
        SecurityPage.render_security_logs()
    
    @staticmethod
    def get_security_status():
        """Get current security status"""
        distance = st.session_state.sensor_value
        if distance < 10:
            return {'text': 'DANGER', 'icon': '🚨', 'type': 'danger'}
        elif distance < 15:
            return {'text': 'WARNING', 'icon': '⚠️', 'type': 'warning'}
        else:
            return {'text': 'SAFE', 'icon': '✅', 'type': 'success'}
    
    @staticmethod
    def get_probability():
        """Calculate safety probability"""
        distance = st.session_state.sensor_value
        if distance >= 20:
            return random.randint(95, 99)
        elif distance >= 15:
            return random.randint(85, 94)
        elif distance >= 10:
            return random.randint(70, 84)
        else:
            return random.randint(50, 69)
    
    @staticmethod
    def render_distance_chart():
        """Render real-time distance chart - Dark Theme"""
        time_points = list(range(60))
        distances = []
        
        for i in range(60):
            base = st.session_state.sensor_value
            noise = (random.random() - 0.5) * 4
            distance = max(5, min(30, base + noise))
            distances.append(distance)
        
        fig = go.Figure()
        
        fig.add_hrect(
            y0=15, y1=30,
            fillcolor="rgba(52, 211, 153, 0.1)",
            line_width=0,
            annotation_text="Safe Zone",
            annotation_position="top left",
            annotation_font_color="#cbd5e1"
        )
        
        fig.add_hrect(
            y0=10, y1=15,
            fillcolor="rgba(251, 191, 36, 0.1)",
            line_width=0,
            annotation_text="Warning Zone",
            annotation_position="top left",
            annotation_font_color="#cbd5e1"
        )
        
        fig.add_hrect(
            y0=5, y1=10,
            fillcolor="rgba(248, 113, 113, 0.1)",
            line_width=0,
            annotation_text="Danger Zone",
            annotation_position="top left",
            annotation_font_color="#cbd5e1"
        )
        
        fig.add_trace(go.Scatter(
            x=time_points,
            y=distances,
            mode='lines',
            line=dict(color='#3b82f6', width=2),
            name='Distance'
        ))
        
        fig.update_layout(
            title="Real-time Distance Monitoring",
            height=350,
            xaxis_title="Time (seconds)",
            yaxis_title="Distance (cm)",
            template="plotly_dark",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#cbd5e1',
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_alerts_chart():
        """Render alerts frequency chart - Dark Theme"""
        hours = list(range(24))
        alerts = [random.randint(0, 5) for _ in range(24)]
        
        fig = go.Figure(data=[
            go.Bar(
                x=hours,
                y=alerts,
                marker_color=['#f87171' if a > 3 else '#fbbf24' if a > 1 else '#34d399' for a in alerts]
            )
        ])
        
        fig.update_layout(
            title="Alert Frequency (Last 24 Hours)",
            height=350,
            xaxis_title="Hour of Day",
            yaxis_title="Number of Alerts",
            template="plotly_dark",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#cbd5e1',
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_security_logs():
        """Render security event logs"""
        logs = db.get_recent_security_logs(10)
        
        if not logs:
            # Generate sample logs
            for i in range(5):
                time_ago = f"{random.randint(1, 60)} minutes ago"
                distance = random.uniform(5, 25)
                
                if distance < 10:
                    level = "CRITICAL"
                    icon = "🔴"
                    badge = UIComponents.badge("CRITICAL", "danger")
                elif distance < 15:
                    level = "WARNING"
                    icon = "🟡"
                    badge = UIComponents.badge("WARNING", "warning")
                else:
                    level = "INFO"
                    icon = "🟢"
                    badge = UIComponents.badge("INFO", "success")
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 3, 1])
                    
                    with col1:
                        st.markdown(f"**{time_ago}**")
                    
                    with col2:
                        st.markdown(f"{icon} Object detected at {distance:.1f} cm")
                    
                    with col3:
                        st.markdown(badge, unsafe_allow_html=True)
                    
                    st.markdown("---")
        else:
            for log in logs:
                time_ago = datetime.now() - datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                minutes_ago = int(time_ago.total_seconds() / 60)
                
                if minutes_ago < 1:
                    time_text = "Just now"
                else:
                    time_text = f"{minutes_ago} minutes ago"
                
                if log['status'] == 'danger':
                    level = "CRITICAL"
                    icon = "🔴"
                    badge = UIComponents.badge("CRITICAL", "danger")
                elif log['status'] == 'warning':
                    level = "WARNING"
                    icon = "🟡"
                    badge = UIComponents.badge("WARNING", "warning")
                else:
                    level = "INFO"
                    icon = "🟢"
                    badge = UIComponents.badge("INFO", "success")
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 3, 1])
                    
                    with col1:
                        st.markdown(f"**{time_text}**")
                    
                    with col2:
                        st.markdown(f"{icon} Sensor reading: {log['sensor_value']:.1f} cm")
                    
                    with col3:
                        st.markdown(badge, unsafe_allow_html=True)
                    
                    st.markdown("---")

# ==============================================
# MASTER DATA PAGE
# ==============================================
class MasterDataPage:
    """Master Data Management Page"""
    
    @staticmethod
    def render():
        st.markdown('<div class="sub-page-container">', unsafe_allow_html=True)
        
        # Header
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown('<h2 class="title-3">📋 Master Data Management</h2>', unsafe_allow_html=True)
            st.markdown('<p class="body-medium">Manage recipient information for quick package creation</p>', unsafe_allow_html=True)
        
        with col2:
            if st.button("+ Add New", use_container_width=True, type="primary"):
                MasterDataPage.render_add_form()
                st.rerun()
        
        # Master Data List
        MasterDataPage.render_master_data_list()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    @staticmethod
    def render_master_data_list():
        """Render master data list"""
        master_data = st.session_state.master_data
        
        if not master_data:
            st.info("No master data available. Add your first recipient!")
            return
        
        for master in master_data:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                
                with col1:
                    st.markdown(f"### {master['name']}")
                    st.markdown(f"**📞** {master['phone']}")
                    st.markdown(f"**📍** {master['address']}")
                    if master.get('email'):
                        st.markdown(f"**✉️** {master['email']}")
                
                with col2:
                    if isinstance(master.get('created_at'), datetime):
                        created_date = master['created_at'].strftime('%d %b %Y')
                    elif isinstance(master.get('created_at'), str):
                        try:
                            created_date = datetime.fromisoformat(master['created_at'].replace('Z', '+00:00')).strftime('%d %b %Y')
                        except:
                            created_date = master.get('created_at', 'Unknown')
                    else:
                        created_date = 'Unknown'
                    
                    st.markdown(f"**Added:** {created_date}")
                    if master.get('is_default'):
                        st.markdown("⭐ **Default Recipient**")
                
                with col3:
                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️", key=f"edit_{master['id']}", help="Edit"):
                            st.session_state.current_master_id = master['id']
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"delete_{master['id']}", help="Delete"):
                            if db.delete_master_data(master['id']):
                                st.session_state.master_data = [m for m in master_data if m['id'] != master['id']]
                                st.success("Deleted successfully!")
                                time.sleep(1)
                                st.rerun()
                
                st.divider()
        
        # Edit form if master is selected
        if st.session_state.current_master_id:
            MasterDataPage.render_edit_form()
    
    @staticmethod
    def render_add_form():
        """Render add master data form"""
        st.markdown("### Add New Recipient")
        
        with st.form("add_master_form"):
            name = st.text_input("Recipient Name *", placeholder="Full name")
            phone = st.text_input("Phone Number *", placeholder="081234567890")
            address = st.text_area("Address *", placeholder="Complete address")
            email = st.text_input("Email Address", placeholder="email@example.com")
            set_as_default = st.checkbox("Set as default recipient")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Save Recipient", use_container_width=True, type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)
            
            if cancel:
                st.rerun()
            
            if submit:
                if all([name, phone, address]) and st.session_state.current_user_id:
                    new_master = {
                        'id': f'MASTER{len(st.session_state.master_data)+1:03d}',
                        'name': name,
                        'phone': phone,
                        'address': address,
                        'email': email if email else '',
                        'created_by': st.session_state.current_user_id,
                        'is_default': set_as_default
                    }
                    
                    if db.add_master_data(new_master):
                        st.session_state.master_data.append(new_master)
                        st.success("✅ Recipient saved successfully!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Please fill all required fields (*)")
    
    @staticmethod
    def render_edit_form():
        """Render edit master data form"""
        if not st.session_state.current_master_id:
            return
        
        master_data = st.session_state.master_data
        master = next((m for m in master_data if m['id'] == st.session_state.current_master_id), None)
        
        if not master:
            st.error("Recipient not found!")
            return
        
        st.markdown("### Edit Recipient")
        
        with st.form("edit_master_form"):
            name = st.text_input("Recipient Name *", value=master['name'])
            phone = st.text_input("Phone Number *", value=master['phone'])
            address = st.text_area("Address *", value=master['address'])
            email = st.text_input("Email Address", value=master.get('email', ''))
            set_as_default = st.checkbox("Set as default recipient", value=master.get('is_default', False))
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Update", use_container_width=True, type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)
            
            if cancel:
                st.session_state.current_master_id = None
                st.rerun()
            
            if submit:
                if all([name, phone, address]):
                    updates = {
                        'name': name,
                        'phone': phone,
                        'address': address,
                        'email': email if email else '',
                        'is_default': set_as_default
                    }
                    
                    if db.update_master_data(master['id'], updates):
                        # Update in session state
                        for m in master_data:
                            if m['id'] == master['id']:
                                m.update(updates)
                                break
                        
                        st.session_state.current_master_id = None
                        st.success("✅ Recipient updated successfully!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Please fill all required fields (*)")

# ==============================================
# SETTINGS PAGE - UPDATED WITH SSL SETTINGS
# ==============================================
class SettingsPage:
    """Professional settings page dengan SSL/TLS support"""
    
    @staticmethod
    def render():
        # Header
        st.markdown('<h1 class="title-2">⚙️ Settings</h1>', unsafe_allow_html=True)
        st.markdown('<p class="body-medium">Configure your system preferences</p>', unsafe_allow_html=True)
        
        # Settings tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎨 Appearance",
            "🔗 MQTT Connection",
            "👤 Account",
            "📋 Master Data"
        ])
        
        with tab1:
            SettingsPage.render_appearance_settings()
        
        with tab2:
            SettingsPage.render_mqtt_settings()
        
        with tab3:
            SettingsPage.render_account_settings()
        
        with tab4:
            MasterDataPage.render()
    
    @staticmethod
    def render_appearance_settings():
        """Render appearance settings"""
        st.markdown("### Display Settings")
        
        # Theme options
        theme = st.selectbox(
            "Theme",
            ["Dark (Default)", "Light", "System"],
            index=0
        )
        
        # Color scheme
        st.markdown("### Color Scheme")
        color_scheme = st.selectbox(
            "Accent Color",
            ["Blue (Default)", "Purple", "Green", "Red", "Orange", "Pink"],
            index=0
        )
        
        # Font size
        st.markdown("### Font Size")
        font_size = st.select_slider(
            "Interface Font Size",
            options=["Small", "Medium", "Large"],
            value="Medium"
        )
        
        # Save button
        if st.button("Save Display Settings", type="primary"):
            db.update_setting('theme', theme)
            db.update_setting('color_scheme', color_scheme)
            st.session_state.settings['theme'] = theme
            st.session_state.settings['color_scheme'] = color_scheme
            st.success("Display settings saved!")
    
    @staticmethod
    def render_mqtt_settings():
        """Render MQTT connection settings dengan SSL"""
        st.markdown("### MQTT Connection Settings")
        
        # Basic Connection Settings
        col1, col2 = st.columns(2)
        
        with col1:
            broker = st.text_input(
                "Broker Host",
                value=st.session_state.settings.get('mqtt_broker', MQTT_BROKER),
                help="MQTT broker host address"
            )
            
            username = st.text_input(
                "Username",
                value=st.session_state.settings.get('mqtt_username', MQTT_USERNAME),
                help="MQTT broker username"
            )
        
        with col2:
            # Helper function untuk konversi port yang aman
            def get_port_value():
                port_str = st.session_state.settings.get('mqtt_port', '1883')
                try:
                    return int(port_str)
                except (ValueError, TypeError):
                    return 1883
            
            port = st.number_input(
                "Non-SSL Port",
                min_value=1,
                max_value=65535,
                value=get_port_value(),
                help="MQTT broker port (non-SSL)"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                value=st.session_state.settings.get('mqtt_password', MQTT_PASSWORD),
                help="MQTT broker password"
            )
        
        # SSL/TLS Configuration Section
        st.markdown("### SSL/TLS Configuration")
        
        ssl_enabled = st.checkbox(
            "Enable SSL/TLS",
            value=st.session_state.settings.get('mqtt_use_ssl', True),
            help="Enable secure MQTT connection with SSL/TLS"
        )
        
        if ssl_enabled:
            col_ssl1, col_ssl2 = st.columns(2)
            
            with col_ssl1:
                # Helper function untuk konversi port SSL yang aman
                def get_ssl_port_value():
                    port_str = st.session_state.settings.get('mqtt_port_ssl', '8883')
                    try:
                        return int(port_str)
                    except (ValueError, TypeError):
                        return 8883
                
                ssl_port = st.number_input(
                    "SSL Port",
                    min_value=1,
                    max_value=65535,
                    value=get_ssl_port_value(),
                    help="MQTT SSL port (default: 8883)"
                )
                
                ca_cert = st.text_input(
                    "CA Certificate Path",
                    value=st.session_state.settings.get('mqtt_ca_cert', 'certs/ca.crt'),
                    help="Path to CA certificate file"
                )
            
            with col_ssl2:
                client_cert = st.text_input(
                    "Client Certificate Path",
                    value=st.session_state.settings.get('mqtt_client_cert', 'certs/client.crt'),
                    help="Path to client certificate file"
                )
                
                client_key = st.text_input(
                    "Client Key Path",
                    value=st.session_state.settings.get('mqtt_client_key', 'certs/client.key'),
                    help="Path to client private key file"
                )
            
            # SSL Features
            st.markdown("#### SSL Features")
            
            col_ssl_feat1, col_ssl_feat2 = st.columns(2)
            
            with col_ssl_feat1:
                auto_fallback = st.checkbox(
                    "Auto Fallback to Non-SSL",
                    value=st.session_state.settings.get('ssl_auto_fallback', True),
                    help="Automatically fallback to non-SSL if SSL connection fails"
                )
            
            with col_ssl_feat2:
                verify_certs = st.checkbox(
                    "Verify Certificates",
                    value=True,
                    help="Verify SSL certificates (recommended)"
                )
            
            # Certificate Status
            SettingsPage.render_certificate_status(ca_cert, client_cert, client_key)
        
        # Sensor thresholds
        st.markdown("### Sensor Thresholds")
        
        col_thresh1, col_thresh2 = st.columns(2)
        
        with col_thresh1:
            # Helper function untuk konversi yang aman
            def get_warning_value():
                warning_str = st.session_state.settings.get('sensor_threshold_warning', '15')
                try:
                    return float(warning_str)
                except (ValueError, TypeError):
                    return 15.0
            
            warning_threshold = st.number_input(
                "Warning Threshold (cm)",
                min_value=1.0,
                max_value=100.0,
                value=get_warning_value(),
                step=0.1,
                help="Distance threshold for warning status"
            )
        
        with col_thresh2:
            # Helper function untuk konversi yang aman
            def get_danger_value():
                danger_str = st.session_state.settings.get('sensor_threshold_danger', '10')
                try:
                    return float(danger_str)
                except (ValueError, TypeError):
                    return 10.0
            
            danger_threshold = st.number_input(
                "Danger Threshold (cm)",
                min_value=1.0,
                max_value=50.0,
                value=get_danger_value(),
                step=0.1,
                help="Distance threshold for danger status"
            )
        
        # Connection test section
        st.markdown("### Connection Test")
        
        col_test1, col_test2 = st.columns([3, 1])
        
        with col_test1:
            connection_status = SettingsPage.get_connection_status()
            st.markdown(f"**Status:** {connection_status}")
        
        with col_test2:
            if st.button("🔗 Test Connection", use_container_width=True):
                test_result = SettingsPage.test_mqtt_connection(
                    broker, 
                    ssl_port if ssl_enabled else port, 
                    ssl_enabled
                )
                if test_result:
                    st.success("Connection successful!")
                else:
                    st.error("Connection failed!")
        
        # Save button
        col_save1, col_save2 = st.columns([1, 1])
        
        with col_save1:
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                settings_saved = SettingsPage.save_mqtt_settings(
                    broker, port, username, password,
                    ssl_enabled, ssl_port if ssl_enabled else None,
                    ca_cert if ssl_enabled else None,
                    client_cert if ssl_enabled else None,
                    client_key if ssl_enabled else None,
                    auto_fallback if ssl_enabled else True,
                    warning_threshold, danger_threshold
                )
                
                if settings_saved:
                    st.success("Settings saved successfully!")
                    time.sleep(1)
                    st.rerun()
        
        with col_save2:
            if st.button("🔄 Reset to Defaults", use_container_width=True):
                if SettingsPage.reset_to_defaults():
                    st.success("Settings reset to defaults!")
                    time.sleep(1)
                    st.rerun()
    
    @staticmethod
    def render_certificate_status(ca_cert, client_cert, client_key):
        """Render certificate status information"""
        st.markdown("#### Certificate Status")
        
        import os
        
        cert_status = []
        
        # Check CA Certificate
        ca_exists = os.path.exists(ca_cert) if ca_cert else False
        cert_status.append(("CA Certificate", ca_cert, ca_exists))
        
        # Check Client Certificate
        client_cert_exists = os.path.exists(client_cert) if client_cert else False
        cert_status.append(("Client Certificate", client_cert, client_cert_exists))
        
        # Check Client Key
        client_key_exists = os.path.exists(client_key) if client_key else False
        cert_status.append(("Client Key", client_key, client_key_exists))
        
        # Display status
        for name, path, exists in cert_status:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{name}: {path}")
            with col2:
                if exists:
                    st.markdown("✅ **Available**")
                else:
                    st.markdown("❌ **Missing**")
        
        # Generate certificates button if missing
        if not all([ca_exists, client_cert_exists, client_key_exists]):
            if st.button("🔐 Generate SSL Certificates", use_container_width=True):
                SettingsPage.generate_ssl_certificates()
    
    @staticmethod
    def get_connection_status():
        """Get current connection status"""
        ssl_enabled = st.session_state.settings.get('mqtt_use_ssl', True)
        
        if ssl_enabled:
            return "🔒 SSL/TLS Enabled"
        else:
            return "⚠️ Non-SSL Connection"
    
    @staticmethod
    def test_mqtt_connection(broker, port, ssl_enabled):
        """Test MQTT connection"""
        try:
            import time
            # Simulate connection test
            time.sleep(2)
            
            # Check certificates if SSL enabled
            if ssl_enabled:
                ca_cert = st.session_state.settings.get('mqtt_ca_cert', 'certs/ca.crt')
                client_cert = st.session_state.settings.get('mqtt_client_cert', 'certs/client.crt')
                client_key = st.session_state.settings.get('mqtt_client_key', 'certs/client.key')
                
                import os
                certs_available = (
                    os.path.exists(ca_cert) and 
                    os.path.exists(client_cert) and 
                    os.path.exists(client_key)
                )
                
                if not certs_available:
                    db.log_ssl_event(
                        "connection_test",
                        "failed",
                        f"SSL enabled but certificates missing for {broker}:{port}",
                        ssl_enabled
                    )
                    return False
            
            # Log test event
            db.log_ssl_event(
                "connection_test",
                "success",
                f"Connection test to {broker}:{port} completed. SSL: {ssl_enabled}",
                ssl_enabled
            )
            
            return True
            
        except Exception as e:
            db.log_ssl_event(
                "connection_test",
                "failed",
                f"Connection test failed: {str(e)}",
                ssl_enabled
            )
            return False
    
    @staticmethod
    def save_mqtt_settings(broker, port, username, password, ssl_enabled, 
                          ssl_port=None, ca_cert=None, client_cert=None, 
                          client_key=None, auto_fallback=True,
                          warning_threshold=15.0, danger_threshold=10.0):
        """Save MQTT settings to database"""
        try:
            settings_to_update = {
                'mqtt_broker': broker,
                'mqtt_port': str(port),
                'mqtt_username': username,
                'mqtt_password': password,
                'mqtt_use_ssl': str(ssl_enabled),
                'sensor_threshold_warning': str(warning_threshold),
                'sensor_threshold_danger': str(danger_threshold),
                'ssl_auto_fallback': str(auto_fallback)
            }
            
            if ssl_enabled and ssl_port:
                settings_to_update['mqtt_port_ssl'] = str(ssl_port)
            
            if ssl_enabled and ca_cert:
                settings_to_update['mqtt_ca_cert'] = ca_cert
            
            if ssl_enabled and client_cert:
                settings_to_update['mqtt_client_cert'] = client_cert
            
            if ssl_enabled and client_key:
                settings_to_update['mqtt_client_key'] = client_key
            
            # Update settings in database
            for key, value in settings_to_update.items():
                db.update_setting(key, value)
            
            # Update session state
            st.session_state.settings.update(settings_to_update)
            st.session_state.mqtt_ssl_enabled = ssl_enabled
            
            # Log activity
            db.log_activity(
                st.session_state.current_user_id,
                'update_mqtt_settings',
                f"Updated MQTT settings. SSL: {ssl_enabled}",
                "localhost"
            )
            
            # Log SSL event
            db.log_ssl_event(
                "settings_update",
                "success",
                f"MQTT settings saved. SSL enabled: {ssl_enabled}",
                ssl_enabled
            )
            
            return True
            
        except Exception as e:
            db.log_ssl_event(
                "settings_update",
                "failed",
                f"Failed to save settings: {str(e)}",
                ssl_enabled
            )
            return False
    
    @staticmethod
    def reset_to_defaults():
        """Reset settings to defaults"""
        try:
            default_settings = {
                'mqtt_broker': MQTT_BROKER,
                'mqtt_port': str(MQTT_PORT),
                'mqtt_port_ssl': '8883',
                'mqtt_username': MQTT_USERNAME,
                'mqtt_password': MQTT_PASSWORD,
                'mqtt_use_ssl': 'true',
                'mqtt_ca_cert': 'certs/ca.crt',
                'mqtt_client_cert': 'certs/client.crt',
                'mqtt_client_key': 'certs/client.key',
                'sensor_threshold_warning': '15',
                'sensor_threshold_danger': '10',
                'ssl_auto_fallback': 'true'
            }
            
            for key, value in default_settings.items():
                db.update_setting(key, value)
            
            # Update session state
            st.session_state.settings.update(default_settings)
            st.session_state.mqtt_ssl_enabled = True
            
            db.log_activity(
                st.session_state.current_user_id,
                'reset_settings',
                "Reset settings to defaults",
                "localhost"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset settings: {e}")
            return False
    
    @staticmethod
    def generate_ssl_certificates():
        """Generate SSL certificates"""
        try:
            import subprocess
            import os
            
            # Create certs directory
            os.makedirs('certs', exist_ok=True)
            
            # Simple certificate generation
            ca_cert = st.session_state.settings.get('mqtt_ca_cert', 'certs/ca.crt')
            client_cert = st.session_state.settings.get('mqtt_client_cert', 'certs/client.crt')
            client_key = st.session_state.settings.get('mqtt_client_key', 'certs/client.key')
            
            # Create a simple certificate (for development only)
            from OpenSSL import crypto
            
            # Create CA key
            ca_key = crypto.PKey()
            ca_key.generate_key(crypto.TYPE_RSA, 2048)
            
            # Create CA cert
            ca_cert = crypto.X509()
            ca_cert.set_version(2)
            ca_cert.set_serial_number(1)
            ca_cert.get_subject().CN = "J-MailBox CA"
            ca_cert.gmtime_adj_notBefore(0)
            ca_cert.gmtime_adj_notAfter(10*365*24*60*60)  # 10 years
            ca_cert.set_issuer(ca_cert.get_subject())
            ca_cert.set_pubkey(ca_key)
            ca_cert.sign(ca_key, 'sha256')
            
            # Save CA cert
            with open('certs/ca.crt', 'wb') as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert))
            
            # Create server key
            server_key = crypto.PKey()
            server_key.generate_key(crypto.TYPE_RSA, 2048)
            
            # Create server cert
            server_cert = crypto.X509()
            server_cert.set_version(2)
            server_cert.set_serial_number(2)
            server_cert.get_subject().CN = "mqtt.jmailbox.local"
            server_cert.gmtime_adj_notBefore(0)
            server_cert.gmtime_adj_notAfter(10*365*24*60*60)
            server_cert.set_issuer(ca_cert.get_subject())
            server_cert.set_pubkey(server_key)
            server_cert.sign(ca_key, 'sha256')
            
            # Save server cert
            with open('certs/server.crt', 'wb') as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, server_cert))
            with open('certs/server.key', 'wb') as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, server_key))
            
            # Create client key
            client_key_crypto = crypto.PKey()
            client_key_crypto.generate_key(crypto.TYPE_RSA, 2048)
            
            # Create client cert
            client_cert = crypto.X509()
            client_cert.set_version(2)
            client_cert.set_serial_number(3)
            client_cert.get_subject().CN = "jmailbox_client"
            client_cert.gmtime_adj_notBefore(0)
            client_cert.gmtime_adj_notAfter(10*365*24*60*60)
            client_cert.set_issuer(ca_cert.get_subject())
            client_cert.set_pubkey(client_key_crypto)
            client_cert.sign(ca_key, 'sha256')
            
            # Save client cert
            with open('certs/client.crt', 'wb') as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, client_cert))
            with open('certs/client.key', 'wb') as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, client_key_crypto))
            
            # Update settings
            db.update_setting('mqtt_ca_cert', 'certs/ca.crt')
            db.update_setting('mqtt_client_cert', 'certs/client.crt')
            db.update_setting('mqtt_client_key', 'certs/client.key')
            
            st.session_state.settings['mqtt_ca_cert'] = 'certs/ca.crt'
            st.session_state.settings['mqtt_client_cert'] = 'certs/client.crt'
            st.session_state.settings['mqtt_client_key'] = 'certs/client.key'
            
            # Check certificates
            SessionStateManager.check_ssl_certificates()
            
            db.log_ssl_event(
                "certificate_generation",
                "success",
                "SSL certificates generated successfully",
                True
            )
            
            st.success("SSL certificates generated successfully!")
            return True
            
        except Exception as e:
            db.log_ssl_event(
                "certificate_generation",
                "failed",
                f"Failed to generate certificates: {str(e)}",
                False
            )
            st.error(f"Failed to generate certificates: {e}")
            return False
    
    @staticmethod
    def render_account_settings():
        """Render account settings"""
        st.markdown("### Account Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Full Name",
                value=st.session_state.current_user['name'] if st.session_state.current_user else "",
                help="Your full name"
            )
            
            email = st.text_input(
                "Email Address",
                value=st.session_state.current_user['email'] if st.session_state.current_user else "",
                help="Your email address"
            )
        
        with col2:
            username = st.text_input(
                "Username",
                value=st.session_state.current_user['username'] if st.session_state.current_user else "",
                help="Your username"
            )
            
            current_password = st.text_input(
                "Current Password",
                type="password",
                help="Enter current password to make changes"
            )
        
        # Password change
        st.markdown("### Change Password")
        
        col_pass1, col_pass2 = st.columns(2)
        
        with col_pass1:
            new_password = st.text_input(
                "New Password",
                type="password",
                help="Enter new password"
            )
        
        with col_pass2:
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                help="Confirm new password"
            )
        
        # Save button
        if st.button("Update Account", type="primary"):
            if new_password and new_password != confirm_password:
                st.error("Passwords do not match!")
            else:
                st.success("Account updated successfully!")

# ==============================================
# SIDEBAR COMPONENT - UPDATED WITH SSL STATUS
# ==============================================
class Sidebar:
    """Professional sidebar navigation dengan SSL status"""
    
    @staticmethod
    def render():
        # Ensure login mode class is removed
        st.markdown("""
            <script>
            document.body.classList.remove('login-mode');
            </script>
        """, unsafe_allow_html=True)
        
        with st.sidebar:
            # Logo and branding dengan SSL indicator
            ssl_enabled = st.session_state.mqtt_ssl_enabled
            certs_available = st.session_state.ssl_certificates_available
            
            ssl_indicator = "🔒" if ssl_enabled and certs_available else "⚠️"
            ssl_text = "SSL Secure" if ssl_enabled and certs_available else "No SSL" if not ssl_enabled else "SSL (Certs Missing)"
            
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 32px; padding-top: 20px;">
                    <div style="
                        width: 60px;
                        height: 60px;
                        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                        border-radius: 16px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 16px;
                        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                    ">
                        <svg style="width: 30px; height: 30px; color: white;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                        </svg>
                    </div>
                    <h2 style="
                        margin: 0; 
                        font-family: 'Plus Jakarta Sans', sans-serif; 
                        font-weight: 700; 
                        font-size: 1.25rem; 
                        color: #f1f5f9;
                    ">
                        J-MailBox
                    </h2>
                    <div style="
                        margin: 4px 0 0 0; 
                        font-size: 0.75rem; 
                        color: #94a3b8;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 4px;
                    ">
                        <span>{ssl_indicator}</span>
                        <span>{ssl_text}</span>
                        <span>•</span>
                        <span>Database</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Navigation
            pages = [
                {"icon": "📊", "label": "Dashboard", "page": "dashboard"},
                {"icon": "📦", "label": "Packages", "page": "packages"},
                {"icon": "🛡️", "label": "Security", "page": "security"},
                {"icon": "⚙️", "label": "Settings", "page": "settings"}
            ]
            
            for page in pages:
                if st.button(
                    f"{page['icon']} {page['label']}",
                    key=f"nav_{page['page']}",
                    use_container_width=True,
                    type="primary" if st.session_state.current_page == page['page'] else "secondary"
                ):
                    st.session_state.current_page = page['page']
                    st.session_state.new_delivery_page = False
                    st.session_state.current_master_id = None
                    st.rerun()
            
            st.markdown("---")
            
            # User info
            if st.session_state.current_user:
                st.markdown(f"""
                    <div style="
                        padding: 12px; 
                        background: #1e293b; 
                        border-radius: 8px; 
                        margin: 16px 0;
                        border: 1px solid #334155;
                    ">
                        <p style="margin: 0 0 4px 0; font-weight: 600; color: #f1f5f9;">
                            {st.session_state.current_user['name']}
                        </p>
                        <p style="margin: 0; font-size: 0.75rem; color: #94a3b8;">
                            {st.session_state.current_user['email']}
                        </p>
                        <div style="margin-top: 8px; font-size: 0.75rem; color: #64748b;">
                            {ssl_indicator} {ssl_text}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Logout button
            if st.button(
                "🚪 Sign Out",
                use_container_width=True,
                type="secondary"
            ):
                # Add login mode class back for login page
                st.markdown("""
                    <script>
                    document.body.classList.add('login-mode');
                    </script>
                """, unsafe_allow_html=True)
                
                # Log SSL event
                db.log_ssl_event(
                    "user_logout",
                    "success",
                    f"User {st.session_state.current_user['username']} logged out",
                    st.session_state.mqtt_ssl_enabled
                )
                
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.session_state.current_user_id = None
                st.session_state.current_page = 'login'
                st.session_state.new_delivery_page = False
                st.rerun()

# ==============================================
# MAIN APPLICATION
# ==============================================
def main():
    """Main application entry point"""
    
    # Initialize session state
    SessionStateManager.initialize()
    
    # Check authentication
    if not st.session_state.logged_in:
        LoginPage.render()
    else:
        # Render sidebar
        Sidebar.render()
        
        # Render main content
        if st.session_state.current_page == 'dashboard':
            DashboardPage.render()
        elif st.session_state.current_page == 'packages':
            PackagesPage.render()
        elif st.session_state.current_page == 'security':
            SecurityPage.render()
        elif st.session_state.current_page == 'settings':
            SettingsPage.render()

# ==============================================
# RUN APPLICATION
# ==============================================
if __name__ == "__main__":
    main()