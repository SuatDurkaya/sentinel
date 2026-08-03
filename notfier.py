import redis
import smtplib
import json
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379,
    decode_responses=True
)

def start_listening():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("alerts")
    print("Notifier started, listening for alerts...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            alert_data = json.loads(message['data'])
            send_notification(alert_data)


def send_notification(alert: dict):
    text = f"{alert['url']} is DOWN (error: {alert.get('error', 'status ' + str(alert.get('status_code')))})"
    print(f"[NOTIFICATION] {text}")
    recipient = alert.get("owner_email")
    if recipient:
        send_email("Sentinel Alert", text, recipient)
    else:
        print("No owner_email found, skipping email")

def send_email(subject: str, body: str, to_email: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    start_listening()