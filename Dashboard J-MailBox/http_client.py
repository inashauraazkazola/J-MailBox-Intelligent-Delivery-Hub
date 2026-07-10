# http_client.py
import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HTTPClient:
    """Klien HTTP untuk komunikasi dengan backend API"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'J-MailBox-Dashboard/1.0.0'
        })
    
    def scan_resi(self, resi: str, tipe_pembayaran: str = "COD") -> Optional[Dict]:
        """Scan resi baru"""
        try:
            response = self.session.post(
                f"{self.base_url}/scan_resi",
                json={
                    "resi": resi,
                    "tipe_pembayaran": tipe_pembayaran
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Scan resi failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error scanning resi: {e}")
            return None
    
    def upload_foto(self, resi: str, image_path: str) -> Optional[Dict]:
        """Upload foto untuk resi"""
        try:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                response = self.session.post(
                    f"{self.base_url}/upload_wajah/{resi}",
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Upload foto failed: {response.status_code} - {response.text}")
                return None
                
        except (IOError, requests.RequestException) as e:
            logger.error(f"HTTP error uploading foto: {e}")
            return None
    
    def update_status(self, resi: str, jarak: float, durasi: float, 
                     slot: int, tombol: int = 0) -> Optional[Dict]:
        """Update status monitoring"""
        try:
            response = self.session.post(
                f"{self.base_url}/update_status",
                json={
                    "resi": resi,
                    "jarak": jarak,
                    "durasi": durasi,
                    "slot": slot,
                    "tombol": tombol
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Update status failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error updating status: {e}")
            return None
    
    def send_mqtt_command(self, resi: str, command: str, reason: str = "") -> Optional[Dict]:
        """Kirim perintah via MQTT"""
        try:
            response = self.session.post(
                f"{self.base_url}/mqtt/send_command",
                json={
                    "resi": resi,
                    "command": command,
                    "reason": reason
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Send MQTT command failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error sending MQTT command: {e}")
            return None
    
    def get_mqtt_status(self) -> Optional[Dict]:
        """Get status MQTT"""
        try:
            response = self.session.get(
                f"{self.base_url}/mqtt/status",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get MQTT status failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error getting MQTT status: {e}")
            return None
    
    def get_packages(self) -> Optional[Dict]:
        """Get semua packages"""
        try:
            response = self.session.get(
                f"{self.base_url}/list_resi",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get packages failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error getting packages: {e}")
            return None
    
    def get_statistics(self) -> Optional[Dict]:
        """Get statistics"""
        try:
            response = self.session.get(
                f"{self.base_url}/stats",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get statistics failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error getting statistics: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if API is healthy"""
        try:
            response = self.session.get(
                f"{self.base_url}/",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False