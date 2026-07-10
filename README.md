# J-MailBox: Intelligent Delivery Hub
**"Secure AI-Powered IoT Mailbox with Automated COD Payment System"**

**🏆 National Top 10 Project – Samsung Innovation Campus (SIC) Batch 7 - 2025/2026**

Developed by **Team Controller** (MAN 2 Kota Bekasi).

## Project Overview
**J-Mailbox** is an intelligent delivery hub designed to revolutionize last-mile delivery. As a recognized **Top 10 National Finalist** in the Samsung Innovation Campus (SIC) Batch 7, this project provides an innovative solution to parcel security and the inefficiencies of Cash on Delivery (COD) processes. By integrating AI, IoT hardware, and secure data communication, J-Mailbox offers a modern and automated logistics solution.

## Team "Controller"
The success of this project is driven by the collaborative efforts of our team members:

* **Kayla Diara Ramadhani** – Team Management
* **Inashaura Azkazola Ridalistiyanti** – Hardware Development
* **Khaizuran Danish Safaraz** – AI and Machine Learning
* **Muhammad Alfathan Ghaniy** – Software Engineer

## Key Features
* **AI-Powered Smart Assistance:** Utilizes a Machine Learning model (Logistic Regression) to analyze ultrasonic sensor data for adaptive, real-time activity pattern classification and security monitoring.
* **Automated COD System:** Features an integrated automated payment handling mechanism using servo-controlled cash management, synchronized with barcode-based receipt validation.
* **Secure Communication:** Implements end-to-end communication via the MQTT protocol, secured with SSL/TLS encryption (Port 8883) through an Nginx gateway.
* **Real-time Control Center:** Centralized web dashboard providing live system status, transaction history, and visual security log access.
* **Visual Documentation:** Integrates an ESP32-CAM module for automated snapshot capture during delivery, providing digital proof of parcel arrival.
* **Robust Data Management:** Employs an SQLite database system for reliable activity logging, transaction tracking, and comprehensive audit trails.
  
## Tech Stack
* **Hardware:** ESP32 (Main Controller), ESP32-CAM (Visual Monitoring), HC-SR04/JSN-SR04T Ultrasonic Sensor, GM65 Barcode Scanner, SG90 Servo Motor, I2C LCD 20x4 Display, Buzzer, Power Management (LM2596 Buck Converter).
* **Backend:** Python (Flask/FastAPI for API, Streamlit for Dashboard, Paho-MQTT for data communication).
* **Database:** SQLite.
* **Security & Infrastructure:** Eclipse Mosquitto (MQTT Broker), SSL/TLS (HTTPS), Nginx (Reverse Proxy), Virtual Private Server (VPS).
* **AI/ML:** Scikit-learn (Logistic Regression Model for ultrasonic sensor activity classification).

## Installation & Setup
1. Ensure Python 3.11+ is installed.
2. Initialize the MQTT broker using `docker-compose-mqtt.yml`.
3. Generate unique SSL certificates:
   - Linux/VPS: Run `./generate_certs.sh`
   - Windows: Run `fix_ssl_windows.bat`
4. Install dependencies: `pip install -r requirements.txt`
5. Configure environment variables (see [Configuration](#configuration) section below)
6. Launch the dashboard: `streamlit run app.py`

## Configuration
Create a `.env` file in the root directory with the following variables:
```env
MQTT_BROKER=your_broker_ip
MQTT_PORT=8883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
DATABASE_PATH=./data/mailbox.db
STREAMLIT_PORT=8501
SECRET_KEY=your_secret_key_here
```

## Usage & Examples
### Starting the System
```bash
# 1. Start MQTT Broker (if using Docker)
docker-compose -f docker-compose-mqtt.yml up -d

# 2. Run the Streamlit Dashboard
streamlit run app.py

# 3. Access the dashboard
# Navigate to http://localhost:8501
```

### API Endpoints (if Flask backend available)
```bash
# Get mailbox status
curl https://your_server:5000/api/mailbox/status

# Get delivery logs
curl https://your_server:5000/api/logs

# Process COD payment
curl -X POST https://your_server:5000/api/payment -d '{"order_id": "123", "amount": 50000}'
```

## Troubleshooting
| Issue | Solution |
|-------|----------|
| **SSL Certificate Error** | Regenerate certificates using `generate_certs.sh` or `fix_ssl_windows.bat` |
| **MQTT Connection Failed** | Check broker is running: `docker ps` and verify IP/port in `.env` |
| **Streamlit Port Already in Use** | Change `STREAMLIT_PORT` in `.env` or kill process: `lsof -ti:8501 \| xargs kill -9` |
| **Database Lock Error** | Ensure only one instance of app.py is running |
| **Model Not Found** | Verify `ultrasonic_model.pkl` exists in the project root |

## Contributing
We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/amazing-feature`
3. **Commit changes** with clear messages: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Submit a Pull Request** with detailed description

### Code Standards
- Follow PEP 8 for Python code
- Add comments for complex logic
- Update documentation when adding features
- Test changes before submitting PR

## Official Pitch & Recognition
We are proud to share that J-Mailbox was selected as one of the **Top 10 National Finalists** in Samsung Innovation Campus (SIC) Batch 7. You can watch our official project pitch featured on Samsung's official channel:
[▶️ Watch J-Mailbox Official Pitch (Samsung Official YouTube)](https://www.youtube.com/live/WX22WUUMDmQ?si=KjuwWsrh_abpPfPy)

## License
This project is licensed under the Apache License 2.0 – see the [LICENSE](LICENSE) file for details.
**Note:** If you deploy this project commercially, please ensure compliance with all local regulations regarding IoT devices, data security, and payment processing systems.

## Security & Privacy Notice
* **Sensitive Data:** This repository excludes sensitive configuration files, production databases, and private SSL keys (`certs/`, `*.db`, `*.pem`, `*.key`) to ensure deployment security.
* **AI Model:** The trained detection model (`ultrasonic_model.pkl`) is required for local deployment.

---
*Proudly developed as a Top 10 National Finalist project for Samsung Innovation Campus Batch 7 - 2025/2026.*
