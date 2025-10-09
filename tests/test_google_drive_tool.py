import pytest
from unittest.mock import patch
from tools.GoogleDriveTool import GoogleDriveTool, GoogleDriveToolInput


class TestGoogleDriveTool:
    """Test suite for GoogleDriveTool"""

    def setup_method(self):
        """Setup method called before each test"""
        self.tool = GoogleDriveTool()

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_list_mode_success(self, mock_service_util):
        """Test successful file listing in list mode"""
        # Mock the service util response
        mock_files = [
            {"id": "file1", "name": "Document 1"},
            {"id": "file2", "name": "Document 2"},
        ]
        mock_service_util.list_accessible_files.return_value = mock_files

        # Test input parameters
        input_params = {"alias": "test_token", "mode": "list", "file_type": "doc"}

        result = self.tool.run(input_params)

        # Assertions - check if it's a dict with 'message' key (ToolOutputMessage)
        assert isinstance(result, dict)
        assert "message" in result
        assert "📂 Files of type 'doc':" in result["message"]
        assert "Document 1 (ID: file1)" in result["message"]
        assert "Document 2 (ID: file2)" in result["message"]
        mock_service_util.list_accessible_files.assert_called_once_with(
            "doc", "test_token"
        )

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_list_mode_no_files_found(self, mock_service_util):
        """Test list mode when no files are found"""
        mock_service_util.list_accessible_files.return_value = []

        input_params = {"alias": "test_token", "mode": "list", "file_type": "pdf"}

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "message" in result
        assert result["message"] == "No files of type 'pdf' found."
        mock_service_util.list_accessible_files.assert_called_once_with(
            "pdf", "test_token"
        )

    def test_list_mode_missing_file_type(self):
        """Test list mode with missing file_type parameter"""
        input_params = {
            "alias": "test_token",
            "mode": "list",
            # file_type is missing
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "Missing 'file_type' parameter for list mode" in result["error"]

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_upload_mode_success(self, mock_service_util):
        """Test successful file upload in upload mode"""
        mock_uploaded_file = {"id": "uploaded_file_id", "name": "uploaded_file.pdf"}
        mock_service_util.upload_file_simple.return_value = mock_uploaded_file

        input_params = {
            "alias": "test_token",
            "mode": "upload",
            "file_path": "/path/to/local/file.pdf",
            "name": "My Uploaded File",
            "mime_type": "application/pdf",
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "message" in result
        assert "✅ File 'uploaded_file.pdf' uploaded successfully" in result["message"]
        assert (
            "🔗 Link: https://drive.google.com/file/d/uploaded_file_id/view"
            in result["message"]
        )
        mock_service_util.upload_file_simple.assert_called_once_with(
            "test_token",
            "/path/to/local/file.pdf",
            "My Uploaded File",
            "application/pdf",
        )

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_upload_mode_default_name(self, mock_service_util):
        """Test upload mode using default name from file path"""
        mock_uploaded_file = {"id": "uploaded_file_id", "name": "file.pdf"}
        mock_service_util.upload_file_simple.return_value = mock_uploaded_file

        input_params = {
            "alias": "test_token",
            "mode": "upload",
            "file_path": "/path/to/file.pdf",
            # name and mime_type not provided
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "message" in result
        mock_service_util.upload_file_simple.assert_called_once_with(
            "test_token",
            "/path/to/file.pdf",
            "file.pdf",  # Default name extracted from path
            "application/octet-stream",  # Default mime type
        )

    def test_upload_mode_missing_file_path(self):
        """Test upload mode with missing file_path parameter"""
        input_params = {
            "alias": "test_token",
            "mode": "upload",
            # file_path is missing
        }

        result = self.tool.run(input_params)

        # This should fail because file_path will be None and cause an exception
        assert isinstance(result, dict)
        assert "error" in result
        assert "GoogleDriveTool error:" in result["error"]

    def test_unsupported_mode(self):
        """Test unsupported mode parameter"""
        input_params = {"alias": "test_token", "mode": "invalid_mode"}

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "Unsupported mode: 'invalid_mode'" in result["error"]
        assert "Use 'list' or 'upload'" in result["error"]

    def test_case_insensitive_mode(self):
        """Test that mode parameter is case insensitive"""
        input_params = {"alias": "test_token", "mode": "LIST"}  # uppercase

        result = self.tool.run(input_params)

        # Should fail due to missing file_type, but mode should be converted to lowercase
        assert isinstance(result, dict)
        assert "error" in result
        assert "Missing 'file_type' parameter for list mode" in result["error"]

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_list_mode_exception_handling(self, mock_service_util):
        """Test exception handling in list mode"""
        mock_service_util.list_accessible_files.side_effect = Exception("API Error")

        input_params = {"alias": "test_token", "mode": "list", "file_type": "doc"}

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "❌ GoogleDriveTool error: API Error" in result["error"]

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_upload_mode_exception_handling(self, mock_service_util):
        """Test exception handling in upload mode"""
        mock_service_util.upload_file_simple.side_effect = Exception("Upload failed")

        input_params = {
            "alias": "test_token",
            "mode": "upload",
            "file_path": "/path/to/file.pdf",
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "❌ GoogleDriveTool error: Upload failed" in result["error"]

    def test_missing_alias_parameter(self):
        """Test behavior when alias parameter is missing"""
        input_params = {
            "mode": "list",
            "file_type": "doc",
            # alias is missing
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "GoogleDriveTool error:" in result["error"]

    def test_missing_mode_parameter(self):
        """Test behavior when mode parameter is missing"""
        input_params = {
            "alias": "test_token"
            # mode is missing
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "error" in result
        assert "GoogleDriveTool error:" in result["error"]

    def test_none_input_params(self):
        """Test behavior with None input parameters"""
        result = self.tool.run(input_params=None)  # type: ignore

        assert isinstance(result, dict)
        assert "error" in result
        assert "GoogleDriveTool error:" in result["error"]

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_upload_mode_with_special_characters_in_path(self, mock_service_util):
        """Test upload mode with special characters in file path"""
        mock_uploaded_file = {"id": "uploaded_file_id", "name": "file with spaces.pdf"}
        mock_service_util.upload_file_simple.return_value = mock_uploaded_file

        input_params = {
            "alias": "test_token",
            "mode": "upload",
            "file_path": "/path/to/file with spaces.pdf",
        }

        result = self.tool.run(input_params)

        assert isinstance(result, dict)
        assert "message" in result
        mock_service_util.upload_file_simple.assert_called_once_with(
            "test_token",
            "/path/to/file with spaces.pdf",
            "file with spaces.pdf",  # Name extracted correctly
            "application/octet-stream",
        )

    @patch("tools.GoogleServiceUtil.GoogleServiceUtil")
    def test_list_mode_different_file_types(self, mock_service_util):
        """Test list mode with different file types"""
        file_types = ["spreadsheet", "doc", "pdf", "slides"]

        for file_type in file_types:
            mock_files = [{"id": f"file_{file_type}", "name": f"Test {file_type}"}]
            mock_service_util.list_accessible_files.return_value = mock_files

            input_params = {
                "alias": "test_token",
                "mode": "list",
                "file_type": file_type,
            }

            result = self.tool.run(input_params)

            assert isinstance(result, dict)
            assert "message" in result
            assert f"Files of type '{file_type}':" in result["message"]
            mock_service_util.list_accessible_files.assert_called_with(
                file_type, "test_token"
            )


class TestGoogleDriveToolInput:
    """Test suite for GoogleDriveToolInput class"""

    def test_tool_attributes(self):
        """Test GoogleDriveTool class attributes"""
        tool = GoogleDriveTool()

        assert tool.name == "GoogleDriveTool"
        assert "list" in tool.description
        assert "upload" in tool.description
        assert tool.args_schema == GoogleDriveToolInput
        assert tool.return_direct is False

    def test_input_schema_creation(self):
        """Test that GoogleDriveToolInput can be created with valid parameters"""
        # Test with minimal required parameters
        input_obj = GoogleDriveToolInput(alias="test_token", mode="list")
        assert input_obj.alias == "test_token"
        assert input_obj.mode == "list"
        assert input_obj.file_type == "spreadsheet"  # default value

    def test_input_schema_with_all_parameters(self):
        """Test GoogleDriveToolInput with all parameters"""
        input_obj = GoogleDriveToolInput(
            alias="test_token",
            mode="upload",
            file_type="pdf",
            file_path="/path/to/file.pdf",
            name="My File",
            mime_type="application/pdf",
        )
        assert input_obj.alias == "test_token"
        assert input_obj.mode == "upload"
        assert input_obj.file_type == "pdf"
        assert input_obj.file_path == "/path/to/file.pdf"
        assert input_obj.name == "My File"
        assert input_obj.mime_type == "application/pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
