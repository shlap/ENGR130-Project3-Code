import re
import cv2
import numpy as np
import easyocr

PANEL_WIDTH = 350
OCR_EVERY_N_FRAMES = 15   # OCR is slow; raise this if the video lags
MIN_CONFIDENCE = 0.3      # EasyOCR confidence is 0-1
LINE_Y_TOLERANCE = 15     # Boxes whose tops are within this many pixels are on the same line

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

    items.sort()   # sort by top, then left
    lines = []
    for top, left, text in items:
        if lines and abs(lines[-1]['top'] - top) <= LINE_Y_TOLERANCE:
            lines[-1]['parts'].append((left, text))
        else:
            lines.append({'top': top, 'parts': [(left, text)]})

    result = []
    for line in lines:
        parts = sorted(line['parts'])
        result.append(" ".join(t for _, t in parts))
    return result


def extract_fields(lines):
    """Pull name, address, dorm, and room number out of the lines of text."""
    fields = {'name': None, 'address': None, 'dorm': None, 'room': None}

    # Name: the line after "SHIP TO", or the first line that looks like a two-word name
    for i, line in enumerate(lines):
        if re.search(r'ship\s*to', line, re.IGNORECASE) and i + 1 < len(lines):
            fields['name'] = lines[i + 1]
            break
    if fields['name'] is None:
        for line in lines:
            if re.fullmatch(r"[A-Z][a-z'-]+ [A-Z][a-z'-]+", line):
                fields['name'] = line
                break

    # Address: a line with a house number and a street suffix, or a PO Box
    for line in lines:
        if re.search(r'\d+\s+\w+.*' + STREET_SUFFIX, line, re.IGNORECASE) or \
           re.search(r'\bP\.?\s*O\.?\s*Box\b', line, re.IGNORECASE):
            fields['address'] = line
            break

    # Dorm: a line naming a residence building
    for line in lines:
        if re.search(DORM_WORDS, line, re.IGNORECASE):
            fields['dorm'] = line
            break

    # Room: "Room 204", "Rm 204", "Apt 3B", "Suite 12"
    for line in lines:
        match = ROOM_PATTERN.search(line)
        if match:
            fields['room'] = match.group(1)
            break

    return fields


reader = easyocr.Reader(['en'], gpu=False)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("Cannot open webcam")

print("Press 'q' to quit.")

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
        lines = group_into_lines(last_results)
        last_fields = extract_fields(lines)

    # Draw boxes around all recognized text
    annotated = frame.copy()
    for bbox, text, conf in last_results:
        if conf < MIN_CONFIDENCE:
            continue
        pts = np.array(bbox, dtype=np.int32)
        cv2.polylines(annotated, [pts], isClosed=True,
                      color=(0, 255, 0), thickness=2)

    # Build the side panel with the four fields
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
        # Wrap long values so they stay inside the panel
        for i in range(0, len(value), 36):
            cv2.putText(panel, value[i:i + 36], (20, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
            y_pos += 22
        y_pos += 12

    combined = np.hstack([annotated, panel])
    cv2.imshow("Webcam OCR - Press 'q' to Quit", combined)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()