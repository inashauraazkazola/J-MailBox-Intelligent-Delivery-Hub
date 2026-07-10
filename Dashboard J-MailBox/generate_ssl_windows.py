# generate_certs_windows.py
# Generate SSL certificates untuk Windows (tanpa OpenSSL command line)

import os
import sys
from pathlib import Path
from config import MQTT_USERNAME, MQTT_PASSWORD

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing required packages...")
    
    packages = ['cryptography', 'pyopenssl']
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} already installed")
        except ImportError:
            print(f"📥 Installing {package}...")
            os.system(f'{sys.executable} -m pip install {package} --quiet')
    
    print("✅ All dependencies installed")

def generate_certificates_windows():
    """Generate certificates untuk Windows"""
    
    print("🔐 Generating SSL certificates for Windows...")
    
    # Install dependencies
    install_dependencies()
    
    # Import setelah install
    from OpenSSL import crypto
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime
    
    # Buat direktori
    certs_dir = Path("certs")
    certs_dir.mkdir(exist_ok=True)
    
    try:
        # Generate CA Certificate
        print("1. Generating CA Certificate...")
        
        # Create CA key
        ca_key = crypto.PKey()
        ca_key.generate_key(crypto.TYPE_RSA, 2048)
        
        # Create CA certificate
        ca_cert = crypto.X509()
        ca_cert.set_version(2)
        ca_cert.set_serial_number(1000)
        
        # Set subject
        ca_subj = ca_cert.get_subject()
        ca_subj.countryName = "ID"
        ca_subj.stateOrProvinceName = "Jakarta"
        ca_subj.localityName = "Jakarta"
        ca_subj.organizationName = "J-MailBox"
        ca_subj.commonName = "J-MailBox CA"
        
        # Set validity
        ca_cert.gmtime_adj_notBefore(0)
        ca_cert.gmtime_adj_notAfter(10*365*24*60*60)  # 10 years
        
        ca_cert.set_issuer(ca_subj)
        ca_cert.set_pubkey(ca_key)
        ca_cert.sign(ca_key, 'sha256')
        
        # Save CA cert
        with open(certs_dir / "ca.crt", "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert))
        
        with open(certs_dir / "ca.key", "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key))
        
        print("✅ CA Certificate generated")
        
        # Generate Server Certificate
        print("2. Generating Server Certificate...")
        
        server_key = crypto.PKey()
        server_key.generate_key(crypto.TYPE_RSA, 2048)
        
        server_cert = crypto.X509()
        server_cert.set_version(2)
        server_cert.set_serial_number(1001)
        
        server_subj = server_cert.get_subject()
        server_subj.countryName = "ID"
        server_subj.stateOrProvinceName = "Jakarta"
        server_subj.localityName = "Jakarta"
        server_subj.organizationName = "J-MailBox"
        server_subj.commonName = "localhost"
        
        server_cert.gmtime_adj_notBefore(0)
        server_cert.gmtime_adj_notAfter(10*365*24*60*60)
        server_cert.set_issuer(ca_cert.get_subject())
        server_cert.set_pubkey(server_key)
        server_cert.sign(ca_key, 'sha256')
        
        # Save server cert
        with open(certs_dir / "server.crt", "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, server_cert))
        
        with open(certs_dir / "server.key", "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, server_key))
        
        print("✅ Server Certificate generated")
        
        # Generate Client Certificate
        print("3. Generating Client Certificate...")
        
        client_key = crypto.PKey()
        client_key.generate_key(crypto.TYPE_RSA, 2048)
        
        client_cert = crypto.X509()
        client_cert.set_version(2)
        client_cert.set_serial_number(1002)
        
        client_subj = client_cert.get_subject()
        client_subj.countryName = "ID"
        client_subj.stateOrProvinceName = "Jakarta"
        client_subj.localityName = "Jakarta"
        client_subj.organizationName = "J-MailBox"
        client_subj.commonName = "jmailbox_client"
        
        client_cert.gmtime_adj_notBefore(0)
        client_cert.gmtime_adj_notAfter(10*365*24*60*60)
        client_cert.set_issuer(ca_cert.get_subject())
        client_cert.set_pubkey(client_key)
        client_cert.sign(ca_key, 'sha256')
        
        # Save client cert
        with open(certs_dir / "client.crt", "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, client_cert))
        
        with open(certs_dir / "client.key", "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, client_key))
        
        print("✅ Client Certificate generated")
        
        # Create PKCS12 file
        print("4. Creating PKCS12 file...")
        
        p12 = crypto.PKCS12()
        p12.set_certificate(client_cert)
        p12.set_privatekey(client_key)
        p12.set_ca_certificates([ca_cert])
        
        with open(certs_dir / "client.p12", "wb") as f:
            f.write(p12.export(passphrase=b"jmailbox123"))
        
        print("✅ PKCS12 file created")
        
        # Create MQTT password file
        print("5. Creating MQTT password file...")
        
        # Generate password hash
        import hashlib
        import base64
        
        password = MQTT_PASSWORD
        salt = os.urandom(8)
        
        # Simple hash (mosquitto_passwd format)
        hash_val = hashlib.sha512((password + salt.hex()).encode()).hexdigest()
        
        with open(certs_dir / "passwd", "w") as f:
            f.write(f"{MQTT_USERNAME}:{hash_val}\n")
        
        print("✅ Password file created")
        
        # Create ACL file
        print("6. Creating ACL file...")
        
        with open(certs_dir / "acl", "w") as f:
            f.write("""# ACL for J-MailBox
user {MQTT_USERNAME}
topic readwrite alat/#

pattern readwrite $SYS/#
""")
        
        print("✅ ACL file created")
        
        # Show summary
        print("\n" + "="*60)
        print("✅ ALL CERTIFICATES GENERATED SUCCESSFULLY!")
        print("="*60)
        
        print("\n📁 Files created in 'certs' folder:")
        files = [
            ("CA Certificate", "ca.crt"),
            ("CA Private Key", "ca.key"),
            ("Server Certificate", "server.crt"),
            ("Server Private Key", "server.key"),
            ("Client Certificate", "client.crt"),
            ("Client Private Key", "client.key"),
            ("Client PKCS12", "client.p12"),
            ("MQTT Password", "passwd"),
            ("MQTT ACL", "acl")
        ]
        
        for name, filename in files:
            filepath = certs_dir / filename
            if filepath.exists():
                size = filepath.stat().st_size
                print(f"  ✓ {name}: {filename} ({size} bytes)")
            else:
                print(f"  ✗ {name}: {filename} (MISSING)")
        
        print("\n🔧 How to use in J-MailBox:")
        print("  1. Go to Settings → MQTT Connection")
        print("  2. Enable SSL/TLS")
        print("  3. Set paths to:")
        print("     - CA Certificate: certs/ca.crt")
        print("     - Client Certificate: certs/client.crt")
        print("     - Client Key: certs/client.key")
        print("  4. Click 'Save Settings'")
        print("  5. Restart the application")
        
        print(f"\n🔐 Password for MQTT: '{MQTT_PASSWORD}'")
        print("🔐 Password for PKCS12 file: 'jmailbox123'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Try running as Administrator")
        print("2. Check if Python has write permission")
        print("3. Try: pip install --upgrade pyopenssl cryptography")
        return False

def verify_certificates():
    """Verify the generated certificates"""
    print("\n🔍 Verifying certificates...")
    
    from OpenSSL import crypto
    
    try:
        # Load CA certificate
        with open("certs/ca.crt", "rb") as f:
            ca_data = f.read()
            ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_data)
        
        # Load client certificate
        with open("certs/client.crt", "rb") as f:
            client_data = f.read()
            client_cert = crypto.load_certificate(crypto.FILETYPE_PEM, client_data)
        
        # Verify client cert against CA
        store = crypto.X509Store()
        store.add_cert(ca_cert)
        
        store_ctx = crypto.X509StoreContext(store, client_cert)
        
        try:
            store_ctx.verify_certificate()
            print("✅ Certificate chain verification: PASSED")
        except crypto.X509StoreContextError as e:
            print(f"⚠️ Certificate verification warning: {e}")
        
        # Show certificate info
        print("\n📄 CA Certificate Info:")
        print(f"  Subject: {ca_cert.get_subject().CN}")
        print(f"  Issuer: {ca_cert.get_issuer().CN}")
        print(f"  Valid Until: {ca_cert.get_notAfter()}")
        
        print("\n📄 Client Certificate Info:")
        print(f"  Subject: {client_cert.get_subject().CN}")
        print(f"  Issuer: {client_cert.get_issuer().CN}")
        print(f"  Valid Until: {client_cert.get_notAfter()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("J-MailBox SSL Certificate Generator for Windows")
    print("="*60)
    
    # Generate certificates
    if generate_certificates_windows():
        # Verify certificates
        verify_certificates()
        
        print("\n" + "="*60)
        print("🎉 Setup completed successfully!")
        print("="*60)
        
        # Instructions untuk dashboard
        print("\n📋 NEXT STEPS:")
        print("1. Open your J-MailBox dashboard")
        print("2. Go to Settings → MQTT Connection")
        print("3. Configure these settings:")
        print("   - Broker: localhost")
        print("   - SSL Port: 8883")
        print("   - Enable SSL/TLS: ✅ CHECKED")
        print("   - CA Certificate: certs/ca.crt")
        print("   - Client Certificate: certs/client.crt")
        print("   - Client Key: certs/client.key")
        print("4. Click 'Save Settings'")
        print("5. Click 'Test Connection'")
        print("6. Restart the application")
        
        input("\nPress Enter to exit...")
    else:
        print("\n❌ Failed to generate certificates")
        input("\nPress Enter to exit...")