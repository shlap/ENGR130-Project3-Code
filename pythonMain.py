import csv
import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import cv2
import numpy as np
import easyocr

PANEL_WIDTH = 350
OCR_EVERY_N_FRAMES = 100   
MIN_CONFIDENCE = 0.2      # EasyOCR confidence is 0-1
LINE_Y_TOLERANCE = 15     # Boxes whose tops are within this many pixels are on the same line
SHEET_FILE = "extracted_labels.csv"
RESIDENT_FILE = "residents.csv"

DORM_NAME = "Lee-Such Tower, Honors North" 

GMAIL_ADDRESS = "team14.emailer@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

SUBJECT = "Package Delivered"
BODY = "Hi {first}, your package was delivered at {time}."

ROOM_PATTERN = re.compile(r'\b(?:room|rm|apt|suite|ste)\.?\s*#?\s*([A-Za-z0-9-]+)', re.IGNORECASE)


def group_into_lines(results):
    """Turn EasyOCR boxes into ordered lines of text, top to bottom, left to right."""
    items = []
    for bbox, text, conf in results:
        if conf < MIN_CONFIDENCE:
            continue
        pts = np.array(bbox, dtype=np.int32)
        items.append((pts[:, 1].min(), pts[:, 0].min(), text.strip()))

    items.sort()
    lines = []
    for top, left, text in items:
        if lines and abs(lines[-1]['top'] - top) <= LINE_Y_TOLERANCE:
            lines[-1]['parts'].append((left, text))
        else:
            lines.append({'top': top, 'parts': [(left, text)]})

    return [" ".join(t for _, t in sorted(line['parts'])) for line in lines]


def extract_fields(lines):
    """Pull name, address, and room number from the label. Dorm is predetermined."""
    fields = {'name': None, 'address': None, 'room': None}

    for i, line in enumerate(lines):
        if re.search(r'ship\s*to', line, re.IGNORECASE) and i + 1 < len(lines):
            fields['name'] = lines[i + 1]
            break
    if fields['name'] is None:
        for line in lines:
            if re.fullmatch(r"[A-Z][a-z'-]+ [A-Z][a-z'-]+", line):
                fields['name'] = line
                break

    for line in lines:
        match = ROOM_PATTERN.search(line)
        if match:
            fields['room'] = match.group(1)
            break

    return fields


def save_to_sheet(fields):
    is_new = not os.path.exists(SHEET_FILE)
    with open(SHEET_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "name", "address", "dorm", "room"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"),
                         fields['name'] or "", fields['address'] or "",
                         DORM_NAME, fields['room'] or ""])

def load_residents(path=RESIDENT_FILE):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def fields_to_scan(fields):
    """Convert OCR fields into the scan dict used for resident matching."""
    scan = {}
    if fields['name']:
        parts = fields['name'].split(" ", 1)
        scan['first'] = parts[0]
        if len(parts) > 1:
            scan['last'] = parts[1]
    if fields['room']:
        scan['room'] = fields['room']
    return scan

def matches_scan(resident, scan):
    """Check each piece of information the scan found."""
    if scan.get("first") and resident["First Name"].strip().lower() != scan["first"].lower():
        return False
    if scan.get("last") and resident["Last Name"].strip().lower() != scan["last"].lower():
        return False
    if scan.get("floor") and resident["Floor"].strip() != scan["floor"]:
        return False
    if scan.get("room") and resident["Room"].strip().lower() != scan["room"].lower():
        return False
    return True

def find_resident(scan, path=RESIDENT_FILE):
    matches = [r for r in load_residents(path) if matches_scan(r, scan)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        return "No matching name/email in database"
    else:
        return "Not enough information, please do manual entry"

def build_email(resident, time_str):
    first_name = resident["First Name"].strip()
    message = MIMEText(BODY.format(first=first_name, time=time_str))
    message["Subject"] = SUBJECT
    message["From"] = GMAIL_ADDRESS
    message["To"] = resident["Email"].strip()
    return message

def notify(fields):
    """Look up the resident from the label fields and email them."""
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD):
        return "Error: GMAIL_ADDRESS / GMAIL_APP_PASSWORD environment variables are not set"

    result = find_resident(fields_to_scan(fields))
    if isinstance(result, str):      # a string means an error message
        return "Error: " + result

    time_str = datetime.now().strftime("%I:%M %p")
    message = build_email(result, time_str)

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(message)
    return f"Sent '{SUBJECT}' to {message['To']}"

def main():
    reader = easyocr.Reader(['en'], gpu=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise IOError("Cannot open webcam")

    print("Press 'e' to extract, save to CSV, and notify the resident. 'q' to quit.")

    frame_count = 0
    last_results = []
    last_fields = {'name': None, 'address': None, 'room': None}

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        frame_count += 1
        if frame_count % OCR_EVERY_N_FRAMES == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            last_results = reader.readtext(rgb)
            last_fields = extract_fields(group_into_lines(last_results))

        annotated = frame.copy()
        for bbox, text, conf in last_results:
            if conf < MIN_CONFIDENCE:
                continue
            pts = np.array(bbox, dtype=np.int32)
            cv2.polylines(annotated, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

        h, w = annotated.shape[:2]
        panel = np.full((h, PANEL_WIDTH, 3), 30, dtype=np.uint8)
        cv2.putText(panel, "Label info", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        y_pos = 70
        rows = [('Name', last_fields['name']),
                ('Address', last_fields['address']),
                ('Dorm', DORM_NAME),
                ('Room', last_fields['room'])]
        for label, value in rows:
            value = value or "--"
            cv2.putText(panel, label + ":", (10, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
            y_pos += 22
            for i in range(0, len(value), 36):
                cv2.putText(panel, value[i:i + 36], (20, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
                y_pos += 22
            y_pos += 12

        cv2.putText(panel, "Press 'e' to save", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        combined = np.hstack([annotated, panel])
        cv2.imshow("Webcam OCR - Press 'e' to Extract, 'q' to Quit", combined)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('e'):
            if last_fields['name'] or last_fields['address'] or last_fields['room']:
                save_to_sheet(last_fields)
                print("Saved:", last_fields, "Dorm:", DORM_NAME)
                try:
                    print(notify(last_fields))
                except (smtplib.SMTPException, OSError) as e:
                    print("Saved, but email failed:", e)
            else:
                print("Nothing extracted to save.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()