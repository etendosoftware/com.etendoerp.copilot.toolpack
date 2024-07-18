from unittest.mock import patch

import pytest
from langsmith import unit

from tools import PrintDirectoryTool
from tools.PrintDirectoryTool import PrintDirToolInput


@unit
def test_directory_exists(mocker):
    tool = PrintDirectoryTool()
    valid_dir_path = "/path/to/valid_dir"

    # Mock os.path.exists and os.listdir
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=["file1.txt", "file2.txt", "subdir"])

    input_params = {"path": valid_dir_path, "recursive": False}
    result = tool.run(input_params)

    expected_output = f"/path/to/valid_dir/file1.txt\n/path/to/valid_dir/file2.txt\n/path/to/valid_dir/subdir\n"
    assert result["message"] == expected_output


@unit
def test_directory_does_not_exist():
    tool = PrintDirectoryTool()
    invalid_dir_path = "/path/to/nonexistent_dir"

    # Mock os.path.exists
    with patch("os.path.exists", return_value=False):
        input_params = {"path": invalid_dir_path, "recursive": False}
        result = tool.run(input_params)
        assert "error" in result
        assert result["error"] == f"Path does not exist: {invalid_dir_path}"


@unit
def test_empty_directory(mocker):
    tool = PrintDirectoryTool()
    empty_dir_path = "/path/to/empty_dir"

    # Mock os.path.exists and os.listdir
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=[])

    input_params = {"path": empty_dir_path, "recursive": False}
    result = tool.run(input_params)

    assert result["message"] == ""


@unit
def test_invalid_input_params():
    with pytest.raises(Exception):
        PrintDirToolInput(path=123, recursive="true")  # Invalid types
