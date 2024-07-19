import os
import pytest
from langsmith import unit, expect
from tools import WriteFileTool
from tools.WriteFileTool import WriteFileToolInput

@pytest.fixture
def setup_tool():
    return WriteFileTool()

@pytest.fixture
def filepath():
    return "/tmp/test_write_file_tool.txt"

@pytest.fixture
def new_filepath():
    return "/tmp/test_write_file_tool_new.txt"

@pytest.fixture
def file_content():
    return "Hello world"

@pytest.fixture
def file_backup_pattern():
    return "/tmp/test_write_file_tool.txt.bak"

@pytest.fixture(autouse=True)
def cleanup_files(filepath, new_filepath, file_backup_pattern):
    # Cleanup before running each test
    yield
    # Cleanup after running each test
    if os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(new_filepath):
        os.remove(new_filepath)
    # Remove backups if they were created
    for file in os.listdir("/tmp"):
        if file.startswith("test_write_file_tool.txt.bak"):
            os.remove(os.path.join("/tmp", file))

@unit
def test_write_file_successfully(setup_tool, filepath, file_content):
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": True,
        "lineno": -1
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(filepath)
    assert open(filepath).read() == file_content
    expect.value(result['message']).to_contain("File /tmp/test_write_file_tool.txt written successfully")

@unit
def test_write_file_with_backup(setup_tool, filepath, file_content, file_backup_pattern):
    open(filepath, 'w').write("Old content")
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": True,
        "lineno": -1
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(filepath)
    assert open(filepath).read() == file_content
    backups = [f for f in os.listdir("/tmp") if f.startswith("test_write_file_tool.txt.bak")]
    assert len(backups) == 1
    expect.value(result['message']).to_contain("File /tmp/test_write_file_tool.txt written successfully, backup: True")

@unit
def test_append_file_content(setup_tool, filepath, file_content):
    open(filepath, 'w').write("Old content")
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": False,
        "lineno": -1
    }
    result = setup_tool.run(input_params)
    expected_content = "Old content" + file_content
    assert os.path.exists(filepath)
    assert open(filepath).read() == expected_content

@unit
def test_insert_content_at_line(setup_tool, filepath, file_content):
    existing_content = "Line1\nLine2"
    open(filepath, 'w').write(existing_content)
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": False,
        "lineno": 1
    }
    result = setup_tool.run(input_params)
    expected_content = "Line1\nHello world\nLine2"
    assert os.path.exists(filepath)
    assert open(filepath).read() == expected_content