import os
from langsmith import traceable

from copilot.core.tool_wrapper import ToolWrapper


class SendEmailTool(ToolWrapper):
    name = 'SendEmailTool'
    description = ('This is the SendMail tool, for sending mails.'
                   ' This is the best way to send emails. '
                   'Receives  "subject", "mailto" and "html" string parameters. '
                   'The "subject" parameters is the subject of the email. '
                   'The "mailto" parameters is the email address of the recipient.'
                   'The "html" parameters is the html of the email. ')
    inputs = ['subject', 'mailto', 'html']
    outputs = ['message']

    @traceable
    def run(self, input, *args, **kwargs):
        import json

        # if json is a string, convert it to json, else, use the json
        if isinstance(input, str):
            json = json.loads(input)
        else:
            json = input
        p_subject = json.get('subject')
        p_to = json.get('mailto')
        p_html = json.get('html')

        # print arguments
        print("Subject: " + p_subject)
        print("To: " + p_to)
        print("Html: " + p_html)

        # print extra arguments
        print("Extra arguments: " + str(args))
        # print extra keyword arguments
        print("Extra keyword arguments: " + str(kwargs))
        mail_method = os.getenv("MAIL_METHOD", "SMTP")
        if (mail_method == "resend"):
            import resend
            resend.api_key = os.getenv("RESEND_API_KEY")
            print("Sending mail to: " + p_to + " with subject: " + p_subject + " and html: " + p_html)
            # Send an email
            r = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": p_to,
                "subject": '[Copilot Tool Test]:' + p_subject,
                "html": p_html
            })
        elif (mail_method == "SMTP"):
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders

            fromaddr = os.getenv("MAIL_FROM")
            toaddr = p_to
            msg = MIMEMultipart()
            msg['From'] = fromaddr
            msg['To'] = toaddr
            msg['Subject'] = p_subject
            body = p_html
            msg.attach(MIMEText(body, 'html'))
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(fromaddr, os.getenv("SMTP_PASSWORD", "SMTP"))
            text = msg.as_string()
            server.sendmail(fromaddr, toaddr, text)
            server.quit()
        else:
            return {"message": "Mail method not supported"}

        return {"message": "Mail sent successfully" }


