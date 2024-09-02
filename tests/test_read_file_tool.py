from unittest.mock import mock_open

import pytest
from langchain_core.pydantic_v1 import ValidationError
from langsmith import unit

from tools import ReadFileTool
from tools.ReadFileTool import ReadFileToolInput


@unit
def test_read_existing_file(mocker):
    tool = ReadFileTool()
    valid_file_path = "/path/to/test.txt"
    file_content = "This is a test file content."

    # Mock open
    mocker.patch("builtins.open", mock_open(read_data=file_content))
    # Mock os.path.exists to return True
    mocker.patch("os.path.exists", return_value=True)

    input_params = {"filepath": valid_file_path}
    result = tool.run(input_params)

    assert result["message"] == file_content


@unit
def test_file_does_not_exist(mocker):
    tool = ReadFileTool()
    invalid_file_path = "/path/to/nonexistent.txt"

    # Mock open to raise FileNotFoundError
    mocker.patch("builtins.open", side_effect=FileNotFoundError)
    # Mock os.path.exists to return False
    mocker.patch("os.path.exists", return_value=False)

    input_params = {"filepath": invalid_file_path}
    with pytest.raises(FileNotFoundError):
        tool.run(input_params)


@unit
def test_read_empty_file(mocker):
    tool = ReadFileTool()
    empty_file_path = "/path/to/empty.txt"
    file_content = ""

    # Mock open
    mocker.patch("builtins.open", mock_open(read_data=file_content))
    # Mock os.path.exists to return True
    mocker.patch("os.path.exists", return_value=True)

    input_params = {"filepath": empty_file_path}
    result = tool.run(input_params)

    assert result["message"] == file_content


@unit
def test_invalid_input_params():
    with pytest.raises(ValidationError):
        ReadFileToolInput(fil=123)  # Invalid type for filepath


@unit
def test_invalid_input_params():
    with pytest.raises(ValidationError):
        ReadFileToolInput()  # Invalid type for filepath
