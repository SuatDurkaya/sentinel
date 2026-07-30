import redis
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_TO_EMAIL = os.getenv("ALERT_TO_EMAIL")    

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
            alert_text = message['data']
            send_notification(alert_text)


def send_notification(text: str):
    # Placeholder for sending notifications (e.g., email, SMS, etc.)
    print(f"[NOTIFICATION] {text}")
    send_email("Sentinel Alert", text)

def send_email(subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ALERT_TO_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {ALERT_TO_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    start_listening()