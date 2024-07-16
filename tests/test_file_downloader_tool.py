import os
import pytest
import responses
from langsmith import unit
from tools import FileDownloaderTool

@pytest.fixture
def setup_responses():
    with responses.RequestsMock(assert_all_requests_are_fired=True, passthru_prefixes=['https://api.smith.langchain.com']) as rsps:
        yield rsps

@unit
def test_file_downloader_tool_valid_url(setup_responses):
    tool = FileDownloaderTool()
    test_url = "http://example.com/testfile.txt"

    setup_responses.add(
        responses.GET,
        test_url,
        body="This is a test file.",
        content_type="text/plain",
        status=200
    )

    result = tool.run(test_url)
    temp_file_path = result['temp_file_path']

    assert os.path.exists(temp_file_path), "The file should be downloaded and saved to a temporary file."
    with open(temp_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content == "This is a test file.", "The content of the downloaded file should match the expected content."

@unit
def test_file_downloader_tool_invalid_url(setup_responses):
    tool = FileDownloaderTool()
    test_url = "http://example.com/testfile.txt"

    setup_responses.add(
        responses.GET,
        test_url,
        status=404
    )

    result = tool.run(test_url)

    assert 'error' in result, "The result should contain an error message for an invalid URL."
    assert result['error'] == 'File could not be downloaded. Status code: 404', "The error message should indicate a 404 status code for a non-existent URL."

@unit
def test_file_downloader_tool_non_url_input():
    tool = FileDownloaderTool()
    input_data = "/path/to/local/file.txt"

    result = tool.run(input_data)

    assert 'error' in result, "The result should contain an error message for a non-URL input."
    assert result['error'] == 'The provided input is not a valid URL.', "The error message should indicate that the input is not a valid URL."