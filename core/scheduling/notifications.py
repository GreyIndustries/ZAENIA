"""Owner-configured channels; no addresses or destinations come from a model."""
import os
import ssl
import smtplib
from email.message import EmailMessage
from urllib.request import Request,urlopen
import json

def send(body):
    label = 'now' if body['minutes']==0 else f"in {body['minutes']} minutes"
    text = f"ZÆNIA: {body['title']} — {label}. Scheduled: {body['start']}"
    channel = body['channel']
    if channel == 'console':
        print(text,flush=True)
    elif channel == 'email':
        host = os.environ['ZAENIA_SMTP_HOST']
        recipient = os.environ['ZAENIA_OWNER_EMAIL']
        sender = os.environ['ZAENIA_SMTP_USER']
        message = EmailMessage()
        message['From'],message['To'],message['Subject'] = sender,recipient,'ZÆNIA reminder'
        # Deterministic ID helps some receivers; SMTP cannot guarantee deduplication.
        import hashlib
        message['Message-ID'] = '<'+hashlib.sha256(body['delivery_id'].encode()).hexdigest()+'@zaenia.local>'
        message.set_content(text)
        with smtplib.SMTP_SSL(host,int(os.environ.get('ZAENIA_SMTP_PORT','465')),timeout=30,context=ssl.create_default_context()) as smtp:
            smtp.login(sender,os.environ['ZAENIA_SMTP_PASSWORD'])
            smtp.send_message(message)
    elif channel == 'phone':
        # ntfy-compatible HTTPS endpoint, configured locally by the owner.
        url = os.environ['ZAENIA_PHONE_TOPIC_URL']
        if not url.startswith('https://'): raise ValueError('Phone endpoint requires HTTPS.')
        headers = {'Content-Type':'text/plain; charset=utf-8','Title':'ZAENIA reminder'}
        token = os.environ.get('ZAENIA_PHONE_TOKEN')
        if token: headers['Authorization']='Bearer '+token
        with urlopen(Request(url,data=text.encode(),headers=headers,method='POST'),timeout=30) as response:
            if not 200 <= response.status < 300: raise RuntimeError('Push failed.')
    else:
        raise ValueError('Unknown notification channel.')
