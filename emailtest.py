import csv
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText

SENDER_EMAIL = "team14.emailer@gmail.com"
SENDER_PASSWORD = 'copg zfhp xgtc tfig'

residentData = "residents.csv"

SUBJECTS = "Package Delivered"

BODIES = "Hi {first}, your package was delivered at {time}."

def loadData(path):
    file = open(path, newline="", encoding="utf-8")
    rows = list(csv.DictReader(file))
    file.close()
    return rows

def matches_scan(resident, scan):
    # Check each piece of information the scan found
    if scan.get("first"):
        if resident["First Name"].strip().lower() != scan["first"].lower():
            return False
    if scan.get("last"):
        if resident["Last Name"].strip().lower() != scan["last"].lower():
            return False
    if scan.get("floor"):
        if resident["Floor"].strip() != scan["floor"]:
            return False
    if scan.get("Room"):
        if resident["Room"].strip() != scan["Room"]:
            return False
    return True


def find_resident(scan, path=residentData):
    residents = loadData(path)

    matches = []
    for resident in residents:
        if matches_scan(resident, scan):
            matches.append(resident)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        return "No matching name/email in database"
    else:
        return "Not enough information, please do manual entry"


def build_email(resident, time_str):
    first_name = resident["First Name"].strip()
    body = BODIES.format(first=first_name, time=time_str)

    message = MIMEText(body)
    message["Subject"] = SUBJECTS
    message["From"] = SENDER_EMAIL
    message["To"] = resident["Email"].strip()
    return message


def notify(scan, time_str):
    result = find_resident(scan)

    # If find_resident returned a string, it's an error message
    if isinstance(result, str):
        return "Error: " + result

    message = build_email(result, time_str)

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.send_message(message)
    server.quit()
    print("Email Sent")
    return "Sent '" + SUBJECTS + "' to " + message["To"]

#first, last = full_name.split(" ", 1)

scan = {"first": "Christopher", "last": "Park", "room": "2149"}

print(notify(scan, datetime.now().strftime("%I:%M %p")))
