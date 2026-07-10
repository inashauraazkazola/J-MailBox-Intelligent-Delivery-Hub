@echo off
echo ========================================
echo J-MailBox SSL Fix for Windows
echo ========================================
echo.

echo Step 1: Creating certs directory...
if not exist "certs" mkdir certs

echo Step 2: Installing required packages...
pip install pyopenssl cryptography --quiet

echo Step 3: Generating certificates...
python -c 
from OpenSSL import crypto
import os

# Create certs
ca_key = crypto.PKey()
ca_key.generate_key(crypto.TYPE_RSA, 2048)

ca_cert = crypto.X509()
ca_cert.set_version(2)
ca_cert.set_serial_number(1000)

subj = ca_cert.get_subject()
subj.C = 'ID'
subj.O = 'J-MailBox'
subj.CN = 'J-MailBox CA'

ca_cert.gmtime_adj_notBefore(0)
ca_cert.gmtime_adj_notAfter(10*365*24*60*60)
ca_cert.set_issuer(subj)
ca_cert.set_pubkey(ca_key)
ca_cert.sign(ca_key, 'sha256')

with open('certs/ca.crt', 'wb') as f:
    f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert))

with open('certs/ca.key', 'wb') as f:
    f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key))

# Client cert
client_key = crypto.PKey()
client_key.generate_key(crypto.TYPE_RSA, 2048)

client_cert = crypto.X509()
client_cert.set_version(2)
client_cert.set_serial_number(1001)

client_subj = client_cert.get_subject()
client_subj.C = 'ID'
client_subj.O = 'J-MailBox'
client_subj.CN = 'jmailbox_client'

client_cert.gmtime_adj_notBefore(0)
client_cert.gmtime_adj_notAfter(10*365*24*60*60)
client_cert.set_issuer(subj)
client_cert.set_pubkey(client_key)
client_cert.sign(ca_key, 'sha256')

with open('certs/client.crt', 'wb') as f:
    f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, client_cert))

with open('certs/client.key', 'wb') as f:
    f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, client_key))

print('Certificates generated in certs/ folder')


echo.
echo ========================================
echo  SSL Certificates Generated!
echo ========================================
echo.
echo Files created:
echo   - certs/ca.crt
echo   - certs/ca.key
echo   - certs/client.crt
echo   - certs/client.key
echo.
echo Next steps:
echo   1. Open J-MailBox dashboard
echo   2. Go to Settings -> MQTT Connection
echo   3. Enable SSL/TLS
echo   4. Set certificate paths to:
echo        CA: certs/ca.crt
echo        Client Cert: certs/client.crt
echo        Client Key: certs/client.key
echo   5. Save and restart
echo.
pause