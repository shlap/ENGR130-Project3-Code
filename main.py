import csv
import os
import re
from datetime import datetime

import cv2
import numpy as np
import easyocr

PANEL_WIDTH = 350
OCR_EVERY_N_FRAMES = 15   # OCR is slow; raise this if the video lags
MIN_CONFIDENCE = 0.3      # EasyOCR confidence is 0-1
LINE_Y_TOLERANCE = 15     # Boxes whose tops are within this many pixels are on the same line
SHEET_FILE = "extracted_labels.csv"

STREET_SUFFIX = r'\b(St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Hwy)\b'
DORM_WORDS = r'\b(Hall|Residence|Residences|Dorm|Dormitory|House|Tower|Towers|Village|Apartments|Suites|Commons)\b'
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

# This is the important code - this extracts the text.
def extract_fields(lines):
    """Pull name, address, dorm, and room number out of the lines of text."""
    fields = {'name': None, 'address': None, 'dorm': None, 'room': None}

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
        if re.search(r'\d+\s+\w+.*' + STREET_SUFFIX, line, re.IGNORECASE) or \
           re.search(r'\bP\.?\s*O\.?\s*Box\b', line, re.IGNORECASE):
            fields['address'] = line
            break

    for line in lines:
        if re.search(DORM_WORDS, line, re.IGNORECASE):
            fields['dorm'] = line
            break

    for line in lines:
        match = ROOM_PATTERN.search(line)
        if match:
            fields['room'] = match.group(1)
            break

    return fields


def save_to_sheet(fields):
    """Append one row of extracted fields to the CSV file."""
    is_new = not os.path.exists(SHEET_FILE)
    with open(SHEET_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "name", "address", "dorm", "room"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"),
                         fields['name'] or "", fields['address'] or "",
                         fields['dorm'] or "", fields['room'] or ""])


reader = easyocr.Reader(['en'], gpu=False)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("Cannot open webcam")

print("Press 'e' to extract and save to CSV, 'q' to quit.")

frame_count = 0
last_results = []
last_fields = {'name': None, 'address': None, 'dorm': None, 'room': None}

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
        cv2.polylines(annotated, [pts], isClosed=True,
                      color=(0, 255, 0), thickness=2)

    h, w = annotated.shape[:2]
    panel = np.full((h, PANEL_WIDTH, 3), 30, dtype=np.uint8)
    cv2.putText(panel, "Label info", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    y_pos = 70
    for label in ['name', 'address', 'dorm', 'room']:
        value = last_fields[label] or "--"
        cv2.putText(panel, label.capitalize() + ":", (10, y_pos),
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
        if any(last_fields.values()):
            save_to_sheet(last_fields)
            print("Saved:", last_fields)
        else:
            print("Nothing extracted to save.")

cap.release()
cv2.destroyAllWindows()