import os, smtplib
from email.message import EmailMessage

def send_email(to, subject, body):
    user, password = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if not user or not password:
        return {"sent": False, "reason": "Configure SMTP_USER and SMTP_PASSWORD"}
    msg = EmailMessage(); msg["From"] = user; msg["To"] = to; msg["Subject"] = subject; msg.set_content(body)
    with smtplib.SMTP_SSL(os.getenv("SMTP_HOST","smtp.gmail.com"), int(os.getenv("SMTP_PORT","465"))) as s:
        s.login(user,password); s.send_message(msg)
    return {"sent": True}
