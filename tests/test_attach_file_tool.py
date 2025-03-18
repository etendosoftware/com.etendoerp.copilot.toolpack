import unittest
from unittest.mock import patch, mock_open

from tools.AttachFileTool import AttachFileTool


class TestAttachFileTool(unittest.TestCase):
    def setUp(self):
        self.valid_input = {
            "filepath": "/path/to/file.txt",
            "ad_tab_id": 123,
            "record_id": "12345678901234567890123456789012",
        }

    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"Test file content")
    @patch(
        "copilot.core.threadcontext.ThreadContext.get_data",
        return_value={"auth": {"ETENDO_TOKEN": "dummy_token"}},
    )
    @patch.object(AttachFileTool, "attach_file", return_value={"success": True})
    def test_run_success(
        self, mock_attach_file, mock_get_data, mock_open, mock_access, mock_isfile
    ):
        result = AttachFileTool().run(self.valid_input)
        self.assertEqual(result, {"success": True})

    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"Test file content")
    @patch(
        "copilot.core.threadcontext.ThreadContext.get_data",
        return_value={"auth": {"ETENDO_TOKEN": "dummy_token"}},
    )
    @patch.object(
        AttachFileTool,
        "attach_file",
        return_value={"success": False, "error": "Attachment failed"},
    )
    def test_run_attach_file_failure(
        self, mock_attach_file, mock_get_data, mock_open, mock_access, mock_isfile
    ):
        result = AttachFileTool().run(self.valid_input)
        self.assertEqual(result, {"success": False, "error": "Attachment failed"})

    @patch("os.path.isfile", return_value=False)
    def test_run_file_not_exist(self, mock_isfile):
        result = AttachFileTool().run(self.valid_input)
        self.assertEqual(result, {"error": "File does not exist or is not accessible"})

    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=False)
    def test_run_file_not_accessible(self, mock_access, mock_isfile):
        result = AttachFileTool().run(self.valid_input)
        self.assertEqual(result, {"error": "File does not exist or is not accessible"})

    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"Test file content")
    @patch("copilot.core.threadcontext.ThreadContext.get_data", return_value=None)
    def test_run_no_access_token(
        self, mock_get_data, mock_open, mock_access, mock_isfile
    ):
        try:
            AttachFileTool().run(self.valid_input)
        except Exception as e:
            self.assertIn("No access token provided", str(e))


if __name__ == "__main__":
    unittest.main()
