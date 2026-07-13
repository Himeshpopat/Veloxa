import os
import requests

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(to_email, subject, body):

    api_key = os.getenv("BREVO_API_KEY")

    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not set.")

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    data = {
        "sender": {
            "name": "Veloxa",
            "email": os.getenv("MAIL_USERNAME"),
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "textContent": body,
    }

    response = requests.post(BREVO_API_URL, headers=headers, json=data, timeout=15)
    response.raise_for_status()