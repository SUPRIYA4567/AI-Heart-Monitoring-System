# AI-Based Multi-Sensor Heart Monitoring System

## 📖 Project Overview
This project is a real-time health monitoring solution integrating ECG (AD8232) and PPG (MAX30100) sensors, an Edge Impulse AI model, and IoT visualization using ThingSpeak Cloud.

## ⚙️ Technologies Used
- Arduino Uno SMD
- Raspberry Pi 4
- Edge Impulse (AI Model)
- Python
- ThingSpeak Cloud
- AD8232 (ECG Sensor)
- MAX30100 (PPG Sensor)

## 🚀 Features
- Real-time ECG, HR, and SpO₂ data acquisition.
- AI anomaly detection: Normal vs Sudden Change.
- Data upload & visualization on ThingSpeak.
- Portable & low-cost embedded solution.

## 📂 Folder Structure
- `arduino_code/` – Arduino sketch for sensor interfacing.
- `raspberry_pi_code/` – Python inference & IoT code.
- `dataset/` – Sample dataset for training/testing.
- `model/` – Trained Edge Impulse model (.eim file).
- `docs/` – Detailed project report in PDF.

## 📈 Results
- Achieved ~92% training accuracy and ~88% testing accuracy.
- Real-time anomaly detection triggered based on thresholds.
- Data visualized remotely in real time.

## 📄 License
MIT License
