import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sender_email = 'team14.emailer@gmail.com'
receiver_email = 'dutaa106@purdue.edu'

password = 'copg zfhp xgtc tfig'

subject = "This was the big CP and his auto emailer"
body = "If you don't PU for lunch, then you like ladyboys."
i = 0

while i < 3:
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    message.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(message)
