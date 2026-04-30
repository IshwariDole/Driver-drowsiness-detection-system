from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

client = Client(TWILIO_SID, TWILIO_AUTH)

def send_alert(to_number, message):
    client.messages.create(
        body=message,
        from_=TWILIO_PHONE,
        to=to_number
    )
