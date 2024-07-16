import os
import pytest
from langsmith import unit
from tools import ReadFileTool


@pytest.fixture
def setup_test_directory(tmp_path):
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("This is a test file.")
    return file_path


@unit
def test_read_existing_file(setup_test_directory):
    tool = ReadFileTool()
    file_path = str(setup_test_directory)
    result = tool.run(input={"filepath": file_path})

    assert result["message"] == "This is a test file."


@unit
def test_read_existing_file_from_string_path(setup_test_directory):
    tool = ReadFileTool()
    file_path = str(setup_test_directory)
    result = tool.run(input=file_path)

    assert result["message"] == "This is a test file."


@unit
def test_read_non_existing_file():
    tool = ReadFileTool()
    non_existing_file_path = "/non/existing/file/path.txt"

    with pytest.raises(FileNotFoundError):
        tool.run(input={"filepath": non_existing_file_path})