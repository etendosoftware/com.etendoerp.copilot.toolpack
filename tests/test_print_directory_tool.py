import tempfile
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from tools import PrintDirectoryTool
from tools.PrintDirectoryTool import PrintDirToolInput


def test_directory_exists(mocker):
    tool = PrintDirectoryTool()
    valid_dir_path = "/path/to/valid_dir"

    # Mock os.path.exists and os.listdir
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=["file1.txt", "file2.txt", "subdir"])
    mock_file1 = MagicMock()
    mock_file1.name = "file1.txt"
    mock_file1.is_file.return_value = True
    mock_file1.path = "/path/to/valid_dir/file1.txt"
    mock_file2 = MagicMock()
    mock_file2.name = "file2.txt"
    mock_file2.is_file.return_value = True
    mock_file2.path = "/path/to/valid_dir/file2.txt"
    mock_subdir = MagicMock()
    mock_subdir.name = "subdir"
    mock_subdir.is_file.return_value = False
    mock_subdir.path = "/path/to/valid_dir/subdir"
    with patch("os.scandir") as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = [mock_file1, mock_file2]
        input_params = {"path": valid_dir_path, "recursive": False}
        result = tool.run(input_params)

        expected_output = "/path/to/valid_dir/file1.txt\n/path/to/valid_dir/file2.txt\n"
        assert result["message"] == expected_output


def test_directory_does_not_exist():
    tool = PrintDirectoryTool()
    invalid_dir_path = "/path/to/nonexistent_dir"

    # Mock os.path.exists
    with patch("os.path.exists", return_value=False):
        input_params = {"path": invalid_dir_path, "recursive": False}
        result = tool.run(input_params)
        assert "error" in result
        assert result["error"] == f"Path does not exist: {invalid_dir_path}"


def test_empty_directory(mocker):
    tool = PrintDirectoryTool()

    # Mock os.path.exists and os.listdir
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=[])
    # create a empty directory in /tmp  to execute the test
    empty_dir_path = tempfile.mkdtemp(prefix="empty_dir_test")

    input_params = {"path": empty_dir_path, "recursive": False}
    result = tool.run(input_params)

    assert result["message"] == ""


def test_invalid_input_params():
    with pytest.raises(ValidationError):
        PrintDirToolInput(paaath=123, recursive="true")  # Invalid types


def test_invalid_input_params2():
    with pytest.raises(ValidationError):
        PrintDirToolInput(recursive="true")  # Invalid types
