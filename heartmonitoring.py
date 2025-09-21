#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, csv
from collections import deque
import serial
import requests
import numpy as np

# Edge Impulse runner
from edge_impulse_linux.runner import ImpulseRunner

# ---------------- USER CONFIG ----------------
SERIAL_PORT = os.environ.get("HR_SERIAL", "/dev/ttyACM0")
BAUD        = int(os.environ.get("HR_BAUD", "115200"))

MODEL_PATH = "/home/rsa/Downloads/heartmonitor-linux-armv7-v3.eim"

FREQUENCY_HZ   = int(os.environ.get("HR_FREQ", "50"))    # must match training
WINDOW_SECONDS = float(os.environ.get("HR_WIN", "10"))   # must match training
STEP_SECONDS   = float(os.environ.get("HR_STEP", "2"))   # how often to run inference

# ThingSpeak
THINGSPEAK_WRITE_KEY = os.environ.get("THINGSPEAK_WRITE_KEY", "EWMQXDLDYW4YVEY9")
THINGSPEAK_URL       = "https://api.thingspeak.com/update"

# Logging
LOG_CSV_PATH = "/home/rsa/heartmonitor_log.csv"


# Classification thresholds
SUDDEN_CLASS_NAME = os.environ.get("HR_CLASS", "sudden_change")
SUDDEN_THRESHOLD  = float(os.environ.get("HR_THRESH", "0.70"))
ANOMALY_THRESHOLD = float(os.environ.get("HR_ANOM", "0.50"))
# --------------------------------------------

def send_to_thingspeak(hr, spo2, ecg=None, prob_sudden=None, anomaly_score=None, prob_normal=None):
    params = {
        "api_key": THINGSPEAK_WRITE_KEY,
        "field1": f"{hr:.2f}",
        "field2": f"{spo2:.2f}",
        "field3": f"{ecg:.2f}" if ecg is not None else "",
        "field4": f"{prob_sudden:.3f}" if prob_sudden is not None else "",
        "field5": f"{anomaly_score:.3f}" if anomaly_score is not None else "",
        "field6": f"{prob_normal:.3f}" if prob_normal is not None else ""
    }

    try:
        r = requests.get(THINGSPEAK_URL, params=params, timeout=6)
        if r.status_code == 200 and r.text.strip() != "0":
            print(f"[ThingSpeak] Sent: {params}")
            return True
        else:
            print(f"[ThingSpeak] Failed. Response: {r.text}")
            return False
    except Exception as e:
        print(f"[ThingSpeak] Exception: {e}")
        return False

def parse_csv_line(line):
    # Expect: hr,spo2,ecg
    parts = line.strip().split(",")
    if len(parts) != 3:
        return None
    try:
        hr = float(parts[0])
        spo2 = float(parts[1])
        ecg = float(parts[2])
        return hr, spo2, ecg
    except ValueError:
        return None

def main():
    # Open serial port
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)

    # Prepare Edge Impulse runner
    runner = ImpulseRunner(MODEL_PATH)
    try:
        model_info = runner.init()
        print(model_info)
        
        # Get expected input length from model
        input_len = model_info['model_parameters']['input_features_count']
        print(f"Model expects input length: {input_len}")


        window_len = int(WINDOW_SECONDS * FREQUENCY_HZ)
        step_len   = int(STEP_SECONDS * FREQUENCY_HZ)

        buf_hr  = deque(maxlen=window_len)
        buf_spo = deque(maxlen=window_len)
        buf_ecg = deque(maxlen=window_len)

        # CSV logging
        if LOG_CSV_PATH:
            os.makedirs(os.path.dirname(LOG_CSV_PATH), exist_ok=True)
            logf = open(LOG_CSV_PATH, "a", newline="")
            logger = csv.writer(logf)
            if logf.tell() == 0:
                logger.writerow(["ts", "hr", "spo2", "ecg", "pred_sudden", "anomaly"])
        else:
            logger = None

        last_infer = 0.0
        last_push_ok = 0.0

        print("Streaming... Ctrl+C to exit.")
        while True:
            raw = ser.readline().decode("utf-8", errors="ignore")
            sample = parse_csv_line(raw)
            if not sample:
                continue

            hr, spo2, ecg = sample
            buf_hr.append(hr)
            buf_spo.append(spo2)
            buf_ecg.append(ecg)

            # Routine ThingSpeak update every 15s
            now = time.time()
            if now - last_push_ok >= 15.0:
                send_to_thingspeak(hr, spo2, ecg, prob_sudden=None, anomaly_score=None, prob_normal=None)
                last_push_ok = now

            # Inference
            have_window = len(buf_hr) == window_len and len(buf_spo) == window_len and len(buf_ecg) == window_len
            if have_window and (now - last_infer) >= STEP_SECONDS:
                last_infer = now

                # Take last `input_len` samples from each buffer
                a_hr  = np.array(buf_hr)[-input_len:].astype(np.float32)
                a_spo = np.array(buf_spo)[-input_len:].astype(np.float32)
                a_ecg = np.array(buf_ecg)[-input_len:].astype(np.float32)

                # Combine channels if your model expects multiple
                feats = np.empty(input_len, dtype=np.float32)
                # Adjust this depending on how your model was trained
                # Here we use only HR as a single-channel example
                feats[:] = a_hr

                res = runner.classify(feats)
                pred_sudden = None
                anomaly = None

                classes = res.get('result', {}).get('classification', {})
                if classes:
                    pred_sudden = float(classes.get(SUDDEN_CLASS_NAME, 0.0))
                    pred_normal = float(classes.get("normal", 0.0))  # Add this line


                if 'anomaly' in res.get('result', {}):
                    anomaly = float(res['result']['anomaly'])
                # Decide label
                if pred_sudden is not None and pred_normal is not None:
                    label = "sudden_change" if pred_sudden >= pred_normal else "normal"
                else:
                    label = "unknown"
                # Event detection
                is_event = False
                reason = ""
                if pred_sudden is not None and pred_sudden >= SUDDEN_THRESHOLD:
                    is_event = True
                    reason = f"{SUDDEN_CLASS_NAME} prob {pred_sudden:.2f}"
                elif anomaly is not None and anomaly >= ANOMALY_THRESHOLD:
                    is_event = True
                    reason = f"anomaly {anomaly:.2f}"

                if is_event:
                    print(f"[EVENT] {time.strftime('%F %T')}  HR={hr:.1f} SpO2={spo2:.1f} ECG={ecg:.1f} -> {label} prob_sudden={pred_sudden:.2f} prob_normal={pred_normal:.2f}")
                    send_to_thingspeak(hr, spo2, ecg, pred_sudden, anomaly, pred_normal)


                # Log CSV
                if logger:
                    logger.writerow([int(now), f"{hr:.2f}", f"{spo2:.2f}", f"{ecg:.2f}",
                                     f"{pred_sudden:.3f}" if pred_sudden is not None else "",
                                     f"{anomaly:.3f}" if anomaly is not None else ""])
                    logf.flush()

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        try:
            runner.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
