import os
import logging
import httpx

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = "avdienkoaa@gmail.com"
FROM_NAME = "Job Hunter Germany"


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str = None,
    from_name: str = FROM_NAME
) -> bool:
    """Отправляет письмо через SendGrid API.
    Если передан html_body — отправляет обе версии (plain + HTML).
    """
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    content = [{"type": "text/plain", "value": body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": from_name},
        "subject": subject,
        "content": content
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code in (200, 202):
                logging.info(f"Email sent to {to_email} | subject: {subject}")
                return True
            else:
                logging.error(f"SendGrid error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logging.error(f"Email send error: {e}")
        return False


def _build_html(anschreiben: str, lebenslauf: str, candidate_name: str) -> str:
    """Формирует HTML версию письма — читается лучше ATS системами."""
    anschreiben_html = anschreiben.replace("\n", "<br>")
    lebenslauf_html = lebenslauf.replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #222; max-width: 700px; margin: 0 auto;">
  <div style="margin-bottom: 32px;">
    {anschreiben_html}
  </div>
  <hr style="border: 1px solid #ccc; margin: 32px 0;">
  <div>
    <h2 style="font-size: 16px; font-weight: bold;">LEBENSLAUF</h2>
    {lebenslauf_html}
  </div>
  <hr style="border: 1px solid #ccc; margin: 32px 0;">
  <p>Mit freundlichen Grüßen,<br><strong>{candidate_name}</strong></p>
</body>
</html>"""


async def send_application(
    to_email: str,
    candidate_name: str,
    company_name: str,
    subject: str,
    anschreiben: str,
    lebenslauf: str
) -> bool:
    """Отправляет заявку: Anschreiben + Lebenslauf."""
    plain_body = f"""{anschreiben}

---
LEBENSLAUF / РЕЗЮМЕ:

{lebenslauf}

---
Mit freundlichen Grüßen,
{candidate_name}
"""
    html_body = _build_html(anschreiben, lebenslauf, candidate_name)

    return await send_email(
        to_email=to_email,
        subject=subject,
        body=plain_body,
        html_body=html_body,
        from_name=candidate_name
    )


async def send_followup(
    to_email: str,
    candidate_name: str,
    company_name: str,
    subject: str,
    followup_text: str
) -> bool:
    """Отправляет follow-up письмо."""
    return await send_email(
        to_email=to_email,
        subject=subject,
        body=followup_text,
        from_name=candidate_name
    )