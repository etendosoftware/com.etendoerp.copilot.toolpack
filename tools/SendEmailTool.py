import os
from typing import Type, Dict

from copilot.core.tool_wrapper import ToolWrapper
from pydantic import BaseModel, Field


class SendEmailToolInput(BaseModel):
    subject: str = Field(description="Subject of the email")
    mailto: str = Field(description="Email address of the recipient")
    html: str = Field(description="HTML content of the email")


class SendEmailTool(ToolWrapper):
    name = 'SendEmailTool'
    description = (''' This tool sends an email using the SMTP method or the Resend method.
    It is very important not to omit information, because the email is sent to another person and
    the information must be clear and concise, and not summarized.
    ''')
    args_schema: Type[BaseModel] = SendEmailToolInput

    def run(self, input_params: Dict, *args, **kwargs):
        try:
            import json

            # if json is a string, convert it to json, else, use the json

            p_subject = input_params.get('subject')
            p_to = input_params.get('mailto')
            p_html = input_params.get('html')

            # print arguments
            print("Subject: " + p_subject)
            print("To: " + p_to)
            print("Html: " + p_html)

            # print extra arguments
            print("Extra arguments: " + str(args))
            # print extra keyword arguments
            print("Extra keyword arguments: " + str(kwargs))
            mail_method = os.getenv("MAIL_METHOD", "SMTP")
            if mail_method == "resend":
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
            elif mail_method == "SMTP":
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

            return {"message": "Mail sent successfully"}
        except Exception as e:
            return {"message": "Error: " + str(e)}