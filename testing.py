import smtplib

email = "team14.emailer@gmail.com"
receiver_email = "Chrispy1729@gmail.com"

message = "67"
subject = "56"

text = f"Subject : {subject}\n\n{message}"

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()

server.login(email, "kvnn otpf jirv okje")

server.sendmail(email, receiver_email, text)