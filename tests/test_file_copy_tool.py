import os
import shutil
import pytest
from langsmith import unit
from tools import FileCopyTool

@pytest.fixture
def setup_files(tmp_path):
    source_file = tmp_path / "source.txt"
    destination_dir = tmp_path / "destination"
    source_file.write_text("This is a test file.")
    return source_file, destination_dir

@unit
def test_file_copy_tool_valid_input(setup_files):
    source_file, destination_dir = setup_files
    tool = FileCopyTool()

    input_data = {
        "source_path": str(source_file),
        "destination_directory": str(destination_dir)
    }

    result = tool.run(input_data)
    destination_file_path = os.path.join(destination_dir, source_file.name)

    assert os.path.exists(destination_file_path), "The file should be copied to the destination directory."
    assert result["file_path"] == destination_file_path, "The returned file path should match the destination file path."

@unit
def test_file_copy_tool_invalid_source():
    tool = FileCopyTool()
    input_data = {
        "source_path": "non_existent_file.txt",
        "destination_directory": "destination_directory"
    }

    try:
        result = tool.run(input_data)
    except Exception as e:
        assert isinstance(e, FileNotFoundError), "The tool should handle non-existent source file gracefully."

@unit
def test_file_copy_tool_invalid_destination(setup_files):
    source_file, _ = setup_files
    tool = FileCopyTool()
    input_data = {
        "source_path": str(source_file),
        "destination_directory": "non_existent_directory/subdir"
    }

    try:
        result = tool.run(input_data)
    except Exception as e:
        assert isinstance(e, FileNotFoundError), "The tool should handle non-existent destination directory gracefully."