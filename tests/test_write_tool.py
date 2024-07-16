import os
import pytest
from unittest import mock
from langsmith import unit
from tools import WriteFileTool

@pytest.fixture
def setup_test_directory(tmp_path):
    test_file_path = tmp_path / "test_file.txt"
    test_file_path.write_text("Initial content\nSecond line")
    return test_file_path

@unit
def test_write_file_tool_override(setup_test_directory):
    tool = WriteFileTool()
    file_path = str(setup_test_directory)
    
    input_data = {
        "filepath": file_path,
        "content": "New content",
        "override": True,
        "lineno": -1
    }
    
    result = tool.run(input=input_data)
    expected_message = f"File {file_path} written successfully, backup: True"
    
    assert result["message"] == expected_message
    assert setup_test_directory.read_text() == "Initial content\nSecond lineNew content"

@unit
def test_write_file_tool_append(setup_test_directory):
    tool = WriteFileTool()
    file_path = str(setup_test_directory)
    
    input_data = {
        "filepath": file_path,
        "content": "Appended content",
        "override": False,
        "lineno": -1
    }
    
    result = tool.run(input=input_data)
    expected_message = f"File {file_path} written successfully, backup: True"
    
    assert result["message"] == expected_message
    assert setup_test_directory.read_text() == "Initial content\nSecond lineAppended content"

@unit
def test_write_file_tool_write_at_lineno(setup_test_directory):
    tool = WriteFileTool()
    file_path = str(setup_test_directory)
    
    input_data = {
        "filepath": file_path,
        "content": "Inserted content",
        "override": True,
        "lineno": 1
    }
    
    result = tool.run(input=input_data)
    expected_message = f"File {file_path} written successfully, backup: True"
    
    assert result["message"] == expected_message
    assert setup_test_directory.read_text() == "Initial content\nInserted content\nSecond line"

@unit
def test_write_file_tool_invalid_json():
    tool = WriteFileTool()
    input_data = "Invalid JSON string"
    
    result = tool.run(input=input_data)
    assert result["message"] == 'Invalid input. Example of input: { "filepath": "/tmp/test.txt", "content": "Hello world", "lineno": 1 }'

@unit
def test_write_file_tool_create_new_file(tmp_path):
    tool = WriteFileTool()
    file_path = str(tmp_path / "new_test_file.txt")
    
    input_data = {
        "filepath": file_path,
        "content": "New file content",
        "override": False,
        "lineno": -1
    }
    
    result = tool.run(input=input_data)
    
    expected_message = f"File {file_path} written successfully, backup: False"
    
    assert result["message"] == expected_message
    assert open(file_path).read() == "New file content"
