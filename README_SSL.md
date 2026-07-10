# J-MailBox MQTT dengan SSL/TLS

## Fitur SSL/TLS
1. **Secure MQTT Connection** (Port 8883)
2. **Secure WebSocket** (Port 8083) untuk dashboard web
3. **Certificate Authentication** menggunakan CA signed certificates
4. **Fallback mechanism** ke non-SSL jika SSL gagal
5. **Secure password storage** dengan password hashing

## Instalasi Quick Start

### 1. Generate Certificates
```bash
# Berikan permission execute
chmod +x generate_certs.sh

# Generate certificates
./generate_certs.sh