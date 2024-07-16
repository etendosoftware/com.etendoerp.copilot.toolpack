import os
import pytest
from langsmith import unit
from tools import PrintDirectoryTool

@pytest.fixture
def setup_test_directory(tmp_path):
    d = tmp_path / "test_dir"
    d.mkdir()

    sub_dir = d / "sub_dir"
    sub_dir.mkdir()

    file1 = d / "file1.txt"
    file1.write_text("content of file1")

    file2 = sub_dir / "file2.txt"
    file2.write_text("content of file2")

    return d

@unit
def test_print_directory_non_recursive(setup_test_directory):
    test_dir = setup_test_directory
    os.chdir(test_dir)

    tool = PrintDirectoryTool()
    result = tool.run(inputs={"recursive": False, "parent_doubledot_qty": 0})

    # Ensure both files and directories from the specified directory are listed
    assert len(result["message"]) == 2
    assert any("file1.txt" in os.path.basename(entry) for entry in result["message"])
    assert any("sub_dir" in os.path.basename(entry) for entry in result["message"])

@unit
def test_print_directory_recursive(setup_test_directory):
    test_dir = setup_test_directory
    os.chdir(test_dir)

    tool = PrintDirectoryTool()
    result = tool.run(inputs={"recursive": True, "parent_doubledot_qty": 0})

    # Ensure all files including subdirectories are listed
    assert len(result["message"]) == 2
    assert any("file1.txt" in path for path in result["message"])
    assert any("file2.txt" in path for path in result["message"])

@unit
def test_print_parent_directory(setup_test_directory):
    parent_dir = setup_test_directory
    os.chdir(parent_dir / "sub_dir")

    tool = PrintDirectoryTool()
    result = tool.run(inputs={"recursive": False, "parent_doubledot_qty": 1})

    # Ensure both files and directories from the parent directory are listed
    assert len(result["message"]) == 2
    assert any("file1.txt" in os.path.basename(entry) for entry in result["message"])
    assert any("sub_dir" in os.path.basename(entry) for entry in result["message"])

@unit
def test_print_parent_directory_recursive(setup_test_directory):
    parent_dir = setup_test_directory
    os.chdir(parent_dir / "sub_dir")

    tool = PrintDirectoryTool()
    result = tool.run(inputs={"recursive": True, "parent_doubledot_qty": 1})

    # Ensure all files including subdirectories of the parent directory are listed
    assert len(result["message"]) == 2
    assert any("file1.txt" in path for path in result["message"])
    assert any("file2.txt" in path for path in result["message"])