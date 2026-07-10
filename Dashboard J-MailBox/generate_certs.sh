#!/bin/bash
# generate_certs.sh
# Script untuk generate SSL certificates untuk MQTT Mosquitto

set -e

echo "🔐 Generating SSL Certificates for MQTT Mosquitto"

# Buat direktori untuk certificates
mkdir -p certs
cd certs

# 1. Generate CA private key
echo "📝 Generating CA private key..."
openssl genrsa -out ca.key 2048

# 2. Generate CA certificate
echo "📝 Generating CA certificate..."
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=J-MailBox/CN=J-MailBox CA"

# 3. Generate server private key
echo "📝 Generating server private key..."
openssl genrsa -out server.key 2048

# 4. Generate server certificate signing request
echo "📝 Generating server CSR..."
openssl req -new -out server.csr -key server.key \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=J-MailBox/CN=mqtt.jmailbox.local"

# 5. Sign server certificate dengan CA
echo "📝 Signing server certificate..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 3650 -sha256

# 6. Generate client private key
echo "📝 Generating client private key..."
openssl genrsa -out client.key 2048

# 7. Generate client certificate signing request
echo "📝 Generating client CSR..."
openssl req -new -out client.csr -key client.key \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=J-MailBox/CN=jmailbox_client"

# 8. Sign client certificate dengan CA
echo "📝 Signing client certificate..."
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out client.crt -days 3650 -sha256

# 9. Convert client certificate ke format PKCS#12 (pem+key)
echo "📝 Creating client PKCS#12 file..."
openssl pkcs12 -export -in client.crt -inkey client.key \
  -out client.p12 -password pass:jmailbox123

# 10. Buat file password untuk MQTT
echo "📝 Creating MQTT password file..."
touch passwd
mosquitto_passwd -b passwd "${MQTT_USER:-username}" "${MQTT_PASS:-password}"
mosquitto_passwd -b passwd admin securepassword123

# 11. Buat file ACL
echo "📝 Creating ACL file..."
cat > acl << 'EOF'
# ACL untuk J-MailBox
user "${MQTT_USER:-username}"
topic readwrite alat/#

user admin
topic readwrite #

pattern readwrite $SYS/#
EOF

echo "✅ SSL certificates generated successfully!"
echo ""
echo "📁 Files generated:"
echo "  - ca.crt          : Certificate Authority"
echo "  - server.crt      : Server certificate"
echo "  - server.key      : Server private key"
echo "  - client.crt      : Client certificate"
echo "  - client.key      : Client private key"
echo "  - client.p12      : Client PKCS#12 bundle"
echo "  - passwd          : MQTT password file"
echo "  - acl             : MQTT ACL file"
echo ""
echo "🔧 To install certificates on Mosquitto:"
echo "  sudo cp *.crt *.key /etc/mosquitto/certs/"
echo "  sudo cp passwd acl /etc/mosquitto/"
echo "  sudo systemctl restart mosquitto"