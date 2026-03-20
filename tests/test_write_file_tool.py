import os
import pytest
from tools import WriteFileTool


@pytest.fixture
def setup_tool():
    return WriteFileTool()


@pytest.fixture
def filepath(tmp_path):
    return str(tmp_path / "test_write_file_tool.txt")


@pytest.fixture
def new_filepath(tmp_path):
    return str(tmp_path / "test_write_file_tool_new.txt")


@pytest.fixture
def file_content():
    return "Hello world"


@pytest.fixture(autouse=True)
def cleanup_files(filepath, new_filepath, tmp_path):
    yield
    if os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(new_filepath):
        os.remove(new_filepath)
    for file in os.listdir(str(tmp_path)):
        if file.startswith("test_write_file_tool.txt.bak"):
            os.remove(os.path.join(str(tmp_path), file))


def test_write_file_successfully(setup_tool, filepath, file_content):
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": True,
        "lineno": -1,
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(filepath)
    assert open(filepath).read() == file_content
    assert "written successfully" in result["message"]


def test_write_file_with_backup(setup_tool, filepath, file_content, tmp_path):
    open(filepath, "w").write("Old content")
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": True,
        "lineno": -1,
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(filepath)
    assert open(filepath).read() == file_content
    backups = [
        f
        for f in os.listdir(str(tmp_path))
        if f.startswith("test_write_file_tool.txt.bak")
    ]
    assert len(backups) == 1
    assert "written successfully, backup: True" in result["message"]


def test_append_file_content(setup_tool, filepath, file_content):
    open(filepath, "w").write("Old content")
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": False,
        "lineno": -1,
    }
    setup_tool.run(input_params)
    expected_content = "Old content" + file_content
    assert os.path.exists(filepath)
    assert open(filepath).read() == expected_content


def test_insert_content_at_line(setup_tool, filepath, file_content):
    existing_content = "Line1\nLine2"
    open(filepath, "w").write(existing_content)
    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": False,
        "lineno": 1,
    }
    setup_tool.run(input_params)
    expected_content = "Line1\nHello world\nLine2"
    assert os.path.exists(filepath)
    assert open(filepath).read() == expected_content


def test_write_creates_folder(setup_tool, tmp_path, file_content):
    nested_path = str(tmp_path / "new_dir" / "sub" / "file.txt")
    input_params = {
        "filepath": nested_path,
        "content": file_content,
        "override": True,
        "lineno": -1,
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(nested_path)
    assert open(nested_path).read() == file_content
    assert "written successfully" in result["message"]


def test_write_with_chmod(setup_tool, tmp_path, file_content, mocker):
    nested_path = str(tmp_path / "chmod_dir" / "file.txt")
    mocker.patch(
        "tools.WriteFileTool.read_optional_env_var", return_value="0o666"
    )
    mock_chmod = mocker.patch("os.chmod")

    input_params = {
        "filepath": nested_path,
        "content": file_content,
        "override": True,
        "lineno": -1,
    }
    result = setup_tool.run(input_params)
    assert os.path.exists(nested_path)
    assert mock_chmod.call_count >= 2  # folder + file
    assert "written successfully" in result["message"]


def test_write_with_chmod_existing_file(setup_tool, filepath, file_content, mocker):
    open(filepath, "w").write("Old content")
    mocker.patch(
        "tools.WriteFileTool.read_optional_env_var", return_value="0o644"
    )
    mock_chmod = mocker.patch("os.chmod")

    input_params = {
        "filepath": filepath,
        "content": file_content,
        "override": True,
        "lineno": -1,
    }
    result = setup_tool.run(input_params)
    assert open(filepath).read() == file_content
    assert mock_chmod.call_count >= 1  # file chmod
    assert "backup: True" in result["message"]
