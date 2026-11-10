import csv
import os
from datetime import datetime

CSV_FILE = "extracted_text.csv"

def save_row(text):
    is_new = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "text"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), text])

print("Type text and press Enter to save it to the CSV.")
print("Type 'quit' to exit.\n")

while True:
    text = input("> ").strip()
    if text.lower() == "quit":
        break
    if text:
        save_row(text)
        print(f"Saved to {CSV_FILE}")

print("Done.")