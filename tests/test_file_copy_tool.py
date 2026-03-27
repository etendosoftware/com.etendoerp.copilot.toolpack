import os
import pytest

from tools import FileCopyTool


@pytest.fixture
def setup_files(tmp_path):
    source_file = tmp_path / "source.txt"
    destination_dir = tmp_path / "destination"
    source_file.write_text("This is a test file.")
    return source_file, destination_dir


def test_file_copy_tool_valid_input(setup_files):
    source_file, destination_dir = setup_files
    tool = FileCopyTool()

    input_data = {
        "source_path": str(source_file),
        "destination_directory": str(destination_dir),
    }

    result = tool.run(input_data)
    destination_file_path = os.path.join(destination_dir, source_file.name)

    assert os.path.exists(
        destination_file_path
    ), "The file should be copied to the destination directory."
    assert (
        result["file_path"] == destination_file_path
    ), "The returned file path should match the destination file path."


def test_file_copy_tool_invalid_source():
    tool = FileCopyTool()
    input_data = {
        "source_path": "non_existent_file.txt",
        "destination_directory": "destination_directory",
    }

    with pytest.raises(FileNotFoundError):
        tool.run(input_data)


def test_file_copy_tool_creates_destination_dir(tmp_path):
    source_file = tmp_path / "source.txt"
    source_file.write_text("test content")
    dest_dir = tmp_path / "new_dir" / "nested"

    tool = FileCopyTool()
    input_data = {
        "source_path": str(source_file),
        "destination_directory": str(dest_dir),
    }

    result = tool.run(input_data)

    assert os.path.exists(dest_dir), "The destination directory should be created."
    expected_path = os.path.join(str(dest_dir), "source.txt")
    assert result["file_path"] == expected_path
    assert open(expected_path).read() == "test content"


def test_file_copy_preserves_content(setup_files):
    source_file, destination_dir = setup_files
    tool = FileCopyTool()

    input_data = {
        "source_path": str(source_file),
        "destination_directory": str(destination_dir),
    }

    result = tool.run(input_data)
    copied_content = open(result["file_path"]).read()
    original_content = open(str(source_file)).read()

    assert copied_content == original_content
