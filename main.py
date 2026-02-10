import os

# Get the DRY_RUN environment variable
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

# Original send_email function

def send_email(to, subject, body):
    # Logic to send email
to = recipient@example.com
subject = 'Test Email'
body = 'This is a test email.'

# Check DRY_RUN before sending email
if not DRY_RUN:
    send_email(to, subject, body)
else:
    print('Skipping email sending due to DRY_RUN environment variable being set.')