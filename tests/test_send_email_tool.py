import os
import pytest
from unittest.mock import patch, MagicMock
from tools import SendEmailTool
from tools.SendEmailTool import SendEmailToolInput
from langsmith import unit

try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False
    
@unit
def test_send_email_smtp(mocker):
    tool = SendEmailTool()
    input_params = {
        "subject": "Test Subject",
        "mailto": "test@example.com",
        "html": "<h1>Test Email</h1>"
    }

    # Mock environment variables
    mocker.patch.dict(os.environ, {"MAIL_METHOD": "SMTP", "MAIL_FROM": "from@example.com", "SMTP_PASSWORD": "password"})

    # Mock smtplib
    mock_smtp = mocker.patch("smtplib.SMTP")
    mock_smtp_instance = mock_smtp.return_value
    mock_smtp_instance.sendmail.return_value = None

    result = tool.run(input_params)

    assert result["message"] == "Mail sent successfully"
    mock_smtp_instance.sendmail.assert_called_once()

@unit
@pytest.mark.skipif(not HAS_RESEND, reason="resend module not available")
def test_send_email_resend(mocker):
    tool = SendEmailTool()
    input_params = {
        "subject": "Test Subject",
        "mailto": "test@example.com",
        "html": "<h1>Test Email</h1>"
    }

    # Mock environment variables
    mocker.patch.dict(os.environ, {"MAIL_METHOD": "resend", "RESEND_API_KEY": "fake_api_key"})

    # Mock resend.Emails.send
    mock_resend = mocker.patch("resend.Emails.send", return_value=None)

    result = tool.run(input_params)

    assert result["message"] == "Mail sent successfully"
    mock_resend.assert_called_once_with({
        "from": "onboarding@resend.dev",
        "to": "test@example.com",
        "subject": "[Copilot Tool Test]:Test Subject",
        "html": "<h1>Test Email</h1>"
    })

@unit
def test_mail_method_not_supported(mocker):
    tool = SendEmailTool()
    input_params = {
        "subject": "Test Subject",
        "mailto": "test@example.com",
        "html": "<h1>Test Email</h1>"
    }

    # Mock environment variables
    mocker.patch.dict(os.environ, {"MAIL_METHOD": "unsupported_method"})

    result = tool.run(input_params)

    assert result["message"] == "Mail method not supported"

@unit
def test_invalid_input_params():
    with pytest.raises(Exception):
        SendEmailToolInput(subject=123, mailto="test@example.com", html="<h1>Test Email</h1>")  # Invalid type for subject