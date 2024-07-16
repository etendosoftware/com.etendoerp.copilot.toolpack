import os
import pytest
from unittest import mock
from langsmith import unit
from tools import SendEmailTool

try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False

@unit
@mock.patch("smtplib.SMTP")
def test_send_email_smtp(mock_smtp):
    tool = SendEmailTool()
    os.environ["MAIL_METHOD"] = "SMTP"
    os.environ["MAIL_FROM"] = "test@example.com"
    os.environ["SMTP_PASSWORD"] = "password"

    result = tool.run(input={"subject": "Test Subject", "mailto": "recipient@example.com", "html": "<p>Test Email</p>"})

    # Verify that the email was sent
    assert result["message"] == "Mail sent successfully"

    # Verify that SMTP was called correctly
    mock_smtp.assert_called_with('smtp.gmail.com', 587)
    instance = mock_smtp.return_value
    instance.starttls.assert_called_once()
    instance.login.assert_called_once_with("test@example.com", "password")
    instance.sendmail.assert_called_once()

if HAS_RESEND:
    @unit
    @mock.patch("resend.Emails.send")
    def test_send_email_resend(mock_resend_send):
        tool = SendEmailTool()
        os.environ["MAIL_METHOD"] = "resend"
        os.environ["RESEND_API_KEY"] = "test_api_key"

        result = tool.run(input={"subject": "Test Subject", "mailto": "recipient@example.com", "html": "<p>Test Email</p>"})

        # Verify that the mail was sent
        assert result["message"] == "Mail sent successfully"

        # Verify that resend was called correctly
        mock_resend_send.assert_called_once_with({
            "from": "onboarding@resend.dev",
            "to": "recipient@example.com",
            "subject": '[Copilot Tool Test]:Test Subject',
            "html": "<p>Test Email</p>"
        })

@unit
def test_send_email_unsupported_method():
    tool = SendEmailTool()
    os.environ["MAIL_METHOD"] = "unsupported"

    result = tool.run(input={"subject": "Test Subject", "mailto": "recipient@example.com", "html": "<p>Test Email</p>"})

    assert result["message"] == "Mail method not supported"

@unit
def test_send_email_invalid_input():
    tool = SendEmailTool()

    with pytest.raises(ValueError):
        tool.run(input="Invalid JSON String")
