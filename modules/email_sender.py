import os
import logging
import httpx

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = "avdienkoaa@gmail.com"
FROM_NAME = "Job Hunter Germany"

async def send_email(to_email: str, subject: str, body: str, from_name: str = FROM_NAME) -> bool:
    """Отправляет письмо через SendGrid API."""
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": from_name},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}]
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code in (200, 202):
                logging.info(f"Email sent to {to_email}")
                return True
            else:
                logging.error(f"SendGrid error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logging.error(f"Email send error: {e}")
        return False

async def send_application(
    to_email: str,
    candidate_name: str,
    company_name: str,
    subject: str,
    anschreiben: str,
    lebenslauf: str
) -> bool:
    """Отправляет письмо с резюме и мотивационным письмом."""
    body = f"""{anschreiben}

---
LEBENSLAUF / РЕЗЮМЕ:

{lebenslauf}

---
Mit freundlichen Grüßen / С уважением,
{candidate_name}
"""
    return await send_email(to_email, subject, body, from_name=candidate_name)

async def send_followup(
    to_email: str,
    candidate_name: str,
    company_name: str,
    subject: str,
    followup_text: str
) -> bool:
    """Отправляет follow-up письмо."""
    return await send_email(to_email, subject, followup_text, from_name=candidate_name)
